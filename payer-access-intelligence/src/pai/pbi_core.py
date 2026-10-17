"""PBIP/TMDL/PBIR writers adapted from the user-owned Rx Market Pulse generator.
Report design and measures are defined by pai.powerbi, independently of Rx data.
"""
from __future__ import annotations
import csv, hashlib, json, uuid
from dataclasses import dataclass, field
from pathlib import Path
_M_TYPES = {"string": "type text", "int64": "Int64.Type", "double": "type number", "dateTime": "type date"}
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
TEAL, OCHRE, SLATE, RUST = "#087F8C", "#B87822", "#60758A", "#A8472A"
INK, PAPER, RULE = "#102B46", "#F7F8FA", "#D9E2EB"
def _guid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"payer-access-intelligence/{name}"))

def _oid(name: str) -> str:
    return hashlib.sha1(name.encode()).hexdigest()[:20]

@dataclass
class Table:
    name: str
    columns: list[tuple[str, str]]  # (name, dataType) dataType in string|int64|double|dateTime
    rows: list[tuple]
    measures: list[tuple[str, str, str]] = field(default_factory=list)  # (name, dax, formatString)
    hidden_cols: set[str] = field(default_factory=set)

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
        "metadata": {"type": "SemanticModel", "displayName": "PayerAccess"},
        "config": {"version": "2.0", "logicalId": _guid("semantic-model")}}, indent=2), encoding="utf-8")
    (defn / "database.tmdl").write_text("database PayerAccess\n\tcompatibilityLevel: 1601\n", encoding="utf-8")
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
    ignore: tuple[int, ...] = ()

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

def write_report() -> None:
    d = REPORT / "definition"
    (REPORT / "StaticResources" / "RegisteredResources").mkdir(parents=True, exist_ok=True)
    (REPORT / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "PayerAccess"},
        "config": {"version": "2.0", "logicalId": _guid("report")}}, indent=2), encoding="utf-8")
    (REPORT / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../PayerAccess.SemanticModel"}}}, indent=2), encoding="utf-8")

    theme = {
        "name": "PayerAccess",
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
    (REPORT / "StaticResources" / "RegisteredResources" / "PayerAccess.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")

    (d / "pages").mkdir(parents=True, exist_ok=True)
    (d / "version.json").write_text(json.dumps({"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2), encoding="utf-8")
    (d / "report.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/report/3.0.0/schema.json",
        "themeCollection": {"customTheme": {"name": "PayerAccess.json", "reportVersionAtImport": {"visual": "2.0.0", "report": "3.0.0", "page": "2.0.0"}, "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "PayerAccess.json", "path": "PayerAccess.json", "type": "CustomTheme"}]}],
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