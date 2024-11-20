# InvokeAI Models CLI

[![PyPI](https://img.shields.io/pypi/v/invokeai-models-cli)](https://pypi.org/project/invokeai-models-cli/)
[![Python Versions](https://img.shields.io/pypi/pyversions/invokeai-models-cli)](https://pypi.org/project/invokeai-models-cli/)

> [!NOTE]
> This project feature set were driven by personal needs and not a sense to create a general-purpose tool. As such, the tool may not be suitable for all use cases. Please use it with caution and always back up your data before making any changes. It is not intended to replace the official Invoke AI web UI but provides additional functionality for managing orphaned models.

**InvokeAI Models CLI** is a simplified command-line tool for managing orphaned Invoke AI models left in the database after their external sources have been deleted. This tool allows you to list, compare, and delete models automatically or via an interactive selection menu.

![screenshot](https://raw.githubusercontent.com/regiellis/invokeai-models-cli/main/screen.png)



## Installation

Choose one of the following methods to install/run the tool:

### Using `pipx` (Recommended)

```bash
pipx install invokeai-models-cli
```

### Using `pip`

```bash
pip install .
```

Or, if you prefer a local installation with the ability to explore and modify the code:

```bash
pip install -e .
```

Make sure to create and activate a virtual environment before installing locally.

## Usage

After installation, use the following commands:

```bash
invokeai-models [OPTIONS] COMMAND [ARGS]
```

**Available Commands:**

- **database**
  - `create-snapshot`: Create a snapshot of the current database state.
  - `list-snapshots`: List available snapshots.
  - `delete-snapshot`: Delete a snapshot by ID.
  - `restore-snapshot`: Restore a snapshot by ID.

- **local-models**: Display local models information.

- **compare-models**: Compare models based on specific criteria (e.g., model name, hash).

- **sync-models**: Sync orphaned models with the current external sources or delete them if they no longer exist.

- **database-models**: List and manage models in the Invoke AI database, including orphaned ones.

## Examples

- Create a snapshot: `invokeai-models database create-snapshot`
- List snapshots: `invokeai-models database list-snapshots`
- Delete a snapshot: `invokeai-models database delete-snapshot`
- Restore a snapshot: `invokeai-models database restore-snapshot`
- Compare models: `invokeai-models compare-models`
