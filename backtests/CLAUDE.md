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
