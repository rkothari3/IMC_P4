import pandas as pd
import matplotlib.pyplot as plt

# Load data — each day has timestamps starting from 0, keep them separate
days = {
    "Day -2": ("Round_0/prices_round_0_day_-2.csv", "Round_0/trades_round_0_day_-2.csv"),
    "Day -1": ("Round_0/prices_round_0_day_-1.csv", "Round_0/trades_round_0_day_-1.csv"),
}
products = ["EMERALDS", "TOMATOES"]

# 2x2 chart grid
fig, axes = plt.subplots(2, 2, figsize=(16, 8))
fig.suptitle("Round 0 — Mid Price per Day", fontsize=12)


# Outer loop to pick day; inner to pick a prod and then draw prod char for the day in correct chart in the grid. 
# Mid Line (blue line)  
# Shaded blue band (Bid-Ask Spread) - wide band: hard to trade ; narrow: easy to buy/sell without losing money
# Red dots (trades): inside band - normal; outside: unusual
for col, (day_label, (pfile, tfile)) in enumerate(days.items()):
    prices = pd.read_csv(pfile, sep=";")
    trades = pd.read_csv(tfile, sep=";")

    for row, product in enumerate(products):
        ax = axes[row][col]
        p = prices[prices["product"] == product].dropna(subset=["bid_price_1", "ask_price_1"])
        t = trades[trades["symbol"] == product]

        ax.plot(p["timestamp"], p["mid_price"], linewidth=0.8, label="Mid price")
        ax.fill_between(p["timestamp"], p["bid_price_1"], p["ask_price_1"], alpha=0.15, label="Bid-ask spread")
        ax.scatter(t["timestamp"], t["price"], s=10, color="red", zorder=5, label="Trades")

        ax.ticklabel_format(useOffset=False, style="plain")
        ax.set_title(f"{product} — {day_label}")
        ax.set_ylabel("Price")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

for ax in axes[-1]:
    ax.set_xlabel("Timestamp")

plt.tight_layout()
plt.savefig("Round_0/analysis.png", dpi=150)
plt.show()
print("Saved to Round_0/analysis.png")
