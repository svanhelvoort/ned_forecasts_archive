Created with Claude Opus 5.5. First run on 2026-11-11 (or as they call it in Oeteldonk: Elfde van de Elfde)

# NED forecast archive

NED.nl overwrites its forecasts. This repo snapshots every national (NL) forecast
series from the NED API every 6 hours via GitHub Actions and commits each snapshot,
so forecasts are preserved as issued.

## Output
`data/YYYY/MM/ned_YYYYMMDDTHHMMZ.csv.gz`, one file per run. Columns are the raw API
fields plus `type_name`, `activity_name` (providing / consuming / import / export) and
`retrieved_utc` (pull time, i.e. the forecast issue time as seen by this archive).

Query: `point=0` (NL), `classification=1` (forecast), `granularity=5` (hourly),
`granularitytimezone=0` (UTC), window today to +8 days, paginated until an empty page.

## Types
From https://ned.nl/datacatalogus (rows with a forecast horizon):
1 Wind, 2 Solar, 17 WindOffShore, 18 FossilGasPower, 19 FossilHardCoal, 20 Nuclear,
21 WastePower, 25 BiomassPower, 26 OtherPower, 27 ElectricityMix, 35 WKK Total,
51 WindOffshoreC, 53/54/55 gas consumer combinations, 59 ElectricityLoad.

Each type is tried with activity 1 (providing) and 2 (consuming); ElectricityMix also
with 3 (import) and 4 (export). Combos that return nothing are logged and skipped.
To add a type, add it to `TYPES` in `archive.py`.

## Setup
1. Get a free API key at ned.nl.
2. Push this repo to GitHub (keep it private unless NED's licence allows redistribution).
3. Settings → Secrets and variables → Actions → add `NED_TOKEN`.
4. Actions → archive → Run workflow; check the log and the new file under `data/`.

Local run: `NED_TOKEN=... python archive.py`.

## Maintenance
- Failed runs trigger GitHub's default failure email. The job fails only if no type
  returned data (typical cause: expired token or API change).
- GitHub disables scheduled workflows after 60 days of repo inactivity; the regular
  snapshot commits prevent this.
