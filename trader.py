from datamodel import OrderDepth, TradingState, Order
from typing import List


POSITION_LIMIT = 50


class Trader:

    def run(self, state: TradingState):
        result = {}

        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = self.trade_aco(state)

        return result, 0, ""

    def trade_aco(self, state: TradingState) -> List[Order]:
        """
        Frankfurt StaticTrader logic for ASH_COATED_OSMIUM.

        Fair value = wall_mid = midpoint of (worst bid, worst ask).
        For a stable mean-reverting ~10000 asset, this reliably anchors near 10000.

        Strategy:
          - TAKING: cross any ask <= wall_mid - 1, or any bid >= wall_mid + 1
                    (also flatten inventory at wall_mid when position is one-sided)
          - MAKING: queue-improve around wall_mid
                    bid just above the best bid that is still below wall_mid
                    ask just below the best ask that is still above wall_mid
        """
        orders: List[Order] = []
        od: OrderDepth = state.order_depths["ASH_COATED_OSMIUM"]
        pos = state.position.get("ASH_COATED_OSMIUM", 0)

        if not od.buy_orders or not od.sell_orders:
            return orders

        # Sorted book: bids descending, asks ascending, all volumes positive
        bids = {p: abs(v) for p, v in sorted(od.buy_orders.items(), reverse=True)}
        asks = {p: abs(v) for p, v in sorted(od.sell_orders.items())}

        bid_wall = min(bids)          # worst (lowest) bid
        ask_wall = max(asks)          # worst (highest) ask
        wall_mid = (bid_wall + ask_wall) / 2

        # Running capacity (decremented as we place orders)
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

        # --- TAKING ---
        for ask_p, ask_v in asks.items():
            if ask_p <= wall_mid - 1:
                buy(ask_p, ask_v)                        # clearly cheap
            elif ask_p <= wall_mid and pos < 0:
                buy(ask_p, min(ask_v, abs(pos)))         # reduce short at mid

        for bid_p, bid_v in bids.items():
            if bid_p >= wall_mid + 1:
                sell(bid_p, bid_v)                       # clearly expensive
            elif bid_p >= wall_mid and pos > 0:
                sell(bid_p, min(bid_v, pos))             # reduce long at mid

        # --- MAKING: queue-improve around wall_mid ---
        # Bid: start at bid_wall + 1, then overbid the best bid below wall_mid
        bid_price = bid_wall + 1
        for bp, bv in bids.items():
            if bp >= wall_mid:
                continue
            bid_price = max(bid_price, (bp + 1) if bv > 1 else bp)
            break

        # Ask: start at ask_wall - 1, then underbid the best ask above wall_mid
        ask_price = ask_wall - 1
        for ap, av in asks.items():
            if ap <= wall_mid:
                continue
            ask_price = min(ask_price, (ap - 1) if av > 1 else ap)
            break

        # Safety: prevent bid >= ask
        if bid_price >= ask_price:
            bid_price  = int(wall_mid) - 1
            ask_price  = int(wall_mid) + 1

        buy(bid_price, buy_cap)
        sell(ask_price, sell_cap)

        return [o for o in orders if o.quantity != 0]
