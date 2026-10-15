"""Write a Power BI project (PBIP) from the warehouse marts.

    python -m rx.powerbi            # writes powerbi/ (CSV data + semantic model + report)

The output is a Power BI Desktop *project*: plain text folders Desktop opens directly (File > Open > RxMarketPulse.pbip).
  powerbi/data/*.csv                      the tables, a star schema of the marts
  powerbi/RxMarketPulse.SemanticModel/    TMDL: tables, relationships, DAX measures
  powerbi/RxMarketPulse.Report/           PBIR: six pages of visuals and a theme
Generating it from code keeps the model, the measures and the report in step with the data, and in git.
"""

from __future__ import annotations

import csv
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .build import connect
from .sources import ROOT

PBI = ROOT / "powerbi"
DATA = PBI / "data"
MODEL = PBI / "RxMarketPulse.SemanticModel"
REPORT = PBI / "RxMarketPulse.Report"

TEAL, OCHRE, SLATE, RUST = "#008E7C", "#B5731A", "#5B6B73", "#A8472A"
INK, PAPER, RULE = "#15302C", "#FAF8F3", "#E1DCCD"


def _guid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rx-market-pulse/{name}"))


def _oid(name: str) -> str:
    return hashlib.sha1(name.encode()).hexdigest()[:20]


# ------------------------------------------------------------------------------------------------ data
@dataclass
class Table:
    name: str
    columns: list[tuple[str, str]]  # (name, dataType) dataType in string|int64|double|dateTime
    rows: list[tuple]
    measures: list[tuple[str, str, str]] = field(default_factory=list)  # (name, dax, formatString)
    hidden_cols: set[str] = field(default_factory=set)


