from .__version__ import __version__
import typer
from typing_extensions import Annotated


from .functions import (
    list_snapshots,
    delete_snapshot,
    restore_snapshot,
    create_snapshot,
    database_models_display,
    local_models_display,
    compare_models_display,
    sync_models_commands,
    about_cli,
)

from rich.traceback import install

install()


"""
=========================================================================
Invoke Preset CLI - Simplified Tool for installing Invoke AI styling presets
=========================================================================

Invoke preset is a simplified tool for installing and updating Invoke AI
styles presets from the command line.


Usage:
$ pipx install invoke-presets (recommended)
$ pipx install . (if you want to install it globally)
$ pip install -e . (if you want to install it locally and poke around, 
make sure to create a virtual environment)
$ invoke-presets [OPTIONS] [COMMAND] [ARGS]

Commands:

invoke-presets database create-snapshot
invoke-presets database list-snapshots
invoke-presets database delete-snapshot
invoke-presets database restore-snapshot

"""

__all__ = ["invoke_models_cli"]
__version__ = __version__

invoke_models_cli = typer.Typer()
database_cli = typer.Typer()
# utils_cli = typer.Typer()

invoke_models_cli.add_typer(
    database_cli,
    name="database",
    help="Manage the snapshots of the Invoke AI database.",
    no_args_is_help=True,
)
# invoke_models_cli.add_typer(
#     utils_cli, name="tools", help="Utilities.", no_args_is_help=True
# )


@database_cli.command(
    "create-snapshot", help="Create a snapshot of the Invoke AI database."
)
def datebase_create_command():
    create_snapshot()


@database_cli.command("list-snapshots", help="List all available snapshots.")
def database_list_command():
    list_snapshots()


@database_cli.command(
    "delete-snapshot", help="Delete a snapshot of the Invoke AI database."
)
def database_delete_command():
    delete_snapshot()


@database_cli.command(
    "restore-snapshot", help="Restore a snapshot of the Invoke AI database."
)
def database_restore_command():
    restore_snapshot()


@invoke_models_cli.command("local-models", help="List local models files.")
def local_models_command(
    display_tree: bool = typer.Option(
        False, "--tree", "-t", help="Display the model tree"
    )
):
    local_models_display(display_tree=display_tree)


@invoke_models_cli.command("database-models", help="List models in the database.")
def database_models_command():
    database_models_display()


@invoke_models_cli.command("compare-models", help="List models in the database.")
def compare_models_command():
    compare_models_display()
    

@invoke_models_cli.command(
    "sync-models", help="Sync database models with local model files."
)
def sync_models_command():
    sync_models_commands()


# @invoke_models_cli.command(
#     "list",
#     help="List models in the database, but no longer on disk.",
# )
# def list_command():
#     list_models_cli()


@invoke_models_cli.command("about", help="Functions for information on this tool.")
def about_command(
    readme: bool = typer.Option(
        True, "--readme", "-r", help="Show the README.md content"
    ),
    changelog: bool = typer.Option(
        False, "--changelog", "-c", help="Show the CHANGELOG.md content"
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show the current version",
    ),
):
    """
    Show README.md and/or CHANGELOG.md content.
    """

    if version:
        typer.echo(f"InvokeAI Preset CLI version: {__version__}", color=True)
        return

    about_cli(readme, changelog)
