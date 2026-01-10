"""The SQL macros and the Python reference must agree on every input, including the awkward ones."""

import random
from pathlib import Path

import duckdb
import pytest

from rx.ndc import product_ndc9, to_ndc11

MACROS = (Path(__file__).resolve().parents[1] / "sql" / "00_macros.sql").read_text(encoding="utf-8")

CASES = [
    "0002-1433-80", "50242-040-01", "12345-1234-1", "12345-1234-12", "00002143380", " 00002143380 ",
    "1234567890", "0002-1433", "12-34-56", "abcde-fghi-jk", "00002-1433-800", "", "12345-12345-1",
    "0000-0000-00", "99999-999-99", "99999-9999-9",
]


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    c.execute(MACROS)
    return c


def _random_ndcs(n: int = 300) -> list[str]:
    rng = random.Random(7)
    shapes = [(4, 4, 2), (5, 3, 2), (5, 4, 1), (5, 4, 2), (3, 4, 2), (5, 5, 2)]
    out = []
    for _ in range(n):
        a, b, c = rng.choice(shapes)
        out.append("-".join("".join(rng.choice("0123456789") for _ in range(k)) for k in (a, b, c)))
    return out


def test_ndc11_macro_matches_python(con):
    values = CASES + _random_ndcs()
    sql_out = [r[0] for r in con.execute("select ndc11_of(v) from (select unnest(?) v)", [values]).fetchall()]
    # unnest keeps order for a literal list
    for value, got in zip(values, sql_out):
        assert got == to_ndc11(value), value


def test_ndc9_macro_matches_python_reference(con):
    products = ["0002-1433", "50242-040", "12345-1234", "123-4567", "1234567", "abcd-efgh", ""]
    sql_out = [r[0] for r in con.execute("select ndc9_of_product(v) from (select unnest(?) v)", [products]).fetchall()]
    for value, got in zip(products, sql_out):
        py = product_ndc9(to_ndc11(value + "-00")) if value else None
        assert got == py, value