def build_tables(con) -> list[Table]:
    years = list(range(2019, 2026))
    areas = [r[0] for r in con.execute("select area from mart_area_year where year = 2025 group by 1 order by sum(spend) desc").fetchall()]
    t: list[Table] = []

    t.append(Table("dim_year", [("year", "int64")], [(y,) for y in years]))
    t.append(Table("dim_area", [("area", "string"), ("sort", "int64")], [(a, i) for i, a in enumerate(areas)]))

    states = con.execute("select state, state_name, census_region, coalesce(cast(expanded_medicaid as varchar), 'unknown') from dim_state where is_state order by state_name").fetchall()
    t.append(Table("dim_state", [("state", "string"), ("state_name", "string"), ("region", "string"), ("expanded_medicaid", "string")], states))

    top_owners = [r[0] for r in con.execute("""select owner from sales_nat where year = 2025 and owner <> 'Unmatched'
                                              group by 1 order by sum(spend) desc limit 25""").fetchall()]
    if "Merck (MSD)" not in top_owners:
        top_owners.append("Merck (MSD)")
    owner_list = ",".join("'" + o.replace("'", "''") + "'" for o in top_owners)
    prod = con.execute(f"""
        with big as (
            select family, market_class from (select family, market_class, year, sum(spend) s from sales_nat group by all)
            group by 1, 2 having max(s) >= 2e6)
        select s.year,
               case when b.family is not null then s.family else 'All other products' end as family,
               s.market_class,
               case when s.owner in ({owner_list}) then s.owner else 'All other companies' end as owner,
               s.area,
               coalesce(max(s.ingredient), ''), case when bool_or(s.is_biologic) then 'Yes' else 'No' end,
               sum(s.spend), sum(s.rx), sum(s.units)
        from sales_nat s left join big b on b.family = s.family and b.market_class = s.market_class
        group by 1, 2, 3, 4, 5 order by 1, 8 desc""").fetchall()
    t.append(Table("fact_product_year",
                   [("year", "int64"), ("family", "string"), ("market_class", "string"), ("owner", "string"), ("area", "string"),
                    ("ingredient", "string"), ("is_biologic", "string"), ("spend_usd", "double"), ("rx_count", "double"), ("units_count", "double")], prod))

    t.append(Table("dim_owner", [("owner", "string")], [(o,) for o in [*top_owners, "All other companies"]]))

    t.append(Table("fact_state_area_year",
                   [("state", "string"), ("year", "int64"), ("area", "string"), ("spend_usd", "double"), ("rx_count", "double"), ("brand_spend_usd", "double")],
                   con.execute("""select state, year, area, spend, rx, coalesce(brand_spend, 0) from mart_state_area_year
                                  where state in (select state from dim_state where is_state) order by 1, 2, 3""").fetchall()))

    # reporting-break flag per state-year: same rule as the dashboard and the workbook (3-year window)
    flags = {(s, y): (f, c) for s, y, f, c in con.execute("select state, year, ffs_share, yoy_change from mart_state_flags").fetchall()}
    enroll = con.execute("""select state, year, enrollment, spend from mart_state_year where is_state and enrollment is not null order by 1, 2""").fetchall()
    sy = []
    for s, y, en, sp in enroll:
        swing = max([abs(flags[(s, k)][1]) for k in range(y - 2, y + 1) if (s, k) in flags and flags[(s, k)][1] is not None] or [0.0])
        shift = abs(flags[(s, y)][0] - flags[(s, y - 3)][0]) if (s, y) in flags and (s, y - 3) in flags else 0.0
        sy.append((s, y, en, flags[(s, y)][0], sp, "Check" if (shift >= 0.25 or swing >= 0.40) else "OK"))
    t.append(Table("fact_state_year", [("state", "string"), ("year", "int64"), ("enrollment", "double"), ("ffs_share", "double"), ("spend_usd", "double"), ("reporting", "string")], sy))

    step_order = {"volume": 1, "mix": 2, "price": 3, "newProducts": 4, "lostProducts": 5}
    step_name = {"volume": "More or fewer prescriptions", "mix": "Shift to costlier products", "price": "Spend per prescription",
                 "newProducts": "New products", "lostProducts": "Discontinued products"}
    pv = []
    for seg, y0, y1, vol, mix, price, new, lost in con.execute("select segment, y0, y1, volume, mix, price, new_products, lost_products from mart_pvm").fetchall():
        name = "All areas" if seg == "All market" else seg
        for key, val in (("volume", vol), ("mix", mix), ("price", price), ("newProducts", new), ("lostProducts", lost)):
            pv.append((name, f"{y0}-{y1}", step_name[key], step_order[key], val))
    t.append(Table("fact_pvm", [("segment", "string"), ("pair", "string"), ("step", "string"), ("step_order", "int64"), ("value", "double")], pv))

    loe = con.execute("""select family, owner, area, spend_2025, status, core_protection_end, substance_patent_expiry, year(core_protection_end)
                         from mart_loe where status = 'Protected' order by spend_2025 desc""").fetchall()
    t.append(Table("fact_loe", [("family", "string"), ("owner", "string"), ("area", "string"), ("spend_2025_usd", "double"), ("status", "string"),
                                ("core_end", "dateTime"), ("substance_end", "dateTime"), ("core_year", "int64")], loe))

    er = con.execute("""select c.ingredient, coalesce(c.brand_family, c.ingredient), c.quarters_since_entry, c.brand_spend_index, c.generic_share
                        from mart_erosion_curve c order by 1, 3""").fetchall()
    t.append(Table("fact_erosion", [("ingredient", "string"), ("brand", "string"), ("quarters_since_entry", "int64"), ("brand_index", "double"), ("generic_share", "double")], er))

    dq = [(r["id"], r["dimension"], r["name"], r["result"], r["status"].upper(), float(r["dollars"]) if r["dollars"] else None)
          for r in csv.DictReader(open(ROOT / "data" / "marts" / "dq_checks.csv", encoding="utf-8"))]
    t.append(Table("fact_quality", [("id", "string"), ("dimension", "string"), ("check", "string"), ("result", "string"), ("status", "string"), ("dollars", "double")], dq))
    return t


