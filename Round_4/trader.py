import json
import math
from statistics import NormalDist
from typing import Any, Dict, List, Optional, Tuple
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


# ─── Logger ──────────────────────────────────────────────────────────────────

class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(self.to_json([
            self.compress_state(state, ""), self.compress_orders(orders), conversions, "", "", "",
        ]))
        max_item_length = (self.max_log_length - base_length) // 3
        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders), conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp, trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        return {sym: [od.buy_orders, od.sell_orders] for sym, od in order_depths.items()}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for t in arr:
                compressed.append([t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp])
        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        co = {}
        for product, obs in observations.conversionObservations.items():
            co[product] = [obs.bidPrice, obs.askPrice, obs.transportFees, obs.exportTariff,
                           obs.importTariff, obs.sugarPrice, obs.sunlightIndex]
        return [observations.plainValueObservations, co]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for arr in orders.values() for o in arr]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."
            if len(json.dumps(candidate)) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1
        return out


logger = Logger()


# ─── Constants ───────────────────────────────────────────────────────────────

VE = "VELVETFRUIT_EXTRACT"
HYDROGEL = "HYDROGEL_PACK"


# ─── Black-Scholes ───────────────────────────────────────────────────────────

class BlackScholes:
    NORM = NormalDist()

    @staticmethod
    def call_price(spot: float, strike: float, tte: float, sigma: float) -> float:
        intrinsic = max(0.0, spot - strike)
        if tte <= 0.0 or sigma <= 0.0 or spot <= 0.0 or strike <= 0.0:
            return intrinsic
        root_t = math.sqrt(tte)
        vol_term = sigma * root_t
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte) / vol_term
        d2 = d1 - vol_term
        return spot * BlackScholes.NORM.cdf(d1) - strike * BlackScholes.NORM.cdf(d2)

    @staticmethod
    def delta(spot: float, strike: float, tte: float, sigma: float) -> float:
        if tte <= 0.0:
            return 1.0 if spot > strike else 0.0
        root_t = math.sqrt(tte)
        vol_term = sigma * root_t
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte) / vol_term
        return BlackScholes.NORM.cdf(d1)


# ─── BotTracker ──────────────────────────────────────────────────────────────

class BotTracker:
    """
    Tracks per-bot activity warmth in [0,1] via exponential decay.
    Mark 38 warmth is shared across HG, VEV_4000, VEV_4500 — when Mark 38
    trades any of them, all three warm up. This solves VEV_4500 cold-start
    (almost no bot-to-bot trades in historical data for that product).
    """
    DECAY = 0.999
    BUMP  = 0.40
    MARK38_PRODUCTS = (HYDROGEL, "VEV_4000", "VEV_4500")

    @staticmethod
    def update(data: dict, market_trades: dict) -> None:
        w38 = float(data.get("warm_m38", 0.0)) * BotTracker.DECAY
        hydro_flow = float(data.get("hydro_flow_m38", 0.0)) * 0.90
        hydro_signed = 0
        for product in BotTracker.MARK38_PRODUCTS:
            for trade in market_trades.get(product, []):
                b = getattr(trade, "buyer", "") or ""
                s = getattr(trade, "seller", "") or ""
                if b == "Mark 38" or s == "Mark 38":
                    w38 = min(1.0, w38 + BotTracker.BUMP)
                # Track Mark 38 signed taker pressure specifically in HYDROGEL.
                if product == HYDROGEL and b == "Mark 38":
                    hydro_signed += int(getattr(trade, "quantity", 0))
                elif product == HYDROGEL and s == "Mark 38":
                    hydro_signed -= int(getattr(trade, "quantity", 0))
        data["warm_m38"] = w38
        hydro_flow += max(-1.0, min(1.0, hydro_signed / 30.0))
        data["hydro_flow_m38"] = max(-1.0, min(1.0, hydro_flow))

        w55 = float(data.get("warm_m55", 0.0)) * BotTracker.DECAY
        ve_flow = float(data.get("ve_flow", 0.0)) * 0.90
        ve_signed = 0
        for trade in market_trades.get(VE, []):
            b = getattr(trade, "buyer", "") or ""
            s = getattr(trade, "seller", "") or ""
            if b == "Mark 55" or s == "Mark 55":
                w55 = min(1.0, w55 + BotTracker.BUMP)
            q = int(getattr(trade, "quantity", 0))
            if q <= 0:
                continue
            # Directional VE pressure proxy from informed/taker bots.
            if b in ("Mark 55", "Mark 67"):
                ve_signed += q
            if s in ("Mark 55", "Mark 49"):
                ve_signed -= q
        data["warm_m55"] = w55
        ve_flow += max(-1.0, min(1.0, ve_signed / 40.0))
        data["ve_flow"] = max(-1.0, min(1.0, ve_flow))


# ─── Trader ──────────────────────────────────────────────────────────────────

