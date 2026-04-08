# IMC Prosperity 3 — Master Strategy Reference
## For use as persistent context in IMC Prosperity 4 preparation

**Sources**: Frankfurt Hedgehogs (2nd global), CMU Physics (7th global / 1st USA), Alpha Animals (9th global / 2nd USA)
**Competition scale**: 12,000–13,500 teams, 5 rounds over 15 days, April 2025

---

## SECTION 1: COMPETITION STRUCTURE

Each round lasts 3 days. New products introduced each round; old products remain tradable.
Each round = 1 algorithmic challenge + 1 manual challenge. They are scored independently.
Algorithm is evaluated for 10,000 iterations on the live day. Local backtest = 1,000 iterations on sample data.
The simulation processes orders sequentially each timestep: deep-liquidity makers first → occasional takers → YOUR bot → other bots. Speed is irrelevant. You get a full snapshot of the book every timestep.

**Round schedule P3 (expect similar for P4):**
- Round 1: 3 products (market making basics)
- Round 2: +5 products (ETF arbitrage)
- Round 3: +6 products (options)
- Round 4: +1 product (location arbitrage)
- Round 5: No new products, trader IDs revealed

---

## SECTION 2: ROUND-BY-ROUND PRODUCT BREAKDOWN

### ROUND 1 PRODUCTS

#### Product 1: Rainforest Resin (Fixed Fair Value)
**What it is**: Price permanently fixed at 10,000. Never moves.
**The edge**: Buy below 10,000, sell above 10,000. Pocket the spread.
**Strategy**:
1. Take any sell order priced below 10,000 immediately
2. Take any buy order priced above 10,000 immediately
3. Post passive bids slightly below 10,000 (e.g. 9,998), asks slightly above (e.g. 10,002)
4. If position gets skewed, flatten at exactly 10,000

**Wall Mid concept**: The "true price" proxy — average of the deepest bid wall and ask wall in the book. More stable than raw mid. Use this as fair value for all products, not raw mid-price.

**PnL**: ~39,000 SeaShells/round (Frankfurt). Free money if implemented correctly.
**Position limit**: 50 units

**Key implementation note**: The simulation places deep-liquidity maker bots first, then takers, then your bot. This means you can always see the full book before acting. No need to race. Optimize the edge vs fill probability tradeoff.

---

#### Product 2: Kelp (Slow Random Walk)
**What it is**: True price follows a slow random walk. Small movements (~40 SeaShells over 10,000 steps). Unpredictable direction.
**The insight**: Future price cannot be forecasted. Best estimate of future price = current price.
**Strategy**: Identical to Resin. Treat Wall Mid as fair value and quote around it.

**How to find fair value**:
- CMU method: Find the one persistent large market maker bot. Their mid-price = fair value. Verify by buying 1 unit and checking end-of-day PnL.
- Frankfurt method: Use Wall Mid (average of deepest bid/ask walls in the book).

**PnL**: ~5,000 SeaShells/round (Frankfurt). Lower than Resin due to tighter spreads.

---

#### Product 3: Squid Ink (Noisy + Bot Pattern)
**What it is**: High volatility product with occasional 100+ SeaShell jumps. Tighter bid-ask spread relative to price movement. ALSO contains a hidden bot signal.

**The Olivia Signal (MOST IMPORTANT INSIGHT FROM P3)**:
- One anonymous bot (later revealed as "Olivia") bought exactly 15 units at the daily low every day and sold exactly 15 units at the daily high every day.
- This was detectable by filtering market_trades for quantity == 15 at price extremes.
- Frankfurt identified this in Round 1 and followed it for the entire competition.
- CMU spotted the pattern in Round 2 but didn't build a strategy until Round 5.
- Alpha Animals didn't confirm until Round 5 via trader ID analysis.

**How to detect Olivia (before IDs are revealed)**:
- Track running daily minimum and maximum prices
- Monitor market_trades for trades of a specific fixed quantity (likely 15 in P4)
- When a trade occurs at a daily extreme in the direction you'd expect → flag as signal
- Go long on buy signal, short on sell signal
- Reset signal on invalidation (new extreme in the opposite direction)

**Strategy options (ranked by reliability)**:
1. Follow Olivia signal only — no market making. Low risk, high reliability. (Frankfurt approach)
2. Market make with 10% position, spike-detect for mean reversion on the remaining 90%. (CMU approach)
3. 3-standard-deviation mean reversion on short rolling window. (Alpha Animals approach)

**PnL from Olivia signal alone**: ~8,000 SeaShells/round (Frankfurt)
**PnL if you YOLO into Olivia on Croissants in Round 5**: Up to 120,000 SeaShells (CMU)