# ------------------------------------------------------------------------------------------------ measures
B = '"$#,0"'
M = '"$#,0.0""M"""'  # for measures already divided by a million
RXM = '"#,0"'
PCT = "0.0%"
USD0 = '"$#,0"'


def add_measures(tables: dict[str, Table]) -> None:
    fp = tables["fact_product_year"]
    fp.measures = [
        ("Spend", "SUM(fact_product_year[spend_usd])", B),
        ("Prescriptions", "SUM(fact_product_year[rx_count])", RXM),
        ("Spend per Rx", "DIVIDE([Spend], [Prescriptions])", USD0),
        ("Brand Spend", 'CALCULATE([Spend], fact_product_year[market_class] = "Brand")', B),
        ("Generic Spend", 'CALCULATE([Spend], fact_product_year[market_class] <> "Brand")', B),
        ("Brand Share of Spend", "DIVIDE([Brand Spend], [Spend])", PCT),
        ("Brand Share of Rx", 'DIVIDE(CALCULATE([Prescriptions], fact_product_year[market_class] = "Brand"), [Prescriptions])', PCT),
        ("Latest Year", "CALCULATE(MAX(dim_year[year]), ALL(dim_year))", "0"),
        ("First Year", "CALCULATE(MIN(dim_year[year]), ALL(dim_year))", "0"),
        ("Spend (latest year)", "VAR y = [Latest Year] RETURN CALCULATE([Spend], dim_year[year] = y)", B),
        ("Spend (first year)", "VAR y = [First Year] RETURN CALCULATE([Spend], dim_year[year] = y)", B),
        ("Prescriptions (latest year)", "VAR y = [Latest Year] RETURN CALCULATE([Prescriptions], dim_year[year] = y)", RXM),
        ("Spend per Rx (latest year)", "VAR y = [Latest Year] RETURN CALCULATE([Spend per Rx], dim_year[year] = y)", USD0),
        ("Brand Share of Spend (latest year)", "VAR y = [Latest Year] RETURN CALCULATE([Brand Share of Spend], dim_year[year] = y)", PCT),
        ("Brand Share of Rx (latest year)", "VAR y = [Latest Year] RETURN CALCULATE([Brand Share of Rx], dim_year[year] = y)", PCT),
        ("Spend Change since First Year", "[Spend (latest year)] - [Spend (first year)]", B),
        ("Spend CAGR", "IF(ISBLANK([Spend (first year)]) || [Spend (first year)] <= 0 || ISBLANK([Spend (latest year)]), BLANK(), DIVIDE([Spend (latest year)], [Spend (first year)]) ^ (1 / ([Latest Year] - [First Year])) - 1)", PCT),
        ("Spend $M (latest year)", "DIVIDE([Spend (latest year)], 1000000)", M),
        ("Company Spend (latest year)", 'IF(SELECTEDVALUE(dim_owner[owner], "All other companies") = "All other companies", BLANK(), [Spend (latest year)])', B),
    ]
    tables["fact_pvm"].measures = [
        ("Bridge Change", 'VAR sel = SELECTEDVALUE(dim_area[area], "All areas") VAR pr = SELECTEDVALUE(fact_pvm[pair], "2022-2025") RETURN CALCULATE(SUM(fact_pvm[value]), fact_pvm[segment] = sel, fact_pvm[pair] = pr)', B),
    ]
    tables["fact_state_area_year"].measures = [
        ("Spend per Enrollee", "VAR y = SELECTEDVALUE(dim_year[year], CALCULATE(MAX(dim_year[year]), ALL(dim_year))) RETURN CALCULATE(DIVIDE(SUM(fact_state_area_year[spend_usd]), SUM(fact_state_year[enrollment])), dim_year[year] = y)", USD0),
        ("Reporting Flag", 'VAR y = SELECTEDVALUE(dim_year[year], CALCULATE(MAX(dim_year[year]), ALL(dim_year))) RETURN CALCULATE(SELECTEDVALUE(fact_state_year[reporting], "OK"), dim_year[year] = y)', '"@"'),
        ("State Spend $M", "VAR y = SELECTEDVALUE(dim_year[year], CALCULATE(MAX(dim_year[year]), ALL(dim_year))) RETURN CALCULATE(SUM(fact_state_area_year[spend_usd]), dim_year[year] = y) / 1000000", M),
    ]
    tables["fact_loe"].measures = [
        ("Protected Spend (2025)", "SUM(fact_loe[spend_2025_usd])", B),
        ("Protected Brands", "COUNTROWS(fact_loe)", "0"),
        ("Protected Spend $M (2025)", "DIVIDE([Protected Spend (2025)], 1000000)", M),
    ]
    tables["fact_erosion"].measures = [
        ("Median Brand Index", "MEDIANX(VALUES(fact_erosion[ingredient]), CALCULATE(AVERAGE(fact_erosion[brand_index])))", "0"),
        ("Brands in Median", "DISTINCTCOUNT(fact_erosion[ingredient])", "0"),
    ]


