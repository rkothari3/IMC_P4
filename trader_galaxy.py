import json
import math
from typing import Optional

from datamodel import Order, OrderDepth, Symbol, TradingState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def best_bid_ask(order_depth: OrderDepth) -> tuple[Optional[int], Optional[int]]:
    best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
    best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
    return best_bid, best_ask


def mid_price(order_depth: OrderDepth) -> Optional[float]:
    best_bid, best_ask = best_bid_ask(order_depth)
    if best_bid is None or best_ask is None:
        return None
    return (best_bid + best_ask) / 2.0


def clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def clean_history(raw_values, history_limit: int) -> list[int]:
    cleaned: list[int] = []
    if not isinstance(raw_values, list):
        return cleaned
    for value in raw_values[-history_limit:]:
        try:
            cleaned.append(int(value))
        except (TypeError, ValueError):
            continue
    return cleaned


def rolling_spread_z_score(
    history: list[int],
    current_value: int,
    window: int,
    min_history: int,
) -> Optional[float]:
    lookback = history[-window:]
    if len(lookback) < min_history:
        return None
    mean = sum(lookback) / len(lookback)
    mean_square = sum(v * v for v in lookback) / len(lookback)
    variance = max(0.0, mean_square - mean * mean)
    std = math.sqrt(variance)
    if std <= 0.0:
        return None
    return (current_value - mean) / std


def order_to_target(
    product: Symbol,
    order_depth: OrderDepth,
    current_position: int,
    target_position: int,
    position_limit: int,
    max_order_size: int,
) -> list[Order]:
    orders: list[Order] = []
    target_position = clamp(target_position, -position_limit, position_limit)
    desired_delta = target_position - current_position
    if desired_delta == 0:
        return orders
    best_bid, best_ask = best_bid_ask(order_depth)
    if desired_delta > 0:
        if best_ask is None:
            return orders
        visible_volume = max(0, -order_depth.sell_orders.get(best_ask, 0))
        limit_room = max(0, position_limit - current_position)
        quantity = min(desired_delta, visible_volume, limit_room, max_order_size)
        if quantity > 0:
            orders.append(Order(product, best_ask, quantity))
        return orders
    if best_bid is None:
        return orders
    visible_volume = max(0, order_depth.buy_orders.get(best_bid, 0))
    limit_room = max(0, position_limit + current_position)
    quantity = min(-desired_delta, visible_volume, limit_room, max_order_size)
    if quantity > 0:
        orders.append(Order(product, best_bid, -quantity))
    return orders


def market_make(
    product: Symbol,
    order_depth: OrderDepth,
    current_position: int,
    position_limit: int,
    max_order_size: int,
) -> list[Order]:
    orders: list[Order] = []
    best_bid, best_ask = best_bid_ask(order_depth)
    if best_bid is None or best_ask is None:
        return orders
    bid_price = best_bid + 1
    ask_price = best_ask - 1
    if bid_price >= ask_price:
        return orders
    buy_room = max(0, position_limit - current_position)
    buy_quantity = min(buy_room, max_order_size)
    if buy_quantity > 0:
        orders.append(Order(product, bid_price, buy_quantity))
    sell_room = max(0, position_limit + current_position)
    sell_quantity = min(sell_room, max_order_size)
    if sell_quantity > 0:
        orders.append(Order(product, ask_price, -sell_quantity))
    return orders


# ---------------------------------------------------------------------------
# Galaxy Sounds module
# ---------------------------------------------------------------------------

