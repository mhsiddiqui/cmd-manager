"""End-to-end integration tests.

These exercise the full command flow through Click's CLI group (not just
individual commands), drive the example CLI as a real subprocess, and cover
realistic host-app integration scenarios.
"""
import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

import click
from click.testing import CliRunner

from cmd_manager import Argument, AsyncBaseCommand, BaseCommand, ManagementCommandSystem

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE_RUNNER = REPO_ROOT / "example_runner.py"


def _run_example_cli(*args, stdin=""):
    """Invoke ``example_runner.py`` as a true subprocess and return CompletedProcess."""
    env = os.environ.copy()
    # Make sure the in-tree package is importable regardless of installed version.
    env["PYTHONPATH"] = (
        str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    )
    return subprocess.run(
        [sys.executable, str(EXAMPLE_RUNNER), *args],
        capture_output=True,
        text=True,
        input=stdin,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=15,
    )


class ExampleRunnerSubprocessTests(unittest.TestCase):
    """Run the actual example_runner.py from disk to catch packaging mistakes."""

    def test_help_lists_registered_commands(self):
        result = _run_example_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("whats_my_name", result.stdout)
        self.assertIn("list", result.stdout)

    def test_whats_my_name_command_runs_with_prompt(self):
        result = _run_example_cli("whats_my_name", stdin="Alice\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("My Name is Alice", result.stdout)

    def test_whats_my_name_with_explicit_name(self):
        result = _run_example_cli("whats_my_name", "--name", "Bob")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("My Name is Bob", result.stdout)

    def test_list_subcommand_via_subprocess(self):
        result = _run_example_cli("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("whats_my_name", result.stdout)

    def test_unknown_command_exits_nonzero(self):
        result = _run_example_cli("does_not_exist")
        self.assertNotEqual(result.returncode, 0)

    def test_help_for_specific_command(self):
        result = _run_example_cli("whats_my_name", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--name", result.stdout)


class HostApplicationDIIntegrationTests(unittest.TestCase):
    """Simulates a FastAPI/Flask host passing itself into commands via DI."""

    def test_app_is_shared_across_commands(self):
        class FakeApp:
            def __init__(self):
                self.events = []

            def record(self, what):
                self.events.append(what)

        app = FakeApp()

        class StartCommand(BaseCommand):
            def run(self, *args, **kwargs):
                self.kwargs["app"].record("start")
                click.echo("started")

        class StopCommand(BaseCommand):
            def run(self, *args, **kwargs):
                self.kwargs["app"].record("stop")
                click.echo("stopped")

        system = ManagementCommandSystem(app=app)
        system.register_command(StartCommand, name="start")
        system.register_command(StopCommand, name="stop")

        cli = system.create_cli()
        runner = CliRunner()
        self.assertEqual(runner.invoke(cli, ["start"]).output.strip(), "started")
        self.assertEqual(runner.invoke(cli, ["stop"]).output.strip(), "stopped")
        self.assertEqual(app.events, ["start", "stop"])

    def test_per_package_di_override(self):
        host_app = mock.Mock(name="host")
        plugin_app = mock.Mock(name="plugin")
        seen = {}

        class HostCommand(BaseCommand):
            def run(self, *args, **kwargs):
                seen["host"] = self.kwargs["app"]

        class PluginCommand(BaseCommand):
            def run(self, *args, **kwargs):
                seen["plugin"] = self.kwargs["app"]

        system = ManagementCommandSystem(app=host_app)
        system.register_command(HostCommand, name="host-cmd")
        system.register_command(
            PluginCommand, name="plugin-cmd", init_kwargs={"app": plugin_app}
        )

        cli = system.create_cli()
        runner = CliRunner()
        runner.invoke(cli, ["host-cmd"])
        runner.invoke(cli, ["plugin-cmd"])
        self.assertIs(seen["host"], host_app)
        self.assertIs(seen["plugin"], plugin_app)


class MultiPackageRegistrationIntegrationTests(unittest.TestCase):
    """Verify multiple register() calls coexist in a single CLI group."""

    def test_two_packages_with_distinct_prefixes(self):
        system = ManagementCommandSystem()
        system.register(prefix="a-", package="tests.test_commands")
        system.register(prefix="b-", package="tests.test_recursive", recursive=True)

        cli = system.create_cli()
        runner = CliRunner()

        # Help should expose commands from both packages.
        help_result = runner.invoke(cli, ["--help"])
        self.assertIn("a-test_command", help_result.output)
        self.assertIn("b-top", help_result.output)

        # Both invocable end-to-end.
        result_a = runner.invoke(cli, ["a-test_command", "x", "--n", "1"])
        self.assertEqual(result_a.exit_code, 0)

        result_b = runner.invoke(cli, ["b-top"])
        self.assertEqual(result_b.exit_code, 0)


class AsyncCommandIntegrationTests(unittest.TestCase):
    """Drive an async command through the assembled Click group, with full lifecycle."""

    def test_full_async_lifecycle(self):
        events = []

        class TimedAsync(AsyncBaseCommand):
            arguments = (Argument.option("--label", default="x"),)

            async def setup(self):
                events.append("setup")

            async def run(self, *args, **kwargs):
                events.append(("run", kwargs["label"]))
                click.echo(f"done {kwargs['label']}")

            async def teardown(self, exc=None):
                events.append(("teardown", exc))

        system = ManagementCommandSystem()
        system.register_command(TimedAsync, name="timed")
        cli = system.create_cli()

        result = CliRunner().invoke(cli, ["timed", "--label", "alpha"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("done alpha", result.output)
        self.assertEqual(events[0], "setup")
        self.assertEqual(events[1], ("run", "alpha"))
        self.assertEqual(events[2], ("teardown", None))


class RecursiveRegistrationIntegrationTests(unittest.TestCase):
    """Run a nested command through the real CLI group, not by direct indexing."""

    def test_nested_command_runs_through_cli_group(self):
        system = ManagementCommandSystem()
        system.register(package="tests.test_recursive", recursive=True)
        cli = system.create_cli()
        runner = CliRunner()

        # Primary nested name works.
        nested = runner.invoke(cli, ["inner-nested"])
        self.assertEqual(nested.exit_code, 0)
        self.assertIn("nested", nested.output)

        # Alias works and is omitted from --help (hidden).
        alias = runner.invoke(cli, ["n"])
        self.assertEqual(alias.exit_code, 0)

        help_out = runner.invoke(cli, ["--help"]).output
        self.assertIn("inner-nested", help_out)
        self.assertNotIn("\n  n ", help_out)  # alias hidden from listing


class EntryPointPluginIntegrationTests(unittest.TestCase):
    """Simulate a plugin package advertising commands via entry points."""

    def test_plugin_command_callable_through_assembled_cli(self):
        class PluginGreet(BaseCommand):
            """Greet from a plugin."""

            arguments = (Argument.option("--name", default="world"),)

            def run(self, *args, **kwargs):
                click.echo(f"plugin says hi to {kwargs['name']}")

        fake_ep = mock.MagicMock()
        fake_ep.name = "greet"
        fake_ep.load.return_value = PluginGreet

        fake_eps = mock.MagicMock()
        fake_eps.select.return_value = [fake_ep]

        with mock.patch("cmd_manager.management.entry_points", return_value=fake_eps):
            system = ManagementCommandSystem()
            system.register_entry_points()

        cli = system.create_cli()
        result = CliRunner().invoke(cli, ["greet", "--name", "Ada"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("plugin says hi to Ada", result.output)

    def test_mixed_local_and_plugin_registration(self):
        """Local register() and register_entry_points() coexist."""

        class PluginCmd(BaseCommand):
            def run(self, *args, **kwargs):
                click.echo("plugin")

        fake_ep = mock.MagicMock()
        fake_ep.name = "plugin"
        fake_ep.load.return_value = PluginCmd
        fake_eps = mock.MagicMock()
        fake_eps.select.return_value = [fake_ep]

        with mock.patch("cmd_manager.management.entry_points", return_value=fake_eps):
            system = ManagementCommandSystem()
            system.register(package="tests.test_recursive")  # has `top`
            system.register_entry_points()

        cli = system.create_cli()
        runner = CliRunner()
        self.assertEqual(runner.invoke(cli, ["top"]).exit_code, 0)
        self.assertEqual(runner.invoke(cli, ["plugin"]).exit_code, 0)
        list_out = runner.invoke(cli, ["list"]).output
        self.assertIn("top", list_out)
        self.assertIn("plugin", list_out)


if __name__ == "__main__":
    unittest.main()
