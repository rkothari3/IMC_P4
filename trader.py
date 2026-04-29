import json
from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, Symbol, TradingState


class Trader:
    PRODUCTS = (
        "SNACKPACK_CHOCOLATE",
        "SNACKPACK_VANILLA",
        "SNACKPACK_PISTACHIO",
        "SNACKPACK_STRAWBERRY",
        "SNACKPACK_RASPBERRY",
    )
    GALAXY = (
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
    )
    OXYGEN = (
        "OXYGEN_SHAKE_MORNING_BREATH",
        "OXYGEN_SHAKE_EVENING_BREATH",
        "OXYGEN_SHAKE_MINT",
        "OXYGEN_SHAKE_CHOCOLATE",
        "OXYGEN_SHAKE_GARLIC",
    )
    UV = (
        "UV_VISOR_AMBER",
        "UV_VISOR_ORANGE",
        "UV_VISOR_MAGENTA",
    )
    PANELS = (
        "PANEL_2X2",
        "PANEL_1X4",
        "PANEL_2X4",
    )
    SLEEP_PODS = (
        "SLEEP_POD_SUEDE",
        "SLEEP_POD_POLYESTER",
        "SLEEP_POD_COTTON",
    )
    TRANSLATORS = (
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_VOID_BLUE",
    )
    MICROCHIPS = (
        "MICROCHIP_CIRCLE",
        "MICROCHIP_OVAL",
        "MICROCHIP_RECTANGLE",
        "MICROCHIP_TRIANGLE",
    )
    LIMIT = 10
    MIN_SPREAD = 8

    # CHOC and VAN show strong same-tick anti-correlation.
    PAIR_A = "SNACKPACK_CHOCOLATE"
    PAIR_B = "SNACKPACK_VANILLA"
    PAIR_BETA = 1.041
    PEBBLES = ("PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL")
    PEBBLES_PARITY = 50000.0
    # External "free alpha" signals transformed into a small fair-value drift bias.
    # Tuple is (h1, h2, h3, h4) directional components; score uses weighted average.
    DRIFT_ALPHA: Dict[Symbol, Tuple[float, float, float, float]] = {
        "GALAXY_SOUNDS_SOLAR_FLAMES": (290.0, 485.5, 537.8333, 277.3333),
        "PEBBLES_XL": (551.5, 302.1667, 1300.0, 2045.3333),
        "PEBBLES_XS": (0.8333, -217.8333, -1030.6667, -1326.1667),
        "SLEEP_POD_COTTON": (265.3333, 277.3333, 463.3333, 471.5),
        "SLEEP_POD_POLYESTER": (-63.1667, 439.1667, 71.5, 655.6667),
        "SLEEP_POD_SUEDE": (190.5, -64.0, 370.0, 603.0),
        "TRANSLATOR_ECLIPSE_CHARCOAL": (41.5, 22.3333, -280.5, -88.1667),
        "TRANSLATOR_VOID_BLUE": (178.1667, 19.8333, 214.1667, 509.1667),
        "UV_VISOR_ORANGE": (164.8333, 314.0, 558.3333, -226.5),
        "UV_VISOR_AMBER": (-410.3333, -487.1667, -629.5, -954.5),
        "PANEL_1X4": (-387.8333, -425.3333, -538.3333, -269.8333),
    }
    DRIFT_SCALE = 0.0038
    DRIFT_CAP = 5.0
    DRIFT_MULT: Dict[Symbol, float] = {
        "PEBBLES_XL": 1.05,
        "PEBBLES_XS": 0.55,
        "PANEL_1X4": 1.0,
        "SLEEP_POD_COTTON": 0.45,
        "SLEEP_POD_POLYESTER": 1.0,
        "GALAXY_SOUNDS_SOLAR_FLAMES": 0.70,
        "TRANSLATOR_ECLIPSE_CHARCOAL": 0.80,
        "TRANSLATOR_VOID_BLUE": 1.0,
        "UV_VISOR_AMBER": 0.45,
    }

    def _load_data(self, trader_data: str) -> Dict:
        if not trader_data:
            return {"pair_mean": None, "pair_var": None, "robot_ema": {}}
        try:
            parsed = json.loads(trader_data)
            if isinstance(parsed, dict):
                if "robot_ema" not in parsed or not isinstance(parsed["robot_ema"], dict):
                    parsed["robot_ema"] = {}
                return parsed
        except Exception:
            pass
        return {"pair_mean": None, "pair_var": None, "robot_ema": {}}

    def _dump_data(self, data: Dict) -> str:
        payload = {
            "pair_mean": data.get("pair_mean"),
            "pair_var": data.get("pair_var"),
            "robot_ema": data.get("robot_ema", {}),
        }
        return json.dumps(payload, separators=(",", ":"))

    @staticmethod
    def _best_bid_ask(depth: OrderDepth) -> Tuple[int, int, int, int]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        bid_vol = abs(int(depth.buy_orders.get(best_bid, 0)))
        ask_vol = abs(int(depth.sell_orders.get(best_ask, 0)))
        return best_bid, best_ask, bid_vol, ask_vol

    def _drift_bias(self, product: Symbol, spread: int) -> float:
        comp = self.DRIFT_ALPHA.get(product)
        if comp is None:
            return 0.0
        # Spread gating: suppress drift on low-information books.
        if spread < 10:
            return 0.0
        h1, h2, h3, h4 = comp
        score = 0.4 * h1 + 0.3 * h2 + 0.2 * h3 + 0.1 * h4
        mult = self.DRIFT_MULT.get(product, 1.0)
        if spread < 14:
            mult *= 0.6
        bias = self.DRIFT_SCALE * score * mult
        if bias > self.DRIFT_CAP:
            return self.DRIFT_CAP
        if bias < -self.DRIFT_CAP:
            return -self.DRIFT_CAP
        return bias

    def _quote_product(
        self, product: Symbol, depth: OrderDepth, position: int, fair: float
    ) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask, _, _ = self._best_bid_ask(depth)
        spread = best_ask - best_bid
        if spread < self.MIN_SPREAD:
            return orders

        half_width = max(2.0, 0.45 * spread)
        bid_px = int(round(fair - half_width))
        ask_px = int(round(fair + half_width))

        buy_room = self.LIMIT - position
        sell_room = self.LIMIT + position

        inventory_scale = max(0.3, 1.0 - abs(position) / self.LIMIT)
        quote_size = max(1, int(round(2 * inventory_scale)))

        inside_bid = best_bid + 1
        inside_ask = best_ask - 1
        if inside_bid < inside_ask:
            bid_px = max(bid_px, inside_bid)
            ask_px = min(ask_px, inside_ask)
        bid_px = min(bid_px, best_ask - 1)
        ask_px = max(ask_px, best_bid + 1)
        if ask_px <= bid_px:
            ask_px = bid_px + 1

        if buy_room > 0:
            orders.append(Order(product, bid_px, min(quote_size, buy_room)))
        if sell_room > 0:
            orders.append(Order(product, ask_px, -min(quote_size, sell_room)))

        return orders

    def _quote_pebbles(
        self,
        product: Symbol,
        depth: OrderDepth,
        position: int,
        fair: float,
        timestamp: int,
    ) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask, bid_vol, ask_vol = self._best_bid_ask(depth)
        spread = best_ask - best_bid
        if spread < 8:
            return orders

        buy_room = self.LIMIT - position
        sell_room = self.LIMIT + position

        take_edge = 2.0
        take_cap = 2
        quote_cap = 2

        # Targeted XL opening brake to reduce D+2 blowups.
        if product == "PEBBLES_XL" and timestamp < 1800:
            take_edge = 3.2
            take_cap = 1
            quote_cap = 1

        if fair - best_ask >= take_edge and buy_room > 0:
            qty = min(buy_room, ask_vol, take_cap)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_room -= qty
        if best_bid - fair >= take_edge and sell_room > 0:
            qty = min(sell_room, bid_vol, take_cap)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                sell_room -= qty

        fair_adj = fair - 0.7 * position
        half_width = max(2.0, 0.40 * spread)
        bid_px = int(round(fair_adj - half_width))
        ask_px = int(round(fair_adj + half_width))
        bid_px = min(bid_px, best_ask - 1)
        ask_px = max(ask_px, best_bid + 1)
        if ask_px <= bid_px:
            ask_px = bid_px + 1

        qsz = 1 if abs(position) >= 7 else quote_cap
        if buy_room > 0:
            orders.append(Order(product, bid_px, min(qsz, buy_room)))
        if sell_room > 0:
            orders.append(Order(product, ask_px, -min(qsz, sell_room)))
        return orders

    def _run_passive_mm_bucket(
        self,
        state: TradingState,
        result: Dict[Symbol, List[Order]],
        products: Tuple[Symbol, ...],
        inventory_k: float = 0.8,
        use_drift: bool = True,
    ) -> None:
        """Shared passive-MM loop for simple product buckets."""
        for product in products:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue
            bb, ba, _, _ = self._best_bid_ask(depth)
            mid = 0.5 * (bb + ba)
            pos = int(state.position.get(product, 0))
            fair = mid - inventory_k * pos
            if use_drift:
                fair += self._drift_bias(product, ba - bb)
            orders = self._quote_product(product, depth, pos, fair)
            if orders:
                result[product] = orders

    def run(self, state: TradingState):
        result: Dict[Symbol, List[Order]] = {}
        data = self._load_data(state.traderData)

        mids: Dict[Symbol, float] = {}
        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue
            bb, ba, _, _ = self._best_bid_ask(depth)
            mids[product] = 0.5 * (bb + ba)

        # Pair signal for CHOC/VAN relative value.
        z = 0.0
        if self.PAIR_A in mids and self.PAIR_B in mids:
            pair_val = mids[self.PAIR_A] + self.PAIR_BETA * mids[self.PAIR_B]
            mean = data.get("pair_mean")
            var = data.get("pair_var")
            if mean is None:
                mean = pair_val
                var = 400.0
            alpha = 0.02
            diff = pair_val - mean
            mean = (1.0 - alpha) * mean + alpha * pair_val
            var = (1.0 - alpha) * var + alpha * (diff * diff)
            std = max(5.0, var ** 0.5)
            z = (pair_val - mean) / std
            data["pair_mean"] = mean
            data["pair_var"] = var

        pos_a = int(state.position.get(self.PAIR_A, 0))
        pos_b = int(state.position.get(self.PAIR_B, 0))
        hedge_pos = pos_a + self.PAIR_BETA * pos_b

        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue

            pos = int(state.position.get(product, 0))
            mid = mids[product]
            bb, ba, _, _ = self._best_bid_ask(depth)

            # Base fair for MM with strong inventory penalty.
            fair = mid - 0.9 * pos
            fair += self._drift_bias(product, ba - bb)

            # Pair-informed skew only for CHOC and VAN.
            if product == self.PAIR_A:
                fair -= 1.2 * z
                fair -= 0.20 * hedge_pos
            elif product == self.PAIR_B:
                fair += 1.2 * z
                fair -= 0.20 * self.PAIR_BETA * hedge_pos

            orders = self._quote_product(product, depth, pos, fair)
            if orders:
                result[product] = orders

        # Category-level passive MM buckets.
        self._run_passive_mm_bucket(state, result, self.GALAXY)
        self._run_passive_mm_bucket(state, result, self.OXYGEN + self.UV)
        self._run_passive_mm_bucket(state, result, self.PANELS)
        self._run_passive_mm_bucket(state, result, self.SLEEP_PODS)
        self._run_passive_mm_bucket(state, result, self.TRANSLATORS)

        # Robots: dishes = EMA reversion; ironing = reversion + short-horizon imbalance.
        robot_ema = data.get("robot_ema", {})
        dishes_depth = state.order_depths.get("ROBOT_DISHES")
        if dishes_depth and dishes_depth.buy_orders and dishes_depth.sell_orders:
            bb, ba, _, _ = self._best_bid_ask(dishes_depth)
            spread = ba - bb
            if spread >= 7:
                mid = 0.5 * (bb + ba)
                pos = int(state.position.get("ROBOT_DISHES", 0))
                prev_ema = float(robot_ema.get("ROBOT_DISHES", mid))
                alpha = 0.03
                ema = alpha * mid + (1.0 - alpha) * prev_ema
                robot_ema["ROBOT_DISHES"] = ema

                dev = mid - ema
                threshold = 34.0
                take_cap = 4
                buy_room = self.LIMIT - pos
                sell_room = self.LIMIT + pos

                r_orders: List[Order] = []
                if dev > threshold and sell_room > 0:
                    qty = min(sell_room, take_cap)
                    if qty > 0:
                        r_orders.append(Order("ROBOT_DISHES", bb, -qty))
                elif dev < -threshold and buy_room > 0:
                    qty = min(buy_room, take_cap)
                    if qty > 0:
                        r_orders.append(Order("ROBOT_DISHES", ba, qty))
                else:
                    fair = ema - 1.2 * pos
                    r_orders = self._quote_product("ROBOT_DISHES", dishes_depth, pos, fair)
                if r_orders:
                    result["ROBOT_DISHES"] = r_orders

        ironing_depth = state.order_depths.get("ROBOT_IRONING")
        if ironing_depth and ironing_depth.buy_orders and ironing_depth.sell_orders:
            bb_i, ba_i, bv_i, av_i = self._best_bid_ask(ironing_depth)
            spread_i = ba_i - bb_i
            if spread_i >= 7:
                mid_i = 0.5 * (bb_i + ba_i)
                pos_i = int(state.position.get("ROBOT_IRONING", 0))
                prev_ie = float(robot_ema.get("ROBOT_IRONING", mid_i))
                ie_alpha = 0.025
                ema_i = ie_alpha * mid_i + (1.0 - ie_alpha) * prev_ie
                robot_ema["ROBOT_IRONING"] = ema_i
                imb_denom = float(bv_i + av_i)
                imb = (bv_i - av_i) / imb_denom if imb_denom > 0 else 0.0
                dev_i = mid_i - ema_i
                buy_rm = self.LIMIT - pos_i
                sell_rm = self.LIMIT + pos_i

                ironing_orders: List[Order] = []
                rev_thresh = 28.0
                if dev_i > rev_thresh and sell_rm > 0:
                    qty = min(sell_rm, 3)
                    if qty > 0:
                        ironing_orders.append(Order("ROBOT_IRONING", bb_i, -qty))
                elif dev_i < -rev_thresh and buy_rm > 0:
                    qty = min(buy_rm, 3)
                    if qty > 0:
                        ironing_orders.append(Order("ROBOT_IRONING", ba_i, qty))
                elif imb > 0.24 and spread_i <= 36 and buy_rm > 0:
                    qty = min(buy_rm, 2)
                    if qty > 0:
                        ironing_orders.append(Order("ROBOT_IRONING", ba_i, qty))
                elif imb < -0.24 and spread_i <= 36 and sell_rm > 0:
                    qty = min(sell_rm, 2)
                    if qty > 0:
                        ironing_orders.append(Order("ROBOT_IRONING", bb_i, -qty))
                else:
                    fair_i = ema_i - 1.1 * pos_i
                    ironing_orders = self._quote_product(
                        "ROBOT_IRONING", ironing_depth, pos_i, fair_i
                    )
                if ironing_orders:
                    result["ROBOT_IRONING"] = ironing_orders

        data["robot_ema"] = robot_ema

        # Microchips: conservative passive MM on historically less-toxic names.
        for product in self.MICROCHIPS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue
            bb, ba, _, _ = self._best_bid_ask(depth)
            spread = ba - bb
            if spread < 8:
                continue
            mid = 0.5 * (bb + ba)
            pos = int(state.position.get(product, 0))
            fair = mid - 1.0 * pos
            fair += self._drift_bias(product, spread)
            orders = self._quote_product(product, depth, pos, fair)
            if orders:
                result[product] = orders

        # Pebbles parity fair values:
        #   XS + S + M + L + XL ~= 50000
        pebble_mids: Dict[str, float] = {}
        for p in self.PEBBLES:
            d = state.order_depths.get(p)
            if not d or not d.buy_orders or not d.sell_orders:
                continue
            bb, ba, _, _ = self._best_bid_ask(d)
            pebble_mids[p] = 0.5 * (bb + ba)

        if len(pebble_mids) == len(self.PEBBLES):
            total = sum(pebble_mids[p] for p in self.PEBBLES)
            parity_offset = total - self.PEBBLES_PARITY
            for p in self.PEBBLES:
                depth = state.order_depths[p]
                pos = int(state.position.get(p, 0))
                pbb, pba, _, _ = self._best_bid_ask(depth)
                fair = pebble_mids[p] - 0.20 * parity_offset
                # Rearranged parity gives product-specific synthetic fair.
                fair = 0.5 * fair + 0.5 * (self.PEBBLES_PARITY - (total - pebble_mids[p]))
                fair += self._drift_bias(p, pba - pbb)
                p_orders = self._quote_pebbles(p, depth, pos, fair, state.timestamp)
                if p_orders:
                    result[p] = p_orders

        trader_data = self._dump_data(data)

        conversions = 0
        return result, conversions, trader_data
