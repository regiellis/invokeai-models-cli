import typer
import shutil
import os
import json
import inquirer
import importlib.resources

import tempfile

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Union

import sqlite3
from .helpers import (
    feedback_message,
    create_table,
    random_name,
    process_tuples,
    tuple_to_dict,
)

from operator import itemgetter
from rich.markdown import Markdown
from rich.progress import Progress
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.console import Console

from rich.traceback import install

install()

from . import INVOKE_AI_DIR, MODELS_DIR, SNAPSHOTS

console = Console()

# Get the package directory
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_PATH = os.path.join(INVOKE_AI_DIR, "databases", "invokeai.db")
SNAPSHOTS_DIR = os.path.join(PACKAGE_DIR, "snapshots")
SNAPSHOTS_JSON = os.path.join(SNAPSHOTS_DIR, "snapshots.json")
MODELS_INDEX_JSON = os.path.join(SNAPSHOTS_DIR, "models-index.json")

__all__ = [
    "create_snapshot",
    "list_snapshots",
    "delete_snapshot",
    "restore_snapshot",
]


def get_db(connection: bool) -> Any:
    database = sqlite3.connect(DATABASE_PATH)
    if connection:
        return database

    return database.cursor()


# ANCHOR: DATABASE FUNCTIONS START
def create_snapshot() -> None:
    if not os.access(SNAPSHOTS_DIR, os.W_OK):
        console.print(
            "[bold red]Error:[/bold red] No write permission for the snapshots directory."
        )
        return

    # Generate a human-readable timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot_name = f"{random_name()}_{timestamp.replace(':', '-')}.db"
    snapshot_path = os.path.join(SNAPSHOTS_DIR, snapshot_name)

    try:
        console.print("[green]Creating snapshot...[/green]")

        # Use SQLite backup API
        with (
            get_db(connection=True) as source_conn,
            sqlite3.connect(snapshot_path) as dest_conn,
        ):
            source_conn.backup(dest_conn)

        snapshots = load_snapshots()
        snapshots.append(
            {"name": snapshot_name, "timestamp": timestamp, "path": snapshot_path}
        )

        if len(snapshots) > int(SNAPSHOTS):
            oldest_snapshot = snapshots.pop(0)
            old_snapshot_path = os.path.join(SNAPSHOTS_DIR, oldest_snapshot["name"])
            if os.path.exists(old_snapshot_path):
                os.remove(old_snapshot_path)
                feedback_message(
                    f"Removed oldest snapshot: {oldest_snapshot['name']}", "info"
                )

        save_snapshots(snapshots)
        feedback_message(f"Created snapshot: {snapshot_name}", "success")
    except sqlite3.Error as e:
        feedback_message(f"Error creating snapshot: {str(e)}", "error")
    except Exception as e:
        feedback_message(f"Error creating snapshot: {str(e)}", "error")


