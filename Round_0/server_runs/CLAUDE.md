# Server Runs Reference

Each subfolder (e.g., `Trader_N/`) contains the output from one live server submission to the IMC Prosperity platform.

---

## File Structure (per run)

Each run folder contains 3 files named with the submission ID (e.g., `63248`):

| File | Contents |
|------|----------|
| `<id>.py` | The exact trader code submitted for this run |
| `<id>.json` | Structured JSON result from the server |
| `<id>.log` | Raw log blob (same data as JSON but as a single-line JSON string) |

---

## JSON Schema (`<id>.json`)

```json
{
  "round": 0,             // Which round this was submitted for (0 = tutorial)
  "status": "FINISHED",   // Execution status
  "profit": 774.59,       // Final realized PnL (seashells)
  "positions": [          // Open positions at end of run (unrealized exposure)
    {"symbol": "TOMATOES", "quantity": 15},
    {"symbol": "EMERALDS", "quantity": -16},
    {"symbol": "XIRECS", "quantity": 85826}
  ],
  "activitiesLog": "...", // CSV-style string, semicolon-delimited (see below)
  "graphLog": "..."       // Time-series of aggregate portfolio PnL (see below)
}
```

### `activitiesLog` columns (semicolon-delimited CSV)

```
day ; timestamp ; product ;
bid_price_1 ; bid_volume_1 ; bid_price_2 ; bid_volume_2 ; bid_price_3 ; bid_volume_3 ;
ask_price_1 ; ask_volume_1 ; ask_price_2 ; ask_volume_2 ; ask_price_3 ; ask_volume_3 ;
mid_price ; profit_and_loss
```

- `day`: -1 = tutorial day, 0/1/2 = real round days
- `timestamp`: within-day tick (0 to ~999900, step 100)
- `bid_price_N / bid_volume_N`: top 3 levels of the buy-side order book
- `ask_price_N / ask_volume_N`: top 3 levels of the sell-side order book
- `mid_price`: (best_bid + best_ask) / 2
- `profit_and_loss`: **cumulative realized PnL** for this product up to this tick (unrealized not included)

### `graphLog` columns

```
timestamp ; value
```

- `value`: aggregate portfolio PnL (all products combined) at that timestamp
- This is what the leaderboard score is based on

---

## Run Log

| Folder | Submission ID | Round | Total PnL | Notes |
|--------|--------------|-------|-----------|-------|
| Trader_1 | 63248 | 0 (tutorial) | **774.59** | First run; EMERALDS + TOMATOES only |

---

## Systematic Analysis Framework

### 1. Product-level PnL split

Immediately decompose: which product made what. Identify best and worst contributors. Are any products net-negative?

### 2. Trade activity vs. opportunity

Count how many ticks each product was active (PnL changed) vs. total ticks. Low activity on a known-fair-value product = quoting is too aggressive or too conservative.

### 3. PnL curve shape (graphLog)

Plot it. Look for:
- **Monotone up** — strategy working, just needs scaling
- **Drawdown then recovery** — inventory risk; check position at the trough
- **Plateau** — hit position limit and got stuck
- **Late drawdown** — EOD position marks or bad fills near close

### 4. End-of-day position check

Open positions = unrealized risk carried home. For a pure MM strategy, target flat EOD. Large positions mean hedging/unwinding is broken.

### 5. Compare `profit` (JSON) vs. graphLog final value

`profit` includes unrealized MTM; graphLog is realized-only. Large divergence = big open position affecting score.

### 6. Overlay fills on mid-price

Parse `activitiesLog`, reconstruct fills from PnL deltas, and verify: buying near lows, selling near highs — not chasing.

### 7. Code diff vs. prior run

Every new Trader folder should have a diff of what changed. Attribute PnL delta to specific code changes, not luck.

---

## Trader_1 Detailed Breakdown

**Strategy**: Naive market-making — fixed fair value for EMERALDS (10000), mid-price estimate for TOMATOES. Take mispriced orders, post passive quotes around fair value.

| Product | Final PnL | Trade Count | Notes |
|---------|-----------|-------------|-------|
| EMERALDS | 300.00 | 29 ticks | Undertraded; wide market (9992/10008), posting at 9998/10002 |
| TOMATOES | 474.59 | 1935 ticks | Active; mid-price fair value, posting floor-1/ceil+1 |

**Open positions at run end** (unrealized risk):
- TOMATOES: +15 (long)
- EMERALDS: -16 (short)
- XIRECS: +85826 (large — conversion artifact, needs investigation)

**Mid-price ranges observed**:
- EMERALDS: 9996 – 10004 (very tight, oscillates around 10000)
- TOMATOES: 4974.5 – 5009.0 (wanders ~35 pts)

**Graphlog peak**: 751.69 | **Final**: 749.51

**Key issues**:
1. EMERALDS posting at 9998/10002 — market rarely crosses 10000, so almost no fills. Tighten to 9999/10001.
2. TOMATOES take threshold tied to exact mid — leaving edge on the table when spread is wide.
3. XIRECS large open position — conversion product not being managed.

