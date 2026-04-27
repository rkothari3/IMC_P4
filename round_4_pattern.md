# ROUND 4 — Price & Counterparty Pattern Reference

**Source data:** `round_4_data/prices_round_4_day_{1,2,3}.csv` and `trades_round_4_day_{1,2,3}.csv`
**Days in sample:** 3 (labeled Day 1, 2, 3; Round 4 actual day = 0 TTE remaining at submission)
**TTE mapping:** Day 1 = 4d TTE, Day 2 = 3d TTE, Day 3 = 2d TTE
**Products:** HYDROGEL_PACK, VELVETFRUIT_EXTRACT, VEV_4000/4500/5000/5100/5200/5300/5400/5500/6000/6500
**Bots:** Mark 01, Mark 14, Mark 22, Mark 38, Mark 49, Mark 55, Mark 67
**Total trades in sample:** 4,281 across 3 days

---

## HYDROGEL_PACK

### Position limit: 200 | Tick: 1

### Headline numbers

| Metric          | Day 1        | Day 2        | Day 3        | 3-Day Pooled  |
|-----------------|-------------|-------------|-------------|---------------|
| Mean mid price  | 9,992.06    | 9,989.40    | 10,002.50   | ~9,994        |
| Std             | 37.61       | 31.62       | 32.95       | ~34           |
| Range           | 9908–10079  | 9891–10051  | 9923–10081  | 9891–10081    |
| Median spread   | 16 ticks    | 16 ticks    | 16 ticks    | **16 ticks**  |
| Trades / day    | ~341        | ~333        | ~348        | ~1,022 total  |

The spread is **16 ticks in 92.5% of observations**, the same as Round 3. A small minority of observations show 15 or 17 ticks, and a tiny cluster at 7–9 ticks (thin book moments).

### Autocorrelation of price *changes* (return-level ACF)

| Lag | Day 1   | Day 2   | Day 3   |
|-----|---------|---------|---------|
| 1   | -0.1240 | -0.1254 | -0.1233 |
| 2   | +0.011  | +0.022  | -0.014  |
| 5   | +0.004  | +0.005  | -0.001  |
| 10+ | ≈ 0    | ≈ 0     | ≈ 0     |

**Interpretation:** There is a statistically significant -0.12 lag-1 mean reversion in tick-by-tick changes. This reflects the market microstructure (prices bounce between the bid and ask side of the 16-tick spread). Beyond lag 2, changes are essentially white noise. The *level* autocorrelation is 0.998 at lag 1 (very persistent — macro trends are slow to revert).

### Intra-day drift

| Day | Slope (ticks/tick) | Total move      | R²    |
|-----|--------------------|-----------------|-------|
| 1   | +0.000084          | **+84.4 ticks** | 0.419 |
| 2   | +0.000051          | **+50.8 ticks** | 0.216 |
| 3   | -0.000074          | **-73.7 ticks** | 0.417 |

HG has a significant intra-day linear drift (R² 0.22–0.42), but the **direction is not consistent across days** (+up, +up, -down). The magnitude is 50–85 ticks per day. A fixed-mean assumption will be systematically wrong for 30–40% of the day.

### One-sided run lengths (consecutive ticks above/below mean)

| Day | Max run (ticks) | Median run |
|-----|----------------|------------|
| 1   | 2,301          | 3          |
| 2   | 2,096          | 3          |
| 3   | 2,051          | 3          |

The **median run is 3 ticks** (flips very fast) but maximum runs exceed 2,000 ticks (~20% of the day). These long one-sided runs correspond to the intra-day drift regime. The distribution is highly bimodal: most runs are short, but the day can include a single multi-hour excursion.

### Volatility

Rolling-100-tick std ranges from approximately 5 to 35 ticks. Volatility is clustered — calm periods near 7–10, bursts reaching 25–35. No consistent intra-day time-of-day pattern.

---

## VELVETFRUIT_EXTRACT

### Position limit: 200 | Tick: 1

### Headline numbers

| Metric         | Day 1       | Day 2       | Day 3       |
|----------------|-------------|-------------|-------------|
| Mean mid price | 5,248.39    | 5,255.39    | 5,239.16    |
| Std            | 14.61       | 16.99       | 18.60       |
| Range          | 5198–5283   | 5207–5300   | 5192–5300   |
| Median spread  | **5 ticks** | **5 ticks** | **5 ticks** |
| Trades / day   | ~460        | ~430        | ~490        |

