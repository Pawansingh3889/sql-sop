"""Exercise snapshot flags and failure reporting through the real CLI."""

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from sql_guard import snapshot
from sql_guard.cli import app

runner = CliRunner()


def test_snapshot_flags_and_validate_roundtrip(snapshot_dsn: str, tmp_path: Path):
    output = tmp_path / "nested" / "snapshot.yml"
    result = runner.invoke(
        app,
        [
            "schema-snapshot",
            "--dsn",
            snapshot_dsn,
            "--output",
            str(output),
            "--schema",
            "main",
            "--include-table",
            "ORDERS",
            "--include-table",
            "customers",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "with 2 tables" in " ".join(result.output.split())
    data = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert set(data["tables"]) == {"orders", "customers"}
    assert data["tables"]["orders"]["columns"]["customer_id"]["foreign_key"] == "customers.id"
    validation = runner.invoke(app, ["validate-contract", "--contract", str(output)])
    assert validation.exit_code == 0, validation.output
    assert "2 tables, 6 columns, 2 primary keys, 1 foreign keys" in " ".join(
        validation.output.split()
    )


def test_snapshot_default_output(
    snapshot_dsn: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["schema-snapshot", "--dsn", snapshot_dsn])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load((tmp_path / "contract.yml").read_text(encoding="utf-8"))
    assert set(data["tables"]) == {"customers", "orders", "audit"}


def test_snapshot_invalid_schema_does_not_write(snapshot_dsn: str, tmp_path: Path):
    output = tmp_path / "failed.yml"
    result = runner.invoke(
        app,
        ["schema-snapshot", "--dsn", snapshot_dsn, "--schema", "nonexistent", "-o", str(output)],
    )
    assert result.exit_code == 2
    assert "Snapshot failed:" in result.output
    assert not output.exists()


def test_snapshot_dependency_error_preserves_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def unavailable():
        raise snapshot.SnapshotError("SQLAlchemy is unavailable")

    monkeypatch.setattr(snapshot, "_require_sqlalchemy", unavailable)
    output = tmp_path / "existing.yml"
    output.write_text("original", encoding="utf-8")
    result = runner.invoke(app, ["schema-snapshot", "--dsn", "sqlite://", "-o", str(output)])
    assert result.exit_code == 2
    assert "SQLAlchemy is unavailable" in result.output
    assert output.read_text(encoding="utf-8") == "original"