def load_snapshots() -> List[Dict[str, str]]:
    if os.path.exists(SNAPSHOTS_JSON):
        try:
            with open(SNAPSHOTS_JSON, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            console.print(
                "[bold yellow]Warning:[/bold yellow] Snapshots file is corrupted. Starting with an empty list."
            )
    return []


def save_snapshots(snapshots: List[Dict[str, str]]) -> None:
    try:
        with open(SNAPSHOTS_JSON, "w") as f:
            json.dump(snapshots, f, indent=2)
    except Exception as e:
        console.print(f"[bold red]Error saving snapshots metadata:[/bold red] {str(e)}")


def list_snapshots() -> None:
    snapshots = load_snapshots()
    if not snapshots:
        console.print("[yellow]No snapshots found.[/yellow]")
        return

    snapshots_table = create_table(
        "Database Snapshots",
        [("Name", "white"), ("Timestamp", "yellow dim"), ("Path", "white")],
    )
    for snapshot in snapshots:
        snapshots_table.add_row(
            snapshot["name"], snapshot["timestamp"], snapshot["path"]
        )
    console.print(snapshots_table)


def delete_snapshot() -> None:
    snapshots = load_snapshots()

    if not snapshots:
        console.print("[yellow]No snapshots found to delete.[/yellow]")
        return

    # Create choices for the inquirer prompt
    choices = [f"{s['name']} ({s['timestamp']})" for s in snapshots]

    # Create the checkbox prompt
    questions = [
        inquirer.Checkbox(
            "snapshots",
            message="Select snapshots to delete (use spacebar to select, enter to confirm)",
            choices=choices,
        )
    ]

    # Present the selection menu
    answers = inquirer.prompt(questions)

    if not answers or not answers["snapshots"]:
        console.print("No snapshots selected. Deletion cancelled.")
        return

    # Confirmation prompt
    confirm = inquirer.confirm(
        f"Are you sure you want to delete {len(answers['snapshots'])} snapshot(s)? This action is irreversible."
    )

    if not confirm:
        console.print("Deletion cancelled.")
        return

    for selected in answers["snapshots"]:
        snapshot_name = selected.split(" (")[0]  # Extract the name from the selection
        snapshots = [s for s in snapshots if s["name"] != snapshot_name]
        snapshot_path = os.path.join(SNAPSHOTS_DIR, snapshot_name)
        if os.path.exists(snapshot_path):
            try:
                os.remove(snapshot_path)
                console.print(
                    f"[green]Snapshot '{snapshot_name}' deleted successfully.[/green]"
                )
            except Exception as e:
                console.print(
                    f"[bold red]Error deleting snapshot file '{snapshot_name}':[/bold red] {str(e)}"
                )
        else:
            console.print(
                f"[yellow]Warning: Snapshot file '{snapshot_name}' not found on disk.[/yellow]"
            )

    save_snapshots(snapshots)
    console.print("[green]Snapshot deletion process completed.[/green]")


def restore_snapshot():
    snapshots = load_snapshots()

    if not snapshots:
        console.print("[yellow]No snapshots found to restore.[/yellow]")
        return

    # Create choices for the inquirer prompt
    choices = [f"{s['name']} ({s['timestamp']})" for s in snapshots]
    choices.append("Cancel")

    # Create the selection prompt
    questions = [
        inquirer.List(
            "snapshot",
            message="Select a snapshot to restore",
            choices=choices,
            default="Cancel",
        )
    ]

    # Present the selection menu
    answers = inquirer.prompt(questions)

    if not answers or answers["snapshot"] == "Cancel":
        console.print("Restoration cancelled.")
        return

    # Extract the snapshot name from the selection
    snapshot_name = answers["snapshot"].split(" (")[0]
    snapshot_to_restore = next(
        (s for s in snapshots if s["name"] == snapshot_name), None
    )

    if not snapshot_to_restore:
        console.print("[bold red]Error:[/bold red] Selected snapshot not found.")
        return

    # Confirmation prompt
    confirm = inquirer.confirm(
        "Are you sure you want to restore this snapshot? This will replace your current database."
    )

    if not confirm:
        console.print("Restoration cancelled.")
        return

    snapshot_path = os.path.join(SNAPSHOTS_DIR, snapshot_name)
    if not os.path.exists(snapshot_path):
        console.print(
            f"[bold red]Error:[/bold red] Snapshot file '{snapshot_name}' not found on disk."
        )
        return

    # Backup current database
    backup_path = DATABASE_PATH + ".backup"
    try:
        shutil.copy2(DATABASE_PATH, backup_path)
        console.print(f"[green]Current database backed up to {backup_path}[/green]")
    except Exception as e:
        console.print(
            f"[bold red]Error backing up current database:[/bold red] {str(e)}"
        )
        return

    # Restore snapshot
    try:
        shutil.copy2(snapshot_path, DATABASE_PATH)
        console.print(
            f"[green]Snapshot '{snapshot_name}' successfully restored.[/green]"
        )
    except Exception as e:
        console.print(f"[bold red]Error restoring snapshot:[/bold red] {str(e)}")
        # If restoration fails, try to restore the backup
        try:
            shutil.copy2(backup_path, DATABASE_PATH)
            console.print(
                "[yellow]Restoration failed. Original database has been restored.[/yellow]"
            )
        except Exception as e2:
            console.print(
                f"[bold red]Error restoring original database:[/bold red] {str(e2)}"
            )
            console.print(
                "[bold yellow]Please manually restore your database from the backup file.[/bold yellow]"
            )
    finally:
        # Clean up the backup file
        if os.path.exists(backup_path):
            os.remove(backup_path)


def ensure_snapshots_dir():
    if not os.path.exists(SNAPSHOTS_DIR):
        try:
            os.makedirs(SNAPSHOTS_DIR)
            console.print(
                f"[green]Created snapshots directory: {SNAPSHOTS_DIR}[/green]"
            )
        except Exception as e:
            console.print(
                f"[bold red]Error creating snapshots directory:[/bold red] {str(e)}"
            )
            return False
    return True


# ANCHOR: DATABASE FUNCTIONS END

def filter_unmatched(
    local_models: List[Dict[str, Any]], db_models: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    set_local = set(local_models)
    set_db = set(db_models)
    unmatched = list(set_local.symmetric_difference(set_db))

    return unmatched


def compare_models(
    local_models: List[Dict[str, Any]], db_models: List[Dict[str, Any]]
) -> None:
    """
    Compare local model files with database entries and display differences.

    Args:
    local_models (List[Dict[str, Any]]): Information about local model files.
    db_models (List[Dict[str, Any]]): Information about models in the database.
    """

    # Create sets for easy comparison
    local_filenames = {model["name"] for model in local_models}
    db_filenames = {model["name"] for model in db_models}

    # Models present in local files but not in the database
    missing_in_db = local_filenames - db_filenames
    
    # Prepare a table to display the results
    console = Console()
    table = Table(title="Local Models Missing in Database")

    table.add_column("Filename", justify="left", style="cyan")
    table.add_column("Type", justify="left", style="magenta")
    table.add_column("Created", justify="left", style="green")
    table.add_column("Updated", justify="left", style="yellow")

    # Filter and sort missing models
    missing_models = sorted(
        [model for model in local_models if model["filename"] in missing_in_db],
        key=itemgetter("filename")
    )

    # Add entries for missing models
    for model in missing_models:
        table.add_row(
            model["filename"],
            model["type"],
            model["created"],
            model["updated"],
        )

    # Display the table
    if missing_models:
        console.print(table)
    else:
        console.print("All local models are present in the database.")


def collect_model_info(models_dir: str) -> List[Dict[str, Any]]:
    """
    Collect information about model files in the specified directories.

    Args:
    models_dir (str): Path to the directory containing 'checkpoints' and 'lora' folders.

    Returns:
    List[Dict[str, Any]]: List of dictionaries containing information about each model file with .safetensor extension.
    """
    model_info = []
    subdirs = ["checkpoints", "loras"]

    for subdir in subdirs:
        dir_path = os.path.join(models_dir, subdir)
        if not os.path.isdir(dir_path):
            continue

        for root, _, files in os.walk(dir_path):
            for file in files:
                # Only process files with .safetensors extension
                if not file.endswith(".safetensors"):
                    continue

                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, models_dir)

                # Get file stats
                stats = os.stat(file_path)
                created = datetime.fromtimestamp(stats.st_ctime)
                modified = datetime.fromtimestamp(stats.st_mtime)

                # Determine type based on subdirectory
                type_parts = relative_path.split(os.path.sep)[
                    1:-1
                ]  # Exclude the main subdir and filename
                type_str = " ".join(
                    part.replace("_", " ") for part in type_parts
                ).lower()

                model_info.append(
                    {
                        "filename": file,
                        "name": os.path.splitext(file)[0],
                        "file_path": file_path,
                        "relative_path": relative_path,
                        "type": (
                            type_str if type_str else subdir.rstrip("s")
                        ),  # Use subdir name if no subdirectories
                        "created": created.isoformat(),
                        "updated": modified.isoformat(),
                    }
                )

    return model_info


def display_database_models(data: List[Union[Dict[str, Any], Tuple]]) -> None:
    console = Console()

    for item in data:
        # Check if item is a tuple or dict
        if isinstance(item, tuple):
            # Convert tuple to dict
            keys = [
                "key",
                "hash",
                "base",
                "type",
                "path",
                "format",
                "name",
                "description",
                "source",
                "source_type",
                "source_api_response",
                "cover_image",
                "metadata_json",
                "created_at",
                "updated_at",
            ]
            item = dict(zip(keys, item))

        # Only display items where source_type is "path"
        if item.get("source_type") != "path":
            continue

        # Create a tree for each item
        tree = Tree(f"[bold blue]{item.get('name', 'Unnamed Item')}[/bold blue]")

        # Add main attributes
        main_attrs = ["key", "hash", "base", "type", "format", "description"]
        for attr in main_attrs:
            if attr in item and item[attr]:
                tree.add(f"[green]{attr}:[/green] {item[attr]}")

        # Add path and source in a subtree
        path_tree = tree.add("Paths")
        if "path" in item:
            path_tree.add(f"[yellow]path:[/yellow] {item['path']}")
        if "source" in item:
            path_tree.add(f"[yellow]source:[/yellow] {item['source']}")
        path_tree.add(f"[yellow]source_type:[/yellow] {item['source_type']}")

        # Add timestamps
        time_tree = tree.add("Timestamps")
        if "created_at" in item:
            time_tree.add(f"[cyan]created_at:[/cyan] {item['created_at']}")
        if "updated_at" in item:
            time_tree.add(f"[cyan]updated_at:[/cyan] {item['updated_at']}")

        # Add metadata if present
        if "metadata" in item and item["metadata"]:
            metadata_tree = tree.add("[magenta]metadata[/magenta]")
            for k, v in item["metadata"].items():
                metadata_tree.add(f"[magenta]{k}:[/magenta] {v}")
        elif "metadata_json" in item and item["metadata_json"]:
            try:
                metadata = json.loads(item["metadata_json"])
                metadata_tree = tree.add("[magenta]metadata[/magenta]")
                for k, v in metadata.items():
                    metadata_tree.add(f"[magenta]{k}:[/magenta] {v}")
            except json.JSONDecodeError:
                tree.add("[red]Invalid metadata JSON[/red]")

        # Display the tree in a panel
        console.print(Panel(tree, expand=False))
        console.print("\n")


def display_local_models(model_info: List[Dict[str, Any]], display_tree: bool):
    """
    Display the model information in a formatted, colorful output using rich.

    Args:
    model_info (List[Dict[str, Any]]): List of dictionaries containing model information.
    """
    console = Console()

    # Group models by type
    models_by_type = {}
    for model in model_info:
        model_type = model["type"]
        if model_type not in models_by_type:
            models_by_type[model_type] = []
        models_by_type[model_type].append(model)

    # Display models grouped by type
    for model_type, models in models_by_type.items():
        console.print(f"\n[bold blue]== {model_type.upper()} ==[/bold blue]")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Filename", style="cyan", no_wrap=True)
        table.add_column("Relative Path", style="green")
        table.add_column("Created", style="yellow")
        table.add_column("Updated", style="yellow")

        for model in models:
            table.add_row(
                model["filename"],
                model["relative_path"],
                model["created"],
                model["updated"],
            )

        console.print(table)

        # Display detailed information for each model
        if display_tree:
            for model in models:
                tree = Tree(f"[bold cyan]{model['filename']}[/bold cyan]")
                tree.add(f"[yellow]Full Path:[/yellow] {model['file_path']}")
                tree.add(f"[yellow]Relative Path:[/yellow] {model['relative_path']}")
                tree.add(f"[yellow]Type:[/yellow] {model['type']}")
                tree.add(f"[yellow]Created:[/yellow] {model['created']}")
                tree.add(f"[yellow]Updated:[/yellow] {model['updated']}")

                console.print(Panel(tree, expand=False))
                console.print()

def local_models_display(display_tree: bool = False) -> None:
    local_models = collect_model_info(MODELS_DIR)
    display_local_models(local_models, display_tree)
    
    
def database_models_display() -> None:
    db = get_db(connection=True)
    invokeai_models = db.execute("SELECT * FROM models").fetchall()
    database_models = process_tuples(invokeai_models)
    display_database_models(database_models)


# def list_models_cli() -> None:
#     db = get_db(connection=True)
#     # display_model_info(collect_model_info(MODELS_DIR))
#     invokeai_models = db.execute("SELECT * FROM models").fetchall()
#     local_models = collect_model_info(MODELS_DIR)
#     database_models = process_tuples(invokeai_models)
#     compare_models(local_models, database_models)

    # display_data(invokeai_models)


# ANCHOR: ABOUT FUNCTIONS START


def display_readme(requested_file: str) -> None:

    readme_path = Path(requested_file)

    if readme_path.exists():
        with readme_path.open("r", encoding="utf-8") as f:
            markdown_content = f.read()

        md = Markdown(markdown_content)
        console.print(md)
    else:
        typer.echo(f"{requested_file} not found in the current directory.")


def about_cli(readme: bool, changelog: bool) -> None:
    documents: List[str] = []
    if readme:
        documents.append("README.md")
    if changelog:
        documents.append("CHANGELOG.md")
    if not documents:
        feedback_message(
            "No document specified. please --readme [-r] or --changelog [-c]", "warning"
        )

    for document in documents:
        try:
            # Try to get the file content from the package resources
            with importlib.resources.open_text("civitai_models_manager", document) as f:
                content = f.read()
            # Create a temporary file to pass to display_readme
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".md"
            ) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            display_readme(temp_file_path)
            # Remove the temporary file
            Path(temp_file_path).unlink()
        except (FileNotFoundError, ImportError, ModuleNotFoundError):
            # If not found in package resources, try the current directory
            local_path = Path(document)
            if local_path.exists():
                display_readme(str(local_path))
            else:
                # Try one directory up
                parent_path = local_path.parent.parent / document
                if parent_path.exists():
                    display_readme(str(parent_path))
                else:
                    typer.echo(f"{document} not found.")


# ANCHOR: ABOUT FUNCTIONS END
