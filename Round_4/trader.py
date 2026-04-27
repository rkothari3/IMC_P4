import json
import math
from statistics import NormalDist
from typing import Any, Dict, List, Optional, Tuple
from collections import deque
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

TRADED_VOUCHERS = {
    "VEV_5000": {"strike": 5000, "sigma": 0.202, "edge": 0.75, "take_size": 10,  "mm_size": 4,  "mm_width": 1.80, "clear_size": 10, "iv_scalp_threshold": 0.015},
    "VEV_5100": {"strike": 5100, "sigma": 0.197, "edge": 0.70, "take_size": 12,  "mm_size": 5,  "mm_width": 1.50, "clear_size": 10, "iv_scalp_threshold": 0.015},
    "VEV_5200": {"strike": 5200, "sigma": 0.202, "edge": 0.62, "take_size": 16,  "mm_size": 6,  "mm_width": 1.20, "clear_size": 12, "iv_scalp_threshold": 0.020},
    "VEV_5300": {"strike": 5300, "sigma": 0.205, "edge": 0.45, "take_size": 28,  "mm_size": 10, "mm_width": 0.95, "clear_size": 16, "iv_scalp_threshold": 0.012},
    "VEV_5400": {"strike": 5400, "sigma": 0.191, "edge": 0.35, "take_size": 32,  "mm_size": 12, "mm_width": 0.85, "clear_size": 18, "iv_scalp_threshold": 0.012},
    "VEV_5500": {"strike": 5500, "sigma": 0.210, "edge": 0.40, "take_size": 24,  "mm_size": 10, "mm_width": 0.90, "clear_size": 16, "iv_scalp_threshold": 0.015},
}


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


# ─── Volatility Smile ────────────────────────────────────────────────────────

