from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import jsonpickle


class Trader:
    LIMIT = 200
    SYMBOL = "HYDROGEL_PACK"

    MM_BASE_SIZE = 12

    Z_FIXED_MEAN = 9990.0
    Z_FIXED_STD = 25.0
    Z_ENTRY = 1.0
    Z_QTY = 35
    Z_INV_FADE_POW = 2.0
    Z_MAX_INV_FRAC = 0.85

    TREND_WINDOW = 50
    TREND_BLOCK_TICKS = 12
    HISTORY_KEEP = 60

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {p: [] for p in state.order_depths}
        td = self._load_state(state.traderData)

        od = state.order_depths.get(self.SYMBOL)
        if od and od.buy_orders and od.sell_orders:
            pos = int(state.position.get(self.SYMBOL, 0))
            best_bid = max(od.buy_orders)
            best_ask = min(od.sell_orders)
            mid = (best_bid + best_ask) / 2.0

            mids = td["mids"]
            mids.append(mid)
            if len(mids) > self.HISTORY_KEEP:
                del mids[:-self.HISTORY_KEEP]

            take_orders, taken = self._taker(od, pos, mids)
            orders = list(take_orders)
            orders.extend(self._mm_quote(od, pos + taken))
            result[self.SYMBOL] = orders

        return result, 0, jsonpickle.encode(td)

    def _load_state(self, raw: str):
        if not raw:
            return {"mids": []}
        try:
            d = jsonpickle.decode(raw)
            if isinstance(d, dict) and "mids" in d:
                return d
        except Exception:
            pass
        return {"mids": []}

    def _taker(self, od: OrderDepth, pos: int, mids: List[float]):
        if not mids:
            return [], 0
        z = (mids[-1] - self.Z_FIXED_MEAN) / self.Z_FIXED_STD
        if abs(z) < self.Z_ENTRY:
            return [], 0

        if len(mids) >= self.TREND_WINDOW:
            move = mids[-1] - mids[-self.TREND_WINDOW]
            if z > 0 and move > self.TREND_BLOCK_TICKS:
                return [], 0
            if z < 0 and move < -self.TREND_BLOCK_TICKS:
                return [], 0

        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        cap = int(self.LIMIT * self.Z_MAX_INV_FRAC)
        inv_factor = max(0.0, 1.0 - abs(pos) / self.LIMIT) ** self.Z_INV_FADE_POW
        orders, taken = [], 0

        if z > self.Z_ENTRY:
            if pos <= -cap:
                return [], 0
            qty = min(int(self.Z_QTY * inv_factor), cap + pos, od.buy_orders[best_bid])
            if qty > 0:
                orders.append(Order(self.SYMBOL, best_bid, -qty))
                taken = -qty
        else:
            if pos >= cap:
                return [], 0
            qty = min(int(self.Z_QTY * inv_factor), cap - pos, -od.sell_orders[best_ask])
            if qty > 0:
                orders.append(Order(self.SYMBOL, best_ask, qty))
                taken = qty
        return orders, taken

    def _mm_quote(self, od: OrderDepth, pos: int) -> List[Order]:
        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        if best_bid >= best_ask:
            return []

        base = self.MM_BASE_SIZE
        buy_size  = min(base, max(0, self.LIMIT - pos))
        sell_size = min(base, max(0, self.LIMIT + pos))

        if best_ask - best_bid > 1:
            bid_price = best_bid + 1
            ask_price = best_ask - 1
        else:
            bid_price = best_bid
            ask_price = best_ask
        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        orders: List[Order] = []
        if buy_size > 0:
            orders.append(Order(self.SYMBOL, bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order(self.SYMBOL, ask_price, -sell_size))
        return orders