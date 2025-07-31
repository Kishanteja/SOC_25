from typing import List, Dict
from collections import deque
from statistics import mean, stdev
from src.backtester import Order, OrderBook

class Trader:
    def __init__(self):
        self.window_size = 20
        self.mid_prices = deque(maxlen=self.window_size)
        self.max_position = 50
        self.std_factor = 1.5
        self.min_spread = 2  # to avoid trading noise

    def run(self, state, current_position: int) -> Dict[str, List[Order]]:
        order_depth: OrderBook = state.order_depth
        result: Dict[str, List[Order]] = {}
        orders: List[Order] = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            result["PRODUCT"] = []
            return result

        # Get best bid and ask
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        spread = best_ask - best_bid

        if spread < self.min_spread:
            # No real opportunity, avoid overtrading
            result["PRODUCT"] = []
            return result

        # Update mid-price history
        mid_price = (best_ask + best_bid) / 2
        self.mid_prices.append(mid_price)

        if len(self.mid_prices) < self.window_size:
            result["PRODUCT"] = []
            return result

        avg_price = mean(self.mid_prices)
        std_dev = stdev(self.mid_prices)

        upper_threshold = avg_price + self.std_factor * std_dev
        lower_threshold = avg_price - self.std_factor * std_dev

        # BUY Logic: price much lower than expected
        best_ask_price, ask_volume = sorted(order_depth.sell_orders.items())[0]
        if best_ask_price < lower_threshold and current_position < self.max_position:
            buy_qty = min(-ask_volume, self.max_position - current_position)
            if buy_qty > 0:
                orders.append(Order("PRODUCT", best_ask_price, buy_qty))

        # SELL Logic: price much higher than expected
        best_bid_price, bid_volume = sorted(order_depth.buy_orders.items(), reverse=True)[0]
        if best_bid_price > upper_threshold and current_position > -self.max_position:
            sell_qty = min(bid_volume, current_position + self.max_position)
            if sell_qty > 0:
                orders.append(Order("PRODUCT", best_bid_price, -sell_qty))

        result["PRODUCT"] = orders
        return result
