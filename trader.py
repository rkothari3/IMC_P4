from datamodel import OrderDepth, TradingState, Order
from typing import List
import math


class Trader:

    EM_FAIR = 10000
    EM_POSITION_LIMIT = 80
    EM_EDGE = 7
    EM_SKEW = 0.05

    TM_POSITION_LIMIT = 80
    TM_BASE_EDGE = 3
    TM_TIGHT_EDGE = 5
    TM_TIGHT_SPREAD_THRESHOLD = 10
    TM_SKEW = 0.05

    def bid(self):
        return 15

    def run(self, state: TradingState):
        result = {}

        if "EMERALDS" in state.order_depths:
            orders: List[Order] = []
            order_depth: OrderDepth = state.order_depths["EMERALDS"]
            pos = state.position.get("EMERALDS", 0)

            # Flatten inventory at fair value when possible.
            if pos > 0 and self.EM_FAIR in order_depth.buy_orders:
                available = order_depth.buy_orders[self.EM_FAIR]
                qty = min(available, self.EM_POSITION_LIMIT + pos, pos)
                if qty > 0:
                    orders.append(Order("EMERALDS", self.EM_FAIR, -qty))
                    pos -= qty
            elif pos < 0 and self.EM_FAIR in order_depth.sell_orders:
                available = -order_depth.sell_orders[self.EM_FAIR]
                qty = min(available, self.EM_POSITION_LIMIT - pos, -pos)
                if qty > 0:
                    orders.append(Order("EMERALDS", self.EM_FAIR, qty))
                    pos += qty

            for price in sorted(order_depth.sell_orders.keys()):
                max_buy = self.EM_POSITION_LIMIT - pos
                if max_buy <= 0:
                    break
                if price < self.EM_FAIR:
                    available = -order_depth.sell_orders[price]
                    qty = min(available, max_buy)
                    if qty > 0:
                        orders.append(Order("EMERALDS", price, qty))
                        pos += qty

            for price in sorted(order_depth.buy_orders.keys(), reverse=True):
                max_sell = self.EM_POSITION_LIMIT + pos
                if max_sell <= 0:
                    break
                if price > self.EM_FAIR:
                    available = order_depth.buy_orders[price]
                    qty = min(available, max_sell)
                    if qty > 0:
                        orders.append(Order("EMERALDS", price, -qty))
                        pos -= qty

            skew = round(pos * self.EM_SKEW)
            bid_price = self.EM_FAIR - self.EM_EDGE - skew
            ask_price = self.EM_FAIR + self.EM_EDGE - skew

            if order_depth.sell_orders:
                best_ask = min(order_depth.sell_orders.keys())
                bid_price = min(bid_price, best_ask - 1)
            if order_depth.buy_orders:
                best_bid = max(order_depth.buy_orders.keys())
                ask_price = max(ask_price, best_bid + 1)
            if bid_price >= ask_price:
                bid_price = ask_price - 1

            max_buy = self.EM_POSITION_LIMIT - pos
            max_sell = self.EM_POSITION_LIMIT + pos
            if max_buy > 0:
                orders.append(Order("EMERALDS", bid_price, max_buy))
            if max_sell > 0:
                orders.append(Order("EMERALDS", ask_price, -max_sell))

            result["EMERALDS"] = orders

        if "TOMATOES" in state.order_depths:
            orders: List[Order] = []
            order_depth: OrderDepth = state.order_depths["TOMATOES"]
            pos = state.position.get("TOMATOES", 0)

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            bid_vol = order_depth.buy_orders[best_bid]
            ask_vol = -order_depth.sell_orders[best_ask]

            denom = bid_vol + ask_vol
            if denom > 0:
                fair_value = (best_bid * ask_vol + best_ask * bid_vol) / denom
            else:
                fair_value = (best_bid + best_ask) / 2

            for price in sorted(order_depth.sell_orders.keys()):
                max_buy = self.TM_POSITION_LIMIT - pos
                if max_buy <= 0:
                    break
                if price < fair_value:
                    available = -order_depth.sell_orders[price]
                    qty = min(available, max_buy)
                    if qty > 0:
                        orders.append(Order("TOMATOES", price, qty))
                        pos += qty

            for price in sorted(order_depth.buy_orders.keys(), reverse=True):
                max_sell = self.TM_POSITION_LIMIT + pos
                if max_sell <= 0:
                    break
                if price > fair_value:
                    available = order_depth.buy_orders[price]
                    qty = min(available, max_sell)
                    if qty > 0:
                        orders.append(Order("TOMATOES", price, -qty))
                        pos -= qty

            market_spread = best_ask - best_bid
            if market_spread < self.TM_TIGHT_SPREAD_THRESHOLD:
                edge = self.TM_TIGHT_EDGE
                size_mult = 0.5
            else:
                edge = self.TM_BASE_EDGE
                size_mult = 1.0

            skew = round(pos * self.TM_SKEW)
            bid_price = math.floor(fair_value) - edge - skew
            ask_price = math.ceil(fair_value) + edge - skew

            bid_price = min(bid_price, best_ask - 1)
            ask_price = max(ask_price, best_bid + 1)
            if bid_price >= ask_price:
                bid_price = ask_price - 1

            max_buy = self.TM_POSITION_LIMIT - pos
            max_sell = self.TM_POSITION_LIMIT + pos
            passive_buy_qty = int(max_buy * size_mult)
            passive_sell_qty = int(max_sell * size_mult)

            if passive_buy_qty > 0:
                orders.append(Order("TOMATOES", bid_price, passive_buy_qty))
            if passive_sell_qty > 0:
                orders.append(Order("TOMATOES", ask_price, -passive_sell_qty))

            result["TOMATOES"] = orders

        print(
            f"POS {state.timestamp} "
            + " ".join(f"{p}:{state.position.get(p, 0)}" for p in state.order_depths)
        )

        traderData = ""
        conversions = 0
        return result, conversions, traderData
