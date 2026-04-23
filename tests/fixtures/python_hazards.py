"""Intentionally bad Python patterns used as sql-sop test fixtures.

This file is never imported or executed by the package; it is read as text
by the Python scanner. The SQL inside is synthetic and harmless.
"""
from __future__ import annotations


def unsafe_fstring(cursor, table: str) -> None:
    # P001 + E001 (DELETE without WHERE on the literal side)
    cursor.execute(f"DELETE FROM {table}")


def unsafe_concat(cursor, user_id: str) -> None:
    # P002
    cursor.execute("SELECT * FROM users WHERE id = " + user_id)


def unsafe_format(cursor, name: str) -> None:
    # P003 (format)
    cursor.execute("SELECT * FROM users WHERE name = '{}'".format(name))


def unsafe_percent(cursor, name: str) -> None:
    # P003 (percent)
    cursor.execute("SELECT * FROM users WHERE name = '%s'" % name)


def bare_variable(cursor, query: str) -> None:
    # P004
    cursor.execute(query)


def literal_with_sql_issues(cursor) -> None:
    # E001 via literal SQL in execute
    cursor.execute("DELETE FROM audit_log")
    # W001 via literal SQL
    cursor.execute("SELECT * FROM orders ORDER BY id")


def safe_parameterised(cursor, user_id: int) -> None:
    cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))


def safe_sqlalchemy(connection, user_id: int):
    from sqlalchemy import text

    return connection.execute(
        text("SELECT name FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )


def variable_assigned_raw():
    sql = "DELETE FROM staging"  # reachable via SQL_VARIABLE_NAMES
    return sql


def unsafe_sqlalchemy_text_fstring(connection, user_id):
    # P005 - f-string wrapped in sqlalchemy.text()
    from sqlalchemy import text

    return connection.execute(text(f"SELECT * FROM users WHERE id = {user_id}"))
