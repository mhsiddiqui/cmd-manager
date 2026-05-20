# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`cmd-manager` is a small, framework-agnostic Python library that brings Django-style management commands to any Python app (FastAPI, Flask, Sanic, Starlette, or plain Python). It wraps `click` so users can drop `Command` classes into a package and have them auto-discovered as CLI subcommands.

## Common commands

Dependencies are managed by Poetry; `setup.py` is kept only for legacy installs and lists extras (`pytest`, `httpx`, `pytest-click`) that are not in `pyproject.toml`. When developing, install via `poetry install`.

- Run the full test suite across supported Pythons: `tox` (envs: py37–py312, uses `python -m unittest`).
- Run tests in the current interpreter: `python -m unittest discover tests` or `pytest tests`.
- Run a single test: `python -m unittest tests.test_management.ManagementCommandSystemTestCases.test_management_command_working`.
- Run the example CLI: `python example_runner.py whats_my_name` (commands live under `example/scripts/`).
- Pre-commit lint/format stack: `pre-commit run --all-files` (runs `isort`, `black`, `flake8 --max-line-length=100`).

## Architecture

Three files in `cmd_manager/` cover the whole library — they are tightly coupled and best understood together:

- `management.py` — `ManagementCommandSystem.register(package=...)` uses `importlib` + `pkgutil.iter_modules` to walk a package directory and pick up every module that exposes a top-level `Command` class. Each `Command` is instantiated (forwarding the `*args, **kwargs` originally passed to `ManagementCommandSystem`, which is how any host object — a FastAPI/Flask/Sanic/Starlette app, a config object, a DI container, or anything else — can be threaded into commands), its `get_arguments()` is called once, and the returned `Argument` objects are stacked onto a `@click.command(name)` via `_add_arguments`. Module filename becomes the command name; `prefix=` is prepended to avoid collisions when registering multiple external packages. `create_cli()` collects every registered command into a `@click.group()` for the entrypoint script.
- `command.py` — `BaseCommand` is the user-facing base class. Subclasses override `get_arguments()` (returns a `list[Argument]`) and `run(*args, **kwargs)`. `run` receives parsed Click values as kwargs keyed by the argument's long name (see `example/scripts/whats_my_name.py` and `tests/test_commands/test_command.py`).
- `argument.py` — `Argument` is a thin shim over `click.argument` / `click.option`. The `is_argument` flag toggles between the two; everything else in `**attrs` is forwarded verbatim, so any `click.Argument`/`click.Option` kwarg (`type=`, `prompt=`, `required=`, multi-value, etc.) works without code changes here.

Discovery is filename-driven and class-name-driven: a module is only registered if it defines a class literally named `Command`. Tests rely on this — `tests/test_commands/test_command.py` is itself a registrable command module that the `unittest` suite re-discovers through `ManagementCommandSystem`.
