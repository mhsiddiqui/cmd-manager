from typing import Any, ClassVar, List, Optional, Sequence

from cmd_manager.argument import Argument


class BaseCommand:
    """Base class for synchronous management commands.

    Subclasses override :meth:`run` (and optionally :meth:`get_arguments`,
    :meth:`setup`, :meth:`teardown`). Metadata can be supplied either via
    class attributes (``help``, ``short_help``, ``aliases``, ``hidden``,
    ``arguments``) or — for ``help`` — the class docstring.
    """

    #: Display name override. When ``None`` the system uses the module name.
    name: ClassVar[Optional[str]] = None
    #: Long help text. Falls back to the class docstring.
    help: ClassVar[Optional[str]] = None
    #: Short help text shown in command listings.
    short_help: ClassVar[Optional[str]] = None
    #: Additional names the command can be invoked under.
    aliases: ClassVar[Sequence[str]] = ()
    #: Hide the command from ``--help`` listings.
    hidden: ClassVar[bool] = False
    #: Default argument list. Overridden by :meth:`get_arguments` when provided.
    arguments: ClassVar[Sequence[Argument]] = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    def get_arguments(self) -> List[Argument]:
        """Return the list of :class:`Argument` declarations for this command.

        Defaults to the class-level :attr:`arguments` attribute. Override for
        dynamic argument lists.
        """
        return list(self.arguments)

    def setup(self) -> None:
        """Lifecycle hook called before :meth:`run`."""

    def teardown(self, exc: Optional[BaseException] = None) -> None:
        """Lifecycle hook called after :meth:`run`, even on exception."""

    def run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("Subclasses must implement the run() method.")


class AsyncBaseCommand(BaseCommand):
    """Base class for asynchronous management commands.

    :meth:`run`, :meth:`setup`, and :meth:`teardown` are coroutines. The
    :class:`ManagementCommandSystem` will execute them on an event loop.
    """

    async def setup(self) -> None:  # type: ignore[override]
        return None

    async def teardown(self, exc: Optional[BaseException] = None) -> None:  # type: ignore[override]
        return None

    async def run(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        raise NotImplementedError("Subclasses must implement the run() method.")
