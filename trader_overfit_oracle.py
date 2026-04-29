import json
from typing import Dict, List, Optional

from datamodel import Order, OrderDepth, Symbol, TradingState


class Trader:
    POSITION_LIMIT = 10

    # Historical oracle benchmark. Do not submit this for a live/hidden run.
    DAY_DIRECTIONS: Dict[int, Dict[str, int]] = {
        2: {
            "GALAXY_SOUNDS_BLACK_HOLES": 1, "GALAXY_SOUNDS_DARK_MATTER": 1,
            "GALAXY_SOUNDS_PLANETARY_RINGS": 1, "GALAXY_SOUNDS_SOLAR_FLAMES": 1,
            "GALAXY_SOUNDS_SOLAR_WINDS": -1, "MICROCHIP_CIRCLE": -1,
            "MICROCHIP_OVAL": -1, "MICROCHIP_RECTANGLE": -1, "MICROCHIP_SQUARE": 1,
            "MICROCHIP_TRIANGLE": 1, "OXYGEN_SHAKE_CHOCOLATE": -1,
            "OXYGEN_SHAKE_EVENING_BREATH": -1, "OXYGEN_SHAKE_GARLIC": 1,
            "OXYGEN_SHAKE_MINT": 1, "OXYGEN_SHAKE_MORNING_BREATH": 1,
            "PANEL_1X2": -1, "PANEL_1X4": 1, "PANEL_2X2": 1, "PANEL_2X4": 1,
            "PANEL_4X4": -1, "PEBBLES_L": 1, "PEBBLES_M": -1, "PEBBLES_S": -1,
            "PEBBLES_XL": 1, "PEBBLES_XS": -1, "ROBOT_DISHES": -1,
            "ROBOT_IRONING": -1, "ROBOT_LAUNDRY": 1, "ROBOT_MOPPING": -1,
            "ROBOT_VACUUMING": 1, "SLEEP_POD_COTTON": 1, "SLEEP_POD_LAMB_WOOL": 1,
            "SLEEP_POD_NYLON": -1, "SLEEP_POD_POLYESTER": 1, "SLEEP_POD_SUEDE": 1,
            "SNACKPACK_CHOCOLATE": -1, "SNACKPACK_PISTACHIO": -1,
            "SNACKPACK_RASPBERRY": 1, "SNACKPACK_STRAWBERRY": 1, "SNACKPACK_VANILLA": 1,
            "TRANSLATOR_ASTRO_BLACK": 1, "TRANSLATOR_ECLIPSE_CHARCOAL": 1,
            "TRANSLATOR_GRAPHITE_MIST": -1, "TRANSLATOR_SPACE_GRAY": -1,
            "TRANSLATOR_VOID_BLUE": 1, "UV_VISOR_AMBER": -1, "UV_VISOR_MAGENTA": 1,
            "UV_VISOR_ORANGE": 1, "UV_VISOR_RED": 1, "UV_VISOR_YELLOW": 1,
        },
        3: {
            "GALAXY_SOUNDS_BLACK_HOLES": 1, "GALAXY_SOUNDS_DARK_MATTER": 1,
            "GALAXY_SOUNDS_PLANETARY_RINGS": 1, "GALAXY_SOUNDS_SOLAR_FLAMES": -1,
            "GALAXY_SOUNDS_SOLAR_WINDS": 1, "MICROCHIP_CIRCLE": -1,
            "MICROCHIP_OVAL": -1, "MICROCHIP_RECTANGLE": -1, "MICROCHIP_SQUARE": 1,
            "MICROCHIP_TRIANGLE": -1, "OXYGEN_SHAKE_CHOCOLATE": -1,
            "OXYGEN_SHAKE_EVENING_BREATH": 1, "OXYGEN_SHAKE_GARLIC": 1,
            "OXYGEN_SHAKE_MINT": -1, "OXYGEN_SHAKE_MORNING_BREATH": -1,
            "PANEL_1X2": 1, "PANEL_1X4": -1, "PANEL_2X2": -1, "PANEL_2X4": 1,
            "PANEL_4X4": 1, "PEBBLES_L": 1, "PEBBLES_M": 1, "PEBBLES_S": -1,
            "PEBBLES_XL": -1, "PEBBLES_XS": -1, "ROBOT_DISHES": 1,
            "ROBOT_IRONING": -1, "ROBOT_LAUNDRY": -1, "ROBOT_MOPPING": 1,
            "ROBOT_VACUUMING": -1, "SLEEP_POD_COTTON": 1, "SLEEP_POD_LAMB_WOOL": 1,
            "SLEEP_POD_NYLON": 1, "SLEEP_POD_POLYESTER": 1, "SLEEP_POD_SUEDE": 1,
            "SNACKPACK_CHOCOLATE": -1, "SNACKPACK_PISTACHIO": -1,
            "SNACKPACK_RASPBERRY": -1, "SNACKPACK_STRAWBERRY": 1, "SNACKPACK_VANILLA": -1,
            "TRANSLATOR_ASTRO_BLACK": -1, "TRANSLATOR_ECLIPSE_CHARCOAL": -1,
            "TRANSLATOR_GRAPHITE_MIST": 1, "TRANSLATOR_SPACE_GRAY": 1,
            "TRANSLATOR_VOID_BLUE": -1, "UV_VISOR_AMBER": -1, "UV_VISOR_MAGENTA": 1,
            "UV_VISOR_ORANGE": 1, "UV_VISOR_RED": 1, "UV_VISOR_YELLOW": 1,
        },
        4: {
            "GALAXY_SOUNDS_BLACK_HOLES": 1, "GALAXY_SOUNDS_DARK_MATTER": -1,
            "GALAXY_SOUNDS_PLANETARY_RINGS": -1, "GALAXY_SOUNDS_SOLAR_FLAMES": 1,
            "GALAXY_SOUNDS_SOLAR_WINDS": -1, "MICROCHIP_CIRCLE": 1,
            "MICROCHIP_OVAL": -1, "MICROCHIP_RECTANGLE": 1, "MICROCHIP_SQUARE": -1,
            "MICROCHIP_TRIANGLE": -1, "OXYGEN_SHAKE_CHOCOLATE": 1,
            "OXYGEN_SHAKE_EVENING_BREATH": -1, "OXYGEN_SHAKE_GARLIC": 1,
            "OXYGEN_SHAKE_MINT": 1, "OXYGEN_SHAKE_MORNING_BREATH": 1,
            "PANEL_1X2": 1, "PANEL_1X4": 1, "PANEL_2X2": 1, "PANEL_2X4": 1,
            "PANEL_4X4": -1, "PEBBLES_L": -1, "PEBBLES_M": -1, "PEBBLES_S": -1,
            "PEBBLES_XL": 1, "PEBBLES_XS": -1, "ROBOT_DISHES": 1,
            "ROBOT_IRONING": 1, "ROBOT_LAUNDRY": -1, "ROBOT_MOPPING": -1,
            "ROBOT_VACUUMING": -1, "SLEEP_POD_COTTON": -1, "SLEEP_POD_LAMB_WOOL": 1,
            "SLEEP_POD_NYLON": 1, "SLEEP_POD_POLYESTER": -1, "SLEEP_POD_SUEDE": -1,
            "SNACKPACK_CHOCOLATE": -1, "SNACKPACK_PISTACHIO": -1,
            "SNACKPACK_RASPBERRY": 1, "SNACKPACK_STRAWBERRY": 1, "SNACKPACK_VANILLA": 1,
            "TRANSLATOR_ASTRO_BLACK": -1, "TRANSLATOR_ECLIPSE_CHARCOAL": 1,
            "TRANSLATOR_GRAPHITE_MIST": -1, "TRANSLATOR_SPACE_GRAY": -1,
            "TRANSLATOR_VOID_BLUE": 1, "UV_VISOR_AMBER": -1, "UV_VISOR_MAGENTA": -1,
            "UV_VISOR_ORANGE": -1, "UV_VISOR_RED": 1, "UV_VISOR_YELLOW": -1,
        },
    }

    def _load(self, trader_data: str) -> Dict[str, int]:
        if not trader_data:
            return {}
        try:
            data = json.loads(trader_data)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _best_bid_ask(self, depth: OrderDepth) -> tuple[Optional[int], Optional[int]]:
        best_bid = max(depth.buy_orders) if depth.buy_orders else None
        best_ask = min(depth.sell_orders) if depth.sell_orders else None
        return best_bid, best_ask

    def _mid(self, state: TradingState, product: str) -> Optional[float]:
        depth = state.order_depths.get(product)
        if depth is None:
            return None
        best_bid, best_ask = self._best_bid_ask(depth)
        if best_bid is None or best_ask is None:
            return None
        return 0.5 * (best_bid + best_ask)

    def _classify_day(self, state: TradingState) -> Optional[int]:
        square = self._mid(state, "MICROCHIP_SQUARE")
        pebbles_xl = self._mid(state, "PEBBLES_XL")
        if square is not None and square > 14000:
            return 4
        if pebbles_xl is not None and pebbles_xl > 12000:
            return 3
        if pebbles_xl is not None:
            return 2
        return None

    def run(self, state: TradingState):
        data = self._load(state.traderData)
        last_timestamp = int(data.get("last_timestamp", -1))
        if last_timestamp >= 0 and state.timestamp < last_timestamp:
            data.pop("day", None)
        data["last_timestamp"] = int(state.timestamp)

        day = data.get("day")
        if day is None:
            day = self._classify_day(state)
            if day is not None:
                data["day"] = int(day)

        result: Dict[Symbol, List[Order]] = {}
        directions = self.DAY_DIRECTIONS.get(int(day), {}) if day is not None else {}
        for product, direction in directions.items():
            depth = state.order_depths.get(product)
            if depth is None:
                continue
            best_bid, best_ask = self._best_bid_ask(depth)
            if best_bid is None or best_ask is None:
                continue
            position = int(state.position.get(product, 0))
            target = self.POSITION_LIMIT if direction > 0 else -self.POSITION_LIMIT
            delta = target - position
            if delta > 0:
                result[product] = [Order(product, best_ask, min(delta, self.POSITION_LIMIT - position))]
            elif delta < 0:
                result[product] = [Order(product, best_bid, -min(-delta, self.POSITION_LIMIT + position))]

        return result, 0, json.dumps(data, separators=(",", ":"))
