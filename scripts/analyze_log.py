#!/usr/bin/env python3
"""
IMC Prosperity 4 — Log Analyzer
Parses backtest or server run logs and outputs structured analysis.

Usage:
    python analyze_log.py <path_to_log_file> [--json] [--product PRODUCT]

Claude Code can run this after every backtest to get structured feedback:
    python scripts/analyze_log.py backtests/2026-04-09_00-37-19.log
    python scripts/analyze_log.py server_runs/Trader_4/67202.log --json
"""

import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class ProductStats:
    product: str
    final_pnl: float = 0.0
    max_pnl: float = 0.0
    min_pnl: float = 0.0
    total_fills: int = 0
    buy_fills: int = 0
    sell_fills: int = 0
    buy_volume: int = 0
    sell_volume: int = 0
    avg_buy_price: float = 0.0
    avg_sell_price: float = 0.0
    max_long_position: int = 0
    max_short_position: int = 0
    # Spread stats (from activity log)
    avg_spread: float = 0.0
    avg_mid_price: float = 0.0
    ticks: int = 0


@dataclass
class Analysis:
    source_file: str
    format: str  # "backtest" or "server_run"
    total_pnl: float = 0.0
    products: dict = field(default_factory=dict)
    adverse_selection_events: list = field(default_factory=list)
    pnl_timeline: list = field(default_factory=list)  # [(timestamp, pnl), ...]
    position_limits_hit: list = field(default_factory=list)
    summary: str = ""


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_activity_log_csv(csv_text: str) -> list[dict]:
    """Parse the Activities log CSV section (works for both formats)."""
    rows = []
    lines = csv_text.strip().split('\n')
    start = 1 if lines and lines[0].startswith('day') else 0

    for line in lines[start:]:
        line = line.strip()
        if not line:
            break
        cols = line.split(';')
        if len(cols) < 17:
            continue

        def safe_float(v):
            try:
                return float(v) if v else None
            except ValueError:
                return None

        rows.append({
            'day': int(cols[0]),
            'timestamp': int(cols[1]),
            'product': cols[2],
            'bid_prices': [safe_float(cols[i]) for i in [3, 5, 7] if safe_float(cols[i]) is not None],
            'bid_volumes': [safe_float(cols[i]) for i in [4, 6, 8] if safe_float(cols[i]) is not None],
            'ask_prices': [safe_float(cols[i]) for i in [9, 11, 13] if safe_float(cols[i]) is not None],
            'ask_volumes': [safe_float(cols[i]) for i in [10, 12, 14] if safe_float(cols[i]) is not None],
            'mid_price': safe_float(cols[15]) or 0.0,
            'pnl': safe_float(cols[16]) or 0.0,
        })
    return rows


def detect_and_parse(log_path: str) -> tuple[str, list[dict], list[dict]]:
    """
    Returns (format, activity_rows, trade_history).
    format is "server_run" or "backtest".
    """
    text = Path(log_path).read_text(encoding='utf-8')

    # Try JSON (server run format)
    try:
        data = json.loads(text)
        if 'activitiesLog' in data:
            activity_rows = parse_activity_log_csv(data['activitiesLog'])
            trade_history = data.get('tradeHistory', [])
            return 'server_run', activity_rows, trade_history
    except (json.JSONDecodeError, KeyError):
        pass

    # Backtest text format
    lines = text.splitlines()
    activity_start = next((i for i, l in enumerate(lines) if l.strip() == 'Activities log:'), None)
    if activity_start is None:
        raise ValueError("Could not find 'Activities log:' section in log file")

    csv_text = '\n'.join(lines[activity_start + 1:])
    activity_rows = parse_activity_log_csv(csv_text)
    return 'backtest', activity_rows, []


# ── Analysis ──────────────────────────────────────────────────────────────────

# IMPORTANT: Update this dict manually at the start of each new round.
# New products are introduced each round — add them here with their correct
# position limits (check the IMC Prosperity round announcement). Any product
# not listed falls back to 80, which may be wrong.
POSITION_LIMITS = {
    'EMERALDS': 80,
    'TOMATOES': 80,
    'ASH_COATED_OSMIUM': 50,
    'INTARIAN_PEPPER_ROOT': 50,
}


