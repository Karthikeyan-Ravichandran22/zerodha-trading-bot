"""
Angel One SmartAPI Client
Supports both session-based and TOTP-based authentication
"""

import os
import pyotp
from datetime import datetime
from typing import Optional, Dict
from loguru import logger

try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None
    logger.warning("SmartApi not installed. Run: pip install smartapi-python")


class AngelOneClient:
    """Client for Angel One SmartAPI"""
    
    def __init__(self):
        self.api_key = os.getenv('ANGEL_API_KEY', '')
        self.secret_key = os.getenv('ANGEL_SECRET_KEY', '')
        self.client_id = os.getenv('ANGEL_CLIENT_ID', '')
        self.mpin = os.getenv('ANGEL_MPIN', '')
        self.totp_secret = os.getenv('ANGEL_TOTP_SECRET', '')  # Optional
        
        self.smart_api = None
        self.auth_token = None
        self.refresh_token = None
        self.is_authenticated = False
        
    def initialize(self):
        """Initialize the SmartAPI client"""
        if not SmartConnect:
            logger.error("SmartApi not installed!")
            return False
            
        if not self.api_key:
            logger.warning("ANGEL_API_KEY not set")
            return False
            
        try:
            self.smart_api = SmartConnect(api_key=self.api_key)
            logger.info("✅ Angel One client initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Angel One: {e}")
            return False
    
    def generate_totp(self) -> Optional[str]:
        """Generate TOTP if secret is available"""
        if self.totp_secret:
            try:
                totp = pyotp.TOTP(self.totp_secret)
                return totp.now()
            except Exception as e:
                logger.error(f"Failed to generate TOTP: {e}")
        return None
    
    def authenticate(self, otp: Optional[str] = None) -> bool:
        """
        Authenticate with Angel One.
        If TOTP secret is available, auto-generates OTP.
        Otherwise uses provided OTP.
        """
        if not self.smart_api:
            logger.error("Client not initialized")
            return False
        
        try:
            # Try to generate TOTP if available
            if not otp and self.totp_secret:
                otp = self.generate_totp()
                logger.info("🔐 Using auto-generated TOTP")
            
            if not otp:
                logger.error("OTP required but not provided and TOTP secret not available")
                return False
            
            # Login with Angel One
            data = self.smart_api.generateSession(
                clientCode=self.client_id,
                password=self.mpin,
                totp=otp
            )
            
            if data.get('status'):
                self.auth_token = data['data']['jwtToken']
                self.refresh_token = data['data']['refreshToken']
                self.is_authenticated = True
                
                # Get profile
                profile = self.smart_api.getProfile(self.refresh_token)
                user_name = profile.get('data', {}).get('name', 'Unknown')
                
                logger.info(f"✅ Angel One authenticated: {user_name}")
                return True
            else:
                logger.error(f"Authentication failed: {data.get('message')}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def get_margins(self) -> Optional[Dict]:
        """Get account margins/funds"""
        if not self.is_authenticated:
            return None
            
        try:
            margins = self.smart_api.rmsLimit()
            if margins.get('status'):
                data = margins.get('data', {})
                return {
                    'available': float(data.get('net', 0)),
                    'used': float(data.get('utilised', {}).get('exposure', 0)),
                    'total': float(data.get('availablecash', 0))
                }
        except Exception as e:
            logger.error(f"Failed to get margins: {e}")
        return None
    
    def place_order(self, symbol: str, transaction_type: str, quantity: int,
                   order_type: str = "MARKET", price: float = 0,
                   trigger_price: float = 0, product: str = "INTRADAY") -> Optional[str]:
        """
        Place an order on Angel One.
        
        Args:
            symbol: Trading symbol (e.g., "SBIN-EQ")
            transaction_type: "BUY" or "SELL"
            quantity: Number of shares
            order_type: "MARKET", "LIMIT", "STOPLOSS_LIMIT", "STOPLOSS_MARKET"
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for SL orders)
            product: "INTRADAY" or "DELIVERY"
        """
        if not self.is_authenticated:
            logger.error("Not authenticated")
            return None
        
        try:
            # Get token for the symbol
            token = self._get_symbol_token(symbol)
            if not token:
                logger.error(f"Could not find token for {symbol}")
                return None
            
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": transaction_type,
                "exchange": "NSE",
                "ordertype": order_type,
                "producttype": product,
                "duration": "DAY",
                "quantity": quantity
            }
            
            if order_type in ["LIMIT", "STOPLOSS_LIMIT"]:
                order_params["price"] = price
            
            if order_type in ["STOPLOSS_LIMIT", "STOPLOSS_MARKET"]:
                order_params["triggerprice"] = trigger_price
            
            response = self.smart_api.placeOrder(order_params)
            
            if response.get('status'):
                order_id = response['data']['orderid']
                logger.info(f"✅ Order placed: {order_id}")
                return order_id
            else:
                logger.error(f"Order failed: {response.get('message')}")
                return None
                
        except Exception as e:
            logger.error(f"Order error: {e}")
            return None
    
    def _get_symbol_token(self, symbol: str) -> Optional[str]:
        """Get token for a trading symbol"""
        # Common NSE symbol tokens (add more as needed)
        symbol_tokens = {
            "SBIN-EQ": "3045",
            "RELIANCE-EQ": "2885",
            "INFY-EQ": "1594",
            "TCS-EQ": "11536",
            "HDFCBANK-EQ": "1333",
            "ICICIBANK-EQ": "4963",
            "KOTAKBANK-EQ": "1922",
            "LT-EQ": "11483",
            "TATAMOTORS-EQ": "3456",
            "TATASTEEL-EQ": "3499",
            "SAIL-EQ": "2963",
            "PNB-EQ": "10666",
            "IRFC-EQ": "3041",
            "IDEA-EQ": "14366",
            "CANBK-EQ": "10794",
            "IDFCFIRSTB-EQ": "11184"
        }
        
        # Try exact match
        if symbol in symbol_tokens:
            return symbol_tokens[symbol]
        
        # Try without -EQ suffix
        symbol_eq = f"{symbol}-EQ"
        if symbol_eq in symbol_tokens:
            return symbol_tokens[symbol_eq]
        
        return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if not self.is_authenticated:
            return False
            
        try:
            response = self.smart_api.cancelOrder(order_id, "NORMAL")
            return response.get('status', False)
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            return False
    
    def get_positions(self) -> list:
        """Get current positions"""
        if not self.is_authenticated:
            return []
            
        try:
            response = self.smart_api.position()
            if response.get('status'):
                return response.get('data', [])
        except Exception as e:
            logger.error(f"Get positions error: {e}")
        return []
    
    def get_orders(self) -> list:
        """Get today's orders"""
        if not self.is_authenticated:
            return []
            
        try:
            response = self.smart_api.orderBook()
            if response.get('status'):
                return response.get('data', [])
        except Exception as e:
            logger.error(f"Get orders error: {e}")
        return []


def get_angel_client() -> AngelOneClient:
    """Factory function to get Angel One client"""
    return AngelOneClient()
