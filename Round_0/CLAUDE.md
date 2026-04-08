## What the two CSV files are

**prices_round_0_day_*.csv** — the order book snapshot every 100ms:
- Each row = one product at one timestamp
- bid_price_1/2/3 = the top bid levels (highest buy prices first) and their volumes
- ask_price_1/2/3 = the top ask levels (lowest sell prices first) and their volumes
- best bid = highest bid price (bid_price_1)
- best ask = lowest ask price (ask_price_1)
- mid_price = (bid_price_1 + ask_price_1) / 2 — a rough "fair value" estimate
- some rows have fewer than 3 levels; missing levels are blank fields (normal)

**trades_round_0_day_*.csv** — actual executed trades between bots:
- buyer/seller are empty (bot-to-bot, anonymous)
- Shows what prices trades actually happened at, and what quantity

## General Notes

- **Emeralds**: mid_price is often around 10000.0, but not always exactly 10000 at every snapshot. It can be 9996.0, 10004.0, etc. when best bid/ask shift (e.g., 9992/10000 or 10000/10008). Treat 10000 as a strong anchor, not a strict constant.
- **TOMATOES**: mid_price bounces around — 5000, 5002.5, 5001, 5001.5, 4999. It drifts. You need to track where it's going.

