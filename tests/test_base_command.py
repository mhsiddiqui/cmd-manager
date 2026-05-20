"""Contract tests for BaseCommand and AsyncBaseCommand themselves."""

import asyncio
import unittest

from cmd_manager import Argument, AsyncBaseCommand, BaseCommand


class BaseCommandContractTests(unittest.TestCase):
    def test_class_defaults(self):
        self.assertIsNone(BaseCommand.name)
        self.assertIsNone(BaseCommand.help)
        self.assertIsNone(BaseCommand.short_help)
        self.assertEqual(BaseCommand.aliases, ())
        self.assertFalse(BaseCommand.hidden)
        self.assertEqual(BaseCommand.arguments, ())

    def test_constructor_stores_args_and_kwargs(self):
        instance = BaseCommand("a", "b", app="x")
        self.assertEqual(instance.args, ("a", "b"))
        self.assertEqual(instance.kwargs, {"app": "x"})

    def test_run_raises_not_implemented_by_default(self):
        with self.assertRaises(NotImplementedError):
            BaseCommand().run()

    def test_setup_and_teardown_are_noops(self):
        instance = BaseCommand()
        # Should not raise; should not return anything meaningful.
        self.assertIsNone(instance.setup())
        self.assertIsNone(instance.teardown())
        self.assertIsNone(instance.teardown(RuntimeError("x")))

    def test_get_arguments_returns_class_attribute(self):
        class HasArgs(BaseCommand):
            arguments = (Argument.option("--name"),)

            def run(self, *args, **kwargs):
                pass

        self.assertEqual(len(HasArgs().get_arguments()), 1)

    def test_get_arguments_can_be_overridden(self):
        class DynamicArgs(BaseCommand):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.extra = kwargs.get("extra", 0)

            def get_arguments(self):
                return [Argument.option(f"--n{i}") for i in range(self.extra)]

            def run(self, *args, **kwargs):
                pass

        self.assertEqual(len(DynamicArgs(extra=3).get_arguments()), 3)


class AsyncBaseCommandContractTests(unittest.TestCase):
    def test_run_is_coroutine_function(self):
        self.assertTrue(asyncio.iscoroutinefunction(AsyncBaseCommand.run))

    def test_setup_and_teardown_are_coroutine_functions(self):
        self.assertTrue(asyncio.iscoroutinefunction(AsyncBaseCommand.setup))
        self.assertTrue(asyncio.iscoroutinefunction(AsyncBaseCommand.teardown))

    def test_run_raises_not_implemented(self):
        async def _run():
            await AsyncBaseCommand().run()

        with self.assertRaises(NotImplementedError):
            asyncio.run(_run())

    def test_setup_and_teardown_default_noop(self):
        instance = AsyncBaseCommand()

        async def _exercise():
            self.assertIsNone(await instance.setup())
            self.assertIsNone(await instance.teardown())
            self.assertIsNone(await instance.teardown(RuntimeError("x")))

        asyncio.run(_exercise())


if __name__ == "__main__":
    unittest.main()
