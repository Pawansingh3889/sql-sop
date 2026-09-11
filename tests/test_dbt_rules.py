"""Tests for the dbt-aware rule pack (DBT001-DBT00N)."""

from __future__ import annotations

from pathlib import Path

from sql_guard.checker import check_file
from sql_guard.dbt import load_dbt_project
from sql_guard.rules import build_dbt_rules, get_rules
from sql_guard.rules.dbt import ModelWithoutTest, SelectStarInMart

FIXTURE_PROJECT_YML = Path(__file__).parent / "fixtures" / "dbt_project" / "dbt_project.yml"
FIXTURE_MODELS = FIXTURE_PROJECT_YML.parent / "models"


# DBT001 model-without-test -------------------------------------------------


def test_dbt001_quiet_for_model_with_tests_key():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rule = ModelWithoutTest(project)
    # stg_orders uses the dbt <=1.4 `tests:` spelling.
    path = FIXTURE_MODELS / "staging" / "stg_orders.sql"
    assert rule.check_file(str(path)) == []


def test_dbt001_quiet_for_model_with_data_tests_key():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rule = ModelWithoutTest(project)
    # fct_orders uses the dbt >=1.5 `data_tests:` spelling.
    path = FIXTURE_MODELS / "marts" / "fct_orders.sql"
    assert rule.check_file(str(path)) == []


def test_dbt001_fires_on_model_listed_but_untested():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rule = ModelWithoutTest(project)
    path = FIXTURE_MODELS / "marts" / "fct_customers.sql"
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].rule_id == "DBT001"
    assert findings[0].severity == "warning"


def test_dbt001_message_names_the_model():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rule = ModelWithoutTest(project)
    path = FIXTURE_MODELS / "marts" / "fct_customers.sql"
    findings = rule.check_file(str(path))
    assert "fct_customers" in findings[0].message


def test_dbt001_fires_on_unregistered_model(tmp_path):
    # A .sql model under model-paths with no schema.yml entry at all.
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    models = tmp_path / "models" / "marts"
    models.mkdir(parents=True)
    rogue = models / "fct_rogue.sql"
    rogue.write_text("SELECT 1;\n")

    project = load_dbt_project(tmp_path / "dbt_project.yml")
    rule = ModelWithoutTest(project)
    findings = rule.check_file(str(rogue))
    assert len(findings) == 1
    assert findings[0].rule_id == "DBT001"


def test_dbt001_skips_non_sql_file():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rule = ModelWithoutTest(project)
    # A .py file even under model-paths should not be inspected -- the
    # rule is about dbt SQL models.
    assert rule.check_file(str(FIXTURE_MODELS / "marts" / "helper.py")) == []


def test_dbt001_skips_file_outside_model_paths(tmp_path):
    # Tiny project where the .sql file lives in macros/, not models/.
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    macros = tmp_path / "macros"
    macros.mkdir()
    macro = macros / "helper.sql"
    macro.write_text("SELECT 1;\n")

    project = load_dbt_project(tmp_path / "dbt_project.yml")
    rule = ModelWithoutTest(project)
    assert rule.check_file(str(macro)) == []


# DBT005 select-star-in-mart --------------------------------------------------


def _dbt005_project(tmp_path, model_sql: str, subdir: str = "marts"):
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    model_dir = tmp_path / "models" / subdir
    model_dir.mkdir(parents=True)
    model_path = model_dir / "fct_orders.sql"
    model_path.write_text(model_sql)
    project = load_dbt_project(tmp_path / "dbt_project.yml")
    return SelectStarInMart(project), model_path


def test_dbt005_fires_on_select_star_in_marts_dir(tmp_path):
    rule, path = _dbt005_project(tmp_path, "SELECT * FROM {{ ref('stg_orders') }}\n")
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].rule_id == "DBT005"
    assert findings[0].severity == "warning"


def test_dbt005_quiet_outside_marts_dir(tmp_path):
    rule, path = _dbt005_project(tmp_path, "SELECT * FROM {{ ref('stg_orders') }}\n", subdir="staging")
    assert rule.check_file(str(path)) == []


def test_dbt005_fires_once_per_line(tmp_path):
    sql = "SELECT * FROM a\nSELECT col FROM b\nSELECT * FROM c\n"
    rule, path = _dbt005_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert [f.line for f in findings] == [1, 3]


