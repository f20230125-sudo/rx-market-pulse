"""Territory Targeting Model: an Excel workbook that ranks the 51 states and allocates a growth target.

    python -m rx.workbook            # writes excel/Territory-Targeting-Model.xlsx

Everything on the Scorecard is a live formula (SUMIFS, INDEX/MATCH, PERCENTRANK, RANK), so changing a
yellow input on the Inputs sheet recalculates the whole model. The data sheets hold only the numbers
from the warehouse marts; no result is pasted in.
"""

from __future__ import annotations

from pathlib import Path

import xlsxwriter

from .build import connect
from .sources import ROOT

OUT = ROOT / "excel" / "Territory-Targeting-Model.xlsx"

# One palette across the workbook, the dashboard and the Power BI kit.
INK = "#16302F"
TEAL = "#0F766E"
TEAL_LIGHT = "#D9EEEA"
SLATE = "#5B6B73"
RULE = "#D5DEDD"
INPUT_FILL = "#FFF6D6"
INPUT_FONT = "#1D4ED8"
AMBER = "#B45309"

FIRST, LAST_ROW = 7, 57  # Scorecard rows (1-based) for the 51 states
N_STATES = LAST_ROW - FIRST + 1


def load(con):
    states = con.execute("select state, state_name, census_region from dim_state where is_state order by state_name").fetchall()
    areas = [r[0] for r in con.execute("select area from mart_area_year group by 1 order by sum(spend) desc").fetchall()]
    data = con.execute("""select state, year, area, spend, rx, coalesce(brand_spend, 0)
                          from mart_state_area_year
                          where state in (select state from dim_state where is_state) order by 1, 2, 3""").fetchall()
    enroll = con.execute("""select state, year, enrollment from mart_state_year
                            where is_state and enrollment is not null order by 1, 2""").fetchall()
    national = con.execute("select year, area, sum(spend), sum(rx) from mart_area_year group by 1, 2 order by 1, 2").fetchall()
    flags = con.execute("""select state, year, ffs_share, yoy_change from mart_state_flags
                          where state in (select state from dim_state where is_state) order by 1, 2""").fetchall()
    return states, areas, data, enroll, national, flags


