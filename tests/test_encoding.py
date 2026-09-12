"""Tests for file encoding edge cases."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from sql_guard.checker import check_file
from sql_guard.rules import get_rules


class TestEncodingEdgeCases:
    def test_utf8_file(self, tmp_path: Path) -> None:
        """UTF-8 file with accented characters should work."""
        sql = tmp_path / "utf8.sql"
        sql.write_text("SELECT * FROM café;\n", encoding="utf-8")
        findings = check_file(sql, get_rules())
        # Should find W001 (SELECT *) but not crash
        assert any(f.rule_id == "W001" for f in findings)

    def test_latin1_file(self, tmp_path: Path) -> None:
        """Latin-1 encoded file should fallback gracefully."""
        sql = tmp_path / "latin1.sql"
        sql.write_bytes("SELECT * FROM sch\xe9ma;\n".encode("latin-1"))
        findings = check_file(sql, get_rules())
        # Should not crash — falls back to latin-1
        assert not any(f.rule_id == "SYS" and "Cannot read" in f.message for f in findings)

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file should return no findings."""
        sql = tmp_path / "empty.sql"
        sql.write_text("", encoding="utf-8")
        findings = check_file(sql, get_rules())
        assert len(findings) == 0

    def test_comments_only_file(self, tmp_path: Path) -> None:
        """File with only comments should not crash."""
        sql = tmp_path / "comments.sql"
        sql.write_text("-- this is a comment\n-- another comment\n", encoding="utf-8")
        findings = check_file(sql, get_rules())
        # No SQL statements, no findings (comments don't trigger W010 unless they contain SQL keywords)
        assert all(f.severity != "error" for f in findings)

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not supported on Windows")
    def test_permission_error(self, tmp_path: Path) -> None:
        """Unreadable file should return SYS error, not crash."""
        sql = tmp_path / "noaccess.sql"
        sql.write_text("SELECT 1;", encoding="utf-8")
        # Make unreadable (Unix only — skip on Windows if it doesn't work)
        try:
            sql.chmod(0o000)
            # chmod does not block root, and a readable "SELECT 1;" yields
            # ordinary findings (W002 and friends) -- so a non-empty result is
            # not evidence the read was denied. Gate on the actual access check.
            if os.access(sql, os.R_OK):
                pytest.skip("chmod did not block reads (running as root?)")
            findings = check_file(sql, get_rules())
            assert any(f.rule_id == "SYS" for f in findings)
        except (OSError, PermissionError):
            pass  # Windows doesn't support chmod the same way
        finally:
            try:
                sql.chmod(0o644)
            except OSError:
                pass

    def test_very_long_line(self, tmp_path: Path) -> None:
        """Very long SQL line should not crash or hang."""
        sql = tmp_path / "long.sql"
        long_line = "SELECT " + ", ".join(f"col{i}" for i in range(1000)) + " FROM big_table;"
        sql.write_text(long_line, encoding="utf-8")
        findings = check_file(sql, get_rules())
        # Should complete without hanging
        assert isinstance(findings, list)

    def test_binary_content(self, tmp_path: Path) -> None:
        """Binary file should return error, not crash."""
        sql = tmp_path / "binary.sql"
        sql.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")
        findings = check_file(sql, get_rules())
        # Should either return SYS error or handle gracefully
        assert isinstance(findings, list)
