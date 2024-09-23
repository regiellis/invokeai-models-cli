import sys
from . import cli


def main():
    if len(sys.argv) == 1:
        sys.argv.append("--help")
    cli.invoke_models_cli()
