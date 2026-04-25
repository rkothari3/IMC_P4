# ROUND 3 — HYDROGEL_PACK Price Pattern (reference doc)

## Source
- 3 days of historical data: `data/round3/prices_round_3_day_{0,1,2}.csv` and `trades_round_3_day_{0,1,2}.csv`.
- Position limit: **200**. Tick = 1.

## Headline numbers (3-day pooled, mid_price)

| Metric | Value |
|---|---|
| Mean | **9990.8** |
| Range | 9891 – 10079 (spread 188 ticks) |
| Day 0 mean | 9990.96 |
| Day 1 mean | 9992.06 |
| Day 2 mean | 9989.40 |
| Spread (best ask − best bid), 92.7% of time | **16 ticks** |
| Trades / day | ~333 (mean size 4) |
| Best-bid + best-ask depth | ~25 shares total (12 + 13) |

The level is **stable** across days (drift ±2 ticks day-to-day) so a fixed anchor near 9990 is *defensible* — but it is **NOT the right anchor for intra-day decisions**.

## Behavior characteristics

### 1. Mean reversion is real but **very slow**
| Lag | Autocorr |
|---|---|
| 1 | 0.9977 |
| 10 | 0.99 |
| 100 | 0.8437 |
| 500 | 0.5123 |

**Half-life ≈ 1000–1200 ticks.** A price 1σ away from the mean takes ~50+ obs to halve the displacement. **Z-score signals at small thresholds (z=1.0) DO NOT mean a quick snapback.**

### 2. Within-day drift (NOT a stationary process intra-day)
- Q1 → Q4 drift of **+28 to +52 ticks** every day, consistently *upward*.
- Day-day mean shifts are tiny but **intra-day mean walks 25–50 ticks** in one direction.
- A fixed-mean assumption like `Z_FIXED_MEAN = 9990` makes the strategy **systematically short the morning and long the evening.**

### 3. Long sustained one-sided streaks
- Day 1: 2,301 consecutive ticks below mean (23% of day).
- Day 2: 2,096 consecutive ticks above mean (21% of day).
- These are NOT outliers — they are a regular regime feature.

### 4. Volatility clusters
- Rolling-100 std: avg **7**, range **2 – 18**. **8× vol clustering.**
- Fixed σ assumption breaks during volatility spikes — quotes become too tight or too wide.

### 5. Distribution slightly fat-tailed
- ±1σ contains 66.8% (Gaussian = 68%)
- ±2σ contains 95.5% (Gaussian = 95%)
- ±2σ excursions occur ~4.5% of obs and persist hundreds of ticks each.

### 6. Per-day PnL ceiling is HIGH (because spread is wide)
- Spread is 16 ticks 92%+ of the time. Each round-trip MM trade ≈ 4–8 ticks of edge if quoted inside.
- A simple inventory-managed MM with no directional bets should print steady PnL **without taking drawdowns**.
