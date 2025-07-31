from src.backtester import Order, OrderBook
from typing import List, Dict

class Trader:
    '''
    Trading strategy that reacts to spread opportunities.
    '''
    def __init__(self):
        self.max_position = 20
        self.product = "PRODUCT"

    def run(self, state, current_position: int) -> Dict[str, List[Order]]:
        result = {}
        orders: List[Order] = []
        order_depth: OrderBook = state.order_depth

        if not order_depth.buy_orders or not order_depth.sell_orders:
            result[self.product] = orders
            return result

        # Get best prices
        best_ask, ask_volume = min(order_depth.sell_orders.items())
        best_bid, bid_volume = max(order_depth.buy_orders.items())

        spread = best_ask - best_bid
        mid_price = (best_ask + best_bid) / 2

        # Define trade thresholds relative to spread
        buy_price = int(mid_price - 0.25 * spread)
        sell_price = int(mid_price + 0.25 * spread)

        # --- Buy if ask is cheap ---
        if best_ask <= buy_price:
            buy_limit = self.max_position - current_position
            if buy_limit > 0:
                volume = min(ask_volume, buy_limit)
                orders.append(Order(self.product, best_ask, volume))

        # --- Sell if bid is rich ---
        if best_bid >= sell_price:
            sell_limit = current_position + self.max_position  # allows shorting up to -max
            if sell_limit > 0:
                volume = min(bid_volume, sell_limit)
                orders.append(Order(self.product, best_bid, -volume))

        result[self.product] = orders
        return result
