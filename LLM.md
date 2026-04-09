# IMC Prosperity 4 — Strategy Audit & Upgrade Plan

## Run Stats (Trader_1 / 63248.json)
- **Total PnL: 774.59** (749.51 from graph log after mark-to-market)
- EMERALDS PnL: 300.00 | TOMATOES PnL: 474.59
- Max drawdown: 133.52 | Sharpe-like ratio: 0.77
- Final positions: EMERALDS -16, TOMATOES +15 (both carrying risk at end)

---

## Implementation Status

### IMPLEMENTED (v1 - High Confidence)
- ✅ Task 1: EMERALDS Quote Widening (EDGE=7)
- ✅ Task 2: EMERALDS Inventory Skew (SKEW=0.05)
- ✅ Task 3: EMERALDS Flatten at Fair Value
- ✅ Task 4: TOMATOES Weighted Mid Fair Value
- ✅ Task 5: TOMATOES Inventory Skew
- ✅ Task 6: TOMATOES Wider Base Spread (EDGE=3 normal, 5 tight)
- ✅ Task 7: TOMATOES Regime Filter (spread < 10 triggers wider edge + half size)

### NOT YET IMPLEMENTED (Experimental)
- ⏳ Task 8: EMA Fair Value with traderData Persistence
- ⏳ Task 9: Position-Aware Aggressive Taking

---

## Backtest Results

| Metric | Trader_1 baseline | New v1 | Delta |
|--------|------------------|--------|-------|
| Total PnL | 7,376 | 21,318 | +13,942 (+189%) |
| Sharpe ratio | 4.24 | 48.70 | +11x |
| Max drawdown | 1,825 | 1,214 | -611 |
| EMERALDS | 4,150 | 12,973 | +8,823 |
| TOMATOES | 3,227 | 8,344 | +5,117 |

---

## A) Current Weaknesses (Beginner-Friendly)

### What your bot does now

**EMERALDS (fixed fair value = 10,000):**
Your bot does two things each tick: (1) "take" — buy anything listed below 10,000 or sell anything above it, (2) "make" — post a standing buy order at 9,998 and a sell order at 10,002, hoping bots trade against you.

**TOMATOES (drifting fair value ~5,000):**
Same structure, but instead of hardcoded 10,000, you estimate fair value as the midpoint between the best bid and best ask. Then you take mispriced orders and post quotes at `floor(fair)-1` / `ceil(fair)+1`.

### The 5 problems killing your PnL

**1. EMERALDS: Your quotes are too tight (spread = 4), leaving money on the table.**
The bot market has a 16-tick spread (9992/10008). You quote 9998/10002, earning only 2 ticks per passive fill. The Frankfurt Hedgehogs (2nd place globally in P3) instead "overbid on bids and undercut on asks" — i.e., quote at 9993/10007, earning 7 ticks per fill while still being best-in-book. You're giving away ~3.5× more edge per trade than necessary.

**2. TOMATOES: Simple mid-price is a noisy fair value estimate.**
Your `(best_bid + best_ask) / 2` treats a bid of 10 lots the same as a bid of 1 lot. A volume-weighted mid-price gives you a better "true" value estimate, reducing how often you buy too high or sell too low. The top teams in P3 used the average of the large-quantity price levels (which closely track the hidden fair value) rather than the simple mid.

**3. No inventory management — you're exposed to directional risk.**
You ended the run with -16 EMERALDS and +15 TOMATOES. These are open positions that could be worth more or less by end-of-day. Top teams "skew" their quotes: if long, they lower both bid and ask to encourage selling; if short, they raise both. This keeps inventory near zero, reducing risk and freeing position capacity for more trades.

**4. No adverse selection protection on TOMATOES.**
When the spread suddenly tightens from 13→5 ticks, it often means a bot is about to push the price. Your bot keeps quoting the same tight spread and gets "picked off" — you buy just before the price drops. Top teams either widen their spread or stop quoting in tight-spread regimes.

**5. Position capacity wasted at limits.**
When you hit +80 or -80, you can't trade anymore. Every tick at the limit is lost PnL. The Ding Crab team (28th in P3) added a step to "offload excessive inventory at fair price" before doing market making, keeping the position centered and capacity available.

---

## B) Top 5 Strategy Upgrades (Ranked by Expected PnL Impact)

### Upgrade 1: EMERALDS — Widen Passive Quotes + Penny the Bots
**Expected impact: +150–300% on EMERALDS PnL (from ~300 to ~750–1200)**

