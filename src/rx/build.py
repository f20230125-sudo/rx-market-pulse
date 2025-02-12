"""Build the DuckDB warehouse from data/raw.

    python -m rx.build              # stage -> model -> marts
    python -m rx.build stage        # only the staging layer
    python -m rx.build model marts  # re-run later layers on an existing staging layer

Layers (each is a numbered SQL file in sql/, run in order):
    01-02  staging: sources as published, typed, nothing removed
    03     quarantine: rows that fail a rule go to a table of their own, with the reason
    04     dimensions: one clean row per product (NDC), manufacturer, state
    05     facts: utilisation with only trustworthy rows
    06+    marts: small tables the dashboard, workbook and report read
"""

from __future__ import annotations

import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

import duckdb

from .areas import area_for_class, area_for_name, load_name_rules, load_rules
from .ingredients import first_name, ingredient_key
from .labelers import normalise_labeler, parent_company
from .ndc import to_ndc11
from .sources import MARTS, RAW, REF, ROOT, WAREHOUSE

SQL_DIR = ROOT / "sql"


def connect(path: Path = WAREHOUSE) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    # The same tested Python functions the unit tests cover are the ones the SQL calls.
    for name, fn in (
        ("to_ndc11", to_ndc11),
        ("ingredient_key", ingredient_key),
        ("first_name", first_name),
        ("parent_company", parent_company),
        ("normalise_labeler", normalise_labeler),
    ):
        con.create_function(name, fn, [str], str, null_handling="special")
    con.execute((SQL_DIR / "00_macros.sql").read_text(encoding="utf-8"))
    return con


def _run_sql(con: duckdb.DuckDBPyConnection, name: str, **params: str) -> None:
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    for key, value in params.items():
        sql = sql.replace("{" + key + "}", value)
    started = time.time()
    con.execute(sql)
    print(f"  {name:<28} {time.time() - started:5.1f}s")


def _unzip(zip_path: Path, member: str, dest: Path) -> Path:
    if not dest.exists() or dest.stat().st_mtime < zip_path.stat().st_mtime:
        with zipfile.ZipFile(zip_path) as z:
            data = z.read(member)
        dest.write_bytes(data)
    return dest


def stage(con: duckdb.DuckDBPyConnection) -> None:
    print("stage")
    sdud_files = sorted(RAW.glob("sdud_*.csv"))
    if not sdud_files:
        raise SystemExit("no sdud_*.csv in data/raw: run python -m rx.fetch first")
    files = "[" + ", ".join("'" + p.as_posix() + "'" for p in sdud_files) + "]"
    _run_sql(con, "01_stage_sdud.sql", files=files)

    ob = RAW / "orange_book"
    ob.mkdir(exist_ok=True)
    for member in ("products.txt", "patent.txt", "exclusivity.txt"):
        _unzip(RAW / "orange_book.zip", member, ob / member)
    _run_sql(
        con,
        "02_stage_reference.sql",
        mdrp=(RAW / "mdrp_products.csv").as_posix(),
        enrollment=(RAW / "enrollment.csv").as_posix(),
        ob_products=(ob / "products.txt").as_posix(),
        ob_patents=(ob / "patent.txt").as_posix(),
        ob_exclusivity=(ob / "exclusivity.txt").as_posix(),
    )

    fda_json = _unzip(RAW / "openfda_ndc.json.zip", "drug-ndc-0001-of-0001.json", RAW / "openfda_ndc.json")
    _run_sql(con, "02b_stage_openfda.sql", fda_json=fda_json.as_posix())


def build_class_map(con: duckdb.DuckDBPyConnection) -> None:
    """class string -> therapeutic area. Done in Python so each rule's regex is compiled once."""
    started = time.time()
    rules = load_rules(REF / "therapeutic_area_rules.csv")
    classes = [r[0] for r in con.execute(
        "select distinct unnest(pharm_class) from stg_fda_product where pharm_class is not null").fetchall()]
    rows = []
    for c in classes:
        hit = area_for_class(c, rules)
        if hit:
            rows.append((c, hit[0], hit[1]))
    con.execute("create or replace table map_pharm_class (pharm_class varchar, area varchar, priority integer)")
    con.executemany("insert into map_pharm_class values (?, ?, ?)", rows)
    print(f"  {'map_pharm_class (python)':<28} {time.time() - started:5.1f}s  {len(rows)} of {len(classes)} classes mapped")


def build_name_map(con: duckdb.DuckDBPyConnection) -> None:
    """ingredient / brand name -> therapeutic area, from the curated rules file."""
    started = time.time()
    rules = load_name_rules(REF / "name_area_rules.csv")
    names = [r[0] for r in con.execute(
        "select ingredient_key from product_base where ingredient_key is not null "
        "union select product_family from product_base where product_family is not null").fetchall()]
    rows = [(n, a) for n in names if (a := area_for_name(n, rules))]
    con.execute("create or replace table map_name_area (name varchar, area varchar)")
    con.executemany("insert into map_name_area values (?, ?)", rows)
    # Overrides win over every other step: a short, documented list of known misclassifications.
    overrides = load_name_rules(REF / "area_overrides.csv")
    over = [(n, a) for n in names if (a := area_for_name(n, overrides))]
    con.execute("create or replace table map_override_area (name varchar, area varchar)")
    con.executemany("insert into map_override_area values (?, ?)", over)
    print(f"  {'name maps (python)':<28} {time.time() - started:5.1f}s  "
          f"{len(rows)} name rules, {len(over)} overrides, of {len(names)} names")


# Steps that are not SQL run just before the SQL file named here.
_BEFORE = {"04b_product_base.sql": build_class_map, "04c_dim_product.sql": build_name_map}


def model(con: duckdb.DuckDBPyConnection) -> None:
    print("model")
    for name in sorted(p.name for p in SQL_DIR.glob("0[3-5]*.sql")):
        if name in _BEFORE:
            _BEFORE[name](con)
        _run_sql(con, name, ref_dir=REF.as_posix())


def marts(con: duckdb.DuckDBPyConnection) -> None:
    print("marts")
    MARTS.mkdir(parents=True, exist_ok=True)
    # The Orange Book is a monthly download; its file date is the "as of" date for protection status.
    as_of = datetime.fromtimestamp((RAW / "orange_book.zip").stat().st_mtime).date().isoformat()
    for name in sorted(p.name for p in SQL_DIR.glob("[0-9][0-9]*.sql") if int(p.name[:2]) >= 6):
        _run_sql(con, name, marts_dir=MARTS.as_posix(), ref_dir=REF.as_posix(), as_of=as_of)


LAYERS = {"stage": stage, "model": model, "marts": marts}


def main(argv: list[str] | None = None) -> int:
    wanted = (argv if argv is not None else sys.argv[1:]) or list(LAYERS)
    unknown = [w for w in wanted if w not in LAYERS]
    if unknown:
        print(f"unknown layer(s): {', '.join(unknown)}; choose from {', '.join(LAYERS)}", file=sys.stderr)
        return 2
    con = connect()
    for layer in wanted:
        LAYERS[layer](con)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