RELATIONSHIPS = [
    ("fact_product_year", "year", "dim_year", "year"),
    ("fact_product_year", "area", "dim_area", "area"),
    ("fact_product_year", "owner", "dim_owner", "owner"),
    ("fact_state_area_year", "year", "dim_year", "year"),
    ("fact_state_area_year", "area", "dim_area", "area"),
    ("fact_state_area_year", "state", "dim_state", "state"),
    ("fact_state_year", "year", "dim_year", "year"),
    ("fact_state_year", "state", "dim_state", "state"),
    ("fact_loe", "area", "dim_area", "area"),
]


# ------------------------------------------------------------------------------------------------ writers
def write_csv(t: Table) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / f"{t.name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([c for c, _ in t.columns])
        for row in t.rows:
            out = []
            for v, (_, ty) in zip(row, t.columns):
                if v is None:
                    out.append("")
                elif ty == "dateTime":
                    out.append(v.isoformat())
                elif ty == "double":
                    out.append(repr(float(v)))
                else:
                    out.append(v)
            w.writerow(out)


_M_TYPES = {"string": "type text", "int64": "Int64.Type", "double": "type number", "dateTime": "type date"}


def tmdl_table(t: Table) -> str:
    L: list[str] = [f"table {t.name}", f"\tlineageTag: {_guid('table/' + t.name)}", ""]
    for name, dax, fmt in t.measures:
        qn = f"'{name}'" if any(c in name for c in " .=:'()") else name
        L.append(f"\tmeasure {qn} = {dax}")
        L.append(f"\t\tformatString: {fmt}")
        L.append(f"\t\tdisplayFolder: Measures")
        L.append(f"\t\tlineageTag: {_guid('measure/' + t.name + '/' + name)}")
        L.append("")
    for name, ty in t.columns:
        qn = f"'{name}'" if any(c in name for c in " .=:'()") else name
        L.append(f"\tcolumn {qn}")
        L.append(f"\t\tdataType: {ty}")
        if ty == "dateTime":
            L.append("\t\tformatString: mmm yyyy")
        elif ty == "int64":
            L.append("\t\tformatString: 0")
        L.append(f"\t\tlineageTag: {_guid('column/' + t.name + '/' + name)}")
        L.append("\t\tsummarizeBy: none")
        L.append(f"\t\tsourceColumn: {name}")
        L.append("")
    m_types = ", ".join(f'{{"{n}", {_M_TYPES[ty]}}}' for n, ty in t.columns)
    L += [
        f"\tpartition {t.name} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Source = Csv.Document(File.Contents(DataFolder & "{t.name}.csv"), [Delimiter=",", Columns={len(t.columns)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "\t\t\t\t    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        f"\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted, {{{m_types}}}, \"en-US\")",
        "\t\t\t\tin",
        "\t\t\t\t    Typed",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(L)


def write_model(tables: list[Table]) -> None:
    defn = MODEL / "definition"
    (defn / "tables").mkdir(parents=True, exist_ok=True)
    (MODEL / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    (MODEL / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": "RxMarketPulse"},
        "config": {"version": "2.0", "logicalId": _guid("semantic-model")}}, indent=2), encoding="utf-8")
    (defn / "database.tmdl").write_text("database RxMarketPulse\n\tcompatibilityLevel: 1601\n", encoding="utf-8")
    refs = "\n".join(f"ref table {t.name}" for t in tables)
    (defn / "model.tmdl").write_text(
        "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n"
        "\tsourceQueryCulture: en-US\n\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
        f"{refs}\n\nref expression DataFolder\n", encoding="utf-8")
    data_dir = str(DATA).replace("/", "\\") + "\\"
    (defn / "expressions.tmdl").write_text(
        f'expression DataFolder = "{data_dir}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {_guid('expression/DataFolder')}\n\n"
        "\tannotation PBI_ResultType = Text\n", encoding="utf-8")
    rel = []
    for frm, fcol, to, tcol in RELATIONSHIPS:
        rel.append(f"relationship {_guid(f'rel/{frm}.{fcol}-{to}.{tcol}')}\n\tfromColumn: {frm}.{fcol}\n\ttoColumn: {to}.{tcol}\n")
    (defn / "relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")
    for t in tables:
        (defn / "tables" / f"{t.name}.tmdl").write_text(tmdl_table(t), encoding="utf-8")


