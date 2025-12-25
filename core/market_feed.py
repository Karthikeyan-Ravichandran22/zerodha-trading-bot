"""
Angel One Market Feed WebSocket Client

Uses the Market Feeds API for real-time price streaming
Provides live LTP updates to strategies
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Callable, Set
import threading
import os
import logging
import json
import pyotp

from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


class MarketFeedClient:
    """
    WebSocket client for real-time market data
    Uses the Market Feeds API credentials
    """
    
    # Subscription modes
    MODE_LTP = 1      # Last Traded Price only
    MODE_QUOTE = 2    # LTP + Open, High, Low, Close
    MODE_FULL = 3     # Full market depth
    
    def __init__(self):
        # Use Market Feed API credentials
        self.api_key = os.getenv('ANGEL_FEED_API_KEY')
        self.secret_key = os.getenv('ANGEL_FEED_SECRET_KEY')
        
        # Common authentication details
        self.client_id = os.getenv('ANGEL_CLIENT_ID')
        self.mpin = os.getenv('ANGEL_MPIN')
        self.totp_secret = os.getenv('ANGEL_TOTP_SECRET')
        
        self.smart_api: Optional[SmartConnect] = None
        self.websocket: Optional[SmartWebSocketV2] = None
        self.is_authenticated = False
        self.is_connected = False
        self.feed_token = ""
        self.auth_token = ""
        
        # Subscribed symbols
        self.subscriptions: Set[str] = set()
        
        # Latest prices cache
        self.prices: Dict[str, dict] = {}
        
        # Callbacks
        self._price_callbacks: List[Callable] = []
        
        # Thread lock
        self._lock = threading.Lock()
        
        logger.info("📡 Market Feed Client initialized")
    
    def authenticate(self) -> bool:
        """Authenticate with Angel One Market Feed API"""
        try:
            if not self.api_key:
                logger.warning("⚠️ Market Feed API key not configured, using Trading API")
                self.api_key = os.getenv('ANGEL_API_KEY')
                self.secret_key = os.getenv('ANGEL_SECRET_KEY')
            
            if not all([self.api_key, self.client_id, self.mpin, self.totp_secret]):
                logger.error("❌ Missing credentials for Market Feed API")
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
                self.feed_token = self.smart_api.getfeedToken()
                self.is_authenticated = True
                logger.info("✅ Market Feed API authenticated")
                return True
            else:
                logger.error(f"❌ Market Feed Auth failed: {data.get('message')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Market Feed Auth error: {e}")
            return False
    
    def connect(self) -> bool:
        """Connect to WebSocket for live data"""
        if not self.is_authenticated:
            if not self.authenticate():
                return False
        
        try:
            # Create WebSocket connection
            self.websocket = SmartWebSocketV2(
                auth_token=self.auth_token,
                api_key=self.api_key,
                client_code=self.client_id,
                feed_token=self.feed_token
            )
            
            # Set callbacks
            self.websocket.on_data = self._on_data
            self.websocket.on_error = self._on_error
            self.websocket.on_close = self._on_close
            self.websocket.on_open = self._on_open
            
            # Connect in a separate thread
            ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
            ws_thread.start()
            
            logger.info("📡 WebSocket connecting...")
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection error: {e}")
            return False
    
    def _run_websocket(self):
        """Run WebSocket in background thread"""
        try:
            self.websocket.connect()
        except Exception as e:
            logger.error(f"❌ WebSocket runtime error: {e}")
    
    def _on_open(self, wsapp):
        """Called when WebSocket connection opens"""
        self.is_connected = True
        logger.info("📡 WebSocket connected")
        
        # Resubscribe to previous symbols
        if self.subscriptions:
            self._subscribe_all()
    
    def _on_data(self, wsapp, data):
        """Called when data is received"""
        try:
            with self._lock:
                # Parse the data
                if isinstance(data, str):
                    data = json.loads(data)
                
                symbol_token = data.get('token', '')
                
                price_data = {
                    'ltp': data.get('ltp', 0) / 100,  # Angel One sends price * 100
                    'open': data.get('open_price_day', 0) / 100,
                    'high': data.get('high_price_day', 0) / 100,
                    'low': data.get('low_price_day', 0) / 100,
                    'close': data.get('close_price', 0) / 100,
                    'volume': data.get('volume_trade_day', 0),
                    'timestamp': datetime.now(IST)
                }
                
                self.prices[symbol_token] = price_data
                
                # Call registered callbacks
                for callback in self._price_callbacks:
                    try:
                        callback(symbol_token, price_data)
                    except Exception as e:
                        logger.error(f"❌ Callback error: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Data parsing error: {e}")
    
    def _on_error(self, wsapp, error):
        """Called on WebSocket error"""
        logger.error(f"❌ WebSocket error: {error}")
        self.is_connected = False
    
    def _on_close(self, wsapp, code, reason):
        """Called when WebSocket closes"""
        logger.warning(f"📡 WebSocket closed: {code} - {reason}")
        self.is_connected = False
    
    def subscribe(self, symbols: List[str], exchange: str = 'NSE', mode: int = MODE_LTP):
        """
        Subscribe to live price updates for symbols
        
        Args:
            symbols: List of stock symbols
            exchange: Exchange ('NSE', 'BSE', 'MCX')
            mode: Subscription mode (LTP, QUOTE, FULL)
        """
        if not self.is_connected:
            logger.warning("⚠️ WebSocket not connected, queuing subscription")
        
        # Get symbol tokens
        token_list = []
        for symbol in symbols:
            token = self._get_symbol_token(symbol, exchange)
            if token:
                token_list.append({
                    "exchangeType": self._get_exchange_type(exchange),
                    "tokens": [token]
                })
                self.subscriptions.add(f"{exchange}:{symbol}")
        
        if token_list and self.is_connected:
            try:
                self.websocket.subscribe("correlation_id", mode, token_list)
                logger.info(f"📡 Subscribed to {len(symbols)} symbols")
            except Exception as e:
                logger.error(f"❌ Subscription error: {e}")
    
    def _subscribe_all(self):
        """Resubscribe to all saved subscriptions"""
        if not self.subscriptions:
            return
        
        # Group by exchange
        nse_symbols = []
        mcx_symbols = []
        
        for sub in self.subscriptions:
            exchange, symbol = sub.split(':')
            if exchange == 'NSE':
                nse_symbols.append(symbol)
            elif exchange == 'MCX':
                mcx_symbols.append(symbol)
        
        if nse_symbols:
            self.subscribe(nse_symbols, 'NSE')
        if mcx_symbols:
            self.subscribe(mcx_symbols, 'MCX')
    
    def unsubscribe(self, symbols: List[str], exchange: str = 'NSE'):
        """Unsubscribe from symbols"""
        if not self.is_connected:
            return
        
        token_list = []
        for symbol in symbols:
            token = self._get_symbol_token(symbol, exchange)
            if token:
                token_list.append({
                    "exchangeType": self._get_exchange_type(exchange),
                    "tokens": [token]
                })
                self.subscriptions.discard(f"{exchange}:{symbol}")
        
        if token_list:
            try:
                self.websocket.unsubscribe("correlation_id", self.MODE_LTP, token_list)
                logger.info(f"📡 Unsubscribed from {len(symbols)} symbols")
            except Exception as e:
                logger.error(f"❌ Unsubscription error: {e}")
    
    def get_ltp(self, symbol: str, exchange: str = 'NSE') -> Optional[float]:
        """Get cached LTP for a symbol"""
        token = self._get_symbol_token(symbol, exchange)
        if token and token in self.prices:
            return self.prices[token].get('ltp')
        return None
    
    def get_price_data(self, symbol: str, exchange: str = 'NSE') -> Optional[dict]:
        """Get full cached price data for a symbol"""
        token = self._get_symbol_token(symbol, exchange)
        if token and token in self.prices:
            return self.prices[token]
        return None
    
    def register_callback(self, callback: Callable):
        """Register a callback for price updates"""
        self._price_callbacks.append(callback)
    
    def _get_exchange_type(self, exchange: str) -> int:
        """Get exchange type code"""
        return {
            'NSE': 1,
            'NFO': 2,
            'BSE': 3,
            'MCX': 5,
            'CDS': 13
        }.get(exchange.upper(), 1)
    
    def _get_symbol_token(self, symbol: str, exchange: str = 'NSE') -> Optional[str]:
        """Get symbol token"""
        # Reuse the same token mapping
        NSE_TOKENS = {
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
            'GOLDM': '66243',
            'SILVERM': '66249',
        }
        return NSE_TOKENS.get(symbol.upper())
    
    def disconnect(self):
        """Disconnect WebSocket"""
        if self.websocket:
            try:
                self.websocket.close_connection()
                self.is_connected = False
                logger.info("📡 WebSocket disconnected")
            except Exception as e:
                logger.error(f"❌ Disconnect error: {e}")


# Global market feed client instance
market_feed = MarketFeedClient()
