# Final Iteration: ~1500 → 2600+ Strategy Push

## Current Performance (Trader_3 / 64681.json)
| Metric | Value |
|---|---|
| Total PnL | 1,381 |
| EMERALDS PnL | 599 |
| TOMATOES PnL | 782 |
| Max drawdown | 144 |
| Final pos | EM: -12, TM: +6 |
| Pos limit violations (EMERALDS) | **35 ticks (1.75%)** |

---

## A) Plain-English Diagnosis

Your bot is fundamentally sound — it nearly doubled PnL from Trader_1. But there are two concrete problems bleeding PnL right now, and two untapped improvements that can add significant alpha.

**Problem 1: EMERALDS position limit violations are killing entire ticks of orders.**
The log shows 35 ticks where ALL EMERALDS orders were cancelled because aggregate order quantity would exceed the 80-unit limit if fully filled. This is your flattening logic interacting badly with passive quotes. When your bot sends a flatten order + take orders + passive quotes, the *total* buy or sell quantity can exceed the limit. Every cancelled tick = lost passive fill opportunity = lost PnL.

*Simple explanation:* Imagine you're allowed to carry 80 apples. You're holding 13 already. Your bot tries to buy 5 to flatten, take 10 cheap apples from the market, AND post a standing order to buy 62 more. That's 5+10+62 = 77 buy apples, which if all fill means you'd hold 13+77 = 90. Over the limit → ALL orders cancelled, including the profitable ones.

**Problem 2: EMERALDS trades are very infrequent — only 17 fills over 2000 ticks.**
That's one trade every ~118 ticks. With EDGE=7, you earn ~7 per fill on each side, but you're only doing ~38 buy units and ~50 sell units total. The main bottleneck is fill rate — bot market orders that trigger fills against your passive quotes happen rarely. The fix is to be slightly more aggressive on taking when it doesn't cost much.

**Problem 3: EMERALDS PnL plateaus in the second half.**
First half PnL: 520. Second half: only 79 more. Your position gets stuck (at -14 for long stretches) and you can't trade. The skew + flatten logic isn't recovering fast enough.

**TOMATOES is healthy** — 64 fills, steady PnL accumulation, reasonable positions. Main improvement is position-aware taking and possibly slightly tighter edge to capture more fills.

---

## B) Unimplemented Tasks from Old Plan — Assessment

| Task | Status | Still Worth Doing? | Expected Impact |
|---|---|---|---|
| Task 8: EMA Fair Value (traderData) | Not implemented | **NO** — low priority. Weighted mid is already good. EMA adds lag for marginal improvement on this tutorial data. Skip. | ~0-2% |
| Task 9: Position-aware taking | Not implemented | **YES — HIGH PRIORITY.** When you're short 14 EMERALDS, buying at 10000 (break-even) to flatten is better than staying stuck. Same for TOMATOES. | +10-20% |
| Task 7: Regime filter | Implemented ✅ | Already in. Working well. No change needed. | N/A |

---

## C) Top 7 Changes — Ranked by Expected PnL Impact

### 1. Fix EMERALDS Position Limit Bug [CRITICAL — ~+200 PnL]
**What's happening:** Your flatten logic adds orders to the list BEFORE the take loop, but position tracking uses a local `pos` variable that doesn't account for whether the flatten order will actually fill. Then take orders + passive quotes are sized based on the updated `pos`, and the TOTAL exceeds the limit.

**The real issue in the code:** When a bot posts at 10000 (your flatten target), you send a flatten order AND then your passive quotes are sized using the `pos` AFTER the hypothetical flatten. But the exchange checks all orders together. If flatten_qty + take_qty + passive_qty > limit, everything dies.

**Fix:** After ALL order construction, validate total buy and sell quantities don't exceed limits. If they do, trim the passive quotes first.

### 2. Position-Aware Aggressive Taking [HIGH — ~+150 PnL]
**Hypothesis:** When you're short 14 EMERALDS, any buy at ≤10000 is profitable (you're short, so buying reduces exposure AND you'd sell later above 10000). Currently you only buy below 10000. Relaxing to ≤10000 when short gives you more flattening opportunities.

**For TOMATOES:** Same logic — if you're long 15, accept selling at fair_value (zero edge) to reduce inventory and free capacity.

### 3. Increase EMERALDS Skew Factor [HIGH — ~+100 PnL]
**Current:** SKEW=0.05 → at position 14, skew = 1 tick. This is too gentle. Position sits at -14 for 400+ ticks.