Spread is 5 ticks in ~74% of observations, 6 ticks in ~18%, and 2–3 ticks in ~7% (the book is sometimes tighter).

### Autocorrelation of price *changes*

| Lag | Day 1   | Day 2   | Day 3   |
|-----|---------|---------|---------|
| 1   | -0.1693 | -0.1551 | -0.1560 |
| 2   | ≈ 0     | ≈ 0     | -0.033  |
| 5+  | ≈ 0     | ≈ 0     | ≈ 0     |

**Interpretation:** VEV has faster and stronger tick-level mean reversion than HG (-0.16 vs -0.12). Price movements beyond 1 tick are not forecastable. This pattern is identical to Round 3, confirming VEV is a tight, fast mean-reverting market. The **reversion half-life is within 5 ticks**.

### Intra-day drift

| Day | Slope (ticks/tick) | Total move    | R²    |
|-----|--------------------|---------------|-------|
| 1   | +0.000008          | +7.6 ticks    | 0.023 |
| 2   | -0.000007          | -7.1 ticks    | 0.015 |
| 3   | -0.000001          | -1.2 ticks    | 0.000 |

**VEV has essentially zero intra-day trend** (R² < 0.025, move < 8 ticks). The day-over-day level shift is ≤17 ticks. VEV is a stationary process intra-day: the mean is stable throughout the session.

### One-sided run lengths

| Day | Max run (ticks) | Median run |
|-----|----------------|------------|
| 1   | 1,692          | 3          |
| 2   | 2,861          | 3          |
| 3   | 2,083          | 3          |

Same qualitative pattern as HG: typical run is 3 ticks, but prolonged regimes occur.

### Multi-day level drift

- Day 1 → Day 2: +7.0 (spot rises)
- Day 2 → Day 3: -16.2 (spot falls)
- No directional bias confirmed over these 3 days.

---

## VEV VOUCHERS — All 10 Strikes

### Position limit: 300 per voucher | Calls on VELVETFRUIT_EXTRACT

### Spot and moneyness at each day

| Day | VEV Spot | VEV_4000 | VEV_4500 | VEV_5000 | VEV_5100 | VEV_5200 | VEV_5300 | VEV_5400 | VEV_5500 | VEV_6000 | VEV_6500 |
|-----|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| 1   | 5248     | ITM 1.31x | ITM 1.17x | ITM 1.05x | ITM 1.03x | ATM 1.01x | OTM 0.99x | OTM 0.97x | OTM 0.95x | Deep OTM | Deep OTM |
| 2   | 5255     | ITM 1.31x | ITM 1.17x | ITM 1.05x | ITM 1.03x | ATM 1.01x | OTM 0.99x | OTM 0.97x | OTM 0.95x | Deep OTM | Deep OTM |
| 3   | 5239     | ITM 1.31x | ITM 1.17x | ITM 1.05x | ITM 1.03x | ATM 1.00x | OTM 1.01x | OTM 0.97x | OTM 0.95x | Deep OTM | Deep OTM |

### Time-decay: mean mid price by day

| Voucher   | Day 1    | Day 2    | Day 3    | D1→D2      | D2→D3      |
|-----------|----------|----------|----------|------------|------------|
| VEV_4000  | 1248.41  | 1255.40  | 1239.16  | +0.6%      | -1.3%      |
| VEV_4500  | 748.41   | 755.40   | 739.16   | +0.9%      | -2.1%      |
| VEV_5000  | 253.26   | 258.54   | 241.63   | +2.1%      | **-6.5%**  |
| VEV_5100  | 164.98   | 167.33   | 150.28   | +1.4%      | **-10.2%** |
| VEV_5200  | 95.13    | 94.05    | 77.81    | -1.1%      | **-17.3%** |
| VEV_5300  | 46.91    | 44.48    | 32.14    | -5.2%      | **-27.7%** |
| VEV_5400  | 15.65    | 13.73    | 8.50     | -12.3%     | **-38.1%** |
| VEV_5500  | 6.57     | 5.29     | 2.26     | -19.4%     | **-57.3%** |
| VEV_6000  | 0.50     | 0.50     | 0.50     | 0%         | 0%         |
| VEV_6500  | 0.50     | 0.50     | 0.50     | 0%         | 0%         |

