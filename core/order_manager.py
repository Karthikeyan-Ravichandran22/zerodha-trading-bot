"""
Order Manager - Handles order placement, tracking, and execution
"""

from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from config.settings import TRADING_MODE, PRODUCT_TYPE


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "PENDING"
    PLACED = "PLACED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    stop_loss: float
    target: float
    order_id: Optional[str] = None
    sl_order_id: Optional[str] = None
    target_order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    entry_time: datetime = None
    exit_time: datetime = None
    exit_price: float = None
    pnl: float = 0.0
    strategy: str = ""


class OrderManager:
    """Manages order placement and tracking"""
    
    def __init__(self, zerodha_client=None):
        self.client = zerodha_client
        self.active_orders: Dict[str, Order] = {}
        self.completed_orders: List[Order] = []
    
    def place_bracket_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        target: float,
        strategy: str = ""
    ) -> Optional[Order]:
        """Place entry order with SL and target"""
        
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=entry_price,
            stop_loss=stop_loss,
            target=target,
            strategy=strategy,
            entry_time=datetime.now()
        )
        
        if TRADING_MODE == "paper":
            order.order_id = f"PAPER_{datetime.now().timestamp()}"
            order.status = OrderStatus.COMPLETE
            logger.info(f"📝 [PAPER] {side.value} {quantity} {symbol} @ ₹{entry_price}")
            logger.info(f"   SL: ₹{stop_loss} | Target: ₹{target}")
            self.active_orders[order.order_id] = order
            return order
        
        if TRADING_MODE == "signal":
            logger.info(f"📢 [SIGNAL] {side.value} {quantity} {symbol} @ ₹{entry_price}")
            logger.info(f"   SL: ₹{stop_loss} | Target: ₹{target}")
            return order
        
        # Real order placement
        if self.client and self.client.is_connected:
            order_id = self.client.place_order(
                symbol=symbol,
                exchange="NSE",
                transaction_type=side.value,
                quantity=quantity,
                order_type="LIMIT",
                product=PRODUCT_TYPE,
                price=entry_price
            )
            if order_id:
                order.order_id = order_id
                order.status = OrderStatus.PLACED
                self.active_orders[order_id] = order
                self._place_sl_order(order)
                return order
        
        return None
    
    def _place_sl_order(self, order: Order):
        """Place stop-loss order for an existing position"""
        if not self.client:
            return
        
        sl_side = OrderSide.SELL if order.side == OrderSide.BUY else OrderSide.BUY
        sl_order_id = self.client.place_order(
            symbol=order.symbol,
            exchange="NSE",
            transaction_type=sl_side.value,
            quantity=order.quantity,
            order_type="SL-M",
            product=PRODUCT_TYPE,
            trigger_price=order.stop_loss
        )
        if sl_order_id:
            order.sl_order_id = sl_order_id
    
    def close_position(self, order_id: str, exit_price: float = None) -> Optional[float]:
        """Close an open position"""
        if order_id not in self.active_orders:
            return None
        
        order = self.active_orders[order_id]
        order.exit_time = datetime.now()
        order.exit_price = exit_price or order.target
        
        # Calculate P&L
        if order.side == OrderSide.BUY:
            order.pnl = (order.exit_price - order.price) * order.quantity
        else:
            order.pnl = (order.price - order.exit_price) * order.quantity
        
        order.status = OrderStatus.COMPLETE
        self.completed_orders.append(order)
        del self.active_orders[order_id]
        
        logger.info(f"{'💚' if order.pnl >= 0 else '🔴'} Closed {order.symbol}: ₹{order.pnl:,.2f}")
        return order.pnl
    
    def get_open_positions(self) -> List[Order]:
        return list(self.active_orders.values())
    
    def square_off_all(self):
        """Square off all open positions"""
        logger.warning("🔔 Squaring off all positions!")
        for order_id in list(self.active_orders.keys()):
            self.close_position(order_id)
