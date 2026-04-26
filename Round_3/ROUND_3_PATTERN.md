# ROUND 3 — Price Pattern Reference Doc

---

## HYDROGEL_PACK

### Source
- 3 days of historical data: `data/round3/prices_round_3_day_{0,1,2}.csv` and `trades_round_3_day_{0,1,2}.csv`.
- Position limit: **200**. Tick = 1.

### Headline numbers (3-day pooled, mid_price)

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

### Behavior characteristics

#### 1. Mean reversion is real but **very slow**
| Lag | Autocorr |
|---|---|
| 1 | 0.9977 |
| 10 | 0.99 |
| 100 | 0.8437 |
| 500 | 0.5123 |

**Half-life ≈ 1000–1200 ticks.** A price 1σ away from the mean takes ~50+ obs to halve the displacement. **Z-score signals at small thresholds (z=1.0) DO NOT mean a quick snapback.**

#### 2. Within-day drift (NOT a stationary process intra-day)
- Q1 → Q4 drift of **+28 to +52 ticks** every day, consistently *upward*.
- Day-day mean shifts are tiny but **intra-day mean walks 25–50 ticks** in one direction.
- A fixed-mean assumption like `Z_FIXED_MEAN = 9990` makes the strategy **systematically short the morning and long the evening.**

#### 3. Long sustained one-sided streaks
- Day 1: 2,301 consecutive ticks below mean (23% of day).
- Day 2: 2,096 consecutive ticks above mean (21% of day).
- These are NOT outliers — they are a regular regime feature.

#### 4. Volatility clusters
- Rolling-100 std: avg **7**, range **2 – 18**. **8× vol clustering.**
- Fixed σ assumption breaks during volatility spikes — quotes become too tight or too wide.

#### 5. Distribution slightly fat-tailed
- ±1σ contains 66.8% (Gaussian = 68%)
- ±2σ contains 95.5% (Gaussian = 95%)
- ±2σ excursions occur ~4.5% of obs and persist hundreds of ticks each.

#### 6. Per-day PnL ceiling is HIGH (because spread is wide)
- Spread is 16 ticks 92%+ of the time. Each round-trip MM trade ≈ 4–8 ticks of edge if quoted inside.
- A simple inventory-managed MM with no directional bets should print steady PnL **without taking drawdowns**.

---

## VELVETFRUIT_EXTRACT (VEV) — Underlying

### Source
- Same 3-day historical files. Position limit: **200**. Tick = 1.
- TTE context: Day 0 = TTE 8d, Day 1 = 7d, Day 2 = 6d. **Round 3 actual = TTE 5d.**

### Headline numbers

| Metric | Value |
|---|---|
| Mean (3-day pooled) | **~5250** |
| Range | 5198 – 5300 (102 ticks, 1.93%) |
| Day 0 mean ± std | 5246.51 ± 13.68 |
| Day 1 mean ± std | 5248.39 ± 14.61 |
| Day 2 mean ± std | 5255.39 ± 16.99 |
| Spread (best ask − best bid) | **5 ticks** (median = exactly 5, 95%+ of time) |
| Trades / day | ~450, mean size ~6 |

### Behavior characteristics

#### 1. Mean reversion is FAST (unlike HYDROGEL_PACK)
| Lag | Autocorr |
|---|---|
| 1 | **-0.15 to -0.17** (negative — mean-reverting) |
| 5–20 | Near zero |

Reversion happens within **5–10 ticks**. This is very different from HYDROGEL_PACK's slow drift. Small price spikes reverse quickly.

#### 2. Very low volatility, no clustering
- Realized vol: ~0.02% per tick.
- Max single move: ~50 bps. Stable across all 3 days.
- No volatility regimes — this is a calm, tight market.

#### 3. Slight multi-day upward drift
- +8.88 total over 3 days (+0.17%). Not meaningful for intra-day strategy but worth noting.
- Intra-day linear trends are statistically significant (p<0.0001) but extremely weak (R² < 0.09).

---

## VELVETFRUIT_EXTRACT_VOUCHER — All 10 Strikes

### Strike overview (given VEV ≈ 5250)

