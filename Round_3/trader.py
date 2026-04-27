import json
import math
from statistics import NormalDist
from typing import Dict, List, Optional, Tuple
from collections import deque
from datamodel import Order, OrderDepth, Symbol, TradingState

VE = "VELVETFRUIT_EXTRACT"
HYDROGEL = "HYDROGEL_PACK"

TRADED_VOUCHERS = {
    "VEV_5000": {"strike": 5000, "sigma": 0.202, "edge": 0.75, "take_size": 10, "mm_size": 4, "mm_width": 1.80, "clear_size": 10, "iv_scalp_threshold": 0.015},
    "VEV_5100": {"strike": 5100, "sigma": 0.197, "edge": 0.70, "take_size": 12, "mm_size": 5, "mm_width": 1.50, "clear_size": 10, "iv_scalp_threshold": 0.015},
    "VEV_5200": {"strike": 5200, "sigma": 0.202, "edge": 0.62, "take_size": 16, "mm_size": 6, "mm_width": 1.20, "clear_size": 12, "iv_scalp_threshold": 0.020},
    "VEV_5300": {"strike": 5300, "sigma": 0.205, "edge": 0.45, "take_size": 28, "mm_size": 10, "mm_width": 0.95, "clear_size": 16, "iv_scalp_threshold": 0.012},
    "VEV_5400": {"strike": 5400, "sigma": 0.191, "edge": 0.35, "take_size": 32, "mm_size": 12, "mm_width": 0.85, "clear_size": 18, "iv_scalp_threshold": 0.012},
    "VEV_5500": {"strike": 5500, "sigma": 0.210, "edge": 0.40, "take_size": 24, "mm_size": 10, "mm_width": 0.90, "clear_size": 16, "iv_scalp_threshold": 0.015},
}


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

    @staticmethod
    def implied_vol_from_price(spot: float, strike: float, tte: float, price: float) -> float:
        if tte <= 0.0 or price <= 0.0:
            return 0.2
        intrinsic = max(0.0, spot - strike)
        if price < intrinsic:
            return 0.01
        low, high = 0.001, 2.0
        for _ in range(50):
            mid = (low + high) / 2.0
            if BlackScholes.call_price(spot, strike, tte, mid) < price:
                low = mid
            else:
                high = mid
            if high - low < 0.0001:
                break
        return (low + high) / 2.0


