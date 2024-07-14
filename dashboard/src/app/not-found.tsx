import Link from "next/link";

export default function NotFound() {
  return (
    <main id="main" className="shell" style={{ padding: "96px 0" }}>
      <p className="kicker">
        <b>Rx Market Pulse</b>
      </p>
      <h1 style={{ fontFamily: "var(--serif)", fontSize: 40, margin: "16px 0 12px" }}>That page does not exist</h1>
      <p className="lede" style={{ fontSize: 18, color: "var(--ink-2)", maxWidth: "52ch" }}>
        The report is one page. Go back to it and use the section links at the top.
      </p>
      <p>
        <Link href="/">Back to the report</Link>
      </p>
    </main>
  );
}