| Voucher | Strike | Moneyness (S/K) | Region | Day 0 Price | Day 2 Price | 2-day Δ |
|---|---|---|---|---|---|---|
| VEV_4000 | 4000 | 1.31 | Deep ITM | 1246.52 | 1255.40 | +0.71% |
| VEV_4500 | 4500 | 1.17 | Deep ITM | 746.52 | 755.40 | +1.19% |
| VEV_5000 | 5000 | 1.05 | Weakly ITM | 253.26 | 258.54 | +2.09% |
| VEV_5100 | 5100 | 1.03 | Weakly ITM | 168.11 | 167.33 | -0.47% |
| VEV_5200 | 5200 | 1.01 | Near ATM | 97.47 | 94.05 | -3.51% |
| VEV_5300 | 5300 | 0.99 | Slightly OTM | 48.89 | 44.48 | -9.03% |
| VEV_5400 | 5400 | 0.97 | OTM | 18.47 | 13.73 | **-25.6%** |
| VEV_5500 | 5500 | 0.95 | OTM | 8.06 | 5.29 | **-34.3%** |
| VEV_6000 | 6000 | 0.87 | Deep OTM | 0.50 | 0.50 | 0% (pinned) |
| VEV_6500 | 6500 | 0.81 | Deep OTM | 0.50 | 0.50 | 0% (pinned) |

### Liquidity by region

| Region | Vouchers | Trades (3-day) | Notes |
|---|---|---|---|
| Deep ITM | 4000 | 464 | Very active market-making bot |
| Deep ITM | 4500 | 1 | Essentially illiquid |
| Near ATM | 5000, 5100 | 1 each | Dead zone — no market |
| Near ATM | 5200 | 18 | Very thin |
| OTM | 5300 | 121 | Moderate |
| OTM | 5400 | 225 | Active |
| OTM | 5500 | 267 | Active |
| Deep OTM | 6000, 6500 | 284 each | Bot pairs; one-way market (asks only, no bids) |

**Critical:** Near-ATM region (5000–5200) is a **liquidity desert**. The active trading is at the extremes.

### Time decay pattern

OTM options show dramatic and accelerating theta decay:
- VEV_5400: -15.2% (D0→D1), -12.3% (D1→D2) = **-25.6% total**
- VEV_5500: -18.5% (D0→D1), -19.4% (D1→D2) = **-34.3% total**

Deep OTM (6000, 6500) are **pinned at 0.50** — this appears to be a bid-ask floor effect. They show zero decay despite being far OTM.

For the actual Round 3 (TTE=5d), decay will be **more aggressive** than Day 2 historical.

### Mean reversion in vouchers

Strong negative lag-1 autocorrelation at both extremes:

| Voucher | ACF Lag-1 | Strength |
|---|---|---|
| VEV_4000 | -0.280 | Very strong |
| VEV_5400 | -0.270 | Very strong |
| VEV_5500 | -0.260 | Very strong |
| VEV_5300 | -0.215 | Strong |
| VEV_5200 | -0.146 | Moderate |
| VEV_5000/5100 | -0.09 to -0.10 | Weak |

ATM = weakest mean reversion. ITM and OTM = strongest. This matches Frankfurt Hedgehogs' findings on Volcanic Rock Vouchers.

### Implied Volatility Smile

**Reverse skew pattern** (unusual — high IV at both extremes, low in the middle):

| Voucher | IV (Day 0) | IV (Day 2) | Trend |
|---|---|---|---|
| VEV_4000 | 51.0% | 56.9% | Rising |
| VEV_4500 | 29.5% | 34.4% | Rising |
| VEV_5000 | ~22.7% | ~23.7% | Flat |
| VEV_5200 | ~22.7% | ~23.2% | Flat |
| VEV_5300 | ~22.2% | ~24.2% | Flat |
| VEV_5400 | ~22.2% | ~22.1% | **Flat** (only exception) |
| VEV_6000 | 35.5% | 40.5% | Rising |
| VEV_6500 | 53.7% | 61.6% | Rising |

IV minimum is at ATM (~22–24%). IV rises sharply at both extremes. **Rising IV term structure** (as TTE decreases, IV goes up) — unusual, partly explains why OTM decay looks smaller than raw theta would predict.

### Bot signatures

- **VEV_6000/6500:** Coordinated bot — 284 trades each with identical timestamps. Systematic ~3.5s interval. **Interpretation:** hedging/arb bot executing symmetric pairs.
- **VEV_4000:** Market-making bot with 1/2/3 contract sizing. 464 trades.
- **Deep OTM asks-only:** VEV_6000/6500 have no bid side. Any long you take, you can only unwind at 0 or wait for expiry.

### Correlation to VEV spot

| Voucher | Beta to VEV | R² |
|---|---|---|
| VEV_4000 | 3.13× | 0.354 |
| VEV_4500 | 4.64× | 0.355 |
| VEV_5000 | 13.49× | 0.567 |

Leverage increases as moneyness decreases. VEV_5000 has highest sensitivity (13.5× beta, 57% R²).
