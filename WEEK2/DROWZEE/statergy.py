from src.backtester import Order, OrderBook
from typing import List, Dict

class Trader:
    '''
    A basic liquidity-providing strategy.
    
    state: 
    - state.timestamp: int
    - state.order_depth: OrderBook
    current_position: int
    '''

    def __init__(self):
        self.max_position = 50
        self.order_size = 10
        self.product = "PRODUCT"
        self.spread_threshold = 4

    def run(self, state, current_position: int) -> Dict[str, List[Order]]:
        result = {}
        orders: List[Order] = []
        order_depth: OrderBook = state.order_depth

        if not order_depth.buy_orders or not order_depth.sell_orders:
            result[self.product] = orders
            return result

        # Get best bid and ask
        best_bid, bid_volume = max(order_depth.buy_orders.items(), key=lambda x: int(x[0]))
        best_ask, ask_volume = min(order_depth.sell_orders.items(), key=lambda x: int(x[0]))
        spread = int(best_ask) - int(best_bid)

        # Only trade if spread is small (i.e. tight market)
        if spread <= self.spread_threshold:
            # Determine remaining capacity
            buy_limit = self.max_position - current_position
            sell_limit = current_position + self.max_position  # allows shorting

            # Adjust order sizes to stay within limits
            buy_size = min(self.order_size, buy_limit)
            sell_size = min(self.order_size, sell_limit)

            # Place buy order at best bid
            if buy_size > 0:
                orders.append(Order(self.product, int(best_bid), buy_size))

            # Place sell order at best ask
            if sell_size > 0:
                orders.append(Order(self.product, int(best_ask), -sell_size))

        result[self.product] = orders
        return result
