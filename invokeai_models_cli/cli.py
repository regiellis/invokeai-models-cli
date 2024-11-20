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
    update_cache,
    about_cli,
    delete_models,
)

"""
==============================================================================
Invoke Models CLI - Simplified Tool for working with orphaned Invoke AI models
==============================================================================

Invoke models CLI is a simplified tool for working with orphaned Invoke AI models
left in the database after they have been deleted by a external source. It allows
you to list, compare, and delete models automatically or via a selection menu.

Wrote this tool to solve a personal pain point with orphaned external models
that are not managed by Invoke AI. This tool is not a replacement for the
official Invoke AI web ui.


Usage:
$ pipx install invokeai-models (recommended)
$ pipx install . (if you want to install it globally)
$ pip install -e . (if you want to install it locally and poke around, 
make sure to create a virtual environment)
$ invokeai-models [OPTIONS] [COMMAND] [ARGS]

Commands:

invokeai-models database create-snapshot
invokeai-models database list-snapshots
invokeai-models database delete-snapshot
invokeai-models database restore-snapshot
invokeai-models local-models
invokeai-models compare-models
invokeai-models sync-models
invokeai-models database-models
invokeai-models about
"""

__version__ = __version__
__all__ = ["invoke_models_cli"]

invoke_models_cli = typer.Typer()
database_cli = typer.Typer()

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


@invoke_models_cli.command("update-cache")
def update_cache_command():
    """
    Manually update both local and database model caches.
    """
    update_cache(display=True)


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


@invoke_models_cli.command(
    "compare-models", help="Compare models in the database with local files."
)
def compare_models_command():
    compare_models_display()


@invoke_models_cli.command(
    "sync-models", help="Sync database models with local model files."
)
def sync_models_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Perform a dry run without making changes"
    )
):
    sync_models_commands(dry_run=dry_run)


@invoke_models_cli.command(
    "delete-models", help="Delete models from the database and disk."
)
def delete_models_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Perform a dry run without making changes"
    )
):
    delete_models(dry_run=dry_run)


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