**WARNING**: Do NOT aggressively market make Squid Ink without understanding the bot pattern first. Many teams lost more here than they made everywhere else combined.

---

### ROUND 2 PRODUCTS

#### Products: PICNIC_BASKET1, PICNIC_BASKET2, Croissants, Jams, Djembes (ETF Arbitrage)

**What they are**:
- PICNIC_BASKET1 = 6x Croissants + 3x Jams + 1x Djembe
- PICNIC_BASKET2 = 4x Croissants + 2x Jams
- Baskets trade at a premium or discount to their synthetic value (sum of parts)
- This premium is mean-reverting

**The edge**: Basket price temporarily diverges from synthetic value → trade the reversion.

**Price generation insight (Frankfurt)**: The 3 constituents are independently randomized. A mean-reverting noise sequence is added on top to produce basket price. Therefore: BASKETS mean-revert toward constituents, NOT the other way around. Trade baskets, not constituents (unless also using Olivia signal).

**Frankfurt strategy (simpler, more robust)**:
- Fixed threshold model: enter long basket when spread < -threshold, enter short when spread > +threshold
- Fixed thresholds tuned via grid search, NOT dynamic z-scores
- Subtract estimated running premium (mean of spread) to prevent bias
- Integrate Olivia signal: if Olivia is short Croissants, shift basket thresholds to favor short entry
- Exit when spread crosses zero (adjusted for Olivia bias)
- 50% hedge with constituents in final round only
- PnL: 40,000–60,000 SeaShells/round on baskets + 20,000 from Croissants directly

**CMU strategy (more complex, similar results)**:
- Z-score of basket premium vs short rolling window
- Entry at z > 20 or z < -20
- Hedge by trading opposite position in constituents
- Split position limits: 100% of Basket1 limit + 60% of Basket2 limit for basket-vs-basket spread
- Remaining 32% of Basket2 for direct z-score, 8% for market making
- PnL: similar to Frankfurt

**WARNING (Frankfurt)**: Do NOT use moving average crossovers or z-scores without theoretical justification. The generation process is simple mean-reversion — fixed thresholds beat fancy dynamic signals here. If you can't explain WHY a strategy should work from first principles, it's probably overfitting.

**Parameter selection rule**: Pick parameters in flat, stable regions of the grid search landscape, NOT the peak performers. Peak performers overfit. Stable regions generalize.

**Olivia on Croissants**: Olivia also trades Croissants at daily extremes (same qty=15 pattern). Detect her position on Croissants and use it to bias basket thresholds dynamically.

---

### ROUND 3 PRODUCTS

#### Products: Volcanic Rock (underlying) + 5 Vouchers at strikes 9500/9750/10000/10250/10500

**What they are**: Call options on Volcanic Rock. VR trades around 10,000. Options expire within the competition (start with 7 days to expiry, decrease each round).

**Required knowledge**: Black-Scholes model, implied volatility, volatility smile. If these are unfamiliar, study before Round 3.

**The volatility smile**:
- Plot implied volatility (IV) vs moneyness (m_t = log(K/S_t) / sqrt(TTE)) for all 5 strikes
- Fit a quadratic: IV = a*m^2 + b*m + c
- This gives you "fair IV" for any given moneyness
- Subtract fair IV from actual IV → isolated deviations (scalping opportunities)

**Frankfurt strategy (IV Scalping — primary)**:
- Convert IV deviations into price deviations using Black-Scholes
- Buy options when price < theoretical fair price, sell when price > theoretical fair price
- Dynamically expand to more strikes as underlying moves and expiry approaches
- Statistical validation: test for negative 1-lag autocorrelation in returns → confirms exploitable mean-reversion
- PnL: 100,000–150,000 SeaShells/round

**CMU discovery (critical)**:
- Their quadratic fit stopped being accurate on submission day
- Fix: use SHORT ROLLING WINDOW of actual market mid-IV instead of the fitted curve
- The rolling window self-corrects when market IV drifts from the fit
- This fix raised their backtested PnL from 80k to 200k/day

**On hedging (IMPORTANT)**:
- Delta hedging (buying/selling underlying to be direction-neutral) costs 40,000 SeaShells in spread costs per day
- Max realistic loss from being UNHEDGED: ~16,000 SeaShells
- Conclusion: Going UNHEDGED is better EV than paying 40k in hedging costs
- Frankfurt went unhedged from the start. CMU discovered this late.
- Alpha Animals went unhedged accidentally via a bug and made a fortune.

**Mean reversion on Volcanic Rock itself**:
- VR price showed negative autocorrelation (mean-reverting tendency)
- Frankfurt: lightweight EMA + fixed threshold model. Volatile results: +100k, -50k, -10k across rounds.
- CMU: Z-score approach found by Jasper (post-competition). Could have added 150k/day but highly sensitive to hyperparameters.

