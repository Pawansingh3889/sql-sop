"""Tests for the dbt-aware rule pack (DBT001-DBT00N)."""

from __future__ import annotations

from pathlib import Path

from sql_guard.checker import check_file
from sql_guard.dbt import load_dbt_project
from sql_guard.rules import build_dbt_rules, get_rules
from sql_guard.rules.dbt import (
    DirectTableRef,
    HookWithDdl,
    IncrementalWithoutUniqueKey,
    ModelWithoutTest,
    SelectStarInMart,
)

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


# DBT003 incremental-without-unique-key --------------------------------------


def _dbt003_project(tmp_path, model_sql: str):
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    marts = tmp_path / "models" / "marts"
    marts.mkdir(parents=True)
    model_path = marts / "fct_orders.sql"
    model_path.write_text(model_sql)
    project = load_dbt_project(tmp_path / "dbt_project.yml")
    return IncrementalWithoutUniqueKey(project), model_path


def test_dbt003_errors_for_merge_strategy_without_key(tmp_path):
    sql = (
        "{{ config(materialized='incremental', incremental_strategy='merge') }}\n"
        "SELECT * FROM {{ ref('stg_orders') }}\n"
    )
    rule, path = _dbt003_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].rule_id == "DBT003"
    assert findings[0].severity == "error"


def test_dbt003_errors_for_delete_plus_insert_strategy_without_key(tmp_path):
    sql = (
        "{{ config(materialized='incremental', "
        "incremental_strategy='delete+insert') }}\n"
        "SELECT * FROM {{ ref('stg_orders') }}\n"
    )
    rule, path = _dbt003_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_dbt003_warns_when_strategy_unset(tmp_path):
    sql = "{{ config(materialized='incremental') }}\nSELECT * FROM {{ ref('stg_orders') }}\n"
    rule, path = _dbt003_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].severity == "warning"


def test_dbt003_quiet_for_append_strategy(tmp_path):
    sql = (
        "{{ config(materialized='incremental', incremental_strategy='append') }}\n"
        "SELECT * FROM {{ ref('stg_orders') }}\n"
    )
    rule, path = _dbt003_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt003_quiet_for_insert_overwrite_strategy(tmp_path):
    sql = (
        "{{ config(materialized='incremental', "
        "incremental_strategy='insert_overwrite') }}\n"
        "SELECT * FROM {{ ref('stg_orders') }}\n"
    )
    rule, path = _dbt003_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt003_quiet_when_unique_key_present(tmp_path):
    sql = (
        "{{ config(materialized='incremental', incremental_strategy='merge', "
        "unique_key='order_id') }}\n"
        "SELECT * FROM {{ ref('stg_orders') }}\n"
    )
    rule, path = _dbt003_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt003_quiet_for_non_incremental_materialization(tmp_path):
    sql = "{{ config(materialized='table') }}\nSELECT * FROM {{ ref('stg_orders') }}\n"
    rule, path = _dbt003_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt003_quiet_without_config_call(tmp_path):
    rule, path = _dbt003_project(tmp_path, "SELECT * FROM {{ ref('stg_orders') }}\n")
    assert rule.check_file(str(path)) == []


def test_dbt003_reports_the_config_call_line(tmp_path):
    sql = "-- a leading comment\n{{ config(materialized='incremental') }}\nSELECT 1\n"
    rule, path = _dbt003_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert findings[0].line == 2


def test_dbt003_skips_file_outside_model_paths(tmp_path):
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    macros = tmp_path / "macros"
    macros.mkdir()
    macro = macros / "helper.sql"
    macro.write_text("{{ config(materialized='incremental') }}\nSELECT 1\n")

    project = load_dbt_project(tmp_path / "dbt_project.yml")
    rule = IncrementalWithoutUniqueKey(project)
    assert rule.check_file(str(macro)) == []


# DBT004 hook-with-ddl --------------------------------------------------------


def _dbt004_project(tmp_path, model_sql: str):
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    marts = tmp_path / "models" / "marts"
    marts.mkdir(parents=True)
    model_path = marts / "fct_orders.sql"
    model_path.write_text(model_sql)
    project = load_dbt_project(tmp_path / "dbt_project.yml")
    return HookWithDdl(project), model_path


def test_dbt004_errors_on_drop_in_pre_hook(tmp_path):
    sql = "{{ config(pre_hook=\"DROP TABLE staging_x\") }}\nSELECT 1\n"
    rule, path = _dbt004_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].rule_id == "DBT004"
    assert findings[0].severity == "error"
    assert "pre_hook" in findings[0].message


