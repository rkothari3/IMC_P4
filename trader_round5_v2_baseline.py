import json
import math
from typing import Dict, List, Optional, Tuple

from datamodel import Order, OrderDepth, Symbol, TradingState


class Trader:
    LIMIT = 10
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

    # Small product priors, not day labels. They are deliberately weak: they
    # only skew quote placement until live momentum confirms or rejects them.
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
        ("SLEEP_POD_POLYESTER", "UV_VISOR_AMBER", -1.0),
        ("MICROCHIP_SQUARE", "SLEEP_POD_SUEDE", 1.0),
        ("MICROCHIP_OVAL", "ROBOT_IRONING", 1.0),
        ("GALAXY_SOUNDS_BLACK_HOLES", "OXYGEN_SHAKE_GARLIC", 1.0),
        ("MICROCHIP_SQUARE", "MICROCHIP_RECTANGLE", -1.0),
        ("PEBBLES_XL", "PEBBLES_L", -1.0),
    )

    BLOCKED_PRODUCTS = {
        "GALAXY_SOUNDS_SOLAR_FLAMES",
        "MICROCHIP_TRIANGLE",
        "UV_VISOR_MAGENTA",
        "PANEL_4X4",
        "PANEL_1X2",
        "ROBOT_MOPPING",
        "ROBOT_VACUUMING",
        "SLEEP_POD_LAMB_WOOL",
    }

    TREND_OVERLAY = {
        "MICROCHIP_SQUARE": {"threshold": 300.0, "min_ticks": 400},
        "PEBBLES_XS": {"threshold": 10.0, "min_ticks": 400},
        "UV_VISOR_AMBER": {"threshold": 10.0, "min_ticks": 25},
        "SLEEP_POD_NYLON": {"threshold": 25.0, "min_ticks": 800},
        "OXYGEN_SHAKE_GARLIC": {"threshold": 800.0, "min_ticks": 0},
    }

    # Decide-once daily overlay: at tick k, compare mid to open; then hold +/-LIMIT.
    OPEN_MOM_OVERLAY = {
        "PEBBLES_XL": {"k": 1500, "th": 0.0},
        "PEBBLES_M": {"k": 2000, "th": 0.0},
        "MICROCHIP_OVAL": {"k": 1000, "th": 0.0},
        "PANEL_2X4": {"k": 2000, "th": 0.0},
        "TRANSLATOR_GRAPHITE_MIST": {"k": 3000, "th": 0.0},
        "GALAXY_SOUNDS_BLACK_HOLES": {"k": 2000, "th": 0.0},
    }

    # Pair trading (quote tilting only): (leader a, follower b, window, lag, entry_z, weight)
    PAIRS = (
        ("UV_VISOR_AMBER", "PEBBLES_XS", 200, 20, 1.7, 0.85),
        ("MICROCHIP_OVAL", "ROBOT_IRONING", 200, 20, 1.7, 0.60),
        ("GALAXY_SOUNDS_BLACK_HOLES", "OXYGEN_SHAKE_GARLIC", 200, 20, 1.7, 0.70),
        ("SLEEP_POD_POLYESTER", "SLEEP_POD_COTTON", 200, 5, 1.5, 0.55),
    )
    PAIR_MAX_WINDOW = max(w + lag for _, _, w, lag, _, _ in PAIRS)

    def _load(self, trader_data: str) -> dict:
        base = {
            "last_timestamp": -1,
            "state": {},
            "mid_hist": {},
            "kalman": {},
            "pair_z": {},
            "open_mom_dir": {},
        }
        if not trader_data:
            return base
        try:
            raw = json.loads(trader_data)
            if isinstance(raw, dict):
                base.update(raw)
        except Exception:
            pass
        return base

    def _dump(self, data: dict) -> str:
        return json.dumps(data, separators=(",", ":"))

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

            # Maintain mid history for pair stats.
            h = mid_hist.get(product)
            if not isinstance(h, list):
                h = []
            h.append(float(mid))
            if len(h) > int(self.PAIR_MAX_WINDOW) + 5:
                del h[: len(h) - (int(self.PAIR_MAX_WINDOW) + 5)]
            mid_hist[product] = h

            # Kalman filter stabilizer (latent fair value).
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

        # Pair z-scores and quote tilting.
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
            mean = sum(spreads) / float(w)
            var = sum((s - mean) ** 2 for s in spreads) / float(max(1, w - 1))
            sd = math.sqrt(max(1e-6, var))
            cur = float(hb[-1]) - float(ha[-1 - lag])
            z = (cur - mean) / sd
            key = f"{a}|{b}"
            pair_z[key] = float(z)

            if abs(z) >= float(entry_z):
                adj = float(weight) * max(-2.2, min(2.2, float(z)))
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
        # Blend in Kalman fair lightly as a stabilizer (prevents fair from snapping).
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

    def _trade_product(self, product: str, depth: OrderDepth, pos: int, score: float, trend_target: Optional[int], kalman_x: float) -> List[Order]:
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
        fair = self._micro_fair(depth, mid, score, prior, pos, float(kalman_x))

        buy_room = self.LIMIT - pos
        sell_room = self.LIMIT + pos

        take_edge = max(2.0, 0.35 * spread + 1.0)
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

        if spread < 3 or best_bid + 1 >= best_ask:
            return orders

        # Passive quotes are the core live-safe edge. The fair-value shift and
        # inventory skew decide which side we quote more aggressively.
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

    def run(self, state: TradingState):
        data = self._load(state.traderData)
        if int(data.get("last_timestamp", -1)) >= 0 and state.timestamp < int(data.get("last_timestamp", -1)):
            data = {
                "last_timestamp": state.timestamp,
                "state": {},
                "mid_hist": {},
                "kalman": {},
                "pair_z": {},
                "open_mom_dir": {},
            }
        data["last_timestamp"] = state.timestamp

        scores = self._update_features(state, data)
        result: Dict[Symbol, List[Order]] = {}

        for product in self.PRODUCTS:
            if product in self.BLOCKED_PRODUCTS:
                continue
            depth = state.order_depths.get(product)
            if depth is None:
                continue
            mid = self._mid(depth)
            krec = data.get("kalman", {}).get(product)
            kalman_x = float(krec[0]) if isinstance(krec, list) and len(krec) == 2 else (float(mid) if mid is not None else 0.0)
            open_mom_target = self._open_mom_target(product, data, float(mid)) if mid is not None else None
            if open_mom_target is not None:
                trend_target = int(open_mom_target)
            else:
                trend_target = self._trend_target(product, data, float(mid)) if mid is not None else None
            orders = self._trade_product(
                product,
                depth,
                int(state.position.get(product, 0)),
                float(scores.get(product, 0.0)),
                trend_target,
                float(kalman_x),
            )
            if orders:
                result[product] = orders

        return result, 0, self._dump(data)
