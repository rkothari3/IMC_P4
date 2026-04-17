# Backtests Reference

## Risk Metrics

| Metric | Simple Definition |
|---|---|
| `final_pnl` | Total profit at end of backtest |
| `sharpe_ratio` | Profit vs risk. Above 2 = great. 16+ = near risk-free |
| `annualized_sharpe` | Sharpe scaled to a yearly rate (ignore the large number) |
| `sortino_ratio` | Like Sharpe but only penalizes *losing* periods. `inf` = zero losing periods |
| `max_drawdown_abs` | Worst temporary dip in SeaShells (peak → trough before recovery) |
| `max_drawdown_pct` | Same dip as a percentage of peak value |
| `calmar_ratio` | Total profit ÷ max drawdown. Higher = better. 6+ is excellent |

---

## prosperity4btest CLI

```
prosperity4btest [OPTIONS] ALGORITHM DAYS...
```

### Days format
- `0` — all days in round 0
- `1` — all days in round 1
- `0--2` — round 0, day -2 only
- `1-1` — round 1, day 1 only

### Useful options

| Flag | What it does |
|---|---|
| `--vis` | Open results in the visualizer after run |
| `--merge-pnl` | Merge PnL across days into one number |
| `--print` | Print trader's stdout output while running |
| `--out FILE` | Save log to a specific file |
| `--no-out` | Don't save a log file |
| `--match-trades all\|worse\|none` | How to match orders against market trades (default: `all`) |
| `--limit PRODUCT:LIMIT` | Override position limit for a product |

### Examples
```bash
prosperity4btest trader.py 0
prosperity4btest trader.py 0 --vis
prosperity4btest trader.py 0--2 0--1 --merge-pnl
prosperity4btest trader.py 1 --print
```

### Round 1 — required flags

The backtester defaults to 50-unit limits. Round 1 allows 80. Without `--limit` flags all 80-unit orders are rejected and PnL = 0. **Always use:**

```bash
# Standard Round 1 backtest (all 3 days, merged PnL)
prosperity4btest trader.py 1 --data data --merge-pnl --no-out \
  --limit ASH_COATED_OSMIUM:80 --limit INTARIAN_PEPPER_ROOT:80

# Single day (e.g. day 0)
prosperity4btest trader.py 1-0 --data data --no-out \
  --limit ASH_COATED_OSMIUM:80 --limit INTARIAN_PEPPER_ROOT:80

# With visualizer
prosperity4btest trader.py 1 --data data --merge-pnl \
  --limit ASH_COATED_OSMIUM:80 --limit INTARIAN_PEPPER_ROOT:80 --vis
```

### Round 1 baselines (local, 10k iterations per day)

| Trader version | ACO/day avg | PEP/day avg | Total 3-day | Notes |
|---|---|---|---|---|
| Phase 1.1 (limits→80) | ~17,357 | ~65,187 | 247,631 | PEP_LIMIT fixed, limits correct |
| Phase 1.2 (target=25, width=1) | ~17,357 | ~76,093 | 254,179 | Grid-search optimized target/width |
| Phase 2 attempt (EWMA+A-S) | ~17,357 | ~43,040 | 181,192 | **Reverted** — worse than baseline |