def test_dbt004_errors_on_truncate_in_post_hook(tmp_path):
    sql = "{{ config(post_hook=\"TRUNCATE TABLE staging_x\") }}\nSELECT 1\n"
    rule, path = _dbt004_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert "post_hook" in findings[0].message


def test_dbt004_errors_on_delete_in_hook(tmp_path):
    sql = "{{ config(post_hook=\"DELETE FROM staging_x WHERE 1=1\") }}\nSELECT 1\n"
    rule, path = _dbt004_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_dbt004_warns_on_alter_in_hook(tmp_path):
    sql = "{{ config(post_hook=\"ALTER TABLE {{ this }} CLUSTER BY (id)\") }}\nSELECT 1\n"
    rule, path = _dbt004_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].severity == "warning"


def test_dbt004_fires_once_per_hook_in_a_list(tmp_path):
    sql = (
        "{{ config(post_hook=["
        "\"GRANT SELECT ON {{ this }} TO reporting\", "
        "\"DROP TABLE staging_x\""
        "]) }}\nSELECT 1\n"
    )
    rule, path = _dbt004_project(tmp_path, sql)
    findings = rule.check_file(str(path))
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_dbt004_quiet_for_safe_hook(tmp_path):
    sql = "{{ config(post_hook=\"GRANT SELECT ON {{ this }} TO reporting\") }}\nSELECT 1\n"
    rule, path = _dbt004_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt004_quiet_without_hooks(tmp_path):
    sql = "{{ config(materialized='table') }}\nSELECT 1\n"
    rule, path = _dbt004_project(tmp_path, sql)
    assert rule.check_file(str(path)) == []


def test_dbt004_quiet_without_config_call(tmp_path):
    rule, path = _dbt004_project(tmp_path, "SELECT 1\n")
    assert rule.check_file(str(path)) == []


def test_dbt004_skips_file_outside_model_paths(tmp_path):
    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    macros = tmp_path / "macros"
    macros.mkdir()
    macro = macros / "helper.sql"
    macro.write_text("{{ config(pre_hook=\"DROP TABLE staging_x\") }}\nSELECT 1\n")

    project = load_dbt_project(tmp_path / "dbt_project.yml")
    rule = HookWithDdl(project)
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


def test_build_dbt_rules_returns_dbt_pack():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rules = build_dbt_rules(project)
    ids = {r.id for r in rules}
    assert {"DBT001", "DBT002", "DBT003", "DBT004", "DBT005"} <= ids


def test_get_rules_omits_dbt_pack_by_default():
    rules = get_rules()
    ids = {r.id for r in rules}
    assert not ids & {"DBT001", "DBT002", "DBT003", "DBT004", "DBT005"}


def test_get_rules_includes_dbt_pack_when_project_supplied():
    project = load_dbt_project(FIXTURE_PROJECT_YML)
    rules = get_rules(dbt_project=project)
    ids = {r.id for r in rules}
    assert {"DBT001", "DBT002", "DBT003", "DBT004", "DBT005"} <= ids


# CLI integration -----------------------------------------------------------


def test_dbt_check_result_exposes_active_rules(tmp_path):
    from sql_guard.checker import check

    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    (tmp_path / "models").mkdir()
    model = tmp_path / "models" / "orders.sql"
    model.write_text("select 1\n")
    result = check([str(model)], dbt_project=load_dbt_project(tmp_path / "dbt_project.yml"))
    assert "DBT001" in {rule.id for rule in result.active_rules}


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


def test_cli_dbt_flag_activates_dbt003(tmp_path):
    """End-to-end: --dbt flag discovers the project and fires DBT003."""
    from typer.testing import CliRunner

    from sql_guard.cli import app

    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    models = tmp_path / "models" / "marts"
    models.mkdir(parents=True)
    model = models / "fct_orders.sql"
    model.write_text(
        "{{ config(materialized='incremental', incremental_strategy='merge') }}\nSELECT 1\n"
    )

    runner = CliRunner()
    result = runner.invoke(app, ["check", "--dbt", str(model)])
    assert "DBT003" in result.stdout


def test_cli_dbt_flag_activates_dbt004(tmp_path):
    """End-to-end: --dbt flag discovers the project and fires DBT004."""
    from typer.testing import CliRunner

    from sql_guard.cli import app

    (tmp_path / "dbt_project.yml").write_text('name: x\nmodel-paths: ["models"]\n')
    models = tmp_path / "models" / "marts"
    models.mkdir(parents=True)
    model = models / "fct_orders.sql"
    model.write_text("{{ config(pre_hook=\"DROP TABLE staging_x\") }}\nSELECT 1\n")

    runner = CliRunner()
    result = runner.invoke(app, ["check", "--dbt", str(model)])
    assert "DBT004" in result.stdout


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
