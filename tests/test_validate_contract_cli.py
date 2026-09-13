"""User-visible validation outcomes without a database connection."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sql_guard.cli import app

runner = CliRunner()


def test_validate_sample_contract():
    sample = Path(__file__).parent / "fixtures" / "contract_sample.yml"
    result = runner.invoke(app, ["validate-contract", "--contract", str(sample)])
    assert result.exit_code == 0, result.output
    assert "2 tables, 8 columns, 2 primary keys, 1 foreign keys" in " ".join(result.output.split())


@pytest.mark.parametrize("contents", ["tables: [", "tables: [not-a-mapping]"])
def test_validate_invalid_contract(tmp_path: Path, contents: str):
    path = tmp_path / "invalid.yml"
    path.write_text(contents, encoding="utf-8")
    result = runner.invoke(app, ["validate-contract", "--contract", str(path)])
    assert result.exit_code == 2
    assert "Invalid contract:" in result.output
    assert "OK" not in result.output


def test_validate_missing_contract(tmp_path: Path):
    result = runner.invoke(app, ["validate-contract", "--contract", str(tmp_path / "missing.yml")])
    assert result.exit_code == 2
    assert "Contract file not found:" in result.output


def test_validate_empty_contract_warns(tmp_path: Path):
    path = tmp_path / "empty.yml"
    path.write_text("tables: {}", encoding="utf-8")
    result = runner.invoke(app, ["validate-contract", "--contract", str(path)])
    assert result.exit_code == 0
    assert "no tables were declared" in " ".join(result.output.split())
