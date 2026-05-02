# Round 5 Product Patterns

Data: Days 2–4, ~200k timestamps/day, 50 products, 10 categories.

---

## Price Dynamics (All Products)

- **ACF[1] = 0.993–1.000** for every product — prices are strongly trending/persistent, not mean-reverting
- **ACF[5] = 0.997–0.9998**, **ACF[10] = 0.980–0.9994**
- No product shows negative autocorrelation (oscillation)
- Intraday direction is inconsistent: same product can be UP day 2, DOWN day 3, UP day 4
- No systematic gap or reset at day boundaries — trends continue across days
- 80–99% of the time, prices deviate >100 units from 10,000 (products maintain distinct price levels)

---

## Category Patterns

### 1. Galaxy Sounds
| Product | Mean Price | Avg Spread | Notes |
|---|---|---|---|
| GALAXY_SOUNDS_DARK_MATTER | ~10,200 | ~9.0 | |
| GALAXY_SOUNDS_BLACK_HOLES | ~11,467 | ~9.0 | Highest mean price in category |
| GALAXY_SOUNDS_PLANETARY_RINGS | ~10,500 | ~9.0 | |
| GALAXY_SOUNDS_SOLAR_WINDS | ~10,300 | ~9.0 | |
| GALAXY_SOUNDS_SOLAR_FLAMES | ~10,200 | ~9.0 | |

- Within-category correlations mostly < 0.7 — products move somewhat independently
- GALAXY_SOUNDS_BLACK_HOLES cross-correlates strongly with OXYGEN_SHAKE_GARLIC (r=0.885) and negatively with PEBBLES_S (r=−0.885)
- Trade volume: 9,025 total per category (avg 733 trades/product)

---

### 2. Sleep Pods
| Product | Mean Price | Avg Spread | Notes |
|---|---|---|---|
| SLEEP_POD_SUEDE | ~10,300 | ~9.5 | |
| SLEEP_POD_LAMB_WOOL | ~10,100 | ~9.5 | |
| SLEEP_POD_POLYESTER | ~11,841 | ~9.5 | Highest mean in category |
| SLEEP_POD_NYLON | ~10,400 | ~9.5 | |
| SLEEP_POD_COTTON | ~11,528 | ~9.5 | |

- **SLEEP_POD_POLYESTER ↔ SLEEP_POD_COTTON**: r=0.875 (strong positive within-category)
- **SLEEP_POD_SUEDE ↔ SLEEP_POD_POLYESTER**: r=0.860 (strong positive)
- SLEEP_POD_POLYESTER cross-correlates with UV_VISOR_AMBER: r=−0.941 (strong negative)
- SLEEP_POD_SUEDE ↔ MICROCHIP_SQUARE: r=0.919 (cross-category)
- Intraday moves >1,000 units recorded (e.g., SLEEP_POD_COTTON rises 1,002 in one day)
- Trade volume: 9,025 total per category

---

### 3. Microchips
| Product | Mean Price | Avg Spread | Notes |
|---|---|---|---|
| MICROCHIP_CIRCLE | ~9,200 | ~8.5 | Asymmetric volume (r=0.274) |
| MICROCHIP_OVAL | ~8,180 | ~7.45 | Tightest spread in category; ACF[1]=1.000 |
| MICROCHIP_SQUARE | ~9,500 | ~8.8 | |
| MICROCHIP_RECTANGLE | ~9,400 | ~8.9 | Asymmetric volume (r=0.218) |
| MICROCHIP_TRIANGLE | ~9,100 | ~8.7 | Only product with clear cyclical component |

- **MICROCHIP_OVAL ↔ MICROCHIP_TRIANGLE**: r=0.871 (positive within-category)
- **MICROCHIP_SQUARE ↔ MICROCHIP_RECTANGLE**: r=−0.882 (strong negative within-category)
- MICROCHIP_CIRCLE and MICROCHIP_RECTANGLE have highly asymmetric bid/ask volumes (bid-ask volume correlation: 0.27 and 0.22 respectively)
- **MICROCHIP_TRIANGLE**: dominant FFT period ≈ 1,667 timestamps — the only product in all 50 with a detectable cyclical pattern
- MICROCHIP_SQUARE cross-correlates negatively with UV_VISOR_AMBER (r=−0.914) and PEBBLES_XS (r=−0.914)
- MICROCHIP_OVAL leads ROBOT_IRONING by ~20 timestamps (r=0.882)
- **Lowest trade volume of any category**: 5,595 total (1,119/product, 569 trades/product) — roughly half of most other categories

