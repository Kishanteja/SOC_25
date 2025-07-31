from typing import List, Dict
from collections import deque
from statistics import mean, stdev
from src.backtester import Order, OrderBook
import math

class StrategyBase:
    def __init__(self, symbol, max_limit):
        self.symbol = symbol
        self.max_limit = max_limit

    def compute_orders(self, snapshot, book, net_pos):
        return []

class MMStrategy1(StrategyBase):
    def __init__(self):
        super().__init__('SUDOWOODO', 50)
        self.base_val = 10000
        self.tick = 1
        self.req_spread = 2

    def compute_orders(self, snapshot, book, net_pos):
        output = []
        bid = max(book.buy_orders) if book.buy_orders else None
        ask = min(book.sell_orders) if book.sell_orders else None

        if bid is None or ask is None:
            return output

        mid_val = 0.5 * (bid + ask)
        spread_val = ask - bid

        buy_price = bid + self.tick if spread_val > self.req_spread else mid_val - 1
        sell_price = ask - self.tick if spread_val > self.req_spread else mid_val + 1

        volume_cap = 15
        factor = 1 - abs(net_pos) / self.max_limit
        adjusted_size = int(volume_cap * factor)

        if net_pos < self.max_limit and adjusted_size > 0:
            output.append(Order(self.symbol, int(buy_price), min(adjusted_size, self.max_limit - net_pos)))
        if net_pos > -self.max_limit and adjusted_size > 0:
            output.append(Order(self.symbol, int(sell_price), -min(adjusted_size, net_pos + self.max_limit)))

        return output

class MeanRevertMomentum(StrategyBase):
    def __init__(self):
        super().__init__('DROWZEE', 50)
        self.price_mem = deque(maxlen=50)
        self.volumes = deque(maxlen=20)

    def compute_orders(self, snapshot, book, net_pos):
        result = []
        bid = max(book.buy_orders) if book.buy_orders else None
        ask = min(book.sell_orders) if book.sell_orders else None

        if bid is None or ask is None:
            return result

        mid = (bid + ask) / 2
        self.price_mem.append(mid)

        bid_vol = book.buy_orders.get(bid, 0)
        ask_vol = book.sell_orders.get(ask, 0)
        imbalance = bid_vol - ask_vol

        if len(self.price_mem) < 10:
            return result

        short_avg = mean(list(self.price_mem)[-10:])
        long_avg = mean(self.price_mem)
        std = stdev(self.price_mem)
        momentum = mid - long_avg
        vol_factor = std / mid if mid > 0 else 0

        low_bound = -0.8 * std
        high_bound = 0.8 * std

        base_vol = 12
        conf = min(2.0, abs(momentum) / std) if std > 0 else 1
        qty = int(base_vol * conf)

        if momentum < low_bound and net_pos < self.max_limit:
            px = bid + 1 if imbalance > 0 else bid
            result.append(Order(self.symbol, px, min(qty, self.max_limit - net_pos)))
        elif momentum > high_bound and net_pos > -self.max_limit:
            px = ask - 1 if imbalance < 0 else ask
            result.append(Order(self.symbol, px, -min(qty, net_pos + self.max_limit)))

        return result

class TrendRevert(StrategyBase):
    def __init__(self):
        super().__init__('ABRA', 50)
        self.history = deque(maxlen=80)
        self.trend_data = deque(maxlen=20)

    def compute_orders(self, snapshot, book, net_pos):
        orders = []
        bid = max(book.buy_orders) if book.buy_orders else None
        ask = min(book.sell_orders) if book.sell_orders else None

        if bid is None or ask is None:
            return orders

        mid_val = (bid + ask) / 2
        self.history.append(mid_val)

        if len(self.history) < 20:
            return orders

        mean_val = mean(self.history)
        std_dev = stdev(self.history)
        z_val = (mid_val - mean_val) / std_dev if std_dev > 0 else 0

        past_prices = list(self.history)[-10:]
        trend_val = (past_prices[-1] - past_prices[0]) / len(past_prices)
        self.trend_data.append(trend_val)

        strength = abs(trend_val) / std_dev if std_dev > 0 else 0
        threshold = 1.2
        adj = 0.3 * strength

        low = -(threshold + adj)
        high = threshold + adj

        max_qty = 15
        control = 1 - abs(net_pos) / self.max_limit
        qty = int(max_qty * control)

        if z_val < low and net_pos < self.max_limit:
            price = bid + 1 if trend_val > 0 else bid
            orders.append(Order(self.symbol, price, min(qty, self.max_limit - net_pos)))
        elif z_val > high and net_pos > -self.max_limit:
            price = ask - 1 if trend_val < 0 else ask
            orders.append(Order(self.symbol, price, -min(qty, net_pos + self.max_limit)))

        return orders