class VolatilitySmile:
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self.moneyness_history: deque = deque(maxlen=window_size)
        self.iv_history: deque = deque(maxlen=window_size)

    def add_observation(self, moneyness: float, iv: float):
        self.moneyness_history.append(moneyness)
        self.iv_history.append(iv)

    def fit_smile(self) -> Optional[Tuple[List[float], float]]:
        if len(self.iv_history) < 4:
            return None
        moneyness = list(self.moneyness_history)
        iv = list(self.iv_history)
        n = len(iv)
        sum_m = sum(moneyness)
        sum_m2 = sum(m ** 2 for m in moneyness)
        sum_m3 = sum(m ** 3 for m in moneyness)
        sum_m4 = sum(m ** 4 for m in moneyness)
        sum_v = sum(iv)
        sum_vm = sum(v * m for v, m in zip(iv, moneyness))
        sum_vm2 = sum(v * m ** 2 for v, m in zip(iv, moneyness))
        denom = (n * (sum_m2 * sum_m4 - sum_m3 ** 2)
                 - sum_m * (sum_m * sum_m4 - sum_m2 * sum_m3)
                 + sum_m2 * (sum_m * sum_m3 - sum_m2 ** 2))
        if abs(denom) < 1e-10:
            return None
        c = (n * (sum_m2 * sum_vm2 - sum_m3 * sum_vm) - sum_m * (sum_m * sum_vm2 - sum_m2 * sum_vm)
             + sum_m2 * (sum_m * sum_vm - sum_m2 * sum_v)) / denom
        b = (n * (sum_m2 * sum_vm2 - sum_m3 * sum_vm) - sum_v * (sum_m * sum_m4 - sum_m2 * sum_m3)
             + sum_m2 * (sum_m * sum_vm2 - sum_m2 * sum_v)) / denom
        a = (sum_v - b * sum_m - c * sum_m2) / n
        mean_v = sum_v / n
        ss_tot = sum((v - mean_v) ** 2 for v in iv)
        ss_res = sum((iv[i] - (a + b * moneyness[i] + c * moneyness[i] ** 2)) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        return [a, b, c], r_squared

    def get_fair_iv(self, moneyness: float) -> Optional[float]:
        result = self.fit_smile()
        if result is None:
            return None
        a, b, c = result[0]
        return a + b * moneyness + c * moneyness ** 2

    def get_iv_deviation(self, iv: float, moneyness: float) -> Optional[float]:
        fair_iv = self.get_fair_iv(moneyness)
        if fair_iv is None or fair_iv <= 0:
            return None
        return (iv - fair_iv) / fair_iv


# ─── Mean Reversion Detector ─────────────────────────────────────────────────

class MeanReversionDetector:
    def __init__(self, ema_period: int = 20):
        self.ema_period = ema_period
        self.price_history: deque = deque(maxlen=100)
        self.ema_value: Optional[float] = None
        self.returns_history: deque = deque(maxlen=50)

    def add_price(self, price: float):
        if self.price_history:
            ret = (price - self.price_history[-1]) / self.price_history[-1]
            self.returns_history.append(ret)
        self.price_history.append(price)
        alpha = 2.0 / (self.ema_period + 1)
        self.ema_value = price if self.ema_value is None else alpha * price + (1 - alpha) * self.ema_value

    def get_autocorrelation(self, lag: int = 1) -> Optional[float]:
        if len(self.returns_history) < lag + 5:
            return None
        rets = list(self.returns_history)
        r1, r2 = rets[:-lag], rets[lag:]
        mean_1 = sum(r1) / len(r1)
        mean_2 = sum(r2) / len(r2)
        cov = sum((a - mean_1) * (b - mean_2) for a, b in zip(r1, r2))
        var_1 = sum((r - mean_1) ** 2 for r in r1)
        var_2 = sum((r - mean_2) ** 2 for r in r2)
        if var_1 <= 0 or var_2 <= 0:
            return 0.0
        return cov / math.sqrt(var_1 * var_2)

    def get_mean_reversion_signal(self) -> Tuple[str, float]:
        if self.ema_value is None or len(self.price_history) < 5:
            return "neutral", 0.0
        current_price = self.price_history[-1]
        deviation_pct = (current_price - self.ema_value) / self.ema_value
        acf = self.get_autocorrelation(lag=1)
        if acf is None or acf > -0.05:
            return "neutral", 0.0
        normalized_dev = min(abs(deviation_pct) / 0.02, 1.0)
        if deviation_pct > 0.005:
            return "sell", normalized_dev
        elif deviation_pct < -0.005:
            return "buy", normalized_dev
        return "neutral", 0.0


# ─── Trader ──────────────────────────────────────────────────────────────────

class Trader:

    # === HYDROGEL CONFIG (adaptive Kalman fair value — no fixed mean) ===
    HYDRO_LIMIT = 200
    HYDRO_ENABLE_TAKE = True
    HYDRO_ENABLE_PASSIVE = True
    HYDRO_ANCHOR = 10000.0            # soft anchor; only 25% weight, Kalman adapts
    ENABLE_HYDRO_GAP_ALPHA = True
    HYDRO_GAP_THRESHOLD = 1
    HYDRO_GAP_ALPHA_STRENGTH = 2.0
    ENABLE_HYDRO_GAP_SIZE_SKEW = False
    HYDRO_GAP_FAVORED_SIZE_SCALE = 1.50
    HYDRO_GAP_TOXIC_SIZE_SCALE = 0.40
    ENABLE_HYDRO_DYNAMIC_ANCHOR_WEIGHT = False
    HYDRO_ANCHOR_WEIGHT = 0.10
    HYDRO_USE_TREND_BLOCK = True
    HYDRO_TREND_WINDOW = 50
    HYDRO_CRASH_BLOCK_LONGS = 25.0
    HYDRO_RIP_BLOCK_SHORTS = 25.0
    HYDRO_DISABLE_BID_ABOVE_POS = 180
    HYDRO_DISABLE_ASK_BELOW_POS = -180

    # === OPTIONS CONFIG ===
    # VEV_4500 added: historical data showed 1 trade/3 days (illiquid) but actual Round 3
    # had an active MM bot → swing thrashed 358 trades and lost -18,786. Block it.
    BLOCKED_SWING_PRODUCTS = {HYDROGEL, "VEV_4000", "VEV_4500", "VEV_5000", "VEV_5100",
                               "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"}
    OU_PRODUCTS = ("VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300")
    OU_EMA_SPAN = 1250
    OU_ENTRY_DEV = 17.423
    OU_LIMIT = 300
    OU_STEP = 300

    VOUCHER_LIMIT = 300
    ROUND_TTE_DAYS = 4.0      # Round 3 = 5, Round 4 = 4, Round 5 = 3 — update each round
    DAYS_PER_YEAR = 252.0

    CLEAR_BAND = 0.15
    CLEAR_BAND_BY_PRODUCT: dict = {"VEV_5400": 6.0}  # per-product override; falls through to CLEAR_BAND
    MARK01_INTERCEPT_ENABLED = False
    MARK01_EDGE_MULT = 1.0
    MARK01_ACTIVE_TICKS = 500
    PASSIVE_ONLY_IF_SPREAD_AT_LEAST = 2.0
    MAX_PASSIVE_ABS_POS = 180
    SECOND_HALF_EDGE_MULT = 0.90
    SECOND_HALF_TAKE_MULT = 1.20

    MR_POSITION_SIZE = 15
    MR_ENABLED = False
    IV_SCALP_ENABLED = False

    VE_LIMIT = 0
    MAX_ABS_OPTION_DELTA = 999.0
    MAX_STRATEGY_SHORT = 300
    DELTA_HEDGE_THRESHOLD = 999_999.0
    ENABLED_PRODUCTS = {"VEV_5400", "VEV_5500"}
    MAX_SHORT_BY_PRODUCT = {"VEV_5100": 300, "VEV_5200": 300, "VEV_5300": 300, "VEV_5400": 300, "VEV_5500": 300}
    EARLY_MAX_SHORT_BY_PRODUCT = {"VEV_5100": 0, "VEV_5200": 0, "VEV_5300": 150, "VEV_5400": 90, "VEV_5500": 50}
    MIN_SELL_PRICE_BY_PRODUCT = {"VEV_5100": 183, "VEV_5200": 107, "VEV_5300": 55, "VEV_5400": 7, "VEV_5500": 1}
    SECOND_ENTRY_MIN_SELL_PRICE_BY_PRODUCT = {"VEV_5100": 182, "VEV_5200": 107, "VEV_5300": 53, "VEV_5400": 6, "VEV_5500": 1}
    PROFIT_TAKE_ASK_BY_PRODUCT = {"VEV_5100": 157, "VEV_5200": 88, "VEV_5300": 41, "VEV_5400": 5, "VEV_5500": 1}

    SWING_RULES = {
        HYDROGEL: {"limit": 200, "phases": [{"target": -200}, {"target": 200}, {"target": -200}, {"target": 200}]},
        VE:       {"limit": 200, "phases": [{"target": -200}, {"target": 200}, {"target": -200}]},
        "VEV_4000": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_4500": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5000": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5100": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5200": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5300": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5400": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
        "VEV_5500": {"limit": 300, "phases": [{"target": -300}, {"target": 300}, {"target": -300}]},
    }
    SWING_FEATURE_PRODUCTS = {HYDROGEL, VE, "VEV_4000", "VEV_4500", "VEV_5000", "VEV_5100",
                               "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"}
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

    def __init__(self):
        self.volatility_smiles: Dict[str, VolatilitySmile] = {p: VolatilitySmile() for p in TRADED_VOUCHERS}
        self.mean_reverter = MeanReversionDetector(ema_period=20)

    # =========================================================================
    # State
    # =========================================================================

    def _load_state(self, trader_data: str) -> dict:
        base = {
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
    # Hydrogel — adaptive Kalman fair-value market maker (hydrogel_alpha)
    # =========================================================================

    def get_hydrogel_orders(self, product: str, order_depth: OrderDepth,
                            current_pos: int, state_data: dict) -> List[Order]:
        orders: List[Order] = []
        effective_limit = self.HYDRO_LIMIT

        sorted_asks = sorted(order_depth.sell_orders.items())
        sorted_bids = sorted(order_depth.buy_orders.items(), reverse=True)

        last_fair = state_data.get("hydro_last_fair",
                                   state_data.get("hydro_kalman_x", self.HYDRO_ANCHOR))

        if not sorted_asks and not sorted_bids:
            return orders

        if not sorted_asks:
            best_bid = sorted_bids[0][0]
            buy_price = best_bid + 1
            if self.HYDRO_ENABLE_PASSIVE and last_fair - buy_price >= 2 and current_pos < self.HYDRO_DISABLE_BID_ABOVE_POS:
                buy_qty = min(8, effective_limit - current_pos)
                if buy_qty > 0:
                    orders.append(Order(product, buy_price, buy_qty))
            if self.HYDRO_ENABLE_TAKE and current_pos > 0:
                unwind_qty = min(8, current_pos)
                if unwind_qty > 0:
                    orders.append(Order(product, int(math.ceil(last_fair + 1)), -unwind_qty))
            return orders

        if not sorted_bids:
            best_ask = sorted_asks[0][0]
            sell_price = best_ask - 1
            if self.HYDRO_ENABLE_PASSIVE and sell_price - last_fair >= 2 and current_pos > self.HYDRO_DISABLE_ASK_BELOW_POS:
                sell_qty = min(8, effective_limit + current_pos)
                if sell_qty > 0:
                    orders.append(Order(product, sell_price, -sell_qty))
            if self.HYDRO_ENABLE_TAKE and current_pos < 0:
                unwind_qty = min(8, -current_pos)
                if unwind_qty > 0:
                    orders.append(Order(product, int(math.floor(last_fair - 1)), unwind_qty))
            return orders

        def vwap(levels, depth=3):
            cv, cpv = 0, 0
            for i, (px, vol) in enumerate(levels):
                if i >= depth:
                    break
                v = abs(vol); cv += v; cpv += px * v
            return cpv / cv if cv > 0 else None

        bid_vwap = vwap(sorted_bids)
        ask_vwap = vwap(sorted_asks)
        best_bid, best_bid_qty = sorted_bids[0]
        best_ask, best_ask_qty = sorted_asks[0]
        mid_price = (best_bid + best_ask) / 2.0

        gap_alpha = 0.0
        if self.ENABLE_HYDRO_GAP_ALPHA and len(sorted_bids) >= 2 and len(sorted_asks) >= 2:
            bid_gap = sorted_bids[0][0] - sorted_bids[1][0]
            ask_gap = sorted_asks[1][0] - sorted_asks[0][0]
            gap_skew = bid_gap - ask_gap
            if gap_skew <= -self.HYDRO_GAP_THRESHOLD:
                gap_alpha = self.HYDRO_GAP_ALPHA_STRENGTH
            elif gap_skew >= self.HYDRO_GAP_THRESHOLD:
                gap_alpha = -self.HYDRO_GAP_ALPHA_STRENGTH

        if bid_vwap and ask_vwap:
            tbv = sum(abs(q) for _, q in sorted_bids[:3])
            tav = sum(abs(q) for _, q in sorted_asks[:3])
            observation = (bid_vwap * tav + ask_vwap * tbv) / (tbv + tav) if tbv + tav > 0 else mid_price
        else:
            observation = mid_price

        mid_history: List[float] = state_data.get("hydro_mid_history", [])
        if not isinstance(mid_history, list):
            mid_history = []
        mid_history.append(mid_price)
        max_hist = max(self.HYDRO_TREND_WINDOW + 2, 60)
        if len(mid_history) > max_hist:
            mid_history = mid_history[-max_hist:]
        state_data["hydro_mid_history"] = mid_history

        trend_50 = 0.0
        if len(mid_history) > self.HYDRO_TREND_WINDOW:
            trend_50 = mid_price - float(mid_history[-1 - self.HYDRO_TREND_WINDOW])

        block_new_longs = False
        block_new_shorts = False
        if self.HYDRO_USE_TREND_BLOCK:
            if trend_50 <= -self.HYDRO_CRASH_BLOCK_LONGS:
                block_new_longs = True
            if trend_50 >= self.HYDRO_RIP_BLOCK_SHORTS:
                block_new_shorts = True
        if current_pos >= self.HYDRO_DISABLE_BID_ABOVE_POS:
            block_new_longs = True
        if current_pos <= self.HYDRO_DISABLE_ASK_BELOW_POS:
            block_new_shorts = True

        x_est = state_data.get("hydro_kalman_x", observation)
        P_est = state_data.get("hydro_kalman_P", 1.0)
        Q, R = 0.008, 0.3
        P_pred = P_est + Q
        K = P_pred / (P_pred + R)
        x_est = x_est + K * (observation - x_est)
        P_est = (1 - K) * P_pred
        state_data["hydro_kalman_x"] = x_est
        state_data["hydro_kalman_P"] = P_est
        uncertainty = math.sqrt(P_est)

        def vwap_vol(levels, target_volume=50):
            cv, cpv = 0, 0
            for px, vol in levels:
                v = abs(vol); take = min(v, target_volume - cv)
                if take <= 0: break
                cv += take; cpv += px * take
            return cpv / cv if cv > 0 else None

        depth_mid_raw = (vwap_vol(sorted_bids) or mid_price + vwap_vol(sorted_asks) or mid_price) / 2.0
        bvo = vwap_vol(sorted_bids)
        avo = vwap_vol(sorted_asks)
        depth_mid = (bvo + avo) / 2.0 if bvo and avo else mid_price

        alpha_ema = 0.12
        ema = state_data.get("hydro_ema")
        ema = depth_mid if ema is None else alpha_ema * depth_mid + (1 - alpha_ema) * ema
        state_data["hydro_ema"] = ema

        fair_value_raw = 0.6 * x_est + 0.4 * ema

        tbv1 = abs(best_bid_qty)
        tav1 = abs(best_ask_qty)
        imbalance = (tbv1 - tav1) / (tbv1 + tav1) if tbv1 + tav1 > 0 else 0.0
        fair_value_raw += imbalance * 0.8 + gap_alpha

        anchor_weight = 0.25
        fair_value_raw = (1.0 - anchor_weight) * fair_value_raw + anchor_weight * self.HYDRO_ANCHOR

        pos_ratio = current_pos / float(effective_limit)
        skew = pos_ratio * 2 if pos_ratio < 0.6 else pos_ratio * 5
        fair_value = fair_value_raw - skew
        state_data["hydro_last_fair"] = fair_value

        def max_buy(desired, pos):
            if desired <= 0: return 0
            cap = effective_limit - pos
            if block_new_longs:
                cap = min(cap, -pos) if pos < 0 else 0
            return max(0, min(desired, cap))

        def max_sell(desired, pos):
            if desired <= 0: return 0
            cap = effective_limit + pos
            if block_new_shorts:
                cap = min(cap, pos) if pos > 0 else 0
            return max(0, min(desired, cap))

        if self.HYDRO_ENABLE_TAKE:
            take_threshold = 0.5 + uncertainty * 1.0
            buy_thr = max(0.1, take_threshold - imbalance * 1.0)
            sell_thr = max(0.1, take_threshold + imbalance * 1.0)
            for price, qty in sorted_asks:
                if price < fair_value - buy_thr:
                    amt = max_buy(-qty, current_pos)
                    if amt > 0:
                        orders.append(Order(product, price, amt))
                        current_pos += amt
            for price, qty in sorted_bids:
                if price > fair_value + sell_thr:
                    amt = max_sell(qty, current_pos)
                    if amt > 0:
                        orders.append(Order(product, price, -amt))
                        current_pos -= amt

        if self.HYDRO_ENABLE_PASSIVE:
            base_half = 0.5 + uncertainty * 1.0
            ideal_bid = int(math.floor(fair_value - base_half))
            ideal_ask = int(math.ceil(fair_value + base_half))
            spread = best_ask - best_bid
            if spread > 1:
                my_bid = min(ideal_bid, best_bid + 1)
                my_ask = max(ideal_ask, best_ask - 1)
            else:
                my_bid, my_ask = ideal_bid, ideal_ask
            my_bid = min(my_bid, best_ask - 1)
            my_ask = max(my_ask, best_bid + 1)

            uncertainty_penalty = max(0.3, 1.0 - uncertainty * 0.5)
            inv_penalty = max(0.3, 1.0 - abs(current_pos / float(effective_limit)))
            qty = max(3, int(effective_limit * inv_penalty * uncertainty_penalty))

            bid_scale = max(0.3, 1.0 + imbalance * 2.0)
            ask_scale = max(0.3, 1.0 - imbalance * 2.0)

            if self.ENABLE_HYDRO_GAP_SIZE_SKEW and gap_alpha != 0.0:
                fav, tox = max(0.0, self.HYDRO_GAP_FAVORED_SIZE_SCALE), max(0.0, self.HYDRO_GAP_TOXIC_SIZE_SCALE)
                if gap_alpha > 0.0:
                    bid_scale *= fav; ask_scale *= tox
                else:
                    ask_scale *= fav; bid_scale *= tox

            bid_qty = max_buy(max(1, int(qty * bid_scale)), current_pos)
            if bid_qty > 0:
                orders.append(Order(product, my_bid, bid_qty))

            ask_qty = max_sell(max(1, int(qty * ask_scale)), current_pos)
            if ask_qty > 0:
                orders.append(Order(product, my_ask, -ask_qty))

        return orders

    # =========================================================================
    # Options helpers
    # =========================================================================

    def _best_bid_ask(self, od: OrderDepth) -> Tuple[Optional[int], Optional[int], int, int]:
        best_bid = max(od.buy_orders) if od.buy_orders else None
        best_ask = min(od.sell_orders) if od.sell_orders else None
        bid_vol = int(od.buy_orders.get(best_bid, 0)) if best_bid is not None else 0
        ask_vol = abs(int(od.sell_orders.get(best_ask, 0))) if best_ask is not None else 0
        return best_bid, best_ask, bid_vol, ask_vol

    def _tight_surface_gate(self, state: TradingState) -> bool:
        for product in self.BOT_FLOW_SURFACE_PRODUCTS:
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                return False
            bb, ba, _, _ = self._best_bid_ask(depth)
            if bb is None or ba is None or float(ba - bb) > self.BOT_FLOW_MAX_SPREAD:
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
            bb, ba, _, _ = self._best_bid_ask(depth)
            if bb is None or ba is None:
                continue
            history = list(histories.get(product, []))
            history.append(0.5 * (bb + ba))
            if len(history) > self.SWING_FEATURE_WINDOW:
                history = history[-self.SWING_FEATURE_WINDOW:]
            histories[product] = history

    def _current_swing_snapshot(self, data: dict, product: str) -> Optional[dict]:
        history = list(data.get("swing_history", {}).get(product, []))
        if len(history) < self.SWING_SLOW_WINDOW:
            return None
        prev = history[:-1]
        prev2 = history[:-2]
        rolling_high = max(history)
        rolling_low = min(history)
        rolling_range = rolling_high - rolling_low
        prev_range = max(prev) - min(prev) if len(prev) >= 1 else rolling_range
        prev_drawdown = prev_fms = prev_fms_slope = 0.0
        if len(prev) >= 1:
            prev_drawdown = max(prev) - prev[-1]
            prev_fms = self._trailing_mean(prev, self.SWING_FAST_WINDOW) - self._trailing_mean(prev, self.SWING_SLOW_WINDOW)
        if len(prev2) >= 1:
            prev2_fms = self._trailing_mean(prev2, self.SWING_FAST_WINDOW) - self._trailing_mean(prev2, self.SWING_SLOW_WINDOW)
            prev_fms_slope = prev_fms - prev2_fms
        mid = history[-1]
        drawdown = rolling_high - mid
        rebound = mid - rolling_low
        fms = self._trailing_mean(history, self.SWING_FAST_WINDOW) - self._trailing_mean(history, self.SWING_SLOW_WINDOW)
        fms_slope = fms - prev_fms
        fms_accel = fms_slope - prev_fms_slope
        drawdown_slope = drawdown - prev_drawdown
        bottomness = (0.30 * drawdown - 0.20 * rebound - 2.50 * fms
                      + 12.0 * max(0.0, fms_slope) + 10.0 * max(0.0, fms_accel)
                      - 4.0 * max(0.0, drawdown_slope))
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
        checks = [
            ("fms_min", "fast_minus_slow", lambda v, t: v >= t),
            ("fms_max", "fast_minus_slow", lambda v, t: v <= t),
            ("dd_min",  "drawdown",        lambda v, t: v >= t),
            ("dd_max",  "drawdown",        lambda v, t: v <= t),
            ("rb_min",  "rebound",         lambda v, t: v >= t),
            ("rb_max",  "rebound",         lambda v, t: v <= t),
            ("range_min", "rolling_range", lambda v, t: v >= t),
            ("range_slope_min", "range_slope", lambda v, t: v >= t),
            ("fms_slope_min", "fms_slope", lambda v, t: v >= t),
            ("fms_accel_min", "fms_accel", lambda v, t: v >= t),
            ("dd_slope_max", "drawdown_slope", lambda v, t: v <= t),
            ("bottomness_min", "bottomness", lambda v, t: v >= t),
        ]
        for key, field, fn in checks:
            if key in cfg and not fn(snap[field], float(cfg[key])):
                return False
        return True

    def _update_ve_cycle_state(self, data: dict) -> None:
        snap = self._current_swing_snapshot(data, VE)
        if snap is None:
            return
        extended_up  = snap["fast_minus_slow"] >= 0.72 and snap["drawdown"] <= 3.0 and snap["rebound"] >= 7.5  and snap["rolling_range"] >= 8.5
        capitulation = snap["fast_minus_slow"] <= -4.82 and snap["drawdown"] >= 15.5 and snap["rebound"] <= 2.5  and snap["rolling_range"] >= 17.0
        rebound_1    = (data.get("ve_has_capitulated", False) and snap["fast_minus_slow"] >= 1.5
                        and snap["drawdown"] <= 9.0 and snap["rebound"] >= 6.0 and snap["rolling_range"] >= 12.0)
        retest_up    = (data.get("ve_has_rebounded", False) and snap["fast_minus_slow"] >= 2.61
                        and snap["drawdown"] <= 7.0 and snap["rebound"] >= 14.0 and snap["rolling_range"] >= 18.0)
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
        extended_up   = snap["fast_minus_slow"] >= 0.0  and snap["drawdown"] <= 5.0  and snap["rebound"] >= 6.0  and snap["rolling_range"] >= 8.0
        capitulation  = snap["fast_minus_slow"] <= -10.82 and snap["drawdown"] >= 38.0 and snap["rebound"] <= 4.0  and snap["rolling_range"] >= 39.0
        rebound_short = (data.get("hp_has_capitulated", False) and snap["fast_minus_slow"] >= 0.0
                         and snap["drawdown"] <= 12.0 and snap["rebound"] >= 21.0 and snap["rolling_range"] >= 27.0)
        bottom_build  = (snap["fast_minus_slow"] <= -6.0 and snap["drawdown"] >= 30.0 and snap["rebound"] <= 12.0
                         and snap["rolling_range"] >= 35.0 and snap["fms_slope"] >= 0.20 and snap["fms_accel"] >= 0.0
                         and snap["drawdown_slope"] <= 0.5 and snap["bottomness"] >= 35.0)
        final_buy     = (data.get("hp_has_rebounded", False) and snap["fast_minus_slow"] <= -8.34
                         and snap["drawdown"] >= 22.5 and snap["rebound"] <= 9.5 and snap["rolling_range"] >= 29.0)
        if capitulation:
            data.update({"hp_cycle_state": "capitulation", "hp_has_capitulated": True,
                         "hp_has_rebounded": False, "hp_has_bottomed": False})
        elif bottom_build:
            data.update({"hp_cycle_state": "bottom_build", "hp_has_capitulated": True, "hp_has_bottomed": True})
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
        remaining_days = max(self.ROUND_TTE_DAYS - hist_day - timestamp / 999_900.0, 0.20)
        return remaining_days / self.DAYS_PER_YEAR

    def _cap_delta_qty(self, qty: int, per_unit_delta_change: float, projected_delta: float) -> int:
        if qty <= 0:
            return 0
        full_change = qty * per_unit_delta_change
        if abs(projected_delta + full_change) <= abs(projected_delta):
            return qty
        room = (self.MAX_ABS_OPTION_DELTA - projected_delta if per_unit_delta_change > 0
                else projected_delta + self.MAX_ABS_OPTION_DELTA)
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
            pending_buy_at_ask  = sum( o.quantity for o in result.get(product, []) if o.quantity > 0 and o.price == best_ask)
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
        result: Dict[Symbol, List[Order]] = {}
        u_depth = state.order_depths.get(VE)
        if u_depth is None or not u_depth.buy_orders or not u_depth.sell_orders:
            return result
        spot = 0.5 * (max(u_depth.buy_orders) + min(u_depth.sell_orders))
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
        conversions = 0

        # === HYDROGEL PASS (adaptive Kalman MM) ===
        od = state.order_depths.get(HYDROGEL)
        if od and od.buy_orders and od.sell_orders:
            hydro_orders = self.get_hydrogel_orders(
                HYDROGEL, od, int(state.position.get(HYDROGEL, 0)), data
            )
            if hydro_orders:
                result[HYDROGEL] = hydro_orders

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
            trader_data = self._dump_state(data)
            logger.flush(state, result, conversions, trader_data)
            return result, conversions, trader_data

        ve_best_bid, ve_best_ask, _, _ = self._best_bid_ask(ve_depth)
        if ve_best_bid is None or ve_best_ask is None:
            trader_data = self._dump_state(data)
            logger.flush(state, result, conversions, trader_data)
            return result, conversions, trader_data

        ve_mid = 0.5 * (ve_best_bid + ve_best_ask)
        data["ve_mid"] = ve_mid
        self._update_swing_features(state, data)
        self._update_ve_cycle_state(data)
        self._update_hp_cycle_state(data)
        surface_tight = self._tight_surface_gate(state)
        tte = self._time_to_expiry(int(data["hist_day"]), state.timestamp)

        self.mean_reverter.add_price(ve_mid)

        projected_option_delta = 0.0
        for product, cfg in TRADED_VOUCHERS.items():
            if product not in self.ENABLED_PRODUCTS:
                continue
            pos = int(state.position.get(product, 0))
            if pos == 0:
                continue
            projected_option_delta += pos * BlackScholes.delta(ve_mid, int(cfg["strike"]), tte, float(cfg["sigma"]))

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
                min_sell_price = int(self.SECOND_ENTRY_MIN_SELL_PRICE_BY_PRODUCT.get(
                    product, self.MIN_SELL_PRICE_BY_PRODUCT.get(product, -1_000_000)))
            else:
                min_sell_price = int(self.MIN_SELL_PRICE_BY_PRODUCT.get(product, -1_000_000))

            edge = float(cfg["edge"])
            take_size = int(cfg["take_size"])
            if data.get("ve_cycle_state") == "retest_up" and surface_tight:
                edge *= self.SECOND_HALF_EDGE_MULT
                take_size = int(round(take_size * self.SECOND_HALF_TAKE_MULT))

            # Mark 01 intercept: detect buyer activity and lower edge to front-run Mark 22
            if self.MARK01_INTERCEPT_ENABLED:
                for trade in state.market_trades.get(product, []):
                    if getattr(trade, 'buyer', '') == "Mark 01":
                        data[f"m01_last_{product}"] = state.timestamp
                        break
                m01_last = int(data.get(f"m01_last_{product}", -999999))
                if state.timestamp - m01_last <= self.MARK01_ACTIVE_TICKS:
                    edge *= self.MARK01_EDGE_MULT

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

            if self.IV_SCALP_ENABLED:
                moneyness = math.log(ve_mid / strike) if ve_mid > 0 and strike > 0 else 0.0
                implied_vol = BlackScholes.implied_vol_from_price(ve_mid, strike, tte, mid)
                self.volatility_smiles[product].add_observation(moneyness, implied_vol)
                iv_deviation = self.volatility_smiles[product].get_iv_deviation(implied_vol, moneyness)
                if iv_deviation is not None:
                    iv_threshold = float(cfg.get("iv_scalp_threshold", 0.015))
                    if iv_deviation > iv_threshold and sell_room > 0:
                        qty = min(int(cfg["take_size"]) // 2, ask_vol, sell_room)
                        if qty > 0:
                            orders.append(Order(product, best_ask, -qty))
                    elif iv_deviation < -iv_threshold and buy_room > 0:
                        qty = min(int(cfg["take_size"]) // 2, bid_vol, buy_room)
                        if qty > 0:
                            orders.append(Order(product, best_bid, qty))

            if fair - best_ask >= edge and buy_room > 0:
                qty = self._cap_delta_qty(min(take_size, ask_vol, buy_room), option_delta, projected_option_delta)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    position += qty; buy_room -= qty; sell_room += qty
                    projected_option_delta += qty * option_delta

            if best_bid - fair >= edge and sell_room > 0 and best_bid >= min_sell_price:
                qty = self._cap_delta_qty(min(take_size, bid_vol, sell_room), -option_delta, projected_option_delta)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    position -= qty; sell_room -= qty; buy_room += qty
                    projected_option_delta -= qty * option_delta

            clear_size = int(cfg["clear_size"])
            clear_band = self.CLEAR_BAND_BY_PRODUCT.get(product, self.CLEAR_BAND)
            if position > 0 and best_bid >= fair - clear_band:
                qty = min(position, bid_vol, clear_size)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    position -= qty; projected_option_delta -= qty * option_delta
            elif position < 0 and best_ask <= fair + clear_band:
                qty = min(-position, ask_vol, clear_size)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    position += qty; projected_option_delta += qty * option_delta

            if spread >= self.PASSIVE_ONLY_IF_SPREAD_AT_LEAST and abs(position) < self.MAX_PASSIVE_ABS_POS:
                inv_skew = position / self.VOUCHER_LIMIT
                mm_width = float(cfg["mm_width"])
                intrinsic_floor = int(math.ceil(max(0.0, ve_mid - strike)))
                bid_px = max(intrinsic_floor, min(best_ask - 1, max(best_bid, int(math.floor(fair - mm_width - 0.75 * inv_skew)))))
                ask_px = max(best_bid + 1, min(best_ask, int(math.ceil(fair + mm_width - 0.75 * inv_skew))))
                if buy_room > 0 and fair - best_ask > -0.50 * edge and bid_px < best_ask:
                    qty = self._cap_delta_qty(min(int(cfg["mm_size"]), buy_room), option_delta, projected_option_delta)
                    if qty > 0:
                        orders.append(Order(product, bid_px, qty))
                        position += qty; buy_room -= qty; projected_option_delta += qty * option_delta
                if sell_room > 0 and best_bid - fair > -0.50 * edge and ask_px > best_bid and ask_px >= min_sell_price:
                    qty = self._cap_delta_qty(min(int(cfg["mm_size"]), sell_room), -option_delta, projected_option_delta)
                    if qty > 0:
                        orders.append(Order(product, ask_px, -qty))
                        position -= qty; projected_option_delta -= qty * option_delta

            if orders:
                result[product] = orders

        ve_position = int(state.position.get(VE, 0))
        target_ve = max(-self.VE_LIMIT, min(self.VE_LIMIT, int(round(-projected_option_delta))))
        hedge_qty = target_ve - ve_position
        if abs(hedge_qty) >= self.DELTA_HEDGE_THRESHOLD:
            if hedge_qty > 0 and ve_best_ask is not None:
                qty = min(hedge_qty, self.VE_LIMIT - ve_position)
                if qty > 0:
                    result.setdefault(VE, []).append(Order(VE, ve_best_ask, qty))
            elif hedge_qty < 0 and ve_best_bid is not None:
                qty = min(-hedge_qty, self.VE_LIMIT + ve_position)
                if qty > 0:
                    result.setdefault(VE, []).append(Order(VE, ve_best_bid, -qty))

        self._apply_swing_rules(state, result, data)

        for product in self.OU_PRODUCTS:
            if product in ou_orders:
                result[product] = ou_orders[product]
            elif product in result:
                del result[product]

        if self.MR_ENABLED:
            mr_signal, mr_strength = self.mean_reverter.get_mean_reversion_signal()
            cur_mr = int(data.get("mr_positions", 0))
            if mr_signal != "neutral" and mr_strength > 0.3:
                ve_d = state.order_depths.get(VE)
                if ve_d:
                    bb, ba, bv, av = self._best_bid_ask(ve_d)
                    if bb and ba:
                        mr_qty = int(self.MR_POSITION_SIZE * mr_strength)
                        if mr_signal == "buy" and cur_mr < 100:
                            qty = min(mr_qty, 100 - cur_mr)
                            if qty > 0:
                                result.setdefault(VE, []).append(Order(VE, ba, qty))
                                cur_mr += qty
                        elif mr_signal == "sell" and cur_mr > -100:
                            qty = min(mr_qty, cur_mr + 100)
                            if qty > 0:
                                result.setdefault(VE, []).append(Order(VE, bb, -qty))
                                cur_mr -= qty
                        data["mr_positions"] = cur_mr

        trader_data = self._dump_state(data)
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data
