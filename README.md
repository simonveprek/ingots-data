# ingots-data

Price history for the Ingots iOS app.

A GitHub Action reads live spot prices from [gold-api.com](https://gold-api.com)
every 15 minutes and stores them in `data/<SYMBOL>.json`:

- `intraday` – every new quote for the last 35 days, `[unix_seconds, price]`
- `daily` – last quote of each UTC day, kept forever

Prices are in USD per troy ounce (copper `HG` per pound).
Source: gold-api.com (commercial use permitted by its terms, §9).
