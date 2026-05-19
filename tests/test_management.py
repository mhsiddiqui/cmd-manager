import unittest
from unittest import mock

import click
from click.testing import CliRunner

from cmd_manager import Argument, AsyncBaseCommand, BaseCommand, ManagementCommandSystem


def _get_command(system, name):
    for cmd in system.commands:
        if cmd.name == name:
            return cmd
    raise AssertionError(f"command {name!r} not registered")


class ManagementCommandSystemTestCases(unittest.TestCase):
    def test_registration_discovers_command_modules(self):
        system = ManagementCommandSystem()
        system.register(package="tests.test_commands")
        # test_command + async_command
        names = sorted(c.name for c in system.commands)
        self.assertIn("test_command", names)
        self.assertIn("async_command", names)

    def test_management_command_working(self):
        system = ManagementCommandSystem()
        system.register(package="tests.test_commands")
        runner = CliRunner()
        result = runner.invoke(_get_command(system, "test_command"), ["a", "--n", "2"])
        self.assertEqual(result.exit_code, 0)

    def test_prefix_applied_to_command_names(self):
        system = ManagementCommandSystem()
        system.register(prefix="ext-", package="tests.test_commands")
        names = [c.name for c in system.commands]
        self.assertTrue(all(n.startswith("ext-") for n in names))

    def test_recursive_discovery_flattens_module_paths(self):
        system = ManagementCommandSystem()
        system.register(package="tests.test_recursive", recursive=True)
        names = sorted(c.name for c in system.commands if not c.hidden)
        self.assertIn("top", names)
        self.assertIn("inner-nested", names)

    def test_aliases_are_registered_as_hidden_commands(self):
        system = ManagementCommandSystem()
        system.register(package="tests.test_recursive", recursive=True)
        # alias "n" of inner-nested
        alias_cmd = _get_command(system, "n")
        self.assertTrue(alias_cmd.hidden)
        result = CliRunner().invoke(alias_cmd, [])
        self.assertEqual(result.exit_code, 0)

    def test_register_command_directly(self):
        class GreetCommand(BaseCommand):
            """Say hi."""

            arguments = (Argument.option("--name", default="world"),)

            def run(self, *args, **kwargs):
                click.echo(f"hi {kwargs['name']}")

        system = ManagementCommandSystem()
        system.register_command(GreetCommand, name="greet")
        result = CliRunner().invoke(_get_command(system, "greet"), ["--name", "Sam"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hi Sam", result.output)

    def test_help_text_pulled_from_docstring(self):
        class DocCommand(BaseCommand):
            """A documented command."""

            def run(self, *args, **kwargs):
                pass

        system = ManagementCommandSystem()
        system.register_command(DocCommand, name="doc")
        cmd = _get_command(system, "doc")
        self.assertEqual(cmd.help, "A documented command.")

    def test_lifecycle_hooks_called(self):
        events = []

        class HookCommand(BaseCommand):
            def setup(self):
                events.append("setup")

            def run(self, *args, **kwargs):
                events.append("run")

            def teardown(self, exc=None):
                events.append(("teardown", exc))

        system = ManagementCommandSystem()
        system.register_command(HookCommand, name="hook")
        CliRunner().invoke(_get_command(system, "hook"), [])
        self.assertEqual(events[0], "setup")
        self.assertEqual(events[1], "run")
        self.assertEqual(events[2], ("teardown", None))

    def test_teardown_receives_exception(self):
        events = []

        class FailCommand(BaseCommand):
            def run(self, *args, **kwargs):
                raise RuntimeError("boom")

            def teardown(self, exc=None):
                events.append(exc)

        system = ManagementCommandSystem()
        system.register_command(FailCommand, name="fail")
        result = CliRunner().invoke(_get_command(system, "fail"), [])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], RuntimeError)

    def test_decorator_registers_sync_function(self):
        system = ManagementCommandSystem()

        @system.command("hello", arguments=[Argument.option("--name", default="world")])
        def hello(name):
            """Say hello."""
            click.echo(f"hello {name}")

        result = CliRunner().invoke(_get_command(system, "hello"), ["--name", "Sam"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hello Sam", result.output)

    def test_decorator_registers_async_function(self):
        system = ManagementCommandSystem()

        @system.command("afetch", arguments=[Argument.option("--url", default="x")])
        async def afetch(url):
            click.echo(f"got {url}")

        result = CliRunner().invoke(_get_command(system, "afetch"), ["--url", "y"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("got y", result.output)

    def test_async_command_runs_and_invokes_lifecycle(self):
        system = ManagementCommandSystem()
        system.register(package="tests.test_commands")
        result = CliRunner().invoke(_get_command(system, "async_command"), ["--name", "Ada"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hello Ada", result.output)

    def test_list_subcommand_lists_registered(self):
        system = ManagementCommandSystem()
        system.register(package="tests.test_commands")
        cli = system.create_cli()
        result = CliRunner().invoke(cli, ["list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test_command", result.output)
        self.assertIn("async_command", result.output)

    def test_per_package_init_kwargs(self):
        captured = {}

        class CtxCommand(BaseCommand):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                captured.update(kwargs)

            def run(self, *args, **kwargs):
                pass

        system = ManagementCommandSystem(app="default-app")
        system.register_command(CtxCommand, name="ctx", init_kwargs={"app": "override-app"})
        self.assertEqual(captured["app"], "override-app")

    def test_on_error_warn_skips_broken_modules(self):
        system = ManagementCommandSystem()
        # The package itself is fine; this verifies the option is accepted.
        system.register(package="tests.test_commands", on_error="warn")
        self.assertGreaterEqual(len(system.commands), 1)

    def test_non_package_raises(self):
        system = ManagementCommandSystem()
        with self.assertRaises(ValueError):
            system.register(package="cmd_manager.command")

    def test_on_error_invalid_value(self):
        system = ManagementCommandSystem()
        with self.assertRaises(ValueError):
            system.register(package="tests.test_commands", on_error="bogus")

    def test_recursive_false_does_not_discover_nested(self):
        system = ManagementCommandSystem()
        system.register(package="tests.test_recursive")  # recursive=False
        names = {c.name for c in system.commands}
        self.assertIn("top", names)
        self.assertNotIn("inner-nested", names)

    def test_class_level_name_attribute_is_respected(self):
        class NamedCommand(BaseCommand):
            name = "renamed"

            def run(self, *args, **kwargs):
                pass

        system = ManagementCommandSystem()
        # Pass no explicit name → falls back to class attr.
        system.register_command(NamedCommand)
        self.assertEqual(system.commands[0].name, "renamed")

    def test_class_name_fallback_lowercased(self):
        class MyCmd(BaseCommand):
            def run(self, *args, **kwargs):
                pass

        system = ManagementCommandSystem()
        system.register_command(MyCmd)
        self.assertEqual(system.commands[0].name, "mycmd")

    def test_help_attribute_overrides_docstring(self):
        class Cmd(BaseCommand):
            """Docstring help."""

            help = "Attribute help."

            def run(self, *args, **kwargs):
                pass

        system = ManagementCommandSystem()
        system.register_command(Cmd, name="x")
        self.assertEqual(system.commands[0].help, "Attribute help.")

    def test_hidden_command_excluded_from_list_output(self):
        class HiddenCmd(BaseCommand):
            """Should not appear."""

            hidden = True

            def run(self, *args, **kwargs):
                pass

        class VisibleCmd(BaseCommand):
            """Should appear."""

            def run(self, *args, **kwargs):
                pass

        system = ManagementCommandSystem()
        system.register_command(HiddenCmd, name="hidden")
        system.register_command(VisibleCmd, name="visible")
        result = CliRunner().invoke(system.create_cli(), ["list"])
        self.assertIn("visible", result.output)
        self.assertNotIn("hidden", result.output)

    def test_create_cli_can_omit_list_command(self):
        system = ManagementCommandSystem()
        cli = system.create_cli(include_list_command=False)
        self.assertNotIn("list", cli.commands)

    def test_init_args_positional_override(self):
        captured = {}

        class CtxCommand(BaseCommand):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                captured["args"] = args

            def run(self, *args, **kwargs):
                pass

        system = ManagementCommandSystem("default")
        system.register_command(CtxCommand, name="ctx", init_args=("override",))
        self.assertEqual(captured["args"], ("override",))

    def test_decorator_name_defaults_to_kebab_case(self):
        system = ManagementCommandSystem()

        @system.command()
        def my_long_name():
            pass

        self.assertEqual(system.commands[0].name, "my-long-name")

    def test_decorator_with_aliases(self):
        system = ManagementCommandSystem()

        @system.command("primary", aliases=["p", "pri"])
        def run_it():
            click.echo("ran")

        # Primary + 2 hidden aliases.
        self.assertEqual(len(system.commands), 3)
        names = sorted(c.name for c in system.commands)
        self.assertEqual(names, ["p", "pri", "primary"])

    def test_async_teardown_receives_exception(self):
        captured = []

        class AsyncFail(AsyncBaseCommand):
            async def run(self, *args, **kwargs):
                raise RuntimeError("async boom")

            async def teardown(self, exc=None):
                captured.append(exc)

        system = ManagementCommandSystem()
        system.register_command(AsyncFail, name="afail")
        result = CliRunner().invoke(system.commands[0], [])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(len(captured), 1)
        self.assertIsInstance(captured[0], RuntimeError)

    def test_entry_points_loads_commands(self):
        class PluginCommand(BaseCommand):
            """Plugin-supplied command."""

            def run(self, *args, **kwargs):
                click.echo("from plugin")

        fake_ep = mock.MagicMock()
        fake_ep.name = "plugin-greet"
        fake_ep.load.return_value = PluginCommand

        fake_eps = mock.MagicMock()
        fake_eps.select.return_value = [fake_ep]

        with mock.patch("cmd_manager.management.entry_points", return_value=fake_eps):
            system = ManagementCommandSystem()
            system.register_entry_points()

        self.assertEqual(system.commands[0].name, "plugin-greet")
        result = CliRunner().invoke(system.commands[0], [])
        self.assertIn("from plugin", result.output)

    def test_entry_points_warns_on_invalid_target(self):
        fake_ep = mock.MagicMock()
        fake_ep.name = "broken"
        fake_ep.load.return_value = "not a class"

        fake_eps = mock.MagicMock()
        fake_eps.select.return_value = [fake_ep]

        with mock.patch("cmd_manager.management.entry_points", return_value=fake_eps):
            system = ManagementCommandSystem()
            with self.assertWarns(UserWarning):
                system.register_entry_points()
        self.assertEqual(system.commands, [])

    def test_on_error_warn_actually_handles_broken_module(self):
        system = ManagementCommandSystem()
        with self.assertWarns(UserWarning):
            system.register(package="tests.test_broken", on_error="warn")
        names = {c.name for c in system.commands}
        self.assertIn("good", names)
        self.assertNotIn("broken", names)

    def test_on_error_ignore_silently_skips(self):
        system = ManagementCommandSystem()
        import warnings as _w

        with _w.catch_warnings():
            _w.simplefilter("error")  # any warning would become an exception
            system.register(package="tests.test_broken", on_error="ignore")
        names = {c.name for c in system.commands}
        self.assertIn("good", names)
        self.assertNotIn("broken", names)

    def test_on_error_raise_propagates(self):
        system = ManagementCommandSystem()
        with self.assertRaises(RuntimeError):
            system.register(package="tests.test_broken")  # default on_error="raise"

    def test_module_with_non_basecommand_class_is_skipped(self):
        system = ManagementCommandSystem()
        system.register(package="tests.test_broken", on_error="ignore")
        names = {c.name for c in system.commands}
        self.assertNotIn("not_a_command", names)

    def test_list_output_includes_aliases(self):
        class WithAlias(BaseCommand):
            """Command with alias."""

            aliases = ("alt",)

            def run(self, *args, **kwargs):
                pass

        system = ManagementCommandSystem()
        system.register_command(WithAlias, name="primary")
        result = CliRunner().invoke(system.create_cli(), ["list"])
        self.assertIn("primary", result.output)
        self.assertIn("aliases: alt", result.output)

    def test_async_failure_propagates_from_thread_fallback(self):
        """The worker-thread path must re-raise exceptions, not swallow them."""
        import asyncio

        class AsyncBoom(AsyncBaseCommand):
            async def run(self, *args, **kwargs):
                raise RuntimeError("from-thread")

        system = ManagementCommandSystem()
        system.register_command(AsyncBoom, name="boom")
        click_cmd = system.commands[0]

        async def _driver():
            return CliRunner().invoke(click_cmd, [])

        result = asyncio.run(_driver())
        self.assertNotEqual(result.exit_code, 0)
        self.assertIsInstance(result.exception, RuntimeError)

    def test_async_runs_when_event_loop_already_running(self):
        """The thread-fallback path in _run_async kicks in inside a running loop."""
        import asyncio

        events = []

        class AsyncCmd(AsyncBaseCommand):
            async def run(self, *args, **kwargs):
                events.append("ran")
                return 42

        system = ManagementCommandSystem()
        system.register_command(AsyncCmd, name="ac")
        click_cmd = system.commands[0]

        async def _driver():
            # We are inside a running event loop here; the dispatcher must
            # off-load to a worker thread rather than raising.
            return CliRunner().invoke(click_cmd, [])

        result = asyncio.run(_driver())
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(events, ["ran"])

    def test_register_entry_points_applies_prefix(self):
        class PluginCommand(BaseCommand):
            def run(self, *args, **kwargs):
                pass

        fake_ep = mock.MagicMock()
        fake_ep.name = "greet"
        fake_ep.load.return_value = PluginCommand

        fake_eps = mock.MagicMock()
        fake_eps.select.return_value = [fake_ep]

        with mock.patch("cmd_manager.management.entry_points", return_value=fake_eps):
            system = ManagementCommandSystem()
            system.register_entry_points(prefix="ext-")
        self.assertEqual(system.commands[0].name, "ext-greet")


if __name__ == "__main__":
    unittest.main()
