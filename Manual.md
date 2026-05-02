# Round 1 Manual: "An Intarian Welcome"

This is a sealed-bid auction where you submit last and all bids at/above clearing price execute at that price. The guild buyback is your guaranteed exit.

**DRYLAND_FLAX buyback** = 30/unit (no fees).  
**EMBER_MUSHROOM buyback** = 20/unit (fee = 0.10/unit).

## Strategy
You want to buy at the clearing price and flip immediately to the guild. Since you submit last, you cannot set the clearing price lower by underbidding — you either clear or you don't. But since you're last in time priority at any price level, you need to be at a price where you're the only bidder, or willing to accept partial fill.

### Optimal approach
Submit a large buy order at a price just below the buyback minus fee.

- **FLAX**: buyback = 30. Submit a buy at 29 for max quantity. You profit 1/unit on every fill. Submitting at 30 risks buying from someone else at 30 with no upside. At 29, if the auction clears at 29, you profit 1 each. If it clears at 28 or less, you profit even more (you execute at the clearing price, not your bid).
- **MUSHROOM**: buyback = 20, fee = 0.10, net = 19.90. Submit buy at 19 for max quantity (profit 0.90/unit minimum). Could try 19.5 or 19.90 but since price is likely integer-denominated, 19 is safe.

**Key insight**: Your bid price is your ceiling. The clearing price is the floor for your profit. Go aggressive on quantity since inventory risk is zero — you have a guaranteed buyer.

---

# Round 2 Manual: "Invest & Expand"

**PnL = Research(r) × Scale(s) × Speed_multiplier(sp) − budget_used**  
where:  
- **Research(x)** = 200,000 × ln(1+x) / ln(101)  
- **Scale(x)** = 7x/100  
- **Speed** is rank-based.

## Calculus First
**Budget** = 50,000. Let r, s, sp_pct be your allocations (0-100 each), with r + s + sp_pct ≤ 100.

**Gross PnL** = Research(r) × (7s/100) × speed_mult  
Speed is a prisoner's dilemma: if everyone piles into speed, it's zero-sum. Research and Scale have diminishing/linear returns respectively.

### Numerical optimization
Research grows logarithmically (heavy early returns), Scale is linear, Speed is competitive.  
Fix speed allocation at 0 for a moment. Then:

**Gross = [200k × ln(1+r)/ln(101)] × [7s/100]**  
**Budget used = (r + s) × 500** (since each % costs 500 out of 50,000)  
Maximize over r + s ≤ 100.

Taking the derivative and setting equal shows: optimal unconstrained split between R and S is roughly **r ≈ 60-70, s ≈ 30-40** when ignoring speed.

### Speed is the critical competitive variable
Here's the game theory:

- If most players ignore speed (allocate 0), even small speed investment gets you near the top multiplier (0.9). That's a ~9x multiplier vs 0.1 — worth huge amounts.
- If there's a feeding frenzy on speed, it becomes expensive and zero-sum.

### Recommended allocation
- **Research**: 55%
- **Scale**: 30%
- **Speed**: 15%

#### Rationale
- Speed at 15% is cheap insurance. If few others invest in speed, you likely rank in the top third → multiplier ~0.7+.
- Research at 55 gives near-peak log returns (diminishing returns kick in past ~60%).
- Scale at 30 is enough market breadth.  
**Budget used = 100% (all 50k).**

#### Rough expected PnL
- **Research(55)** = 200k × ln(56)/ln(101) ≈ 200k × 0.826 = 165,200
- **Scale(30)** = 7 × 0.3 = 2.1
- **Speed at rank ~30th percentile** → multiplier ~0.65 (conservative)

**Gross = 165,200 × 2.1 × 0.65 ≈ 225,898**  
**Net = 225,898 − 50,000 = ~175,900**

If speed multiplier goes to 0.9 (you ranked high): **Net ≈ ~262,000.**  
**Do NOT allocate 0 to speed** — the asymmetric upside (0.9 vs 0.1 swing) makes even 10-15% in speed worthwhile.

---

# Round 4 Manual: "Vanilla Just Isn't Exotic Enough"

This is pure derivatives pricing. GBM with **σ = 251% annualized**, zero drift, discrete steps (4/day, 252 days/year). You price and trade at t=0, hold to expiry, mark against 100-sim average fair value.

## Framework
- **σ = 2.51 annualized.** Convert to per-step:  
  **σ_step = 2.51 / sqrt(252 × 4) = 2.51 / 31.75 ≈ 0.079 per step.**
- For a 2-week option:  
  **T = 10 days × 4 steps = 40 steps. T_years = 10/252 = 0.03968.**
- For a 3-week option:  
  **T = 15 days = 60 steps. T_years = 15/252.**

**Black-Scholes** with S₀ = current AETHER_CRYSTAL price, r = 0, σ = 2.51.

## Product-by-Product Strategy

### Vanilla calls/puts
Price them with BS. If market price deviates significantly from BS theoretical, buy cheap / sell rich. With **σ = 251%**, options are extremely expensive in dollar terms — you're working with very high IV.

### Chooser Option (3-week expiry, choose at 2 weeks)
A chooser = max(call, put) at the choice time. By put-call parity, a chooser with choice at time t and expiry T equals:  
**call(T) + put(t, K)** where put has strike K and expires at choice time t.

Concretely:  
**Chooser = Call(3wk, K) + Put(2wk, K).** Compare the displayed price to this synthetic. If the chooser is priced below this replication, buy it — it's a free arbitrage. If above, sell it and buy the synthetic.

### Binary Put
Pays X if S_T < K, zero otherwise.  
**Fair value = X × N(-d2)** where:  
**d2 = [ln(S/K) + (r - σ²/2)T] / (σ√T).**

With zero drift and very high σ, deep ITM binary puts will have value near X, OTM puts near 0. Check if the listed price is below fair value → buy.

### Knock-Out Put
Standard put that dies if S ever hits barrier (discrete monitoring).  
**Fair value < regular put.** The gap depends on how likely the barrier breach is. With **σ = 251%**, barrier breach probability is high for barriers not too far from spot. Price it via Monte Carlo (or analytically with reflection principle).  
- If listed price > fair value → sell (collect premium for issuing the KO risk).  
- If listed price < fair value → buy.

## Execution Checklist

1. Compute BS prices for all vanilla options at current S₀, σ=2.51, r=0.
2. Price the chooser as **Call(3wk) + Put(2wk)** — compare to listed price.
3. Price binary put: **X × N(-d2).**
4. Price KO put via MC simulation (100+ paths with discrete monitoring) — the problem says fair value IS the 100-sim average, so run your own MC.
5. Buy underpriced, sell overpriced, up to stated volume limits.
6. Hedge directional risk: if you end up net long lots of calls and short puts (or vice versa), you have delta exposure. The underlying can be traded — use it to flatten delta if the net exposure is significant.

### Warning on σ = 251%
This means daily moves of **~251%/√252 ≈ 15.8% per day.** In 10 trading days, the distribution of outcomes is extremely wide. Unhedged delta exposure is genuinely dangerous here unlike in P3. Size hedges if you have large directional bets.

### The free money
Any mispricing in the chooser vs its replication is pure arb. Start there. The exotics (binary, KO) likely have wider mispricing than vanillas — that's where most edge lives.