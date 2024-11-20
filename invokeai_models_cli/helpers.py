import typer
import random
import json

from typing import Dict, Any, Tuple, List
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console(soft_wrap=True)

__all__ = [
    "feedback_message",
    "create_table",
    "add_rows_to_table",
    "random_name",
    "process_tuples",
    "tuple_to_dict",
    "get_db",
]

# function that creates random names and rturns them


def random_name(num_words: int = 2, separator: str = "_") -> str:
    adjectives = [
        "happy",
        "sunny",
        "clever",
        "brave",
        "calm",
        "kind",
        "wise",
        "proud",
        "strong",
        "neat",
        "soft",
        "warm",
        "bright",
        "cool",
        "gentle",
        "sharp",
        "fresh",
        "sweet",
        "wild",
        "bold",
    ]

    nouns = [
        "apple",
        "river",
        "mountain",
        "forest",
        "ocean",
        "star",
        "moon",
        "sun",
        "cloud",
        "tree",
        "flower",
        "bird",
        "tiger",
        "lion",
        "wolf",
        "bear",
        "fish",
        "deer",
        "fox",
        "owl",
    ]

    words = []
    for i in range(num_words):
        if i == num_words - 1:
            words.append(random.choice(nouns))
        else:
            words.append(random.choice(adjectives))

    return separator.join(words)


def feedback_message(message: str, type: str = "info") -> None:
    options = {
        "types": {
            "simple": "white",
            "info": "white",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "exception": "red",
        },
        "titles": {
            "info": "Information",
            "success": "Success",
            "warning": "Warning",
            "error": "Error Message",
            "exception": "Exception Message",
        },
    }

    if type not in options["types"]:
        return None

    if type == "simple":
        console.print(message)
        # return message with a exclamation icon
        console.print(f"[yellow]![/yellow] {message}")
        return None

    feedback_message_table = Table(style=options["types"][type])
    feedback_message_table.add_column(options["titles"][type])
    feedback_message_table.add_row(message)

    if type == "exception":
        console.print_exception(feedback_message_table)
        raise typer.Exit()
    console.print(feedback_message_table)
    return None


def create_table(title: str, columns: list) -> Table:
    table = Table(title=title, title_justify="left")
    for col_name, style in columns:
        table.add_column(col_name, style=style)
    return table


def add_rows_to_table(table: Table, data: Dict[str, Any]) -> None:
    for key, value in data.items():
        if isinstance(value, list):
            value = ", ".join(map(str, value))
        table.add_row(key, str(value))


def process_tuples(tuple_list: List[Tuple]) -> List[Dict[str, Any]]:
    return [tuple_to_dict(t) for t in tuple_list]


def tuple_to_dict(input_tuple: Tuple) -> Dict[str, Any]:
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

    result = dict(zip(keys, input_tuple))

    if result["metadata_json"]:
        result["metadata"] = json.loads(result["metadata_json"])
        del result["metadata_json"]
    else:
        result["metadata"] = None

    return result


def ensure_snapshots_dir(directory: Path) -> bool:
    if not directory.exists():
        try:
            directory.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]Created snapshots directory: {directory}[/green]")
        except Exception as e:
            console.print(
                f"[bold red]Error creating snapshots directory:[/bold red] {str(e)}"
            )
            return False
    return True
