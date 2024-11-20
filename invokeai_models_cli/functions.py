import typer
import shutil
import os
import json
import inquirer
import importlib.resources
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Union
import sqlite3
from .helpers import (
    feedback_message,
    create_table,
    random_name,
    process_tuples,
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
SNAPSHOTS_DIR = importlib.resources.files("invokeai_models_cli") / "snapshots"
SNAPSHOTS_JSON = SNAPSHOTS_DIR / "snapshots.json"
MODELS_INDEX_JSON = SNAPSHOTS_DIR / "models-index.json"

__all__ = [
    "create_snapshot",
    "list_snapshots",
    "delete_snapshot",
    "restore_snapshot",
]

# TODO - Need to break this file in to multiple files


def get_db(connection: bool = False) -> Union[sqlite3.Connection, sqlite3.Cursor]:
    # TODO - Move this to a helper file
    database = sqlite3.connect(DATABASE_PATH)
    if connection:
        return database
    return database.cursor()


def get_database_models() -> List[Dict[str, Any]]:
    # TODO - Move this to a helper file
    cached_data = manage_cache("database_models")
    if cached_data is not None:
        return cached_data

    db_models = process_tuples(
        get_db(connection=True).execute("SELECT * FROM models").fetchall()
    )
    return manage_cache("database_models", db_models)


# ANCHOR - CACHE FUNCTIONS START
def update_cache(display: bool = True) -> None:
    """
    Manually update both local and database model caches.
    Deletes existing cache files before creating new ones.
    """
    # TODO - Cache was not updating correctly, need to figure out why, deleting and recreating works fine

    # Delete existing cache files
    for cache_type in ["local_models", "database_models"]:
        cache_file = os.path.join(SNAPSHOTS_DIR, f"{cache_type}_cache.json")
        if os.path.exists(cache_file):
            os.remove(cache_file)
            # if display:
            #     feedback_message("Deleted existing cache file.", "success")

    # Update local models cache
    local_models = collect_model_info(MODELS_DIR)
    manage_cache("local_models", local_models)

    # Update database models cache
    db_models = process_tuples(
        get_db(connection=True).execute("SELECT * FROM models").fetchall()
    )
    manage_cache("database_models", db_models)

    if display:
        feedback_message("Successfully updated cache.", "success")


def manage_cache(
    cache_type: str, data: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    cache_file = os.path.join(SNAPSHOTS_DIR, f"{cache_type}_cache.json")
    current_time = datetime.now()

    if data is not None:
        cache = {"last_updated": current_time.isoformat(), "data": data}
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)
        return data

    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache = json.load(f)

        last_updated = datetime.fromisoformat(cache["last_updated"])
        if current_time - last_updated < timedelta(hours=1):
            return cache["data"]

    # If we reach here, either the cache doesn't exist or it's too old
    return None


# ANCHOR - CACHE FUNCTIONS END


# ANCHOR: DATABASE FUNCTIONS START
def create_snapshot() -> None:
    if not os.access(SNAPSHOTS_DIR, os.W_OK):
        console.print(
            "[bold red]Error:[/bold red] No write permission for the snapshots directory."
        )
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot_name = f"{random_name()}_{timestamp.replace(':', '-')}.db"
    snapshot_path = os.path.join(SNAPSHOTS_DIR, snapshot_name)

    try:
        console.print("[green]Creating snapshot...[/green]")

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


def load_snapshots():
    try:
        with importlib.resources.open_text(
            "invokeai_models_cli.snapshots", "snapshots.json"
        ) as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(
            "[bold yellow]Warning:[/bold yellow] Snapshots file not found. Starting with an empty list."
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

    choices = [f"{s['name']} ({s['timestamp']})" for s in snapshots]

    questions = [
        inquirer.Checkbox(
            "snapshots",
            message="Select snapshots to delete (use spacebar to select, enter to confirm)",
            choices=choices,
        )
    ]

    answers = inquirer.prompt(questions)

    if not answers or not answers["snapshots"]:
        console.print("No snapshots selected. Deletion cancelled.")
        return

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

    choices = [f"{s['name']} ({s['timestamp']})" for s in snapshots]
    choices.append("Cancel")

    questions = [
        inquirer.List(
            "snapshot",
            message="Select a snapshot to restore",
            choices=choices,
            default="Cancel",
        )
    ]

    answers = inquirer.prompt(questions)

    if not answers or answers["snapshot"] == "Cancel":
        console.print("Restoration cancelled.")
        return

    snapshot_name = answers["snapshot"].split(" (")[0]
    snapshot_to_restore = next(
        (s for s in snapshots if s["name"] == snapshot_name), None
    )

    if not snapshot_to_restore:
        console.print("[bold red]Error:[/bold red] Selected snapshot not found.")
        return

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

    backup_path = DATABASE_PATH + ".backup"
    try:
        shutil.copy2(DATABASE_PATH, backup_path)
        console.print(f"[green]Current database backed up to {backup_path}[/green]")
    except Exception as e:
        console.print(
            f"[bold red]Error backing up current database:[/bold red] {str(e)}"
        )
        return

    try:
        shutil.copy2(snapshot_path, DATABASE_PATH)
        console.print(
            f"[green]Snapshot '{snapshot_name}' successfully restored.[/green]"
        )
    except Exception as e:
        console.print(f"[bold red]Error restoring snapshot:[/bold red] {str(e)}")
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
        if os.path.exists(backup_path):
            os.remove(backup_path)


# ANCHOR: DATABASE FUNCTIONS END


# ANCHOR: FILTER FUNCTIONS START
def filter_and_compare_models(
    local_models: List[Dict[str, Any]], db_models: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Filter database models and compare with local model files.

    Args:
    local_models (List[Dict[str, Any]]): Information about local model files.
    db_models (List[Dict[str, Any]]): Information about models in the database.

    Returns:
    List[Dict[str, Any]]: List of models in the database but not on disk.
    """
    update_cache(display=False)
    filtered_db_models = [
        model
        for model in db_models
        if model.get("metadata", {}).get("source_type") == "path"
        and model.get("metadata", {}).get("format", "").lower()
        in ["lora", "checkpoint"]
    ]

    local_filenames = {model["name"] for model in local_models}
    db_filenames = {model["name"] for model in filtered_db_models}

    missing_on_disk = db_filenames - local_filenames

    missing_models = sorted(
        [model for model in filtered_db_models if model["name"] in missing_on_disk],
        key=itemgetter("name"),
    )

    return missing_models


def display_missing_models(missing_models: List[Dict[str, Any]]) -> None:
    """
    Display the models that are in the database but not on disk.

    Args:
    missing_models (List[Dict[str, Any]]): List of models missing on disk.
    """
    models_table = Table(title="Models in Database but not on Disk")

    models_table.add_column("Name", justify="left", style="yellow")
    models_table.add_column("Type", justify="left", style="cyan")
    models_table.add_column("Format", justify="left", style="magenta")
    models_table.add_column("Path", justify="left", style="green")
    models_table.add_column("Created", justify="left", style="white")
    models_table.add_column("Updated", justify="left", style="yellow")

    for model in missing_models:
        metadata = model.get("metadata", {})
        timestamps = model.get("Timestamps", {})
        models_table.add_row(
            model["name"],
            metadata.get("type", "N/A"),
            metadata.get("format", "N/A"),
            metadata.get("path", "N/A"),
            timestamps.get("created_at", "N/A"),
            timestamps.get("updated_at", "N/A"),
        )

    if missing_models:
        console.print(models_table)
    else:
        feedback_message("No missing models found.", "success")


def delete_models(dry_run: bool = False) -> None:
    db_models = get_database_models()

    if not db_models:
        feedback_message("No models found in the database.", "info")
        return

    choices = [
        f"{model['name']} ({model['metadata'].get('format', 'Unknown')})"
        for model in db_models
    ]

    questions = [
        inquirer.Checkbox(
            "models_to_delete",
            message="Select models to delete (from database and disk)",
            choices=choices,
        )
    ]

    answers = inquirer.prompt(questions)

    if not answers or not answers["models_to_delete"]:
        feedback_message("No models selected for deletion.", "info")
        return

    selected_models = [
        model
        for model in db_models
        if f"{model['name']} ({model['metadata'].get('format', 'Unknown')})"
        in answers["models_to_delete"]
    ]

    if dry_run:
        console.print("\n[bold]Dry Run: Changes that would be made:[/bold]")
        for model in selected_models:
            console.print(f"[red]Would delete model:[/red] {model['name']}")
            console.print(f"  [dim]From database[/dim]")
            file_path = model["metadata"].get("path")
            if file_path and os.path.exists(file_path):
                console.print(f"  [dim]From disk: {file_path}[/dim]")
            else:
                console.print(f"  [dim]File not found on disk: {file_path}[/dim]")
            console.print()
        console.print(
            "[bold green]No changes were made to the database or disk.[/bold green]"
        )
        return

    confirm = inquirer.confirm(
        f"Are you sure you want to delete {len(selected_models)} model(s) from both the database and disk? This action is irreversible."
    )

    if not confirm:
        feedback_message("Deletion cancelled.", "info")
        return

    db_conn = get_db(connection=True)
    cursor = db_conn.cursor()

    try:
        for model in selected_models:

            cursor.execute("DELETE FROM models WHERE name = ?", (model["name"],))

            file_path = model["metadata"].get("path")
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                feedback_message(f"Deleted model file: {file_path}", "success")
            else:
                feedback_message(
                    f"Model file not found on disk: {file_path}", "warning"
                )

        db_conn.commit()
        feedback_message("Selected models deleted from database and disk.", "success")
    except sqlite3.Error as e:
        db_conn.rollback()
        feedback_message(
            f"Error during deletion: {str(e)}. Changes rolled back.", "error"
        )
    except Exception as e:
        feedback_message(f"Error deleting model files: {str(e)}", "error")
    finally:
        db_conn.close()

    update_cache()


def sync_models(
    local_models: List[Dict[str, Any]],
    db_models: List[Dict[str, Any]],
    dry_run: bool = False,
) -> None:
    missing_models = filter_and_compare_models(local_models, db_models)

    if not missing_models:
        feedback_message("All database models are in sync with local files.", "success")
        return

    if not dry_run:
        feedback_message(
            "Warning: This operation will modify the database, a snapshot will be created before any changes are made.",
            "warning",
        )
        create_snapshot()

    questions = [
        inquirer.List(
            "sync_method",
            message="How would you like to sync the models?",
            choices=["Automatically", "Manually select models"],
        ),
    ]
    answers = inquirer.prompt(questions)

    if answers["sync_method"] == "Manually select models":
        models_to_sync = select_models_to_sync(missing_models)
    else:
        models_to_sync = missing_models

    if not models_to_sync:
        feedback_message("No models selected for sync. Operation cancelled.", "info")
        return

    if dry_run:
        perform_dry_run(models_to_sync, local_models)
    else:
        perform_sync(models_to_sync, local_models)

    manage_cache("local_models", collect_model_info(MODELS_DIR))
    manage_cache("database_models", get_database_models())


def perform_dry_run(
    models_to_sync: List[Dict[str, Any]], local_models: List[Dict[str, Any]]
) -> None:
    console.print("\n[bold]Dry Run: Changes that would be made:[/bold]")

    for model in models_to_sync:
        local_model = next(
            (m for m in local_models if m["name"] == model["name"]), None
        )
        if local_model:
            console.print(
                f"[yellow]Would update path for model:[/yellow] {model['name']}"
            )
            console.print(
                f"  [dim]Old path:[/dim] {model['metadata'].get('path', 'N/A')}"
            )
            console.print(f"  [dim]New path:[/dim] {local_model['file_path']}\n")
        else:
            console.print(
                f"[red]Would delete model from database:[/red] {model['name']}\n"
            )

    console.print("[bold green]No changes were made to the database.[/bold green]")


def select_models_to_sync(missing_models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Allow user to manually select models to sync.

    Args:
    missing_models (List[Dict[str, Any]]): List of models missing from local files.

    Returns:
    List[Dict[str, Any]]: List of selected models to sync.
    """
    choices = [
        f"{model['name']} ({model.get('metadata', {}).get('format', 'Unknown')})"
        for model in missing_models
    ]
    questions = [
        inquirer.Checkbox(
            "selected_models", message="Select models to sync", choices=choices
        ),
    ]
    answers = inquirer.prompt(questions)
    selected_names = [name.split(" (")[0] for name in answers["selected_models"]]
    return [model for model in missing_models if model["name"] in selected_names]


def perform_sync(
    models_to_sync: List[Dict[str, Any]], local_models: List[Dict[str, Any]]
) -> None:
    """
    Perform the actual sync operation on the database.

    Args:
    models_to_sync (List[Dict[str, Any]]): List of models to sync.
    local_models (List[Dict[str, Any]]): Information about local model files.
    """
    db_conn = get_db(connection=True)
    cursor = db_conn.cursor()

    try:
        for model in models_to_sync:
            local_model = next(
                (m for m in local_models if m["name"] == model["name"]), None
            )
            if local_model:
                new_path = local_model["file_path"]
                cursor.execute(
                    "UPDATE models SET path = ? WHERE name = ?",
                    (new_path, model["name"]),
                )
                feedback_message(f"Updated path for model: {model['name']}", "success")
            else:
                cursor.execute("DELETE FROM models WHERE name = ?", (model["name"],))
                feedback_message(
                    f"Deleted model from database: {model['name']}", "warning"
                )

        db_conn.commit()
        feedback_message("Sync operation completed successfully.", "success")
    except sqlite3.Error as e:
        db_conn.rollback()
        feedback_message(
            f"Error during sync operation: {str(e)}. Changes rolled back.", "error"
        )
    finally:
        db_conn.close()


def compare_models_display() -> None:
    local_models = manage_cache("local_models")
    db_models = manage_cache("database_models")
    missing_models = filter_and_compare_models(local_models, db_models)
    display_missing_models(missing_models)

    if missing_models:
        questions = [
            inquirer.List(
                "action",
                message="What would you like to do?",
                choices=["Sync models", "Dry run", "Cancel"],
            ),
        ]
        answers = inquirer.prompt(questions)

        if answers["action"] == "Sync models":
            sync_models(local_models, db_models)
        elif answers["action"] == "Dry run":
            sync_models(local_models, db_models, dry_run=True)
        else:
            feedback_message("Operation cancelled.", "info")


def compare_models(
    local_models: List[Dict[str, Any]], db_models: List[Dict[str, Any]]
) -> None:
    """
    Compare database entries with local model files and display differences.
    Only includes models with source_type:path and format of LORA or checkpoint.

    Args:
    local_models (List[Dict[str, Any]]): Information about local model files.
    db_models (List[Dict[str, Any]]): Information about models in the database.
    """
    missing_models = filter_and_compare_models(local_models, db_models)
    display_missing_models(missing_models)


def collect_model_info(models_dir: str) -> List[Dict[str, Any]]:
    """
    Collect information about model files in the specified directories.

    Args:
    models_dir (str): Path to the directory containing 'checkpoints' and 'lora' folders.

    Returns:
    List[Dict[str, Any]]: List of dictionaries containing information about each model file
    with .safetensor extension.
    """
    cached_data = manage_cache("local_models")
    if cached_data is not None:
        return cached_data

    model_info = []
    subdirs = ["checkpoints", "loras"]

    for subdir in subdirs:
        dir_path = os.path.join(models_dir, subdir)
        if not os.path.isdir(dir_path):
            continue

        for root, _, files in os.walk(dir_path):
            for file in files:
                if not file.endswith(".safetensors"):
                    continue

                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, models_dir)

                stats = os.stat(file_path)
                created = datetime.fromtimestamp(stats.st_ctime)
                modified = datetime.fromtimestamp(stats.st_mtime)

                type_parts = relative_path.split(os.path.sep)[1:-1]
                type_str = " ".join(
                    part.replace("_", " ") for part in type_parts
                ).lower()

                model_info.append(
                    {
                        "filename": file,
                        "name": os.path.splitext(file)[0],
                        "file_path": file_path,
                        "relative_path": relative_path,
                        "type": (type_str if type_str else subdir.rstrip("s")),
                        "created": created.isoformat(),
                        "updated": modified.isoformat(),
                    }
                )

    return manage_cache("local_models", model_info)


def display_database_models(data: List[Union[Dict[str, Any], Tuple]]) -> None:
    console = Console()

    for item in data:
        if isinstance(item, tuple):
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

        if item.get("source_type") != "path":
            continue

        tree = Tree(f"[bold blue]{item.get('name', 'Unnamed Item')}[/bold blue]")

        main_attrs = ["key", "hash", "base", "type", "format", "description"]
        for attr in main_attrs:
            if attr in item and item[attr]:
                tree.add(f"[green]{attr}:[/green] {item[attr]}")

        path_tree = tree.add("Paths")
        if "path" in item:
            path_tree.add(f"[yellow]path:[/yellow] {item['path']}")
        if "source" in item:
            path_tree.add(f"[yellow]source:[/yellow] {item['source']}")
        path_tree.add(f"[yellow]source_type:[/yellow] {item['source_type']}")

        time_tree = tree.add("Timestamps")
        if "created_at" in item:
            time_tree.add(f"[cyan]created_at:[/cyan] {item['created_at']}")
        if "updated_at" in item:
            time_tree.add(f"[cyan]updated_at:[/cyan] {item['updated_at']}")

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

    models_by_type = {}
    for model in model_info:
        model_type = model["type"]
        if model_type not in models_by_type:
            models_by_type[model_type] = []
        models_by_type[model_type].append(model)

    for model_type, models in models_by_type.items():
        console.print(f"\n[bold blue]== {model_type.upper()} ==[/bold blue]")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Filename", style="cyan", no_wrap=True)
        table.add_column("Relative Path", style="white")
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


def database_models_display():
    db_models = get_database_models()

    if not db_models:
        feedback_message("No models found in the database.", "info")
        return

    console.print(f"\n[bold]Total models in database:[/bold] {len(db_models)}")

    format_counts = {}
    for model in db_models:
        model_format = model.get("metadata", {}).get("format", "Unknown")
        format_counts[model_format] = format_counts.get(model_format, 0) + 1

    for model_format, count in format_counts.items():
        console.print(f"[cyan]{model_format}:[/cyan] {count}")

    display_choice = typer.prompt(
        "\nChoose display option (D: Detailed Table, T: Tree View, S: Select Model, C: Cancel)",
        default="D",
    )

    valid_choices = {
        "D": "Detailed Table",
        "T": "Tree View",
        "S": "Select Model",
        "C": "Cancel",
    }
    while display_choice.upper() not in valid_choices:
        console.print("[red]Invalid choice. Please try again.[/red]")
        display_choice = typer.prompt(
            "\nChoose display option (D: Detailed Table, T: Tree View, S: Select Model, C: Cancel)",
            default="D",
        )

    if display_choice.upper() == "D":
        display_detailed_table(db_models)
    elif display_choice.upper() == "T":
        display_tree_view(db_models)
    elif display_choice.upper() == "C":
        feedback_message("Operation cancelled.", "info")
        return
    else:
        display_model_details(db_models)


def display_detailed_table(db_models):
    models_table = create_table(
        "Database Models",
        [
            ("Name", "yellow"),
            ("Type", "cyan"),
            ("Format", "magenta"),
            ("Path", "green"),
            ("Created", "white"),
            ("Updated", "yellow"),
        ],
    )

    for model in db_models:
        metadata = model.get("metadata", {})
        models_table.add_row(
            model["name"],
            metadata.get("type", "N/A"),
            metadata.get("format", "N/A"),
            metadata.get("path", "N/A"),
            model.get("created_at", "N/A"),
            model.get("updated_at", "N/A"),
        )

    console.print(models_table)


def display_tree_view(db_models):
    tree = Tree("Database Models")
    for model in db_models:
        model_node = tree.add(f"[yellow]{model['name']}[/yellow]")
        add_model_details_to_tree(model_node, model)
    console.print(tree)


def add_model_details_to_tree(node, model):
    metadata = model.get("metadata", {})

    node.add(f"[cyan]Type:[/cyan] {metadata.get('type', 'N/A')}")
    node.add(f"[magenta]Format:[/magenta] {metadata.get('format', 'N/A')}")
    node.add(f"[green]Path:[/green] {metadata.get('path', 'N/A')}")
    node.add(f"[white]Created:[/white] {model.get('created_at', 'N/A')}")
    node.add(f"[yellow]Updated:[/yellow] {model.get('updated_at', 'N/A')}")


def display_model_details(db_models):
    model_names = [model["name"] for model in db_models]
    selected_model = typer.prompt(
        "Enter the name of the model to view details", type=str
    )

    if selected_model not in model_names:
        feedback_message("Model not found.", "error")
        return

    model = next((m for m in db_models if m["name"] == selected_model), None)
    if model:
        tree = Tree(f"[bold]{model['name']}[/bold]")
        add_model_details_to_tree(tree, model)
        console.print(tree)


def display_tree_view(db_models):
    tree = Tree("Database Models")
    for model in db_models:
        model_node = tree.add(f"[yellow]{model['name']}[/yellow]")
        add_model_details_to_tree(model_node, model)
    console.print(tree)


def add_model_details_to_tree(node, model):
    metadata = model.get("metadata", {})
    timestamps = model.get("Timestamps", {})

    node.add(f"[cyan]Type:[/cyan] {metadata.get('type', 'N/A')}")
    node.add(f"[magenta]Format:[/magenta] {metadata.get('format', 'N/A')}")
    node.add(f"[green]Path:[/green] {metadata.get('path', 'N/A')}")
    node.add(f"[white]Created:[/white] {timestamps.get('created_at', 'N/A')}")
    node.add(f"[yellow]Updated:[/yellow] {timestamps.get('updated_at', 'N/A')}")


def display_model_details(db_models):
    model_names = [model["name"] for model in db_models]
    selected_model = typer.prompt(
        "Enter the name of the model to view details", type=str
    )

    if selected_model not in model_names:
        feedback_message("Model not found.", "error")
        return

    model = next((m for m in db_models if m["name"] == selected_model), None)
    if model:
        tree = Tree(f"[bold]{model['name']}[/bold]")
        add_model_details_to_tree(tree, model)
        console.print(tree)


def display_tree_view(db_models):
    tree = Tree("Database Models")
    for model in db_models:
        model_node = tree.add(f"[yellow]{model['name']}[/yellow]")
        add_model_details_to_tree(model_node, model)
    console.print(tree)


def add_model_details_to_tree(node, model):
    metadata = model.get("metadata", {})

    node.add(f"[cyan]Type:[/cyan] {metadata.get('type', 'N/A')}")
    node.add(f"[magenta]Format:[/magenta] {metadata.get('format', 'N/A')}")
    node.add(f"[green]Path:[/green] {metadata.get('path', 'N/A')}")
    node.add(f"[white]Created:[/white] {model.get('created_at', 'N/A')}")
    node.add(f"[yellow]Updated:[/yellow] {model.get('updated_at', 'N/A')}")


def display_model_details(db_models):
    model_names = [model["name"] for model in db_models]

    questions = [
        inquirer.List(
            "selected_model",
            message="Select a model to view details",
            choices=model_names,
        )
    ]

    answers = inquirer.prompt(questions)
    selected_model = answers["selected_model"]

    model = next((m for m in db_models if m["name"] == selected_model), None)
    if model:
        tree = Tree(f"[bold]{model['name']}[/bold]")
        add_model_details_to_tree(tree, model)
        console.print(tree)
    else:
        feedback_message("Model not found.", "error")


def compare_models_display() -> None:
    db = get_db(connection=True)
    invokeai_models = db.execute("SELECT * FROM models").fetchall()
    local_models = collect_model_info(MODELS_DIR)
    database_models = process_tuples(invokeai_models)
    compare_models(local_models, database_models)


def sync_models_commands():
    local_models = collect_model_info(MODELS_DIR)
    db_models = process_tuples(
        get_db(connection=True).execute("SELECT * FROM models").fetchall()
    )
    sync_models(local_models, db_models)


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
            with importlib.resources.open_text("invokeai_models_cli", document) as f:
                content = f.read()
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".md"
            ) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            display_readme(temp_file_path)
            Path(temp_file_path).unlink()
        except (FileNotFoundError, ImportError, ModuleNotFoundError):
            local_path = Path(document)
            if local_path.exists():
                display_readme(str(local_path))
            else:
                parent_path = local_path.parent.parent / document
                if parent_path.exists():
                    display_readme(str(parent_path))
                else:
                    typer.echo(f"{document} not found.")


# ANCHOR: ABOUT FUNCTIONS END