### Upgrade 2: Inventory Skewing for Both Products
**Expected impact: +20–40% total PnL, major drawdown reduction**

### Upgrade 3: TOMATOES — Better Fair Value (Weighted Mid + Large-Order Signal)
**Expected impact: +30–50% on TOMATOES PnL**

### Upgrade 4: TOMATOES — Regime-Aware Spread
**Expected impact: +15–25% on TOMATOES PnL, major adverse selection reduction**

### Upgrade 5: Inventory Flattening Before End-of-Day
**Expected impact: Small direct PnL boost, large variance reduction**

---

## C) Detailed Upgrade Specifications

### Upgrade 1: EMERALDS — Optimal Quote Placement

**Hypothesis:** The bot order book in EMERALDS is always 9992/10008 (spread=16). By quoting at 9993/10007 (one tick inside the bots), you become best-in-book and capture 7 ticks per fill instead of 2. Bots that send market orders MUST trade with you first (price-time priority). This is the same strategy Frankfurt Hedgehogs used for Rainforest Resin.

**Signals/features:** None needed — this is a static improvement.

**Execution logic:**
```python
# EMERALDS passive quotes — replace 9998/10002 with:
EDGE = 7  # ticks inside fair value
bid_price = FAIR_VALUE - EDGE   # 9993
ask_price = FAIR_VALUE + EDGE   # 10007

# BUT: only if no bot is already at that level or tighter
# Check: if best_ask <= 10007, don't post ask (you'd be trading against yourself)
# In practice, bots are at 10008, so 10007 is always safe
```

**Also: take at fair value when bots cross.**
~3% of ticks, a bot posts at exactly 10000. Currently you ignore these (code requires `price < FAIR_VALUE`). Change to `<=` / `>=` when you have inventory to flatten:
```python
# If you're long and a bot bids at 10000, sell to them (free flattening)
# If you're short and a bot asks at 10000, buy from them
```

**Risks:** If P4 changes bot behavior (tighter spreads), the edge shrinks. Mitigated by making EDGE a parameter you can tune.

**Validation:** Backtest with `prosperity4bt`. Compare per-fill edge at 9998/10002 vs 9993/10007. Metric: total PnL, fills/tick, edge/fill.

---

### Upgrade 2: Inventory Skewing

**Hypothesis:** When you're long 40 EMERALDS, you're exposed to 40 × (price move) risk, AND you can only buy 40 more. By shifting your quotes toward flattening (lower bid, lower ask when long), you (a) encourage trades that reduce your position, and (b) get filled at slightly worse prices, but your reduced inventory risk more than compensates.

**Simple English:** Imagine you run a fruit stand. If you have too many apples (long), you lower your prices to sell them faster. If you're out of apples (short), you raise prices to discourage more selling. That's inventory skewing.

**Execution logic:**
```python
# Skew factor: how much to shift quotes per unit of inventory
SKEW_FACTOR = 0.05  # 1 tick per 20 units of position

# For EMERALDS:
pos = state.position.get("EMERALDS", 0)
skew = round(pos * SKEW_FACTOR)  # positive when long → lower prices

bid_price = FAIR_VALUE - EDGE - skew
ask_price = FAIR_VALUE + EDGE - skew

# When long 40: skew=2 → bid=9991, ask=10005 (eager to sell, reluctant to buy)
# When short 40: skew=-2 → bid=9995, ask=10009 (eager to buy, reluctant to sell)
```

**For TOMATOES:** Same logic but using estimated fair_value instead of 10000.

**Risks:** Over-skewing can cause you to miss good trades. Start with SKEW_FACTOR=0.05 and tune up.

**Validation:** Track: average absolute position over time, PnL variance, max drawdown. Skew should reduce all three.

---

### Upgrade 3: TOMATOES — Better Fair Value Estimation

**Hypothesis:** The P2 rank-13 team discovered that the hidden fair value closely matches the average of the two price levels with the largest quantities. Simple mid-price is noisy because small aggressive orders move it. Volume-weighted mid (or "large-order mid") is more stable and accurate.

**Simple English:** If 100 people want to buy at $50 and 1 person wants to buy at $55, the "real" value is closer to $50 than $52.50. Weighting by quantity gives you a better estimate.

