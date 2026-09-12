"""Shared temporary database for contract snapshot tests."""

from pathlib import Path

import pytest


@pytest.fixture
def snapshot_dsn(tmp_path: Path) -> str:
    sa = pytest.importorskip("sqlalchemy")
    dsn = f"sqlite:///{(tmp_path / 'source.db').as_posix()}"
    engine = sa.create_engine(dsn)
    metadata = sa.MetaData()
    sa.Table(
        "customers",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("email", sa.String(80)),
    )
    sa.Table(
        "orders",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
    )
    sa.Table("audit", metadata, sa.Column("message", sa.Text))
    try:
        metadata.create_all(engine)
    finally:
        engine.dispose()
    return dsn
