"""
Round 4 Deep-Analysis Script
Products: HYDROGEL_PACK, VELVETFRUIT_EXTRACT, VEV_4000..VEV_6500
New in R4: full counterparty (buyer/seller) visibility
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats
import warnings, os
warnings.filterwarnings('ignore')

# ─── paths ───────────────────────────────────────────────────────────────────
DATA = os.path.dirname(os.path.abspath(__file__))
PLOTS = os.path.join(DATA, "plots")
os.makedirs(PLOTS, exist_ok=True)

DAYS = [1, 2, 3]

# ─── load ─────────────────────────────────────────────────────────────────────
price_dfs, trade_dfs = [], []
for d in DAYS:
    p = pd.read_csv(f"{DATA}/prices_round_4_day_{d}.csv", sep=';')
    p['day'] = d
    price_dfs.append(p)

    t = pd.read_csv(f"{DATA}/trades_round_4_day_{d}.csv", sep=';')
    t['day'] = d
    trade_dfs.append(t)

prices = pd.concat(price_dfs, ignore_index=True)
trades = pd.concat(trade_dfs, ignore_index=True)

# normalize column names
prices.columns = [c.strip() for c in prices.columns]
trades.columns = [c.strip() for c in trades.columns]

PRODUCTS = sorted(prices['product'].unique())
VOUCHERS = [p for p in PRODUCTS if p.startswith('VEV_')]
VOUCHERS_SORTED = sorted(VOUCHERS, key=lambda x: int(x.split('_')[1]))
UNDERLYING = ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']
ALL_BOTS = sorted(set(trades['buyer'].dropna().tolist() + trades['seller'].dropna().tolist())
                  - {'buyer', 'seller'})

print(f"Products: {PRODUCTS}")
print(f"Bots: {ALL_BOTS}")
print(f"Price rows: {len(prices)}, Trade rows: {len(trades)}")

# ════════════════════════════════════════════════════════════════════════════════
# 1. HYDROGEL_PACK — mid-price, spread, vol, autocorr
# ════════════════════════════════════════════════════════════════════════════════
hg = prices[prices['product'] == 'HYDROGEL_PACK'].copy()
hg['spread'] = hg['ask_price_1'] - hg['bid_price_1']
hg['ret'] = hg['mid_price'].pct_change()

fig, axes = plt.subplots(4, 1, figsize=(16, 14), sharex=False)
fig.suptitle('HYDROGEL_PACK — Full Analysis', fontsize=15, fontweight='bold')

# mid-price all days
ax = axes[0]
for d, col in zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green']):
    sub = hg[hg['day'] == d]
    ax.plot(sub['timestamp'], sub['mid_price'], lw=0.6, color=col, label=f'Day {d}')
ax.set_ylabel('Mid Price')
ax.set_title('Mid Price by Day')
ax.legend()
ax.grid(alpha=0.3)

# spread distribution
ax = axes[1]
for d, col in zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green']):
    sub = hg[hg['day'] == d]
    ax.hist(sub['spread'].dropna(), bins=30, alpha=0.5, color=col, label=f'Day {d}', density=True)
ax.set_xlabel('Bid-Ask Spread (ticks)')
ax.set_ylabel('Density')
ax.set_title('Spread Distribution')
ax.legend()
ax.grid(alpha=0.3)

# rolling 100-tick std
ax = axes[2]
for d, col in zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green']):
    sub = hg[hg['day'] == d].copy()
    sub['roll_std'] = sub['mid_price'].rolling(100).std()
    ax.plot(sub['timestamp'], sub['roll_std'], lw=0.7, color=col, label=f'Day {d}')
ax.set_ylabel('Rolling 100-tick Std')
ax.set_title('Volatility Clustering')
ax.legend()
ax.grid(alpha=0.3)

# autocorrelation of returns
ax = axes[3]
lags = range(1, 51)
for d, col, ls in zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green'], ['-', '--', '-.']):
    sub = hg[hg['day'] == d]['mid_price'].diff().dropna()
    acf = [sub.autocorr(lag=l) for l in lags]
    ax.plot(list(lags), acf, color=col, ls=ls, lw=1.2, label=f'Day {d}')
ax.axhline(0, color='black', lw=0.8)
ax.axhline(1.96/np.sqrt(len(hg)), color='red', ls=':', lw=0.8)
ax.axhline(-1.96/np.sqrt(len(hg)), color='red', ls=':', lw=0.8)
ax.set_xlabel('Lag')
ax.set_ylabel('ACF')
ax.set_title('Return Autocorrelation (lags 1-50)')
ax.legend()
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(f"{PLOTS}/hg_full_analysis.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved hg_full_analysis.png")

# HG stats
print("\n── HYDROGEL_PACK Stats ──")
for d in DAYS:
    sub = hg[hg['day'] == d]
    print(f"  Day {d}: mean={sub['mid_price'].mean():.2f}  std={sub['mid_price'].std():.2f}"
          f"  range=[{sub['mid_price'].min():.0f},{sub['mid_price'].max():.0f}]"
          f"  med_spread={sub['spread'].median():.1f}")
for l in [1, 10, 100, 500]:
    a = hg['mid_price'].autocorr(lag=l)
    print(f"  ACF lag-{l}: {a:.4f}")

# ════════════════════════════════════════════════════════════════════════════════
# 2. VELVETFRUIT_EXTRACT — mid-price, spread, mean reversion
# ════════════════════════════════════════════════════════════════════════════════
vev = prices[prices['product'] == 'VELVETFRUIT_EXTRACT'].copy()
vev['spread'] = vev['ask_price_1'] - vev['bid_price_1']

fig, axes = plt.subplots(4, 1, figsize=(16, 14), sharex=False)
fig.suptitle('VELVETFRUIT_EXTRACT — Full Analysis', fontsize=15, fontweight='bold')

ax = axes[0]
for d, col in zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green']):
    sub = vev[vev['day'] == d]
    ax.plot(sub['timestamp'], sub['mid_price'], lw=0.6, color=col, label=f'Day {d}')
ax.set_ylabel('Mid Price')
ax.set_title('Mid Price by Day')
ax.legend(); ax.grid(alpha=0.3)

ax = axes[1]
for d, col in zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green']):
    sub = vev[vev['day'] == d]
    ax.hist(sub['spread'].dropna(), bins=20, alpha=0.5, color=col, label=f'Day {d}', density=True)
ax.set_xlabel('Bid-Ask Spread (ticks)')
ax.set_ylabel('Density')
ax.set_title('Spread Distribution')
ax.legend(); ax.grid(alpha=0.3)

ax = axes[2]
for d, col in zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green']):
    sub = vev[vev['day'] == d].copy()
    sub['roll_std'] = sub['mid_price'].rolling(100).std()
    ax.plot(sub['timestamp'], sub['roll_std'], lw=0.7, color=col, label=f'Day {d}')
ax.set_ylabel('Rolling 100-tick Std')
ax.set_title('Volatility Clustering')
ax.legend(); ax.grid(alpha=0.3)

ax = axes[3]
lags = range(1, 51)
for d, col, ls in zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green'], ['-', '--', '-.']):
    sub = vev[vev['day'] == d]['mid_price'].diff().dropna()
    acf = [sub.autocorr(lag=l) for l in lags]
    ax.plot(list(lags), acf, color=col, ls=ls, lw=1.2, label=f'Day {d}')
ax.axhline(0, color='black', lw=0.8)
ax.set_xlabel('Lag'); ax.set_ylabel('ACF')
ax.set_title('Return Autocorrelation (lags 1-50)')
ax.legend(); ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(f"{PLOTS}/vev_full_analysis.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved vev_full_analysis.png")

print("\n── VELVETFRUIT_EXTRACT Stats ──")
for d in DAYS:
    sub = vev[vev['day'] == d]
    print(f"  Day {d}: mean={sub['mid_price'].mean():.2f}  std={sub['mid_price'].std():.2f}"
          f"  range=[{sub['mid_price'].min():.0f},{sub['mid_price'].max():.0f}]"
          f"  med_spread={sub['spread'].median():.1f}")
for l in [1, 5, 10, 20]:
    a = vev['mid_price'].autocorr(lag=l)
    print(f"  ACF lag-{l}: {a:.4f}")

# ════════════════════════════════════════════════════════════════════════════════
# 3. VEV VOUCHERS — prices, IV, time-value decay
# ════════════════════════════════════════════════════════════════════════════════

# Black-Scholes for call IV (Newton-Raphson)
from math import log, sqrt, exp
from scipy.stats import norm as snorm

def bs_call(S, K, T, sigma, r=0):
    if T <= 0 or sigma <= 0:
        return max(S - K, 0)
    d1 = (log(S/K) + 0.5*sigma**2*T) / (sigma*sqrt(T))
    d2 = d1 - sigma*sqrt(T)
    return S*snorm.cdf(d1) - K*exp(-r*T)*snorm.cdf(d2)

def implied_vol(C, S, K, T, r=0, tol=1e-5, max_iter=200):
    if C <= 0 or T <= 0:
        return np.nan
    intrinsic = max(S - K, 0)
    if C < intrinsic - tol:
        return np.nan
    sigma = 0.3
    for _ in range(max_iter):
        price = bs_call(S, K, T, sigma, r)
        d1 = (log(S/K) + 0.5*sigma**2*T) / (sigma*sqrt(T)) if sigma > 0 else 0
        vega = S * snorm.pdf(d1) * sqrt(T)
        if abs(vega) < 1e-10:
            break
        sigma -= (price - C) / vega
        if sigma <= 0:
            sigma = 1e-6
        if abs(price - C) < tol:
            break
    return sigma

# TTE: days 1,2,3 correspond to TTE 4,3,2 (Round 4 actual = TTE 1 at submission)
TTE_DAYS = {1: 4, 2: 3, 3: 2}  # trading days remaining at each sample day
ANNUAL_FACTOR = 252.0

fig, axes = plt.subplots(3, 1, figsize=(16, 14))
fig.suptitle('VEV Vouchers — Mid Price by Day', fontsize=15, fontweight='bold')

colors_v = plt.cm.plasma(np.linspace(0.05, 0.95, len(VOUCHERS_SORTED)))

for ax, d in zip(axes, DAYS):
    sub_prices = prices[prices['day'] == d]
    for vch, col in zip(VOUCHERS_SORTED, colors_v):
        vdf = sub_prices[sub_prices['product'] == vch]
        if len(vdf) == 0:
            continue
        ax.plot(vdf['timestamp'], vdf['mid_price'], lw=0.8, color=col, label=vch)
    ax.set_ylabel('Mid Price')
    ax.set_title(f'Day {d} (TTE={TTE_DAYS[d]}d remaining)')
    ax.legend(fontsize=7, ncol=2, loc='upper right')
    ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(f"{PLOTS}/vouchers_mid_price.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved vouchers_mid_price.png")

# Implied vol smile per day
print("\n── Voucher IV Smile ──")
iv_table = {}
vev_spot = {}
for d in DAYS:
    sub_p = prices[prices['day'] == d]
    S_series = sub_p[sub_p['product'] == 'VELVETFRUIT_EXTRACT']['mid_price']
    S = S_series.mean()
    vev_spot[d] = S
    T = TTE_DAYS[d] / ANNUAL_FACTOR
    iv_table[d] = {}
    for vch in VOUCHERS_SORTED:
        K = int(vch.split('_')[1])
        C_series = sub_p[sub_p['product'] == vch]['mid_price']
        if len(C_series) == 0:
            continue
        C = C_series.mean()
        iv = implied_vol(C, S, K, T)
        iv_table[d][vch] = iv
        print(f"  Day {d} {vch:12s} S={S:.0f} K={K} C={C:.2f} IV={iv*100:.1f}%" if iv else
              f"  Day {d} {vch:12s} S={S:.0f} K={K} C={C:.2f} IV=N/A")

# IV smile plot
fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=False)
fig.suptitle('VEV Voucher — Implied Volatility Smile by Day', fontsize=14, fontweight='bold')
for ax, d in zip(axes, DAYS):
    strikes = []
    ivs = []
    for vch in VOUCHERS_SORTED:
        if vch in iv_table[d] and iv_table[d][vch] is not None and not np.isnan(iv_table[d][vch]):
            strikes.append(int(vch.split('_')[1]))
            ivs.append(iv_table[d][vch] * 100)
    ax.plot(strikes, ivs, 'o-', lw=2, ms=6, color='tab:purple')
    ax.axvline(vev_spot[d], color='red', ls='--', lw=1, label=f'Spot={vev_spot[d]:.0f}')
    ax.set_xlabel('Strike')
    ax.set_ylabel('IV (%)')
    ax.set_title(f'Day {d} (TTE={TTE_DAYS[d]}d)')
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(f"{PLOTS}/voucher_iv_smile.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved voucher_iv_smile.png")

# Theta decay: mean mid price per voucher per day
print("\n── Voucher Mean Mid Price by Day ──")
voucher_means = {}
for vch in VOUCHERS_SORTED:
    row = []
    for d in DAYS:
        sub = prices[(prices['product'] == vch) & (prices['day'] == d)]
        row.append(sub['mid_price'].mean() if len(sub) > 0 else np.nan)
    voucher_means[vch] = row
    pct = [(row[i+1]-row[i])/row[i]*100 if row[i] > 0 else np.nan for i in range(len(row)-1)]
    print(f"  {vch:15s} D1={row[0]:.2f} D2={row[1]:.2f} D3={row[2]:.2f}  "
          f"Δ(D1→D2)={pct[0]:+.1f}%  Δ(D2→D3)={pct[1]:+.1f}%")

# Theta decay bar chart
fig, ax = plt.subplots(figsize=(14, 6))
x = np.arange(len(VOUCHERS_SORTED))
width = 0.28
for i, (d, col) in enumerate(zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green'])):
    vals = [voucher_means[v][i] for v in VOUCHERS_SORTED]
    ax.bar(x + i*width, vals, width, label=f'Day {d}', color=col, alpha=0.8)
ax.set_xticks(x + width)
ax.set_xticklabels(VOUCHERS_SORTED, rotation=30, ha='right')
ax.set_ylabel('Mean Mid Price')
ax.set_title('Voucher Mid Price: Day-over-Day Decay')
ax.legend(); ax.grid(alpha=0.3, axis='y')
plt.tight_layout()
plt.savefig(f"{PLOTS}/voucher_decay.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved voucher_decay.png")

# ════════════════════════════════════════════════════════════════════════════════
# 4. COUNTERPARTY ANALYSIS — bot behavior per product
# ════════════════════════════════════════════════════════════════════════════════

print("\n── Counterparty Activity ──")
# overall trade counts per bot (as buyer and seller)
bot_buy = trades.groupby('buyer')['quantity'].agg(['count', 'sum']).rename(
    columns={'count': 'n_buy', 'sum': 'qty_buy'})
bot_sell = trades.groupby('seller')['quantity'].agg(['count', 'sum']).rename(
    columns={'count': 'n_sell', 'sum': 'qty_sell'})
bot_activity = bot_buy.join(bot_sell, how='outer').fillna(0).astype(int)
bot_activity = bot_activity[bot_activity.index.isin(ALL_BOTS)]
bot_activity['total_trades'] = bot_activity['n_buy'] + bot_activity['n_sell']
bot_activity['net_qty'] = bot_activity['qty_buy'] - bot_activity['qty_sell']
print(bot_activity.sort_values('total_trades', ascending=False).to_string())

# per-product counterparty matrix
print("\n── Bot Activity by Product ──")
for prod in PRODUCTS:
    sub = trades[trades['symbol'] == prod]
    if len(sub) == 0:
        continue
    print(f"\n  {prod}: {len(sub)} trades")
    buyers = sub['buyer'].value_counts()
    sellers = sub['seller'].value_counts()
    for bot in ALL_BOTS:
        b = buyers.get(bot, 0)
        s = sellers.get(bot, 0)
        if b + s > 0:
            avg_price = sub[(sub['buyer'] == bot) | (sub['seller'] == bot)]['price'].mean()
            print(f"    {bot:10s}: buy={b:3d}  sell={s:3d}  avg_price={avg_price:.1f}")

# Bot pair trading patterns
print("\n── Bot Pair Frequency ──")
pair_counts = trades.groupby(['buyer', 'seller', 'symbol']).size().reset_index(name='n')
pair_counts = pair_counts[pair_counts['buyer'].isin(ALL_BOTS) & pair_counts['seller'].isin(ALL_BOTS)]
print(pair_counts.sort_values('n', ascending=False).head(30).to_string(index=False))

# Bot activity heatmap (trades per bot pair per product)
fig, axes = plt.subplots(2, 1, figsize=(14, 12))
fig.suptitle('Counterparty Activity Heatmap', fontsize=14, fontweight='bold')

# Panel 1: total buy/sell counts per bot
ax = axes[0]
activity_plot = bot_activity[['n_buy', 'n_sell']].copy()
activity_plot.plot(kind='bar', ax=ax, color=['tab:green', 'tab:red'], alpha=0.8)
ax.set_title('Total Buy vs Sell Trade Count per Bot (all days, all products)')
ax.set_ylabel('# Trades')
ax.set_xlabel('Bot')
ax.tick_params(axis='x', rotation=0)
ax.legend(['Buyer', 'Seller']); ax.grid(alpha=0.3, axis='y')

# Panel 2: activity by product
ax = axes[1]
prod_bot = trades[trades['buyer'].isin(ALL_BOTS)].groupby(['symbol', 'buyer']).size().unstack(fill_value=0)
prod_bot.plot(kind='bar', ax=ax, alpha=0.8, width=0.8)
ax.set_title('Trades per Product per Buyer-Bot')
ax.set_ylabel('# Trades (as buyer)')
ax.set_xlabel('Product')
ax.tick_params(axis='x', rotation=30)
ax.legend(title='Buyer', fontsize=8, loc='upper right'); ax.grid(alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig(f"{PLOTS}/counterparty_heatmap.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved counterparty_heatmap.png")

# ════════════════════════════════════════════════════════════════════════════════
# 5. BOT-SPECIFIC BEHAVIOR — trade timing, price aggressiveness, product focus
# ════════════════════════════════════════════════════════════════════════════════

print("\n── Bot Trade Timing ──")
for bot in ALL_BOTS:
    sub = trades[(trades['buyer'] == bot) | (trades['seller'] == bot)]
    if len(sub) == 0:
        continue
    # inter-trade intervals
    sub_sorted = sub.sort_values(['day', 'timestamp'])
    diffs = sub_sorted.groupby(['day', 'symbol'])['timestamp'].diff().dropna()
    print(f"  {bot}: n_trades={len(sub):4d}  "
          f"median_interval={diffs.median():.0f}  "
          f"min_interval={diffs.min():.0f}  "
          f"products={sorted(sub['symbol'].unique())}")

# Bot price aggressiveness: do they buy high / sell low vs mid?
print("\n── Bot Price Aggressiveness vs Mid ──")
for bot in ALL_BOTS:
    for prod in PRODUCTS:
        sub_t = trades[(trades['symbol'] == prod) &
                       ((trades['buyer'] == bot) | (trades['seller'] == bot))].copy()
        if len(sub_t) < 3:
            continue
        # join with mid price at same timestamp and day (do per-day to avoid sort issues)
        sub_p = prices[(prices['product'] == prod)][['day', 'timestamp', 'mid_price']].copy()
        day_merges = []
        for _d in sub_t['day'].unique():
            lt = sub_t[sub_t['day'] == _d].sort_values('timestamp').reset_index(drop=True)
            lp = sub_p[sub_p['day'] == _d].sort_values('timestamp').reset_index(drop=True)
            if len(lp) == 0:
                continue
            m = pd.merge_asof(lt, lp, on='timestamp', direction='nearest', suffixes=('', '_p'))
            day_merges.append(m)
        if not day_merges:
            continue
        merged = pd.concat(day_merges, ignore_index=True)
        buy_sub = merged[merged['buyer'] == bot]
        sell_sub = merged[merged['seller'] == bot]
        if len(buy_sub) >= 3:
            agg = (buy_sub['price'] - buy_sub['mid_price']).mean()
            print(f"  {bot:10s} BUYS  {prod:25s}: price-vs-mid = {agg:+.2f} ({len(buy_sub)} trades)")
        if len(sell_sub) >= 3:
            agg = (sell_sub['price'] - sell_sub['mid_price']).mean()
            print(f"  {bot:10s} SELLS {prod:25s}: price-vs-mid = {agg:+.2f} ({len(sell_sub)} trades)")

# ════════════════════════════════════════════════════════════════════════════════
# 6. VEV VOUCHER — mean reversion and spread analysis
# ════════════════════════════════════════════════════════════════════════════════

print("\n── Voucher ACF Lag-1 (mean reversion signal) ──")
acf1_data = {}
for vch in VOUCHERS_SORTED:
    sub = prices[prices['product'] == vch]['mid_price'].diff().dropna()
    if len(sub) < 50:
        acf1_data[vch] = np.nan
        continue
    a = sub.autocorr(lag=1)
    acf1_data[vch] = a
    print(f"  {vch:15s}: ACF-1={a:.4f}")

fig, axes = plt.subplots(2, 1, figsize=(14, 10))
fig.suptitle('VEV Vouchers — Mean Reversion & Spread', fontsize=14, fontweight='bold')

ax = axes[0]
vlist = [v for v in VOUCHERS_SORTED if not np.isnan(acf1_data.get(v, np.nan))]
acf_vals = [acf1_data[v] for v in vlist]
colors_bar = ['tab:red' if a < 0 else 'tab:blue' for a in acf_vals]
ax.bar(vlist, acf_vals, color=colors_bar, alpha=0.8)
ax.axhline(0, color='black', lw=0.8)
ax.set_ylabel('ACF Lag-1')
ax.set_title('Mean Reversion Strength (negative = mean-reverting)')
ax.tick_params(axis='x', rotation=30); ax.grid(alpha=0.3, axis='y')

ax = axes[1]
for vch, col in zip(VOUCHERS_SORTED, colors_v):
    sub = prices[prices['product'] == vch].copy()
    if 'ask_price_1' in sub.columns and 'bid_price_1' in sub.columns:
        sub['spread'] = sub['ask_price_1'] - sub['bid_price_1']
        spread_med = sub['spread'].median()
        ax.bar(vch, spread_med, color=col, alpha=0.8)
ax.set_ylabel('Median Bid-Ask Spread')
ax.set_title('Median Spread by Voucher')
ax.tick_params(axis='x', rotation=30); ax.grid(alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig(f"{PLOTS}/voucher_mr_spread.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved voucher_mr_spread.png")

# ════════════════════════════════════════════════════════════════════════════════
# 7. VEV SPOT vs VOUCHER CORRELATION (beta / delta)
# ════════════════════════════════════════════════════════════════════════════════

print("\n── Voucher Beta to VEV Spot ──")
vev_mid = prices[prices['product'] == 'VELVETFRUIT_EXTRACT'][['day', 'timestamp', 'mid_price']].rename(
    columns={'mid_price': 'vev_mid'})

fig, axes = plt.subplots(2, 5, figsize=(20, 8))
axes = axes.flatten()
fig.suptitle('VEV Vouchers — Beta to VELVETFRUIT_EXTRACT Spot', fontsize=14, fontweight='bold')

for i, vch in enumerate(VOUCHERS_SORTED):
    ax = axes[i]
    vdf = prices[prices['product'] == vch][['day', 'timestamp', 'mid_price']].rename(
        columns={'mid_price': 'vch_mid'})
    day_merges2 = []
    for _d in vdf['day'].unique():
        lv = vdf[vdf['day'] == _d].sort_values('timestamp').reset_index(drop=True)
        lr = vev_mid[vev_mid['day'] == _d].sort_values('timestamp').reset_index(drop=True)
        if len(lr) == 0:
            continue
        m = pd.merge_asof(lv, lr, on='timestamp', direction='nearest')
        day_merges2.append(m)
    if not day_merges2:
        ax.set_title(f'{vch}\nNo data'); continue
    merged = pd.concat(day_merges2, ignore_index=True).dropna()
    if len(merged) < 20:
        ax.set_title(f'{vch}\nInsufficent data')
        continue
    # use log-differences for beta
    dx = merged['vev_mid'].diff().dropna()
    dy = merged['vch_mid'].diff().dropna()
    n = min(len(dx), len(dy))
    dx, dy = dx.iloc[:n], dy.iloc[:n]
    slope, intercept, r, p, se = stats.linregress(dx, dy)
    ax.scatter(dx, dy, alpha=0.2, s=2, color='tab:blue')
    xfit = np.linspace(dx.min(), dx.max(), 100)
    ax.plot(xfit, slope*xfit + intercept, 'r-', lw=1.5)
    ax.set_title(f'{vch}\nβ={slope:.2f}  R²={r**2:.2f}')
    ax.set_xlabel('ΔVEV'); ax.set_ylabel('ΔVoucher')
    ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(f"{PLOTS}/voucher_beta.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved voucher_beta.png")

# ════════════════════════════════════════════════════════════════════════════════
# 8. INTRA-DAY DRIFT for all products
# ════════════════════════════════════════════════════════════════════════════════
print("\n── Intra-Day Drift per Product ──")
drift_results = {}
for prod in ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']:
    drift_results[prod] = {}
    for d in DAYS:
        sub = prices[(prices['product'] == prod) & (prices['day'] == d)].copy()
        if len(sub) < 100:
            continue
        slope, intercept, r, p, se = stats.linregress(sub['timestamp'], sub['mid_price'])
        drift_results[prod][d] = {'slope': slope, 'R2': r**2, 'p': p,
                                   'total_move': slope * (sub['timestamp'].max() - sub['timestamp'].min())}
        print(f"  {prod} Day {d}: slope={slope:.6f}/tick  total_move={drift_results[prod][d]['total_move']:+.1f}  R²={r**2:.3f}")

# ════════════════════════════════════════════════════════════════════════════════
# 9. COMBINED OVERVIEW PLOT
# ════════════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(20, 16))
gs = gridspec.GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.35)
fig.suptitle('Round 4 — All Products Overview (3-Day)', fontsize=16, fontweight='bold')

# HG mid price
ax1 = fig.add_subplot(gs[0, 0])
for d, col in zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green']):
    sub = hg[hg['day'] == d]
    ax1.plot(sub['timestamp'], sub['mid_price'], lw=0.7, color=col, label=f'D{d}')
ax1.set_title('HYDROGEL_PACK — Mid Price'); ax1.legend(fontsize=8); ax1.grid(alpha=0.3)

# VEV mid price
ax2 = fig.add_subplot(gs[0, 1])
for d, col in zip(DAYS, ['tab:blue', 'tab:orange', 'tab:green']):
    sub = vev[vev['day'] == d]
    ax2.plot(sub['timestamp'], sub['mid_price'], lw=0.7, color=col, label=f'D{d}')
ax2.set_title('VELVETFRUIT_EXTRACT — Mid Price'); ax2.legend(fontsize=8); ax2.grid(alpha=0.3)

# Voucher mid by day (all strikes, day 1 only)
ax3 = fig.add_subplot(gs[1, :])
sub1 = prices[prices['day'] == 1]
for vch, col in zip(VOUCHERS_SORTED, colors_v):
    vdf = sub1[sub1['product'] == vch]
    ax3.plot(vdf['timestamp'], vdf['mid_price'], lw=0.8, color=col, label=vch, alpha=0.85)
ax3.set_title('All VEV Vouchers — Day 1 Mid Price'); ax3.legend(fontsize=7, ncol=5); ax3.grid(alpha=0.3)

# Trade count per product across days
ax4 = fig.add_subplot(gs[2, 0])
trade_prod_day = trades.groupby(['day', 'symbol']).size().unstack(fill_value=0)
trade_prod_day.T.plot(kind='bar', ax=ax4, alpha=0.8)
ax4.set_title('Trade Count per Product per Day')
ax4.set_ylabel('# Trades'); ax4.tick_params(axis='x', rotation=45)
ax4.legend(title='Day', fontsize=8); ax4.grid(alpha=0.3, axis='y')

# Bot net position (buy qty - sell qty) per product
ax5 = fig.add_subplot(gs[2, 1])
bot_net_prod = trades.copy()
bot_net_prod['buy_qty'] = np.where(bot_net_prod['buyer'].isin(ALL_BOTS), bot_net_prod['quantity'], 0)
bot_net_prod['sell_qty'] = np.where(bot_net_prod['seller'].isin(ALL_BOTS), bot_net_prod['quantity'], 0)
net_by_bot_prod = bot_net_prod.groupby(['buyer'])[['buy_qty']].sum()
net_by_bot_prod2 = bot_net_prod.groupby(['seller'])[['sell_qty']].sum()
net_df = net_by_bot_prod.join(net_by_bot_prod2, how='outer').fillna(0)
net_df = net_df[net_df.index.isin(ALL_BOTS)]
net_df['net'] = net_df['buy_qty'] - net_df['sell_qty']
net_df['net'].plot(kind='bar', ax=ax5, color=['tab:green' if v >= 0 else 'tab:red' for v in net_df['net']], alpha=0.8)
ax5.set_title('Bot Net Qty Accumulated (all products, all days)')
ax5.set_ylabel('Net Qty (positive = net buyer)')
ax5.axhline(0, color='black', lw=0.8)
ax5.tick_params(axis='x', rotation=0); ax5.grid(alpha=0.3, axis='y')

plt.savefig(f"{PLOTS}/r4_overview.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved r4_overview.png")

# ════════════════════════════════════════════════════════════════════════════════
# 10. MARK-01 DEEP DIVE — dominant buyer of vouchers
# ════════════════════════════════════════════════════════════════════════════════
print("\n── Mark 01 Trade Pattern (vouchers) ──")
m1 = trades[(trades['buyer'] == 'Mark 01') | (trades['seller'] == 'Mark 01')]
print(f"  Total trades: {len(m1)}")
print(m1.groupby(['symbol', 'buyer', 'seller'])['quantity'].agg(['count', 'sum', 'mean']).to_string())

# Mark 01 trade timing regularity
print("\n── Mark 01 Timing Regularity ──")
for sym in m1['symbol'].unique():
    sub = m1[m1['symbol'] == sym].sort_values(['day', 'timestamp'])
    diffs = sub.groupby('day')['timestamp'].diff().dropna()
    if len(diffs) > 2:
        print(f"  {sym:20s}: median_interval={diffs.median():.0f}  std={diffs.std():.0f}")

# ════════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ════════════════════════════════════════════════════════════════════════════════
print("\n\n═══ SUMMARY STATISTICS ═══")
print(f"\nAll products: {PRODUCTS}")
print(f"All bots: {ALL_BOTS}")
print(f"Days in data: {DAYS}")
print(f"\nTotal trades: {len(trades)}")
print(f"Trades by day: {trades.groupby('day').size().to_dict()}")
print(f"\nVEV spot by day: {vev_spot}")

print("\nDone. Plots saved to:", PLOTS)
