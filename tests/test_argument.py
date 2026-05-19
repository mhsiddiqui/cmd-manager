import unittest

import click
from click.testing import CliRunner

from cmd_manager import Argument


class ArgumentTestCases(unittest.TestCase):
    def setUp(self):
        @click.command()
        def dummy_command(*args, **kwargs):
            click.echo("Dummy Command")

        self.command = dummy_command

    def test_argument_as_argument_with_one_option(self):
        arg = Argument("a", is_argument=True, nargs=1)
        command = arg.apply(self.command)

        assert isinstance(command, click.Command)
        runner = CliRunner()
        result = runner.invoke(command, ["John"])
        assert result.exit_code == 0

    def test_argument_as_argument_with_invalid_option(self):
        arg = Argument("a", is_argument=True, nargs=1)
        command = arg.apply(self.command)

        assert isinstance(command, click.Command)
        runner = CliRunner()
        result = runner.invoke(command, ["a", "John", "Smith"])
        assert result.exit_code == 2

    def test_argument_as_argument_with_n_options(self):
        arg = Argument("a", is_argument=True, nargs=-1)
        command = arg.apply(self.command)

        assert isinstance(command, click.Command)
        runner = CliRunner()
        result = runner.invoke(command, ["a"] * 5)
        assert result.exit_code == 0

    def test_argument_as_option(self):
        arg = Argument("--n", is_argument=False, type=int)
        command = arg.apply(self.command)

        assert isinstance(command, click.Command)
        runner = CliRunner()
        result = runner.invoke(command, ["--n", 2])
        assert result.exit_code == 0

    def test_argument_prompt(self):
        arg = Argument("--name", is_argument=False, prompt="Your name please")
        command = arg.apply(self.command)

        runner = CliRunner()
        result = runner.invoke(command, input="John\n")
        assert result.exit_code == 0

    def test_positional_factory(self):
        arg = Argument.positional("name")
        assert arg.is_argument is True
        command = arg.apply(self.command)
        result = CliRunner().invoke(command, ["John"])
        assert result.exit_code == 0

    def test_option_factory(self):
        arg = Argument.option("--count", type=int, default=1)
        assert arg.is_argument is False
        command = arg.apply(self.command)
        result = CliRunner().invoke(command, ["--count", "3"])
        assert result.exit_code == 0

    def test_option_flag(self):
        arg = Argument.option("--verbose", is_flag=True)
        command = arg.apply(self.command)
        result = CliRunner().invoke(command, ["--verbose"])
        assert result.exit_code == 0

    def test_option_short_and_long_form(self):
        arg = Argument.option("-n", "--name", default="world")
        command = arg.apply(self.command)
        for argv in (["-n", "Sam"], ["--name", "Sam"]):
            result = CliRunner().invoke(command, argv)
            assert result.exit_code == 0, result.output

    def test_option_multiple(self):
        arg = Argument.option("--item", multiple=True)
        command = arg.apply(self.command)
        result = CliRunner().invoke(command, ["--item", "a", "--item", "b"])
        assert result.exit_code == 0

    def test_attrs_forwarded_verbatim(self):
        arg = Argument.option(
            "--port", type=int, default=8080, show_default=True, envvar="APP_PORT"
        )
        assert arg.attrs == {
            "type": int,
            "default": 8080,
            "show_default": True,
            "envvar": "APP_PORT",
        }