# ---- report (PBIR)
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


def lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


def colour(hex_: str) -> dict:
    return {"solid": {"color": lit(f"'{hex_}'")}}


def col_ref(table: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def meas_ref(table: str, prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def proj(field_: dict, table: str, prop: str, active: bool = True) -> dict:
    return {"field": field_, "queryRef": f"{table}.{prop}", "nativeQueryRef": prop, "active": active}


def C(table: str, prop: str, active: bool = False) -> dict:
    return proj(col_ref(table, prop), table, prop, active)


def cols(table: str, *props: str) -> list[dict]:
    """Table columns: each one active so every field is shown."""
    return [C(table, p_, True) for p_ in props]


def Mz(table: str, prop: str) -> dict:
    return proj(meas_ref(table, prop), table, prop)


@dataclass
class V:
    kind: str
    x: int
    y: int
    w: int
    h: int
    roles: dict[str, list[dict]] = field(default_factory=dict)
    title: str | None = None
    objects: dict | None = None
    sort: tuple[dict, str] | None = None
    text: list[tuple[str, str, str]] | None = None  # for textbox: (text, size, weight)
    pick: tuple[str, str, str] | None = None  # slicer default: (table, column, value)
    ignore: tuple[int, ...] = ()  # indexes of slicers on the page that must not filter this visual


def visual_json(page: str, i: int, v: V) -> dict:
    vis: dict = {"visualType": v.kind}
    if v.kind == "textbox":
        runs = [{"textRuns": [{"value": t, "textStyle": {"fontSize": s, "fontWeight": w, "color": INK}}]} for t, s, w in (v.text or [])]
        vis["objects"] = {"general": [{"properties": {"paragraphs": runs}}]}
    else:
        q: dict = {"queryState": {role: {"projections": ps} for role, ps in v.roles.items()}}
        if v.sort:
            q["sortDefinition"] = {"sort": [{"field": v.sort[0], "direction": v.sort[1]}]}
        vis["query"] = q
        if v.objects:
            vis["objects"] = v.objects
        vis["drillFilterOtherVisuals"] = True
    out: dict = {
        "$schema": f"{SCHEMA}/visualContainer/2.0.0/schema.json",
        "name": _oid(f"{page}/{i}"),
        "position": {"x": v.x, "y": v.y, "z": i, "height": v.h, "width": v.w, "tabOrder": i},
        "visual": vis,
    }
    if v.pick:
        tbl, colname, val = v.pick
        sel = {"Version": 2, "From": [{"Name": "d", "Entity": tbl, "Type": 0}],
               "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": colname}}],
                                               "Values": [[{"Literal": {"Value": f"'{val}'"}}]]}}}]}
        out["visual"].setdefault("objects", {})["general"] = [{"properties": {"filter": {"filter": sel}}}]
    if v.title:
        out["visual"]["visualContainerObjects"] = {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{v.title}'"), "fontSize": lit("12D"), "fontColor": colour(INK)}}]}
    return out


def bar_colour(c: str) -> dict:
    return {"dataPoint": [{"properties": {"fill": colour(c)}}]}


def series_colours(pairs: list[tuple[str, str]]) -> dict:
    return {"dataPoint": [{"properties": {"fill": colour(c)}, "selector": {"metadata": ref}} for ref, c in pairs]}


def pages() -> list[tuple[str, str, list[V]]]:
    P: list[tuple[str, str, list[V]]] = []
    area_slicer = lambda x, y, w=250, h=80: V("slicer", x, y, w, h, {"Values": [C("dim_area", "area", True)]},
                                              objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]}, title="Therapeutic area")
    head = lambda text, sub: [V("textbox", 24, 6, 800, 52, text=[(text, "22pt", "bold")]), V("textbox", 24, 58, 940, 30, text=[(sub, "11pt", "normal")])]

    # 1. Overview
    P.append(("overview", "Overview", head("What Medicaid pays for drugs", "Spend, prescriptions and brand share, 2019 to 2025. US Medicaid only, before rebates.") + [
        area_slicer(990, 14),
        V("card", 24, 100, 300, 110, {"Values": [Mz("fact_product_year", "Spend (latest year)")]}, title="Spend, latest year"),
        V("card", 340, 100, 300, 110, {"Values": [Mz("fact_product_year", "Prescriptions (latest year)")]}, title="Prescriptions, latest year"),
        V("card", 656, 100, 300, 110, {"Values": [Mz("fact_product_year", "Spend per Rx (latest year)")]}, title="Spend per prescription"),
        V("card", 972, 100, 284, 110, {"Values": [Mz("fact_product_year", "Brand Share of Spend (latest year)")]}, title="Brand share of spend"),
        V("columnChart", 24, 232, 620, 456,
          {"Category": [C("dim_year", "year", True)], "Y": [Mz("fact_product_year", "Brand Spend"), Mz("fact_product_year", "Generic Spend")]},
          title="Spend by year: brand and generic",
          objects=series_colours([("fact_product_year.Brand Spend", TEAL), ("fact_product_year.Generic Spend", OCHRE)])),
        V("lineChart", 664, 232, 592, 456,
          {"Category": [C("dim_year", "year", True)], "Y": [Mz("fact_product_year", "Brand Share of Spend"), Mz("fact_product_year", "Brand Share of Rx")]},
          title="Brand share of spend vs of prescriptions",
          objects=series_colours([("fact_product_year.Brand Share of Spend", TEAL), ("fact_product_year.Brand Share of Rx", OCHRE)])),
    ]))

    # 2. Growth
    P.append(("growth", "Growth", head("Where the growth came from", "Bridge from one year to another, and extra spend by therapeutic area.") + [
        V("slicer", 24, 96, 260, 80, {"Values": [C("fact_pvm", "pair", True)]}, title="Years compared",
          objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}], "selection": [{"properties": {"singleSelect": lit("true")}}]}),
        V("slicer", 300, 96, 300, 80, {"Values": [C("dim_area", "area", True)]}, title="Therapeutic area (bridge)",
          objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]}),
        V("waterfallChart", 24, 184, 600, 504, {"Category": [C("fact_pvm", "step", True)], "Y": [Mz("fact_pvm", "Bridge Change")]},
          title="Why spend changed (selected years and area)",
          sort=(col_ref("fact_pvm", "step_order"), "Ascending"),
          objects={"sentimentColors": [{"properties": {"increaseFill": colour(TEAL), "decreaseFill": colour(RUST), "totalFill": colour(INK)}}]}),
        V("clusteredBarChart", 640, 100, 616, 588, {"Category": [C("dim_area", "area", True)], "Y": [Mz("fact_product_year", "Spend Change since First Year")]},
          title="Extra spend since the first year, by area", objects=bar_colour(TEAL),
          sort=(meas_ref("fact_product_year", "Spend Change since First Year"), "Descending")),
    ]))

    # 3. Companies
    P.append(("companies", "Companies", head("Who sells it", "Parent company today; a brand keeps one owner across years. Outside-in view from public data.") + [
        area_slicer(990, 14),
        V("slicer", 24, 96, 320, 80, {"Values": [C("dim_owner", "owner", True)]}, title="Company", objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]}, pick=("dim_owner", "owner", "Merck (MSD)")),
        V("clusteredBarChart", 24, 184, 520, 504, {"Category": [C("dim_owner", "owner", True)], "Y": [Mz("fact_product_year", "Company Spend (latest year)")]},
          title="Latest-year spend by company (largest 26)", objects=bar_colour(TEAL), ignore=(3,),
          sort=(meas_ref("fact_product_year", "Company Spend (latest year)"), "Descending")),
        V("tableEx", 560, 96, 696, 592,
          {"Values": [*cols("fact_product_year", "family", "area"), Mz("fact_product_year", "Spend $M (latest year)"), Mz("fact_product_year", "Spend CAGR")]},
          title="Brands of the selected company", sort=(meas_ref("fact_product_year", "Spend $M (latest year)"), "Descending")),
    ]))

    # 4. Generics and patents
    P.append(("lifecycle", "Generics and patents", head("What happens when generics arrive, and when protection ends", "Brand spend after generic entry (median), and 2025 spend by year core protection ends.") + [
        V("lineChart", 24, 100, 620, 588, {"Category": [C("fact_erosion", "quarters_since_entry", True)], "Y": [Mz("fact_erosion", "Median Brand Index")]},
          title="Median brand spend index by quarter since generics entered (100 = year before)", objects={"dataPoint": [{"properties": {"fill": colour(TEAL)}}]}),
        V("columnChart", 660, 100, 596, 330, {"Category": [C("fact_loe", "core_year", True)], "Y": [Mz("fact_loe", "Protected Spend (2025)")]},
          title="2025 spend by year core protection ends", objects=bar_colour(TEAL)),
        V("tableEx", 660, 446, 596, 242, {"Values": [*cols("fact_loe", "family", "owner", "core_end"), Mz("fact_loe", "Protected Spend $M (2025)")]},
          title="Brands by core protection end date", sort=(meas_ref("fact_loe", "Protected Spend $M (2025)"), "Descending")),
    ]))

    # 5. States
    P.append(("states", "States", head("Which states", "Spend per Medicaid enrollee. A state marked Check changed how it reports; do not read its trend as demand.") + [
        area_slicer(990, 14),
        V("slicer", 24, 96, 200, 80, {"Values": [C("dim_year", "year", True)]}, title="Year", objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}], "selection": [{"properties": {"singleSelect": lit("true")}}]}),
        V("clusteredBarChart", 24, 184, 620, 504, {"Category": [C("dim_state", "state_name", True)], "Y": [Mz("fact_state_area_year", "Spend per Enrollee")]},
          title="Spend per enrollee by state", objects=bar_colour(TEAL), sort=(meas_ref("fact_state_area_year", "Spend per Enrollee"), "Descending")),
        V("tableEx", 660, 100, 596, 588,
          {"Values": [*cols("dim_state", "state_name", "region"), Mz("fact_state_area_year", "State Spend $M"), Mz("fact_state_area_year", "Spend per Enrollee"), Mz("fact_state_area_year", "Reporting Flag")]},
          title="States", sort=(meas_ref("fact_state_area_year", "Spend per Enrollee"), "Descending")),
    ]))

    # 6. Data quality
    P.append(("quality", "Data quality", head("How far to trust it", "Checks run on every build of the warehouse, with the spend each one touches.") + [
        V("tableEx", 24, 100, 1232, 588, {"Values": [*cols("fact_quality", "id", "check", "result", "status", "dollars")]},
          title="Data-quality checks"),
    ]))
    return P