---

### 4. Pebbles
| Product | Mean Price | Avg Spread | Notes |
|---|---|---|---|
| PEBBLES_XS | ~7,405 | ~10.5 | Lowest mean price of all 50 products |
| PEBBLES_S | ~8,900 | ~10.0 | |
| PEBBLES_M | ~10,100 | ~10.0 | Closest to 10,000 in category |
| PEBBLES_L | ~10,900 | ~10.5 | |
| PEBBLES_XL | ~13,226 | ~10.5 | Highest mean price of all 50 products |

- Clear monotonic price gradient: XS < S < M < L < XL by size
- **PEBBLES_S ↔ PEBBLES_XL**: r=−0.834 (strong negative within-category)
- **PEBBLES_XS ↔ PEBBLES_S**: r=0.798 (positive)
- PEBBLES_XS cross-correlates with UV_VISOR_AMBER: r=0.958 (strongest cross-category pair in dataset)
- PEBBLES_XS ↔ SLEEP_POD_POLYESTER: r=−0.893 (negative cross-category)
- **Highest trade volume of any category**: 11,415 total (2,283/product, 644 trades/product) — ~26% more than most categories

---

### 5. Robots
| Product | Mean Price | Avg Spread | Notes |
|---|---|---|---|
| ROBOT_VACUUMING | ~10,400 | **6.75** | |
| ROBOT_MOPPING | ~10,300 | **7.0** | ROBOT_LAUNDRY volume correlation: −0.054 |
| ROBOT_DISHES | ~10,200 | **7.35** | |
| ROBOT_LAUNDRY | ~10,100 | **7.17** | Asymmetric volume (bid-ask r=−0.054) |
| ROBOT_IRONING | ~10,000 | **6.39** | Tightest spread of all 50 products |

- **Tightest spreads of all 10 categories** — most liquid category overall
- **ROBOT_VACUUMING ↔ ROBOT_LAUNDRY**: r=0.787 (positive)
- **ROBOT_VACUUMING ↔ ROBOT_IRONING**: r=0.784 (positive)
- **ROBOT_MOPPING ↔ ROBOT_IRONING**: r=−0.815 (strong negative within-category)
- ROBOT_LAUNDRY has near-zero bid/ask volume correlation (r=−0.054) — unusual asymmetric order flow
- MICROCHIP_OVAL leads ROBOT_IRONING by ~20 timestamps (cross-category lead-lag)
- Trade volume: 9,025 total per category

---

### 6. UV Visors
| Product | Mean Price | Avg Spread | Notes |
|---|---|---|---|
| UV_VISOR_YELLOW | ~9,100 | ~9.5 | |
| UV_VISOR_AMBER | ~7,912 | ~9.5 | 2nd lowest mean price; ACF[1]=1.000 |
| UV_VISOR_ORANGE | ~9,400 | ~9.5 | |
| UV_VISOR_RED | ~9,600 | ~9.5 | Trends UP within days |
| UV_VISOR_MAGENTA | ~9,800 | ~9.5 | |

- **UV_VISOR_AMBER is the most correlated product in the dataset** — appears in 12 of the top 30 cross-category pairs
- UV_VISOR_AMBER correlates with PEBBLES_XS (r=+0.958), negatively with SLEEP_POD_POLYESTER (r=−0.941), MICROCHIP_SQUARE (r=−0.914), SNACKPACK_STRAWBERRY (r=−0.894), SLEEP_POD_SUEDE (r=−0.891)
- UV_VISOR_AMBER trends DOWN within days in most observations
- UV_VISOR_RED trends UP within days
- Within-category correlations mostly < 0.7
- Trade volume: 9,025 total per category

---

### 7. Translators
| Product | Mean Price | Avg Spread | Notes |
|---|---|---|---|
| TRANSLATOR_SPACE_GRAY | ~10,100 | ~8.8 | |
| TRANSLATOR_ASTRO_BLACK | ~10,050 | ~8.6 | Trends DOWN intraday |
| TRANSLATOR_ECLIPSE_CHARCOAL | ~9,950 | ~8.7 | |
| TRANSLATOR_GRAPHITE_MIST | ~10,085 | **~7.9** | Most stable: 74.4% within 100 of 10K |
| TRANSLATOR_VOID_BLUE | ~10,100 | ~8.8 | |

