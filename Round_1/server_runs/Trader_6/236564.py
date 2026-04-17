from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState
from typing import Any, List, Optional
import json


POSITION_LIMIT = 80

# ── PEPPER Strategy: Pure Mean-Reversion MM ──────────────────────────────────
# Strategy: Frankfurt's P3 approach (proven, no signal overlay)
# - Wall Mid as fair value (stable anchor)
# - Explicit position targets (get to +15 avg)
# - Opportunistic taking (when spread > 15)
# - Queue improve (when at target)
# - No signal overlay (qty=8 bot unconfirmed)

PEP_SLOPE           = 0.001   # drift rate: +0.001 per tick (confirmed)
PEP_TARGET_POSITION = 75      # buy-and-hold core target (leave room to MM)
PEP_TARGET_WIDTH    = 5       # hold in [70, 80] to keep small MM buffer
PEP_BID_NORMAL      = 1       # units below fair for normal MM [grid search optimized]
PEP_ASK_NORMAL      = 5       # units above fair for normal MM [grid search optimized]
PEP_BID_AGGRESSIVE  = 0       # units below fair when below target (buy more)
PEP_ASK_AGGRESSIVE  = 6       # units above fair when below target (sell reluctantly)
PEP_BID_DEFENSIVE   = 3       # units below fair when above target (sell more) [grid search derived]
PEP_ASK_DEFENSIVE   = 4       # units above fair when above target (buy reluctantly) [grid search derived]
PEP_TAKING_THRESHOLD = 15     # spread > this = take at mid
PEP_LIMIT           = 80      # round 1 position limit
PEP_NEVER_SELL      = True    # hardcoded carry experiment
PEP_SAFETY_NEG_STREAK = 25    # disable never-sell after sustained down-move


# ── Logger ────────────────────────────────────────────────────────────────────

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


# ── Trader ────────────────────────────────────────────────────────────────────

class Trader:

    def run(self, state: TradingState):
        result = {}

        # Load shared persistent state
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

    def trade_pepper(self, state: TradingState, td: dict) -> tuple:
        """
        INTARIAN_PEPPER_ROOT: Pure mean-reversion market-making.

        Architecture (Frankfurt P3 approach):
          1. Compute wall-mid as fair value (stable anchor)
          2. Determine position mode (below/at/above target)
          3. Quote asymmetrically (to reach target position)
          4. Take opportunities when spread > threshold
          5. Queue improve when at target
        """
        orders: List[Order] = []
        od = state.order_depths["INTARIAN_PEPPER_ROOT"]
        pos = state.position.get("INTARIAN_PEPPER_ROOT", 0)
        t = state.timestamp

        if not od.buy_orders or not od.sell_orders:
            return orders, td

        # ── Step 1: Compute fair value (Wall Mid) ──────────────────────────────
        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        bid_wall = min(od.buy_orders)
        ask_wall = max(od.sell_orders)

        mid = (best_bid + best_ask) / 2
        wall_mid = (bid_wall + ask_wall) / 2
        fair = wall_mid

        last_mid = td.get("pep_last_mid")
        neg_streak = int(td.get("pep_neg_streak", 0))
        if isinstance(last_mid, (int, float)) and mid < last_mid:
            neg_streak += 1
        else:
            neg_streak = 0
        td["pep_last_mid"] = mid
        td["pep_neg_streak"] = neg_streak
        safety_off = neg_streak >= PEP_SAFETY_NEG_STREAK

        if PEP_NEVER_SELL and not safety_off:
            buy_cap = PEP_LIMIT - pos
            if buy_cap <= 0:
                td["pep_mode"] = "hold_never_sell"
                td["pep_fair"] = fair
                td["pep_pos"] = pos
                return orders, td

            market_spread = ask_wall - bid_wall
            if market_spread > PEP_TAKING_THRESHOLD and best_ask <= fair + 2:
                take_qty = min(buy_cap, abs(od.sell_orders[best_ask]), 6)
                if take_qty > 0:
                    orders.append(Order("INTARIAN_PEPPER_ROOT", int(best_ask), take_qty))
                    buy_cap -= take_qty

            if buy_cap > 0:
                bid_price = round(fair - PEP_BID_AGGRESSIVE)
                orders.append(Order("INTARIAN_PEPPER_ROOT", bid_price, buy_cap))

            td["pep_mode"] = "accumulate_never_sell"
            td["pep_fair"] = fair
            td["pep_pos"] = pos
            return [o for o in orders if o.quantity != 0], td

        # ── Step 2: Position mode logic ────────────────────────────────────────
        # Determine if we're below target, at target, or above target
        target_low = PEP_TARGET_POSITION - PEP_TARGET_WIDTH
        target_high = PEP_TARGET_POSITION + PEP_TARGET_WIDTH

        if pos < target_low:
            mode = "accumulate"    # position too low, buy aggressively
        elif pos > target_high:
            mode = "unwind"        # position too high, sell aggressively
        else:
            mode = "target"        # at target, normal MM

        # ── Step 3: Opportunistic taking ───────────────────────────────────────
        # If spread is very wide, take at mid to normalize it
        market_spread = ask_wall - bid_wall
        take_qty = 0

        if market_spread > PEP_TAKING_THRESHOLD:
            # Market is dislocated → take the best side
            if mode != "unwind":  # don't buy more if we're already long
                take_qty = min(abs(int(best_ask) - int(fair)) // 2, 3)  # small clips
                if take_qty > 0:
                    orders.append(Order("INTARIAN_PEPPER_ROOT", int(best_ask), take_qty))
                    logger.print(f"[PEP] TAKING ask @ {best_ask} qty={take_qty}")

        # ── Step 4: Compute quotes based on position mode ────────────────────────
        buy_cap = PEP_LIMIT - pos
        sell_cap = PEP_LIMIT + pos

        if mode == "accumulate":
            bid_price = round(fair - PEP_BID_AGGRESSIVE)
            ask_price = round(fair + PEP_ASK_AGGRESSIVE)
            buy_qty = buy_cap
            sell_qty = sell_cap
        elif mode == "unwind":
            bid_price = round(fair - PEP_BID_DEFENSIVE)
            ask_price = round(fair + PEP_ASK_DEFENSIVE)
            buy_qty = buy_cap
            sell_qty = sell_cap
        else:
            # At target: normal MM with queue improve
            # Bid: queue improve if best_bid < fair, else normal
            if best_bid < fair - 1:
                bid_price = round(best_bid + 1)
            else:
                bid_price = round(fair - PEP_BID_NORMAL)

            # Ask: queue improve if best_ask > fair + 1, else normal
            if best_ask > fair + 1:
                ask_price = round(best_ask - 1)
            else:
                ask_price = round(fair + PEP_ASK_NORMAL)

            buy_qty = buy_cap
            sell_qty = sell_cap

        # Safety: prevent locked quotes
        if bid_price >= ask_price:
            bid_price = round(fair) - 1
            ask_price = round(fair) + 1

        # ── Step 5: Emit orders ────────────────────────────────────────────────
        if buy_qty > 0 and buy_cap > 0:
            orders.append(Order("INTARIAN_PEPPER_ROOT", bid_price, min(buy_qty, buy_cap)))
        if sell_qty > 0 and sell_cap > 0:
            orders.append(Order("INTARIAN_PEPPER_ROOT", ask_price, -min(sell_qty, sell_cap)))

        # ── Step 6: Serialize state ────────────────────────────────────────────
        td["pep_mode"] = mode
        td["pep_fair"] = fair
        td["pep_pos"] = pos
        td["pep_safety_off"] = safety_off

        return [o for o in orders if o.quantity != 0], td