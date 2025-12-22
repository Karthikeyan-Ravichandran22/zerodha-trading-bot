"""
Data Fetcher - Fetches and prepares market data for analysis
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from loguru import logger


class DataFetcher:
    """Fetches market data from Zerodha or backup sources"""
    
    def __init__(self, zerodha_client=None):
        self.client = zerodha_client
        self._cache: Dict[str, pd.DataFrame] = {}
    
    def get_ohlc_data(
        self,
        symbol: str,
        interval: str = "15minute",
        days: int = 5
    ) -> Optional[pd.DataFrame]:
        """
        Get OHLC candle data for a symbol
        
        Args:
            symbol: Stock symbol (e.g., 'TATAMOTORS')
            interval: minute, 5minute, 15minute, 30minute, 60minute, day
            days: Number of days of data
        """
        cache_key = f"{symbol}_{interval}_{days}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if self.client and self.client.is_connected:
            token = self.client.get_instrument_token(symbol, "NSE")
            if token:
                to_date = datetime.now()
                from_date = to_date - timedelta(days=days)
                data = self.client.get_historical_data(
                    token, from_date, to_date, interval
                )
                if data:
                    df = pd.DataFrame(data)
                    df.set_index('date', inplace=True)
                    self._cache[cache_key] = df
                    return df
        
        # Fallback: Use yfinance for historical data
        try:
            import yfinance as yf
            ticker = yf.Ticker(f"{symbol}.NS")
            df = ticker.history(period=f"{days}d", interval=self._convert_interval(interval))
            if not df.empty:
                df.columns = [c.lower() for c in df.columns]
                self._cache[cache_key] = df
                return df
        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
        
        return None
    
    def _convert_interval(self, interval: str) -> str:
        """Convert Zerodha interval to yfinance interval"""
        mapping = {
            "minute": "1m", "5minute": "5m", "15minute": "15m",
            "30minute": "30m", "60minute": "1h", "day": "1d"
        }
        return mapping.get(interval, "15m")
    
    def get_live_quote(self, symbols: List[str]) -> Dict:
        """Get live quotes for symbols"""
        if self.client and self.client.is_connected:
            formatted = [f"NSE:{s}" for s in symbols]
            return self.client.get_quote(formatted)
        return {}
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """Get last traded price"""
        quote = self.get_live_quote([symbol])
        key = f"NSE:{symbol}"
        if key in quote:
            return quote[key].get('last_price')
        return None
    
    def get_vwap(self, symbol: str) -> Optional[float]:
        """Get VWAP for symbol (from quote)"""
        quote = self.get_live_quote([symbol])
        key = f"NSE:{symbol}"
        if key in quote and 'ohlc' in quote[key]:
            ohlc = quote[key]['ohlc']
            # Approximate VWAP
            return (ohlc['high'] + ohlc['low'] + ohlc['close']) / 3
        return None
    
    def clear_cache(self):
        """Clear data cache"""
        self._cache.clear()