**Key observations:**
1. **Deep OTM (6000/6500):** Pinned at 0.50 bid price floor throughout all 3 days. No decay signal despite near-zero theoretical value.
2. **OTM (5400/5500):** Aggressive decay that accelerates exponentially as TTE drops. VEV_5500 loses 57% in the final day.
3. **Near ATM (5200/5300):** Moderate decay. VEV_5200 loses 17% on Day 3, VEV_5300 loses 28%.
4. **Weakly ITM (5000/5100):** Slower decay. VEV_5000 loses 6.5% on Day 3.
5. **Deep ITM (4000/4500):** Minimal decay. Price ≈ intrinsic + tiny time premium. VEV_4000 price = spot - 4000 + ~0.75 time value.

D1→D2 direction flip for ITM options (prices go UP slightly) is driven by spot moving from 5248→5255 (+7), not by time value expanding.

### Implied Volatility smile

Computed using Black-Scholes call, T = TTE/252. Valid strikes only (excluding deep ITM where intrinsic dominates and deep OTM pinned at floor):

| Voucher   | Day 1 IV | Day 2 IV | Day 3 IV | Trend       |
|-----------|----------|----------|----------|-------------|
| VEV_4500  | —        | 39.9%    | —        | (illiquid)  |
| VEV_5000  | 25.7%    | 27.6%    | 30.6%    | Rising      |
| VEV_5100  | 25.3%    | 26.8%    | 29.8%    | Rising      |
| VEV_5200  | 26.0%    | 27.5%    | 30.2%    | Rising      |
| VEV_5300  | 26.3%    | 28.0%    | 30.7%    | Rising      |
| VEV_5400  | 24.4%    | 26.1%    | 29.3%    | Rising      |
| VEV_5500  | 26.5%    | 28.5%    | 30.8%    | Rising      |

**Key observations:**
1. **Realized IV is ~25–31%**, rising as TTE decreases (backwardation / rising near-term IV).
2. The smile is relatively **flat across the 5000–5500 strike range** (24–27% band on Day 1, widening to 29–31% on Day 3).
3. IV rises ~4–5 percentage points per day as TTE decreases. This means the market prices in **higher vol for shorter-dated options** — the term structure is inverted.
4. VEV_6000 and VEV_6500 IVs are numerically unstable (pinned at 0.50, near-zero intrinsic) and should not be used.

### Mean reversion in voucher prices (ACF of changes)

| Voucher  | ACF Lag-1 | Strength    |
|----------|-----------|-------------|
| VEV_4000 | -0.2945   | Very strong |
| VEV_4500 | -0.2338   | Strong      |
| VEV_5000 | -0.1027   | Moderate    |
| VEV_5100 | -0.0972   | Moderate    |
| VEV_5200 | -0.1262   | Moderate    |
| VEV_5300 | -0.2143   | Strong      |
| VEV_5400 | -0.2495   | Very strong |
| VEV_5500 | -0.2402   | Very strong |
| VEV_6000 | NaN       | (pinned)    |
| VEV_6500 | NaN       | (pinned)    |

Mean reversion is **U-shaped**: strongest at the extremes (deep ITM and OTM), weakest near ATM. Near-ATM options have the widest relative bid-ask and are hardest to mean-revert.

### Bid-ask spread by voucher

| Voucher  | Dominant spread | Presence of 2-tick |
|----------|-----------------|--------------------|
| VEV_4000 | 21 ticks (75%)  | 10 ticks sometimes |
| VEV_5000 | (thin data)     | —                  |
| VEV_5200 | 2 ticks         | Tight throughout   |
| VEV_5300 | 2 ticks (89%)   | 1 tick (11%)       |
| VEV_5400 | 1 tick (70%)    | 2 ticks (30%)      |
| VEV_5500 | 1 tick (89%)    | 2 ticks (11%)      |
| VEV_6000 | 1 tick (ask-only)| No bid side       |
| VEV_6500 | 1 tick (ask-only)| No bid side       |

VEV_6000 and VEV_6500 have **no bid side** (bid_present=0%). They are ask-only markets — you can only buy them from bots, never sell.

