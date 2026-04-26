import json
import math
from typing import Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


# --- PROSPERITY LOGGER BOILERPLATE ---
class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                    "",
                ]
            )
        )

        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])
        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]
        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )
        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]
        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])
        return compressed

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

            encoded_candidate = json.dumps(candidate)

            if len(encoded_candidate) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return out


logger = Logger()
# --- END LOGGER BOAKERPLATE ---


class Trader:
    ENABLE_HYDROGEL = True
    HYDRO_PRODUCT = "HYDROGEL_PACK"
    HYDRO_LIMIT = 200

    HYDRO_ENABLE_TAKE = True
    HYDRO_ENABLE_PASSIVE = True

    HYDRO_ANCHOR = 10000.0

    ENABLE_HYDRO_GAP_ALPHA = True
    HYDRO_GAP_THRESHOLD = 1
    HYDRO_GAP_ALPHA_STRENGTH = 2.0

    ENABLE_HYDRO_GAP_SIZE_SKEW = False
    HYDRO_GAP_FAVORED_SIZE_SCALE = 1.50
    HYDRO_GAP_TOXIC_SIZE_SCALE = 0.40

    ENABLE_HYDRO_DYNAMIC_ANCHOR_WEIGHT = False
    HYDRO_ANCHOR_WEIGHT = 0.10

    HYDRO_USE_TREND_BLOCK = True
    HYDRO_TREND_WINDOW = 50
    HYDRO_CRASH_BLOCK_LONGS = 25.0
    HYDRO_RIP_BLOCK_SHORTS = 25.0

    HYDRO_DISABLE_BID_ABOVE_POS = 180
    HYDRO_DISABLE_ASK_BELOW_POS = -180

    def active_products(self) -> list[str]:
        products = []
        if self.ENABLE_HYDROGEL:
            products.append(self.HYDRO_PRODUCT)
        return products

    def position(self, state: TradingState, product: str) -> int:
        return state.position.get(product, 0)

    def best_bid_ask(self, depth: OrderDepth):
        best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
        best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
        return best_bid, best_ask

    def mid(self, depth: OrderDepth):
        bid, ask = self.best_bid_ask(depth)
        if bid is None or ask is None:
            return None
        return (bid + ask) / 2.0

    def load_data(self, trader_data: str) -> dict:
        if not trader_data:
            return {}
        try:
            return json.loads(trader_data)
        except Exception:
            return {}

    def get_hydrogel_orders(self, product: str, order_depth: OrderDepth, current_pos: int, state_data: dict) -> list[Order]:
        orders: list[Order] = []
        effective_limit = self.HYDRO_LIMIT

        sorted_asks = sorted(order_depth.sell_orders.items())
        sorted_bids = sorted(order_depth.buy_orders.items(), reverse=True)

        last_fair = state_data.get("hydro_last_fair", state_data.get("hydro_kalman_x", self.HYDRO_ANCHOR))

        if not sorted_asks and not sorted_bids:
            return orders

        if not sorted_asks:
            best_bid = sorted_bids[0][0]
            buy_price = best_bid + 1
            edge = last_fair - buy_price
            if self.HYDRO_ENABLE_PASSIVE and edge >= 2 and current_pos < self.HYDRO_DISABLE_BID_ABOVE_POS:
                buy_qty = min(8, effective_limit - current_pos)
                if buy_qty > 0:
                    orders.append(Order(product, buy_price, buy_qty))
            if self.HYDRO_ENABLE_TAKE and current_pos > 0:
                unwind_qty = min(8, current_pos)
                if unwind_qty > 0:
                    orders.append(Order(product, int(math.ceil(last_fair + 1)), -unwind_qty))
            return orders

        if not sorted_bids:
            best_ask = sorted_asks[0][0]
            sell_price = best_ask - 1
            edge = sell_price - last_fair
            if self.HYDRO_ENABLE_PASSIVE and edge >= 2 and current_pos > self.HYDRO_DISABLE_ASK_BELOW_POS:
                sell_qty = min(8, effective_limit + current_pos)
                if sell_qty > 0:
                    orders.append(Order(product, sell_price, -sell_qty))
            if self.HYDRO_ENABLE_TAKE and current_pos < 0:
                unwind_qty = min(8, -current_pos)
                if unwind_qty > 0:
                    orders.append(Order(product, int(math.floor(last_fair - 1)), unwind_qty))
            return orders

        def compute_vwap(levels, depth=3):
            cum_vol = 0
            cum_px_vol = 0
            for i, (px, vol) in enumerate(levels):
                if i >= depth:
                    break
                vol_abs = abs(vol)
                cum_vol += vol_abs
                cum_px_vol += px * vol_abs
            return cum_px_vol / cum_vol if cum_vol > 0 else None

        bid_vwap = compute_vwap(sorted_bids)
        ask_vwap = compute_vwap(sorted_asks)
        best_bid, best_bid_qty = sorted_bids[0]
        best_ask, best_ask_qty = sorted_asks[0]
        mid_price = (best_bid + best_ask) / 2.0

        gap_skew = 0
        gap_alpha = 0.0
        if self.ENABLE_HYDRO_GAP_ALPHA and len(sorted_bids) >= 2 and len(sorted_asks) >= 2:
            bid_gap = sorted_bids[0][0] - sorted_bids[1][0]
            ask_gap = sorted_asks[1][0] - sorted_asks[0][0]
            gap_skew = bid_gap - ask_gap
            if gap_skew <= -self.HYDRO_GAP_THRESHOLD:
                gap_alpha = self.HYDRO_GAP_ALPHA_STRENGTH
            elif gap_skew >= self.HYDRO_GAP_THRESHOLD:
                gap_alpha = -self.HYDRO_GAP_ALPHA_STRENGTH

        if bid_vwap and ask_vwap:
            total_bid_vol = sum(abs(q) for _, q in sorted_bids[:3])
            total_ask_vol = sum(abs(q) for _, q in sorted_asks[:3])
            if total_bid_vol + total_ask_vol > 0:
                observation = (bid_vwap * total_ask_vol + ask_vwap * total_bid_vol) / (total_bid_vol + total_ask_vol)
            else:
                observation = mid_price
        else:
            observation = mid_price

        mid_history = state_data.get("hydro_mid_history", [])
        if not isinstance(mid_history, list):
            mid_history = []
        mid_history.append(mid_price)
        max_hist = max(self.HYDRO_TREND_WINDOW + 2, 60)
        if len(mid_history) > max_hist:
            mid_history = mid_history[-max_hist:]
        state_data["hydro_mid_history"] = mid_history

        trend_50 = 0.0
        if len(mid_history) > self.HYDRO_TREND_WINDOW:
            trend_50 = mid_price - float(mid_history[-1 - self.HYDRO_TREND_WINDOW])

        block_new_longs = False
        block_new_shorts = False
        if self.HYDRO_USE_TREND_BLOCK:
            if trend_50 <= -self.HYDRO_CRASH_BLOCK_LONGS:
                block_new_longs = True
            if trend_50 >= self.HYDRO_RIP_BLOCK_SHORTS:
                block_new_shorts = True

        if current_pos >= self.HYDRO_DISABLE_BID_ABOVE_POS:
            block_new_longs = True
        if current_pos <= self.HYDRO_DISABLE_ASK_BELOW_POS:
            block_new_shorts = True

        x_est = state_data.get("hydro_kalman_x", observation)
        P_est = state_data.get("hydro_kalman_P", 1.0)

        Q = 0.008
        R = 0.3

        x_pred = x_est
        P_pred = P_est + Q

        K = P_pred / (P_pred + R)
        x_est = x_pred + K * (observation - x_pred)
        P_est = (1 - K) * P_pred

        state_data["hydro_kalman_x"] = x_est
        state_data["hydro_kalman_P"] = P_est

        kalman_fair = x_est
        uncertainty = math.sqrt(P_est)

        def compute_vwap_orig(levels, target_volume=50):
            cum_vol = 0
            cum_px_vol = 0
            for px, vol in levels:
                vol_abs = abs(vol)
                take = min(vol_abs, target_volume - cum_vol)
                if take <= 0:
                    break
                cum_vol += take
                cum_px_vol += px * take
            return cum_px_vol / cum_vol if cum_vol > 0 else None

        bid_vwap_orig = compute_vwap_orig(sorted_bids)
        ask_vwap_orig = compute_vwap_orig(sorted_asks)

        if bid_vwap_orig and ask_vwap_orig:
            depth_mid = (bid_vwap_orig + ask_vwap_orig) / 2.0
        else:
            depth_mid = mid_price

        alpha_ema = 0.12
        ema = state_data.get("hydro_ema")
        if ema is None:
            ema = depth_mid
        else:
            ema = alpha_ema * depth_mid + (1 - alpha_ema) * ema
        state_data["hydro_ema"] = ema

        fair_value_raw = 0.6 * kalman_fair + 0.4 * ema

        total_bid_vol = abs(best_bid_qty)
        total_ask_vol = abs(best_ask_qty)
        imbalance = 0.0
        if total_bid_vol + total_ask_vol > 0:
            imbalance = (total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol)

        fair_value_raw += imbalance * 0.8 + gap_alpha

        if self.ENABLE_HYDRO_DYNAMIC_ANCHOR_WEIGHT:
            anchor_weight = max(0.0, min(1.0, self.HYDRO_ANCHOR_WEIGHT))
        else:
            anchor_weight = 0.25
        fair_value_raw = (1.0 - anchor_weight) * fair_value_raw + anchor_weight * self.HYDRO_ANCHOR

        pos_ratio = current_pos / float(effective_limit)
        if pos_ratio < 0.6:
            skew = pos_ratio * 2
        else:
            skew = pos_ratio * 5
        fair_value = fair_value_raw - skew

        state_data["hydro_last_fair"] = fair_value

        def max_allowed_buy(desired_qty: int, pos: int) -> int:
            if desired_qty <= 0:
                return 0
            cap = effective_limit - pos
            if block_new_longs:
                if pos < 0:
                    cap = min(cap, -pos)
                else:
                    cap = 0
            return max(0, min(desired_qty, cap))

        def max_allowed_sell(desired_qty: int, pos: int) -> int:
            if desired_qty <= 0:
                return 0
            cap = effective_limit + pos
            if block_new_shorts:
                if pos > 0:
                    cap = min(cap, pos)
                else:
                    cap = 0
            return max(0, min(desired_qty, cap))

        if self.HYDRO_ENABLE_TAKE:
            take_threshold = 0.5 + uncertainty * 1.0
            buy_take_threshold = max(0.1, take_threshold - imbalance * 1.0)
            sell_take_threshold = max(0.1, take_threshold + imbalance * 1.0)

            for price, qty in sorted_asks:
                if price < fair_value - buy_take_threshold:
                    buy_amt = max_allowed_buy(-qty, current_pos)
                    if buy_amt > 0:
                        orders.append(Order(product, price, buy_amt))
                        current_pos += buy_amt

            for price, qty in sorted_bids:
                if price > fair_value + sell_take_threshold:
                    sell_amt = max_allowed_sell(qty, current_pos)
                    if sell_amt > 0:
                        orders.append(Order(product, price, -sell_amt))
                        current_pos -= sell_amt

        if self.HYDRO_ENABLE_PASSIVE:
            base_half_spread = 0.5 + uncertainty * 1.0
            ideal_bid = int(math.floor(fair_value - base_half_spread))
            ideal_ask = int(math.ceil(fair_value + base_half_spread))

            spread = best_ask - best_bid
            if spread > 1:
                my_bid_price = min(ideal_bid, best_bid + 1)
                my_ask_price = max(ideal_ask, best_ask - 1)
            else:
                my_bid_price = ideal_bid
                my_ask_price = ideal_ask

            my_bid_price = min(my_bid_price, best_ask - 1)
            my_ask_price = max(my_ask_price, best_bid + 1)

            uncertainty_penalty = max(0.3, 1.0 - uncertainty * 0.5)
            inv_penalty = max(0.3, 1.0 - abs(current_pos / float(effective_limit)))
            qty = int(effective_limit * inv_penalty * uncertainty_penalty)
            qty = max(3, qty)

            bid_size_scale = max(0.3, 1.0 + imbalance * 2.0)
            ask_size_scale = max(0.3, 1.0 - imbalance * 2.0)

            if self.ENABLE_HYDRO_GAP_SIZE_SKEW and gap_alpha != 0.0:
                favored = max(0.0, self.HYDRO_GAP_FAVORED_SIZE_SCALE)
                toxic = max(0.0, self.HYDRO_GAP_TOXIC_SIZE_SCALE)
                if gap_alpha > 0.0:
                    bid_size_scale *= favored
                    ask_size_scale *= toxic
                else:
                    ask_size_scale *= favored
                    bid_size_scale *= toxic

            bid_qty = max(1, int(qty * bid_size_scale))
            ask_qty = max(1, int(qty * ask_size_scale))

            safe_bid_qty = max_allowed_buy(bid_qty, current_pos)
            if safe_bid_qty > 0:
                orders.append(Order(product, my_bid_price, safe_bid_qty))

            safe_ask_qty = max_allowed_sell(ask_qty, current_pos)
            if safe_ask_qty > 0:
                orders.append(Order(product, my_ask_price, -safe_ask_qty))

        return orders

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        result: dict[Symbol, list[Order]] = {}
        conversions = 0
        data = self.load_data(state.traderData)

        if self.ENABLE_HYDROGEL and self.HYDRO_PRODUCT in state.order_depths:
            hydro_orders = self.get_hydrogel_orders(
                self.HYDRO_PRODUCT,
                state.order_depths[self.HYDRO_PRODUCT],
                self.position(state, self.HYDRO_PRODUCT),
                data,
            )
            if hydro_orders:
                result[self.HYDRO_PRODUCT] = hydro_orders

        trader_data = json.dumps(data, separators=(",", ":"))
        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data