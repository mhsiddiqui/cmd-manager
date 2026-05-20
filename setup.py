"""Legacy setup shim. Authoritative metadata lives in ``pyproject.toml``."""

from setuptools import find_packages, setup

setup(
    name="cmd-manager",
    version="0.2.0",
    description=(
        "A framework-agnostic management command system for Python apps "
        "(FastAPI, Flask, Sanic, Starlette, or plain Python), "
        "inspired by Django management commands."
    ),
    author="Muhammad Hassan Siddiqui",
    author_email="mhassan.eeng@gmail.com",
    packages=find_packages(exclude=["tests*", "example*"]),
    package_data={"cmd_manager": ["py.typed"]},
    install_requires=["click>=8.0"],
    python_requires=">=3.9",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Typing :: Typed",
    ],
)
