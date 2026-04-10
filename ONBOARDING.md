# IMC Prosperity 4 — Project Onboarding

## What Is This Competition?

IMC Prosperity is a simulated market-making competition. You trade two products (EMERALDS, TOMATOES) against bots. Goal: maximize profit (XIRECs) by providing liquidity and capturing the spread.

### Core Concepts (Quick Learn)

- **Market Making**: Post bid (buy) and ask (sell) quotes, earn from the spread
- **Fair Value**: Your estimate of the "true" price
- **Edge**: Profit per fill (difference between your quote and fair value)
- **Position Limit**: Max 80 units per product (exchange rejects exceeding orders)
- **Take vs Make**: "Take" = buy from existing orders. "Make" = post quotes for others to take
- **Adverse Selection**: Getting traded against by informed traders who know more than you

---

## Project Structure

```
.
├── trader.py           # YOUR BOT — main trading algorithm
├── LLM.md             # Research notes, strategy history
├── DOCS.md            # Competition API documentation
├── dashboard/         # HTML visualizer for analyzing runs
├── server_runs/        # Live server submissions (Trader_1/, Trader_2/, etc.)
├── backtests/          # Local backtest outputs
└── Round_0/           # Historical price/trade data for days -2, -1
```

---

## Current Bot (Latest)

**File**: `trader.py`  
**Backtest PnL**: 29,530  
**Strategy**: Market making on EMERALDS (fixed fair 10000) and TOMATOES (drifting fair ~5000)

### Key Code Patterns

```python
class Trader:
    EM_FAIR = 10000           # EMERALDS fixed fair value
    EM_EDGE = 7               # Spread around fair for passive quotes
    EM_SKEW = 0.05            # Inventory risk adjuster
    
    TM_BASE_EDGE = 5          # TOMATOES edge ( widened from 3 )
    TM_TIGHT_EDGE = 7          # Edge when spread < 10
```

**Strategy Flow** (each tick):
1. **Take**: Buy from asks below fair, sell to bids above fair
2. **Position-aware flatten**: Also accept fair-value trades when reducing inventory
3. **Make**: Post passive bid/ask around fair value
4. **Validate**: Trim orders if aggregate would exceed 80 limit

---

## Known Issues / Lessons Learned

1. **Position Limit Violations** (Trader_3 had 35) → Fixed with aggregate validator
2. **Backtest vs Live Gap** (~14x) → Backtest runs 10k ticks/day vs live 2k ticks/day
3. **TOMATOES Edge**: 3→5 gave +50% PnL boost (bots accept wider quotes)
4. **Microprice**: Shows 0 in backtest but may help live (order book imbalance signal)

---

## Visualizer Project (Next)

Reference: `jmerle/imc-prosperity-4-visualizer` (GitHub)

### Current Dashboard

Existing `dashboard/index.html` has:
- File upload for JSON logs
- PnL charts per product
- Position tracking over time
- **Fixed**: XSS bugs, click recursion

### What's Needed

A working visualizer that:
1. Parses server run JSON outputs
2. Plots PnL over time
3. Shows order book state snapshots
4. Displays fills vs quotes
5. Animates the market (optional, nice-to-have)

### Data Sources

- `server_runs/Trader_N/<id>.json` — Full run data
- `server_runs/Trader_N/<id>.py` — Exact code submitted
- `Round_0/prices_*.csv` — Historical price data
- `Round_0/trades_*.csv` — Historical trade data

---

## Quick Start Commands

```bash
# Run backtest
prosperity4btest trader.py 0--2 0--1 --merge-pnl --no-out

# Copy baseline for comparison
cp server_runs/Trader_1/63248.py trader_baseline.py

# Run specific day
prosperity4btest trader.py 0--0 --merge-pnl --no-out
```

---

## Contact Info

- Competition: imcprosperity.com
- Discord: Check competition page for community
- Past winners to study: Frankfurt Hedgehogs (P3 2nd), Ding Crab (P3 28th)

---

## Questions to Answer for Visualizer

1. What charts/visualizations are most useful for debugging a market-making bot?
2. Should it parse live server JSON or local backtest logs?
3. Real-time visualization during backtest (nice) vs post-run analysis (simpler)?
4. What metrics matter most: PnL, fill rate, position, adverse selection?

Good luck! 🎯