**Proposed:** SKEW=0.10 → at position 14, skew = 1 tick (same due to rounding). Actually need SKEW=0.15 → at position 14, skew = 2 ticks. This shifts quotes enough to attract flattening fills.

**Even better: use a nonlinear skew** that accelerates at high positions:
```python
skew = round(pos * 0.05 + (pos/20)**3)
```
At pos=5: skew=0. At pos=14: skew=1. At pos=20: skew=2. Gentle at low inventory, aggressive at high.

### 4. TOMATOES: Increase Skew Factor [MEDIUM — ~+80 PnL]
Same reasoning. Position reaches -23 at one point. With SKEW=0.05 that's only 1 tick of skew. Needs to be 2-3 ticks at that level.

### 5. EMERALDS: Reduce EDGE from 7 to 6 [MEDIUM — ~+70 PnL]
**Hypothesis:** Your current fill rate is very low (17 trades / 2000 ticks). Reducing EDGE from 7 to 6 means quoting at 9994/10006 instead of 9993/10007. You earn 1 less per fill BUT get filled more often. Since the bottleneck is fill frequency, not edge-per-fill, this should net positive.

**Risk:** Lower edge per fill. But 6 ticks is still very healthy — well above the 2 ticks you started with.

**Validation:** Compare total PnL, not PnL-per-fill. If fills increase by >16%, the lower edge is compensated.

### 6. Add Second-Level Passive Quotes [EXPERIMENTAL — ~+50 PnL]
**Concept:** Post a SECOND passive quote deeper in the book at a wider spread. When a large bot market order arrives, it might sweep through your first level and fill your second level too.

```python
# Primary quotes (existing)
orders.append(Order("EMERALDS", 9993, int(max_buy * 0.7)))
# Backup quotes (wider, smaller)
orders.append(Order("EMERALDS", 9991, int(max_buy * 0.3)))
```

**Risk:** Adds complexity, might trigger position limit issues. Must validate total order sizes carefully.

### 7. TOMATOES: Widen Tight-Regime Spread Further [EXPERIMENTAL — ~+30 PnL]
**Current tight edge:** 5 (when market spread < 10). Could try 6 or even pausing passive quotes entirely in tight regime, only taking.

---

## D) Codex TODO List (Implementation Order)

### TODO 1: Fix Position Limit Validation [CRITICAL]
```
File: trader.py → EMERALDS section, end of order construction

After ALL orders are built (flatten + take + passive), add validation:

total_buy_qty = sum(o.quantity for o in orders if o.quantity > 0)
total_sell_qty = sum(-o.quantity for o in orders if o.quantity < 0)
current_pos = state.position.get("EMERALDS", 0)  # ORIGINAL position

# Check: if all buys fill, would we exceed +80?
if current_pos + total_buy_qty > 80:
    # Trim passive buy order quantity
    excess = (current_pos + total_buy_qty) - 80
    # Find the passive buy order (last buy order added) and reduce it
    for i in range(len(orders)-1, -1, -1):
        if orders[i].quantity > 0 and orders[i].price < 10000:
            trim = min(orders[i].quantity, excess)
            orders[i] = Order("EMERALDS", orders[i].price, orders[i].quantity - trim)
            excess -= trim
            if excess <= 0: break

# Same for sells
if current_pos - total_sell_qty < -80:
    excess = -(current_pos - total_sell_qty) - 80
    for i in range(len(orders)-1, -1, -1):
        if orders[i].quantity < 0 and orders[i].price > 10000:
            trim = min(-orders[i].quantity, excess)
            orders[i] = Order("EMERALDS", orders[i].price, orders[i].quantity + trim)
            excess -= trim
            if excess <= 0: break

# Remove zero-quantity orders
orders = [o for o in orders if o.quantity != 0]
```

### TODO 2: Position-Aware Taking (Task 9) [HIGH CONFIDENCE]
```
File: trader.py → EMERALDS section, taking loops

Replace: if price < self.EM_FAIR:
With:    if price < self.EM_FAIR or (price == self.EM_FAIR and pos < 0):

Replace: if price > self.EM_FAIR:
With:    if price > self.EM_FAIR or (price == self.EM_FAIR and pos > 0):

Same for TOMATOES:
Replace: if price < fair_value:
With:    if price < fair_value or (price <= fair_value and pos < 0):
         # Use <= for TOMATOES (more aggressive flatten since FV is estimated)

Replace: if price > fair_value:
With:    if price > fair_value or (price >= fair_value and pos > 0):
```

