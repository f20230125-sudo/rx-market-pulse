import type { ForecastT } from "@/lib/schema";
import { usd } from "@/lib/format";

export function QuarterlyAudit({
  data,
}: {
  data: ForecastT[string]["quarterly"];
}) {
  const selected = data.methods.find((m) => m.chosen)!;
  const baseline = data.methods.find((m) => m.method === "seasonal-naive")!;
  const fmt = (v: number | null) =>
    v === null ? "Unavailable" : `${v.toFixed(2)}%`;
  return (
    <div className="stack">
      <p className="note">
        Model choice used rolling 2022–2023 validation only and was frozen
        before the 2024–2025 test. Test WAPE: {fmt(selected.test.wape)} for the
        selected method; {fmt(baseline.test.wape)} for same quarter last year.
        {(selected.test.wape ?? Infinity) > (baseline.test.wape ?? Infinity) &&
          " The selected method lost to the baseline on the test period."}{" "}
        WAPE weights absolute errors by actual spend. The {data.holdoutCases}{" "}
        cases overlap in time and are not independent observations.
      </p>
      <div className="tbl-wrap">
        <table className="tbl">
          <caption>Validation and independent test</caption>
          <thead>
            <tr>
              <th>Method</th>
              <th>Validation WAPE</th>
              <th>Test WAPE</th>
              <th>Selected before test</th>
            </tr>
          </thead>
          <tbody>
            {data.methods.map((m) => (
              <tr key={m.method}>
                <th>{m.method}</th>
                <td>{fmt(m.selection.wape)}</td>
                <td>{fmt(m.test.wape)}</td>
                <td>{m.chosen ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details>
        <summary>
          Quarterly observations, forecasts and error by horizon
        </summary>
        <div className="tbl-wrap">
          <table className="tbl">
            <caption>28 actual quarters and eight future quarters</caption>
            <thead>
              <tr>
                <th>Quarter</th>
                <th>Kind</th>
                <th>Spend</th>
                <th>Empirical low</th>
                <th>Empirical high</th>
              </tr>
            </thead>
            <tbody>
              {data.actual.map((r) => (
                <tr key={r.period}>
                  <th>{r.period}</th>
                  <td>Actual</td>
                  <td>{usd(r.spend)}</td>
                  <td>—</td>
                  <td>—</td>
                </tr>
              ))}
              {data.forecast.map((r) => (
                <tr key={r.period}>
                  <th>{r.period}</th>
                  <td>Forecast</td>
                  <td>{usd(r.spend)}</td>
                  <td>{usd(r.low)}</td>
                  <td>{usd(r.high)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <table className="tbl">
          <caption>Selected method on test data, by forecast horizon</caption>
          <thead>
            <tr>
              <th>Quarters ahead</th>
              <th>Cases</th>
              <th>WAPE</th>
            </tr>
          </thead>
          <tbody>
            {selected.byHorizon.map((r) => (
              <tr key={r.horizon}>
                <th>{r.horizon}</th>
                <td>{r.n}</td>
                <td>{fmt(r.wape)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
      <p className="note">
        {data.bandDescription} Pre-test error bands covered{" "}
        {(100 * data.holdoutCoverage).toFixed(0)}% of test cases; this is
        observed coverage, not a promise about future quarters.
      </p>
    </div>
  );
}
