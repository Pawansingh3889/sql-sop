"""Tests for the dbt-aware rule pack (DBT001-DBT00N)."""

from __future__ import annotations

from pathlib import Path

from sql_guard.dbt import load_dbt_project
from sql_guard.rules import build_dbt_rules, get_rules
from sql_guard.rules.dbt import DirectTableRef, ModelWithoutTest


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


# DBT002 direct-table-ref ----------------------------------------------------


def _dbt002_project(tmp_path, model_sql: str, model_name: str = "fct_orders"):
    """Build a tiny dbt project with one model under models/marts/."""
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    marts = tmp_path / "models" / "marts"
    marts.mkdir(parents=True)
    model_path = marts / f"{model_name}.sql"
    model_path.write_text(model_sql)
    project = load_dbt_project(tmp_path / "dbt_project.yml")
    return DirectTableRef(project), model_path


def test_dbt002_fires_on_raw_table_in_from(tmp_path):
    rule, path = _dbt002_project(tmp_path, "SELECT * FROM raw_orders\n")
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].rule_id == "DBT002"
    assert findings[0].severity == "warning"
    assert "raw_orders" in findings[0].message


def test_dbt002_fires_on_raw_table_in_join(tmp_path):
    sql = "SELECT * FROM {{ ref('stg_orders') }} o JOIN raw_customers c ON o.customer_id = c.id\n"
    rule, path = _dbt002_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert "raw_customers" in findings[0].message


def test_dbt002_fires_on_schema_qualified_raw_table(tmp_path):
    rule, path = _dbt002_project(tmp_path, "SELECT * FROM raw_db.orders\n")
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert "raw_db.orders" in findings[0].message


def test_dbt002_reports_the_source_line(tmp_path):
    sql = "SELECT *\nFROM raw_orders\n"
    rule, path = _dbt002_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert findings[0].line == 2


def test_dbt002_quiet_for_ref(tmp_path):
    rule, path = _dbt002_project(tmp_path, "SELECT * FROM {{ ref('stg_orders') }}\n")
    assert rule.check_file(str(path)) == []


def test_dbt002_quiet_for_source(tmp_path):
    sql = "SELECT * FROM {{ source('raw', 'orders') }}\n"
    rule, path = _dbt002_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt002_quiet_for_dbt_internal_var(tmp_path):
    # Any Jinja-templated target, not just ref()/source(), is out of scope.
    sql = "SELECT * FROM {{ this }}\n"
    rule, path = _dbt002_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt002_quiet_for_cte_reference(tmp_path):
    sql = "WITH clean_orders AS (SELECT * FROM {{ ref('stg_orders') }})\nSELECT * FROM clean_orders\n"
    rule, path = _dbt002_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt002_quiet_for_comma_cte_reference(tmp_path):
    sql = (
        "WITH a AS ({{ ref('stg_a') }}),\nb AS (SELECT * FROM a)\n"
        "SELECT * FROM b\n"
    )
    rule, path = _dbt002_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt002_quiet_for_subquery(tmp_path):
    sql = "SELECT * FROM (SELECT * FROM {{ ref('stg_orders') }}) x\n"
    rule, path = _dbt002_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt002_quiet_for_information_schema(tmp_path):
    sql = "SELECT * FROM information_schema.columns\n"
    rule, path = _dbt002_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt002_quiet_for_schema_qualified_information_schema(tmp_path):
    sql = "SELECT * FROM mydb.information_schema.tables\n"
    rule, path = _dbt002_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt002_skips_file_outside_model_paths(tmp_path):
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    macros = tmp_path / "macros"
    macros.mkdir()
    macro = macros / "helper.sql"
    macro.write_text("SELECT * FROM raw_orders\n")

    project = load_dbt_project(tmp_path / "dbt_project.yml")
    rule = DirectTableRef(project)
    assert rule.check_file(str(macro)) == []


def test_dbt002_skips_non_sql_file(tmp_path):
    rule, path = _dbt002_project(tmp_path, "SELECT * FROM raw_orders\n")
    py_path = path.with_suffix(".py")
    py_path.write_text("SELECT * FROM raw_orders\n")
    assert rule.check_file(str(py_path)) == []


# Registry wiring -----------------------------------------------------------


def test_build_dbt_rules_returns_dbt001_and_dbt002():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rules = build_dbt_rules(project)
    ids = {r.id for r in rules}
    assert {"DBT001", "DBT002"} <= ids


def test_get_rules_omits_dbt_pack_by_default():
    rules = get_rules()
    ids = {r.id for r in rules}
    assert not ids & {"DBT001", "DBT002"}


def test_get_rules_includes_dbt_pack_when_project_supplied():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rules = get_rules(dbt_project=project)
    ids = {r.id for r in rules}
    assert {"DBT001", "DBT002"} <= ids


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


def test_cli_dbt_flag_activates_dbt002(tmp_path):
    """End-to-end: --dbt flag discovers the project and fires DBT002."""
    from typer.testing import CliRunner

    from sql_guard.cli import app

    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    models = tmp_path / "models" / "marts"
    models.mkdir(parents=True)
    model = models / "fct_orders.sql"
    model.write_text("SELECT * FROM raw_orders\n")

    runner = CliRunner()
    result = runner.invoke(app, ["check", "--dbt", str(model)])
    assert "DBT002" in result.stdout