**Production warning**: CMU's submission failed because Jasper's visualizer caused Lambda memory to exceed 100MB, resetting all rolling windows. NEVER include heavy logging/visualizer code in final submissions.

---

### ROUND 4 PRODUCTS

#### Product: Magnificent Macarons (Location Arbitrage)

**What it is**: Macarons can be traded locally OR converted to/from an external "Pristine Island" market at fixed bid/ask prices, adjusted for:
- Transport fee
- Import tariff (negative = you get PAID to import)
- Export tariff
- Storage fee: 0.1 SeaShells per unit per timestep

**Conversion limit**: 10 units per timestep
**Position limit**: 75 units

**Basic arbitrage**:
- If local ask < external bid - fees → buy locally, export
- If local bid > external ask + fees → import, sell locally

**The hidden taker bot (THE KEY EDGE)**:
- A secret aggressive bot fills sell orders placed at approximately `int(externalBid + 0.5)`
- This bot executes ~60% of eligible offers
- Result: you can sell locally for ~3 SeaShells MORE than the visible local best bid
- Over 10,000 timesteps at 10 units/step: theoretical max ~300,000 SeaShells
- Realistic: 130,000–160,000 SeaShells per round

**Frankfurt final strategy**:
- Place limit sell at `int(externalBid + 0.5)` every timestep
- Quote 10 units (conversion limit) — captures ~60% of theoretical max
- In hindsight: should have quoted 20–30 units to capture surplus on non-fills too

**CMU discovery (post-round)**:
- Were only trading 10 units/step, missing ~4,400 timesteps
- Adjusted to 30 units/step → nearly doubled arb volume
- Max additional downside: 30 × 400 (max price move) = 12,000 SeaShells
- Upside: nearly double PnL

**Sunlight/humidity index**: IMC hints suggested these correlate with Macaron prices. Frankfurt tested a logistic regression with sunlight features and got significant p-values. Chose NOT to implement due to complexity and generalization concerns. Simple arbitrage was far more profitable. Alpha Animals overengineered a regime-switching sunlight model and never shipped it.

**Rule**: When pure arbitrage is available, do the arbitrage. Don't add complexity.

---

### ROUND 5: TRADER IDS REVEALED

**What changes**: You can now see which bot made each trade in market_trades.

**The Olivia confirmation**:
- Directly verify which trades were Olivia's by checking buyer/seller fields
- Update detection logic to use ID directly instead of pattern inference
- Eliminates false positives, catches more genuine signals
- Frankfurt: saved a few hundred SeaShells from cleaner detection

**CMU Round 5 YOLO on Croissants**:
- Normal Croissant position limit: 250
- Long both baskets + direct Croissant position → effective exposure up to 1,050 Croissants
- Olivia's Croissant signal had 40–120 SeaShell daily range
- At 800 extra Croissants: +32k (bad day) to +120k (good day)
- Accepted basket premium risk (~20k realistic max loss) because expected value was near 0
- Strategy: market make baskets while waiting for Olivia signal, then YOLO Croissants on signal

---

## SECTION 3: CROSS-CUTTING STRATEGIES

### The Olivia Pattern — Universal Framework
Every competition has at least one bot with predictable behavior. Look for it immediately in Round 1.

**Detection checklist**:
1. Filter market_trades by fixed quantities (try 1, 5, 10, 15, 20, 25)
2. Plot those trades over price. Do any cluster at daily highs/lows?
3. If yes: track running daily min/max, enter position when suspected Olivia trade occurs at extreme
4. Build invalidation logic: if a new extreme forms contradicting your position, exit and flip

**In Round 5 when IDs reveal**: Switch from pattern detection to direct ID matching.

**Expansion**: Once Olivia is found on one product, check ALL products for the same behavior. She traded Squid Ink AND Croissants in P3.

---

### Position Limit Engineering
Position limits are hard constraints. Hitting them = all orders cancelled for that iteration.

**Always check before sending orders**:
```python
position = state.position.get(product, 0)
max_buy = position_limit - position    # how much more you can buy
max_sell = position_limit + position   # how much more you can sell
```

**CMU's limit utilization approach**:
- Split available position limit across multiple strategy components
- Use each bucket for a different strategy (basket-vs-basket arb, direct z-score, market making)
- Wastes no capacity

---

### Backtesting Philosophy
**Frankfurt rule**: If strategy depends on bot interactions → backtest on official website. If strategy is pure quoting/taking logic → use Jmerle's backtester.