def write_report() -> None:
    d = REPORT / "definition"
    (REPORT / "StaticResources" / "RegisteredResources").mkdir(parents=True, exist_ok=True)
    (REPORT / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "RxMarketPulse"},
        "config": {"version": "2.0", "logicalId": _guid("report")}}, indent=2), encoding="utf-8")
    (REPORT / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../RxMarketPulse.SemanticModel"}}}, indent=2), encoding="utf-8")

    theme = {
        "name": "RxPulse",
        "dataColors": [TEAL, OCHRE, SLATE, RUST, "#6FBFB2", "#8A7A4A", "#2D9C8B", "#B9B29E"],
        "background": PAPER, "foreground": INK, "tableAccent": TEAL,
        "textClasses": {"title": {"fontFace": "Georgia", "fontSize": 12, "color": INK}, "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": INK},
                        "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 28, "color": INK}},
        "visualStyles": {
            "*": {"*": {
                "background": [{"color": {"solid": {"color": PAPER}}, "transparency": 0}],
                "border": [{"show": False}],
                "title": [{"fontFamily": "Georgia", "fontSize": 12, "fontColor": {"solid": {"color": INK}}, "alignment": "left"}],
            }},
            "page": {"*": {"background": [{"color": {"solid": {"color": PAPER}}, "transparency": 0}]}},
        },
    }
    (REPORT / "StaticResources" / "RegisteredResources" / "RxPulse.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")

    (d / "pages").mkdir(parents=True, exist_ok=True)
    (d / "version.json").write_text(json.dumps({"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2), encoding="utf-8")
    (d / "report.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/report/3.0.0/schema.json",
        "themeCollection": {"customTheme": {"name": "RxPulse.json", "reportVersionAtImport": {"visual": "2.0.0", "report": "3.0.0", "page": "2.0.0"}, "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "RxPulse.json", "path": "RxPulse.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True, "useEnhancedTooltips": True},
    }, indent=2), encoding="utf-8")

    ps = pages()
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [_oid(k) for k, _, _ in ps], "activePageName": _oid(ps[0][0])}, indent=2), encoding="utf-8")
    for key, display, visuals in ps:
        pdir = d / "pages" / _oid(key)
        (pdir / "visuals").mkdir(parents=True, exist_ok=True)
        page_json = {"$schema": f"{SCHEMA}/page/2.0.0/schema.json", "name": _oid(key), "displayName": display,
                     "displayOption": "FitToPage", "height": 720, "width": 1280}
        inter = [{"source": _oid(f"{key}/{j}"), "target": _oid(f"{key}/{i}"), "type": "NoFilter"}
                 for i, v in enumerate(visuals) for j in v.ignore]
        if inter:
            page_json["visualInteractions"] = inter
        (pdir / "page.json").write_text(json.dumps(page_json, indent=2), encoding="utf-8")
        for i, v in enumerate(visuals):
            vdir = pdir / "visuals" / _oid(f"{key}/{i}")
            vdir.mkdir(parents=True, exist_ok=True)
            (vdir / "visual.json").write_text(json.dumps(visual_json(key, i, v), indent=2), encoding="utf-8")


def main() -> int:
    con = connect()
    tables = build_tables(con)
    con.close()
    by = {t.name: t for t in tables}
    add_measures(by)
    for t in tables:
        write_csv(t)
    write_model(tables)
    write_report()
    (PBI / "RxMarketPulse.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": "RxMarketPulse.Report"}}], "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
    (PBI / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n", encoding="utf-8")
    n = sum(len(t.rows) for t in tables)
    print(f"wrote {len(tables)} tables ({n:,} rows), {sum(len(t.measures) for t in tables)} measures, {len(pages())} report pages to {PBI}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
