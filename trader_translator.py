import json
import math
from typing import Dict, List, Optional, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    LIMIT = 10

    PRODUCTS = {
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_SPACE_GRAY",
        "TRANSLATOR_VOID_BLUE",
    }

    ANCHOR_PRODUCTS = {
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_SPACE_GRAY",
    }
    NEAR_ANCHOR_REVERT = {
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_GRAPHITE_MIST",
    }
    GRAPHITE_SCOUT_SIZE = 5
    GRAPHITE_CONFIRM_MOVE = 70.0
    GRAPHITE_FLAT_MOVE = 90.0

    # Default values are overwritten dynamically in _config_for.
    CONFIG = {product: {"edge": 3, "size": 10, "inv": 0.0} for product in PRODUCTS}

    def _best(self, od: OrderDepth) -> Tuple[Optional[int], Optional[int], int, int]:
        if not od.buy_orders or not od.sell_orders:
            return None, None, 0, 0
        bid = max(od.buy_orders)
        ask = min(od.sell_orders)
        return bid, ask, od.buy_orders[bid], -od.sell_orders[ask]

    def _mid_and_imbalance(self, od: OrderDepth) -> Tuple[Optional[float], float, float, float]:
        bid, ask, bid_vol, ask_vol = self._best(od)
        if bid is None or ask is None:
            return None, 0.0, 0.0, 0.0

        total = bid_vol + ask_vol
        mid = (bid + ask) / 2.0 if total <= 0 else (bid * ask_vol + ask * bid_vol) / total
        l1_imb = 0.0 if total <= 0 else (bid_vol - ask_vol) / total

        bid_depth = sum(max(0, v) for v in od.buy_orders.values())
        ask_depth = sum(max(0, -v) for v in od.sell_orders.values())
        depth_total = bid_depth + ask_depth
        book_imb = 0.0 if depth_total <= 0 else (bid_depth - ask_depth) / depth_total
        spread = ask - bid
        return mid, l1_imb, book_imb, spread

    def _load_data(self, state: TradingState) -> Dict:
        try:
            data = json.loads(state.traderData) if state.traderData else {}
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _orders_for_product(
        self, product: str, od: OrderDepth, position: int, fair: float, cfg: Dict[str, float]
    ) -> List[Order]:
        edge = cfg["edge"]
        size = cfg["size"]
        orders: List[Order] = []

        bid, ask, _, _ = self._best(od)
        if bid is None or ask is None:
            return orders

        buy_room = self.LIMIT - position
        sell_room = self.LIMIT + position

        if buy_room > 0:
            bid_price = min(bid + 1, math.floor(fair - edge))
            if bid_price < ask:
                qty = min(size, buy_room)
                if qty > 0:
                    orders.append(Order(product, int(bid_price), qty))

        if sell_room > 0:
            ask_price = max(ask - 1, math.ceil(fair + edge))
            if ask_price > bid:
                qty = min(size, sell_room)
                if qty > 0:
                    orders.append(Order(product, int(ask_price), -qty))

        return orders

    def _config_for(self, product: str, start_mid: float) -> Dict[str, float]:
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

    def _cross_to_target(self, product: str, od: OrderDepth, position: int, target: int) -> List[Order]:
        orders: List[Order] = []
        delta = target - position
        bid, ask, _, _ = self._best(od)
        if bid is None or ask is None:
            return orders

        if delta > 0:
            qty = min(delta, -od.sell_orders[ask])
            if qty > 0:
                orders.append(Order(product, ask, qty))
        elif delta < 0:
            qty = min(-delta, od.buy_orders[bid])
            if qty > 0:
                orders.append(Order(product, bid, -qty))

        return orders

    def run(self, state: TradingState):
        data = self._load_data(state)
        result: Dict[str, List[Order]] = {}
        starts = data.setdefault("starts", {})
        fast = data.setdefault("fast", {})
        slow = data.setdefault("slow", {})

        for product in self.PRODUCTS:
            od = state.order_depths.get(product)
            if od is None:
                continue

            mid, l1_imb, book_imb, spread = self._mid_and_imbalance(od)
            if mid is None:
                continue

            starts.setdefault(product, mid)
            start_mid = float(starts[product])
            cfg = self._config_for(product, start_mid)
            pos = state.position.get(product, 0)
            fair = mid
            orders: List[Order] = []
            use_passive_quotes = True

            fast_mid = float(fast.get(product, mid))
            slow_mid = float(slow.get(product, mid))
            fast_mid = 0.96 * fast_mid + 0.04 * mid
            slow_mid = 0.998 * slow_mid + 0.002 * mid
            fast[product] = fast_mid
            slow[product] = slow_mid

            if product in self.ANCHOR_PRODUCTS and abs(start_mid - 10000.0) > 100.0:
                target = 0
                if product == "TRANSLATOR_GRAPHITE_MIST" and start_mid > 10250.0:
                    use_passive_quotes = False
                    if mid > start_mid + self.GRAPHITE_FLAT_MOVE:
                        target = 0
                    elif mid < start_mid - self.GRAPHITE_CONFIRM_MOVE:
                        target = -self.LIMIT
                    else:
                        target = -self.GRAPHITE_SCOUT_SIZE
                elif mid > 10250.0:
                    target = -self.LIMIT
                elif mid < 9750.0:
                    target = self.LIMIT
                orders.extend(self._cross_to_target(product, od, pos, target))
            elif product in self.NEAR_ANCHOR_REVERT and abs(start_mid - 10000.0) <= 100.0:
                signal = fast_mid - slow_mid
                target = None
                if signal > 30.0:
                    target = -self.LIMIT
                elif signal < -30.0:
                    target = self.LIMIT
                if target is not None:
                    orders.extend(self._cross_to_target(product, od, pos, target))

            fair -= cfg["inv"] * pos

            expected_pos = pos + sum(order.quantity for order in orders)
            if use_passive_quotes:
                orders.extend(self._orders_for_product(product, od, expected_pos, fair, cfg))
            if orders:
                result[product] = orders
        return result, 0, json.dumps(data, separators=(",", ":"))