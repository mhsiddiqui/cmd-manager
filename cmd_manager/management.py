import asyncio
import importlib
import inspect
import pkgutil
import threading
import warnings
from importlib.metadata import entry_points
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Type

import click

from cmd_manager.argument import Argument
from cmd_manager.command import AsyncBaseCommand, BaseCommand


class ManagementCommandSystem:
    """Discover :class:`BaseCommand` subclasses and expose them as a Click CLI.

    Commands can be sourced from a Python package (:meth:`register`),
    from installed plugins advertising entry points
    (:meth:`register_entry_points`), or registered individually via
    :meth:`register_command` / the :meth:`command` decorator.
    """

    DEFAULT_ENTRY_POINT_GROUP = "cmd_manager.commands"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Default constructor args are forwarded to every command's ``__init__``.

        Per-package overrides are available on :meth:`register` and
        :meth:`register_command`.
        """
        self.args = args
        self.kwargs = kwargs
        self.commands: List[click.Command] = []
        self._command_specs: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    def register(
        self,
        prefix: str = "",
        package: str = "scripts",
        *,
        recursive: bool = False,
        init_args: Optional[Sequence[Any]] = None,
        init_kwargs: Optional[Dict[str, Any]] = None,
        on_error: str = "raise",
    ) -> None:
        """Discover commands inside *package* and register each one.

        :param prefix: String prepended to every command name (useful when
            integrating multiple packages that share command names).
        :param package: Dotted name of a Python package to scan.
        :param recursive: When ``True``, descend into sub-packages. Nested
            module paths are flattened into command names with ``-``.
        :param init_args: Override the constructor positional args used when
            instantiating commands from this package.
        :param init_kwargs: Override the constructor keyword args.
        :param on_error: Behaviour when a module fails to import. One of
            ``"raise"`` (default), ``"warn"``, ``"ignore"``.
        """
        if on_error not in {"raise", "warn", "ignore"}:
            raise ValueError("on_error must be one of: raise, warn, ignore")

        package_module = importlib.import_module(package)
        if not hasattr(package_module, "__path__"):
            raise ValueError(f"{package!r} is not a package")

        chosen_args = self.args if init_args is None else tuple(init_args)
        chosen_kwargs = self.kwargs if init_kwargs is None else dict(init_kwargs)

        for full_name in self._iter_module_names(package_module.__path__, package, recursive):
            try:
                module = importlib.import_module(full_name)
            except Exception as exc:
                if on_error == "raise":
                    raise
                if on_error == "warn":
                    warnings.warn(f"Failed to import {full_name}: {exc}")
                continue

            command_class = getattr(module, "Command", None)
            if not (isinstance(command_class, type) and issubclass(command_class, BaseCommand)):
                continue

            short_name = full_name[len(package) + 1 :].replace(".", "-")
            self.register_command(
                command_class,
                name=f"{prefix}{short_name}",
                init_args=chosen_args,
                init_kwargs=chosen_kwargs,
            )

    @staticmethod
    def _iter_module_names(paths: Iterable[str], package: str, recursive: bool) -> Iterable[str]:
        if recursive:
            for info in pkgutil.walk_packages(paths, prefix=f"{package}."):
                if info.ispkg:
                    continue
                yield info.name
        else:
            for _, module_name, ispkg in pkgutil.iter_modules(paths):
                if ispkg:
                    continue
                yield f"{package}.{module_name}"

    def register_entry_points(
        self, group: str = DEFAULT_ENTRY_POINT_GROUP, prefix: str = ""
    ) -> None:
        """Register commands advertised by installed plugins via entry points.

        Plugin packages declare entries under *group* (default
        ``cmd_manager.commands``) pointing at a :class:`BaseCommand` subclass::

            [project.entry-points."cmd_manager.commands"]
            greet = "my_pkg.scripts.greet:Command"
        """
        eps = entry_points()
        if hasattr(eps, "select"):
            selected = eps.select(group=group)
        else:  # pragma: no cover - legacy Python compatibility
            selected = eps.get(group, [])  # type: ignore[attr-defined]

        for ep in selected:
            command_class = ep.load()
            if not (isinstance(command_class, type) and issubclass(command_class, BaseCommand)):
                warnings.warn(f"Entry point {ep.name!r} does not resolve to a BaseCommand")
                continue
            self.register_command(command_class, name=f"{prefix}{ep.name}")

    def command(
        self,
        name: Optional[str] = None,
        *,
        arguments: Sequence[Argument] = (),
        help: Optional[str] = None,
        aliases: Sequence[str] = (),
        hidden: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator that registers a plain function as a command.

        Works with both sync and async functions::

            @system.command("greet", arguments=[Argument.option("--name")])
            def greet(name): ...

            @system.command()
            async def fetch(url): ...
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            is_async = asyncio.iscoroutinefunction(func)
            cmd_name = name or func.__name__.replace("_", "-")
            base = AsyncBaseCommand if is_async else BaseCommand

            if is_async:

                async def _run(self, *a: Any, **kw: Any) -> Any:
                    return await func(*a, **kw)

            else:

                def _run(self, *a: Any, **kw: Any) -> Any:
                    return func(*a, **kw)

            attrs: Dict[str, Any] = {
                "arguments": tuple(arguments),
                "aliases": tuple(aliases),
                "hidden": hidden,
                "help": help,
                "run": _run,
                "__doc__": func.__doc__,
            }
            command_class = type(f"_FunctionCommand_{cmd_name}", (base,), attrs)
            self.register_command(command_class, name=cmd_name)
            return func

        return decorator

    # ------------------------------------------------------------------ #
    # Single-command registration
    # ------------------------------------------------------------------ #

    def register_command(
        self,
        command_class: Type[BaseCommand],
        name: Optional[str] = None,
        *,
        init_args: Optional[Sequence[Any]] = None,
        init_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a single :class:`BaseCommand` subclass."""
        chosen_args = self.args if init_args is None else tuple(init_args)
        chosen_kwargs = self.kwargs if init_kwargs is None else dict(init_kwargs)

        instance = command_class(*chosen_args, **chosen_kwargs)
        cmd_name = name or command_class.name or command_class.__name__.lower()
        arguments = list(instance.get_arguments())

        own_doc = command_class.__dict__.get("__doc__") or ""
        help_text = command_class.help or inspect.cleandoc(own_doc) or None

        is_async = isinstance(instance, AsyncBaseCommand) or asyncio.iscoroutinefunction(
            instance.run
        )

        click_command = self._build_click_command(
            cmd_name,
            instance,
            arguments,
            help_text=help_text,
            short_help=command_class.short_help,
            hidden=command_class.hidden,
            is_async=is_async,
        )

        self.commands.append(click_command)
        self._command_specs.append(
            {
                "name": cmd_name,
                "help": help_text,
                "aliases": list(command_class.aliases),
                "hidden": command_class.hidden,
            }
        )

        for alias in command_class.aliases:
            alias_command = self._build_click_command(
                alias,
                instance,
                arguments,
                help_text=f"Alias for {cmd_name}.",
                short_help=None,
                hidden=True,
                is_async=is_async,
            )
            self.commands.append(alias_command)

    def _build_click_command(
        self,
        name: str,
        instance: BaseCommand,
        arguments: Sequence[Argument],
        *,
        help_text: Optional[str],
        short_help: Optional[str],
        hidden: bool,
        is_async: bool,
    ) -> click.Command:
        @click.command(name, help=help_text, short_help=short_help, hidden=hidden)
        @self._add_arguments(arguments)
        def click_command(*args: Any, **kwargs: Any) -> Any:
            return self._invoke(instance, args, kwargs, is_async=is_async)

        return click_command

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #

    @staticmethod
    def _invoke(
        instance: BaseCommand,
        args: tuple,
        kwargs: dict,
        *,
        is_async: bool,
    ) -> Any:
        if is_async:
            return _run_async(_run_async_lifecycle(instance, args, kwargs))

        instance.setup()
        exc: Optional[BaseException] = None
        try:
            return instance.run(*args, **kwargs)
        except BaseException as e:
            exc = e
            raise
        finally:
            instance.teardown(exc)

    def _add_arguments(
        self, arguments: Sequence[Argument]
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            for arg in reversed(list(arguments)):
                func = arg.apply(func)
            return func

        return decorator

    # ------------------------------------------------------------------ #
    # CLI assembly
    # ------------------------------------------------------------------ #

    def create_cli(self, include_list_command: bool = True) -> click.Group:
        """Build a Click group containing every registered command.

        :param include_list_command: When ``True`` (default), add a built-in
            ``list`` subcommand that prints all visible commands.
        """

        @click.group()
        def cli() -> None:
            pass

        for command in self.commands:
            cli.add_command(command)

        if include_list_command:
            cli.add_command(self._build_list_command())

        return cli

    def _build_list_command(self) -> click.Command:
        specs = self._command_specs

        @click.command("list", help="List all registered commands.")
        def list_commands() -> None:
            for spec in specs:
                if spec["hidden"]:
                    continue
                line = spec["name"]
                if spec["aliases"]:
                    line += f" (aliases: {', '.join(spec['aliases'])})"
                if spec["help"]:
                    first_line = spec["help"].splitlines()[0]
                    line += f" — {first_line}"
                click.echo(line)

        return list_commands


# ---------------------------------------------------------------------- #
# Async helpers
# ---------------------------------------------------------------------- #


async def _run_async_lifecycle(instance: BaseCommand, args: tuple, kwargs: dict) -> Any:
    await instance.setup()  # type: ignore[misc]
    exc: Optional[BaseException] = None
    try:
        return await instance.run(*args, **kwargs)  # type: ignore[misc]
    except BaseException as e:
        exc = e
        raise
    finally:
        await instance.teardown(exc)  # type: ignore[misc]


def _run_async(coro: Any) -> Any:
    """Run a coroutine, even when called from inside a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: Dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as e:  # noqa: BLE001
            result["error"] = e

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")
