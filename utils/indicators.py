"""
Technical Indicators - Calculate indicators for strategy analysis
All indicators use pandas for efficiency
"""

import pandas as pd
import numpy as np
from typing import Optional


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average"""
    return series.rolling(window=period).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index
    
    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_vwap(data: pd.DataFrame) -> pd.Series:
    """
    Volume Weighted Average Price
    
    VWAP = Cumulative(Typical Price * Volume) / Cumulative(Volume)
    Typical Price = (High + Low + Close) / 3
    """
    typical_price = (data['high'] + data['low'] + data['close']) / 3
    vwap = (typical_price * data['volume']).cumsum() / data['volume'].cumsum()
    return vwap


def calculate_supertrend(
    data: pd.DataFrame, 
    period: int = 10, 
    multiplier: float = 3.0
) -> pd.DataFrame:
    """
    Supertrend Indicator
    
    Returns DataFrame with 'supertrend' and 'direction' columns
    direction: 1 = bullish (green), -1 = bearish (red)
    """
    df = data.copy()
    
    # Calculate ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    
    # Calculate basic bands
    hl2 = (df['high'] + df['low']) / 2
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    
    # Initialize supertrend
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)
    
    supertrend.iloc[0] = upper_band.iloc[0]
    direction.iloc[0] = 1
    
    for i in range(1, len(df)):
        if df['close'].iloc[i] > supertrend.iloc[i-1]:
            supertrend.iloc[i] = lower_band.iloc[i]
            direction.iloc[i] = 1
        else:
            supertrend.iloc[i] = upper_band.iloc[i]
            direction.iloc[i] = -1
        
        # Adjust bands based on previous values
        if direction.iloc[i] == 1:
            if lower_band.iloc[i] < supertrend.iloc[i-1] and direction.iloc[i-1] == 1:
                supertrend.iloc[i] = supertrend.iloc[i-1]
        else:
            if upper_band.iloc[i] > supertrend.iloc[i-1] and direction.iloc[i-1] == -1:
                supertrend.iloc[i] = supertrend.iloc[i-1]
    
    return pd.DataFrame({
        'supertrend': supertrend,
        'direction': direction
    })


def calculate_macd(
    series: pd.Series, 
    fast: int = 12, 
    slow: int = 26, 
    signal: int = 9
) -> pd.DataFrame:
    """
    MACD - Moving Average Convergence Divergence
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return pd.DataFrame({
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    })


def calculate_bollinger_bands(
    series: pd.Series, 
    period: int = 20, 
    std_dev: float = 2.0
) -> pd.DataFrame:
    """
    Bollinger Bands
    """
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    
    upper_band = sma + (std_dev * std)
    lower_band = sma - (std_dev * std)
    
    return pd.DataFrame({
        'middle': sma,
        'upper': upper_band,
        'lower': lower_band,
        'bandwidth': (upper_band - lower_band) / sma * 100
    })


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range
    """
    high_low = data['high'] - data['low']
    high_close = abs(data['high'] - data['close'].shift())
    low_close = abs(data['low'] - data['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def detect_support_resistance(
    data: pd.DataFrame, 
    window: int = 20, 
    num_levels: int = 3
) -> dict:
    """
    Detect support and resistance levels
    """
    highs = data['high'].rolling(window=window, center=True).max()
    lows = data['low'].rolling(window=window, center=True).min()
    
    resistance_levels = data.loc[data['high'] == highs, 'high'].drop_duplicates().nlargest(num_levels)
    support_levels = data.loc[data['low'] == lows, 'low'].drop_duplicates().nsmallest(num_levels)
    
    return {
        'resistance': resistance_levels.tolist(),
        'support': support_levels.tolist()
    }