### TODO 3: Increase Skew Factors [HIGH CONFIDENCE]
```
File: trader.py → class-level constants

Change: EM_SKEW = 0.05 → EM_SKEW = 0.10
Change: TM_SKEW = 0.05 → TM_SKEW = 0.10

Optional (advanced nonlinear skew):
Replace: skew = round(pos * self.EM_SKEW)
With:    skew = round(pos * self.EM_SKEW + (pos / 25.0)**3)
```

### TODO 4: Try EMERALDS EDGE=6 [MEDIUM CONFIDENCE]
```
File: trader.py → class-level constants

Change: EM_EDGE = 7 → EM_EDGE = 6

Run backtest. Compare:
  - Total EMERALDS PnL
  - Number of fills
  - PnL per fill
Keep whichever EDGE gives higher total PnL.
```

### TODO 5: Same Position Limit Fix for TOMATOES [HIGH CONFIDENCE]
```
File: trader.py → TOMATOES section, after order construction

Same pattern as TODO 1 but for TOMATOES with:
  position_limit = 80
  fair_value = estimated fair_value (not 10000)
  Use actual state.position.get("TOMATOES", 0) for original pos
```

### TODO 6: Remove Flatten-Before-Take Approach for EMERALDS [MEDIUM]
```
The current flatten logic at the top of EMERALDS creates ordering problems.
Instead, merge flattening into position-aware taking (TODO 2).

Remove the flatten block entirely:
  Delete: if pos > 0 and self.EM_FAIR in order_depth.buy_orders: ...
  Delete: elif pos < 0 and self.EM_FAIR in order_depth.sell_orders: ...

The position-aware taking now handles it:
  - When short, buy at 10000 (caught by TODO 2's "price == FAIR and pos < 0")
  - When long, sell at 10000 (caught by TODO 2's "price == FAIR and pos > 0")
This is cleaner AND avoids the double-counting that causes limit violations.
```

**Implementation order:** TODO 6 → TODO 2 → TODO 1 → TODO 3 → TODO 4 → TODO 5

---

## E) Backtest/Validation Checklist

| Metric | Current Value | Target | How to Measure |
|---|---|---|---|
| Position limit violations | 35/2000 (1.75%) | **0** | grep "exceeded limit" in sandbox logs |
| EMERALDS fill count | 17 | > 25 | Count trades where SUBMISSION is buyer/seller |
| EMERALDS PnL | 599 | > 900 | From activitiesLog final row |
| TOMATOES PnL | 782 | > 900 | From activitiesLog final row |
| Total PnL | 1,381 | > 2,000 | From JSON profit field |
| Max abs EMERALDS position | 18 | < 15 | From position logs |
| EMERALDS avg abs position | 10.4 | < 8 | From position logs |
| Max drawdown | 144 | < 150 | From graph log |
| PnL monotonicity | Good 1st half, stalls 2nd | Steady throughout | Visual PnL curve check |

**Acceptance criteria for each change:**
- TODO 1 (limit fix): violations drop to 0. If any remain, debug.
- TODO 2 (position-aware taking): fill count increases. PnL should increase.
- TODO 3 (stronger skew): avg abs position decreases. Max position decreases.
- TODO 4 (EDGE=6): total EMERALDS PnL increases despite lower edge/fill. If it decreases, revert to EDGE=7.

---

## F) Dashboard Watchlist

1. **Position limit violation count** — must be 0 after TODO 1/5/6
2. **EMERALDS fills per 1000 ticks** — currently ~8.5, target >12
3. **EMERALDS PnL growth in 2nd half** — currently plateaus, should continue growing
4. **Max absolute position (either product)** — target < 20 at all times
5. **Time stuck at same position (no trades)** — long gaps = lost opportunity
6. **Per-fill edge** — EMERALDS should be ~6-7, TOMATOES should be ~3-5
7. **TOMATOES PnL in tight-spread ticks** — should be ≥ 0 (regime filter working)

---

## G) Sources Referenced

- Frankfurt Hedgehogs (2nd, P3): github.com/TimoDiehm/imc-prosperity-3 — position limit management, take-then-make-then-flatten ordering
- Ding Crab (28th, P3): github.com/angus4718/imc-prosperity-3-public — three-step strategy, inventory offloading at fair value
- Martin Oravec (73rd, P3): medium.com/@oravec.martin01/imc-prosperity-3 — take/clear bands, position-based skewing, z-score reversion
- Rank 13 team (P2): github.com/pe049395/IMC-Prosperity-2024 — expected utility framework, large-order fair value
- AlphaBaguette (top 1%, P3): github.com/Sylvain-Topeza/imc-prosperity-3 — OU-style fair value, toxic order filtering