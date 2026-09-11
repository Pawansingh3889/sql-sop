"""Tests for the dbt-aware rule pack (DBT001-DBT00N)."""

from __future__ import annotations

from pathlib import Path

from sql_guard.dbt import load_dbt_project
from sql_guard.rules import build_dbt_rules, get_rules
from sql_guard.rules.dbt import ModelWithoutTest, UnquotedVarInterpolation

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


# DBT007 unquoted-var-interpolation -------------------------------------------


def _dbt007_project(tmp_path, model_sql: str):
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    marts = tmp_path / "models" / "marts"
    marts.mkdir(parents=True)
    model_path = marts / "fct_orders.sql"
    model_path.write_text(model_sql)
    project = load_dbt_project(tmp_path / "dbt_project.yml")
    return UnquotedVarInterpolation(project), model_path


def test_dbt007_fires_on_unquoted_interpolation(tmp_path):
    sql = "SELECT * FROM t WHERE status = {{ var('status') }}\n"
    rule, path = _dbt007_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].rule_id == "DBT007"
    assert findings[0].severity == "warning"


def test_dbt007_quiet_when_quoted(tmp_path):
    sql = "SELECT * FROM t WHERE status = '{{ var('status') }}'\n"
    rule, path = _dbt007_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt007_quiet_when_only_one_side_quoted(tmp_path):
    # Malformed either way, but this rule only recognises the fully
    # quoted pair as "safe" -- a half-quote is its own (different) bug.
    sql = "SELECT * FROM t WHERE status = '{{ var('status') }}\n"
    rule, path = _dbt007_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1


def test_dbt007_fires_on_bare_numeric_looking_var(tmp_path):
    # No way to tell numeric intent from string intent statically --
    # v1 flags every unquoted case and lets the suggestion text say so.
    sql = "SELECT * FROM t WHERE qty > {{ var('min_qty') }}\n"
    rule, path = _dbt007_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1


def test_dbt007_quiet_for_nested_var_without_own_braces(tmp_path):
    sql = "{{ config(pre_hook=\"SET threshold = \" ~ var('threshold')) }}\nSELECT 1\n"
    rule, path = _dbt007_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt007_reports_the_source_line(tmp_path):
    sql = "SELECT *\nFROM t\nWHERE status = {{ var('status') }}\n"
    rule, path = _dbt007_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert findings[0].line == 3


def test_dbt007_skips_file_outside_model_paths(tmp_path):
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    macros = tmp_path / "macros"
    macros.mkdir()
    macro = macros / "helper.sql"
    macro.write_text("SELECT {{ var('x') }}\n")

    project = load_dbt_project(tmp_path / "dbt_project.yml")
    rule = UnquotedVarInterpolation(project)
    assert rule.check_file(str(macro)) == []


# Registry wiring -----------------------------------------------------------


def test_build_dbt_rules_returns_dbt001_and_dbt007():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rules = build_dbt_rules(project)
    ids = {r.id for r in rules}
    assert {"DBT001", "DBT007"} <= ids


def test_get_rules_omits_dbt_pack_by_default():
    rules = get_rules()
    ids = {r.id for r in rules}
    assert not ids & {"DBT001", "DBT007"}


def test_get_rules_includes_dbt_pack_when_project_supplied():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rules = get_rules(dbt_project=project)
    ids = {r.id for r in rules}
    assert {"DBT001", "DBT007"} <= ids


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


def test_cli_dbt_flag_activates_dbt007(tmp_path):
    """End-to-end: --dbt flag discovers the project and fires DBT007."""
    from typer.testing import CliRunner

    from sql_guard.cli import app

    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    models = tmp_path / "models" / "marts"
    models.mkdir(parents=True)
    model = models / "fct_orders.sql"
    model.write_text("SELECT * FROM t WHERE status = {{ var('status') }}\n")

    runner = CliRunner()
    result = runner.invoke(app, ["check", "--dbt", str(model)])
    assert "DBT007" in result.stdout
