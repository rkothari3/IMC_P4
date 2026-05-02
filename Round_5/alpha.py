import json
import math
from statistics import mean, stdev
from typing import Dict, List, Optional, Tuple

from datamodel import Order, OrderDepth, Symbol, TradingState


class GalaxyPairsModule:
    PAIRS = (
        ("dmbh", "GALAXY_SOUNDS_DARK_MATTER", "GALAXY_SOUNDS_BLACK_HOLES", 3000, 3000, 2.50),
        ("swsf", "GALAXY_SOUNDS_SOLAR_WINDS", "GALAXY_SOUNDS_SOLAR_FLAMES", 1500, 1500, 3.00),
    )
    TARGET_SIZE = 10
    POSITION_LIMIT = 10

    def _clean_history(self, raw, limit: int) -> list:
        if not isinstance(raw, list):
            return []
        out = []
        for v in raw[-limit:]:
            try:
                out.append(int(v))
            except (TypeError, ValueError):
                continue
        return out

    def _rolling_z(self, history: list, current: int, window: int, min_hist: int):
        lb = history[-window:]
        if len(lb) < min_hist:
            return None
        mu = sum(lb) / len(lb)
        var = max(0.0, sum(v * v for v in lb) / len(lb) - mu * mu)
        std = math.sqrt(var)
        return None if std <= 0.0 else (current - mu) / std

    def _cross(self, product: str, od: OrderDepth, pos: int, target: int) -> list:
        orders = []
        target = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target))
        delta = target - pos
        if delta == 0:
            return orders
        best_bid = max(od.buy_orders) if od.buy_orders else None
        best_ask = min(od.sell_orders) if od.sell_orders else None
        if delta > 0:
            if best_ask is None:
                return orders
            qty = min(delta, max(0, -od.sell_orders.get(best_ask, 0)), max(0, self.POSITION_LIMIT - pos))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
        else:
            if best_bid is None:
                return orders
            qty = min(-delta, max(0, od.buy_orders.get(best_bid, 0)), max(0, self.POSITION_LIMIT + pos))
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
        return orders

    def load_state(self, raw: dict):
        histories = {name: [] for name, *_ in self.PAIRS}
        targets = {name: 0 for name, *_ in self.PAIRS}
        if not isinstance(raw, dict):
            return histories, targets
        h = raw.get("h", {})
        if isinstance(h, dict):
            for name, _, _, window, _, _ in self.PAIRS:
                histories[name] = self._clean_history(h.get(name, []), window)
        t = raw.get("t", {})
        if isinstance(t, dict):
            for name, *_ in self.PAIRS:
                try:
                    v = max(-self.TARGET_SIZE, min(self.TARGET_SIZE, int(t.get(name, 0))))
                except (TypeError, ValueError):
                    v = 0
                targets[name] = v
        return histories, targets

    def dump_state(self, histories: dict, targets: dict) -> dict:
        return {
            "h": {name: histories.get(name, [])[-window:] for name, _, _, window, *_ in self.PAIRS},
            "t": {name: int(targets.get(name, 0)) for name, *_ in self.PAIRS},
        }

    def run(self, state, histories: dict, targets: dict):
        next_targets = {name: targets.get(name, 0) for name, *_ in self.PAIRS}
        diffs: dict = {}
        active = []

        for name, prod_a, prod_b, window, min_hist, entry_z in self.PAIRS:
            da = state.order_depths.get(prod_a)
            db = state.order_depths.get(prod_b)
            if da is None or db is None:
                continue
            ba = max(da.buy_orders) if da.buy_orders else None
            aa = min(da.sell_orders) if da.sell_orders else None
            bb = max(db.buy_orders) if db.buy_orders else None
            ab = min(db.sell_orders) if db.sell_orders else None
            if ba is None or aa is None or bb is None or ab is None:
                continue
            diff = int(round(((ba + aa) / 2.0 - (bb + ab) / 2.0) * 10))
            history = histories[name]
            has_min = len(history) >= min_hist
            z = self._rolling_z(history, diff, window, min_hist)
            prev = targets.get(name, 0)
            if not has_min:
                next_targets[name] = 0
            elif z is None:
                next_targets[name] = prev
            elif z > entry_z:
                next_targets[name] = -self.TARGET_SIZE
            elif z < -entry_z:
                next_targets[name] = self.TARGET_SIZE
            else:
                next_targets[name] = prev
            diffs[name] = diff
            active.append((name, prod_a, prod_b, window))

        orders: Dict[str, list] = {}
        for name, prod_a, prod_b, window in active:
            tgt = next_targets[name]
            oa = self._cross(prod_a, state.order_depths[prod_a], state.position.get(prod_a, 0), tgt)
            ob = self._cross(prod_b, state.order_depths[prod_b], state.position.get(prod_b, 0), -tgt)
            if oa:
                orders[prod_a] = oa
            if ob:
                orders[prod_b] = ob
            h = histories[name]
            if name in diffs:
                h.append(diffs[name])
                if len(h) > window:
                    del h[:len(h) - window]

        return orders, next_targets