### Voucher liquidity tier

| Tier         | Vouchers       | Market Trades (3-day) | Notes                            |
|--------------|----------------|-----------------------|----------------------------------|
| Active (MM)  | 4000           | 442                   | Tight symmetric market           |
| Illiquid     | 4500, 5000, 5100 | 3 each              | Almost no activity               |
| Moderate     | 5200, 5300     | 47, 164               | Some taker flow                  |
| Active       | 5400, 5500     | 276, 306              | High taker flow (Mark 01 dominant)|
| One-way      | 6000, 6500     | 317, 317              | Ask-only; all from Mark 22 → Mark 01 |

---

## COUNTERPARTY PROFILES

Seven bots are active: **Mark 01, 14, 22, 38, 49, 55, 67**. Each has a distinct and consistent role across all days.

### Overall trade counts (all days, all products)

| Bot     | Buys | Sells | Total | Net Qty     | Primary role                  |
|---------|------|-------|-------|-------------|-------------------------------|
| Mark 14 | 1127 | 1045  | 2172  | +302        | Multi-product market maker    |
| Mark 01 | 1599 | 244   | 1843  | +4678       | VEV spot MM + Options accumulator |
| Mark 22 | 42   | 1542  | 1584  | -5477       | Option seller (supply side)   |
| Mark 38 | 733  | 745   | 1478  | -14         | HG taker + VEV_4000 counterpart |
| Mark 55 | 598  | 600   | 1198  | -43         | VEV spot taker (symmetric)    |
| Mark 67 | 165  | 0     | 165   | +1510       | Sporadic large VEV buyer      |
| Mark 49 | 17   | 105   | 122   | -956        | Sporadic VEV seller           |

---

### Mark 01 — "The Options Accumulator"

**Products:** VELVETFRUIT_EXTRACT (260 buy / 244 sell), VEV_5200/5300/5400/5500/6000/6500 (buy only)

**VEV Spot behavior:**
- Buys VEV at avg **-2.60 ticks below mid** (posts bids inside the spread — market maker behavior)
- Sells VEV at avg **+2.69 ticks above mid** (posts offers inside the spread)
- Classic symmetric market maker: provides liquidity in VEV

**Options behavior — Critical pattern:**
- Is the **exclusive buyer** of OTM/Deep-OTM vouchers (5200–6500)
- **Zero sells** of any voucher (net accumulator)
- Always trades with Mark 22 as the counterparty
- Purchases are in sweeps every ~6,000–15,000 ticks
- Typical size: 2–5 contracts per trade (avg 3.5)

**VEV_6000 and VEV_6500 synchronized sweep:**
- Mark 01 buys VEV_6000 and VEV_6500 at **the exact same timestamp**, with the same quantity, 100% of the time (317/317 matching pairs)
- Trade price = 0.00 for both (Mark 22 sells at the floor)
- This is a systematic coordinated accumulation of lottery-ticket exposure, pairs executed atomically

**Timing regularity:**

| Voucher  | Median interval | Std        |
|----------|-----------------|------------|
| VEV_5400 | 7,900 ticks     | 10,628     |
| VEV_5500 | 6,900 ticks     | 9,099      |
| VEV_6000 | 6,450 ticks     | 8,567      |
| VEV_6500 | 6,450 ticks     | 8,567      |
| VEV (spot) | 4,100 ticks   | 5,781      |

High std/median ratio (~1.3) means the intervals are irregular, not on a fixed clock.

---

### Mark 14 — "The Multi-Market Maker"

**Products:** HYDROGEL_PACK, VELVETFRUIT_EXTRACT, VEV_4000, VEV_5200/5300/5400/5500

**HG behavior:**
- Buys at avg **-7.98 ticks below mid** (at the bid, inside the 16-tick spread)
- Sells at avg **+7.94 ticks above mid** (at the ask)
- **Classic symmetric market maker** in HG: posts 2-sided quotes, earns the spread
- 496 buys / 507 sells — nearly flat inventory management

**VEV behavior:**
- Buys at -2.43 / sells at +2.46 (symmetric, inside the 5-tick spread)
- 316 buys / 331 sells

**VEV_4000 behavior:**
- Buys at -10.47 / sells at +10.37 (symmetric; the VEV_4000 spread is ~21 ticks, so Mark 14 earns half)
- 232 buys / 207 sells

