"use client";

import { useMemo, useState, type ReactNode } from "react";
import { ThemeToggle } from "./ThemeToggle";
import { SpendColumns, ShareBars } from "./charts/Market";
import { AreaIncrease, Waterfall } from "./charts/Growth";
import { OwnerBars, ProductRows } from "./charts/Companies";
import { ErosionChart, ProtectedList, ProtectionChart } from "./charts/Lifecycle";
import { StateCallout, TileMap } from "./charts/States";
import { ForecastChart, QualityTable } from "./charts/Outlook";
import { QuarterlyAudit } from "./QuarterlyAudit";
import { areaGrowth, kpis, medianAt, medianCurve, protectionBars, stateRows, topOwners, waterfall } from "@/lib/derive";
import { count, pct, signedPct, usd } from "@/lib/format";
import { ALL, type Dataset } from "@/lib/schema";

function Section({ id, num, title, dek, children }: { id: string; num: string; title: ReactNode; dek: ReactNode; children: ReactNode }) {
  return (
    <section className="sec" id={id} aria-labelledby={`${id}-h`}>
      <div className="sec-head">
        <span className="sec-num" aria-hidden="true">{num}</span>
        <div>
          <h2 id={`${id}-h`}>{title}</h2>
          <p className="dek">{dek}</p>
        </div>
      </div>
      <div className="sec-body">{children}</div>
    </section>
  );
}

function Delta({ from, to, good }: { from: number; to: number; good?: "up" | "down" | "none" }) {
  const change = from ? to / from - 1 : 0;
  const cls = good === "none" ? "" : (change >= 0) === (good !== "down") ? "up" : "down";
  return <span className={cls}>{signedPct(change, Math.abs(change) < 0.1 ? 1 : 0)}</span>;
}