class Trader:

    # === HYDROGEL ===
    HYDRO_LIMIT               = 200
    HYDRO_ANCHOR              = 10000.0
    HYDRO_TREND_WINDOW        = 100
    HYDRO_CRASH_BLOCK_LONGS   = 15.0
    HYDRO_RIP_BLOCK_SHORTS    = 15.0
    HYDRO_DISABLE_BID_ABOVE   = 160
    HYDRO_DISABLE_ASK_BELOW   = -160
    HYDRO_ALPHA_BUY_LEVEL     = 9985
    HYDRO_ALPHA_SELL_LEVEL    = 10015

    # === VEV SPOT MM ===
    VE_MM_LIMIT      = 150
    VE_MM_SOFT       = 80
    VE_MM_MIN_SPREAD = 3

    # === DEEP ITM (VEV_4000 / VEV_4500) ===
    DEEP_ITM_CFG = {
        "VEV_4000": {"strike": 4000, "sigma": 0.25, "min_spread": 6,
                     "base_size": 30, "boost": 50, "take_edge": 10.0, "limit": 300},
        "VEV_4500": {"strike": 4500, "sigma": 0.25, "min_spread": 4,
                     "base_size": 25, "boost": 45, "take_edge": 10.0, "limit": 300},
    }

    # === OU (VE spot + VEV_4000/4500 + VEV_5000–5300) ===
    # Extend OU to deep-ITM and spot: delta≈1 options move 1:1 with spot,
    # so a cheap-VEV signal should also buy deep ITM calls (and spot itself).
    OU_PRODUCTS      = (VE, "VEV_4000", "VEV_4500",
                        "VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300")
    OU_PRODUCT_LIMIT = {VE: 200, "VEV_4000": 300, "VEV_4500": 300,
                        "VEV_5000": 300, "VEV_5100": 300,
                        "VEV_5200": 300, "VEV_5300": 300}
    OU_EMA_SPAN   = 1250
    OU_ENTRY_DEV  = 17.423
    OU_ENTRY_DEV_BY_PRODUCT = {
        VE: 17.423,
        "VEV_4000": 30.0,
        "VEV_4500": 30.0,
    }  # stricter deep-ITM trigger to avoid late-day incomplete OU cycles
    OU_LIMIT      = 300   # fallback; OU_PRODUCT_LIMIT takes priority
    OU_STEP       = 300

    # === OTM CYCLING (VEV_5400/5500) — unchanged ===
    VOUCHER_LIMIT        = 300
    ROUND_TTE_DAYS       = 4.0
    DAYS_PER_YEAR        = 252.0
    CLEAR_BAND           = 0.15
    PASSIVE_MIN_SPREAD   = 2.0
    MAX_PASSIVE_ABS_POS  = 180
    SECOND_HALF_EDGE_MULT  = 0.90
    SECOND_HALF_TAKE_MULT  = 1.20
    MARK01_ACTIVE_TICKS    = 500
    MARK01_EDGE_MULT       = 0.65
    MARK01_TAKE_MULT       = 1.3
    MARK22_EDGE_MULT       = 0.55
    MARK22_TAKE_MULT       = 1.5
    MAX_ABS_OPTION_DELTA   = 999.0
    MAX_STRATEGY_SHORT     = 300

    OTM_VOUCHERS = {
        "VEV_5400": {"strike": 5400, "sigma": 0.191, "edge": 0.35,
                     "take_size": 32, "mm_size": 12, "mm_width": 0.85, "clear_size": 18},
        "VEV_5500": {"strike": 5500, "sigma": 0.210, "edge": 0.40,
                     "take_size": 24, "mm_size": 10, "mm_width": 0.90, "clear_size": 16},
    }
    MAX_LONG_BY_PRODUCT  = {"VEV_5300": 100, "VEV_5400": 0, "VEV_5500": 0}
    MAX_SHORT_BY_PRODUCT = {"VEV_5400": 300, "VEV_5500": 300}
    EARLY_MAX_SHORT      = {"VEV_5400": 90,  "VEV_5500": 50}
    MIN_SELL_PRICE       = {"VEV_5400": 18,  "VEV_5500": 7}
    SECOND_ENTRY_MIN_SELL= {"VEV_5400": 16,  "VEV_5500": 7}
    PROFIT_TAKE_ASK      = {"VEV_5400": 12,  "VEV_5500": 4}

    # === VE SWING (for OTM pass cycle detection) ===
    SWING_WINDOW = 80
    SWING_FAST   = 12
    SWING_SLOW   = 48

    # =========================================================================
    # State helpers
    # =========================================================================

    def _load_state(self, trader_data: str) -> dict:
        base = {
            "last_timestamp": -1,
            "hist_day": 0,
            "ve_mid": None,
            "closed_products": [],
            "swing_history": {},
            "ve_cycle_state": "neutral",
            "ve_has_capitulated": False,
            "ve_has_rebounded": False,
            "ve_full_size_armed": False,
            "ve_second_entry_armed": False,
            "warm_m38": 0.0,
            "warm_m55": 0.0,
            "hydro_flow_m38": 0.0,
            "ve_flow": 0.0,
            "ou_signal": 0,
            "ou_signal_deep_itm": 0,
        }
        if trader_data:
            try:
                raw = json.loads(trader_data)
                if isinstance(raw, dict):
                    base.update(raw)
            except Exception:
                pass
        return base

    def _dump_state(self, data: dict) -> str:
        keep = {k: v for k, v in data.items() if not k.startswith("hydro_mid")}
        # keep mid_history but cap it
        if "hydro_mid_history" in data:
            keep["hydro_mid_history"] = data["hydro_mid_history"][-(self.HYDRO_TREND_WINDOW + 2):]
        return json.dumps(keep, separators=(",", ":"))

    def _best_bid_ask(self, od: OrderDepth) -> Tuple[Optional[int], Optional[int], int, int]:
        bb = max(od.buy_orders)  if od.buy_orders  else None
        ba = min(od.sell_orders) if od.sell_orders else None
        bv = int(od.buy_orders.get(bb, 0))       if bb is not None else 0
        av = abs(int(od.sell_orders.get(ba, 0))) if ba is not None else 0
        return bb, ba, bv, av

    def _tte(self, hist_day: int, timestamp: int) -> float:
        return max(self.ROUND_TTE_DAYS - hist_day - timestamp / 999_900.0, 0.20) / self.DAYS_PER_YEAR

    # =========================================================================
    # VE swing / cycle state (for OTM cycling pass)
    # =========================================================================

    def _tmean(self, vals: list, w: int) -> float:
        chunk = vals[-w:] if len(vals) >= w else vals
        return sum(chunk) / len(chunk)

    def _update_ve_swing(self, state: TradingState, data: dict) -> None:
        depth = state.order_depths.get(VE)
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return
        bb, ba, _, _ = self._best_bid_ask(depth)
        if bb is None or ba is None:
            return
        hist = list(data.get("swing_history", {}).get(VE, []))
        hist.append(0.5 * (bb + ba))
        if len(hist) > self.SWING_WINDOW:
            hist = hist[-self.SWING_WINDOW:]
        data.setdefault("swing_history", {})[VE] = hist

    def _ve_snap(self, data: dict) -> Optional[dict]:
        hist = list(data.get("swing_history", {}).get(VE, []))
        if len(hist) < self.SWING_SLOW:
            return None
        prev  = hist[:-1]
        prev2 = hist[:-2]
        fms  = self._tmean(hist,  self.SWING_FAST) - self._tmean(hist,  self.SWING_SLOW)
        pfms = self._tmean(prev,  self.SWING_FAST) - self._tmean(prev,  self.SWING_SLOW) if prev  else fms
        p2fms= self._tmean(prev2, self.SWING_FAST) - self._tmean(prev2, self.SWING_SLOW) if prev2 else pfms
        rhi  = max(hist); rlo = min(hist)
        mid  = hist[-1]
        return {
            "fast_minus_slow": fms,
            "fms_slope":       fms - pfms,
            "fms_accel":       (fms - pfms) - (pfms - p2fms),
            "drawdown":        rhi - mid,
            "rebound":         mid - rlo,
            "rolling_range":   rhi - rlo,
        }

    def _update_ve_cycle(self, data: dict) -> None:
        snap = self._ve_snap(data)
        if snap is None:
            return
        fms = snap["fast_minus_slow"]
        dd  = snap["drawdown"]
        rb  = snap["rebound"]
        rr  = snap["rolling_range"]
        extended_up  = fms >= 0.72  and dd <= 3.0  and rb >= 7.5  and rr >= 8.5
        capitulation = fms <= -4.82 and dd >= 15.5 and rb <= 2.5  and rr >= 17.0
        rebound_1    = (data.get("ve_has_capitulated") and fms >= 1.5
                        and dd <= 9.0 and rb >= 6.0 and rr >= 12.0)
        retest_up    = (data.get("ve_has_rebounded") and fms >= 2.61
                        and dd <= 7.0 and rb >= 14.0 and rr >= 18.0)
        if capitulation:
            data.update({"ve_cycle_state": "capitulation",
                         "ve_has_capitulated": True, "ve_has_rebounded": False})
        elif retest_up:
            data["ve_cycle_state"] = "retest_up"
        elif rebound_1:
            data.update({"ve_cycle_state": "rebound_1", "ve_has_rebounded": True})
        elif extended_up and not data.get("ve_has_capitulated"):
            data["ve_cycle_state"] = "extended_up"
        elif not data.get("ve_has_capitulated"):
            data["ve_cycle_state"] = "neutral"
        if data["ve_cycle_state"] == "extended_up":
            data["ve_full_size_armed"] = True
        if data["ve_cycle_state"] == "retest_up":
            data["ve_second_entry_armed"] = True

    # =========================================================================
    # Module 1: HYDROGEL MM
    # =========================================================================

    def _hydrogel_mm(self, od: OrderDepth, pos: int, data: dict) -> List[Order]:
        orders: List[Order] = []
        warmth     = float(data.get("warm_m38", 0.0))
        quote_size = 12 + int(12 * warmth)   # 12 cold → 24 hot
        lim        = self.HYDRO_LIMIT

        sorted_asks = sorted(od.sell_orders.items())
        sorted_bids = sorted(od.buy_orders.items(), reverse=True)
        if not sorted_asks or not sorted_bids:
            return orders

        best_bid, best_bid_qty = sorted_bids[0]
        best_ask, best_ask_qty = sorted_asks[0]
        mid   = (best_bid + best_ask) / 2.0
        spread= best_ask - best_bid

        # Trend block
        hist: List[float] = data.get("hydro_mid_history", [])
        if not isinstance(hist, list):
            hist = []
        hist.append(mid)
        if len(hist) > self.HYDRO_TREND_WINDOW + 2:
            hist = hist[-(self.HYDRO_TREND_WINDOW + 2):]
        data["hydro_mid_history"] = hist
        trend = mid - float(hist[-(self.HYDRO_TREND_WINDOW + 1)]) if len(hist) > self.HYDRO_TREND_WINDOW else 0.0
        block_long  = trend <= -self.HYDRO_CRASH_BLOCK_LONGS or pos >= self.HYDRO_DISABLE_BID_ABOVE
        block_short = trend >=  self.HYDRO_RIP_BLOCK_SHORTS  or pos <= self.HYDRO_DISABLE_ASK_BELOW

        def buy(desired: int, respect_block: bool = True) -> int:
            if desired <= 0: return 0
            if respect_block and block_long: return 0
            return max(0, min(desired, lim - pos))

        def sell(desired: int, respect_block: bool = True) -> int:
            if desired <= 0: return 0
            if respect_block and block_short: return 0
            return max(0, min(desired, lim + pos))

        # Kalman fair value
        def vwap3(levels):
            cv = cpv = 0
            for i, (px, vol) in enumerate(levels):
                if i >= 3: break
                v = abs(vol); cv += v; cpv += px * v
            return cpv / cv if cv > 0 else None

        bv = vwap3(sorted_bids); av = vwap3(sorted_asks)
        if bv and av:
            tbv = sum(abs(q) for _, q in sorted_bids[:3])
            tav = sum(abs(q) for _, q in sorted_asks[:3])
            obs = (bv * tav + av * tbv) / (tbv + tav) if tbv + tav > 0 else mid
        else:
            obs = mid

        x  = data.get("hydro_kalman_x", obs)
        P  = data.get("hydro_kalman_P", 1.0)
        Q, R = 0.008, 0.3
        Pp = P + Q
        K  = Pp / (Pp + R)
        x  = x + K * (obs - x)
        P  = (1 - K) * Pp
        data["hydro_kalman_x"] = x
        data["hydro_kalman_P"] = P

        # depth-weighted mid EMA (same as original — improves take-side accuracy)
        def vwap_vol(levels, target_vol=50):
            cv = cpv = 0
            for px, vol in levels:
                v = abs(vol); take = min(v, target_vol - cv)
                if take <= 0: break
                cv += take; cpv += px * take
            return cpv / cv if cv > 0 else None

        bvo = vwap_vol(sorted_bids); avo = vwap_vol(sorted_asks)
        depth_mid = (bvo + avo) / 2.0 if bvo and avo else mid
        alpha_ema = 0.12
        ema = data.get("hydro_ema")
        ema = depth_mid if ema is None else alpha_ema * depth_mid + (1 - alpha_ema) * ema
        data["hydro_ema"] = ema

        bq1 = abs(best_bid_qty); aq1 = abs(best_ask_qty)
        imb = (bq1 - aq1) / (bq1 + aq1) if bq1 + aq1 > 0 else 0.0
        pr  = pos / float(lim)
        skew= pr * 2 if pr < 0.6 else pr * 5
        flow = float(data.get("hydro_flow_m38", 0.0))
        fair_raw = 0.6 * x + 0.4 * ema + imb * 0.8 + flow * 4.0
        fair_raw = 0.75 * fair_raw + 0.25 * self.HYDRO_ANCHOR
        fair = fair_raw - skew
        data["hydro_last_fair"] = fair

        # Fast-path: typical 16-tick spread → penny inside (no trend block)
        if spread >= 14:
            flow = float(data.get("hydro_flow_m38", 0.0))
            shift = int(round(14.0 * flow))
            bqty = buy(max(1, quote_size - shift), respect_block=False)
            aqty = sell(max(1, quote_size + shift), respect_block=False)
            if bqty > 0:
                orders.append(Order(HYDROGEL, best_bid + 1, bqty))
            if aqty > 0:
                orders.append(Order(HYDROGEL, best_ask - 1, -aqty))
            return orders

        # Narrow spread: take mispricings, then post
        cur_pos = pos
        for price, qty in sorted_asks:
            if price < fair - 0.5:
                amt = buy(min(-qty, quote_size))
                if amt > 0:
                    orders.append(Order(HYDROGEL, price, amt))
                    cur_pos += amt
        for price, qty in sorted_bids:
            if price > fair + 0.5:
                amt = sell(min(qty, quote_size))
                if amt > 0:
                    orders.append(Order(HYDROGEL, price, -amt))
                    cur_pos -= amt

        bid_px = min(int(math.floor(fair - 0.5)), best_bid + 1)
        ask_px = max(int(math.ceil(fair + 0.5)), best_ask - 1)
        bid_px = min(bid_px, best_ask - 1)
        ask_px = max(ask_px, best_bid + 1)

        bqty = max(0, min(quote_size, lim - cur_pos)) if not block_long  else 0
        aqty = max(0, min(quote_size, lim + cur_pos)) if not block_short else 0
        if bqty > 0:
            orders.append(Order(HYDROGEL, bid_px, bqty))
        if aqty > 0:
            orders.append(Order(HYDROGEL, ask_px, -aqty))
        return orders

    # =========================================================================
    # Module 2: VEV Spot MM
    # =========================================================================

    def _ve_spot_mm(self, state: TradingState, data: dict, result: dict) -> None:
        depth = state.order_depths.get(VE)
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return
        bb = max(depth.buy_orders)
        ba = min(depth.sell_orders)
        if ba - bb < self.VE_MM_MIN_SPREAD:
            return
        bid_px = bb + 1
        ask_px = ba - 1
        if bid_px >= ask_px:
            return

        warmth    = float(data.get("warm_m55", 0.0))
        base_size = 5 + int(10 * warmth)    # 5 cold → 15 hot
        pos       = int(state.position.get(VE, 0))
        hard      = self.VE_MM_LIMIT
        soft      = self.VE_MM_SOFT
        orders: List[Order] = []

        if pos < hard:
            if pos > soft:
                scale = max(0.1, 1.0 - (pos - soft) / float(hard - soft))
                bsz = max(1, int(base_size * scale))
            else:
                bsz = base_size
            qty = min(bsz, hard - pos)
            if qty > 0:
                orders.append(Order(VE, bid_px, qty))

        if pos > -hard:
            if pos < -soft:
                scale = max(0.1, 1.0 - (-pos - soft) / float(hard - soft))
                asz = max(1, int(base_size * scale))
            else:
                asz = base_size
            qty = min(asz, hard + pos)
            if qty > 0:
                orders.append(Order(VE, ask_px, -qty))

        if orders:
            result[VE] = orders

    # =========================================================================
    # Module 3: Deep ITM MM (VEV_4000 / VEV_4500)
    # =========================================================================

    def _deep_itm_mm(self, state: TradingState, data: dict,
                      result: dict, ve_fair: float, tte: float) -> None:
        warmth = float(data.get("warm_m38", 0.0))

        for product, cfg in self.DEEP_ITM_CFG.items():
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue
            bb  = max(depth.buy_orders);  bv = abs(int(depth.buy_orders[bb]))
            ba  = min(depth.sell_orders); av = abs(int(depth.sell_orders[ba]))
            spread = ba - bb

            strike = int(cfg["strike"]); sigma = float(cfg["sigma"])
            lim    = int(cfg["limit"]);  take_edge = float(cfg["take_edge"])
            intrinsic = max(0.0, ve_fair - strike)
            theo = max(intrinsic, BlackScholes.call_price(ve_fair, strike, tte, sigma))

            pos      = int(state.position.get(product, 0))
            pos     += sum(o.quantity for o in result.get(product, []))
            buy_room = max(0, lim - pos)
            sel_room = max(0, lim + pos)
            orders: List[Order] = list(result.get(product, []))

            # Take obvious mispricings
            if ba < theo - take_edge and buy_room > 0:
                qty = min(20, buy_room, av)
                if qty > 0:
                    orders.append(Order(product, ba, qty))
                    pos += qty; buy_room -= qty; sel_room += qty

            if bb > theo + take_edge and sel_room > 0:
                qty = min(20, sel_room, bv)
                if qty > 0:
                    orders.append(Order(product, bb, -qty))
                    pos -= qty; sel_room -= qty; buy_room += qty

            # Penny inside BBO when spread is wide enough
            if spread >= int(cfg["min_spread"]):
                qsize   = int(cfg["base_size"]) + int(int(cfg["boost"]) * warmth)
                inv_skew= pos / float(lim)
                bid_px  = bb + 1
                ask_px  = ba - 1

                if bid_px < ask_px:
                    if buy_room > 0:
                        bscale = max(0.1, 1.0 - max(0.0, inv_skew - 0.5) * 2.0)
                        bqty   = min(max(1, int(qsize * bscale)), buy_room)
                        orders.append(Order(product, bid_px, bqty))

                    if sel_room > 0:
                        ascale = max(0.1, 1.0 - max(0.0, -inv_skew - 0.5) * 2.0)
                        aqty   = min(max(1, int(qsize * ascale)), sel_room)
                        orders.append(Order(product, ask_px, -aqty))

            if orders:
                result[product] = orders

    # =========================================================================
    # Module 4: OU Mean Reversion (VEV_5000–5300) — unchanged
    # =========================================================================

    def _ou_pass(self, state: TradingState, data: dict) -> dict:
        result: dict = {}
        ud = state.order_depths.get(VE)
        if not ud or not ud.buy_orders or not ud.sell_orders:
            return result
        spot  = 0.5 * (max(ud.buy_orders) + min(ud.sell_orders))
        alpha = 2.0 / (self.OU_EMA_SPAN + 1.0)
        ema   = float(data.get("ou_ema", spot))
        ema   = alpha * spot + (1.0 - alpha) * ema
        data["ou_ema"] = ema
        ve_flow = float(data.get("ve_flow", 0.0))
        dev    = (spot - ema) - 10.0 * ve_flow
        signal = int(data.get("ou_signal", 0))
        deep_signal = int(data.get("ou_signal_deep_itm", 0))
        desired= signal
        deep_desired = deep_signal
        if dev > self.OU_ENTRY_DEV:
            desired = -1
        elif dev < -self.OU_ENTRY_DEV:
            desired = 1
        deep_entry_dev = float(self.OU_ENTRY_DEV_BY_PRODUCT["VEV_4000"])
        if dev > deep_entry_dev:
            deep_desired = -1
        elif dev < -deep_entry_dev:
            deep_desired = 1
        b52 = state.order_depths.get("VEV_5200")
        b53 = state.order_depths.get("VEV_5300")
        tight = (b52 and b53 and b52.buy_orders and b52.sell_orders
                 and b53.buy_orders and b53.sell_orders
                 and min(b52.sell_orders) - max(b52.buy_orders) <= 2
                 and min(b53.sell_orders) - max(b53.buy_orders) <= 2)
        if desired != signal and tight:
            signal = desired
        if deep_desired != deep_signal and tight:
            deep_signal = deep_desired
        data["ou_signal"] = signal
        data["ou_signal_deep_itm"] = deep_signal
        for product in self.OU_PRODUCTS:
            d = state.order_depths.get(product)
            if not d or not d.buy_orders or not d.sell_orders:
                continue
            pb = max(d.buy_orders); pa = min(d.sell_orders)
            bv = abs(int(d.buy_orders[pb])); av = abs(int(d.sell_orders[pa]))
            pos   = int(state.position.get(product, 0))
            plim  = int(self.OU_PRODUCT_LIMIT.get(product, self.OU_LIMIT))
            if product in ("VEV_4000", "VEV_4500"):
                target = plim * deep_signal
            else:
                target = plim * signal
            diff   = target - pos
            if diff > 0:
                qty = min(diff, av, self.OU_STEP, plim - pos)
                if qty > 0:
                    result.setdefault(product, []).append(Order(product, int(pa), int(qty)))
            elif diff < 0:
                qty = min(-diff, bv, self.OU_STEP, plim + pos)
                if qty > 0:
                    result.setdefault(product, []).append(Order(product, int(pb), -int(qty)))
        return result

    # =========================================================================
    # Module 5: OTM Cycling (VEV_5400/5500) — unchanged
    # =========================================================================

    def _cap_delta(self, qty: int, du: float, proj: float) -> int:
        if qty <= 0:
            return 0
        if abs(proj + qty * du) <= abs(proj):
            return qty
        room = (self.MAX_ABS_OPTION_DELTA - proj if du > 0 else proj + self.MAX_ABS_OPTION_DELTA)
        if room <= 0:
            return 0
        return max(0, min(qty, int(math.floor(room / abs(du)))))

    def _otm_pass(self, state: TradingState, data: dict,
                   result: dict, ve_fair: float, tte: float) -> None:
        # surface tightness gate (uses VEV_5200/5300 as signal)
        surface_tight = True
        for p in ("VEV_5200", "VEV_5300"):
            d = state.order_depths.get(p)
            if not d or not d.buy_orders or not d.sell_orders:
                surface_tight = False; break
            if min(d.sell_orders) - max(d.buy_orders) > 2:
                surface_tight = False; break

        proj_delta = 0.0
        for product, cfg in self.OTM_VOUCHERS.items():
            pos = int(state.position.get(product, 0))
            if pos != 0:
                proj_delta += pos * BlackScholes.delta(
                    ve_fair, int(cfg["strike"]), tte, float(cfg["sigma"]))

        for product, cfg in self.OTM_VOUCHERS.items():
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue
            bb, ba, bv, av = self._best_bid_ask(depth)
            if bb is None or ba is None:
                continue

            strike = int(cfg["strike"]); sigma = float(cfg["sigma"])
            fair   = max(BlackScholes.call_price(ve_fair, strike, tte, sigma),
                         max(0.0, ve_fair - strike))
            odelta = BlackScholes.delta(ve_fair, strike, tte, sigma)
            spread = float(ba - bb)
            pos    = int(state.position.get(product, 0))

            max_long  = self.MAX_LONG_BY_PRODUCT.get(product, self.VOUCHER_LIMIT)
            buy_room  = max(0, max_long - pos)
            max_short = int(self.MAX_SHORT_BY_PRODUCT.get(product, self.MAX_STRATEGY_SHORT))
            if not data.get("ve_full_size_armed"):
                max_short = min(max_short, int(self.EARLY_MAX_SHORT.get(product, max_short)))
            sel_room  = max(0, min(self.VOUCHER_LIMIT + pos, max_short + pos))

            closed    = set(data.get("closed_products", []))
            armed2    = bool(data.get("ve_second_entry_armed"))
            min_sell  = int((self.SECOND_ENTRY_MIN_SELL if armed2 and product in closed
                             else self.MIN_SELL_PRICE).get(product, -1_000_000))

            buy_edge      = float(cfg["edge"]); sell_edge = float(cfg["edge"])
            buy_take_size = int(cfg["take_size"]); sell_take_size = int(cfg["take_size"])
            if data.get("ve_cycle_state") == "retest_up" and surface_tight:
                buy_edge  *= self.SECOND_HALF_EDGE_MULT
                sell_edge *= self.SECOND_HALF_EDGE_MULT
                buy_take_size  = int(round(buy_take_size  * self.SECOND_HALF_TAKE_MULT))
                sell_take_size = int(round(sell_take_size * self.SECOND_HALF_TAKE_MULT))

            # Mark 01 / Mark 22 intercept
            for trade in state.market_trades.get(product, []):
                buyer  = getattr(trade, "buyer",  "") or ""
                seller = getattr(trade, "seller", "") or ""
                if buyer  == "Mark 01": data[f"m01_{product}"] = state.timestamp
                if seller == "Mark 22": data[f"m22_{product}"] = state.timestamp
            m01_age = state.timestamp - int(data.get(f"m01_{product}", -999999))
            m22_age = state.timestamp - int(data.get(f"m22_{product}", -999999))
            if m22_age <= self.MARK01_ACTIVE_TICKS:
                buy_edge *= self.MARK22_EDGE_MULT
                buy_take_size = int(round(buy_take_size * self.MARK22_TAKE_MULT))
            if m01_age <= self.MARK01_ACTIVE_TICKS:
                buy_edge *= self.MARK01_EDGE_MULT
                buy_take_size = int(round(buy_take_size * self.MARK01_TAKE_MULT))

            orders: List[Order] = []
            taking_profit = False

            pt_ask = self.PROFIT_TAKE_ASK.get(product)
            if pos < 0 and pt_ask is not None and ba <= pt_ask:
                qty = min(-pos, av)
                if qty > 0:
                    taking_profit = True
                    orders.append(Order(product, ba, qty))
                    pos += qty; buy_room -= qty; sel_room += qty
                    proj_delta += qty * odelta
                    if pos >= 0:
                        closed.add(product)
                        data["closed_products"] = sorted(closed)

            if product in closed and pos >= 0 and not armed2:
                if orders: result[product] = orders
                continue
            if taking_profit:
                result[product] = orders
                continue

            if fair - ba >= buy_edge and buy_room > 0:
                qty = self._cap_delta(min(buy_take_size, av, buy_room), odelta, proj_delta)
                if qty > 0:
                    orders.append(Order(product, ba, qty))
                    pos += qty; buy_room -= qty; sel_room += qty
                    proj_delta += qty * odelta

            if bb - fair >= sell_edge and sel_room > 0 and bb >= min_sell:
                qty = self._cap_delta(min(sell_take_size, bv, sel_room), -odelta, proj_delta)
                if qty > 0:
                    orders.append(Order(product, bb, -qty))
                    pos -= qty; sel_room -= qty; buy_room += qty
                    proj_delta -= qty * odelta

            # Clear band
            csz = int(cfg["clear_size"])
            if pos > 0 and bb >= fair - self.CLEAR_BAND:
                qty = min(pos, bv, csz)
                if qty > 0:
                    orders.append(Order(product, bb, -qty))
                    pos -= qty; proj_delta -= qty * odelta
            elif pos < 0 and ba <= fair + self.CLEAR_BAND:
                qty = min(-pos, av, csz)
                if qty > 0:
                    orders.append(Order(product, ba, qty))
                    pos += qty; proj_delta += qty * odelta

            # Passive MM
            if spread >= self.PASSIVE_MIN_SPREAD and abs(pos) < self.MAX_PASSIVE_ABS_POS:
                inv  = pos / self.VOUCHER_LIMIT
                mw   = float(cfg["mm_width"])
                iflr = int(math.ceil(max(0.0, ve_fair - strike)))
                bid_px = max(iflr, min(ba - 1, max(bb, int(math.floor(fair - mw - 0.75 * inv)))))
                ask_px = max(bb + 1, min(ba,      int(math.ceil( fair + mw - 0.75 * inv))))
                if buy_room > 0 and fair - ba > -0.50 * buy_edge and bid_px < ba:
                    qty = self._cap_delta(min(int(cfg["mm_size"]), buy_room), odelta, proj_delta)
                    if qty > 0:
                        orders.append(Order(product, bid_px, qty))
                        pos += qty; buy_room -= qty; proj_delta += qty * odelta
                if sel_room > 0 and bb - fair > -0.50 * sell_edge and ask_px > bb and ask_px >= min_sell:
                    qty = self._cap_delta(min(int(cfg["mm_size"]), sel_room), -odelta, proj_delta)
                    if qty > 0:
                        orders.append(Order(product, ask_px, -qty))
                        pos -= qty; proj_delta -= qty * odelta

            if orders:
                result[product] = orders

    # =========================================================================
    # run()
    # =========================================================================

    def run(self, state: TradingState):
        data = self._load_state(state.traderData)
        result: Dict[Symbol, List[Order]] = {}
        conversions = 0

        # Day boundary reset
        if data["last_timestamp"] >= 0 and state.timestamp < int(data["last_timestamp"]):
            data["hist_day"] = int(data.get("hist_day", 0)) + 1
            data["swing_history"]       = {}
            data["ve_cycle_state"]      = "neutral"
            data["ve_has_capitulated"]  = False
            data["ve_has_rebounded"]    = False
            data["ve_full_size_armed"]  = False
            data["ve_second_entry_armed"] = False
            data["closed_products"]     = []
            data["ou_signal"]           = 0   # positions reset each day; don't inherit stale signal
            data["ou_signal_deep_itm"]  = 0
        data["last_timestamp"] = state.timestamp

        # 1. Bot tracker
        BotTracker.update(data, state.market_trades)

        # 2. Hydrogel MM
        od = state.order_depths.get(HYDROGEL)
        if od and od.buy_orders and od.sell_orders:
            h = self._hydrogel_mm(od, int(state.position.get(HYDROGEL, 0)), data)
            if h:
                result[HYDROGEL] = h
            # Aggressive alpha overlay for large HG dislocations.
            h_pos = int(state.position.get(HYDROGEL, 0))
            h_bid = max(od.buy_orders)
            h_ask = min(od.sell_orders)
            if h_ask < self.HYDRO_ALPHA_BUY_LEVEL and h_pos < self.HYDRO_LIMIT:
                result[HYDROGEL] = [Order(HYDROGEL, int(h_ask), int(self.HYDRO_LIMIT - h_pos))]
            elif h_bid > self.HYDRO_ALPHA_SELL_LEVEL and h_pos > -self.HYDRO_LIMIT:
                result[HYDROGEL] = [Order(HYDROGEL, int(h_bid), int(-self.HYDRO_LIMIT - h_pos))]

        # All options passes need VE depth
        ve_depth = state.order_depths.get(VE)
        if not ve_depth or not ve_depth.buy_orders or not ve_depth.sell_orders:
            trader_data = self._dump_state(data)
            logger.flush(state, result, conversions, trader_data)
            return result, conversions, trader_data

        ve_bb   = max(ve_depth.buy_orders)
        ve_ba   = min(ve_depth.sell_orders)
        ve_fair = 0.5 * (ve_bb + ve_ba)
        data["ve_mid"] = ve_fair
        tte = self._tte(int(data["hist_day"]), state.timestamp)

        # 3. VE cycle state (for OTM pass)
        self._update_ve_swing(state, data)
        self._update_ve_cycle(data)

        # 6. OU pass
        ou = self._ou_pass(state, data)

        # 7. OTM pass
        self._otm_pass(state, data, result, ve_fair, tte)

        # OU overwrites its products
        for product in self.OU_PRODUCTS:
            if product in ou:
                result[product] = ou[product]
            elif product in result:
                del result[product]

        trader_data = self._dump_state(data)
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data