**Execution logic:**
```python
# Method 1: Volume-weighted mid
def weighted_mid(order_depth):
    best_bid = max(order_depth.buy_orders.keys())
    best_ask = min(order_depth.sell_orders.keys())
    bid_vol = order_depth.buy_orders[best_bid]
    ask_vol = -order_depth.sell_orders[best_ask]
    
    wmid = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)
    return wmid

# Method 2: Large-order mid (P2 rank-13 approach)
# Find the price level with the largest volume on each side
def large_order_mid(order_depth):
    max_bid_price = max(order_depth.buy_orders.keys(), 
                        key=lambda p: order_depth.buy_orders[p])
    max_ask_price = min(order_depth.sell_orders.keys(), 
                        key=lambda p: -order_depth.sell_orders[p])
    return (max_bid_price + max_ask_price) / 2

# Method 3: EMA of mid-prices (requires traderData persistence)
# Smooths out tick-to-tick noise
# alpha = 0.3 → reacts to ~last 3 ticks  
# fair_value = alpha * current_mid + (1-alpha) * prev_fair_value
```

**Risks:** Weighted mid can be manipulated if bots post large fake orders (unlikely in Prosperity). EMA adds lag.

**Validation:** Compare fair value estimates to actual trade prices. The estimate with the lowest mean absolute error vs realized trade prices is best.

---

### Upgrade 4: TOMATOES — Regime-Aware Spread

**Hypothesis:** TOMATOES spread is bimodal: 13-14 ticks (94% of time) vs 5-8 ticks (6%). Tight-spread ticks indicate a bot is about to push the price (adverse selection signal). By widening your spread or pausing quotes when the market spread tightens, you avoid getting picked off.

**Simple English:** If the market suddenly gets "competitive" (tight spread), it usually means someone knows something you don't. Step back and wait.

**Execution logic:**
```python
market_spread = best_ask - best_bid

# Normal regime: spread >= 10
# Tight regime: spread < 10 → danger zone

if market_spread < 10:
    # Widen our spread or skip making
    our_edge = 5  # wider than normal
    # Optionally: reduce quote size
    size_mult = 0.5
else:
    our_edge = 3  # normal
    size_mult = 1.0

bid_price = math.floor(fair_value) - our_edge
ask_price = math.ceil(fair_value) + our_edge
```

**Advanced: Use spread percentile as a continuous signal.**
```python
# Track rolling average spread (via traderData)
# If current spread < 0.7 * avg_spread → tighten or pause
# If current spread > 1.3 * avg_spread → widen quotes for more edge
```

**Risks:** Might miss some profitable trades during tight-spread periods. But the adverse selection you avoid is worth more.

**Validation:** Tag each fill as "tight-spread" or "normal-spread". Compare average PnL-per-fill in each regime. If tight-spread fills have negative average PnL, the filter is working.

---

### Upgrade 5: Inventory Flattening

**Hypothesis:** At end of simulation, your position is marked to market. Holding -16 EMERALDS is fine if fair value is 10000 (you know the price), but +15 TOMATOES at an uncertain price adds variance. More importantly, throughout the day, being at high inventory reduces your capacity to trade.

**Execution logic:**
```python
# Add as the FIRST step in run(), before taking or making:

# Flatten toward zero at fair value
pos = state.position.get(product, 0)
SOFT_LIMIT = 40  # start flattening above this

if abs(pos) > SOFT_LIMIT:
    # For EMERALDS, post orders at 10000 to flatten
    # For TOMATOES, post at fair_value
    flatten_qty = abs(pos) - SOFT_LIMIT
    if pos > 0:
        # Post aggressive sell to flatten
        orders.append(Order(product, fair_value, -flatten_qty))
    else:
        orders.append(Order(product, fair_value, flatten_qty))
```

**Risks:** Flattening at fair_value earns 0 edge per trade. But it frees capacity for future profitable trades.

**Validation:** Track: time spent above SOFT_LIMIT, number of "blocked" ticks where you couldn't trade due to position limits.

---

## D) Codex Change Requests (Copy-Paste Task List)

### Task 1: EMERALDS Quote Widening [HIGH CONFIDENCE]
```
File: trader.py → EMERALDS section
Change: Replace hardcoded 9998/10002 passive quotes with 9993/10007
Specifically:
  - Line "orders.append(Order("EMERALDS", 9998, max_buy))" → change 9998 to 9993
  - Line "orders.append(Order("EMERALDS", 10002, -max_sell))" → change 10002 to 10007
  - Make these configurable: EM_BID_EDGE = 7, EM_ASK_EDGE = 7
  - Final: bid = 10000 - EM_BID_EDGE, ask = 10000 + EM_ASK_EDGE
```