- Most stable category by price level — prices cluster near 10,000
- TRANSLATOR_GRAPHITE_MIST: 74.4% of timestamps within 100 units of 10,000 (most stable of all 50 products)
- TRANSLATOR_ASTRO_BLACK trends DOWN intraday
- Within-category correlations mostly < 0.7 — relatively independent products
- Trade volume: 9,025 total per category

---

### 8. Construction Panels
| Product | Mean Price | Avg Spread | Notes |
|---|---|---|---|
| PANEL_1X2 | ~10,200 | ~8.7 | |
| PANEL_2X2 | ~10,600 | ~8.8 | |
| PANEL_1X4 | ~10,900 | ~8.8 | |
| PANEL_2X4 | ~11,265 | ~9.0 | Most volatile: 99.1% outside ±100 of 10K |
| PANEL_4X4 | ~11,500 | ~9.0 | |

- Clear monotonic price gradient: 1X2 < 2X2 < 1X4 < 2X4 < 4X4 by panel area
- PANEL_2X4 and PANEL_4X4 trend UP consistently within days
- PANEL_2X4: 99.1% of timestamps >100 away from 10,000 — most persistently displaced
- Within-category correlations < 0.7 (products move somewhat independently despite price gradient)
- Trade volume: 9,025 total per category

---

### 9. Oxygen Shakes
| Product | Mean Price | Avg Spread | Notes |
|---|---|---|---|
| OXYGEN_SHAKE_MORNING_BREATH | ~10,300 | ~9.5 | |
| OXYGEN_SHAKE_EVENING_BREATH | ~10,100 | ~9.5 | |
| OXYGEN_SHAKE_MINT | ~10,200 | ~9.5 | |
| OXYGEN_SHAKE_CHOCOLATE | ~10,500 | ~9.5 | |
| OXYGEN_SHAKE_GARLIC | ~11,926 | ~9.5 | Highest mean price of any product |

- OXYGEN_SHAKE_GARLIC is a price outlier: mean ~11,926, significantly above all other Oxygen Shakes
- OXYGEN_SHAKE_GARLIC cross-correlates strongly with GALAXY_SOUNDS_BLACK_HOLES (r=0.885)
- Within-category correlations mostly < 0.7
- Trade volume: 9,025 total per category

---

### 10. Snack Packs
| Product | Mean Price | Avg Spread | Notes |
|---|---|---|---|
| SNACKPACK_CHOCOLATE | ~9,843 | **16.47** | |
| SNACKPACK_VANILLA | ~10,097 | **16.87** | Most stable: 62.7% within 100 of 10K |
| SNACKPACK_PISTACHIO | ~9,950 | **15.93** | Trends DOWN intraday |
| SNACKPACK_STRAWBERRY | ~10,100 | **17.83** | Widest spread of all 50 products |
| SNACKPACK_RASPBERRY | ~10,078 | **16.84** | |

- **Widest spreads of all 10 categories** — least efficient/liquid category
- SNACKPACK_STRAWBERRY spread 17.83 is the widest of all 50 products
- Snack Packs are the most price-stable category: SNACKPACK_VANILLA 62.7% within ±100 of 10K
- SNACKPACK_PISTACHIO trends DOWN intraday
- SNACKPACK_STRAWBERRY cross-correlates negatively with UV_VISOR_AMBER (r=−0.894)
- Within-category correlations < 0.7
- Trade volume: 9,025 total per category

---

## Cross-Category Patterns

### Pairs with |r| > 0.85 (strongest cross-category links)

