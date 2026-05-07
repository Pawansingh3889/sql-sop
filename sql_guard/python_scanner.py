"""libCST-based scanner that extracts SQL strings from Python source.

Lets the core sql-sop rules run on SQL that lives inside ``cursor.execute(...)``
and friends, while a handful of Python-only rules (P001-P004) catch hazards
that only make sense at the Python level such as f-string interpolation or
string concatenation passed straight to ``.execute()``.

libCST is an optional dependency. When it is not installed the helpers in
this module are no-ops, so the package still installs cleanly on minimal
environments and the ``.sql`` linting continues to work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:  # libCST is an optional extra — see pyproject.toml [python] extra
    import libcst as cst

    _LIBCST_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via fallback path
    cst = None  # type: ignore[assignment]
    _LIBCST_AVAILABLE = False


# Attribute names that conventionally take SQL as their first string argument.
EXECUTE_METHODS: frozenset[str] = frozenset(
    {"execute", "executemany", "executescript", "read_sql", "read_sql_query", "text"}
)

# Variable assignment targets that commonly hold raw SQL strings.
SQL_VARIABLE_NAMES: frozenset[str] = frozenset({"sql", "query", "stmt", "statement", "raw_sql"})


@dataclass
class ExtractedSql:
    """A SQL string found in Python source.

    ``kind`` tracks what shape the argument had so Python-level rules can
    distinguish a concrete string literal (safe to re-scan) from an f-string
    or a concatenation (which is already a finding on its own).
    """

    sql: str
    line: int
    kind: str  # "literal" | "fstring" | "concat" | "format" | "percent" | "name"
    call_name: str  # e.g. "execute", "read_sql", or "" for bare assignments


def libcst_available() -> bool:
    """Return True when libCST is importable."""
    return _LIBCST_AVAILABLE


def _call_attr_name(call: "cst.Call") -> str | None:
    """Return the attribute name for ``something.method(...)`` calls."""
    func = call.func
    if isinstance(func, cst.Attribute):
        return func.attr.value
    if isinstance(func, cst.Name):
        return func.value
    return None


def _is_fstring(node: "cst.BaseExpression") -> bool:
    return isinstance(node, cst.FormattedString)


def _is_string_concat(node: "cst.BaseExpression") -> bool:
    if not isinstance(node, cst.BinaryOperation):
        return False
    if not isinstance(node.operator, cst.Add):
        return False
    return _contains_string(node.left) or _contains_string(node.right)


def _is_percent_format(node: "cst.BaseExpression") -> bool:
    if not isinstance(node, cst.BinaryOperation):
        return False
    if not isinstance(node.operator, cst.Modulo):
        return False
    return isinstance(node.left, cst.SimpleString)


def _is_dot_format(node: "cst.BaseExpression") -> bool:
    if not isinstance(node, cst.Call):
        return False
    func = node.func
    if not isinstance(func, cst.Attribute):
        return False
    if func.attr.value != "format":
        return False
    return isinstance(func.value, (cst.SimpleString, cst.ConcatenatedString))


def _contains_string(node: "cst.BaseExpression") -> bool:
    if isinstance(node, (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString)):
        return True
    if isinstance(node, cst.BinaryOperation):
        return _contains_string(node.left) or _contains_string(node.right)
    return False


def _literal_string_value(node: "cst.BaseExpression") -> str | None:
    """Return the literal value of a string node if it is safely constant."""
    if isinstance(node, cst.SimpleString):
        return node.evaluated_value
    if isinstance(node, cst.ConcatenatedString):
        try:
            return node.evaluated_value
        except AttributeError:  # older libcst versions
            return None
    return None


def _first_positional(call: "cst.Call") -> "cst.BaseExpression | None":
    for arg in call.args:
        if arg.keyword is None:
            return arg.value
    return None


def _classify(expr: "cst.BaseExpression") -> str:
    if _is_fstring(expr):
        return "fstring"
    if _is_string_concat(expr):
        return "concat"
    if _is_dot_format(expr):
        return "format"
    if _is_percent_format(expr):
        return "percent"
    if isinstance(expr, cst.Name):
        return "name"
    return "literal"


class _SqlCollector(cst.CSTVisitor if _LIBCST_AVAILABLE else object):
    """libCST visitor that harvests SQL-looking expressions."""

    METADATA_DEPENDENCIES = ()  # populated in __init__ to keep import-time cheap

    def __init__(self, wrapper: "cst.MetadataWrapper") -> None:
        super().__init__()
        self._wrapper = wrapper
        self._positions = wrapper.resolve(cst.metadata.PositionProvider)
        self.sql_hits: list[ExtractedSql] = []

    # ---- helpers ---------------------------------------------------------
    def _line_of(self, node: "cst.CSTNode") -> int:
        try:
            return self._positions[node].start.line
        except KeyError:
            return 0

    def _record(self, node: "cst.BaseExpression", call_name: str) -> None:
        kind = _classify(node)
        literal = _literal_string_value(node) or ""
        self.sql_hits.append(
            ExtractedSql(
                sql=literal,
                line=self._line_of(node),
                kind=kind,
                call_name=call_name,
            )
        )

    # ---- visitors --------------------------------------------------------
    def visit_Call(self, node: "cst.Call") -> None:  # noqa: N802 - libcst API
        name = _call_attr_name(node)
        if name not in EXECUTE_METHODS:
            return
        target = _first_positional(node)
        if target is None:
            return
        if not (
            isinstance(
                target, (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString, cst.Name)
            )
            or isinstance(target, cst.BinaryOperation)
            or _is_dot_format(target)
        ):
            return
        self._record(target, name)

    def visit_Assign(self, node: "cst.Assign") -> None:  # noqa: N802 - libcst API
        # sql = "..." style assignments so the rules still see the SQL even
        # when it is passed through a variable.
        if len(node.targets) != 1:
            return
        target_node = node.targets[0].target
        if not isinstance(target_node, cst.Name):
            return
        if target_node.value.lower() not in SQL_VARIABLE_NAMES:
            return
        value = node.value
        if not isinstance(
            value,
            (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString, cst.BinaryOperation),
        ) and not _is_dot_format(value):
            return
        self._record(value, "")


def extract(source: str) -> list[ExtractedSql]:
    """Parse ``source`` and return all SQL strings worth linting."""
    if not _LIBCST_AVAILABLE:
        return []
    try:
        module = cst.parse_module(source)
    except cst.ParserSyntaxError:
        return []
    wrapper = cst.metadata.MetadataWrapper(module)
    collector = _SqlCollector(wrapper)
    collector.METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)
    wrapper.visit(collector)
    return collector.sql_hits


def extract_from_file(path: Path) -> list[ExtractedSql]:
    """Read ``path`` and return the SQL strings found inside."""
    if not _LIBCST_AVAILABLE:
        return []
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            source = path.read_text(encoding="latin-1")
        except OSError:
            return []
    except OSError:
        return []
    return extract(source)


def iter_literal_sql(hits: Iterable[ExtractedSql]) -> Iterable[ExtractedSql]:
    """Yield only those hits whose SQL is a concrete literal — safe to re-lint."""
    for hit in hits:
        if hit.kind == "literal" and hit.sql:
            yield hit