def analyze(log_path: str) -> Analysis:
    fmt, activity_rows, trade_history = detect_and_parse(log_path)
    result = Analysis(source_file=log_path, format=fmt)

    # ── Activity log analysis ─────────────────────────────────────────────────
    products_seen = set(r['product'] for r in activity_rows)
    stats: dict[str, ProductStats] = {p: ProductStats(product=p) for p in products_seen}

    pnl_by_timestamp: dict[int, float] = defaultdict(float)
    for row in activity_rows:
        p = row['product']
        s = stats[p]
        s.ticks += 1
        s.avg_mid_price += row['mid_price']
        pnl_by_timestamp[row['timestamp']] += row['pnl']

        # Spread
        if row['bid_prices'] and row['ask_prices']:
            s.avg_spread += row['ask_prices'][0] - row['bid_prices'][0]

    # Finalize averages
    for p, s in stats.items():
        if s.ticks > 0:
            s.avg_mid_price /= s.ticks
            s.avg_spread /= s.ticks

    # PnL timeline and final values
    sorted_timestamps = sorted(pnl_by_timestamp.keys())
    result.pnl_timeline = [(ts, pnl_by_timestamp[ts]) for ts in sorted_timestamps]

    # Final PnL per product (last timestamp value)
    last_ts = sorted_timestamps[-1] if sorted_timestamps else None
    if last_ts is not None:
        for row in activity_rows:
            if row['timestamp'] == last_ts:
                stats[row['product']].final_pnl = row['pnl']
                result.total_pnl += row['pnl']

    # Min/max PnL per product
    product_pnl_history: dict[str, list[float]] = defaultdict(list)
    for row in activity_rows:
        product_pnl_history[row['product']].append(row['pnl'])
    for p, history in product_pnl_history.items():
        stats[p].max_pnl = max(history)
        stats[p].min_pnl = min(history)

    # ── Trade history analysis (server runs only) ──────────────────────────────
    position_tracker: dict[str, int] = defaultdict(int)
    product_buy_value: dict[str, float] = defaultdict(float)
    product_sell_value: dict[str, float] = defaultdict(float)

    for trade in sorted(trade_history, key=lambda t: t['timestamp']):
        sym = trade['symbol']
        price = trade['price']
        qty = trade['quantity']
        buyer = trade.get('buyer', '')
        seller = trade.get('seller', '')

        is_our_buy = 'SUBMISSION' in buyer
        is_our_sell = 'SUBMISSION' in seller

        if is_our_buy:
            stats[sym].buy_fills += 1
            stats[sym].buy_volume += qty
            product_buy_value[sym] += price * qty
            position_tracker[sym] += qty
        elif is_our_sell:
            stats[sym].sell_fills += 1
            stats[sym].sell_volume += qty
            product_sell_value[sym] += price * qty
            position_tracker[sym] -= qty

        if sym in stats:
            stats[sym].max_long_position = max(stats[sym].max_long_position, position_tracker[sym])
            stats[sym].max_short_position = min(stats[sym].max_short_position, position_tracker[sym])

            # Check position limit hits
            limit = POSITION_LIMITS.get(sym, 80)
            if abs(position_tracker[sym]) >= limit:
                result.position_limits_hit.append({
                    'timestamp': trade['timestamp'],
                    'product': sym,
                    'position': position_tracker[sym],
                    'limit': limit,
                })

    # Compute average fill prices
    for p in products_seen:
        s = stats[p]
        s.total_fills = s.buy_fills + s.sell_fills
        if s.buy_volume > 0:
            s.avg_buy_price = product_buy_value[p] / s.buy_volume
        if s.sell_volume > 0:
            s.avg_sell_price = product_sell_value[p] / s.sell_volume

    # ── Adverse selection detection ───────────────────────────────────────────
    # Simple heuristic: we bought within N ticks, then mid_price dropped significantly
    # Only doable with trade history + activity log aligned by timestamp
    if trade_history:
        mid_by_ts: dict[str, dict[int, float]] = defaultdict(dict)
        for row in activity_rows:
            mid_by_ts[row['product']][row['timestamp']] = row['mid_price']

        for trade in trade_history:
            sym = trade['symbol']
            ts = trade['timestamp']
            price = trade['price']
            buyer = trade.get('buyer', '')
            seller = trade.get('seller', '')
            if sym not in mid_by_ts:
                continue
            mid = mid_by_ts[sym].get(ts)
            if mid is None:
                continue
            # If we bought above mid or sold below mid, it's likely adverse
            if 'SUBMISSION' in buyer and price > mid + 1:
                result.adverse_selection_events.append({
                    'type': 'buy_above_mid',
                    'product': sym,
                    'timestamp': ts,
                    'fill_price': price,
                    'mid_price': mid,
                    'slippage': price - mid,
                })
            elif 'SUBMISSION' in seller and price < mid - 1:
                result.adverse_selection_events.append({
                    'type': 'sell_below_mid',
                    'product': sym,
                    'timestamp': ts,
                    'fill_price': price,
                    'mid_price': mid,
                    'slippage': mid - price,
                })

    result.products = {p: asdict(s) for p, s in stats.items()}
    result.summary = _build_summary(result, stats)
    return result