**Never optimize purely for website score** — you will overfit to simulation-specific randomness.

**Parameter selection**: Pick stable regions of grid search landscape (flat, consistent performance), not the global maximum. The global max is almost always overfitted.

**CMU's validation trick**: Buy 1 unit of a product, hold to end of day, compare final PnL to your buy price. This reveals the true internal fair value.

---

### AWS Lambda / Submission Gotchas
1. **Lambda is stateless** — class/global variables may NOT persist between calls. Use `traderData` + `jsonpickle` to serialize state.
2. **traderData is cut at 50,000 characters**. Keep serialized state lean.
3. **Minimize print() statements** — verbose logging causes Lambda timeouts and was a cited cause of failures.
4. **Jasper's visualizer crashed CMU in Round 3** — it caused Lambda to exceed 100MB RAM, resetting all rolling windows. NEVER include heavy tools in final submission.
5. **900ms per run() call limit**. Keep algorithms lightweight.

---

## SECTION 4: PERFORMANCE BENCHMARKS

Use these as targets when validating your strategies in backtests:

| Product | Team | PnL/Round |
|---|---|---|
| Rainforest Resin | Frankfurt | ~39,000 |
| Kelp | Frankfurt | ~5,000 |
| Squid Ink (Olivia) | Frankfurt | ~8,000 |
| Baskets | Frankfurt | 40,000–60,000 |
| Croissants (Olivia) | Frankfurt | ~20,000 |
| IV Scalping (Options) | Frankfurt | 100,000–150,000 |
| Macarons (Location Arb) | Frankfurt | 80,000–100,000 |
| Macarons (Location Arb) | CMU | ~100,000 |
| Croissants YOLO (R5) | CMU | Up to 120,000 |

---

## SECTION 5: THINGS THAT DON'T WORK (AVOID THESE)

1. **Hardcoding bot timestamps** — banned mid-P3, teams were disqualified
2. **Moving average crossovers on mean-reverting products** — no theoretical justification, usually overfitting
3. **Z-scores with rolling volatility normalization** — adds unnecessary complexity when volatility is stable. Use fixed thresholds instead.
4. **Regime-switching models on Macarons (sunlight index)** — Alpha Animals tried this and never shipped. Frankfurt tested it and decided simple arb was far more profitable.
5. **Delta hedging options** — costs 40k in spread costs, max realistic benefit is 16k. Go unhedged.
6. **ML models without rigorous cross-validation** — Frankfurt tested logistic regression on sunlight features but declined to use it due to generalization concerns.
7. **Optimizing for peak backtest PnL** — always overfits. Optimize for stability.
8. **Heavy logging/visualizer tools in production** — crashed CMU's Round 3 submission.

---

## SECTION 6: PHILOSOPHY SUMMARY (FRANKFURT HEDGEHOGS)

1. Understand WHY an edge exists before building it. First principles always.
2. Simple strategies beat complex ones when the underlying structure is simple.
3. Watch the bots. The biggest edges come from detecting and copying predictable bot behavior, not from price prediction.
4. Prioritize robustness over max backtest PnL. Flat performance landscape > global peak.
5. Prepare tools BEFORE the competition. Dashboard, backtester, serialization infrastructure — all ready before Round 1.
6. Never change your approach because of Discord noise. Stay disciplined.

---

## SECTION 7: QUICK REFERENCE — PRODUCT ARCHETYPES

| Round | Archetype | Strategy | Key Risk |
|---|---|---|---|
| R1 | Fixed fair value | Pure market making around known price | Position limit bugs |
| R1 | Slow random walk | Market making, use Wall Mid as fair value | Adverse selection from takers |
| R1 | Noisy + bot signal | Find Olivia, follow her. Don't market make. | Missing the signal |
| R2 | ETF basket | Fixed threshold on basket premium vs synthetic | Overfitting thresholds |
| R3 | Options | IV scalping with rolling mid-IV. Go unhedged. | IV model drift |
| R4 | Location arbitrage | Find hidden taker bot, quote at externalBid+0.5 | Missing the hidden mechanic |
| R5 | All + IDs revealed | Switch Olivia detection to direct ID. YOLO correlated products. | Position limit overflow |

---

## SECTION 8: REPO LINKS

- Frankfurt Hedgehogs: https://github.com/TimoDiehm/imc-prosperity-3 (single polished .py file)
- CMU Physics: https://github.com/chrispyroberts/imc-prosperity-3 (round-by-round folders, EDA notebooks)
- Alpha Animals: https://github.com/CarterT27/imc-prosperity-3 (trader.py + research notebooks)
- P4 Backtester: `pip install prosperity4btest`
- P3 Backtester (reference): `pip install prosperity3bt`