export function Report({ data, repoUrl }: { data: Dataset; repoUrl?: string }) {
  const { meta, market, pvm, owners, products, erosion, loe, states, forecast, quality } = data;
  const [area, setArea] = useState(ALL);
  const [pair, setPair] = useState("2022-2025");
  const [owner, setOwner] = useState(owners.pinned);
  const [protYear, setProtYear] = useState<string | null>("2026");
  const [mapYear, setMapYear] = useState(meta.years[meta.years.length - 1]);

  const years = meta.years;
  const scope = area === ALL ? "All therapeutic areas" : area;
  const series = market.series[area];
  const k = useMemo(() => kpis(market, area), [market, area]);
  const bridge = waterfall(pvm, area, pair);
  const areas = useMemo(() => areaGrowth(market, meta.areas), [market, meta.areas]);
  const ownerRows = useMemo(() => topOwners(owners, area, 12), [owners, area]);
  const ownerSel = ownerRows.some((r) => r.owner === owner) ? owner : owners.pinned;
  const ownerItems = products.owners[ownerSel] ?? [];
  const curve = useMemo(() => medianCurve(erosion), [erosion]);
  const m8 = medianAt(curve, 8);
  const bars = useMemo(() => protectionBars(loe, area), [loe, area]);
  const near = bars.filter((b) => ["2026", "2027", "2028"].includes(b.key)).reduce((a, b) => a + b.spend, 0);
  const lookback = 3;
  const sRows = useMemo(() => stateRows(states, area, mapYear, lookback), [states, area, mapYear]);
  const perEnr = sRows.map((r) => r.perEnrollee).filter((v): v is number => v != null).sort((a, b) => a - b);
  const spread = perEnr.length ? perEnr[perEnr.length - 1] / perEnr[0] : 0;
  const fc = forecast[area] ?? forecast[ALL];
  const lastFc = fc.forecast[fc.forecast.length - 1];
  const counts = quality.checks.reduce((a, c) => ({ ...a, [c.status]: (a[c.status as "pass"] ?? 0) + 1 }), {} as Record<string, number>);
  const biggest = bridge ? [...bridge.steps].filter((s) => s.type === "delta").sort((a, b) => Math.abs(b.value) - Math.abs(a.value))[0] : null;
  const driver = (s: { key: string; value: number }) =>
    ({
      volume: s.value >= 0 ? "more prescriptions" : "fewer prescriptions",
      mix: "a shift to costlier products",
      price: s.value >= 0 ? "higher spend per prescription" : "lower spend per prescription",
      newProducts: "new products",
      lostProducts: "products leaving the market",
    })[s.key] ?? s.key;
  const netChange = bridge ? bridge.steps[bridge.steps.length - 1].value : 0;
  const pinnedRank = ownerRows.find((r) => r.owner === ownerSel);

  return (
    <>
      <a className="skip" href="#main">Skip to the report</a>
      <header className="mast">
        <div className="shell">
          <div className="mast-top">
            <p className="kicker"><b>Rx Market Pulse</b> · a commercial-analytics case study by Mohammad Uzair Khan</p>
          </div>
          <h1>What Medicaid pays for prescription drugs, and why the bill keeps growing</h1>
          <p className="lede">
            Seven years of US Medicaid pharmacy data, {years[0]} to {years[years.length - 1]}, cleaned and joined to FDA records.
            Spend rose {pct(kpis(market, ALL).spend1 / kpis(market, ALL).spend0 - 1)} while prescriptions {Math.abs(kpis(market, ALL).rx1 / kpis(market, ALL).rx0 - 1) < 0.02 ? "stayed about level" : "changed"}.
            This page shows where the growth came from, who sells it, what happens when generics arrive, when patents end, and how far to trust any of it.
          </p>
          <ul className="scope" aria-label="Scope of the data">
            <li>Public CMS data, {(meta.rowsLoaded / 1e6).toFixed(1)}M rows</li>
            <li>US Medicaid only, before manufacturer rebates</li>
            <li>99.9% of spend matched to a manufacturer</li>
            <li><a href="#quality">How far to trust it</a></li>
            <li><a href="/ask">Ask the commercial analyst</a></li>
          </ul>
        </div>
      </header>

      <div className="bar">
        <div className="shell bar-in">
          <div className="field">
            <label htmlFor="area">Therapeutic area</label>
            <select id="area" value={area} onChange={(e) => setArea(e.target.value)}>
              <option value={ALL}>{ALL}</option>
              {meta.areas.map((a) => (<option key={a} value={a}>{a}</option>))}
            </select>
          </div>
          <nav aria-label="Sections">
            <a href="#growth">Growth</a><a href="#sellers">Companies</a><a href="#generics">Generics</a><a href="#protection">Patents</a><a href="#states">States</a><a href="#outlook">Outlook</a><a href="#quality">Quality</a>
          </nav>
          <ThemeToggle />
        </div>
      </div>

      <main id="main" className="shell">
        <dl className="ledger" aria-label={`Key numbers, ${scope}`}>
          <div>
            <dt className="led-label">Spend in {k.y1}, {scope.toLowerCase()}</dt>
            <dd style={{ margin: 0 }}>
              <p className="led-value led-hero">{usd(k.spend1)}</p>
              <p className="led-delta"><Delta from={k.spend0} to={k.spend1} good="none" /> since {k.y0} ({usd(k.spend0)})</p>
            </dd>
          </div>
          <div>
            <dt className="led-label">Prescriptions in {k.y1}</dt>
            <dd style={{ margin: 0 }}>
              <p className="led-value">{count(k.rx1)}</p>
              <p className="led-delta"><Delta from={k.rx0} to={k.rx1} good="none" /> since {k.y0}</p>
            </dd>
          </div>
          <div>
            <dt className="led-label">Spend per prescription</dt>
            <dd style={{ margin: 0 }}>
              <p className="led-value">{usd(k.perRx1, 0)}</p>
              <p className="led-delta"><Delta from={k.perRx0} to={k.perRx1} good="none" /> since {k.y0} ({usd(k.perRx0, 0)})</p>
            </dd>
          </div>
          <div>
            <dt className="led-label">Brand share in {k.y1}</dt>
            <dd style={{ margin: 0 }}>
              <p className="led-value">{pct(k.brandSpendShare1, 1)} <span style={{ fontSize: 15, fontWeight: 400, color: "var(--ink-3)" }}>of spend</span></p>
              <p className="led-delta">{pct(k.brandRxShare1, 1)} of prescriptions</p>
            </dd>
          </div>
        </dl>

        <Section
          id="market" num="1"
          title={<>Brands are {pct(k.brandRxShare1)} of prescriptions and {pct(k.brandSpendShare1)} of spend</>}
          dek={<>Generics fill most prescriptions at low cost; brand products carry most of the dollars. In {scope.toLowerCase()}, brand share of spend moved from {pct(k.brandSpendShare0, 1)} in {k.y0} to {pct(k.brandSpendShare1, 1)} in {k.y1}.</>}
        >
          <div className="pair">
            <SpendColumns years={years} s={series} scope={scope} />
            <ShareBars years={years} s={series} scope={scope} />
          </div>
        </Section>

        <Section
          id="growth" num="2"
          title={bridge && biggest ? <>Spend {netChange >= 0 ? "rose" : "fell"} {usd(Math.abs(netChange))} from {bridge.y0} to {bridge.y1}; the biggest driver was {driver(biggest)}</> : <>Why spend changed</>}
          dek="Spend changes for five reasons: more or fewer prescriptions, a shift between cheaper and costlier products (mix), a different spend per prescription for the same product, new products, and products that left. The bridge splits the change into those five, and they add up exactly."
        >
          <div className="pair growth">
            {bridge ? <Waterfall bridge={bridge} scope={scope} pairs={pvm.pairs} pair={pair} onPair={setPair} /> : <p className="note">No bridge for this selection.</p>}
            <AreaIncrease rows={areas} selected={area} onSelect={setArea} years={[years[0], years[years.length - 1]]} />
          </div>
        </Section>

        <Section
          id="sellers" num="3"
          title={<>{ownerRows[0]?.owner} leads {scope === "All therapeutic areas" ? "Medicaid" : scope.toLowerCase()} with {usd(ownerRows[0]?.spend1)}; {ownerSel} is {pinnedRank ? `number ${pinnedRank.rank}` : "outside the top group"}</>}
          dek="Spend is credited to each brand's owner today, so a product keeps one owner across all years even if it changed hands. This is an outside-in view from public data: it shows Medicaid pharmacy spend only, before rebates, and says nothing about any company's total sales."
        >
          <div className="pair wide">
            <OwnerBars rows={ownerRows} selected={ownerSel} onSelect={setOwner} years={[years[0], years[years.length - 1]]} scope={scope.toLowerCase()} />
            <ProductRows owner={ownerSel} items={ownerItems} years={years} />
          </div>
        </Section>

        <Section
          id="generics" num="4"
          title={m8 ? <>Two years after generics arrive, the median brand keeps {Math.round(m8.median)}% of its spend</> : <>What happens when generics arrive</>}
          dek="For each molecule where generics took over during the period, brand spend is followed quarter by quarter from the entry point. Some brands lose almost everything within a year; others hold on for two. The spread matters as much as the median."
        >
          <ErosionChart erosion={erosion} />
        </Section>

        <Section
          id="protection" num="5"
          title={near > 0 ? <>{usd(near)} of 2025 brand spend {area === ALL ? "" : `in ${area.toLowerCase()} `}sits on products whose core protection ends in 2026 to 2028</> : <>When protection ends</>}
          dek="The FDA Orange Book lists the patents and exclusivities that protect approved drugs. Grouping each brand's 2025 spend by the year its core protection ends shows where the next wave of generic competition could come from."
        >
          <ProtectionChart bars={bars} selected={protYear} onSelect={setProtYear} scope={scope.toLowerCase()} asOf={loe.asOf} groups={loe.segments[area]?.groups ?? {}} />
          {protYear && <ProtectedList loe={loe} area={area} year={protYear} />}
        </Section>

        <Section
          id="states" num="6"
          title={spread ? <>Spend per enrollee differs {spread.toFixed(1)}× between the highest and lowest state</> : <>States</>}
          dek="Per-enrollee spend takes out the size of a state's program. What remains reflects who is enrolled, how drugs are covered and billed, and which states changed how they report."
        >
          <TileMap rows={sRows} year={mapYear} lookback={lookback} scope={scope} years={years} onYear={setMapYear} />
          <StateCallout rows={sRows} year={mapYear} lookback={lookback} />
        </Section>

        <Section
          id="outlook" num="7"
          title={<>A range, not a prediction: {usd(lastFc.low, 0)} to {usd(lastFc.high, 0)} by {lastFc.year}</>}
          dek="Built from 28 quarters. Model selection ends in 2023; the separate 2024–2025 test shows how the frozen choice performs. Annual figures sum quarterly forecasts."
        >
          <ForecastChart data={fc} years={years} scope={scope} />
          <QuarterlyAudit data={fc.quarterly} />
        </Section>

        <Section
          id="quality" num="8"
          title={<>{quality.checks.length} checks run on every build: {counts.pass ?? 0} pass, {counts.warn ?? 0} are warnings worth knowing</>}
          dek="The pipeline downloads public files, keys every row to a product code, quarantines what cannot be keyed, harmonises names, and tests the result. These are the checks, in plain terms, with what each one touches."
        >
          <QualityTable quality={quality} />
          <p className="callout">
            <b>What this is not.</b> It is US Medicaid pharmacy data, not the whole market and not the UAE. Dollars are gross reimbursed amounts before rebates, so they overstate what manufacturers net. State rows leave out small cells the source blanks, about {Math.round(states.reconciliation[states.reconciliation.length - 1].gapPct)}% of national spend in {states.reconciliation[states.reconciliation.length - 1].year}.
            The method, not the geography, is the point: it carries to any claims or sales data keyed by product.
          </p>
        </Section>
      </main>

      <footer className="foot">
        <div className="shell">
          <div className="foot-grid">
            <div>
              <h2>Sources</h2>
              <ul>{meta.sources.map((s) => (<li key={s.name}><b>{s.name}</b>, {s.by}: {s.use}.</li>))}</ul>
            </div>
            <div>
              <h2>Method</h2>
              <ul>
                <li>DuckDB and Python build the warehouse; {data.quality.checks.length} data checks plus unit and data tests run on every build.</li>
                <li>Product names and codes are harmonised across four sources; unmatched spend is shown, never guessed.</li>
                <li>Orange Book as of {loe.asOf}. Built {meta.built}.</li>
              </ul>
            </div>
            <div>
              <h2>Take it further</h2>
              <ul>
                <li><a href="/downloads/Territory-Targeting-Model.xlsx" download>Excel territory-targeting model</a> (live formulas, 51 states).</li>
                <li><a href="/downloads/data-quality-scorecard.md" download>Data-quality scorecard</a> (text).</li>
                {repoUrl && <li><a href={repoUrl}>Code and tests on GitHub</a>.</li>}
              </ul>
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}
