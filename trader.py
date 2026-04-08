from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:

    def bid(self):
        return 15

    def run(self, state: TradingState):
        result = {}

        if "EMERALDS" in state.order_depths:
            orders: List[Order] = []

            # Constants
            FAIR_VALUE = 10000
            POSITION_LIMIT = 80

            # TODO: Get current EMERALDS position from state.position
            #       Use .get() with default 0 (position dict may be empty on first tick)
            pos = state.position.get("EMERALDS", 0)

            # TODO: Calculate how many more units we're allowed to buy and sell
            #       max_buy  = how far we are from +80  (POSITION_LIMIT - pos)
            #       max_sell = how far we are from -80  (POSITION_LIMIT + pos)
            max_buy = POSITION_LIMIT - pos
            max_sell = POSITION_LIMIT + pos 

            order_depth: OrderDepth = state.order_depths["EMERALDS"]

            # Sell orders look like: {10008: -14, 10010: -29}
            #   - keys   = prices
            #   - values = NEGATIVE quantities (e.g., -14 means 14 units for sale)
            #
            # Loop through sell_orders sorted by price ASCENDING (cheapest first)
            # For each price below FAIR_VALUE:
            #   - figure out how many units are available (negate the volume)
            #   - buy the min of (available, max_buy)
            #   - append Order("EMERALDS", price, qty)  ← positive qty = BUY
            #   - subtract from max_buy so we don't exceed the position limit
            for price in sorted(order_depth.sell_orders.keys()):
                if price < FAIR_VALUE and max_buy > 0:
                    # TODO: calculate available quantity (remember: volumes are negative!)
                    available = -order_depth.sell_orders[price]
                    qty = abs(min(available, max_buy))
                    # TODO: append a BUY order and update max_buy
                    orders.append(Order("EMERALDS", price, qty))
                    max_buy -= qty

            # Buy orders look like: {9992: 14, 9990: 29}
            #   - keys   = prices
            #   - values = POSITIVE quantities
            #
            # Loop through buy_orders sorted by price DESCENDING (highest first)
            # For each price above FAIR_VALUE:
            #   - sell the min of (available, max_sell)
            #   - append Order("EMERALDS", price, -qty)  ← negative qty = SELL
            #   - subtract from max_sell
            for price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if price > FAIR_VALUE and max_sell > 0:
                    # TODO: calculate available quantity
                    available = order_depth.buy_orders[price]
                    qty = min(available, max_sell)
                    # TODO: append a SELL order and update max_sell
                    orders.append(Order("EMERALDS", price, -qty))
                    max_sell -= qty

            # Use whatever buy/sell capacity remains after taking
            # Post a BID (buy order) at 9998 — we're offering to buy 2 below fair value
            # Post an ASK (sell order) at 10002 — we're offering to sell 2 above fair value
            if max_buy > 0:
                orders.append(Order("EMERALDS", 9998, max_buy))

            if max_sell > 0:
                orders.append(Order("EMERALDS", 10002, -max_sell))

            result["EMERALDS"] = orders

        # ── Step 5: Return ──────────────────────────────────────────────────
        # Must return: (result dict, conversions int, traderData string)
        # conversions = 0 (we don't use conversions for EMERALDS)
        # traderData = "" (no state to persist for this simple strategy)
        traderData = ""
        conversions = 0
        return result, conversions, traderData