class Trader:
    # === HYDROGEL CONFIG ===
    HP_LIMIT = 200
    HP_MM_BASE_SIZE = 12
    HP_Z_FIXED_MEAN = 9990.0
    HP_Z_FIXED_STD = 25.0
    HP_Z_ENTRY = 1.0
    HP_Z_QTY = 35
    HP_Z_INV_FADE_POW = 2.0
    HP_Z_MAX_INV_FRAC = 0.85
    HP_TREND_WINDOW = 50
    HP_TREND_BLOCK_TICKS = 12
    HP_HISTORY_KEEP = 60

    # === OPTIONS CONFIG ===
    BLOCKED_SWING_PRODUCTS = {HYDROGEL, "VEV_4000", "VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"}
    OU_PRODUCTS = ("VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300")
    OU_EMA_SPAN = 1250
    OU_ENTRY_DEV = 17.423
    OU_LIMIT = 300
    OU_STEP = 300

    VOUCHER_LIMIT = 300
    ROUND3_TTE_DAYS = 5.0
    DAYS_PER_YEAR = 252.0

    CLEAR_BAND = 0.15
    PASSIVE_ONLY_IF_SPREAD_AT_LEAST = 2.0
    MAX_PASSIVE_ABS_POS = 180
    SECOND_HALF_EDGE_MULT = 0.90
    SECOND_HALF_TAKE_MULT = 1.20

    VE_LIMIT = 0
    MAX_ABS_OPTION_DELTA = 999.0
    MAX_STRATEGY_SHORT = 300
    DELTA_HEDGE_THRESHOLD = 999_999.0
    ENABLED_PRODUCTS = {"VEV_5400", "VEV_5500"}
    MAX_SHORT_BY_PRODUCT = {"VEV_5100": 300, "VEV_5200": 300, "VEV_5300": 300, "VEV_5400": 300, "VEV_5500": 300}
    EARLY_MAX_SHORT_BY_PRODUCT = {"VEV_5100": 0, "VEV_5200": 0, "VEV_5300": 150, "VEV_5400": 90, "VEV_5500": 50}
    MIN_SELL_PRICE_BY_PRODUCT = {"VEV_5100": 183, "VEV_5200": 107, "VEV_5300": 55, "VEV_5400": 18, "VEV_5500": 7}
    SECOND_ENTRY_MIN_SELL_PRICE_BY_PRODUCT = {"VEV_5100": 182, "VEV_5200": 107, "VEV_5300": 53, "VEV_5400": 16, "VEV_5500": 7}
    PROFIT_TAKE_ASK_BY_PRODUCT = {"VEV_5100": 157, "VEV_5200": 88, "VEV_5300": 41, "VEV_5400": 12, "VEV_5500": 4}

    SWING_RULES = {
        HYDROGEL: {"limit": 200, "phases": [{"target": -200}, {"target": 200}, {"target": -200}, {"target": 200}]},
        VE: {"limit": 200, "phases": [{"target": -200}, {"target": 200}, {"target": -200}]},
        "VEV_4000": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_4500": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5000": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5100": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5200": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5300": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5400": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5500": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
    }
    SWING_FEATURE_PRODUCTS = {HYDROGEL, VE, "VEV_4000", "VEV_4500", "VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"}
    SWING_FEATURE_WINDOW = 80
    SWING_FAST_WINDOW = 12
    SWING_SLOW_WINDOW = 48
    STATEFUL_CONTROLLER_BY_PRODUCT = {
        HYDROGEL: "hp", VE: "ve",
        "VEV_4000": "ve", "VEV_4500": "ve", "VEV_5000": "ve", "VEV_5100": "ve",
        "VEV_5200": "ve", "VEV_5300": "ve", "VEV_5400": "ve", "VEV_5500": "ve",
    }
    STATEFUL_SWING_CONFIG = {
        HYDROGEL: {
            0: {"fms_min": 0.0, "dd_max": 5.0, "rb_min": 6.0, "range_min": 8.0, "range_slope_min": 0.0},
            1: {"fms_max": -10.82, "dd_min": 38.0, "rb_max": 4.0, "range_min": 39.0},
            2: {"fms_min": 0.0, "dd_max": 12.0, "rb_min": 21.0, "range_min": 27.0},
            3: {"fms_max": -8.34, "dd_min": 22.5, "rb_max": 9.5, "range_min": 29.0},
        },
        VE: {
            0: {"fms_min": 0.72, "dd_max": 3.0, "rb_min": 7.5, "range_min": 8.5, "range_slope_min": 0.0},
            1: {"fms_max": -4.82, "dd_min": 15.5, "rb_max": 2.5, "range_min": 17.0},
            2: {"fms_min": 2.61, "dd_max": 7.0, "rb_min": 14.0, "range_min": 18.0, "range_slope_min": 0.0},
        },
        "VEV_4000": {
            0: {"range_min": 3.0},
            1: {"fms_max": -3.10, "dd_min": 11.0, "rb_max": 1.0, "range_min": 12.0},
            2: {"fms_min": 2.18, "dd_max": 1.0, "rb_min": 10.5, "range_min": 11.5, "range_slope_min": 0.0},
        },
        "VEV_4500": {
            0: {"range_min": 2.5},
            1: {"fms_max": -3.16, "dd_min": 10.0, "rb_max": 2.0, "range_min": 11.0},
            2: {"fms_min": 2.17, "dd_max": 1.0, "rb_min": 10.0, "range_min": 11.0, "range_slope_min": 0.0},
        },
        "VEV_5000": {
            0: {"fms_min": -0.74, "dd_max": 5.0, "rb_min": 5.67, "range_min": 4.5, "range_slope_min": 0.0},
            1: {"fms_max": -3.05, "dd_min": 10.0, "rb_max": 1.0, "range_min": 11.0},
            2: {"fms_min": 4.72, "dd_max": 4.0, "rb_min": 12.0, "range_min": 12.0, "range_slope_min": 0.0},
        },
        "VEV_5100": {
            0: {"fms_min": -0.70, "dd_max": 3.0, "rb_min": 6.62, "range_min": 4.5, "range_slope_min": 0.0},
            1: {"fms_max": -2.72, "dd_min": 9.0, "rb_max": 1.5, "range_min": 9.5},
            2: {"fms_min": 4.54, "dd_max": 3.5, "rb_min": 11.0, "range_min": 11.0, "range_slope_min": 0.0},
        },
        "VEV_5200": {
            0: {"fms_min": 0.31, "dd_max": 2.0, "rb_min": 7.17, "range_min": 5.0, "range_slope_min": 0.0},
            1: {"fms_max": -2.43, "dd_min": 7.5, "rb_max": 2.0, "range_min": 8.0},
            2: {"fms_min": 3.77, "dd_max": 3.0, "rb_min": 8.0, "range_min": 8.0, "range_slope_min": 0.0},
        },
        "VEV_5300": {
            0: {"fms_min": 0.0, "dd_max": 1.5, "rb_min": 3.0, "range_min": 3.0, "range_slope_min": 0.0},
            1: {"fms_max": -1.25, "dd_min": 4.5, "rb_max": 1.0, "range_min": 5.0},
            2: {"fms_min": 1.96, "dd_max": 2.0, "rb_min": 5.0, "range_min": 5.0, "range_slope_min": 0.0},
        },
        "VEV_5400": {
            0: {"fms_min": 0.0, "dd_max": 1.0, "rb_min": 1.0, "range_min": 1.0, "range_slope_min": 0.0},
            1: {"fms_max": -0.73, "dd_min": 3.0, "rb_max": 0.5, "range_min": 3.0},
            2: {"fms_min": 1.02, "dd_max": 0.5, "rb_min": 3.0, "range_min": 3.0, "range_slope_min": 0.0},
        },
        "VEV_5500": {
            0: {"dd_max": 0.5, "rb_min": 0.5, "range_min": 0.5, "range_slope_min": 0.0},
            1: {"fms_max": -0.17, "dd_min": 1.0, "rb_max": 0.0, "range_min": 1.0},
            2: {"fms_min": 0.55, "dd_max": 1.0, "rb_min": 1.0, "range_min": 1.0, "range_slope_min": 0.0},
        },
    }
    STATEFUL_PHASE_TO_CYCLE = {
        "ve": {0: "extended_up", 1: "capitulation", 2: "retest_up"},
        "hp": {0: "extended_up", 1: "capitulation", 2: "rebound_short", 3: "final_buy"},
    }
    BOT_FLOW_SURFACE_PRODUCTS = ("VEV_5200", "VEV_5300")
    BOT_FLOW_MAX_SPREAD = 2.0

    # =========================================================================
    # State
    # =========================================================================

    def _load_state(self, trader_data: str) -> dict:
        base = {
            "hp_mids": [],
            "last_timestamp": -1,
            "hist_day": 0,
            "ve_mid": None,
            "mr_positions": 0,
            "closed_products": [],
            "swing_history": {},
            "ve_cycle_state": "neutral",
            "ve_has_capitulated": False,
            "ve_has_rebounded": False,
            "ve_full_size_armed": False,
            "ve_second_entry_armed": False,
            "hp_cycle_state": "neutral",
            "hp_has_capitulated": False,
            "hp_has_rebounded": False,
            "hp_has_bottomed": False,
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
        return json.dumps(data, separators=(",", ":"))

    # =========================================================================
    # Hydrogel helpers
    # =========================================================================

    def _hp_taker(self, od: OrderDepth, pos: int, mids: List[float]) -> Tuple[List[Order], int]:
        if not mids:
            return [], 0
        z = (mids[-1] - self.HP_Z_FIXED_MEAN) / self.HP_Z_FIXED_STD
        if abs(z) < self.HP_Z_ENTRY:
            return [], 0

        if len(mids) >= self.HP_TREND_WINDOW:
            move = mids[-1] - mids[-self.HP_TREND_WINDOW]
            if z > 0 and move > self.HP_TREND_BLOCK_TICKS:
                return [], 0
            if z < 0 and move < -self.HP_TREND_BLOCK_TICKS:
                return [], 0

        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        cap = int(self.HP_LIMIT * self.HP_Z_MAX_INV_FRAC)
        inv_factor = max(0.0, 1.0 - abs(pos) / self.HP_LIMIT) ** self.HP_Z_INV_FADE_POW
        orders, taken = [], 0

        if z > self.HP_Z_ENTRY:
            if pos <= -cap:
                return [], 0
            qty = min(int(self.HP_Z_QTY * inv_factor), cap + pos, od.buy_orders[best_bid])
            if qty > 0:
                orders.append(Order(HYDROGEL, best_bid, -qty))
                taken = -qty
        else:
            if pos >= cap:
                return [], 0
            qty = min(int(self.HP_Z_QTY * inv_factor), cap - pos, -od.sell_orders[best_ask])
            if qty > 0:
                orders.append(Order(HYDROGEL, best_ask, qty))
                taken = qty
        return orders, taken

    def _hp_mm_quote(self, od: OrderDepth, pos: int) -> List[Order]:
        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        if best_bid >= best_ask:
            return []

        buy_size = min(self.HP_MM_BASE_SIZE, max(0, self.HP_LIMIT - pos))
        sell_size = min(self.HP_MM_BASE_SIZE, max(0, self.HP_LIMIT + pos))

        if best_ask - best_bid > 1:
            bid_price = best_bid + 1
            ask_price = best_ask - 1
        else:
            bid_price = best_bid
            ask_price = best_ask
        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        orders: List[Order] = []
        if buy_size > 0:
            orders.append(Order(HYDROGEL, bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order(HYDROGEL, ask_price, -sell_size))
        return orders

    # =========================================================================
    # Options helpers
    # =========================================================================

    def _best_bid_ask(self, order_depth: OrderDepth) -> Tuple[Optional[int], Optional[int], int, int]:
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        bid_vol = int(order_depth.buy_orders.get(best_bid, 0)) if best_bid is not None else 0
        ask_vol = abs(int(order_depth.sell_orders.get(best_ask, 0))) if best_ask is not None else 0
        return best_bid, best_ask, bid_vol, ask_vol

    def _tight_surface_gate(self, state: TradingState) -> bool:
        for product in self.BOT_FLOW_SURFACE_PRODUCTS:
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                return False
            best_bid, best_ask, _, _ = self._best_bid_ask(depth)
            if best_bid is None or best_ask is None:
                return False
            if float(best_ask - best_bid) > self.BOT_FLOW_MAX_SPREAD:
                return False
        return True

    def _trailing_mean(self, values: List[float], window: int) -> float:
        chunk = values[-window:] if len(values) >= window else values
        return sum(chunk) / len(chunk)

    def _update_swing_features(self, state: TradingState, data: dict) -> None:
        histories = data.setdefault("swing_history", {})
        for product in self.SWING_FEATURE_PRODUCTS:
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                continue
            best_bid, best_ask, _, _ = self._best_bid_ask(depth)
            if best_bid is None or best_ask is None:
                continue
            mid = 0.5 * (best_bid + best_ask)
            history = list(histories.get(product, []))
            history.append(float(mid))
            if len(history) > self.SWING_FEATURE_WINDOW:
                history = history[-self.SWING_FEATURE_WINDOW:]
            histories[product] = history

    def _current_swing_snapshot(self, data: dict, product: str) -> Optional[dict]:
        history = list(data.get("swing_history", {}).get(product, []))
        if len(history) < self.SWING_SLOW_WINDOW:
            return None
        prev_history = history[:-1]
        prev_prev_history = history[:-2]
        rolling_high = max(history)
        rolling_low = min(history)
        rolling_range = rolling_high - rolling_low
        prev_range = rolling_range
        prev_drawdown = 0.0
        prev_fms = 0.0
        prev_fms_slope = 0.0
        if len(prev_history) >= 1:
            prev_range = max(prev_history) - min(prev_history)
            prev_mid = prev_history[-1]
            prev_drawdown = max(prev_history) - prev_mid
            prev_fast = self._trailing_mean(prev_history, self.SWING_FAST_WINDOW)
            prev_slow = self._trailing_mean(prev_history, self.SWING_SLOW_WINDOW)
            prev_fms = prev_fast - prev_slow
        if len(prev_prev_history) >= 1:
            prev_prev_fast = self._trailing_mean(prev_prev_history, self.SWING_FAST_WINDOW)
            prev_prev_slow = self._trailing_mean(prev_prev_history, self.SWING_SLOW_WINDOW)
            prev_fms_slope = prev_fms - (prev_prev_fast - prev_prev_slow)
        mid = history[-1]
        drawdown = rolling_high - mid
        rebound = mid - rolling_low
        fast = self._trailing_mean(history, self.SWING_FAST_WINDOW)
        slow = self._trailing_mean(history, self.SWING_SLOW_WINDOW)
        fms = fast - slow
        fms_slope = fms - prev_fms
        fms_accel = fms_slope - prev_fms_slope
        drawdown_slope = drawdown - prev_drawdown
        bottomness = (
            0.30 * drawdown - 0.20 * rebound - 2.50 * fms
            + 12.0 * max(0.0, fms_slope) + 10.0 * max(0.0, fms_accel)
            - 4.0 * max(0.0, drawdown_slope)
        )
        return {
            "mid": mid, "drawdown": drawdown, "rebound": rebound,
            "rolling_range": rolling_range, "range_slope": rolling_range - prev_range,
            "fast_minus_slow": fms, "fms_slope": fms_slope, "fms_accel": fms_accel,
            "drawdown_slope": drawdown_slope, "bottomness": bottomness,
        }

    def _stateful_swing_match(self, data: dict, product: str, phase_idx: int) -> bool:
        cfg = self.STATEFUL_SWING_CONFIG.get(product, {}).get(phase_idx)
        if cfg is None:
            return False
        snap = self._current_swing_snapshot(data, product)
        if snap is None:
            return False
        if "fms_min" in cfg and snap["fast_minus_slow"] < float(cfg["fms_min"]):
            return False
        if "fms_max" in cfg and snap["fast_minus_slow"] > float(cfg["fms_max"]):
            return False
        if "dd_min" in cfg and snap["drawdown"] < float(cfg["dd_min"]):
            return False
        if "dd_max" in cfg and snap["drawdown"] > float(cfg["dd_max"]):
            return False
        if "rb_min" in cfg and snap["rebound"] < float(cfg["rb_min"]):
            return False
        if "rb_max" in cfg and snap["rebound"] > float(cfg["rb_max"]):
            return False
        if "range_min" in cfg and snap["rolling_range"] < float(cfg["range_min"]):
            return False
        if "range_slope_min" in cfg and snap["range_slope"] < float(cfg["range_slope_min"]):
            return False
        if "fms_slope_min" in cfg and snap["fms_slope"] < float(cfg["fms_slope_min"]):
            return False
        if "fms_accel_min" in cfg and snap["fms_accel"] < float(cfg["fms_accel_min"]):
            return False
        if "dd_slope_max" in cfg and snap["drawdown_slope"] > float(cfg["dd_slope_max"]):
            return False
        if "bottomness_min" in cfg and snap["bottomness"] < float(cfg["bottomness_min"]):
            return False
        return True

    def _update_ve_cycle_state(self, data: dict) -> None:
        snap = self._current_swing_snapshot(data, VE)
        if snap is None:
            return
        extended_up = (snap["fast_minus_slow"] >= 0.72 and snap["drawdown"] <= 3.0
                       and snap["rebound"] >= 7.5 and snap["rolling_range"] >= 8.5)
        capitulation = (snap["fast_minus_slow"] <= -4.82 and snap["drawdown"] >= 15.5
                        and snap["rebound"] <= 2.5 and snap["rolling_range"] >= 17.0)
        rebound_1 = (data.get("ve_has_capitulated", False)
                     and snap["fast_minus_slow"] >= 1.5 and snap["drawdown"] <= 9.0
                     and snap["rebound"] >= 6.0 and snap["rolling_range"] >= 12.0)
        retest_up = (data.get("ve_has_rebounded", False)
                     and snap["fast_minus_slow"] >= 2.61 and snap["drawdown"] <= 7.0
                     and snap["rebound"] >= 14.0 and snap["rolling_range"] >= 18.0)

        if capitulation:
            data["ve_cycle_state"] = "capitulation"
            data["ve_has_capitulated"] = True
            data["ve_has_rebounded"] = False
        elif retest_up:
            data["ve_cycle_state"] = "retest_up"
        elif rebound_1:
            data["ve_cycle_state"] = "rebound_1"
            data["ve_has_rebounded"] = True
        elif extended_up and not data.get("ve_has_capitulated", False):
            data["ve_cycle_state"] = "extended_up"
        elif not data.get("ve_has_capitulated", False):
            data["ve_cycle_state"] = "neutral"

        if data["ve_cycle_state"] == "extended_up":
            data["ve_full_size_armed"] = True
        if data["ve_cycle_state"] == "retest_up":
            data["ve_second_entry_armed"] = True

    def _update_hp_cycle_state(self, data: dict) -> None:
        snap = self._current_swing_snapshot(data, HYDROGEL)
        if snap is None:
            return
        extended_up = (snap["fast_minus_slow"] >= 0.0 and snap["drawdown"] <= 5.0
                       and snap["rebound"] >= 6.0 and snap["rolling_range"] >= 8.0)
        capitulation = (snap["fast_minus_slow"] <= -10.82 and snap["drawdown"] >= 38.0
                        and snap["rebound"] <= 4.0 and snap["rolling_range"] >= 39.0)
        rebound_short = (data.get("hp_has_capitulated", False)
                         and snap["fast_minus_slow"] >= 0.0 and snap["drawdown"] <= 12.0
                         and snap["rebound"] >= 21.0 and snap["rolling_range"] >= 27.0)
        bottom_build = (snap["fast_minus_slow"] <= -6.0 and snap["drawdown"] >= 30.0
                        and snap["rebound"] <= 12.0 and snap["rolling_range"] >= 35.0
                        and snap["fms_slope"] >= 0.20 and snap["fms_accel"] >= 0.0
                        and snap["drawdown_slope"] <= 0.5 and snap["bottomness"] >= 35.0)
        final_buy = (data.get("hp_has_rebounded", False)
                     and snap["fast_minus_slow"] <= -8.34 and snap["drawdown"] >= 22.5
                     and snap["rebound"] <= 9.5 and snap["rolling_range"] >= 29.0)

        if capitulation:
            data["hp_cycle_state"] = "capitulation"
            data["hp_has_capitulated"] = True
            data["hp_has_rebounded"] = False
            data["hp_has_bottomed"] = False
        elif bottom_build:
            data["hp_cycle_state"] = "bottom_build"
            data["hp_has_capitulated"] = True
            data["hp_has_bottomed"] = True
        elif final_buy:
            data["hp_cycle_state"] = "final_buy"
        elif rebound_short:
            data["hp_cycle_state"] = "rebound_short"
            data["hp_has_rebounded"] = True
        elif extended_up and not data.get("hp_has_capitulated", False):
            data["hp_cycle_state"] = "extended_up"
        elif not data.get("hp_has_capitulated", False):
            data["hp_cycle_state"] = "neutral"

    def _stateful_phase_active(self, data: dict, product: str, phase_idx: int) -> bool:
        controller = self.STATEFUL_CONTROLLER_BY_PRODUCT.get(product)
        if controller is None:
            return False
        phase_map = self.STATEFUL_PHASE_TO_CYCLE.get(controller, {})
        if phase_idx not in phase_map:
            return False
        cycle_name = phase_map[phase_idx]
        cycle_state = data.get(f"{controller}_cycle_state", "neutral")
        if controller == "hp" and phase_idx == 1:
            return cycle_state in {"capitulation", "bottom_build"}
        return cycle_state == cycle_name

    def _time_to_expiry(self, hist_day: int, timestamp: int) -> float:
        remaining_days = max(self.ROUND3_TTE_DAYS - hist_day - timestamp / 999_900.0, 0.20)
        return remaining_days / self.DAYS_PER_YEAR

    def _cap_delta_qty(self, qty: int, per_unit_delta_change: float, projected_delta: float) -> int:
        if qty <= 0:
            return 0
        full_change = qty * per_unit_delta_change
        if abs(projected_delta + full_change) <= abs(projected_delta):
            return qty
        if per_unit_delta_change > 0:
            room = self.MAX_ABS_OPTION_DELTA - projected_delta
        else:
            room = projected_delta + self.MAX_ABS_OPTION_DELTA
        if room <= 0:
            return 0
        return max(0, min(qty, int(math.floor(room / abs(per_unit_delta_change)))))

    def _apply_swing_rules(self, state: TradingState, result: Dict[Symbol, List[Order]], data: dict) -> None:
        for product, rule in self.SWING_RULES.items():
            if product in self.BLOCKED_SWING_PRODUCTS:
                continue
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                continue
            best_bid, best_ask, bid_vol, ask_vol = self._best_bid_ask(depth)
            if best_bid is None or best_ask is None:
                continue
            pending_sell_at_bid = sum(-o.quantity for o in result.get(product, []) if o.quantity < 0 and o.price == best_bid)
            pending_buy_at_ask = sum(o.quantity for o in result.get(product, []) if o.quantity > 0 and o.price == best_ask)
            position = int(state.position.get(product, 0)) + sum(o.quantity for o in result.get(product, []))
            bid_room = max(0, bid_vol - pending_sell_at_bid)
            ask_room = max(0, ask_vol - pending_buy_at_ask)
            limit = int(rule["limit"])

            for phase_idx, phase in enumerate(rule["phases"]):
                if product not in self.STATEFUL_SWING_CONFIG or phase_idx not in self.STATEFUL_SWING_CONFIG[product]:
                    continue
                if not self._stateful_phase_active(data, product, phase_idx):
                    continue
                target = max(-limit, min(limit, int(phase["target"])))
                if target < position:
                    if position <= target or not self._stateful_swing_match(data, product, phase_idx):
                        continue
                    qty = min(position - target, bid_room, limit + position)
                    if qty > 0:
                        result.setdefault(product, []).append(Order(product, best_bid, -qty))
                    break
                if target > position:
                    if position >= target or not self._stateful_swing_match(data, product, phase_idx):
                        continue
                    qty = min(target - position, ask_room, limit - position)
                    if qty > 0:
                        result.setdefault(product, []).append(Order(product, best_ask, qty))
                    break

    def _ou_pass(self, state: TradingState, data: dict) -> Dict[Symbol, List[Order]]:
        result = {}
        u_depth = state.order_depths.get(VE)
        if u_depth is None or not u_depth.buy_orders or not u_depth.sell_orders:
            return result
        u_bid = max(u_depth.buy_orders)
        u_ask = min(u_depth.sell_orders)
        spot = 0.5 * (u_bid + u_ask)

        ema = float(data.get("ou_ema", spot))
        alpha = 2.0 / (self.OU_EMA_SPAN + 1.0)
        ema = alpha * spot + (1.0 - alpha) * ema
        data["ou_ema"] = ema

        dev = spot - ema
        signal = int(data.get("ou_signal", 0))
        desired = signal
        if dev > self.OU_ENTRY_DEV:
            desired = -1
        elif dev < -self.OU_ENTRY_DEV:
            desired = 1

        b5200 = state.order_depths.get("VEV_5200")
        b5300 = state.order_depths.get("VEV_5300")
        tight = (b5200 and b5300 and b5200.buy_orders and b5200.sell_orders
                 and b5300.buy_orders and b5300.sell_orders
                 and min(b5200.sell_orders) - max(b5200.buy_orders) <= 2
                 and min(b5300.sell_orders) - max(b5300.buy_orders) <= 2)

        if desired != signal and tight:
            signal = desired
        data["ou_signal"] = signal

        for product in self.OU_PRODUCTS:
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                continue
            p_bid = max(depth.buy_orders)
            p_ask = min(depth.sell_orders)
            bv = abs(int(depth.buy_orders[p_bid]))
            av = abs(int(depth.sell_orders[p_ask]))
            pos = int(state.position.get(product, 0))
            target = self.OU_LIMIT * signal
            diff = target - pos
            if diff > 0:
                qty = min(diff, av, self.OU_STEP, self.OU_LIMIT - pos)
                if qty > 0:
                    result.setdefault(product, []).append(Order(product, int(p_ask), int(qty)))
            elif diff < 0:
                qty = min(-diff, bv, self.OU_STEP, self.OU_LIMIT + pos)
                if qty > 0:
                    result.setdefault(product, []).append(Order(product, int(p_bid), -int(qty)))
        return result

    # =========================================================================
    # Main
    # =========================================================================

    def run(self, state: TradingState):
        data = self._load_state(state.traderData)
        result: Dict[Symbol, List[Order]] = {}

        # === HYDROGEL PASS ===
        od = state.order_depths.get(HYDROGEL)
        if od and od.buy_orders and od.sell_orders:
            pos = int(state.position.get(HYDROGEL, 0))
            best_bid = max(od.buy_orders)
            best_ask = min(od.sell_orders)
            mid = (best_bid + best_ask) / 2.0
            hp_mids = data["hp_mids"]
            hp_mids.append(mid)
            if len(hp_mids) > self.HP_HISTORY_KEEP:
                del hp_mids[:-self.HP_HISTORY_KEEP]
            take_orders, taken = self._hp_taker(od, pos, hp_mids)
            orders = list(take_orders)
            orders.extend(self._hp_mm_quote(od, pos + taken))
            if orders:
                result[HYDROGEL] = orders

        # === OPTIONS PASS ===
        ou_orders = self._ou_pass(state, data)

        if data["last_timestamp"] >= 0 and state.timestamp < int(data["last_timestamp"]):
            data["hist_day"] = int(data.get("hist_day", 0)) + 1
            data["closed_products"] = []
            data["swing_history"] = {}
            data["ve_cycle_state"] = "neutral"
            data["ve_has_capitulated"] = False
            data["ve_has_rebounded"] = False
            data["ve_full_size_armed"] = False
            data["ve_second_entry_armed"] = False
            data["hp_cycle_state"] = "neutral"
            data["hp_has_capitulated"] = False
            data["hp_has_rebounded"] = False
        data["last_timestamp"] = state.timestamp

        ve_depth = state.order_depths.get(VE)
        if ve_depth is None or not ve_depth.buy_orders or not ve_depth.sell_orders:
            return result, 0, self._dump_state(data)

        ve_best_bid, ve_best_ask, _, _ = self._best_bid_ask(ve_depth)
        if ve_best_bid is None or ve_best_ask is None:
            return result, 0, self._dump_state(data)

        ve_mid = 0.5 * (ve_best_bid + ve_best_ask)
        data["ve_mid"] = ve_mid
        self._update_swing_features(state, data)
        self._update_ve_cycle_state(data)
        self._update_hp_cycle_state(data)
        surface_tight = self._tight_surface_gate(state)
        tte = self._time_to_expiry(int(data["hist_day"]), state.timestamp)

        projected_option_delta = 0.0
        for product, cfg in TRADED_VOUCHERS.items():
            if product not in self.ENABLED_PRODUCTS:
                continue
            position = int(state.position.get(product, 0))
            if position == 0:
                continue
            projected_option_delta += position * BlackScholes.delta(ve_mid, int(cfg["strike"]), tte, float(cfg["sigma"]))

        for product, cfg in TRADED_VOUCHERS.items():
            if product not in self.ENABLED_PRODUCTS:
                continue
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                continue

            best_bid, best_ask, bid_vol, ask_vol = self._best_bid_ask(depth)
            if best_bid is None or best_ask is None:
                continue

            strike = int(cfg["strike"])
            sigma = float(cfg["sigma"])
            fair = max(BlackScholes.call_price(ve_mid, strike, tte, sigma), max(0.0, ve_mid - strike))
            option_delta = BlackScholes.delta(ve_mid, strike, tte, sigma)
            mid = 0.5 * (best_bid + best_ask)
            spread = float(best_ask - best_bid)
            position = int(state.position.get(product, 0))
            buy_room = self.VOUCHER_LIMIT - position
            max_short = int(self.MAX_SHORT_BY_PRODUCT.get(product, self.MAX_STRATEGY_SHORT))
            if not data.get("ve_full_size_armed", False):
                max_short = min(max_short, int(self.EARLY_MAX_SHORT_BY_PRODUCT.get(product, max_short)))
            sell_room = max(0, min(self.VOUCHER_LIMIT + position, max_short + position))
            closed_products = set(data.get("closed_products", []))
            second_entry_armed = bool(data.get("ve_second_entry_armed", False))
            if second_entry_armed and product in closed_products:
                min_sell_price = int(self.SECOND_ENTRY_MIN_SELL_PRICE_BY_PRODUCT.get(product, self.MIN_SELL_PRICE_BY_PRODUCT.get(product, -1_000_000)))
            else:
                min_sell_price = int(self.MIN_SELL_PRICE_BY_PRODUCT.get(product, -1_000_000))

            edge = float(cfg["edge"])
            take_size = int(cfg["take_size"])
            if data.get("ve_cycle_state") == "retest_up" and surface_tight:
                edge *= self.SECOND_HALF_EDGE_MULT
                take_size = int(round(take_size * self.SECOND_HALF_TAKE_MULT))

            edge_buy = fair - best_ask
            edge_sell = best_bid - fair
            orders: List[Order] = []
            taking_profit = False

            profit_take_ask = self.PROFIT_TAKE_ASK_BY_PRODUCT.get(product)
            if position < 0 and profit_take_ask is not None and best_ask <= profit_take_ask:
                qty = min(-position, ask_vol)
                if qty > 0:
                    taking_profit = True
                    orders.append(Order(product, best_ask, qty))
                    position += qty
                    buy_room -= qty
                    sell_room += qty
                    projected_option_delta += qty * option_delta
                    if position >= 0:
                        closed_products.add(product)
                        data["closed_products"] = sorted(closed_products)

            if product in closed_products and position >= 0 and not second_entry_armed:
                if orders:
                    result[product] = orders
                continue
            if taking_profit:
                result[product] = orders
                continue

            if edge_buy >= edge and buy_room > 0:
                qty = min(take_size, ask_vol, buy_room)
                qty = self._cap_delta_qty(qty, option_delta, projected_option_delta)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    position += qty
                    buy_room -= qty
                    sell_room += qty
                    projected_option_delta += qty * option_delta

            if edge_sell >= edge and sell_room > 0 and best_bid >= min_sell_price:
                qty = min(take_size, bid_vol, sell_room)
                qty = self._cap_delta_qty(qty, -option_delta, projected_option_delta)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    position -= qty
                    sell_room -= qty
                    buy_room += qty
                    projected_option_delta -= qty * option_delta

            clear_size = int(cfg["clear_size"])
            if position > 0 and best_bid >= fair - self.CLEAR_BAND:
                qty = min(position, bid_vol, clear_size)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    position -= qty
                    projected_option_delta -= qty * option_delta
            elif position < 0 and best_ask <= fair + self.CLEAR_BAND:
                qty = min(-position, ask_vol, clear_size)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    position += qty
                    projected_option_delta += qty * option_delta

            if spread >= self.PASSIVE_ONLY_IF_SPREAD_AT_LEAST and abs(position) < self.MAX_PASSIVE_ABS_POS:
                inv_skew = position / self.VOUCHER_LIMIT
                mm_width = float(cfg["mm_width"])
                intrinsic_floor = int(math.ceil(max(0.0, ve_mid - strike)))
                bid_px = max(intrinsic_floor, min(best_ask - 1, max(best_bid, int(math.floor(fair - mm_width - 0.75 * inv_skew)))))
                ask_px = max(best_bid + 1, min(best_ask, int(math.ceil(fair + mm_width - 0.75 * inv_skew))))

                if buy_room > 0 and edge_buy > -0.50 * edge and bid_px < best_ask:
                    qty = self._cap_delta_qty(min(int(cfg["mm_size"]), buy_room), option_delta, projected_option_delta)
                    if qty > 0:
                        orders.append(Order(product, bid_px, qty))
                        position += qty
                        buy_room -= qty
                        projected_option_delta += qty * option_delta

                if sell_room > 0 and edge_sell > -0.50 * edge and ask_px > best_bid and ask_px >= min_sell_price:
                    qty = self._cap_delta_qty(min(int(cfg["mm_size"]), sell_room), -option_delta, projected_option_delta)
                    if qty > 0:
                        orders.append(Order(product, ask_px, -qty))
                        position -= qty
                        projected_option_delta -= qty * option_delta

            if orders:
                result[product] = orders

        self._apply_swing_rules(state, result, data)

        for product in self.OU_PRODUCTS:
            if product in ou_orders:
                result[product] = ou_orders[product]
            elif product in result:
                del result[product]

        return result, 0, self._dump_state(data)