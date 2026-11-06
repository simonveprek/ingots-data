#!/usr/bin/env python3
"""Daily price history backfill from gold-api.com /history (free tier).

Free plan: 10 requests/hour with an API key (GOLD_API_KEY secret). We make one
request per symbol at most once a day, so 7 requests/day. Daily average prices
are merged into data/<SYMBOL>.json["daily"]; days collected live by collect.py
keep their own (closing) value only for today.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.gold-api.com"
DATA = Path(__file__).parent / "data"
STATE = DATA / "backfill-state.json"
START = int(datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp())
MIN_INTERVAL = 20 * 3600


def history(symbol, key):
    query = urllib.parse.urlencode({
        "symbol": symbol, "startTimestamp": START, "endTimestamp": int(time.time()),
        "groupBy": "day", "aggregation": "avg", "orderBy": "asc",
    })
    req = urllib.request.Request(f"{API}/history?{query}", headers={
        "x-api-key": key, "User-Agent": "ingots-data-collector/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def day_ts(value):
    return int(datetime.fromisoformat(str(value)[:10]).replace(tzinfo=timezone.utc).timestamp())


CRYPTO = {"BTC", "ETH"}


def clean(symbol, rows):
    """Drop weekends (metals don't trade) and one-day glitches that jump and return."""
    if symbol not in CRYPTO:
        rows = [r for r in rows if datetime.fromtimestamp(r[0], timezone.utc).weekday() < 5]
    out = []
    for i, row in enumerate(rows):
        if 0 < i < len(rows) - 1:
            prev, nxt = rows[i - 1][1], rows[i + 1][1]
            spike = abs(row[1] / prev - 1) > 0.06 and abs(row[1] / nxt - 1) > 0.06
            if spike and abs(nxt / prev - 1) < 0.03:
                continue
        out.append(row)
    return out


def main():
    key = os.environ.get("GOLD_API_KEY", "").strip()
    if not key:
        print("GOLD_API_KEY not set – skipping backfill")
        return
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if time.time() - state.get("lastRun", 0) < MIN_INTERVAL:
        print("backfill ran recently – skipping")
        return

    symbols = json.loads((DATA / "index.json").read_text())["symbols"]
    today = int(time.time()) // 86400 * 86400
    report = {}
    for symbol in symbols[:9]:  # stay under 10 requests/hour
        try:
            rows = history(symbol, key)
        except Exception as e:  # noqa: BLE001
            report[symbol] = f"error: {e}"
            continue
        merged = {}
        for row in rows:
            price = row.get("avg_price") or row.get("max_price") or row.get("price")
            stamp = row.get("day") or row.get("date")
            if price and stamp:
                merged[day_ts(stamp)] = round(float(price), 4)
        path = DATA / f"{symbol}.json"
        doc = json.loads(path.read_text()) if path.exists() else {"intraday": [], "daily": []}
        for ts, price in doc.get("daily", []):
            if ts >= today or ts not in merged:
                merged[ts] = price
        doc["daily"] = clean(symbol, [[ts, merged[ts]] for ts in sorted(merged)])
        path.write_text(json.dumps(doc, separators=(",", ":")))
        report[symbol] = f"{len(rows)} days"
        time.sleep(2)

    STATE.write_text(json.dumps({"lastRun": int(time.time()), "report": report}, indent=1))
    print(json.dumps(report))


if __name__ == "__main__":
    sys.exit(main())
