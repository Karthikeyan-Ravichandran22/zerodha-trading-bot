"""
Execution Engine - Single point for all order placement

This module:
1. Receives validated signals from Risk Engine
2. Places orders via Angel One Trading API
3. Manages order lifecycle (placed → filled → SL/Target)
4. Handles order confirmations and rejections
5. Updates Risk Engine with position changes
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Dict, List
import threading
import os
import logging
import pyotp

from SmartApi import SmartConnect

from core.signal_aggregator import TradingSignal, SignalType, SignalStatus, signal_aggregator
from core.risk_engine import risk_engine, RiskCheck

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


class OrderStatus(Enum):
    PENDING = "PENDING"
    PLACED = "PLACED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "STOPLOSS_LIMIT"
    SL_MARKET = "STOPLOSS_MARKET"


@dataclass
class Order:
    """Order object for tracking"""
    order_id: str
    signal: TradingSignal
    order_type: OrderType
    status: OrderStatus = OrderStatus.PENDING
    placed_at: datetime = field(default_factory=lambda: datetime.now(IST))
    filled_at: Optional[datetime] = None
    filled_price: float = 0.0
    filled_quantity: int = 0
    rejection_reason: str = ""
    broker_order_id: str = ""
    sl_order_id: str = ""
    target_order_id: str = ""


class ExecutionEngine:
    """
    Central execution engine that places all orders
    Uses Angel One Trading API
    """
    
    def __init__(self):
        self.api_key = os.getenv('ANGEL_API_KEY')
        self.secret_key = os.getenv('ANGEL_SECRET_KEY')
        self.client_id = os.getenv('ANGEL_CLIENT_ID')
        self.mpin = os.getenv('ANGEL_MPIN')
        self.totp_secret = os.getenv('ANGEL_TOTP_SECRET')
        
        self.smart_api: Optional[SmartConnect] = None
        self.is_authenticated = False
        self.auth_token = ""
        self.refresh_token = ""
        self.feed_token = ""
        
        # Order tracking
        self.pending_orders: Dict[str, Order] = {}
        self.executed_orders: Dict[str, Order] = {}
        self.rejected_orders: List[Order] = []
        
        self._lock = threading.Lock()
        
        # Trading mode
        self.trading_mode = os.getenv('TRADING_MODE', 'paper').lower()
        
        logger.info(f"🎯 Execution Engine initialized")
        logger.info(f"   Mode: {self.trading_mode.upper()}")
    
    def authenticate(self) -> bool:
        """Authenticate with Angel One Trading API"""
        try:
            if not all([self.api_key, self.secret_key, self.client_id, self.mpin, self.totp_secret]):
                logger.error("❌ Missing Angel One credentials")
                return False
            
            self.smart_api = SmartConnect(api_key=self.api_key)
            
            # Generate TOTP
            totp = pyotp.TOTP(self.totp_secret)
            totp_code = totp.now()
            
            # Login
            data = self.smart_api.generateSession(
                clientCode=self.client_id,
                password=self.mpin,
                totp=totp_code
            )
            
            if data.get('status'):
                self.auth_token = data['data']['jwtToken']
                self.refresh_token = data['data']['refreshToken']
                self.feed_token = self.smart_api.getfeedToken()
                self.is_authenticated = True
                
                # Get user profile
                profile = self.smart_api.getProfile(self.refresh_token)
                user_name = profile['data'].get('name', 'Unknown')
                
                logger.info(f"✅ Execution Engine authenticated: {user_name}")
                
                # Update risk engine with available funds
                self._sync_funds()
                
                return True
            else:
                logger.error(f"❌ Authentication failed: {data.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return False
    
    def _sync_funds(self):
        """Sync available funds with Risk Engine"""
        try:
            if not self.is_authenticated:
                return
            
            rms_data = self.smart_api.rmsLimit()
            if rms_data.get('status'):
                available = float(rms_data['data'].get('availablecash', 0))
                risk_engine.update_funds(available)
                logger.info(f"💰 Funds synced: ₹{available:,.2f}")
        except Exception as e:
            logger.error(f"❌ Failed to sync funds: {e}")
    
    def execute_signal(self, signal: TradingSignal) -> bool:
        """
        Execute a validated trading signal
        
        Flow:
        1. Signal already validated by Risk Engine
        2. Place entry order
        3. If filled, place SL and Target orders
        4. Track order status
        """
        with self._lock:
            # Check mode
            if self.trading_mode == 'paper':
                return self._paper_execute(signal)
            elif self.trading_mode == 'signal':
                return self._signal_only(signal)
            elif self.trading_mode in ['semi-auto', 'auto']:
                return self._live_execute(signal)
            else:
                logger.warning(f"⚠️ Unknown trading mode: {self.trading_mode}")
                return False
    
    def _paper_execute(self, signal: TradingSignal) -> bool:
        """Paper trading - log but don't place real orders"""
        order_id = f"PAPER_{signal.signal_id}"
        
        order = Order(
            order_id=order_id,
            signal=signal,
            order_type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            filled_at=datetime.now(IST),
            filled_price=signal.entry_price,
            filled_quantity=signal.quantity
        )
        
        self.executed_orders[order_id] = order
        
        # Update risk tracking
        risk_engine.add_position(signal.symbol, {
            'entry_price': signal.entry_price,
            'quantity': signal.quantity,
            'signal_type': signal.signal_type.value,
            'order_id': order_id
        })
        
        # Update signal status
        signal_aggregator.mark_signal_status(signal.signal_id, SignalStatus.EXECUTED)
        
        logger.info(f"📝 [PAPER] Executed: {signal.symbol} {signal.signal_type.value} x{signal.quantity} @ ₹{signal.entry_price:.2f}")
        logger.info(f"   SL: ₹{signal.stop_loss:.2f} | Target: ₹{signal.target:.2f}")
        
        return True
    
    def _signal_only(self, signal: TradingSignal) -> bool:
        """Signal mode - notify but don't execute"""
        logger.info(f"📡 [SIGNAL] {signal.symbol} {signal.signal_type.value}")
        logger.info(f"   Entry: ₹{signal.entry_price:.2f}")
        logger.info(f"   SL: ₹{signal.stop_loss:.2f} | Target: ₹{signal.target:.2f}")
        logger.info(f"   Qty: {signal.quantity} | Risk: ₹{signal.risk_amount:.2f}")
        
        # Update signal status
        signal_aggregator.mark_signal_status(signal.signal_id, SignalStatus.APPROVED)
        
        # TODO: Send Telegram notification
        
        return True
    
    def _live_execute(self, signal: TradingSignal) -> bool:
        """Live trading - place real orders"""
        if not self.is_authenticated:
            if not self.authenticate():
                logger.error("❌ Cannot execute - not authenticated")
                return False
        
        try:
            # Get instrument token for the stock
            symbol_token = self._get_symbol_token(signal.symbol)
            if not symbol_token:
                logger.error(f"❌ Symbol token not found for {signal.symbol}")
                return False
            
            # Determine transaction type
            transaction_type = "BUY" if signal.signal_type == SignalType.BUY else "SELL"
            
            # Place entry order
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": signal.symbol + "-EQ",
                "symboltoken": symbol_token,
                "transactiontype": transaction_type,
                "exchange": "NSE",
                "ordertype": "LIMIT",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "price": str(signal.entry_price),
                "quantity": str(signal.quantity)
            }
            
            if self.trading_mode == 'semi-auto':
                # Semi-auto: Log order params for manual confirmation
                logger.info(f"🔔 [SEMI-AUTO] Order ready for {signal.symbol}:")
                logger.info(f"   {transaction_type} x{signal.quantity} @ ₹{signal.entry_price:.2f}")
                logger.info(f"   SL: ₹{signal.stop_loss:.2f} | Target: ₹{signal.target:.2f}")
                
                # Mark as approved, waiting for manual execution
                signal_aggregator.mark_signal_status(signal.signal_id, SignalStatus.APPROVED)
                return True
            
            # Auto mode: Place actual order
            order_response = self.smart_api.placeOrder(order_params)
            
            if order_response.get('status'):
                broker_order_id = order_response['data']['orderid']
                
                order = Order(
                    order_id=f"LIVE_{signal.signal_id}",
                    signal=signal,
                    order_type=OrderType.LIMIT,
                    status=OrderStatus.PLACED,
                    broker_order_id=broker_order_id
                )
                
                self.pending_orders[order.order_id] = order
                
                logger.info(f"✅ [LIVE] Order placed: {signal.symbol} {transaction_type} x{signal.quantity}")
                logger.info(f"   Broker Order ID: {broker_order_id}")
                
                # Update signal status
                signal_aggregator.mark_signal_status(signal.signal_id, SignalStatus.EXECUTED)
                
                return True
            else:
                reason = order_response.get('message', 'Unknown error')
                logger.error(f"❌ Order rejected: {reason}")
                signal_aggregator.mark_signal_status(signal.signal_id, SignalStatus.REJECTED)
                return False
                
        except Exception as e:
            logger.error(f"❌ Order execution error: {e}")
            signal_aggregator.mark_signal_status(signal.signal_id, SignalStatus.REJECTED)
            return False
    
    def _get_symbol_token(self, symbol: str) -> Optional[str]:
        """Get Angel One symbol token for a stock"""
        # Common NSE stock tokens (hardcoded for speed)
        # In production, fetch from Angel One's instrument master
        SYMBOL_TOKENS = {
            'PNB': '10666',
            'SAIL': '2963',
            'IDEA': '14366',
            'IRFC': '26195',
            'PFC': '14299',
            'BPCL': '526',
            'BHEL': '438',
            'TATAMOTORS': '3456',
            'TATASTEEL': '3499',
            'SBIN': '3045',
            'RELIANCE': '2885',
            'ICICIBANK': '4963',
            'HDFCBANK': '1333',
            'INFY': '1594',
            'TCS': '11536',
            'ITC': '1660',
        }
        return SYMBOL_TOKENS.get(symbol)
    
    def process_pending_signals(self):
        """
        Main loop to process pending signals
        Called periodically by the trading bot
        """
        # Get highest priority signal
        signal = signal_aggregator.get_next_signal()
        
        if not signal:
            return
        
        # Validate through risk engine
        risk_check = risk_engine.validate_signal(signal)
        
        if risk_check.passed:
            # Adjust quantity if needed
            if risk_check.adjusted_quantity != signal.quantity:
                logger.info(f"📊 Quantity adjusted: {signal.quantity} → {risk_check.adjusted_quantity}")
                signal.quantity = risk_check.adjusted_quantity
            
            # Execute the signal
            self.execute_signal(signal)
        else:
            # Mark signal as rejected
            signal_aggregator.mark_signal_status(signal.signal_id, SignalStatus.REJECTED)
            logger.warning(f"🛡️ Signal rejected: {signal.symbol} - {risk_check.reason}")
    
    def get_open_orders(self) -> List[dict]:
        """Get all open/pending orders"""
        return [
            {
                'order_id': order.order_id,
                'symbol': order.signal.symbol,
                'type': order.signal.signal_type.value,
                'quantity': order.signal.quantity,
                'entry': order.signal.entry_price,
                'status': order.status.value,
                'broker_order_id': order.broker_order_id
            }
            for order in self.pending_orders.values()
        ]
    
    def get_execution_stats(self) -> dict:
        """Get execution statistics"""
        return {
            'mode': self.trading_mode,
            'is_authenticated': self.is_authenticated,
            'pending_orders': len(self.pending_orders),
            'executed_orders': len(self.executed_orders),
            'rejected_orders': len(self.rejected_orders)
        }


# Global execution engine instance
execution_engine = ExecutionEngine()
