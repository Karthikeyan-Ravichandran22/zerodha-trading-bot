"""
Zerodha Kite Connect API Client Wrapper
Handles authentication, connection, and basic API operations
"""

import os
import webbrowser
from datetime import datetime, date
from typing import Optional, Dict, List, Any
from kiteconnect import KiteConnect, KiteTicker
from loguru import logger

from config.settings import (
    KITE_API_KEY, 
    KITE_API_SECRET,
    TRADING_MODE
)


class ZerodhaClient:
    """
    Wrapper for Zerodha Kite Connect API
    Handles authentication and provides clean interface for trading operations
    """
    
    def __init__(self):
        self.api_key = KITE_API_KEY
        self.api_secret = KITE_API_SECRET
        self.kite: Optional[KiteConnect] = None
        self.ticker: Optional[KiteTicker] = None
        self.access_token: Optional[str] = None
        self.is_connected = False
        self._instruments_cache: Dict = {}
        
    def initialize(self) -> bool:
        """Initialize the Kite Connect client"""
        if not self.api_key:
            logger.error("❌ KITE_API_KEY not set. Please configure in .env file")
            logger.info("📝 Get API key from https://kite.trade (₹2000/month)")
            return False
            
        try:
            self.kite = KiteConnect(api_key=self.api_key)
            logger.info(f"✅ Kite Connect initialized with API key: {self.api_key[:8]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kite Connect: {e}")
            return False
    
    def get_login_url(self) -> str:
        """Get the login URL for authentication"""
        if not self.kite:
            self.initialize()
        return self.kite.login_url()
    
    def authenticate(self, request_token: str = None) -> bool:
        """
        Authenticate with Zerodha using request token
        
        Flow:
        1. User visits login URL
        2. After login, Zerodha redirects with request_token
        3. Exchange request_token for access_token
        """
        if not self.kite:
            if not self.initialize():
                return False
        
        # Check if we have a saved access token
        saved_token = self._load_access_token()
        if saved_token:
            try:
                self.kite.set_access_token(saved_token)
                # Verify token is still valid
                profile = self.kite.profile()
                logger.info(f"✅ Logged in as: {profile['user_name']} ({profile['user_id']})")
                self.access_token = saved_token
                self.is_connected = True
                return True
            except Exception:
                logger.warning("⚠️ Saved token expired, need fresh login")
        
        # Need fresh authentication
        if not request_token:
            login_url = self.get_login_url()
            logger.info(f"\n{'='*60}")
            logger.info("🔐 AUTHENTICATION REQUIRED")
            logger.info("="*60)
            logger.info(f"1. Open this URL in browser:\n   {login_url}")
            logger.info(f"2. Login with your Zerodha credentials")
            logger.info(f"3. Copy the 'request_token' from redirect URL")
            logger.info(f"4. Run: python main.py --token YOUR_REQUEST_TOKEN")
            logger.info("="*60 + "\n")
            
            # Try to open browser automatically
            try:
                webbrowser.open(login_url)
            except:
                pass
                
            return False
        
        try:
            # Exchange request token for access token
            data = self.kite.generate_session(
                request_token, 
                api_secret=self.api_secret
            )
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            
            # Save token for future use
            self._save_access_token(self.access_token)
            
            # Get user profile
            profile = self.kite.profile()
            logger.info(f"✅ Successfully logged in as: {profile['user_name']}")
            logger.info(f"   User ID: {profile['user_id']}")
            logger.info(f"   Email: {profile['email']}")
            
            self.is_connected = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            return False
    
    def _save_access_token(self, token: str):
        """Save access token to file for reuse (valid for one day)"""
        token_file = f".access_token_{date.today().isoformat()}"
        with open(token_file, 'w') as f:
            f.write(token)
        logger.debug(f"Access token saved to {token_file}")
    
    def _load_access_token(self) -> Optional[str]:
        """Load saved access token if exists and is from today"""
        token_file = f".access_token_{date.today().isoformat()}"
        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                return f.read().strip()
        return None
    
    # =========================================================================
    # MARKET DATA
    # =========================================================================
    
    def get_quote(self, symbols: List[str]) -> Dict:
        """
        Get current quotes for given symbols
        
        Args:
            symbols: List of symbols like ['NSE:TATAMOTORS', 'NSE:SBIN']
        """
        if not self.is_connected:
            logger.error("Not connected to Zerodha")
            return {}
            
        try:
            return self.kite.quote(symbols)
        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            return {}
    
    def get_ltp(self, symbols: List[str]) -> Dict:
        """Get Last Traded Price for symbols"""
        try:
            return self.kite.ltp(symbols)
        except Exception as e:
            logger.error(f"Failed to get LTP: {e}")
            return {}
    
    def get_ohlc(self, symbols: List[str]) -> Dict:
        """Get OHLC data for symbols"""
        try:
            return self.kite.ohlc(symbols)
        except Exception as e:
            logger.error(f"Failed to get OHLC: {e}")
            return {}
    
    def get_historical_data(
        self, 
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "15minute"
    ) -> List[Dict]:
        """
        Get historical candle data
        
        Args:
            instrument_token: Numeric token for the instrument
            from_date: Start date
            to_date: End date
            interval: minute, 3minute, 5minute, 10minute, 15minute, 
                     30minute, 60minute, day
        """
        try:
            data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                interval
            )
            return data
        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
            return []
    
    # =========================================================================
    # INSTRUMENTS
    # =========================================================================
    
    def get_instruments(self, exchange: str = "NSE") -> List[Dict]:
        """Get list of all instruments for an exchange"""
        cache_key = f"instruments_{exchange}"
        if cache_key in self._instruments_cache:
            return self._instruments_cache[cache_key]
            
        try:
            instruments = self.kite.instruments(exchange)
            self._instruments_cache[cache_key] = instruments
            return instruments
        except Exception as e:
            logger.error(f"Failed to get instruments: {e}")
            return []
    
    def get_instrument_token(self, symbol: str, exchange: str = "NSE") -> Optional[int]:
        """Get instrument token for a symbol"""
        instruments = self.get_instruments(exchange)
        for inst in instruments:
            if inst['tradingsymbol'] == symbol:
                return inst['instrument_token']
        return None
    
    # =========================================================================
    # ORDERS
    # =========================================================================
    
    def place_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,  # BUY or SELL
        quantity: int,
        order_type: str = "LIMIT",  # LIMIT, MARKET, SL, SL-M
        product: str = "MIS",  # MIS, CNC, NRML
        price: float = None,
        trigger_price: float = None,
        tag: str = None
    ) -> Optional[str]:
        """
        Place an order on Zerodha
        
        Returns:
            Order ID if successful, None otherwise
        """
        if TRADING_MODE == "paper":
            logger.info(f"📝 [PAPER] Order: {transaction_type} {quantity} {symbol} @ {price}")
            return f"PAPER_{datetime.now().timestamp()}"
        
        if not self.is_connected:
            logger.error("Not connected to Zerodha")
            return None
            
        try:
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=order_type,
                product=product,
                price=price,
                trigger_price=trigger_price,
                tag=tag
            )
            logger.info(f"✅ Order placed: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"❌ Order failed: {e}")
            return None
    
    def modify_order(
        self,
        order_id: str,
        quantity: int = None,
        price: float = None,
        trigger_price: float = None,
        order_type: str = None
    ) -> bool:
        """Modify an existing order"""
        try:
            self.kite.modify_order(
                variety=self.kite.VARIETY_REGULAR,
                order_id=order_id,
                quantity=quantity,
                price=price,
                trigger_price=trigger_price,
                order_type=order_type
            )
            logger.info(f"✅ Order modified: {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to modify order: {e}")
            return False
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self.kite.cancel_order(
                variety=self.kite.VARIETY_REGULAR,
                order_id=order_id
            )
            logger.info(f"✅ Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to cancel order: {e}")
            return False
    
    def get_orders(self) -> List[Dict]:
        """Get all orders for the day"""
        try:
            return self.kite.orders()
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    def get_order_history(self, order_id: str) -> List[Dict]:
        """Get history of a specific order"""
        try:
            return self.kite.order_history(order_id)
        except Exception as e:
            logger.error(f"Failed to get order history: {e}")
            return []
    
    # =========================================================================
    # POSITIONS & HOLDINGS
    # =========================================================================
    
    def get_positions(self) -> Dict:
        """Get current positions (day and net)"""
        try:
            return self.kite.positions()
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return {"day": [], "net": []}
    
    def get_holdings(self) -> List[Dict]:
        """Get current holdings (delivery stocks)"""
        try:
            return self.kite.holdings()
        except Exception as e:
            logger.error(f"Failed to get holdings: {e}")
            return []
    
    # =========================================================================
    # ACCOUNT
    # =========================================================================
    
    def get_margins(self) -> Dict:
        """Get account margins"""
        try:
            return self.kite.margins()
        except Exception as e:
            logger.error(f"Failed to get margins: {e}")
            return {}
    
    def get_available_margin(self, segment: str = "equity") -> float:
        """Get available margin for trading"""
        margins = self.get_margins()
        if segment in margins:
            return margins[segment].get('available', {}).get('live_balance', 0)
        return 0
    
    def get_profile(self) -> Dict:
        """Get user profile"""
        try:
            return self.kite.profile()
        except Exception as e:
            logger.error(f"Failed to get profile: {e}")
            return {}
    
    # =========================================================================
    # WEBSOCKET (Real-time data)
    # =========================================================================
    
    def start_ticker(self, tokens: List[int], on_tick_callback):
        """Start WebSocket ticker for real-time data"""
        if not self.access_token:
            logger.error("Not authenticated, cannot start ticker")
            return
            
        self.ticker = KiteTicker(self.api_key, self.access_token)
        
        def on_connect(ws, response):
            logger.info("Ticker connected, subscribing to tokens...")
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_FULL, tokens)
        
        def on_close(ws, code, reason):
            logger.warning(f"Ticker closed: {code} - {reason}")
        
        def on_error(ws, code, reason):
            logger.error(f"Ticker error: {code} - {reason}")
        
        self.ticker.on_ticks = on_tick_callback
        self.ticker.on_connect = on_connect
        self.ticker.on_close = on_close
        self.ticker.on_error = on_error
        
        self.ticker.connect(threaded=True)
        logger.info("Ticker started in background thread")
    
    def stop_ticker(self):
        """Stop WebSocket ticker"""
        if self.ticker:
            self.ticker.close()
            logger.info("Ticker stopped")


# Singleton instance
_client: Optional[ZerodhaClient] = None

def get_zerodha_client() -> ZerodhaClient:
    """Get or create Zerodha client singleton"""
    global _client
    if _client is None:
        _client = ZerodhaClient()
    return _client
