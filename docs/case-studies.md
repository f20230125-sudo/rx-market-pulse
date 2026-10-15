# Case studies, in interview order

Each one: the question, what I did, what I found, what went wrong, and what I would do next. Numbers are from the built data and are re-checked by tests; if you rebuild, they may move by a decimal.

## 30-second pitch

I took seven years of public US Medicaid pharmacy claims, 36 million rows, and built what a commercial-analytics team builds on top of sales data: a clean product and manufacturer master, a market view with a price/volume/mix bridge, an Excel model that ranks territories, and a Power BI report. The part I would stress is not the charts. It is that the first look at the raw data showed three things that would have made every later number wrong, and the pipeline now catches each one.

## Project 3, Drug Data Harmonisation and Quality (the foundation)

**Question.** Can six sources that each name a drug differently be joined, with the loss measured instead of hidden?

**What I did.** Staged each source as published and typed it, nothing removed. Rows that cannot be keyed to a product go to a quarantine table with the reason. A product master is built per NDC (the 11-digit drug code) from the Medicaid product list, enriched from the FDA directory, then given a manufacturer parent, an ingredient and a therapeutic area. Nineteen checks run on every build and write a scorecard.

**What the first profile found.**
1. **About half of the state rows are blank** (51%: the source suppresses cells under 11 prescriptions), and those cells are counted in the national row. Summing the 51 states gives about 92% of the national total, never 100%. A naive state sum would understate the market by 6–7%.
2. **Product names are cut at exactly 10 characters** (`LEVOTHYROX`), so names cannot be the key.
3. **NDCs come in several layouts.** Padding the front of a hyphenated 10-digit code gives a wrong key; the hyphens say which segment to pad.
4. Puerto Rico appears from 2023 only, with no enrollment series, and quietly turned my "51 states" test into 52 until a data test caught it.

**Things I got wrong and fixed.**
- My therapeutic-area step first classified 81% of spend. A curated name list and a "same ingredient" step brought it to 97.8%. Reviewing the 330 largest products by hand then found about a dozen misclassifications (for example two multiple-sclerosis drugs landing in oncology through a CD20 rule). Each is now fixed by tightening a rule or by a short, documented override list, with tests.
- Two class patterns were too loose (a drug-interaction label matched a "virus" rule). I traced each bad result to the pattern that caused it and tightened the pattern, rather than patching names.
- A Python function applied to two million rows took minutes; applying it to the 1,300 distinct names took a second. The NDC conversion is in SQL for speed, with a parity test against the Python reference.

**Be ready for.** "How do you know the match is right?" Match rates are measured by spend at each step (exact pack 91.9%, same product 2.2%, unmatched 5.9%) and the unmatched share is shown, never guessed. "Why not fuzzy matching?" Exact keys first; fuzzy only where there is no key, and every fuzzy step would need its own error rate.

**Next.** Orange Book biologics are missing; the FDA Purple Book would fill the biologic patent gap. Add the Medicaid NADAC price series to separate price from mix at the NDC level.

## Project 2, Territory Targeting Model (Excel)

**Question.** Where should a commercial team focus first, and how much of a growth target should each state carry?

**What I did.** A workbook where every number on the Scorecard is a live formula. Four factors (market size, growth, spend per enrollee, brand share) become percentiles among the 51 states, a weighted score gives the rank and tier, and the national target is split in proportion to score times current spend.

**Choices to defend.**
- Percentiles, not raw values, so one huge state cannot swamp the rest.
- Growth uses a minimum prior-year spend, below which a state gets the median growth, because growth on a tiny base is noise.
- **The reporting-break flag.** California jumped 14.6% a year and New York 18.7%, but both moved their pharmacy benefit to state fee-for-service (California in 2022, New York in 2023), which changes what is reported without changing demand. A state is flagged when its fee-for-service share moves 25 points or any year swings 40%, and by default gets the median growth. It is a switch on the Inputs sheet, so a reviewer can turn it off and see the difference.

**How I knew it works.** I drove Excel itself through COM, set six input scenarios, read every state's result back, and compared it with a Python recalculation that shares no code with the workbook. First run failed: the percentile and rank formulas returned `#NAME?` because newer Excel functions need a prefix in the file format. The second run exposed a window calculation that used implicit intersection; I replaced it with `MAXIFS`. All six scenarios now match for all 51 states.

**Be ready for.** "Why percentile rank rather than z-scores?" Robust to outliers and easy to read. "What is not in it?" Patient counts, rebates, field-force cost; it ranks opportunity in reported Medicaid spend, nothing more.

## Project 1, Market Pulse (dashboard and Power BI)

**Question.** What drove Medicaid's drug bill up, who sells it, and what is coming?

**Findings.**
- Spend rose 60% to $116.9B (2019 to 2025) while prescriptions stayed level.
- 2022 to 2025 (+$16.8B): fewer prescriptions −$6.2B, shift to costlier products +$11.9B, spend per prescription for the same product +$2.7B, new products +$8.9B. The five pieces add up exactly.
- Brands are 14% of prescriptions and 89% of spend.
- Median brand keeps 19% of its spend two years after generics arrive; the spread is wide (one brand kept 3% after a year, another 76% after two).
- $13.1B of 2025 brand spend sits on products whose core protection ends in 2026 to 2028.
- Per-enrollee spend differs 3.5× between states; five states are flagged for reporting breaks.

**Merck (MSD), outside in.** Public data shows only Medicaid pharmacy spend, before rebates, so it says little about total sales. It does show product-level shape: Keytruda about $0.9B and growing 14% a year, Januvia $0.3B and falling about 10% a year with its core patent ending in November 2026, and Winrevair, new since 2024, at $0.2B. Orange Book dates are where protection ends, not when a generic launches.

**Forecast.** Seven annual points, so the method is simple and the backtest is the point: forecast each year from the years before it and compare. Recent growth continued beat "same as last year" (6.3% against 8.3% average miss), and the range comes from those misses.

**Power BI.** A star schema, 28 DAX measures and six pages, written as a Power BI project and checked by opening it in Power BI Desktop. Desktop rejected the first versions with clear errors (a measure used inside a filter, a measure named like a column); each was fixed in the generator. Walk through the measures in `powerbi/README.md` before the interview.

**Be ready for.** "Is this the whole market?" No: Medicaid only, gross of rebates, US. "Why does it matter for a UAE team?" It is the method: keying messy claims to products, harmonising names, separating real change from reporting change, and saying how much of the answer to trust. "What would you do with MSD's own data?" Replace the public sources with the internal ones and keep the checks.

## Things to verify yourself before relying on them

- Open the Power BI project once and click through every page so you have seen each visual and measure.
- The patent and exclusivity dates, and the company mapping, come from public files and my rules; spot-check two or three you will be asked about.
- The area classification is rule-based; open `data/ref/` to see exactly what each rule says.