**Options taker behavior (secondary):**
- Buys OTM vouchers (5200–5500) from Mark 22, in smaller quantities than Mark 01
- Average size: 3.3 per trade
- No sells — also an accumulator, but secondary to Mark 01

**Trade frequency:** Median interval 2,800 ticks — the **most active market maker**.

---

### Mark 22 — "The Option Seller / Spread Provider"

**Products:** All vouchers (as seller), minimal HG and VEV spot

**Options behavior — Critical pattern:**
- **Never buys any voucher.** 100% seller of every voucher type.
- Sells VEV_5200 (46), VEV_5300 (163), VEV_5400 (276), VEV_5500 (306), VEV_6000 (317), VEV_6500 (317)
- Also sells VEV_4500, VEV_5000, VEV_5100 in tiny amounts (via Mark 38 counterpart)

**Sell prices vs mid:**
- VEV_5200: sells at **-0.93 below mid** (hits the bid — below fair value)
- VEV_5300: sells at **-0.87 below mid**
- VEV_5400: sells at **-0.59 below mid**
- VEV_5500: sells at **-0.53 below mid**
- VEV_6000: sells at **-0.50 below mid** (at the floor price = 0.00)
- VEV_6500: sells at **-0.50 below mid** (at the floor price = 0.00)

Mark 22 consistently sells options at **below the mid price** (at the bid side or at the floor). It is the systematic supply of options to Mark 01 and Mark 14.

**VEV spot:** Minor activity only (25 buy / 101 sell). Sells at +0.71 above mid — takes the offer side of VEV spot occasionally.

**Timing:** Median 7,900 ticks between trades — slower than Mark 14, only trades when Mark 01/14 demand options.

---

### Mark 38 — "The HG Flow / VEV_4000 Counterpart"

**Products:** HYDROGEL_PACK (dominant), VEV_4000 (secondary), tiny VEV_4500/5000/5100

**HG behavior:**
- Buys at avg **+7.87 ticks ABOVE mid** (lifting the offer — aggressive taker)
- Sells at avg **-7.90 ticks BELOW mid** (hitting the bid — aggressive taker)
- **NOT a market maker**: Mark 38 crosses the spread in both directions. It generates the order flow that Mark 14 extracts from.
- 515 buys / 507 sells — roughly flat inventory

**Key structural insight:** Mark 14 posts bids and asks; Mark 38 hits them. The HG market is essentially a bilateral duel: **Mark 14 (maker) vs Mark 38 (taker)**, with 1003 of the 1022 total HG trades between just these two.

**VEV_4000 behavior:**
- Same pattern: buys at +10.32 above mid, sells at -10.44 below mid
- Always trades against Mark 14

**VEV_4500/5000/5100:** Tiny exposure (2–3 trades each), all with Mark 22 as counterpart. These appear to be residual/testing trades.

