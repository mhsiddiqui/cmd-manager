from cmd_manager import BaseCommand


class Command(BaseCommand):
    aliases = ("n",)

    def run(self, *args, **kwargs):
        print("nested")
