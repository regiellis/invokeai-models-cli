import os
import re
import io
import pytest
import json
import sqlite3
from typer.testing import CliRunner
from invokeai_models_cli.cli import invoke_models_cli
from unittest.mock import patch, MagicMock


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_db(tmp_path):
    # Create a temporary database file
    db_path = tmp_path / "test_models.db"
    os.environ["INVOKEAI_MODELS_DB"] = str(db_path)

    # Create the database and set up the schema
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS models (
        key TEXT PRIMARY KEY,
        hash TEXT NOT NULL,
        name TEXT NOT NULL,
        base TEXT,
        type TEXT NOT NULL,
        path TEXT NOT NULL,
        description TEXT,
        format TEXT NOT NULL,
        source TEXT,
        source_type TEXT,
        source_api_response TEXT,
        cover_image TEXT,
        metadata_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    conn.commit()
    conn.close()

    yield db_path

    # Clean up
    if os.path.exists(db_path):
        os.unlink(db_path)
    else:
        print(f"Warning: Database file {db_path} not found during cleanup")


@pytest.fixture
def mock_models_dir(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "checkpoints").mkdir()
    (models_dir / "loras").mkdir()
    return models_dir


@pytest.fixture
def mock_snapshots_dir(tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    snapshots_dir.mkdir()
    return snapshots_dir


def strip_ansi(text):
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def simplify_rich_output(text):
    text = strip_ansi(text)
    text = re.sub(r"[│├─┤┌┐└┘┏┓┗┛]", "+", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def test_compare_models(runner, mock_db, mock_models_dir, mock_snapshots_dir):
    # Insert some sample data into the mock database
    conn = sqlite3.connect(str(mock_db))
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO models (key, hash, name, type, path, format, source_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "model1_key",
            "hash1",
            "model1",
            "checkpoint",
            "/path/to/model1",
            "safetensors",
            "path",
        ),
    )
    conn.commit()
    conn.close()

    with (
        patch("invokeai_models_cli.cli.MODELS_DIR", str(mock_models_dir)),
        patch("invokeai_models_cli.cli.SNAPSHOTS_DIR", str(mock_snapshots_dir)),
    ):
        result = runner.invoke(invoke_models_cli, ["compare"])
        simplified_output = simplify_rich_output(result.stdout)
        assert result.exit_code == 0
        assert "Models in Database but Not on Disk" in simplified_output


def test_sync_models(runner, mock_db, mock_models_dir, mock_snapshots_dir):
    # Insert some sample data into the mock database
    conn = sqlite3.connect(str(mock_db))
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO models (key, hash, name, type, path, format, source_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "model1_key",
            "hash1",
            "model1",
            "checkpoint",
            "/path/to/model1",
            "safetensors",
            "path",
        ),
    )
    conn.commit()
    conn.close()

    with (
        patch("invokeai_models_cli.cli.MODELS_DIR", str(mock_models_dir)),
        patch("invokeai_models_cli.cli.SNAPSHOTS_DIR", str(mock_snapshots_dir)),
        patch("builtins.input", return_value="y"),
    ):  # Simulate user confirming sync
        result = runner.invoke(invoke_models_cli, ["sync"])
        simplified_output = simplify_rich_output(result.stdout)
        assert result.exit_code == 0
        assert (
            "Sync operation completed successfully" in simplified_output
            or "All database models are in sync" in simplified_output
        )


@pytest.mark.parametrize("cache_type", ["local_models", "database_models"])
def test_cache_creation(
    runner, mock_db, mock_models_dir, mock_snapshots_dir, cache_type
):
    cache_file = mock_snapshots_dir / f"{cache_type}_cache.json"
    with (
        patch("invokeai_models_cli.cli.MODELS_DIR", str(mock_models_dir)),
        patch("invokeai_models_cli.cli.SNAPSHOTS_DIR", str(mock_snapshots_dir)),
    ):
        result = runner.invoke(invoke_models_cli, ["compare"])
        assert result.exit_code == 0
        assert cache_file.exists()


def test_cache_usage(runner, mock_db, mock_models_dir, mock_snapshots_dir):
    cache_file = mock_snapshots_dir / "local_models_cache.json"
    mock_data = {
        "last_updated": "2023-01-01T00:00:00",
        "data": [{"name": "test_model", "type": "checkpoint"}],
    }
    cache_file.write_text(json.dumps(mock_data))

    with (
        patch("invokeai_models_cli.cli.MODELS_DIR", str(mock_models_dir)),
        patch("invokeai_models_cli.cli.SNAPSHOTS_DIR", str(mock_snapshots_dir)),
    ):
        result = runner.invoke(invoke_models_cli, ["compare"])
        simplified_output = simplify_rich_output(result.stdout)
        assert result.exit_code == 0
        assert "test_model" in simplified_output


def test_cache_update(runner, mock_db, mock_models_dir, mock_snapshots_dir):
    cache_file = mock_snapshots_dir / "local_models_cache.json"
    old_data = {
        "last_updated": "2000-01-01T00:00:00",  # Very old date to force update
        "data": [{"name": "old_model", "type": "checkpoint"}],
    }
    cache_file.write_text(json.dumps(old_data))

    with (
        patch("invokeai_models_cli.cli.MODELS_DIR", str(mock_models_dir)),
        patch("invokeai_models_cli.cli.SNAPSHOTS_DIR", str(mock_snapshots_dir)),
    ):
        result = runner.invoke(invoke_models_cli, ["compare"])
        assert result.exit_code == 0

    # Check if the cache file has been updated
    updated_cache = json.loads(cache_file.read_text())
    assert updated_cache["last_updated"] > old_data["last_updated"]


def test_nonexistent_command(runner):
    result = runner.invoke(invoke_models_cli, ["nonexistent"])
    simplified_output = simplify_rich_output(result.stdout)
    assert result.exit_code != 0
    assert "No such command" in simplified_output


def test_invalid_option(runner):
    result = runner.invoke(invoke_models_cli, ["compare", "--invalid-option"])
    simplified_output = simplify_rich_output(result.stdout)
    assert result.exit_code != 0
    assert "Got unexpected extra argument" in simplified_output