**Timing:** Median 2,600 ticks — second most frequent (closely follows Mark 14's rhythm).

---

### Mark 55 — "The VEV Taker"

**Products:** VELVETFRUIT_EXTRACT exclusively (598 buy / 600 sell)

**Behavior:**
- Buys at avg **+2.49 ticks ABOVE mid** (lifts the offer — taker)
- Sells at avg **-2.47 ticks BELOW mid** (hits the bid — taker)
- Near-zero net position (+43 qty over 3 days)
- Symmetric in both directions — neither long nor short biased
- Trades with Mark 14 (331+316 trades), Mark 01 (260+244), and occasionally Mark 22/49

**Key structural insight:** Mark 55 is the flow that drives VEV market makers (Mark 14, Mark 01) to earn the spread. Mark 55 crosses the spread consistently. Combined with Mark 38's role in HG, the pattern is clear:

- **HG:** Mark 14 makes, Mark 38 takes
- **VEV:** Mark 14 + Mark 01 make, Mark 55 takes

**Timing:** Median 1,800 ticks — the **fastest** bot, drives most VEV tick activity.

---

### Mark 67 — "The Sporadic Large VEV Buyer"

**Products:** VELVETFRUIT_EXTRACT only (165 buys, zero sells)

**Behavior:**
- Always a buyer, never a seller in any product
- Avg **+0.80 ticks above mid** (slight taker — lifts near the offer)
- Large block size: 165 trades with 1,510 total qty = **avg 9.15 contracts/trade** (compare: Mark 55 averages 5.4)
- Trades against Mark 49 (89 trades), Mark 22 (75 trades)
- Timing: Median 13,300 tick interval — very slow, infrequent

**Net position: +1,510 (massive net long VEV over 3 days)**

Mark 67 accumulates VEV spot at a slow pace in large blocks. It appears to be a directional buyer, not a market maker. No mechanism to unwind is visible in the data.

---

### Mark 49 — "The Sporadic VEV Seller"

**Products:** VELVETFRUIT_EXTRACT only (17 buy / 105 sell)

**Behavior:**
- Predominantly a seller (105 vs 17)
- Sells at avg **+0.67 above mid** (above fair value — selling at the ask side)
- Buys at avg **-1.50 below mid** (at the bid)
- Small trades: avg ~6 contracts
- Trades against Mark 22 (12), Mark 55 (5), Mark 67 (89 as counterpart — sells to Mark 67)
- Timing: Median 16,700 ticks — the slowest, most infrequent bot

**Net position: -956 (substantial net short over 3 days)**

Mark 49 is the primary supply counterpart for Mark 67. Together, Mark 67 (buyer) and Mark 49 (seller) form a slow bilateral flow in VEV.

---

## STRUCTURAL SUMMARY

### Market architecture by product

| Product        | Maker(s)              | Taker(s)          | One-sided / Inactive    |
|----------------|----------------------|-------------------|-------------------------|
| HYDROGEL_PACK  | Mark 14               | Mark 38           | Mark 22 (tiny)          |
| VELVETFRUIT_EXTRACT | Mark 14, Mark 01 | Mark 55           | Mark 67, Mark 49 (sporadic) |
| VEV_4000       | Mark 14               | Mark 38           |                         |
| VEV_5200–5500  | (Mark 22 offers only) | Mark 01 (buyer), Mark 14 (secondary) |        |
| VEV_6000–6500  | Mark 22 (offers only) | Mark 01 (buyer)   | **No bid side exists**  |
| VEV_4500/5000/5100 | Mark 22 (offers) | Mark 38 (occasional) | Essentially illiquid |

### Critical asymmetries

1. **VEV_6000 and VEV_6500 have no bid side.** Any position you take, you can only exit at expiry or at 0. Mark 01 buys them at 0 and holds.

2. **Mark 22 is the universal option seller.** It sells every voucher, never buys. It is the counterparty of last resort for OTM options demand.

3. **The HG market is a duopoly** (Mark 14 vs Mark 38 = 98% of all trades). All other bots are spectators.

4. **Mark 01 has a massive accumulated long in OTM/Deep-OTM vouchers.** Across 3 days it bought 1,599 voucher positions and sold zero. This is a net directional bet on VEV spot rising.

5. **Mark 55 is the sole VEV flow generator** — its high-frequency crossing of the 5-tick spread is what funds the market makers. The entire VEV MM ecosystem exists because of Mark 55's order flow.

6. **Mark 67 accumulates VEV spot at a net +1,510 qty** over 3 days. It buys from Mark 49 at large block sizes. Combined with Mark 01's options accumulation, there is structural directional demand pressure on VEV.

---

## APPENDIX — Plots Generated

All plots saved to `round_4_data/plots/`:

| File                         | Contents                                          |
|------------------------------|---------------------------------------------------|
| `hg_full_analysis.png`       | HG mid price, spread dist, vol clustering, ACF    |
| `vev_full_analysis.png`      | VEV mid price, spread dist, vol clustering, ACF   |
| `vouchers_mid_price.png`     | All 10 voucher mid prices per day                 |
| `voucher_iv_smile.png`       | IV smile by strike, 3 panels (Day 1/2/3)         |
| `voucher_decay.png`          | Day-over-day mean price bar chart per strike      |
| `counterparty_heatmap.png`   | Bot trade counts + per-product activity           |
| `voucher_mr_spread.png`      | ACF lag-1 per voucher + median spread              |
| `voucher_beta.png`           | Voucher ΔPrice vs ΔVEV spot regression per strike |
| `r4_overview.png`            | Combined overview: all products + bot net qty     |
