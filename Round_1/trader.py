from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState
from typing import Any, List
import json


POSITION_LIMIT = 80

PEP_TARGET_POSITION  = 75
PEP_TARGET_WIDTH     = 5
PEP_BID_NORMAL       = 1
PEP_ASK_NORMAL       = 5
PEP_BID_AGGRESSIVE   = 0
PEP_ASK_AGGRESSIVE   = 6
PEP_BID_DEFENSIVE    = 3
PEP_ASK_DEFENSIVE    = 4
PEP_TAKING_THRESHOLD = 15
PEP_LIMIT            = 80
PEP_NEVER_SELL       = True
PEP_SAFETY_NEG_STREAK = 25
PEP_ENTRY_TAKE_EDGE  = 8
PEP_ENTRY_TAKE_CLIP  = 8


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(self.to_json([
            self.compress_state(state, ""),
            self.compress_orders(orders),
            conversions, "", "",
        ]))
        max_item_length = (self.max_log_length - base_length) // 3

        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
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
        return [
            [t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
            for arr in trades.values() for t in arr
        ]

    def compress_observations(self, observations: Observation) -> list[Any]:
        conv = {
            prod: [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff, o.importTariff]
            for prod, o in observations.conversionObservations.items()
        }
        return [observations.plainValueObservations, conv]

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


class Trader:

    def run(self, state: TradingState):
        result = {}

        td: dict = {}
        if state.traderData:
            try:
                td = json.loads(state.traderData)
            except Exception:
                td = {}

        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = self.trade_aco(state)

        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            result["INTARIAN_PEPPER_ROOT"], td = self.trade_pepper(state, td)

        trader_data = json.dumps(td)
        conversions = 0
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data

    def trade_aco(self, state: TradingState) -> List[Order]:
        orders: List[Order] = []
        od: OrderDepth = state.order_depths["ASH_COATED_OSMIUM"]
        pos = state.position.get("ASH_COATED_OSMIUM", 0)

        if not od.buy_orders or not od.sell_orders:
            return orders

        # Sorted book: bids descending, asks ascending, all volumes positive
        bids = {p: abs(v) for p, v in sorted(od.buy_orders.items(), reverse=True)}
        asks = {p: abs(v) for p, v in sorted(od.sell_orders.items())}

        bid_wall = min(bids)
        ask_wall = max(asks)
        wall_mid = (bid_wall + ask_wall) / 2

        buy_cap  = POSITION_LIMIT - pos
        sell_cap = POSITION_LIMIT + pos

        def buy(price, volume):
            nonlocal buy_cap
            vol = min(abs(int(volume)), buy_cap)
            if vol > 0:
                orders.append(Order("ASH_COATED_OSMIUM", int(price), vol))
                buy_cap -= vol

        def sell(price, volume):
            nonlocal sell_cap
            vol = min(abs(int(volume)), sell_cap)
            if vol > 0:
                orders.append(Order("ASH_COATED_OSMIUM", int(price), -vol))
                sell_cap -= vol

        for ask_p, ask_v in asks.items():
            if ask_p <= wall_mid - 1:
                buy(ask_p, ask_v)
            elif ask_p <= wall_mid and pos < 0:
                buy(ask_p, min(ask_v, abs(pos)))

        for bid_p, bid_v in bids.items():
            if bid_p >= wall_mid + 1:
                sell(bid_p, bid_v)
            elif bid_p >= wall_mid and pos > 0:
                sell(bid_p, min(bid_v, pos))

        # Queue-improve: start at wall extremes, then step inside best resting order
        bid_price = bid_wall + 1
        for bp, bv in bids.items():
            if bp >= wall_mid:
                continue
            bid_price = max(bid_price, (bp + 1) if bv > 1 else bp)
            break

        ask_price = ask_wall - 1
        for ap, av in asks.items():
            if ap <= wall_mid:
                continue
            ask_price = min(ask_price, (ap - 1) if av > 1 else ap)
            break

        if bid_price >= ask_price:
            bid_price = int(wall_mid) - 1
            ask_price = int(wall_mid) + 1

        buy(bid_price, buy_cap)
        sell(ask_price, sell_cap)

        return [o for o in orders if o.quantity != 0]

    def trade_pepper(self, state: TradingState, td: dict) -> tuple:
        orders: List[Order] = []
        od = state.order_depths["INTARIAN_PEPPER_ROOT"]
        pos = state.position.get("INTARIAN_PEPPER_ROOT", 0)

        if not od.buy_orders or not od.sell_orders:
            return orders, td

        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        bid_wall = min(od.buy_orders)
        ask_wall = max(od.sell_orders)
        fair = (bid_wall + ask_wall) / 2
        mid  = (best_bid + best_ask) / 2

        last_mid   = td.get("pep_last_mid")
        neg_streak = int(td.get("pep_neg_streak", 0))
        neg_streak = neg_streak + 1 if isinstance(last_mid, (int, float)) and mid < last_mid else 0
        td["pep_last_mid"]   = mid
        td["pep_neg_streak"] = neg_streak
        safety_off = neg_streak >= PEP_SAFETY_NEG_STREAK

        if PEP_NEVER_SELL and not safety_off:
            buy_cap = PEP_LIMIT - pos
            if buy_cap <= 0:
                td["pep_fair"] = fair
                td["pep_pos"]  = pos
                return orders, td

            if best_ask <= fair + PEP_ENTRY_TAKE_EDGE:
                take_qty = min(buy_cap, abs(od.sell_orders[best_ask]), PEP_ENTRY_TAKE_CLIP)
                if take_qty > 0:
                    orders.append(Order("INTARIAN_PEPPER_ROOT", best_ask, take_qty))
                    buy_cap -= take_qty

            if buy_cap > 0:
                orders.append(Order("INTARIAN_PEPPER_ROOT", round(fair - PEP_BID_AGGRESSIVE), buy_cap))

            td["pep_fair"] = fair
            td["pep_pos"]  = pos
            return [o for o in orders if o.quantity != 0], td

        # Safety fallback: standard asymmetric MM toward target position
        target_low  = PEP_TARGET_POSITION - PEP_TARGET_WIDTH
        target_high = PEP_TARGET_POSITION + PEP_TARGET_WIDTH

        if pos < target_low:
            mode = "accumulate"
        elif pos > target_high:
            mode = "unwind"
        else:
            mode = "target"

        market_spread = ask_wall - bid_wall
        if market_spread > PEP_TAKING_THRESHOLD and mode != "unwind":
            take_qty = min(abs(best_ask - int(fair)) // 2, 3)
            if take_qty > 0:
                orders.append(Order("INTARIAN_PEPPER_ROOT", best_ask, take_qty))

        buy_cap  = PEP_LIMIT - pos
        sell_cap = PEP_LIMIT + pos

        if mode == "accumulate":
            bid_price = round(fair - PEP_BID_AGGRESSIVE)
            ask_price = round(fair + PEP_ASK_AGGRESSIVE)
        elif mode == "unwind":
            bid_price = round(fair - PEP_BID_DEFENSIVE)
            ask_price = round(fair + PEP_ASK_DEFENSIVE)
        else:
            bid_price = round(best_bid + 1) if best_bid < fair - 1 else round(fair - PEP_BID_NORMAL)
            ask_price = round(best_ask - 1) if best_ask > fair + 1 else round(fair + PEP_ASK_NORMAL)

        if bid_price >= ask_price:
            bid_price = round(fair) - 1
            ask_price = round(fair) + 1

        if buy_cap > 0:
            orders.append(Order("INTARIAN_PEPPER_ROOT", bid_price, buy_cap))
        if sell_cap > 0:
            orders.append(Order("INTARIAN_PEPPER_ROOT", ask_price, -sell_cap))

        td["pep_mode"]      = mode
        td["pep_fair"]      = fair
        td["pep_pos"]       = pos
        td["pep_safety_off"] = safety_off

        return [o for o in orders if o.quantity != 0], td