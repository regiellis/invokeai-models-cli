import os
import inquirer
import importlib.resources
from pathlib import Path
from typing import Final
from dotenv import load_dotenv, set_key
import typer
import platform

from .helpers import feedback_message, ensure_snapshots_dir


def get_required_input(prompt: str) -> str:
    while True:
        questions = [
            inquirer.Text(
                "response", message=prompt, validate=lambda _, x: x.strip() != ""
            )
        ]
        answers = inquirer.prompt(questions)
        if answers and answers["response"]:
            return answers["response"].strip()
        feedback_message("Required. Please enter a valid location.", "warning")


def validate_directory(path: str) -> str:
    dir_path = Path(path).expanduser().resolve()
    if not dir_path.exists():
        try:
            dir_path.mkdir(parents=True)
            feedback_message(f"Created directory: {dir_path}", "info")
        except Exception as e:
            feedback_message(f"Error creating directory: {e}", "error")
            return validate_directory(
                get_required_input("Please enter a valid directory path: ")
            )
    elif not dir_path.is_dir():
        feedback_message(f"{dir_path} is not a directory.", "error")
        return validate_directory(
            get_required_input("Please enter a valid directory path: ")
        )
    return str(dir_path)


def create_env_file(env_path: Path) -> None:
    feedback_message(f"Creating new .env file at {env_path}", "info")

    invokeai_dir = validate_directory(
        get_required_input("The path to your Invoke AI install directory: ")
    )
    set_key(env_path, "INVOKE_AI_DIR", invokeai_dir)

    models_dir = validate_directory(
        get_required_input("The path to your models directory ")
    )
    set_key(env_path, "MODELS_DIR", models_dir)

    if models_dir:
        set_key(env_path, "MODELS_DIR", models_dir)

    snapshots_dir = validate_directory(
        get_required_input(
            "The path to your snapshots directory (or press Enter to skip): "
        )
    )
    if snapshots_dir:
        set_key(env_path, "SNAPSHOTS", snapshots_dir)

    feedback_message(f".env file created successfully at {env_path}", "info")


def get_default_env_locations():
    system = platform.system()
    if system == "Windows":
        return [
            os.path.expandvars("%APPDATA%\\invokeai-models-itsjustregi\\.env"),
            os.path.expandvars("%USERPROFILE%\\.invokeai-models-itsjustregi\\.env"),
            os.path.expandvars("%USERPROFILE%\\.env"),
            os.path.abspath(".env"),
        ]
    else:  # Unix-like systems (Linux, macOS)
        return [
            "~/.config/invokeai-models-itsjustregi/.env",
            "~/.invokeai-models-itsjustregi/.env",
            "~/.env",
            "./.env",
        ]


def load_environment_variables() -> None:
    env_locations = get_default_env_locations()

    env_path = None
    env_file_found = False

    for path in env_locations:
        env_path = Path(path).expanduser().resolve()
        if env_path.is_file():
            load_dotenv(env_path)
            env_file_found = True
            # feedback_message(f"Loaded .env file from: {env_path}", "info")
            break

    if not env_file_found:
        feedback_message(
            ".env file not found in any of the following locations:", "warning"
        )
        for path in env_locations:
            print(f"  - {Path(path).expanduser()}")

        create_new = inquirer.confirm(
            "Would you like to create a new .env file?", default=True
        )
        if create_new:
            default_path = Path(env_locations[0]).expanduser()
            questions = [
                inquirer.Path(
                    "env_path",
                    message="Enter path for new .env file",
                    default=str(default_path),
                    exists=False,
                    path_type=inquirer.Path.FILE,
                )
            ]
            answers = inquirer.prompt(questions)
            env_path = (
                Path(answers["env_path"]).expanduser() if answers else default_path
            )
            env_path.parent.mkdir(parents=True, exist_ok=True)
            create_env_file(env_path)
            load_dotenv(env_path)
        else:
            feedback_message(
                "No .env file found and user chose not to create one. Exiting.",
                "error",
            )
            exit()

    # Set environment variables
    os.environ["INVOKE_AI_DIR"] = os.getenv("INVOKE_AI_DIR", "")
    os.environ["MODELS_DIR"] = os.getenv("MODELS_DIR", "")
    os.environ["SNAPSHOTS"] = os.getenv("SNAPSHOTS", "")

    # Verify that required variables are set
    if not os.environ["INVOKE_AI_DIR"]:
        feedback_message(
            "INVOKE_AI_DIR is not set in the .env file. Please set it manually.",
            "error",
        )
        exit()

    if not os.environ["MODELS_DIR"]:
        feedback_message(
            "MODELS_DIR is not set in the .env file. Please set it manually.",
            "error",
        )
        exit()


# Load environment variables
load_environment_variables()

# Define constants
INVOKE_AI_DIR: Final = os.environ["INVOKE_AI_DIR"]
MODELS_DIR: Final = os.environ["MODELS_DIR"]
SNAPSHOTS: Final = os.environ["SNAPSHOTS"]

SNAPSHOTS_DIR = Path(importlib.resources.files("invokeai_models_cli")) / "snapshots"
ensure_snapshots_dir(SNAPSHOTS_DIR)