def _build_summary(result: Analysis, stats: dict[str, ProductStats]) -> str:
    lines = [
        f"=== IMC Prosperity 4 Log Analysis ===",
        f"File   : {result.source_file}",
        f"Format : {result.format}",
        f"",
        f"TOTAL PnL: {result.total_pnl:,.1f} XIREC",
        f"",
        "── Per-Product ──────────────────────────────",
    ]
    for p, s in stats.items():
        lines.append(f"  {p}:")
        lines.append(f"    Final PnL    : {s.final_pnl:,.1f}")
        lines.append(f"    PnL range    : [{s.min_pnl:,.1f}, {s.max_pnl:,.1f}]")
        lines.append(f"    Ticks        : {s.ticks:,}")
        lines.append(f"    Avg mid price: {s.avg_mid_price:.2f}")
        lines.append(f"    Avg spread   : {s.avg_spread:.2f}")
        if s.total_fills > 0:
            lines.append(f"    Fills        : {s.total_fills} ({s.buy_fills} buys @ {s.avg_buy_price:.2f}, {s.sell_fills} sells @ {s.avg_sell_price:.2f})")
            lines.append(f"    Volume       : {s.buy_volume} bought, {s.sell_volume} sold")
            lines.append(f"    Max position : +{s.max_long_position} / {s.max_short_position}")

    if result.position_limits_hit:
        lines.append(f"")
        lines.append(f"── Position Limit Hits ({len(result.position_limits_hit)}) ──────────────")
        for hit in result.position_limits_hit[:5]:
            lines.append(f"  ts={hit['timestamp']:,}  {hit['product']}  pos={hit['position']}  limit=±{hit['limit']}")
        if len(result.position_limits_hit) > 5:
            lines.append(f"  ... and {len(result.position_limits_hit) - 5} more")

    if result.adverse_selection_events:
        lines.append(f"")
        lines.append(f"── Adverse Selection ({len(result.adverse_selection_events)} events) ──────────")
        worst = sorted(result.adverse_selection_events, key=lambda e: -e['slippage'])[:5]
        for ev in worst:
            lines.append(f"  ts={ev['timestamp']:,}  {ev['product']}  {ev['type']}  slippage={ev['slippage']:.1f}")

    return '\n'.join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Analyze an IMC Prosperity 4 log file')
    parser.add_argument('log_file', help='Path to the log file (.log)')
    parser.add_argument('--json', action='store_true', help='Output raw JSON instead of human-readable summary')
    parser.add_argument('--product', help='Filter output to a specific product')
    args = parser.parse_args()

    try:
        result = analyze(args.log_file)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        output = asdict(result) if hasattr(result, '__dataclass_fields__') else result.__dict__
        # Convert Analysis to dict manually
        output = {
            'source_file': result.source_file,
            'format': result.format,
            'total_pnl': result.total_pnl,
            'products': result.products,
            'adverse_selection_count': len(result.adverse_selection_events),
            'adverse_selection_events': result.adverse_selection_events[:20],
            'position_limits_hit': result.position_limits_hit,
            'pnl_timeline_length': len(result.pnl_timeline),
        }
        if args.product and args.product in output['products']:
            output = {'product': args.product, **output['products'][args.product]}
        print(json.dumps(output, indent=2))
    else:
        print(result.summary)


if __name__ == '__main__':
    main()