| Product A | Product B | r | Lead-lag (≈20 TS) |
|---|---|---|---|
| PEBBLES_XS | UV_VISOR_AMBER | +0.958 | UV_VISOR_AMBER leads PEBBLES_XS |
| SLEEP_POD_POLYESTER | UV_VISOR_AMBER | −0.941 | SLEEP_POD_POLYESTER leads UV_VISOR_AMBER |
| MICROCHIP_SQUARE | SLEEP_POD_SUEDE | +0.919 | MICROCHIP_SQUARE leads SLEEP_POD_SUEDE |
| MICROCHIP_SQUARE | UV_VISOR_AMBER | −0.914 | |
| MICROCHIP_SQUARE | PEBBLES_XS | −0.914 | |
| SNACKPACK_STRAWBERRY | UV_VISOR_AMBER | −0.894 | |
| PEBBLES_XS | SLEEP_POD_POLYESTER | −0.893 | |
| SLEEP_POD_SUEDE | UV_VISOR_AMBER | −0.891 | |
| GALAXY_SOUNDS_BLACK_HOLES | OXYGEN_SHAKE_GARLIC | +0.885 | GALAXY_SOUNDS_BLACK_HOLES leads OXYGEN_SHAKE_GARLIC |
| GALAXY_SOUNDS_BLACK_HOLES | PEBBLES_S | −0.885 | |
| MICROCHIP_OVAL | ROBOT_IRONING | +0.882 | MICROCHIP_OVAL leads ROBOT_IRONING |

- Total cross-category pairs with |r| > 0.7: **203**
- Total within-category pairs with |r| > 0.7: **19**
- Cross-category correlations far dominate within-category

### Systematic Lead-Lag (≈20 Timestamp Delay)

All high-correlation pairs tested show the leading product moves ~20 timestamps before the follower:
- UV_VISOR_AMBER → PEBBLES_XS (≈20 TS lag)
- SLEEP_POD_POLYESTER → UV_VISOR_AMBER (≈20 TS lag)
- MICROCHIP_SQUARE → SLEEP_POD_SUEDE (≈20 TS lag)
- MICROCHIP_OVAL → ROBOT_IRONING (≈20 TS lag)
- GALAXY_SOUNDS_BLACK_HOLES → OXYGEN_SHAKE_GARLIC (≈20 TS lag)

---

## Liquidity Summary

| Category | Avg Spread | Trade Volume | Notes |
|---|---|---|---|
| Robots | ~7.1 | 9,025 | Most liquid |
| Microchips | ~8.8 | 5,595 | Low volume |
| Translators | ~8.7 | 9,025 | |
| Panels | ~8.8 | 9,025 | |
| Pebbles | ~10.3 | 11,415 | Highest volume |
| Galaxy Sounds | ~9.0 | 9,025 | |
| Sleep Pods | ~9.5 | 9,025 | |
| UV Visors | ~9.5 | 9,025 | |
| Oxygen Shakes | ~9.5 | 9,025 | |
| Snack Packs | ~16.8 | 9,025 | Least liquid (widest spreads) |

---

## Price Level Outliers

**Lowest mean prices:**
1. PEBBLES_XS: ~7,405
2. UV_VISOR_AMBER: ~7,912
3. MICROCHIP_OVAL: ~8,180

**Highest mean prices:**
1. OXYGEN_SHAKE_GARLIC: ~11,926
2. PEBBLES_XL: ~13,226
3. GALAXY_SOUNDS_BLACK_HOLES: ~11,467

**Most stable (closest to 10,000):**
1. SNACKPACK_VANILLA: 62.7% within ±100
2. SNACKPACK_CHOCOLATE: 63.6% within ±100
3. SNACKPACK_RASPBERRY: 63.7% within ±100
4. TRANSLATOR_GRAPHITE_MIST: 74.4% within ±100

**Most displaced (furthest from 10,000):**
1. PANEL_2X4: 99.1% outside ±100
2. PEBBLES_XL: 99.0% outside ±100
3. UV_VISOR_AMBER: 98.2% outside ±100
4. GALAXY_SOUNDS_BLACK_HOLES: 98.3% outside ±100

---

## Special Cases

- **MICROCHIP_TRIANGLE**: Only product with detectable cyclical/periodic component. Dominant FFT period ≈ 1,667 timestamps.
- **UV_VISOR_AMBER**: Most correlated product in dataset — appears in 12 of top 30 cross-category correlation pairs.
- **ROBOT_LAUNDRY**: Only product with negative bid/ask volume correlation (r=−0.054) — unusual asymmetric order flow.
- **MICROCHIP_CIRCLE, MICROCHIP_RECTANGLE**: Both have highly asymmetric bid/ask volumes (r=0.27 and 0.22).
- **PEBBLES (XS→XL)**: Strict monotonic price gradient by size; XS=~7,405, XL=~13,226.
- **PANELS (1X2→4X4)**: Strict monotonic price gradient by area; 1X2=~10,200, 4X4=~11,500.