### Task 2: Inventory Skew for EMERALDS [HIGH CONFIDENCE]
```
File: trader.py → EMERALDS section
After calculating pos, max_buy, max_sell:
  Add: skew = round(pos * 0.05)  # shift quotes based on inventory
  Modify passive quotes:
    bid_price = 10000 - EM_BID_EDGE - skew
    ask_price = 10000 + EM_ASK_EDGE - skew
  Ensure bid_price < ask_price always (safety check)
```

### Task 3: EMERALDS Flatten at Fair Value [HIGH CONFIDENCE]
```
File: trader.py → EMERALDS section
Before the take loops, add inventory flattening:
  If pos > 0 and there are buy_orders at 10000: sell min(pos, available) at 10000
  If pos < 0 and there are sell_orders at 10000: buy min(-pos, available) at 10000
  This captures the 3% of ticks where bots post at exactly 10000
  Change taking condition from "< FAIR_VALUE" to "<= FAIR_VALUE" for flattening
  (but only take AT fair value if it reduces abs(position))
```

### Task 4: TOMATOES Weighted Mid Fair Value [HIGH CONFIDENCE]
```
File: trader.py → TOMATOES section
Replace simple mid calculation with volume-weighted mid:
  best_bid = max(order_depth.buy_orders.keys())
  best_ask = min(order_depth.sell_orders.keys())
  bid_vol = order_depth.buy_orders[best_bid]
  ask_vol = -order_depth.sell_orders[best_ask]
  fair_value = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)
  
  ALSO: try large_order_mid as an alternative (find max-volume level on each side)
  Run both in backtest and keep whichever has lower MAE vs realized trade prices.
```

### Task 5: TOMATOES Inventory Skew [HIGH CONFIDENCE]
```
File: trader.py → TOMATOES section
Same pattern as EMERALDS:
  TM_SKEW = 0.05
  skew = round(pos * TM_SKEW)
  bid_price = math.floor(fair_value) - TM_EDGE - skew
  ask_price = math.ceil(fair_value) + TM_EDGE - skew
```

### Task 6: TOMATOES Wider Base Spread [HIGH CONFIDENCE]
```
File: trader.py → TOMATOES section
Change passive quote offset from 1 to 3:
  bid_price = math.floor(fair_value) - 3  (was -1)
  ask_price = math.ceil(fair_value) + 3   (was +1)
Make configurable: TM_EDGE = 3
```

### Task 7: TOMATOES Regime Filter [EXPERIMENTAL]
```
File: trader.py → TOMATOES section
After calculating fair_value, add:
  market_spread = best_ask - best_bid
  if market_spread < 10:
      # Tight regime: widen spread, reduce size
      TM_EDGE = 5
      size_mult = 0.5
  else:
      TM_EDGE = 3
      size_mult = 1.0
  
  Apply size_mult to max_buy and max_sell for passive quotes only
  (still take aggressively when price is clearly mispriced)
```

### Task 8: EMA Fair Value with traderData Persistence [EXPERIMENTAL]
```
File: trader.py → TOMATOES section
Use traderData to persist an EMA of fair values across ticks:
  import json
  
  # Deserialize
  if state.traderData:
      data = json.loads(state.traderData)
      ema_fair = data.get("tm_ema", None)
  else:
      ema_fair = None
  
  # Update
  current_mid = weighted_mid(order_depth)
  ALPHA = 0.3
  if ema_fair is None:
      ema_fair = current_mid
  else:
      ema_fair = ALPHA * current_mid + (1 - ALPHA) * ema_fair
  
  fair_value = ema_fair
  
  # Serialize
  traderData = json.dumps({"tm_ema": ema_fair})
```

### Task 9: Position-Aware Aggressive Taking [EXPERIMENTAL]
```
File: trader.py → both products
When taking, be MORE aggressive if the take reduces position:
  # If we're long 30 and see a bid above fair_value:
  # Normal: sell if bid > fair_value
  # Upgraded: sell if bid >= fair_value (break even is fine for flattening)
  
  For taking buys (from sell_orders):
    threshold = fair_value if pos >= 0 else fair_value + 1
    # If short, we WANT to buy → accept tighter edge
    
  For taking sells (from buy_orders):
    threshold = fair_value if pos <= 0 else fair_value - 1
    # If long, we WANT to sell → accept tighter edge
```

