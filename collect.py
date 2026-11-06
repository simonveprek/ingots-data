#!/usr/bin/env python3
"""Ingots price collector.

Every run reads live spot prices from gold-api.com (free, commercial use
permitted – https://gold-api.com/terms §9) and appends them to
data/<SYMBOL>.json:

  intraday – every new quote for the last 35 days  [[unix, price], ...]
  daily    – last quote of each UTC day, kept forever [[unix_midnight, price], ...]

Prices are USD per the symbol's quote unit (troy ounce; copper HG per pound).
"""
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.gold-api.com"
DATA = Path(__file__).parent / "data"
INTRADAY_DAYS = 35
HEADERS = {"User-Agent": "ingots-data-collector/1.0 (+https://github.com/simonveprek/ingots-data)"}


def get(path):
    for attempt in range(3):
        try:
            req = urllib.request.Request(API + path, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                raise
            time.sleep(3)


def load(path):
    if path.exists():
        return json.loads(path.read_text())
    return {"intraday": [], "daily": []}


def update(symbol, name):
    quote = get(f"/price/{symbol}")
    price = round(float(quote["price"]), 4)
    ts = int(datetime.fromisoformat(quote["updatedAt"].replace("Z", "+00:00")).timestamp())

    path = DATA / f"{symbol}.json"
    doc = load(path)
    changed = False

    intraday = doc["intraday"]
    if not intraday or intraday[-1][0] < ts:
        intraday.append([ts, price])
        changed = True
    cutoff = int(time.time()) - INTRADAY_DAYS * 86400
    doc["intraday"] = [p for p in intraday if p[0] >= cutoff]

    day = ts - ts % 86400
    daily = doc["daily"]
    if daily and daily[-1][0] == day:
        if daily[-1][1] != price:
            daily[-1][1] = price
            changed = True
    elif not daily or daily[-1][0] < day:
        daily.append([day, price])
        changed = True

    doc.update({"symbol": symbol, "name": name, "currency": "USD", "updatedAt": ts})
    if changed:
        path.write_text(json.dumps(doc, separators=(",", ":")))
    return changed


def main():
    DATA.mkdir(exist_ok=True)
    symbols = get("/symbols")
    updated = []
    for s in symbols:
        try:
            if update(s["symbol"], s["name"]):
                updated.append(s["symbol"])
        except Exception as e:  # noqa: BLE001
            print(f"{s['symbol']}: {e}")
    index = {"symbols": [s["symbol"] for s in symbols], "generatedAt": int(time.time()),
             "source": "gold-api.com"}
    (DATA / "index.json").write_text(json.dumps(index, separators=(",", ":")))
    print("updated:", ", ".join(updated) or "nothing")


if __name__ == "__main__":
    main()