class GalaxyPairsModule:
    PAIRS: tuple[tuple[str, Symbol, Symbol, int, int, float], ...] = (
        ("dmbh", "GALAXY_SOUNDS_DARK_MATTER", "GALAXY_SOUNDS_BLACK_HOLES", 3000, 3000, 2.50),
        ("swsf", "GALAXY_SOUNDS_SOLAR_WINDS", "GALAXY_SOUNDS_SOLAR_FLAMES", 1500, 1500, 3.00),
    )
    TARGET_SIZE = 10
    POSITION_LIMIT = 10
    MAX_ORDER_SIZE = 10
    RESIDUAL_SCALE = 10
    HOLD_TO_FLIP = True

    def empty_state(self) -> tuple[dict[str, list[int]], dict[str, int]]:
        return (
            {name: [] for name, *_ in self.PAIRS},
            {name: 0 for name, *_ in self.PAIRS},
        )

    def load_state(self, loaded) -> tuple[dict[str, list[int]], dict[str, int]]:
        histories, targets = self.empty_state()
        if not isinstance(loaded, dict):
            return histories, targets
        raw_histories = loaded.get("h", {})
        if isinstance(raw_histories, dict):
            for name, _, _, window, _, _ in self.PAIRS:
                histories[name] = clean_history(raw_histories.get(name, []), window)
        raw_targets = loaded.get("t", {})
        if isinstance(raw_targets, dict):
            for name, *_ in self.PAIRS:
                try:
                    target = int(raw_targets.get(name, 0))
                except (TypeError, ValueError):
                    target = 0
                targets[name] = clamp(target, -self.TARGET_SIZE, self.TARGET_SIZE)
        return histories, targets

    def dump_state(self, histories: dict[str, list[int]], targets: dict[str, int]) -> dict:
        return {
            "h": {name: histories.get(name, [])[-window:] for name, _, _, window, *_ in self.PAIRS},
            "t": {name: int(targets.get(name, 0)) for name, *_ in self.PAIRS},
        }

    def target_from_signal(
        self,
        previous_target: int,
        z_score: Optional[float],
        has_min_history: bool,
        entry_z: float,
    ) -> int:
        if not has_min_history or z_score is None:
            return 0 if not has_min_history else previous_target
        if z_score > entry_z:
            return -self.TARGET_SIZE
        if z_score < -entry_z:
            return self.TARGET_SIZE
        return previous_target

    def run(
        self,
        state: TradingState,
        histories: dict[str, list[int]],
        targets: dict[str, int],
        result: dict[Symbol, list[Order]],
    ) -> dict[str, int]:
        next_targets: dict[str, int] = {name: targets.get(name, 0) for name, *_ in self.PAIRS}
        diffs: dict[str, int] = {}
        active_pairs: list[tuple[str, Symbol, Symbol, int, int, float]] = []

        for pair in self.PAIRS:
            name, prod_a, prod_b, window, min_history, entry_z = pair
            depth_a = state.order_depths.get(prod_a)
            depth_b = state.order_depths.get(prod_b)
            if depth_a is None or depth_b is None:
                continue
            mid_a = mid_price(depth_a)
            mid_b = mid_price(depth_b)
            if mid_a is None or mid_b is None:
                continue
            diff = int(round((mid_a - mid_b) * self.RESIDUAL_SCALE))
            history = histories[name]
            has_min_history = len(history) >= min_history
            z_score = rolling_spread_z_score(history, diff, window, min_history)
            next_targets[name] = self.target_from_signal(
                targets.get(name, 0), z_score, has_min_history, entry_z
            )
            diffs[name] = diff
            active_pairs.append(pair)

        for name, prod_a, prod_b, _, _, _ in active_pairs:
            target = next_targets[name]
            orders_a = order_to_target(
                prod_a,
                state.order_depths[prod_a],
                state.position.get(prod_a, 0),
                target,
                self.POSITION_LIMIT,
                self.MAX_ORDER_SIZE,
            )
            if orders_a:
                result[prod_a] = orders_a
            orders_b = order_to_target(
                prod_b,
                state.order_depths[prod_b],
                state.position.get(prod_b, 0),
                -target,
                self.POSITION_LIMIT,
                self.MAX_ORDER_SIZE,
            )
            if orders_b:
                result[prod_b] = orders_b

        for name, _, _, window, _, _ in active_pairs:
            history = histories[name]
            history.append(diffs[name])
            if len(history) > window:
                del history[: len(history) - window]

        return next_targets


# ---------------------------------------------------------------------------
# Standalone Trader
# ---------------------------------------------------------------------------

class Trader:
    GALAXY_STATE_KEY = "gx"

    def __init__(self) -> None:
        self.galaxy = GalaxyPairsModule()

    def _load_json(self, trader_data: str) -> dict:
        if not trader_data:
            return {}
        try:
            loaded = json.loads(trader_data)
        except Exception:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def run(self, state: TradingState):
        loaded = self._load_json(state.traderData)
        histories, targets = self.galaxy.load_state(loaded.get(self.GALAXY_STATE_KEY, {}))

        result: dict[Symbol, list[Order]] = {}
        next_targets = self.galaxy.run(state, histories, targets, result)

        # Market make any galaxy product without an active signal
        active_products: set[Symbol] = set()
        for name, prod_a, prod_b, *_ in self.galaxy.PAIRS:
            if next_targets.get(name, 0) != 0:
                active_products.add(prod_a)
                active_products.add(prod_b)

        for product, depth in state.order_depths.items():
            if product not in active_products:
                mm_orders = market_make(
                    product,
                    depth,
                    state.position.get(product, 0),
                    position_limit=10,
                    max_order_size=10,
                )
                if mm_orders:
                    result[product] = mm_orders

        trader_data = json.dumps(
            {self.GALAXY_STATE_KEY: self.galaxy.dump_state(histories, next_targets)},
            separators=(",", ":"),
        )
        return result, 0, trader_data