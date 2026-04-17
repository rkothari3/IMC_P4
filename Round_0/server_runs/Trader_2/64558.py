from datamodel import OrderDepth, TradingState, Order
from typing import List
import math
import json


class Trader:

    def bid(self):
        return 15

    def run(self, state: TradingState):
        result = {}
        # EMERALDS — fixed fair value at 10000
        if "EMERALDS" in state.order_depths:
            orders: List[Order] = []
            FAIR_VALUE = 10000
            POSITION_LIMIT = 80

            pos = state.position.get("EMERALDS", 0)
            max_buy = POSITION_LIMIT - pos
            max_sell = POSITION_LIMIT + pos

            order_depth: OrderDepth = state.order_depths["EMERALDS"]

            for price in sorted(order_depth.sell_orders.keys()):
                if price <= FAIR_VALUE and max_buy > 0:
                    available = -order_depth.sell_orders[price]
                    qty = min(available, max_buy)
                    orders.append(Order("EMERALDS", price, qty))
                    max_buy -= qty

            for price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if price >= FAIR_VALUE and max_sell > 0:
                    available = order_depth.buy_orders[price]
                    qty = min(available, max_sell)
                    orders.append(Order("EMERALDS", price, -qty))
                    max_sell -= qty

            if max_buy > 0:
                orders.append(Order("EMERALDS", 9999, max_buy))
            if max_sell > 0:
                orders.append(Order("EMERALDS", 10001, -max_sell))

            result["EMERALDS"] = orders

        # TOMATOES — fair value drifts slowly, must estimate each tick
        #
        # Unlike EMERALDS where fair value is always 10000, TOMATOES price
        # wanders around ~5000. We estimate fair value from the order book
        # each tick, then do the same take + make strategy around it.
        #
        # Key difference: TOMATOES is MEAN-REVERTING (if price goes up,
        # it tends to come back down). This makes market making safer —
        # if we buy and the price drops, it'll likely recover.
        #
        if "TOMATOES" in state.order_depths:
            orders: List[Order] = []
            POSITION_LIMIT = 80

            pos = state.position.get("TOMATOES", 0)
            max_buy = POSITION_LIMIT - pos
            max_sell = POSITION_LIMIT + pos

            order_depth: OrderDepth = state.order_depths["TOMATOES"]

            # ── Step 1: Estimate fair value ─────────────────────────────────
            # We need to figure out what TOMATOES is "really worth" right now.
            #
            # Method: mid price = (best_bid + best_ask) / 2
            #   best_bid = highest price someone is willing to buy at
            #   best_ask = lowest price someone is willing to sell at
            #
            # Example: if buy_orders = {4993: 7, 4992: 17}
            #          and sell_orders = {5007: -7, 5008: -17}
            #          best_bid = 4993, best_ask = 5007
            #          fair_value = (4993 + 5007) / 2 = 5000.0
            #
            # TODO: Get the best bid price (hint: max() of buy_orders keys)
            # TODO: Get the best ask price (hint: min() of sell_orders keys)
            # TODO: Calculate fair_value as their average
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            fair_value = (best_bid + best_ask) / 2

            # ── Step 2: TAKE — buy any sell orders below fair value ─────────
            # Same logic as EMERALDS, but using our estimated fair_value
            # instead of a hardcoded 10000.
            #
            # Since fair_value is a float (e.g., 5000.5), we buy anything
            # priced BELOW it. An ask at exactly fair_value is not profitable.
            #
            # TODO: Loop through sell_orders sorted ascending
            #       For each price < fair_value: buy min(available, max_buy)
            #       Remember: sell_orders volumes are negative!
            for price in sorted(order_depth.sell_orders.keys()):
                if price < fair_value and max_buy > 0:
                    available = -order_depth.sell_orders[price]
                    qty = min(available, max_buy)
                    # TODO: append buy order, update max_buy
                    orders.append(Order("TOMATOES", price, qty))
                    max_buy -= qty

            # ── Step 3: TAKE — sell into any buy orders above fair value ────
            # TODO: Loop through buy_orders sorted descending
            #       For each price > fair_value: sell min(available, max_sell)
            for price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if price > fair_value and max_sell > 0:
                    available = order_depth.buy_orders[price]
                    qty = min(available, max_sell)
                    # TODO: append sell order, update max_sell
                    orders.append(Order("TOMATOES", price, -qty))
                    max_sell -= qty

            # ── Step 4: MAKE — post passive quotes ──────────────────────────
            # Post bid/ask around our estimated fair value.
            #
            # Since Order prices must be integers, we round:
            #   bid_price = floor(fair_value) - 1   (buy a bit below)
            #   ask_price = ceil(fair_value) + 1     (sell a bit above)
            #
            # Example: fair_value = 5000.5
            #   bid_price = floor(5000.5) - 1 = 4999
            #   ask_price = ceil(5000.5) + 1  = 5002
            #   → we earn 3 per round trip (buy at 4999, sell at 5002)
            #
            # math.floor() rounds down, math.ceil() rounds up
            #
            # Skew quotes toward fair value when carrying inventory.
            # If long (pos > 0), shift both quotes down to sell more aggressively.
            # If short (pos < 0), shift both quotes up to buy more aggressively.
            # Scale: ±3 ticks max at position limit.
            skew = round(3 * pos / POSITION_LIMIT)
            bid_price = math.floor(fair_value) - 1 - skew
            ask_price = math.ceil(fair_value) + 1 - skew

            if max_buy > 0:
                # TODO: append buy order at bid_price
                orders.append(Order("TOMATOES", bid_price, max_buy))
            if max_sell > 0:
                # TODO: append sell order at ask_price
                orders.append(Order("TOMATOES", ask_price, -max_sell))

            result["TOMATOES"] = orders

        # Log positions each tick so the dashboard can plot exact position over time.
        # These appear in the sandboxLog of the server run output.
        print(f"POS {state.timestamp} " + " ".join(
            f"{p}:{state.position.get(p, 0)}" for p in state.order_depths
        ))

        traderData = ""
        conversions = 0
        return result, conversions, traderData