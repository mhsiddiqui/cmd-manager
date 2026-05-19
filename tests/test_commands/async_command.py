"""Async command fixture used by tests."""
import click

from cmd_manager import Argument, AsyncBaseCommand


class Command(AsyncBaseCommand):
    """Echo a greeting asynchronously."""

    arguments = (Argument.option("--name", default="world"),)

    async def setup(self):
        self.setup_called = True

    async def run(self, *args, **kwargs):
        click.echo(f"hello {kwargs['name']}")
        return kwargs["name"]

    async def teardown(self, exc=None):
        self.teardown_called = True
        self.teardown_exc = exc
