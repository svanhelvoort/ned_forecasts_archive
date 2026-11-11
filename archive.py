"""Snapshot every NED.nl national forecast series into data/YYYY/MM/ned_YYYYMMDDTHHMMZ.csv.gz.

NED overwrites its forecasts, so each run preserves them as issued.
A failing or empty (type, activity) combo is logged and skipped; the run fails only
if nothing at all was retrieved.
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

# Forecast types from https://ned.nl/datacatalogus (rows with a forecast horizon).
TYPES = {
    1: "Wind", 2: "Solar", 17: "WindOffShore", 18: "FossilGasPower",
    19: "FossilHardCoal", 20: "Nuclear", 21: "WastePower", 25: "BiomassPower",
    26: "OtherPower", 27: "ElectricityMix", 35: "WKKTotal", 51: "WindOffshoreC",
    53: "IndustrialConsumersGasCombination",
    54: "IndustrialConsumersPowerGasCombination",
    55: "LocalDistributionCompaniesCombination", 59: "ElectricityLoad",
}
# NED activities: 1 providing, 2 consuming, 3 import, 4 export.
# Production types publish under 1, consumer/load types under 2; trying both is cheap
# (an empty combo costs one request) and keeps the list maintenance-free.
ACTIVITIES = {1: "providing", 2: "consuming"}
EXTRA_ACTIVITIES = {27: {3: "import", 4: "export"}}  # ElectricityMix import/export (1 d)

URL = "https://api.ned.nl/v1/utilizations"
GRANULARITY_HOUR = 5
RETRY_STATUS = (429, 500, 502, 503, 504)

now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
token = os.environ.get("NED_TOKEN")
if not token:
    sys.exit("NED_TOKEN env var is not set")
HDR = {"X-AUTH-TOKEN": token, "accept": "application/json"}
session = requests.Session()


def get(params):
    last = None
    for attempt in range(5):
        try:
            r = session.get(URL, params=params, headers=HDR, timeout=60)
        except requests.RequestException as e:  # network hiccup: retry
            last = e
        else:
            if r.status_code not in RETRY_STATUS:
                r.raise_for_status()
                data = r.json()
                # plain JSON is a list; tolerate JSON-LD if the API ever switches
                return data.get("hydra:member", []) if isinstance(data, dict) else data
            last = f"HTTP {r.status_code}"
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gave up after retries: {last}")


def fetch(type_id, activity):
    rows, page = [], 1
    while True:
        batch = get({
            "point": 0, "type": type_id, "granularity": GRANULARITY_HOUR,
            "granularitytimezone": 0, "classification": 1, "activity": activity,
            "page": page, "itemsPerPage": 200,
            "validfrom[after]": now.strftime("%Y-%m-%d"),
            "validfrom[strictly_before]": (now + timedelta(days=8)).strftime("%Y-%m-%d"),
        })
        time.sleep(0.5)
        if not batch:
            return rows
        rows += batch
        page += 1


frames, empty, failed = [], [], []
for tid, name in TYPES.items():
    for act, act_name in {**ACTIVITIES, **EXTRA_ACTIVITIES.get(tid, {})}.items():
        label = f"{tid} {name} ({act_name})"
        try:
            rows = fetch(tid, act)
        except Exception as e:
            failed.append(label)
            print(f"failed: {label}: {e}")
            continue
        if not rows:
            empty.append(label)
            continue
        d = pd.DataFrame(rows)
        d["type_name"] = name
        d["activity_name"] = act_name
        frames.append(d)
        print(f"ok: {label}: {len(rows)} rows")

got = {f["type_name"].iat[0] for f in frames}
missing = [f"{t} {n}" for t, n in TYPES.items() if n not in got]
print(f"empty combos: {empty}")
print(f"failed combos: {failed}")
print(f"types without any data: {missing}")

if not frames:
    sys.exit("no data from any type")

df = pd.concat(frames, ignore_index=True)
df["retrieved_utc"] = now.isoformat()
out = Path(f"data/{now:%Y/%m}/ned_{now:%Y%m%dT%H%M}Z.csv.gz")
out.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(out, index=False, compression="gzip")
print(f"saved {len(df)} rows to {out}")