def test_dbt005_matches_marts_case_insensitively(tmp_path):
    rule, path = _dbt005_project(tmp_path, "SELECT * FROM a\n", subdir="Marts")
    findings = rule.check_file(str(path))
    assert len(findings) == 1


def test_dbt005_skips_non_sql_file(tmp_path):
    rule, path = _dbt005_project(tmp_path, "SELECT * FROM a\n")
    py_path = path.with_suffix(".py")
    py_path.write_text("SELECT * FROM a\n")
    assert rule.check_file(str(py_path)) == []


def test_checker_suppresses_w001_when_dbt005_fires_same_line(tmp_path):
    """DBT005 is more specific than W001 for the same SELECT * -- only
    the dbt-aware finding should survive on that line."""
    from sql_guard.rules import get_rules

    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    marts = tmp_path / "models" / "marts"
    marts.mkdir(parents=True)
    model = marts / "fct_orders.sql"
    model.write_text("SELECT * FROM {{ ref('stg_orders') }}\n")

    project = load_dbt_project(tmp_path / "dbt_project.yml")
    rules = get_rules(dbt_project=project)
    findings = check_file(model, rules)

    ids_on_line_1 = {f.rule_id for f in findings if f.line == 1}
    assert "DBT005" in ids_on_line_1
    assert "W001" not in ids_on_line_1


def test_checker_keeps_w001_outside_marts(tmp_path):
    """Same SELECT *, but staging/ isn't a mart -- W001 fires normally."""
    from sql_guard.rules import get_rules

    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    staging = tmp_path / "models" / "staging"
    staging.mkdir(parents=True)
    model = staging / "stg_orders.sql"
    model.write_text("SELECT * FROM raw_orders\n")

    project = load_dbt_project(tmp_path / "dbt_project.yml")
    rules = get_rules(dbt_project=project)
    findings = check_file(model, rules)

    ids_on_line_1 = {f.rule_id for f in findings if f.line == 1}
    assert "W001" in ids_on_line_1
    assert "DBT005" not in ids_on_line_1


# Registry wiring -----------------------------------------------------------


def test_build_dbt_rules_returns_dbt001_and_dbt005():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rules = build_dbt_rules(project)
    ids = {r.id for r in rules}
    assert {"DBT001", "DBT005"} <= ids


def test_get_rules_omits_dbt_pack_by_default():
    rules = get_rules()
    ids = {r.id for r in rules}
    assert not ids & {"DBT001", "DBT005"}


def test_get_rules_includes_dbt_pack_when_project_supplied():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rules = get_rules(dbt_project=project)
    ids = {r.id for r in rules}
    assert {"DBT001", "DBT005"} <= ids


# CLI integration -----------------------------------------------------------


def test_cli_dbt_flag_activates_dbt001(tmp_path):
    """End-to-end: --dbt flag discovers the project and fires DBT001."""
    from typer.testing import CliRunner

    from sql_guard.cli import app

    # Tiny dbt project with one untested model.
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    models = tmp_path / "models" / "marts"
    models.mkdir(parents=True)
    untested = models / "fct_orders.sql"
    untested.write_text("SELECT 1 AS id;\n")

    runner = CliRunner()
    result = runner.invoke(app, ["check", "--dbt", str(untested)])
    assert "DBT001" in result.stdout


def test_cli_without_dbt_flag_does_not_fire_dbt001(tmp_path):
    """Same project, no --dbt: rule is silent."""
    from typer.testing import CliRunner

    from sql_guard.cli import app

    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    models = tmp_path / "models" / "marts"
    models.mkdir(parents=True)
    untested = models / "fct_orders.sql"
    untested.write_text("SELECT 1 AS id;\n")

    runner = CliRunner()
    result = runner.invoke(app, ["check", str(untested)])
    assert "DBT001" not in result.stdout


def test_cli_dbt_flag_activates_dbt005(tmp_path):
    """End-to-end: --dbt flag discovers the project and fires DBT005."""
    from typer.testing import CliRunner

    from sql_guard.cli import app

    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    marts = tmp_path / "models" / "marts"
    marts.mkdir(parents=True)
    model = marts / "fct_orders.sql"
    model.write_text("SELECT * FROM {{ ref('stg_orders') }}\n")

    runner = CliRunner()
    result = runner.invoke(app, ["check", "--dbt", str(model)])
    assert "DBT005" in result.stdout
    assert "W001" not in result.stdout
