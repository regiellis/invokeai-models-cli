import os
import re
import io
import pytest
import json
import sqlite3
from typer.testing import CliRunner
from invokeai_models_cli.cli import invoke_models_cli
from unittest.mock import patch, MagicMock
from invokeai_models_cli import MODELS_DIR, SNAPSHOTS
#TODO: Fix the tests

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def mock_db(tmp_path):
    db_path = tmp_path / "test_models.db"
    os.environ["INVOKEAI_MODELS_DB"] = str(db_path)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
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
    """)
    conn.commit()
    conn.close()
    yield db_path
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

def test_compare_models(runner, mock_db, mock_models_dir, mock_snapshots_dir, capsys):
    conn = sqlite3.connect(str(mock_db))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO models (key, hash, name, type, path, format, source_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("model1_key", "hash1", "model1", "checkpoint", "/path/to/model1", "safetensors", "path")
    )
    conn.commit()
    conn.close()

    with patch("invokeai_models_cli.MODELS_DIR", str(mock_models_dir)), \
         patch("invokeai_models_cli.SNAPSHOTS", str(mock_snapshots_dir)):
        result = runner.invoke(invoke_models_cli, ["compare"])
        captured = capsys.readouterr()
        print(f"Stdout: {captured.out}")
        print(f"Stderr: {captured.err}")
        simplified_output = simplify_rich_output(captured.out)
        assert result.exit_code == 2
        assert "Models in Database but Not on Disk" in simplified_output
        assert "model1" in simplified_output

def test_sync_models(runner, mock_db, mock_models_dir, mock_snapshots_dir, capsys):
    conn = sqlite3.connect(str(mock_db))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO models (key, hash, name, type, path, format, source_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("model1_key", "hash1", "model1", "checkpoint", "/path/to/model1", "safetensors", "path")
    )
    conn.commit()
    conn.close()

    with patch("invokeai_models_cli.MODELS_DIR", str(mock_models_dir)), \
         patch("invokeai_models_cli.SNAPSHOTS", str(mock_snapshots_dir)), \
         patch("builtins.input", return_value="y"):
        result = runner.invoke(invoke_models_cli, ["sync"])
        captured = capsys.readouterr()
        print(f"Stdout: {captured.out}")
        print(f"Stderr: {captured.err}")
        simplified_output = simplify_rich_output(captured.out)
        assert result.exit_code == 2
        assert "Sync operation completed successfully" in simplified_output or "All database models are in sync" in simplified_output

        conn = sqlite3.connect(str(mock_db))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM models WHERE key = ?", ("model1_key",))
        assert cursor.fetchone() is None  # Assuming the sync operation should remove this model
        conn.close()

@pytest.mark.parametrize("cache_type", ["local_models", "database_models"])
def test_cache_creation(runner, mock_db, mock_models_dir, mock_snapshots_dir, cache_type, capsys):
    cache_file = mock_snapshots_dir / f"{cache_type}_cache.json"
    with patch("invokeai_models_cli.MODELS_DIR", str(mock_models_dir)), \
         patch("invokeai_models_cli.SNAPSHOTS", str(mock_snapshots_dir)):
        result = runner.invoke(invoke_models_cli, ["compare"])
        captured = capsys.readouterr()
        print(f"Stdout: {captured.out}")
        print(f"Stderr: {captured.err}")
        assert result.exit_code == 0
        assert cache_file.exists(), f"Cache file {cache_file} was not created"

def test_cache_usage(runner, mock_db, mock_models_dir, mock_snapshots_dir, capsys):
    cache_file = mock_snapshots_dir / "local_models_cache.json"
    mock_data = {
        "last_updated": "2023-01-01T00:00:00",
        "data": [{"name": "test_model", "type": "checkpoint"}],
    }
    cache_file.write_text(json.dumps(mock_data))

    with patch("invokeai_models_cli.MODELS_DIR", str(mock_models_dir)), \
         patch("invokeai_models_cli.SNAPSHOTS", str(mock_snapshots_dir)):
        result = runner.invoke(invoke_models_cli, ["compare"])
        captured = capsys.readouterr()
        print(f"Stdout: {captured.out}")
        print(f"Stderr: {captured.err}")
        simplified_output = simplify_rich_output(captured.out)
        assert result.exit_code == 0
        assert "test_model" in simplified_output

def test_cache_update(runner, mock_db, mock_models_dir, mock_snapshots_dir, capsys):
    cache_file = mock_snapshots_dir / "local_models_cache.json"
    old_data = {
        "last_updated": "2000-01-01T00:00:00",
        "data": [{"name": "old_model", "type": "checkpoint"}],
    }
    cache_file.write_text(json.dumps(old_data))

    with patch("invokeai_models_cli.MODELS_DIR", str(mock_models_dir)), \
         patch("invokeai_models_cli.SNAPSHOTS", str(mock_snapshots_dir)):
        result = runner.invoke(invoke_models_cli, ["compare"])
        captured = capsys.readouterr()
        print(f"Stdout: {captured.out}")
        print(f"Stderr: {captured.err}")
        assert result.exit_code == 0

    updated_cache = json.loads(cache_file.read_text())
    assert updated_cache["last_updated"] > old_data["last_updated"]
    assert "old_model" not in [model["name"] for model in updated_cache["data"]]

def test_nonexistent_command(runner, capsys):
    result = runner.invoke(invoke_models_cli, ["nonexistent"])
    captured = capsys.readouterr()
    print(f"Stdout: {captured.out}")
    print(f"Stderr: {captured.err}")
    simplified_output = simplify_rich_output(captured.out)
    assert result.exit_code != 0
    assert "No such command" in simplified_output

def test_invalid_option(runner, capsys):
    result = runner.invoke(invoke_models_cli, ["compare", "--invalid-option"])
    captured = capsys.readouterr()
    print(f"Stdout: {captured.out}")
    print(f"Stderr: {captured.err}")
    simplified_output = simplify_rich_output(captured.out)
    assert result.exit_code != 0
    assert "Got unexpected extra argument" in simplified_output