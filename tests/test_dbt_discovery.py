"""Tests for sql_guard.dbt project discovery and schema.yml parsing."""

from __future__ import annotations

from pathlib import Path

from sql_guard.dbt import find_dbt_project, load_dbt_project


FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "dbt_project"


# find_dbt_project ----------------------------------------------------------


def test_find_dbt_project_finds_yml_in_same_dir(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: x\n")
    assert find_dbt_project(tmp_path) == (tmp_path / "dbt_project.yml").resolve()


def test_find_dbt_project_walks_up_from_subdir(tmp_path):
    project_yml = tmp_path / "dbt_project.yml"
    project_yml.write_text("name: x\n")
    sub = tmp_path / "models" / "marts"
    sub.mkdir(parents=True)
    assert find_dbt_project(sub) == project_yml.resolve()


def test_find_dbt_project_accepts_file_input(tmp_path):
    project_yml = tmp_path / "dbt_project.yml"
    project_yml.write_text("name: x\n")
    sub = tmp_path / "models"
    sub.mkdir()
    sql_file = sub / "model.sql"
    sql_file.write_text("SELECT 1;\n")
    assert find_dbt_project(sql_file) == project_yml.resolve()


def test_find_dbt_project_returns_none_when_absent(tmp_path):
    # No dbt_project.yml in this tree. The function may still return a
    # path outside tmp_path if the real filesystem ancestors host one;
    # only assert that nothing inside tmp_path is reported.
    sub = tmp_path / "deep" / "nested" / "dir"
    sub.mkdir(parents=True)
    result = find_dbt_project(sub)
    if result is not None:
        assert not str(result.resolve()).startswith(str(tmp_path.resolve()))


# load_dbt_project ----------------------------------------------------------


def test_load_dbt_project_reads_model_paths_from_fixture():
    project = load_dbt_project(FIXTURE_PROJECT / "dbt_project.yml")
    assert (FIXTURE_PROJECT / "models").resolve() in project.model_paths


def test_load_dbt_project_finds_all_models_in_fixture():
    project = load_dbt_project(FIXTURE_PROJECT / "dbt_project.yml")
    names = {m.name for m in project.models}
    assert names == {"stg_orders", "fct_orders", "fct_customers"}


def test_load_dbt_project_recognises_tests_key():
    # dbt <= 1.4 spelling.
    project = load_dbt_project(FIXTURE_PROJECT / "dbt_project.yml")
    stg = next(m for m in project.models if m.name == "stg_orders")
    assert stg.has_tests is True


def test_load_dbt_project_recognises_data_tests_key():
    # dbt >= 1.5 spelling.
    project = load_dbt_project(FIXTURE_PROJECT / "dbt_project.yml")
    fct = next(m for m in project.models if m.name == "fct_orders")
    assert fct.has_tests is True


def test_load_dbt_project_model_without_tests():
    project = load_dbt_project(FIXTURE_PROJECT / "dbt_project.yml")
    fct = next(m for m in project.models if m.name == "fct_customers")
    assert fct.has_tests is False


def test_load_dbt_project_captures_description():
    project = load_dbt_project(FIXTURE_PROJECT / "dbt_project.yml")
    stg = next(m for m in project.models if m.name == "stg_orders")
    assert stg.description == "Raw orders from the source system."


def test_load_dbt_project_missing_description_is_none():
    project = load_dbt_project(FIXTURE_PROJECT / "dbt_project.yml")
    fct = next(m for m in project.models if m.name == "fct_customers")
    assert fct.description is None


def test_load_dbt_project_malformed_schema_yml_does_not_crash(tmp_path):
    project_yml = tmp_path / "dbt_project.yml"
    project_yml.write_text('name: x\nmodel-paths: ["models"]\n')
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "schema.yml").write_text("not: [valid yaml")
    project = load_dbt_project(project_yml)
    assert project.models == ()


def test_load_dbt_project_falls_back_to_default_model_paths(tmp_path):
    project_yml = tmp_path / "dbt_project.yml"
    project_yml.write_text("name: x\n")  # no model-paths key
    project = load_dbt_project(project_yml)
    paths = {p.name for p in project.model_paths}
    assert paths == {"models"}


def test_load_dbt_project_explicit_multiple_model_paths(tmp_path):
    project_yml = tmp_path / "dbt_project.yml"
    project_yml.write_text(
        'name: x\nmodel-paths: ["models", "transforms"]\n'
    )
    (tmp_path / "models").mkdir()
    (tmp_path / "transforms").mkdir()
    project = load_dbt_project(project_yml)
    paths = {p.name for p in project.model_paths}
    assert paths == {"models", "transforms"}
