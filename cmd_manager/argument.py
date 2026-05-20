from typing import Any, Callable

import click


class Argument:
    """Declarative wrapper around ``click.argument`` and ``click.option``.

    Use :meth:`positional` for positional arguments and :meth:`option` for
    options/flags. The lower-level ``Argument(..., is_argument=bool)``
    constructor is preserved for backwards compatibility.
    """

    def __init__(self, *param_decls: str, is_argument: bool = False, **attrs: Any):
        """
        :param param_decls: The parameter declarations forwarded to click
            (e.g. ``"name"`` for a positional, or ``"--name", "-n"`` for an option).
        :param is_argument: ``True`` to render as ``click.argument``,
            ``False`` (default) to render as ``click.option``.
        :param attrs: Additional keyword arguments forwarded verbatim to the
            underlying click decorator (``type=``, ``prompt=``, ``required=``,
            ``default=``, ``is_flag=``, ``multiple=``, ...).
        """
        self.param_decls = param_decls
        self.is_argument = is_argument
        self.attrs = attrs

    @classmethod
    def positional(cls, *param_decls: str, **attrs: Any) -> "Argument":
        """Declare a positional argument (``click.argument``)."""
        return cls(*param_decls, is_argument=True, **attrs)

    @classmethod
    def option(cls, *param_decls: str, **attrs: Any) -> "Argument":
        """Declare an option or flag (``click.option``)."""
        return cls(*param_decls, is_argument=False, **attrs)

    def apply(self, func: Callable) -> Callable:
        """Wrap *func* with the corresponding click decorator and return it."""
        decorator = click.argument if self.is_argument else click.option
        return decorator(*self.param_decls, **self.attrs)(func)