### Implementation Order:
1. Tasks 1, 6 (quote widening) — biggest immediate PnL boost
2. Tasks 2, 5 (inventory skew) — risk reduction
3. Task 4 (weighted mid) — accuracy improvement
4. Task 3 (flatten at FV) — capacity management
5. Tasks 7, 8, 9 (experimental) — test one at a time

---

## E) Dashboard Checklist — What to Watch

| Metric | Why It Matters | Target |
|--------|---------------|--------|
| PnL per product per tick | Is each product contributing? | Positive trend |
| Edge per fill (trade price - fair_value) | Are you buying low / selling high? | > 2 for EMERALDS, > 1.5 for TOMATOES |
| Average absolute position | Are you staying centered? | < 30 (50% of limit) |
| Time at max position | Lost trading capacity | < 5% of ticks |
| Max drawdown | Worst case scenario | < 200 |
| Fill rate (passive orders that get filled) | Are your quotes competitive? | > 10% |
| PnL in tight-spread vs normal-spread ticks | Adverse selection detection | Tight should be ≥ 0 |
| Sharpe-like ratio (mean PnL / stdev PnL) | Risk-adjusted performance | > 1.0 |
| Final open position value | End-of-day risk | < 100 |
| Takes vs makes ratio | Edge source breakdown | Track, don't target |

---

## F) Key Concepts Explained

### Adverse Selection
When you post a quote (e.g., "I'll buy at 9998"), you're offering to trade with anyone. The problem: the people most likely to trade with you are those who *know* the price is about to drop. You buy at 9998, and the real value was actually 9990. You just lost 8. In Prosperity, this happens when bots suddenly tighten the spread — it signals an imminent price move.

### Inventory Risk
If you hold 80 TOMATOES and the price drops 5 ticks, you just lost 400. Market makers want to hold as close to zero inventory as possible. Every unit of inventory is a bet on the price direction — and as a market maker, you don't *want* directional bets. You want to earn the spread.

### Spread Capture
The core of market making: buy at 9993, sell at 10007, earn 14 per round trip. Your current bot earns 4 per round trip. The wider your spread, the more you earn per trade, but the fewer trades you do. The optimal spread balances these.

### Quote Pennying / Undercutting
Posting your order one tick better than the competition. If bots bid at 9992, you bid at 9993. Now any seller must trade with *you* first (price-time priority). This is the single most impactful change for EMERALDS.

### Position Skewing (Avellaneda-Stoikov)
A mathematical framework for optimal market making. The key insight: shift your mid-quote based on inventory. If long, your "virtual mid" drops, making you more eager to sell. The formula is roughly: `adjusted_mid = fair_value - inventory * risk_aversion * volatility`. Your SKEW_FACTOR = 0.05 is a simplified version of this.

---

## G) Sources & References

1. **Frankfurt Hedgehogs (2nd, P3)** — github.com/TimoDiehm/imc-prosperity-3
   Key insight: Overbid bots by 1 tick, flatten at fair value, build fallback logic.

2. **Alpha Animals UCSD (9th, P3)** — github.com/CarterT27/imc-prosperity-3
   Key insight: Filter large orders for fair value, copy insider traders in R5.

3. **CMU Physics (7th, P3)** — github.com/chrispyroberts/imc-prosperity-3
   Key insight: Aggressive MM on options using fitted IV, auto-hedging.

4. **Rank 13 Team (P2)** — github.com/pe049395/IMC-Prosperity-2024
   Key insight: Large-quantity price levels = hidden fair value. Expected utility framework.

5. **AlphaBaguette (top 1%, P3)** — github.com/Sylvain-Topeza/imc-prosperity-3
   Key insight: OU-style fair value for Kelp, filter "toxic" small orders for Squid Ink.

6. **Ding Crab (28th, P3)** — github.com/angus4718/imc-prosperity-3-public
   Key insight: Three-step strategy (take → flatten → make), inventory offloading.

7. **Martin Oravec (73rd, P3)** — medium.com/@oravec.martin01/imc-prosperity-3
   Key insight: z-score reversion quotes, volatility-aware spread, take/clear band system.

8. **jmerle's backtester** — github.com/jmerle/imc-prosperity-3-backtester
   Essential tool. Install prosperity4bt when available.