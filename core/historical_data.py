"""
Angel One Historical Data Client

Uses the Historical Data API to fetch OHLC candle data
for indicator calculations and strategy analysis
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
import pandas as pd
import os
import logging
import pyotp

from SmartApi import SmartConnect

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


class HistoricalDataClient:
    """
    Client for fetching historical OHLC data from Angel One
    Uses the Historical Data API credentials
    """
    
    # Interval mappings for Angel One API
    INTERVALS = {
        '1m': 'ONE_MINUTE',
        '3m': 'THREE_MINUTE',
        '5m': 'FIVE_MINUTE',
        '10m': 'TEN_MINUTE',
        '15m': 'FIFTEEN_MINUTE',
        '30m': 'THIRTY_MINUTE',
        '1h': 'ONE_HOUR',
        '1d': 'ONE_DAY'
    }
    
    def __init__(self):
        # Use Historical Data API credentials
        self.api_key = os.getenv('ANGEL_HIST_API_KEY')
        self.secret_key = os.getenv('ANGEL_HIST_SECRET_KEY')
        
        # Common authentication details (same for all APIs)
        self.client_id = os.getenv('ANGEL_CLIENT_ID')
        self.mpin = os.getenv('ANGEL_MPIN')
        self.totp_secret = os.getenv('ANGEL_TOTP_SECRET')
        
        self.smart_api: Optional[SmartConnect] = None
        self.is_authenticated = False
        
        # Symbol token cache
        self._symbol_cache: Dict[str, str] = {}
        
        logger.info("📊 Historical Data Client initialized")
    
    def authenticate(self) -> bool:
        """Authenticate with Angel One Historical Data API"""
        try:
            if not self.api_key:
                logger.warning("⚠️ Historical API key not configured, using Trading API")
                # Fallback to trading API key
                self.api_key = os.getenv('ANGEL_API_KEY')
                self.secret_key = os.getenv('ANGEL_SECRET_KEY')
            
            if not all([self.api_key, self.client_id, self.mpin, self.totp_secret]):
                logger.error("❌ Missing credentials for Historical Data API")
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
                self.is_authenticated = True
                logger.info("✅ Historical Data API authenticated")
                return True
            else:
                logger.error(f"❌ Historical Auth failed: {data.get('message')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Historical Auth error: {e}")
            return False
    
    def get_candles(
        self,
        symbol: str,
        interval: str = '5m',
        days: int = 5,
        exchange: str = 'NSE'
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical OHLC candle data
        
        Args:
            symbol: Stock symbol (e.g., 'PNB', 'SAIL')
            interval: Candle interval ('1m', '5m', '15m', '1h', '1d')
            days: Number of days of data to fetch
            exchange: Exchange ('NSE', 'BSE')
            
        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
        """
        if not self.is_authenticated:
            if not self.authenticate():
                return None
        
        try:
            # Get symbol token
            symbol_token = self._get_symbol_token(symbol, exchange)
            if not symbol_token:
                logger.error(f"❌ Symbol token not found: {symbol}")
                return None
            
            # Calculate date range
            to_date = datetime.now(IST)
            from_date = to_date - timedelta(days=days)
            
            # Format dates for API
            from_str = from_date.strftime('%Y-%m-%d %H:%M')
            to_str = to_date.strftime('%Y-%m-%d %H:%M')
            
            # Get interval code
            interval_code = self.INTERVALS.get(interval, 'FIVE_MINUTE')
            
            # Fetch historical data
            params = {
                "exchange": exchange,
                "symboltoken": symbol_token,
                "interval": interval_code,
                "fromdate": from_str,
                "todate": to_str
            }
            
            response = self.smart_api.getCandleData(params)
            
            if response.get('status') and response.get('data'):
                # Convert to DataFrame
                data = response['data']
                df = pd.DataFrame(data, columns=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume'])
                
                # Parse datetime
                df['Datetime'] = pd.to_datetime(df['Datetime'])
                df.set_index('Datetime', inplace=True)
                
                # Ensure numeric types
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Add lowercase aliases for strategy compatibility
                df['open'] = df['Open']
                df['high'] = df['High']
                df['low'] = df['Low']
                df['close'] = df['Close']
                df['volume'] = df['Volume']
                
                logger.debug(f"📊 Fetched {len(df)} candles for {symbol} ({interval})")
                return df
            else:
                logger.warning(f"⚠️ No data for {symbol}: {response.get('message', 'Unknown')}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching candles for {symbol}: {e}")
            return None
    
    def _get_symbol_token(self, symbol: str, exchange: str = 'NSE') -> Optional[str]:
        """Get symbol token for a stock"""
        # Check cache first
        cache_key = f"{exchange}:{symbol}"
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key]
        
        # Common NSE stock tokens
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
            'ICICIBANK': '4963',
            'HDFCBANK': '1333',
            'INFY': '1594',
            'TCS': '11536',
            'ITC': '1660',
            'BANKBARODA': '4668',
            'CANBK': '10794',
            'IOC': '1624',
            'ONGC': '2475',
            'NTPC': '11630',
            'POWERGRID': '14977',
            'COALINDIA': '20374',
            'GAIL': '4717',
            'VEDL': '3063',
            'HINDALCO': '1363',
            'JSWSTEEL': '11723',
            'NMDC': '15332',
            'ADANIENT': '25',
            'ADANIPORTS': '15083',
            # MCX Commodities
            'GOLD': '66241',
            'GOLDM': '66243',
            'SILVER': '66247',
            'SILVERM': '66249',
            'CRUDEOIL': '66277',
            'NATURALGAS': '66283'
        }
        
        token = NSE_TOKENS.get(symbol.upper())
        if token:
            self._symbol_cache[cache_key] = token
        
        return token
    
    def get_ltp(self, symbol: str, exchange: str = 'NSE') -> Optional[float]:
        """Get Last Traded Price for a symbol"""
        if not self.is_authenticated:
            if not self.authenticate():
                return None
        
        try:
            symbol_token = self._get_symbol_token(symbol, exchange)
            if not symbol_token:
                return None
            
            response = self.smart_api.ltpData(exchange, symbol, symbol_token)
            
            if response.get('status') and response.get('data'):
                return float(response['data'].get('ltp', 0))
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting LTP for {symbol}: {e}")
            return None
    
    def get_market_depth(self, symbol: str, exchange: str = 'NSE') -> Optional[dict]:
        """Get market depth (order book) for a symbol"""
        if not self.is_authenticated:
            if not self.authenticate():
                return None
        
        try:
            symbol_token = self._get_symbol_token(symbol, exchange)
            if not symbol_token:
                return None
            
            response = self.smart_api.getMarketData(
                mode="FULL",
                exchangeTokens={exchange: [symbol_token]}
            )
            
            if response.get('status') and response.get('data'):
                return response['data']
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting market depth for {symbol}: {e}")
            return None


# Global historical data client instance
historical_client = HistoricalDataClient()
