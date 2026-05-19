[![Build](https://github.com/mhsiddiqui/cmd-manager/actions/workflows/build.yml/badge.svg)](https://github.com/mhsiddiqui/cmd-manager/actions/workflows/build.yml)
# Cli Manager

A Python package that enables you to create and manage custom management commands, similar to Django's management system, for any Python application — FastAPI, Flask, Sanic, Starlette, or plain Python. This package uses Python's `click` to define, register, and execute commands for your application dynamically. Both synchronous and asynchronous commands are supported.

## Features

- **Dynamic Command Registration:** Automatically discover and register commands located in specific directories (recursively, optionally).
- **Class-Based Commands:** Easily define reusable commands by subclassing `BaseCommand` (sync) or `AsyncBaseCommand` (async).
- **Decorator API:** Register plain functions (sync or `async`) directly with `@system.command()`.
- **Custom Arguments:** Commands can specify their own arguments and options via `Argument.positional(...)` / `Argument.option(...)`.
- **Lifecycle Hooks:** `setup()` and `teardown(exc)` run before and after every command, even on exceptions.
- **Aliases, Help & Hidden Commands:** Class-level `aliases`, `help`, `short_help`, `hidden` attributes for ergonomic CLIs.
- **Plugin Discovery:** Register commands advertised by installed packages through `cmd_manager.commands` entry points.
- **Framework-agnostic:** Drop into any Python app — FastAPI, Flask, Sanic, Starlette, or a plain script — and thread your app/context into commands via constructor args.

## Installation

Install the package via `pip`:

```bash
pip install cmd-manager
```

## Usage

### 1. Define a synchronous command

```python
# src/scripts/mycommand.py
from cmd_manager import Argument, BaseCommand


class Command(BaseCommand):
    """Print the arguments passed in."""

    arguments = (
        Argument.positional("arg1"),
        Argument.option("--n", type=int, default=1),
    )

    def run(self, *args, **kwargs):
        print(f"Running with args: {args}, kwargs: {kwargs}")
```

`Argument.positional` wraps `click.argument`; `Argument.option` wraps `click.option`. Every `click` keyword (`type`, `prompt`, `required`, `is_flag`, `multiple`, ...) is forwarded verbatim.

### 2. Define an asynchronous command

```python
# src/scripts/fetch.py
import click
from cmd_manager import Argument, AsyncBaseCommand


class Command(AsyncBaseCommand):
    """Fetch a URL asynchronously."""

    arguments = (Argument.option("--url", required=True),)

    async def setup(self):
        self.session = await open_session()

    async def run(self, *args, **kwargs):
        body = await self.session.get(kwargs["url"])
        click.echo(body)

    async def teardown(self, exc=None):
        await self.session.close()
```

The system detects async commands automatically and runs them on an event loop — `setup`, `run`, and `teardown` are all awaited.

### 3. Register and run

```python
# cli_runner.py
from cmd_manager import ManagementCommandSystem

system = ManagementCommandSystem()
system.register(package="src.scripts")
cli = system.create_cli()

if __name__ == "__main__":
    cli()
```

Then:

```bash
python cli_runner.py mycommand arg1_value --n 3
python cli_runner.py fetch --url https://example.com
python cli_runner.py list   # built-in: prints every registered command
```

### 4. Recursive discovery & sub-packages

```python
system.register(package="src.scripts", recursive=True)
```

`src/scripts/users/create.py` becomes the command `users-create`.

### 5. Prefixing third-party command packages

```python
system.register(prefix="ext-", package="external_package.scripts")
```

Per-package constructor args (useful when the host app and a plugin expect different DI payloads). `app` can be any framework instance (FastAPI, Flask, Sanic, Starlette, ...) or any arbitrary object — `ManagementCommandSystem` is framework-agnostic and just forwards constructor args to each command:

```python
system = ManagementCommandSystem(app=app)  # app is any object you want injected
system.register(package="external_package.scripts",
                init_kwargs={"app": app, "config": plugin_cfg})
```

### 6. Decorator API for one-off commands

```python
from cmd_manager import Argument

@system.command("greet", arguments=[Argument.option("--name", default="world")])
def greet(name):
    """Say hello."""
    click.echo(f"hello {name}")


@system.command()  # name defaults to "fetch-once" (kebab-cased function name)
async def fetch_once(url):
    ...
```

### 7. Plugin discovery via entry points

A plugin package declares the command in its `pyproject.toml`:

```toml
[project.entry-points."cmd_manager.commands"]
greet = "my_plugin.scripts.greet:Command"
```

The host app then loads every installed plugin command with one call:

```python
system.register_entry_points()
```

### 8. Command metadata

Any `BaseCommand` / `AsyncBaseCommand` subclass can set class-level attributes:

```python
class Command(BaseCommand):
    """Long help text comes from the docstring by default."""

    name = "do-thing"            # override the discovered name
    short_help = "Do a thing."   # one-liner shown in `--help`
    aliases = ("dt",)             # alternate names (registered as hidden subcommands)
    hidden = False                # hide from `--help` listings
```

### Example

See the `example/` folder; run it with:

```bash
python example_runner.py whats_my_name
python example_runner.py list
```

## Authors
[@mhsiddiqui](https://github.com/mhsiddiqui)

## Contributing
Contributions are always welcome! Please read `CONTRIBUTING.md` and adhere to the project's code of conduct.

## Feedback and Support
Please open an issue and follow the template, so the community can help you.