class Trader:
    """
    Sleeping pods: same as trader.py (blocked LAMB_WOOL, NYLON open→close trend overlay, poly/cotton pair tilt,
    default _trade_product for SUEDE/POLY/COTTON/NYLON).

    Domestic robots: alpha stack — DISHES rolling MR blend, MOPPING aggressive long (capped), IRONING aggressive
    short (capped), LAUNDRY MM; ROBOT_VACUUMING blocked.
    """

    LIMIT = 10
    TREND_POSITION_CAP = 10
    FAST_ALPHA = 0.18
    SLOW_ALPHA = 0.018
    VOL_ALPHA = 0.08

    PRODUCTS = (
        "GALAXY_SOUNDS_DARK_MATTER",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
        "SLEEP_POD_SUEDE",
        "SLEEP_POD_LAMB_WOOL",
        "SLEEP_POD_POLYESTER",
        "SLEEP_POD_NYLON",
        "SLEEP_POD_COTTON",
        "MICROCHIP_CIRCLE",
        "MICROCHIP_OVAL",
        "MICROCHIP_SQUARE",
        "MICROCHIP_RECTANGLE",
        "MICROCHIP_TRIANGLE",
        "PEBBLES_XS",
        "PEBBLES_S",
        "PEBBLES_M",
        "PEBBLES_L",
        "PEBBLES_XL",
        "ROBOT_VACUUMING",
        "ROBOT_MOPPING",
        "ROBOT_DISHES",
        "ROBOT_LAUNDRY",
        "ROBOT_IRONING",
        "UV_VISOR_YELLOW",
        "UV_VISOR_AMBER",
        "UV_VISOR_ORANGE",
        "UV_VISOR_RED",
        "UV_VISOR_MAGENTA",
        "TRANSLATOR_SPACE_GRAY",
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_VOID_BLUE",
        "PANEL_1X2",
        "PANEL_2X2",
        "PANEL_1X4",
        "PANEL_2X4",
        "PANEL_4X4",
        "OXYGEN_SHAKE_MORNING_BREATH",
        "OXYGEN_SHAKE_EVENING_BREATH",
        "OXYGEN_SHAKE_MINT",
        "OXYGEN_SHAKE_CHOCOLATE",
        "OXYGEN_SHAKE_GARLIC",
        "SNACKPACK_CHOCOLATE",
        "SNACKPACK_VANILLA",
        "SNACKPACK_PISTACHIO",
        "SNACKPACK_STRAWBERRY",
        "SNACKPACK_RASPBERRY",
    )

    STRUCTURAL_PRIOR = {
        "PEBBLES_XS": -0.35,
        "PEBBLES_S": -0.20,
        "PEBBLES_XL": 0.25,
        "MICROCHIP_OVAL": -0.35,
        "MICROCHIP_TRIANGLE": -0.15,
        "OXYGEN_SHAKE_GARLIC": 0.30,
        "GALAXY_SOUNDS_BLACK_HOLES": 0.25,
        "PANEL_2X4": 0.20,
        "UV_VISOR_AMBER": -0.25,
        "UV_VISOR_RED": 0.20,
        "SNACKPACK_PISTACHIO": -0.15,
    }

    LEAD_LAG = (
        ("UV_VISOR_AMBER", "PEBBLES_XS", 1.0),
        ("MICROCHIP_SQUARE", "SLEEP_POD_SUEDE", 1.0),
        ("MICROCHIP_OVAL", "ROBOT_IRONING", 1.0),
        ("GALAXY_SOUNDS_BLACK_HOLES", "OXYGEN_SHAKE_GARLIC", 1.0),
        ("MICROCHIP_SQUARE", "MICROCHIP_RECTANGLE", -1.0),
        ("PEBBLES_XL", "PEBBLES_L", -1.0),
    )

    BLOCKED_PRODUCTS = {
        "PANEL_4X4",
        "PANEL_1X2",
    }

    TREND_OVERLAY = {
        "MICROCHIP_SQUARE": {"threshold": 300.0, "min_ticks": 400},
        "PEBBLES_XS": {"threshold": 10.0, "min_ticks": 400},
        "UV_VISOR_AMBER": {"threshold": 10.0, "min_ticks": 25},
        "SLEEP_POD_NYLON": {"threshold": 25.0, "min_ticks": 800},
        "OXYGEN_SHAKE_GARLIC": {"threshold": 800.0, "min_ticks": 0},
    }

    OPEN_MOM_OVERLAY = {
        "PEBBLES_XL": {"k": 1500, "th": 0.0},
        "PEBBLES_M": {"k": 2000, "th": 0.0},
        "MICROCHIP_OVAL": {"k": 1000, "th": 0.0},
        "PANEL_2X4": {"k": 2000, "th": 0.0},
    }

    PAIRS = (
        ("UV_VISOR_AMBER", "PEBBLES_XS", 200, 20, 1.7, 0.85),
        ("MICROCHIP_OVAL", "ROBOT_IRONING", 200, 20, 1.7, 0.60),
        ("GALAXY_SOUNDS_BLACK_HOLES", "OXYGEN_SHAKE_GARLIC", 200, 20, 1.7, 0.70),
    )
    PAIR_MAX_WINDOW = max(w + lag for _, _, w, lag, _, _ in PAIRS)

    MICRO_OLS = {
        "MICROCHIP_CIRCLE":    (14328.038892, {"MICROCHIP_OVAL": -0.2144216226, "MICROCHIP_RECTANGLE":  0.1239698234, "MICROCHIP_SQUARE": -0.1626194856, "MICROCHIP_TRIANGLE": -0.2303292061}, 6.0),
        "MICROCHIP_RECTANGLE": (12595.888647, {"MICROCHIP_CIRCLE":  0.1056072980, "MICROCHIP_OVAL":       0.2521946893, "MICROCHIP_SQUARE": -0.2712089572, "MICROCHIP_TRIANGLE": -0.3316449080}, 6.0),
        "MICROCHIP_TRIANGLE":  ( 8897.550320, {"MICROCHIP_CIRCLE": -0.1771853113, "MICROCHIP_OVAL":       0.5638225952, "MICROCHIP_RECTANGLE": -0.2994843207, "MICROCHIP_SQUARE":  0.0312598043}, 6.0),
        "ROBOT_IRONING":       (18545.658868, {"ROBOT_VACUUMING":   0.1213313931, "ROBOT_MOPPING":       -0.6035255162, "ROBOT_DISHES":      -0.4402725705, "ROBOT_LAUNDRY":      0.0156519013}, 6.0),
    }

    UV_OLS = {
        "UV_VISOR_RED":    (27273.019104, {"UV_VISOR_YELLOW": -0.3820067579, "UV_VISOR_AMBER": -0.6817909920, "UV_VISOR_ORANGE": -0.1361414455, "UV_VISOR_MAGENTA": -0.4688981022}, 2.5),
        "UV_VISOR_YELLOW": (25282.300224, {"UV_VISOR_AMBER":  -0.4210596715, "UV_VISOR_ORANGE": -0.2513172083, "UV_VISOR_RED":   -0.8739096888, "UV_VISOR_MAGENTA":  0.1165551453}, 2.5),
        "UV_VISOR_MAGENTA":(19824.977619, {"UV_VISOR_YELLOW":  0.0312302762, "UV_VISOR_AMBER": -0.6565830083, "UV_VISOR_ORANGE": -0.0653029897, "UV_VISOR_RED":     -0.2874209085}, 2.5),
    }

    UV_SNACK_COEFFS = {
        "UV_VISOR_RED":    -1.02,
        "UV_VISOR_YELLOW": -1.10,
        "UV_VISOR_MAGENTA":-1.25,
    }
    SNACK_PRODUCTS = ("SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA", "SNACKPACK_PISTACHIO", "SNACKPACK_STRAWBERRY", "SNACKPACK_RASPBERRY")

    ROBOT_MR_DISH_WINDOW = 100
    ROBOT_MR_DISH_CAP = 1000
    DISH_MR_TRADE = 4
    DISH_MR_BAND = 0.53
    # Floor σ for z-score to avoid exploding signals when dispersion is negligible.
    DISH_SIGMA_FLOOR = 22.0
    # Extreme intraday dispersion: backbone MM only (reduces spike risk on DISHES).
    DISH_MR_MAX_SIGMA = 300.0

    _ALPHA_TREND_LONG = frozenset({"ROBOT_MOPPING", "SLEEP_POD_SUEDE", "SLEEP_POD_POLYESTER"})
    _SIMPLE_MM_PRODUCTS = frozenset({"SLEEP_POD_LAMB_WOOL", "SLEEP_POD_NYLON", "ROBOT_VACUUMING", "ROBOT_LAUNDRY"})

    TRANSLATOR_PRODUCTS = frozenset({
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_SPACE_GRAY",
        "TRANSLATOR_VOID_BLUE",
    })
    TRANSLATOR_ANCHOR = frozenset({
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_SPACE_GRAY",
    })
    TRANSLATOR_NEAR_ANCHOR = frozenset({"TRANSLATOR_ASTRO_BLACK", "TRANSLATOR_GRAPHITE_MIST"})
    TRANSLATOR_GRAPHITE_SCOUT = 5
    TRANSLATOR_GRAPHITE_CONFIRM = 70.0
    TRANSLATOR_GRAPHITE_FLAT = 90.0

    _GALAXY = GalaxyPairsModule()

    # Notebook-inspired snackpack signal (submission-safe):
    # Use the strongest relative-value pair found in our offline scan:
    # d(t) = sqrt(mid_chocolate / mid_vanilla), smooth with EWMA, then lean fair values when z is extreme.
    _SNACK_A = "SNACKPACK_CHOCOLATE"
    _SNACK_B = "SNACKPACK_VANILLA"
    _SNACK_D_EWMA_ALPHA = 0.0025
    _SNACK_Z_WINDOW = 500
    _SNACK_ENTRY_Z = 2.0
    _SNACK_FAIR_CLIP = 6.0

    def _trend_inventory_cap(self) -> int:
        """Max abs position for capped robots (mopping / ironing)."""
        return min(self.LIMIT, int(self.TREND_POSITION_CAP))

    def _load(self, trader_data: str) -> dict:
        base = {
            "last_timestamp": -1,
            "state": {},
            "mid_hist": {},
            "kalman": {},
            "pair_z": {},
            "open_mom_dir": {},
            "snack_prev": {},
            "dishes_mid_hist": [],
            "translator_starts": {},
            "translator_fast": {},
            "translator_slow": {},
            "galaxy": {},
            "snackpair": {},
        }
        if not trader_data:
            return base
        try:
            raw = json.loads(trader_data)
            if isinstance(raw, dict):
                base.update(raw)
        except Exception:
            pass
        if not isinstance(base.get("dishes_mid_hist"), list):
            base["dishes_mid_hist"] = []
        return base

    def _dump(self, data: dict) -> str:
        return json.dumps(data, separators=(",", ":"))

    def _reset_data(self, state_timestamp: int) -> dict:
        return {
            "last_timestamp": state_timestamp,
            "state": {},
            "mid_hist": {},
            "kalman": {},
            "pair_z": {},
            "open_mom_dir": {},
            "snack_prev": {},
            "dishes_mid_hist": [],
            "translator_starts": {},
            "translator_fast": {},
            "translator_slow": {},
            "galaxy": {},
            "snackpair": {},
        }

    def _open_mom_target(self, product: str, data: dict, mid: float) -> Optional[int]:
        cfg = self.OPEN_MOM_OVERLAY.get(product)
        if cfg is None:
            return None

        dmap = data.setdefault("open_mom_dir", {})
        if not isinstance(dmap, dict):
            dmap = {}
            data["open_mom_dir"] = dmap

        if product in dmap:
            direction = int(dmap[product])
            return direction * self.LIMIT

        rec = data.get("state", {}).get(product)
        if not isinstance(rec, list) or len(rec) != 6:
            return None
        open_mid = float(rec[4])
        tick_count = int(rec[5])

        k = int(cfg["k"])
        if tick_count < k:
            return None
        move = float(mid) - open_mid
        th = float(cfg["th"])
        if move > th:
            dmap[product] = 1
            return self.LIMIT
        if move < -th:
            dmap[product] = -1
            return -self.LIMIT
        dmap[product] = 0
        return 0

    def _best(self, depth: OrderDepth) -> Tuple[Optional[int], Optional[int], int, int]:
        best_bid = max(depth.buy_orders) if depth.buy_orders else None
        best_ask = min(depth.sell_orders) if depth.sell_orders else None
        bid_vol = int(depth.buy_orders.get(best_bid, 0)) if best_bid is not None else 0
        ask_vol = abs(int(depth.sell_orders.get(best_ask, 0))) if best_ask is not None else 0
        return best_bid, best_ask, bid_vol, ask_vol

    def _mid(self, depth: OrderDepth) -> Optional[float]:
        best_bid, best_ask, _, _ = self._best(depth)
        if best_bid is None or best_ask is None:
            return None
        return 0.5 * (best_bid + best_ask)

    def _update_features(self, state: TradingState, data: dict) -> Dict[str, float]:
        features = data.setdefault("state", {})
        mid_hist = data.setdefault("mid_hist", {})
        kalman = data.setdefault("kalman", {})
        scores: Dict[str, float] = {}

        for product, depth in state.order_depths.items():
            mid = self._mid(depth)
            if mid is None:
                continue

            rec = features.get(product)
            if not isinstance(rec, list) or len(rec) != 6:
                rec = [mid, mid, 1.0, mid, mid, 0]

            fast, slow, vol, last_mid, open_mid, tick_count = rec
            fast = float(fast)
            slow = float(slow)
            vol = float(vol)
            last_mid = float(last_mid)
            open_mid = float(open_mid)
            tick_count = int(tick_count) + 1
            change = mid - last_mid
            fast = self.FAST_ALPHA * mid + (1.0 - self.FAST_ALPHA) * fast
            slow = self.SLOW_ALPHA * mid + (1.0 - self.SLOW_ALPHA) * slow
            vol = self.VOL_ALPHA * abs(change) + (1.0 - self.VOL_ALPHA) * max(vol, 0.25)
            features[product] = [round(fast, 4), round(slow, 4), round(vol, 4), round(mid, 4), round(open_mid, 4), tick_count]

            trend = fast - slow
            denom = max(6.0, 5.0 * vol)
            scores[product] = max(-3.0, min(3.0, trend / denom))

            h = mid_hist.get(product)
            if not isinstance(h, list):
                h = []
            h.append(float(mid))
            if len(h) > int(self.PAIR_MAX_WINDOW) + 5:
                del h[: len(h) - (int(self.PAIR_MAX_WINDOW) + 5)]
            mid_hist[product] = h

            krec = kalman.get(product)
            if not (isinstance(krec, list) and len(krec) == 2):
                x, P = float(mid), 1.0
            else:
                x, P = float(krec[0]), float(krec[1])
            Q = 0.02 + 0.15 * float(vol)
            R = 1.2 + 2.5 * float(vol)
            P = P + Q
            K = P / (P + R)
            x = x + K * (float(mid) - x)
            P = (1.0 - K) * P
            kalman[product] = [round(x, 4), round(P, 4)]

        for leader, follower, sign in self.LEAD_LAG:
            leader_score = scores.get(leader, 0.0)
            if follower in scores and abs(leader_score) > 0.35:
                scores[follower] = max(-3.0, min(3.0, scores[follower] + 0.45 * sign * leader_score))

        pair_z = {}
        for a, b, w, lag, entry_z, weight in self.PAIRS:
            ha = mid_hist.get(a, [])
            hb = mid_hist.get(b, [])
            if not (isinstance(ha, list) and isinstance(hb, list)):
                continue
            if len(hb) < w or len(ha) < w + lag:
                continue
            spreads = []
            for i in range(w):
                spreads.append(float(hb[-1 - i]) - float(ha[-1 - i - lag]))
            mean_sp = sum(spreads) / float(w)
            var = sum((s - mean_sp) ** 2 for s in spreads) / float(max(1, w - 1))
            sd = math.sqrt(max(1e-6, var))
            cur = float(hb[-1]) - float(ha[-1 - lag])
            z_pair = (cur - mean_sp) / sd
            key = f"{a}|{b}"
            pair_z[key] = float(z_pair)

            if abs(z_pair) >= float(entry_z):
                adj = float(weight) * max(-2.2, min(2.2, float(z_pair)))
                if a in scores:
                    scores[a] = max(-3.0, min(3.0, float(scores[a]) + adj))
                if b in scores:
                    scores[b] = max(-3.0, min(3.0, float(scores[b]) - adj))

        data["pair_z"] = pair_z

        return scores

    def _micro_fair(self, depth: OrderDepth, mid: float, score: float, prior: float, pos: int, kalman_x: float) -> float:
        best_bid, best_ask, bid_vol, ask_vol = self._best(depth)
        if best_bid is None or best_ask is None or bid_vol + ask_vol <= 0:
            return mid

        micro = (best_ask * bid_vol + best_bid * ask_vol) / (bid_vol + ask_vol)
        spread = best_ask - best_bid
        inventory_skew = 0.28 * pos
        signal_shift = max(-4.0, min(4.0, 1.15 * score + prior))
        imbalance_shift = max(-2.0, min(2.0, (bid_vol - ask_vol) / max(1, bid_vol + ask_vol) * spread * 0.35))
        return 0.52 * mid + 0.43 * micro + 0.05 * float(kalman_x) + signal_shift + imbalance_shift - inventory_skew

    def _base_size(self, product: str, spread: int, score: float, favored: bool) -> int:
        if product == "MICROCHIP_TRIANGLE":
            base = 2
        elif product == "ROBOT_IRONING":
            base = 2
        elif product == "ROBOT_DISHES":
            base = 4
        elif product.startswith("ROBOT_"):
            base = 3
        elif product.startswith("TRANSLATOR_") or product.startswith("MICROCHIP_"):
            base = 3
        elif product.startswith("SNACKPACK_"):
            base = 4
        else:
            base = 5

        if spread >= 12:
            base += 1
        if favored and abs(score) > 0.7:
            base += 1
        if not favored and abs(score) > 1.1:
            base -= 1
        return max(1, min(5, base))

    def _trend_target(self, product: str, data: dict, mid: float) -> Optional[int]:
        cfg = self.TREND_OVERLAY.get(product)
        if cfg is None:
            return None
        rec = data.get("state", {}).get(product)
        if not isinstance(rec, list) or len(rec) != 6:
            return None
        open_mid = float(rec[4])
        tick_count = int(rec[5])
        if tick_count < int(cfg["min_ticks"]):
            return None
        move = mid - open_mid
        threshold = float(cfg["threshold"])
        if move > threshold:
            return self.LIMIT
        if move < -threshold:
            return -self.LIMIT
        return 0

    def _sweep_buy_asks(
        self, product: str, depth: OrderDepth, pos: int, room: int
    ) -> Tuple[List[Order], int]:
        """Lift every ask until room exhausted; returns orders and simulated end position."""
        orders: List[Order] = []
        p = pos
        remaining = room
        if remaining <= 0:
            return orders, p

        asks = sorted((int(px), abs(int(depth.sell_orders[px]))) for px in depth.sell_orders)
        for ap, avol in asks:
            if remaining <= 0:
                break
            take = min(remaining, avol)
            if take > 0:
                orders.append(Order(product, ap, take))
                p += take
                remaining -= take
        return orders, p

    def _clip_orders_to_position_limit(
        self, product: str, pos: int, orders: List[Order]
    ) -> List[Order]:
        """
        Prosperity rejects *all* orders for a product if aggregate buy (sell) qty would exceed
        the position limit if fully matched. Multi-level sweeps + passive legs must stay inside
        buy_room / sell_room when applied in sequence (simulated fill order = list order).
        """
        if not orders:
            return []
        lim = self.LIMIT
        cur = pos
        out: List[Order] = []
        for o in orders:
            q = int(o.quantity)
            if q > 0:
                room = lim - cur
                if room <= 0:
                    continue
                take = min(q, room)
                if take > 0:
                    out.append(Order(product, int(o.price), take))
                    cur += take
            elif q < 0:
                room = cur + lim
                if room <= 0:
                    continue
                take = min(-q, room)
                if take > 0:
                    out.append(Order(product, int(o.price), -take))
                    cur -= take
        return out

    def _sweep_sell_bids(
        self, product: str, depth: OrderDepth, pos: int, room: int
    ) -> Tuple[List[Order], int]:
        """Hit every bid selling until room exhausted (room = max contracts we can sell from position)."""
        orders: List[Order] = []
        p = pos
        remaining = room
        if remaining <= 0:
            return orders, p

        bids = sorted(
            ((int(px), int(depth.buy_orders[px])) for px in depth.buy_orders),
            key=lambda t: t[0],
            reverse=True,
        )
        for bp, bvol in bids:
            if remaining <= 0:
                break
            take = min(remaining, bvol)
            if take > 0:
                orders.append(Order(product, bp, -take))
                p -= take
                remaining -= take
        return orders, p

    def _alpha_trend_max_long(self, product: str, depth: OrderDepth, pos: int) -> List[Order]:
        """ROBOT_MOPPING only: sweep asks then passive bid; cap = TREND_POSITION_CAP."""
        target = self._trend_inventory_cap()
        room = target - pos
        if room <= 0:
            return []

        orders, np = self._sweep_buy_asks(product, depth, pos, room)
        still = target - np
        if still <= 0:
            return orders

        best_bid, best_ask, _, _ = self._best(depth)
        if best_bid is None:
            return orders
        passive_px = best_bid + 1
        if best_ask is not None:
            passive_px = min(passive_px, best_ask - 1)
        if passive_px > best_bid and still > 0:
            orders.append(Order(product, int(passive_px), still))

        return orders

    def _alpha_trend_max_short(self, product: str, depth: OrderDepth, pos: int) -> List[Order]:
        """Aggressive short capped at -_trend_inventory_cap(); symmetric to long."""
        target = -self._trend_inventory_cap()
        room = pos - target
        if room <= 0:
            return []

        orders, np = self._sweep_sell_bids(product, depth, pos, room)
        still = np - target
        if still <= 0:
            return orders

        best_bid, best_ask, _, _ = self._best(depth)
        if best_ask is None:
            return orders
        passive_px = best_ask - 1
        if best_bid is not None:
            passive_px = max(passive_px, best_bid + 1)
        if passive_px < best_ask and still > 0:
            orders.append(Order(product, int(passive_px), -still))

        return orders

    def _trade_dishes_risk_managed(
        self,
        depth: OrderDepth,
        mid: float,
        pos: int,
        hist: List[float],
        score: float,
        kalman_x: float,
        fair_adj: float,
    ) -> Tuple[List[Order], List[float]]:
        """
        Rolling 100-bar MR when signal is decisive and dispersion is bounded; σ floor on denominator;
        wide window σ → backbone MM only (avoids pathology when MR would dominate).

        Near mean (inside band): full backbone quoting. MR sweeps gated by capped trade size DISH_MR_TRADE.
        """
        prod = "ROBOT_DISHES"
        h = list(hist)
        h.append(float(mid))
        if len(h) > self.ROBOT_MR_DISH_CAP:
            del h[: len(h) - self.ROBOT_MR_DISH_CAP]

        win = self.ROBOT_MR_DISH_WINDOW
        tc = min(self.DISH_MR_TRADE, self.LIMIT)
        band = self.DISH_MR_BAND

        def backbone() -> List[Order]:
            return self._trade_product(prod, depth, pos, score, None, kalman_x, fair_adj)

        if len(h) < win:
            return backbone(), h

        window = h[-win:]
        mu = mean(window)
        sigma_raw = stdev(window) if len(window) >= 2 else 0.0

        # Very spiky residual window: backbone only (risk control).
        if sigma_raw > float(self.DISH_MR_MAX_SIGMA):
            return backbone(), h

        sigma_eff = max(float(sigma_raw), float(self.DISH_SIGMA_FLOOR))
        z = (float(mid) - mu) / sigma_eff

        if abs(z) <= band:
            return backbone(), h

        orders: List[Order] = []
        if z < -band:
            delta = min(tc - pos, self.LIMIT - pos)
            if delta <= 0:
                return backbone(), h
            sweep, _ = self._sweep_buy_asks(prod, depth, pos, delta)
            best_bid, best_ask, _, _ = self._best(depth)
            if sweep:
                orders.extend(sweep)
            elif best_ask is not None:
                orders.append(Order(prod, int(best_ask), delta))
            return orders, h

        want = -tc
        delta = min(pos - want, pos + self.LIMIT)
        if delta <= 0:
            return backbone(), h
        sweep, _ = self._sweep_sell_bids(prod, depth, pos, delta)
        best_bid, _, _, _ = self._best(depth)
        if sweep:
            orders.extend(sweep)
        elif best_bid is not None:
            orders.append(Order(prod, int(best_bid), -delta))

        return orders, h

    def _trade_product(self, product: str, depth: OrderDepth, pos: int, score: float, trend_target: Optional[int], kalman_x: float, fair_adj: float = 0.0) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask, bid_vol, ask_vol = self._best(depth)
        if best_bid is None or best_ask is None:
            return orders

        mid = 0.5 * (best_bid + best_ask)
        spread = best_ask - best_bid

        if trend_target is not None:
            delta = trend_target - pos
            if delta > 0:
                qty = min(delta, self.LIMIT - pos)
                if qty > 0:
                    return [Order(product, best_ask, qty)]
            if delta < 0:
                qty = min(-delta, self.LIMIT + pos)
                if qty > 0:
                    return [Order(product, best_bid, -qty)]
            if trend_target != 0:
                return orders

        prior = float(self.STRUCTURAL_PRIOR.get(product, 0.0))
        fair = self._micro_fair(depth, mid, score, prior, pos, float(kalman_x)) + fair_adj

        buy_room = self.LIMIT - pos
        sell_room = self.LIMIT + pos

        take_edge = max(2.0, 0.35 * spread + 1.0)
        # Snackpacks are extremely wide (spread ~16-18 on sample days). Crossing that spread is usually toxic.
        # Raise taker threshold so we mostly make markets and only take when mispricing is *very* large.
        if product.startswith("SNACKPACK_"):
            take_edge = max(take_edge, 0.65 * spread + 1.0)
        if best_ask <= fair - take_edge and buy_room > 0:
            qty = min(buy_room, ask_vol, 2 + int(abs(score) >= 1.0))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                pos += qty
                buy_room -= qty
                sell_room += qty

        if best_bid >= fair + take_edge and sell_room > 0:
            qty = min(sell_room, bid_vol, 2 + int(abs(score) >= 1.0))
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                pos -= qty
                buy_room += qty
                sell_room -= qty

        if spread < 4 or best_bid + 1 >= best_ask:
            return orders

        bid_price = min(best_bid + 1, best_ask - 1, math.floor(fair - 0.35))
        ask_price = max(best_ask - 1, best_bid + 1, math.ceil(fair + 0.35))
        if bid_price >= ask_price:
            bid_price = best_bid + 1
            ask_price = best_ask - 1
        if bid_price >= ask_price:
            return orders

        bid_favored = score + prior > -0.15
        ask_favored = score + prior < 0.15
        bid_size = self._base_size(product, spread, score, bid_favored)
        ask_size = self._base_size(product, spread, score, ask_favored)

        if pos > 3:
            bid_size = max(0, bid_size - 2)
            ask_size += 1
        elif pos < -3:
            ask_size = max(0, ask_size - 2)
            bid_size += 1

        if buy_room > 0 and bid_size > 0:
            orders.append(Order(product, int(bid_price), min(buy_room, bid_size)))
        if sell_room > 0 and ask_size > 0:
            orders.append(Order(product, int(ask_price), -min(sell_room, ask_size)))

        return orders

    def _compute_fair_adjs(self, mids: Dict[str, float], data: dict) -> Dict[str, float]:
        adjs: Dict[str, float] = {}

        for product, (intercept, coefs, clip) in self.MICRO_OLS.items():
            if product not in mids or not all(o in mids for o in coefs):
                continue
            predicted = intercept + sum(c * mids[o] for o, c in coefs.items())
            diff = predicted - mids[product]
            adjs[product] = clip if diff > 0 else (-clip if diff < 0 else 0.0)

        for product, (intercept, coefs, clip) in self.UV_OLS.items():
            if product not in mids or not all(o in mids for o in coefs):
                continue
            predicted = intercept + sum(c * mids[o] for o, c in coefs.items())
            diff = predicted - mids[product]
            adjs[product] = adjs.get(product, 0.0) + (clip if diff > 0 else (-clip if diff < 0 else 0.0))

        snack_prev = data.get("snack_prev") or {}
        snack_cur  = [mids[p] for p in self.SNACK_PRODUCTS if p in mids]
        snack_prv  = [float(snack_prev[p]) for p in self.SNACK_PRODUCTS if p in mids and p in snack_prev]
        if snack_cur and len(snack_prv) == len(snack_cur):
            delta = sum(snack_cur) / len(snack_cur) - sum(snack_prv) / len(snack_prv)
            for product, coeff in self.UV_SNACK_COEFFS.items():
                if product in mids:
                    adjs[product] = adjs.get(product, 0.0) + max(-5.0, min(5.0, coeff * delta))
        data["snack_prev"] = {p: mids[p] for p in self.SNACK_PRODUCTS if p in mids}

        # Snackpack pair drift-reversion (Pistachio vs Strawberry), implemented as fair nudges (not forced crossing).
        # This avoids paying the very wide snackpack spread while still biasing your maker to lean the right way.
        if self._SNACK_A in mids and self._SNACK_B in mids and float(mids[self._SNACK_B]) > 0:
            sp = data.get("snackpair", {})
            if not isinstance(sp, dict):
                sp = {}
            d = math.sqrt(float(mids[self._SNACK_A]) / float(mids[self._SNACK_B]))
            prev = sp.get("d_ewma", None)
            if prev is None:
                d_ewma = float(d)
            else:
                a = float(self._SNACK_D_EWMA_ALPHA)
                try:
                    d_ewma = a * float(d) + (1.0 - a) * float(prev)
                except (TypeError, ValueError):
                    d_ewma = float(d)
            sp["d_ewma"] = float(d_ewma)

            res = float(d) - float(d_ewma)
            hist = sp.get("res", [])
            if not isinstance(hist, list):
                hist = []
            hist.append(float(res))
            if len(hist) > int(self._SNACK_Z_WINDOW) + 50:
                del hist[: len(hist) - (int(self._SNACK_Z_WINDOW) + 50)]
            sp["res"] = hist

            if len(hist) >= int(self._SNACK_Z_WINDOW):
                window = hist[-int(self._SNACK_Z_WINDOW) :]
                mu = sum(window) / float(len(window))
                var = sum((x - mu) ** 2 for x in window) / float(max(1, len(window) - 1))
                sd = math.sqrt(max(1e-9, var))
                z = (res - mu) / sd

                if abs(z) >= float(self._SNACK_ENTRY_Z):
                    # If z>0, pist is rich vs straw -> push pist fair down (sell bias), straw fair up (buy bias).
                    k = min(float(self._SNACK_FAIR_CLIP), max(0.0, 1.8 * abs(z)))
                    if z > 0:
                        adjs[self._SNACK_A] = adjs.get(self._SNACK_A, 0.0) - k
                        adjs[self._SNACK_B] = adjs.get(self._SNACK_B, 0.0) + k
                    else:
                        adjs[self._SNACK_A] = adjs.get(self._SNACK_A, 0.0) + k
                        adjs[self._SNACK_B] = adjs.get(self._SNACK_B, 0.0) - k

            data["snackpair"] = sp

        return adjs

    def _translator_config(self, product: str, start_mid: float) -> dict:
        if abs(start_mid - 10000.0) <= 100.0:
            inv = 0.0
            if product == "TRANSLATOR_ASTRO_BLACK":
                inv = 0.35
            elif product == "TRANSLATOR_GRAPHITE_MIST":
                inv = 1.20
            return {"edge": 3, "size": 10, "inv": inv}
        if product == "TRANSLATOR_ASTRO_BLACK":
            return {"edge": 3, "size": 10, "inv": 0.35}
        if product == "TRANSLATOR_VOID_BLUE":
            return {"edge": 3, "size": 10, "inv": 0.45}
        if product == "TRANSLATOR_ECLIPSE_CHARCOAL":
            return {"edge": 4, "size": 6, "inv": 1.40}
        if product == "TRANSLATOR_GRAPHITE_MIST":
            return {"edge": 4, "size": 6, "inv": 1.00}
        return {"edge": 4, "size": 5, "inv": 1.50}

    def _translator_cross_to_target(self, product: str, depth: OrderDepth, pos: int, target: int) -> List[Order]:
        orders: List[Order] = []
        delta = target - pos
        best_bid, best_ask, _, _ = self._best(depth)
        if best_bid is None or best_ask is None:
            return orders
        if delta > 0:
            avail = abs(int(depth.sell_orders.get(best_ask, 0)))
            qty = min(delta, avail, self.LIMIT - pos)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
        elif delta < 0:
            avail = int(depth.buy_orders.get(best_bid, 0))
            qty = min(-delta, avail, self.LIMIT + pos)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
        return orders

    def _translator_passive_quotes(self, product: str, depth: OrderDepth, pos: int, fair: float, cfg: dict) -> List[Order]:
        edge = int(cfg["edge"])
        size = int(cfg["size"])
        orders: List[Order] = []
        best_bid, best_ask, _, _ = self._best(depth)
        if best_bid is None or best_ask is None:
            return orders
        buy_room = self.LIMIT - pos
        sell_room = self.LIMIT + pos
        if buy_room > 0:
            bid_price = min(best_bid + 1, math.floor(fair - edge))
            if bid_price < best_ask:
                qty = min(size, buy_room)
                if qty > 0:
                    orders.append(Order(product, int(bid_price), qty))
        if sell_room > 0:
            ask_price = max(best_ask - 1, math.ceil(fair + edge))
            if ask_price > best_bid:
                qty = min(size, sell_room)
                if qty > 0:
                    orders.append(Order(product, int(ask_price), -qty))
        return orders

    def _trade_translator(self, product: str, depth: OrderDepth, pos: int, data: dict, mid: float, fair_adj: float) -> List[Order]:
        starts = data.setdefault("translator_starts", {})
        fast_d = data.setdefault("translator_fast", {})
        slow_d = data.setdefault("translator_slow", {})

        starts.setdefault(product, mid)
        start_mid = float(starts[product])

        fast_mid = float(fast_d.get(product, mid))
        slow_mid = float(slow_d.get(product, mid))
        fast_mid = 0.96 * fast_mid + 0.04 * mid
        slow_mid = 0.998 * slow_mid + 0.002 * mid
        fast_d[product] = fast_mid
        slow_d[product] = slow_mid

        cfg = self._translator_config(product, start_mid)
        orders: List[Order] = []
        use_passive = True

        if product in self.TRANSLATOR_ANCHOR and abs(start_mid - 10000.0) > 100.0:
            target = 0
            if product == "TRANSLATOR_GRAPHITE_MIST" and start_mid > 10250.0:
                use_passive = False
                if mid > start_mid + self.TRANSLATOR_GRAPHITE_FLAT:
                    target = 0
                elif mid < start_mid - self.TRANSLATOR_GRAPHITE_CONFIRM:
                    target = -self.LIMIT
                else:
                    target = -self.TRANSLATOR_GRAPHITE_SCOUT
            elif mid > 10250.0:
                target = -self.LIMIT
            elif mid < 9750.0:
                target = self.LIMIT
            orders.extend(self._translator_cross_to_target(product, depth, pos, target))
        elif product in self.TRANSLATOR_NEAR_ANCHOR and abs(start_mid - 10000.0) <= 100.0:
            signal = fast_mid - slow_mid
            if signal > 30.0:
                orders.extend(self._translator_cross_to_target(product, depth, pos, -self.LIMIT))
            elif signal < -30.0:
                orders.extend(self._translator_cross_to_target(product, depth, pos, self.LIMIT))

        fair = mid - cfg["inv"] * float(pos) + fair_adj
        exp_pos = pos + sum(o.quantity for o in orders)
        if use_passive:
            orders.extend(self._translator_passive_quotes(product, depth, exp_pos, fair, cfg))
        return orders

    def _simple_mm(self, product: str, depth: OrderDepth, pos: int) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask, _, _ = self._best(depth)
        if best_bid is None or best_ask is None:
            return orders
        bid_price = best_bid + 1
        ask_price = best_ask - 1
        if bid_price >= ask_price:
            return orders
        buy_room = self.LIMIT - pos
        sell_room = self.LIMIT + pos
        if buy_room > 0:
            orders.append(Order(product, bid_price, min(buy_room, 10)))
        if sell_room > 0:
            orders.append(Order(product, ask_price, -min(sell_room, 10)))
        return orders

    def _trade_cotton_reversion(self, state: TradingState, pos: int) -> List[Order]:
        prod = "SLEEP_POD_COTTON"
        depth = state.order_depths.get(prod)
        if depth is None:
            return []
        mid = self._mid(depth)
        if mid is None:
            return []

        cluster_prods = ("SLEEP_POD_SUEDE", "SLEEP_POD_LAMB_WOOL", "SLEEP_POD_POLYESTER", "SLEEP_POD_NYLON")
        cluster_mids = []
        for p in cluster_prods:
            d = state.order_depths.get(p)
            if d is not None:
                m = self._mid(d)
                if m is not None:
                    cluster_mids.append(m)

        if len(cluster_mids) < 2:
            return self._simple_mm(prod, depth, pos)

        sorted_m = sorted(cluster_mids)
        n = len(sorted_m)
        median = sorted_m[n // 2] if n % 2 == 1 else (sorted_m[n // 2 - 1] + sorted_m[n // 2]) / 2.0
        mad = sum(abs(m - median) for m in cluster_mids) / len(cluster_mids)

        if mad < 5.0:
            return self._simple_mm(prod, depth, pos)

        z = (mid - median) / max(1.0, mad)

        if abs(z) >= 1.25:
            target = -self.LIMIT if z > 0 else self.LIMIT
        elif abs(z) >= 0.45:
            target = -5 if z > 0 else 5
        else:
            target = 0

        orders: List[Order] = []
        delta = target - pos
        best_bid, best_ask, _, _ = self._best(depth)
        if delta > 0 and best_ask is not None:
            qty = min(delta, self.LIMIT - pos)
            if qty > 0:
                orders.append(Order(prod, best_ask, qty))
        elif delta < 0 and best_bid is not None:
            qty = min(-delta, self.LIMIT + pos)
            if qty > 0:
                orders.append(Order(prod, best_bid, -qty))

        if abs(z) < 1.25:
            sim_pos = pos + sum(o.quantity for o in orders)
            orders.extend(self._simple_mm(prod, depth, sim_pos))

        return orders

    def run(self, state: TradingState):
        data = self._load(state.traderData)
        if int(data.get("last_timestamp", -1)) >= 0 and state.timestamp < int(data.get("last_timestamp", -1)):
            data = self._reset_data(state.timestamp)
        data["last_timestamp"] = state.timestamp

        all_mids: Dict[str, float] = {}
        for _prod, _depth in state.order_depths.items():
            _m = self._mid(_depth)
            if _m is not None:
                all_mids[_prod] = _m

        scores = self._update_features(state, data)
        fair_adjs = self._compute_fair_adjs(all_mids, data)
        result: Dict[Symbol, List[Order]] = {}

        # --- Galaxy pairs ---
        g_hist, g_tgt = self._GALAXY.load_state(data.get("galaxy", {}))
        galaxy_orders, g_next_tgt = self._GALAXY.run(state, g_hist, g_tgt)
        data["galaxy"] = self._GALAXY.dump_state(g_hist, g_next_tgt)
        galaxy_handled: set = set(galaxy_orders.keys())
        result.update(galaxy_orders)

        dishes_hist_in = list(data.get("dishes_mid_hist") or []) if isinstance(data.get("dishes_mid_hist"), list) else []

        for product in self.PRODUCTS:
            if product in self.BLOCKED_PRODUCTS:
                continue
            if product in galaxy_handled:
                continue
            depth = state.order_depths.get(product)
            if depth is None:
                continue
            mid = self._mid(depth)
            pos = int(state.position.get(product, 0))

            orders: Optional[List[Order]] = None

            if mid is None:
                continue

            krec = data.get("kalman", {}).get(product)
            kalman_x = float(krec[0]) if isinstance(krec, list) and len(krec) == 2 else float(mid)
            if product == "ROBOT_DISHES":
                od, new_hist = self._trade_dishes_risk_managed(
                    depth,
                    float(mid),
                    pos,
                    dishes_hist_in,
                    float(scores.get(product, 0.0)),
                    float(kalman_x),
                    fair_adjs.get(product, 0.0),
                )
                dishes_hist_in = new_hist
                orders = od
            elif product in self._ALPHA_TREND_LONG:
                orders = self._alpha_trend_max_long(product, depth, pos)
            elif product == "ROBOT_IRONING":
                orders = self._alpha_trend_max_short(product, depth, pos)
            elif product in self.TRANSLATOR_PRODUCTS:
                orders = self._trade_translator(product, depth, pos, data, float(mid), fair_adjs.get(product, 0.0))
            elif product in self._SIMPLE_MM_PRODUCTS:
                # For very noisy / spread-driven products, avoid taker logic and just quote inside spread.
                # This is also the only path that meaningfully trades SLEEP_POD_LAMB_WOOL.
                orders = self._simple_mm(product, depth, pos)

            if orders is not None:
                if orders:
                    clipped = self._clip_orders_to_position_limit(product, pos, orders)
                    if clipped:
                        result[product] = clipped
                continue

            open_mom_target = self._open_mom_target(product, data, float(mid)) if mid is not None else None
            if open_mom_target is not None:
                trend_target = int(open_mom_target)
            else:
                trend_target = self._trend_target(product, data, float(mid)) if mid is not None else None
            default_orders = self._trade_product(
                product,
                depth,
                int(state.position.get(product, 0)),
                float(scores.get(product, 0.0)),
                trend_target,
                float(kalman_x),
                fair_adjs.get(product, 0.0),
            )
            if default_orders:
                clipped = self._clip_orders_to_position_limit(
                    product, int(state.position.get(product, 0)), default_orders
                )
                if clipped:
                    result[product] = clipped

        data["dishes_mid_hist"] = dishes_hist_in

        return result, 0, self._dump(data)
