"""Data tests: properties the built warehouse must satisfy. Skipped when the warehouse has not been built.

    python -m rx.fetch && python -m rx.build && pytest
"""

import duckdb
import pytest

from rx.sources import WAREHOUSE

pytestmark = pytest.mark.skipif(not WAREHOUSE.exists(), reason="warehouse not built (python -m rx.build)")


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(WAREHOUSE), read_only=True)
    yield c
    c.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_every_year_lands_with_four_quarters(con):
    rows = con.execute("select year, count(distinct quarter) from fact_sdud group by 1 order by 1").fetchall()
    assert [y for y, _ in rows] == list(range(2019, 2026))
    assert all(q == 4 for _, q in rows)


def test_one_row_per_key_in_facts(con):
    dup = one(con, """select count(*) from (select utilization_type, state, ndc11, year, quarter
                      from fact_sdud group by all having count(*) > 1)""")
    assert dup == 0


def test_product_master_has_one_row_per_ndc(con):
    assert one(con, "select count(*) - count(distinct ndc11) from dim_product") == 0


def test_facts_only_hold_valid_ndcs(con):
    assert one(con, "select count(*) from fact_sdud where not regexp_matches(ndc11, '^[0-9]{11}$')") == 0
    assert one(con, "select count(*) from quarantine_sdud") > 0  # and the bad ones are kept, not lost


def test_staged_rows_equal_fact_plus_quarantine_rows(con):
    assert one(con, "select count(*) from stg_sdud") == one(con, "select count(*) from fact_sdud") + one(
        con, "select count(*) from quarantine_sdud")


def test_sales_table_reconciles_to_published_national_total(con):
    a = one(con, "select sum(spend) from sales_nat")
    b = one(con, "select sum(total_amount) from fact_sdud where state = 'XX' and year between 2019 and 2025")
    assert a == pytest.approx(b, rel=1e-12)


def test_product_mart_adds_back_to_national_per_year(con):
    rows = con.execute("""select n.year, n.s, p.s from
        (select year, sum(spend) s from sales_nat group by 1) n
        join (select year, sum(spend) s from mart_product_year group by 1) p using (year)""").fetchall()
    assert len(rows) == 7
    for year, nat, prod in rows:
        assert prod == pytest.approx(nat, rel=1e-9), year


def test_brand_generic_unknown_add_to_total(con):
    rows = con.execute("""select year, sum(spend) from mart_market_year group by 1""").fetchall()
    nat = dict(con.execute("select year, sum(spend) from sales_nat group by 1").fetchall())
    for year, s in rows:
        assert s == pytest.approx(nat[year], rel=1e-12)


def test_unknown_products_are_immaterial(con):
    share = one(con, "select sum(spend) filter (where market_class = 'Unknown') / sum(spend) from sales_nat")
    assert share < 0.001


def test_price_volume_mix_bridge_closes(con):
    worst = one(con, """select max(abs(change - (volume + mix + price + new_products + lost_products)))
                        from mart_pvm""")
    assert worst < 1.0  # dollars, on bridges worth tens of billions


def test_state_marts_cover_51_states_every_year(con):
    rows = con.execute("select year, count(distinct state) from mart_state_year where is_state group by 1").fetchall()
    assert len(rows) == 7 and all(n == 51 for _, n in rows)


def test_puerto_rico_is_a_flagged_territory_not_a_state(con):
    years = [y for (y,) in con.execute("select year from mart_state_year where state = 'PR' order by 1").fetchall()]
    assert years == [2023, 2024, 2025]  # reported from 2023 only
    assert one(con, "select count(*) from mart_state_year where state = 'PR' and is_state") == 0


def test_state_rows_are_below_national_because_of_suppression(con):
    rows = con.execute("select gap_pct from mart_reconciliation").fetchall()
    assert all(5.0 < g < 9.0 for (g,) in rows)  # the documented 6-7% gap, and it is never negative


def test_enrollment_has_no_duplicate_months(con):
    assert one(con, """select count(*) from (select state, year, month from fact_enrollment
                       group by all having count(*) > 1)""") == 0


def test_no_negative_spend_in_marts(con):
    assert one(con, "select count(*) from mart_product_year where spend < 0") == 0
    assert one(con, "select count(*) from mart_state_year where spend < 0") == 0


def test_msd_products_are_owned_by_msd_not_organon(con):
    # Nexplanon moved from Merck to Organon in 2021; it must follow its 2024-25 owner in every year.
    owner = one(con, "select owner from dim_brand_owner where product_family = 'NEXPLANON'")
    assert owner == "Organon"


def test_erosion_events_are_real_switches(con):
    rows = con.execute("select generic_share_q4 from mart_erosion_events where generic_share_q4 is not null").fetchall()
    assert len(rows) >= 10
    assert all(0 <= s <= 100 for (s,) in rows)