class CointegratedPair(StrategyBase):
    def __init__(self, label, max_qty, partner):
        super().__init__(label, max_qty)
        self.partner = partner
        self.history = deque(maxlen=100)
        self.ratio = 1.0

    def update_hedge(self):
        if len(self.history) < 30:
            return 1.0
        latest = list(self.history)[-30:]
        var = stdev(latest) ** 2
        return max(0.5, min(2.0, 1 / (1 + var)))

    def compute_orders(self, snapshot, book, net_pos):
        if self.partner not in snapshot.order_depth:
            return []

        ob_self = book
        ob_pair = snapshot.order_depth[self.partner]

        if not (ob_self.buy_orders and ob_self.sell_orders and ob_pair.buy_orders and ob_pair.sell_orders):
            return []

        mid_self = (max(ob_self.buy_orders) + min(ob_self.sell_orders)) / 2
        mid_pair = (max(ob_pair.buy_orders) + min(ob_pair.sell_orders)) / 2

        spread_val = mid_self - self.ratio * mid_pair
        self.history.append(spread_val)

        if len(self.history) < 30:
            return []

        self.ratio = self.update_hedge()

        avg_spread = mean(self.history)
        std = stdev(self.history)
        z = (spread_val - avg_spread) / std if std > 0 else 0

        entries = []
        if z > 1.5 and net_pos > -self.max_limit:
            entries.append(Order(self.symbol, min(ob_self.sell_orders), -12))
        elif z < -1.5 and net_pos < self.max_limit:
            entries.append(Order(self.symbol, max(ob_self.buy_orders), 12))
        elif abs(z) < 0.3 and abs(net_pos) > 5:
            if net_pos > 0:
                entries.append(Order(self.symbol, min(ob_self.sell_orders), -min(8, net_pos)))
            else:
                entries.append(Order(self.symbol, max(ob_self.buy_orders), min(8, -net_pos)))

        return entries

class IndexArb(StrategyBase):
    def __init__(self, label, max_pos, components):
        super().__init__(label, max_pos)
        self.weights = components
        self.midpoints = deque(maxlen=100)
        self.value_record = deque(maxlen=50)

    def est_value(self, snapshot):
        val = 0
        total = 0
        for name, wt in self.weights.items():
            ob = snapshot.order_depth.get(name)
            if ob and ob.buy_orders and ob.sell_orders:
                mid = (max(ob.buy_orders) + min(ob.sell_orders)) / 2
                val += wt * mid
                total += wt
        return val / total if total else 0

    def compute_orders(self, snapshot, book, net_pos):
        fair_val = self.est_value(snapshot)
        if fair_val == 0:
            return []

        bid = max(book.buy_orders) if book.buy_orders else None
        ask = min(book.sell_orders) if book.sell_orders else None
        if bid is None or ask is None:
            return []

        mid = (bid + ask) / 2
        self.midpoints.append(mid)
        self.value_record.append(fair_val)

        diff = mid - fair_val

        if len(self.value_record) > 20:
            thresh = max(1.0, stdev(self.value_record) * 2.0)
        else:
            thresh = 2.0

        base_qty = min(15, self.max_limit // 3)
        hedge_possible = all(prod in snapshot.order_depth for prod in self.weights)

        if not hedge_possible:
            return []

        result = []
        if diff > thresh and net_pos > -self.max_limit:
            result.append(Order(self.symbol, ask, -base_qty))
            for prod, wt in self.weights.items():
                ob = snapshot.order_depth[prod]
                if ob.sell_orders:
                    result.append(Order(prod, min(ob.sell_orders), max(1, int(wt * base_qty))))
        elif diff < -thresh and net_pos < self.max_limit:
            result.append(Order(self.symbol, bid, base_qty))
            for prod, wt in self.weights.items():
                ob = snapshot.order_depth[prod]
                if ob.buy_orders:
                    result.append(Order(prod, max(ob.buy_orders), -max(1, int(wt * base_qty))))

        return result

class Trader:
    CAP = 0

    def __init__(self):
        self.models = {
            "SUDOWOODO": MMStrategy1(),
            "DROWZEE": MeanRevertMomentum(),
            "ABRA": TrendRevert(),
            "SHINX": CointegratedPair("SHINX", 60, "JOLTEON"),
            "LUXRAY": CointegratedPair("LUXRAY", 250, "JOLTEON"),
            "JOLTEON": CointegratedPair("JOLTEON", 350, "LUXRAY"),
            "ASH": IndexArb("ASH", 60, {"LUXRAY": 0.6, "JOLTEON": 0.3, "SHINX": 0.1}),
            "MISTY": IndexArb("MISTY", 100, {"LUXRAY": 0.67, "JOLTEON": 0.33}),
            "PRODUCT": StrategyBase("PRODUCT", 50)
        }

    def run(self, state):
        pos = getattr(state, 'positions', {})
        depth = getattr(state, 'order_depth', {})

        if len(depth) == 1 and "PRODUCT" in depth:
            strat = self.models["PRODUCT"]
            p = pos.get("PRODUCT", 0)
            final = strat.compute_orders(state, depth["PRODUCT"], p)
            self.CAP = strat.max_limit
            return final, self.CAP

        res = {}
        for prod, book in depth.items():
            p = pos.get(prod, 0)
            strat = self.models.get(prod, StrategyBase(prod, 50))
            res[prod] = strat.compute_orders(state, book, p)

        return res, self.CAP