def build(path: Path = OUT) -> Path:
    con = connect()
    states, areas, data, enroll, national, flags = load(con)
    con.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(path), {"use_future_functions": True})
    wb.set_calc_mode("auto")
    wb.set_properties({"title": "Territory Targeting Model", "author": "Mohammad Uzair Khan",
                       "comments": "Built from public Medicaid State Drug Utilization Data (CMS)."})

    base = {"font_name": "Calibri", "font_size": 10, "font_color": INK}
    f = lambda **kw: wb.add_format({**base, **kw})
    title = f(font_size=18, bold=True, font_color=INK)
    sub = f(font_color=SLATE, italic=True)
    h = f(bold=True, font_color="white", bg_color=INK, border=0, valign="vcenter", text_wrap=True, align="center")
    h_left = f(bold=True, font_color="white", bg_color=INK, valign="vcenter", text_wrap=True)
    cell = f(bottom=1, bottom_color=RULE)
    money = f(num_format='$#,##0.0,,"M"', bottom=1, bottom_color=RULE)
    money0 = f(num_format='$#,##0', bottom=1, bottom_color=RULE)
    pct = f(num_format="0.0%", bottom=1, bottom_color=RULE)
    pct0 = f(num_format="0%", bottom=1, bottom_color=RULE)
    num0 = f(num_format="#,##0", bottom=1, bottom_color=RULE)
    num1 = f(num_format="0.0", bottom=1, bottom_color=RULE)
    bold = f(bold=True)
    label = f(bold=True, font_color=SLATE)
    inp = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True, align="center")
    inp_pct = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True, num_format="0%", align="center")
    inp_money = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True, num_format="$#,##0", align="center")
    calc_pct = f(num_format="0%", bold=True, align="center", bottom=1, bottom_color=RULE)
    pct_c = f(num_format="0%", align="center", bottom=1, bottom_color=RULE)
    inp_pct_c = f(bg_color=INPUT_FILL, font_color=INPUT_FONT, border=1, border_color="#E6D9A8", bold=True, num_format="0%", align="center")
    note = f(font_color=SLATE, text_wrap=True, valign="top")
    ok = f(bold=True, font_color=TEAL)
    bad = f(bold=True, font_color="#B91C1C")
    tot_money = f(num_format='$#,##0.0,,"M"', bold=True, top=2, top_color=INK)
    tot_label = f(bold=True, top=2, top_color=INK)

    # ------------------------------------------------------------------ sheets (order = tab order)
    ws_read = wb.add_worksheet("Read me")
    ws_in = wb.add_worksheet("Inputs")
    ws_sc = wb.add_worksheet("Scorecard")
    ws_sum = wb.add_worksheet("Summary")
    ws_chk = wb.add_worksheet("Checks")
    ws_data = wb.add_worksheet("Data")
    ws_en = wb.add_worksheet("Enrollment")
    ws_nat = wb.add_worksheet("National")
    ws_flags = wb.add_worksheet("Flags")
    ws_lists = wb.add_worksheet("Lists")
    for ws, colour in ((ws_read, SLATE), (ws_in, "#CA8A04"), (ws_sc, TEAL), (ws_sum, TEAL), (ws_chk, SLATE),
                       (ws_data, "#94A3B8"), (ws_en, "#94A3B8"), (ws_nat, "#94A3B8"), (ws_flags, "#94A3B8"), (ws_lists, "#94A3B8")):
        ws.set_tab_color(colour)
        ws.hide_gridlines(2)

    # ------------------------------------------------------------------ Lists (dropdown sources)
    ws_lists.write_row(0, 0, ["Areas"], h_left)
    area_list = ["All areas"] + areas
    for i, a in enumerate(area_list):
        ws_lists.write(i + 1, 0, a)
    ws_lists.write_row(0, 2, ["Years"], h_left)
    for i, y in enumerate(range(2019, 2026)):
        ws_lists.write_number(i + 1, 2, y)
    ws_lists.write_row(0, 4, ["Scenarios"], h_left)
    scenarios = ["Balanced", "Growth-led", "Size-led", "Custom"]
    for i, s in enumerate(scenarios):
        ws_lists.write(i + 1, 4, s)
    ws_lists.set_column(0, 4, 26)
    ws_lists.hide()

    # ------------------------------------------------------------------ Data sheets
    ws_data.write_row(0, 0, ["state", "year", "area", "spend", "rx", "brand_spend"], h_left)
    for i, (st, yr, ar, sp, rx, bs) in enumerate(data, start=1):
        ws_data.write_string(i, 0, st)
        ws_data.write_number(i, 1, int(yr))
        ws_data.write_string(i, 2, ar)
        ws_data.write_number(i, 3, float(sp or 0))
        ws_data.write_number(i, 4, float(rx or 0))
        ws_data.write_number(i, 5, float(bs or 0))
    ws_data.set_column(0, 1, 8)
    ws_data.set_column(2, 2, 34)
    ws_data.set_column(3, 5, 16, f(num_format="#,##0"))
    ws_data.freeze_panes(1, 0)
    ws_data.autofilter(0, 0, len(data), 5)
    n_data = len(data) + 1

    ws_en.write_row(0, 0, ["state", "year", "avg_enrollment"], h_left)
    for i, (st, yr, en) in enumerate(enroll, start=1):
        ws_en.write_string(i, 0, st)
        ws_en.write_number(i, 1, int(yr))
        ws_en.write_number(i, 2, float(en))
    ws_en.set_column(0, 1, 8)
    ws_en.set_column(2, 2, 18, f(num_format="#,##0"))
    ws_en.freeze_panes(1, 0)
    n_en = len(enroll) + 1

    ws_nat.write_row(0, 0, ["year", "area", "spend", "rx"], h_left)
    for i, (yr, ar, sp, rx) in enumerate(national, start=1):
        ws_nat.write_number(i, 0, int(yr))
        ws_nat.write_string(i, 1, ar)
        ws_nat.write_number(i, 2, float(sp))
        ws_nat.write_number(i, 3, float(rx))
    ws_nat.set_column(0, 0, 8)
    ws_nat.set_column(1, 1, 34)
    ws_nat.set_column(2, 3, 18, f(num_format="#,##0"))
    ws_nat.freeze_panes(1, 0)
    n_nat = len(national) + 1

    ws_flags.write_row(0, 0, ["state", "year", "ffs_share", "yoy_change", "abs_yoy"], h_left)
    for i, (st, yr, ffs, yoy) in enumerate(flags, start=1):
        ws_flags.write_string(i, 0, st)
        ws_flags.write_number(i, 1, int(yr))
        ws_flags.write_number(i, 2, float(ffs))
        if yoy is not None:
            ws_flags.write_number(i, 3, float(yoy))
            ws_flags.write_formula(i, 4, f"=ABS(D{i + 1})")
    ws_flags.set_column(0, 1, 8)
    ws_flags.set_column(2, 4, 14, f(num_format="0.0%"))
    ws_flags.freeze_panes(1, 0)
    n_fl = len(flags) + 1
    FL = lambda col: f"Flags!${col}$2:${col}${n_fl}"  # noqa: E731

    D = lambda col: f"Data!${col}$2:${col}${n_data}"  # noqa: E731
    E = lambda col: f"Enrollment!${col}$2:${col}${n_en}"  # noqa: E731
    N = lambda col: f"National!${col}$2:${col}${n_nat}"  # noqa: E731

    # ------------------------------------------------------------------ Inputs
    ws_in.set_column(0, 0, 3)
    ws_in.set_column(1, 1, 44)
    ws_in.set_column(2, 6, 15)
    ws_in.set_column(7, 7, 38)
    ws_in.write("B1", "Inputs", title)
    ws_in.write("B2", "Change the yellow cells. Everything else in the workbook recalculates.", sub)

    ws_in.write("B4", "Market", label)
    rows = [
        ("B5", "Therapeutic area", "C5", "All areas", inp, "Which part of the market to score. 'All areas' scores total spend."),
        ("B6", "Base year", "C6", 2025, inp, "The year whose spend is being ranked (2019-2025)."),
        ("B7", "Growth look-back (years)", "C7", 3, inp, "Growth is the compound annual rate over this many years, ending in the base year."),
        ("B8", "Minimum prior-year spend ($)", "C8", 1_000_000, inp_money, "Below this, growth is too noisy to rank, so the state gets the median growth."),
    ]
    for lab_cell, lab, val_cell, val, fmt, why in rows:
        ws_in.write(lab_cell, lab)
        ws_in.write(val_cell, val, fmt)
        ws_in.merge_range(f"D{lab_cell[1:]}:H{lab_cell[1:]}", why, note)
    ws_in.data_validation("C5", {"validate": "list", "source": f"=Lists!$A$2:$A${len(area_list) + 1}"})
    ws_in.data_validation("C6", {"validate": "list", "source": "=Lists!$C$2:$C$8"})
    ws_in.data_validation("C7", {"validate": "integer", "criteria": "between", "minimum": 1, "maximum": 5,
                                 "error_title": "Look-back", "error_message": "Choose 1 to 5 years."})

    ws_in.write("B10", "Target", label)
    ws_in.write("B11", "National growth target")
    ws_in.write("C11", 0.08, inp_pct)
    ws_in.merge_range("D11:H11", "The extra spend the team is asked to win next year, as a share of the base year. Split across states below.", note)
    ws_in.write("B12", "Tier A: number of states")
    ws_in.write("C12", 10, inp)
    ws_in.write("B13", "Tier B: number of states")
    ws_in.write("C13", 20, inp)
    ws_in.merge_range("D12:H12", "Tier A gets first call on field resources; B is maintained; C is served remotely. Rest of the 51 are tier C.", note)
    ws_in.data_validation("C11", {"validate": "decimal", "criteria": "between", "minimum": -0.5, "maximum": 1})
    ws_in.data_validation("C12:C13", {"validate": "integer", "criteria": "between", "minimum": 1, "maximum": 50})

    ws_in.write("B15", "Score weights", label)
    ws_in.write_row("B16", ["Factor", "Balanced", "Growth-led", "Size-led", "Custom", "In use"], h_left)
    ws_in.set_row(15, 20)
    factors = [
        ("Market size (spend)", [0.35, 0.20, 0.55, 0.25]),
        ("Growth", [0.25, 0.45, 0.10, 0.25]),
        ("Intensity (spend per enrollee)", [0.20, 0.20, 0.20, 0.25]),
        ("Brand share of spend", [0.20, 0.15, 0.15, 0.25]),
    ]
    ws_in.write("B22", "Scenario", bold)
    ws_in.write("C22", "Balanced", inp)
    ws_in.data_validation("C22", {"validate": "list", "source": "=Lists!$E$2:$E$5"})
    ws_in.merge_range("D22:H22", "Pick a preset, or 'Custom' to use the Custom column. 'In use' follows this choice.", note)
    for i, (name, ws_) in enumerate(factors):
        r = 17 + i  # rows 17..20
        ws_in.write(r - 1, 1, name, cell)
        for j, wv in enumerate(ws_):
            ws_in.write_number(r - 1, 2 + j, wv, inp_pct_c if j == 3 else pct_c)
        ws_in.write_formula(r - 1, 6, f"=INDEX(C{r}:F{r},MATCH($C$22,$C$16:$F$16,0))", calc_pct)
    ws_in.write("B21", "Total (must be 100%)", tot_label)
    for col in "CDEFG":
        ws_in.write_formula(f"{col}21", f"=SUM({col}17:{col}20)", f(num_format="0%", bold=True, top=2, top_color=INK, align="center"))
    ws_in.write_formula("H21", '=IF(ROUND(G21,6)=1,"OK","Weights in use do not add to 100%: scores are not comparable")', f(bold=True, font_color=AMBER))

    ws_in.write("B24", "Read-outs", label)
    ws_in.write("B25", "National spend, selected area and year")
    ws_in.write_formula("C25", f'=SUMIFS({N("C")},{N("A")},$C$6,{N("B")},IF($C$5="All areas","*",$C$5))', money)
    ws_in.write("B26", "Sum of the 51 states, same selection")
    ws_in.write_formula("C26", f"=SUM(Scorecard!D{FIRST}:D{LAST_ROW})", money)
    ws_in.write("B27", "State coverage of national spend")
    ws_in.write_formula("C27", "=IF(C25>0,C26/C25,0)", pct)
    ws_in.merge_range("D27:H27", "", note)
    ws_in.write_formula("D27", '=IF(C27<0.85,"Low coverage: the source blanks small cells in state rows, so state totals understate this area. Treat ranks with care.","Coverage is usual for this source (state rows miss the small cells the source blanks).")',
                        f(font_color=AMBER, text_wrap=True, valign="top"))
    ws_in.set_row(26, 30)
    ws_in.conditional_format("H21", {"type": "cell", "criteria": "==", "value": '"OK"', "format": wb.add_format({"font_color": TEAL, "bold": True})})
    ws_in.write("B29", "Reporting breaks", label)
    ws_in.write("B30", "Neutralise growth where reporting changed")
    ws_in.write("C30", "Yes", inp)
    ws_in.data_validation("C30", {"validate": "list", "source": ["Yes", "No"]})
    ws_in.merge_range("D30:H30", "A state flagged 'Check' on the Scorecard gets the median growth instead of its own, so a bookkeeping change is not scored as demand.", note)
    ws_in.write("B31", "Flag: fee-for-service share moves by at least")
    ws_in.write("C31", 0.25, inp_pct)
    ws_in.merge_range("D31:H31", "States move pharmacy spend between managed-care plans and state fee-for-service (California 2022, New York 2023); totals shift with no change in demand.", note)
    ws_in.write("B32", "Flag: year-on-year swing of at least")
    ws_in.write("C32", 0.40, inp_pct)
    ws_in.merge_range("D32:H32", "Any single year in the look-back window where a state's total spend moves by this much, up or down.", note)
    ws_in.set_row(30, 30)
    wb.define_name("neutralise", "=Inputs!$C$30")
    wb.define_name("ffs_thr", "=Inputs!$C$31")
    wb.define_name("swing_thr", "=Inputs!$C$32")
    wb.define_name("sel_area", "=Inputs!$C$5")
    wb.define_name("sel_year", "=Inputs!$C$6")
    wb.define_name("sel_lookback", "=Inputs!$C$7")
    wb.define_name("min_base", "=Inputs!$C$8")
    wb.define_name("target_growth", "=Inputs!$C$11")
    wb.define_name("tier_a", "=Inputs!$C$12")
    wb.define_name("tier_b", "=Inputs!$C$13")
    wb.define_name("w_size", "=Inputs!$G$17")
    wb.define_name("w_growth", "=Inputs!$G$18")
    wb.define_name("w_intensity", "=Inputs!$G$19")
    wb.define_name("w_brand", "=Inputs!$G$20")

    # ------------------------------------------------------------------ Scorecard
    ws_sc.set_column(0, 0, 6)
    ws_sc.set_column(1, 1, 20)
    ws_sc.set_column(2, 2, 11)
    ws_sc.set_column(3, 4, 13)
    ws_sc.set_column(5, 6, 10)
    ws_sc.set_column(7, 7, 13)
    ws_sc.set_column(8, 9, 12)
    ws_sc.set_column(10, 13, 9)
    ws_sc.set_column(14, 14, 11)
    ws_sc.set_column(15, 16, 7)
    ws_sc.set_column(17, 17, 12)
    ws_sc.set_column(18, 19, 12)
    ws_sc.set_column(20, 22, 11)
    ws_sc.set_column(23, 23, 10)
    ws_sc.write("A1", "Scorecard", title)
    ws_sc.write_formula("A2", '="Scoring "&sel_area&" in "&sel_year&": growth over "&sel_lookback&" year(s), weights: "&Inputs!$C$22',
                        sub)
    ws_sc.write("A3", "Percentile columns run 0 (lowest of the 51 states) to 1 (highest). Score = weighted average of the four percentiles x 100.", sub)
    heads = ["", "State", "Region", "Spend (base year)", "Spend (prior)", "Growth p.a.", "Growth used",
             "Enrollment", "Spend per enrollee", "Brand share",
             "Size pctl", "Growth pctl", "Intensity pctl", "Brand pctl",
             "Opportunity score", "Rank", "Tier", "Weight (score x spend)", "Target spend", "Target growth",
             "FFS share (base)", "FFS share (prior)", "Largest yr-on-yr swing", "Reporting flag"]
    ws_sc.set_row(5, 34)
    for c, name in enumerate(heads):
        ws_sc.write(5, c, name, h if c else h_left)
    ws_sc.write(5, 0, "", h_left)

    for i, (st, nm, rg) in enumerate(states):
        r = FIRST + i  # 1-based row
        ws_sc.write_string(r - 1, 0, st, cell)
        ws_sc.write_string(r - 1, 1, nm, cell)
        ws_sc.write_string(r - 1, 2, rg, cell)
        area_crit = 'IF(sel_area="All areas","*",sel_area)'
        ws_sc.write_formula(r - 1, 3, f"=SUMIFS({D('D')},{D('A')},$A{r},{D('B')},sel_year,{D('C')},{area_crit})", money)
        ws_sc.write_formula(r - 1, 4, f"=SUMIFS({D('D')},{D('A')},$A{r},{D('B')},sel_year-sel_lookback,{D('C')},{area_crit})", money)
        ws_sc.write_formula(r - 1, 5, f'=IF(E{r}>0,(D{r}/E{r})^(1/sel_lookback)-1,"")', pct)
        ws_sc.write_formula(r - 1, 6, f'=IF(AND(E{r}>=min_base,ISNUMBER(F{r}),NOT(AND(neutralise="Yes",X{r}="Check"))),F{r},MEDIAN($F${FIRST}:$F${LAST_ROW}))', pct)
        ws_sc.write_formula(r - 1, 7, f"=SUMIFS({E('C')},{E('A')},$A{r},{E('B')},sel_year)", num0)
        ws_sc.write_formula(r - 1, 8, f"=IF(H{r}>0,D{r}/H{r},0)", money0)
        ws_sc.write_formula(r - 1, 9, f"=IF(D{r}>0,SUMIFS({D('F')},{D('A')},$A{r},{D('B')},sel_year,{D('C')},{area_crit})/D{r},0)", pct)
        for col, src in (("K", "D"), ("L", "G"), ("M", "I"), ("N", "J")):
            ws_sc.write_formula(f"{col}{r}", f"=PERCENTRANK.INC(${src}${FIRST}:${src}${LAST_ROW},{src}{r})", f(num_format="0.00", bottom=1, bottom_color=RULE, align="center"))
        # tiny ROW()-based term breaks exact ties so every state gets a distinct rank
        ws_sc.write_formula(f"O{r}", f"=100*(w_size*K{r}+w_growth*L{r}+w_intensity*M{r}+w_brand*N{r})+ROW()/1000000", f(num_format="0.0", bold=True, bottom=1, bottom_color=RULE, align="center"))
        ws_sc.write_formula(f"P{r}", f"=RANK.EQ(O{r},$O${FIRST}:$O${LAST_ROW})", f(num_format="0", bottom=1, bottom_color=RULE, align="center"))
        ws_sc.write_formula(f"Q{r}", f'=IF(P{r}<=tier_a,"A",IF(P{r}<=tier_a+tier_b,"B","C"))', f(bold=True, bottom=1, bottom_color=RULE, align="center"))
        ws_sc.write_formula(f"R{r}", f"=O{r}*D{r}", f(num_format="#,##0,,", bottom=1, bottom_color=RULE))
        ws_sc.write_formula(f"S{r}", f"=D{r}+SUM($D${FIRST}:$D${LAST_ROW})*target_growth*R{r}/SUM($R${FIRST}:$R${LAST_ROW})", money)
        ws_sc.write_formula(f"T{r}", f'=IF(D{r}>0,S{r}/D{r}-1,"")', pct)
        ws_sc.write_formula(f"U{r}", f"=SUMIFS({FL('C')},{FL('A')},$A{r},{FL('B')},sel_year)", pct0)
        ws_sc.write_formula(f"V{r}", f"=SUMIFS({FL('C')},{FL('A')},$A{r},{FL('B')},sel_year-sel_lookback)", pct0)
        ws_sc.write_formula(f"W{r}", f'=MAXIFS({FL("E")},{FL("A")},$A{r},{FL("B")},">"&(sel_year-sel_lookback),{FL("B")},"<="&sel_year)', pct0)
        ws_sc.write_formula(f"X{r}", f'=IF(OR(ABS(U{r}-V{r})>=ffs_thr,W{r}>=swing_thr),"Check","")', f(bold=True, font_color=AMBER, align="center", bottom=1, bottom_color=RULE))
    t = LAST_ROW + 1
    ws_sc.write(t - 1, 0, "", tot_label)
    ws_sc.write(t - 1, 1, "All 51 states", tot_label)
    for c in (2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17):
        ws_sc.write_blank(t - 1, c, None, tot_label)
    ws_sc.write_formula(t - 1, 3, f"=SUM(D{FIRST}:D{LAST_ROW})", tot_money)
    ws_sc.write_formula(t - 1, 4, f"=SUM(E{FIRST}:E{LAST_ROW})", tot_money)
    ws_sc.write_formula(t - 1, 7, f"=SUM(H{FIRST}:H{LAST_ROW})", f(num_format="#,##0", bold=True, top=2, top_color=INK))
    ws_sc.write_formula(t - 1, 18, f"=SUM(S{FIRST}:S{LAST_ROW})", tot_money)
    ws_sc.write_formula(t - 1, 19, f"=IF(D{t}>0,S{t}/D{t}-1,\"\")", f(num_format="0.0%", bold=True, top=2, top_color=INK))
    ws_sc.freeze_panes(6, 2)
    rng = f"A{FIRST}:T{LAST_ROW}"
    ws_sc.conditional_format(f"Q{FIRST}:Q{LAST_ROW}", {"type": "cell", "criteria": "==", "value": '"A"', "format": wb.add_format({"bg_color": TEAL, "font_color": "white"})})
    ws_sc.conditional_format(f"Q{FIRST}:Q{LAST_ROW}", {"type": "cell", "criteria": "==", "value": '"B"', "format": wb.add_format({"bg_color": TEAL_LIGHT})})
    ws_sc.conditional_format(f"O{FIRST}:O{LAST_ROW}", {"type": "data_bar", "bar_color": "#7DC4BA", "bar_solid": True, "min_type": "num", "min_value": 0, "max_type": "num", "max_value": 100})
    ws_sc.conditional_format(f"T{FIRST}:T{LAST_ROW}", {"type": "cell", "criteria": "<", "value": 0, "format": wb.add_format({"font_color": "#B91C1C"})})
    ws_sc.autofilter(5, 0, LAST_ROW - 1, 23)

    # ------------------------------------------------------------------ Summary
    ws_sum.set_column(0, 0, 3)
    ws_sum.set_column(1, 1, 8)
    ws_sum.set_column(2, 2, 22)
    ws_sum.set_column(3, 6, 14)
    ws_sum.set_column(7, 7, 12)
    ws_sum.set_column(8, 8, 3)
    ws_sum.set_column(9, 14, 12)
    ws_sum.write("B1", "Summary", title)
    ws_sum.write_formula("B2", '=sel_area&", "&sel_year&" - top 10 states by opportunity score"', sub)
    ws_sum.write_row("B4", ["Rank", "State", "Score", "Spend", "Growth p.a.", "Tier", "Reporting"], h)
    for k in range(1, 11):
        r = 4 + k
        ws_sum.write_number(r - 1, 1, k, f(bottom=1, bottom_color=RULE, align="center"))
        m = f"MATCH($B{r},Scorecard!$P${FIRST}:$P${LAST_ROW},0)"
        ws_sum.write_formula(r - 1, 2, f"=INDEX(Scorecard!$B${FIRST}:$B${LAST_ROW},{m})", cell)
        ws_sum.write_formula(r - 1, 3, f"=INDEX(Scorecard!$O${FIRST}:$O${LAST_ROW},{m})", f(num_format="0.0", bottom=1, bottom_color=RULE, align="center"))
        ws_sum.write_formula(r - 1, 4, f"=INDEX(Scorecard!$D${FIRST}:$D${LAST_ROW},{m})", money)
        ws_sum.write_formula(r - 1, 5, f"=INDEX(Scorecard!$G${FIRST}:$G${LAST_ROW},{m})", pct)
        ws_sum.write_formula(r - 1, 6, f"=INDEX(Scorecard!$Q${FIRST}:$Q${LAST_ROW},{m})", f(bold=True, bottom=1, bottom_color=RULE, align="center"))
        ws_sum.write_formula(r - 1, 7, f'=IF(INDEX(Scorecard!$X${FIRST}:$X${LAST_ROW},{m})="Check","Check","")', f(bold=True, font_color=AMBER, align="center", bottom=1, bottom_color=RULE))

    ws_sum.write("B17", "Headline", label)
    ws_sum.write_formula("B18", '="The top 10 states hold "&TEXT(SUMPRODUCT((Scorecard!$P$%d:$P$%d<=10)*Scorecard!$D$%d:$D$%d)/Scorecard!$D$%d,"0%%")&" of reported spend in this selection."' % (FIRST, LAST_ROW, FIRST, LAST_ROW, t), f(text_wrap=False))
    ws_sum.write_formula("B19", '="Tier A ("&tier_a&" states) carries "&TEXT(SUMIFS(Scorecard!$D$%d:$D$%d,Scorecard!$Q$%d:$Q$%d,"A")/Scorecard!$D$%d,"0%%")&" of spend and "&TEXT((SUMIFS(Scorecard!$S$%d:$S$%d,Scorecard!$Q$%d:$Q$%d,"A")-SUMIFS(Scorecard!$D$%d:$D$%d,Scorecard!$Q$%d:$Q$%d,"A"))/(Scorecard!$S$%d-Scorecard!$D$%d),"0%%")&" of the growth target."' % (FIRST, LAST_ROW, FIRST, LAST_ROW, t, FIRST, LAST_ROW, FIRST, LAST_ROW, FIRST, LAST_ROW, FIRST, LAST_ROW, t, t), f())
    ws_sum.write_formula("B21", '="States flagged for a reporting break in this window: "&COUNTIF(Scorecard!$X$%d:$X$%d,"Check")&" (see the Reporting flag column)."' % (FIRST, LAST_ROW), f())
    ws_sum.write_formula("B20", '="National growth target: "&TEXT(target_growth,"0%%")&" = "&TEXT(Scorecard!$S$%d-Scorecard!$D$%d,"$#,##0.0,,")&"M extra spend to win across the 51 states."' % (t, t), f())

    bar = wb.add_chart({"type": "bar"})
    bar.add_series({"name": "Opportunity score", "categories": "=Summary!$C$5:$C$14", "values": "=Summary!$D$5:$D$14",
                    "fill": {"color": TEAL}, "gap": 60, "data_labels": {"value": True, "num_format": "0", "font": {"color": INK, "size": 9}}})
    bar.set_title({"name": "Top 10 states by opportunity score", "name_font": {"size": 11, "bold": True, "color": INK}})
    bar.set_legend({"none": True})
    bar.set_y_axis({"reverse": True, "num_font": {"color": INK, "size": 9}, "line": {"none": True}})
    bar.set_x_axis({"min": 0, "max": 100, "major_gridlines": {"visible": True, "line": {"color": RULE}}, "num_font": {"color": SLATE, "size": 9}, "line": {"none": True}})
    bar.set_size({"width": 520, "height": 330})
    bar.set_chartarea({"border": {"none": True}})
    ws_sum.insert_chart("J4", bar)

    # national trend for the selected area: 7 years, formula-driven helper table
    ws_sum.write_row("B24", ["Year", "National spend, selected area"], h_left)
    for k, yr in enumerate(range(2019, 2026)):
        r = 25 + k
        ws_sum.write_number(r - 1, 1, yr, f(bottom=1, bottom_color=RULE, align="center"))
        ws_sum.write_formula(r - 1, 2, f'=SUMIFS({N("C")},{N("A")},$B{r},{N("B")},IF(sel_area="All areas","*",sel_area))', money)
    line = wb.add_chart({"type": "column"})
    line.add_series({"name": "National spend", "categories": "=Summary!$B$25:$B$31", "values": "=Summary!$C$25:$C$31",
                     "fill": {"color": SLATE}, "gap": 50})
    line.set_title({"name": "National spend in the selected area", "name_font": {"size": 11, "bold": True, "color": INK}})
    line.set_legend({"none": True})
    line.set_y_axis({"num_format": '$#,##0,,,"B"', "major_gridlines": {"visible": True, "line": {"color": RULE}}, "num_font": {"color": SLATE, "size": 9}, "line": {"none": True}})
    line.set_x_axis({"num_font": {"color": INK, "size": 9}})
    line.set_size({"width": 520, "height": 300})
    line.set_chartarea({"border": {"none": True}})
    ws_sum.insert_chart("J22", line)

    # ------------------------------------------------------------------ Checks
    ws_chk.set_column(0, 0, 3)
    ws_chk.set_column(1, 1, 62)
    ws_chk.set_column(2, 3, 20)
    ws_chk.set_column(4, 4, 12)
    ws_chk.write("B1", "Checks", title)
    ws_chk.write("B2", "Every row should say OK. They run on every recalculation.", sub)
    ws_chk.write_row("B4", ["Check", "Value", "Expected", "Result"], h_left)
    checks = [
        ("Weights in use add to 100%", "=Inputs!G21", "=1", 'IF(ABS(C5-D5)<0.000001,"OK","CHECK")', pct0),
        ("State spend adds up to the Data sheet for this selection",
         f"=Scorecard!D{t}", f'=SUMIFS({D("D")},{D("B")},sel_year,{D("C")},IF(sel_area="All areas","*",sel_area))', 'IF(ABS(C6-D6)<1,"OK","CHECK")', money0),
        ("Targets add up to base spend x (1 + growth target)", f"=Scorecard!S{t}", f"=Scorecard!D{t}*(1+target_growth)", 'IF(ABS(C7-D7)<1,"OK","CHECK")', money0),
        ("Every state has a distinct rank 1-51", f"=SUMPRODUCT(1/COUNTIF(Scorecard!P{FIRST}:P{LAST_ROW},Scorecard!P{FIRST}:P{LAST_ROW}))", "=51", 'IF(C8=D8,"OK","CHECK")', num0),
        ("No formula errors on the Scorecard", f"=SUMPRODUCT(--ISERROR(Scorecard!D{FIRST}:X{LAST_ROW}))", "=0", 'IF(C9=D9,"OK","CHECK")', num0),
        ("National Data total equals the National sheet (same selection)",
         f'=SUMIFS({D("D")},{D("B")},sel_year,{D("C")},IF(sel_area="All areas","*",sel_area))',
         f'=SUMIFS({N("C")},{N("A")},sel_year,{N("B")},IF(sel_area="All areas","*",sel_area))*(1-0)', 'IF(C10<=D10+1,"OK","CHECK")', money0),
        ("Enrollment found for all 51 states in the base year", f'=COUNTIFS({E("B")},sel_year)', "=51", 'IF(C11=D11,"OK","CHECK")', num0),
    ]
    for k, (name, v, e, res, fmt) in enumerate(checks):
        r = 5 + k
        ws_chk.write(r - 1, 1, name, cell)
        ws_chk.write_formula(r - 1, 2, v, fmt)
        ws_chk.write_formula(r - 1, 3, e, fmt)
        ws_chk.write_formula(r - 1, 4, "=" + res, f(bold=True, align="center"))
    ws_chk.conditional_format("E5:E11", {"type": "cell", "criteria": "==", "value": '"OK"', "format": wb.add_format({"font_color": TEAL, "bold": True})})
    ws_chk.conditional_format("E5:E11", {"type": "cell", "criteria": "==", "value": '"CHECK"', "format": wb.add_format({"font_color": "#B91C1C", "bold": True})})
    ws_chk.write("B13", "Overall", bold)
    ws_chk.write_formula("C13", '=IF(COUNTIF(E5:E11,"OK")=7,"All checks pass","Review the rows marked CHECK")', f(bold=True))

    # ------------------------------------------------------------------ Read me
    ws_read.set_column(0, 0, 3)
    ws_read.set_column(1, 1, 110)
    ws_read.write("B1", "Territory Targeting Model", title)
    ws_read.write("B2", "Rank the 51 US states for a therapeutic area, then split a national growth target across them.", sub)
    paras = [
        ("What it answers", "Where should a commercial team put field effort first, and how much of a growth target should each state carry? "
         "Pick an area on the Inputs sheet; the Scorecard ranks every state on four things (market size, growth, spend per enrollee, brand share) "
         "and turns the ranking into tiers A, B and C and a target for each state."),
        ("How the score works", "Each state gets a percentile (0 to 1) on each factor among the 51. Opportunity score = 100 x the weighted average of the four percentiles. "
         "Percentiles are used instead of raw values so one huge state (California, New York) cannot swamp the others. "
         "The growth target is split in proportion to score x current spend, so a high-scoring large state carries more of it."),
        ("How to use it", "1) Inputs: choose the area, base year and weights (or a preset).  2) Scorecard: filter or sort; tiers are coloured.  "
         "3) Summary: the top 10, headline sentences, charts.  4) Checks: every row should read OK."),
        ("Where the numbers come from", "CMS State Drug Utilization Data (Medicaid, public), 2019-2025, joined to the Medicaid Drug Rebate Program product list "
         "and the FDA directory so each NDC has a brand/generic flag and a therapeutic area. Enrollment is the monthly Medicaid and CHIP count (CMS), averaged per year. "
         "The full pipeline, tests and data-quality scorecard are in the repository this workbook was generated from."),
        ("What to be careful about", "This is Medicaid only, not the whole US market. Dollars are gross reimbursed amounts before manufacturer rebates. "
         "The source blanks any state-quarter-product cell with fewer than 11 prescriptions, so state rows add up to about 92% of the national total (lower for oncology and rare disease) "
         "(see the coverage line on Inputs); rare-disease areas are the most affected. Spend per enrollee uses total Medicaid and CHIP enrollment, "
         "not the number of patients with the condition. Puerto Rico is left out (reported from 2023 only, no enrollment series)."),
        ("Reporting breaks", "States sometimes move pharmacy spend between managed-care plans and state fee-for-service, which changes reported totals without "
         "changing demand: California did in 2022, New York in 2023, North Carolina over 2021-24, and Virginia reports an identical $6.24B in 2022 and 2023 before "
         "a 42% drop. The Scorecard flags a state 'Check' when its fee-for-service share moves by 25 points or more, or any single year swings 40% or more, "
         "and by default gives it the median growth rather than scoring the break as a trend. Both thresholds, and the switch, are on the Inputs sheet. "
         "Needs Excel 2019 or Microsoft 365 (the flag uses MAXIFS)."),
        ("Colour code", "Yellow cells with blue text are inputs. Everything else is a formula. Grey tabs are data."),
    ]
    row = 3
    for head, text in paras:
        ws_read.write(row, 1, head, bold)
        ws_read.write(row + 1, 1, text, note)
        ws_read.set_row(row + 1, 62)
        row += 3

    wb.close()
    return path


def main() -> int:
    out = build()
    print(f"wrote {out} ({out.stat().st_size / 1e3:,.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
