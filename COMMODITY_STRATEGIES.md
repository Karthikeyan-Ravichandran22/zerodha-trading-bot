# 🏆 Commodity Trading Strategies for MCX

## Overview

This module contains trading strategies optimized for MCX commodities:
- **Gold (GOLDM)** - Gold Mini futures
- **Silver (SILVERM)** - Silver Mini futures  
- **Crude Oil (CRUDEOIL)** - Crude Oil futures

**Broker Integration:** Angel One (SmartAPI) - Auto-login with TOTP

---

## 💰 Balance-Based Trading

The commodity scanner automatically checks your **Angel One balance** before generating signals:

```python
from strategies import create_scanner_with_angel

# Initialize scanner with Angel One (auto-authenticates)
scanner = create_scanner_with_angel()

# Check which commodities you can trade
status = scanner.get_balance_status()
print(f"Available: ₹{status['available_balance']:,.2f}")
print(f"Tradeable: {status['tradeable_commodities']}")
```

### Margin Requirements:
| Commodity | Margin Required |
|-----------|-----------------|
| Gold Mini | ₹40,000 |
| Silver Mini | ₹30,000 |
| Crude Oil | ₹25,000 |

**Note:** Only commodities with sufficient balance will be scanned.

---

### Entry Rules
- **BUY**: 
  - EMA9 crosses above EMA21
  - Price above EMA50 (major uptrend)
  - RSI in 40-65 zone
  - Volume > 1.2x average (preferred)

- **SELL**:
  - EMA9 crosses below EMA21
  - Price below EMA50 (major downtrend)
  - RSI in 35-60 zone
  - Volume > 1.2x average (preferred)

### Why It Works
Silver is more volatile than gold. The wider parameters and volume confirmation help filter out fake moves.

---

## 🛢️ Crude Oil Strategy (`crude_oil_strategy.py`)

### Strategy Type: Dual Strategy - Breakout + Trend Following

This strategy combines two approaches:

### Strategy 1: Camarilla Pivot Breakout

| Level | Usage |
|-------|-------|
| H4 | Breakout Long level |
| H3 | Resistance / Short entry |
| L3 | Support / Long entry |
| L4 | Breakout Short level |

**Entry Rules:**
- **LONG Breakout**: Price > H4 + Volume spike + Supertrend bullish
- **SHORT Breakout**: Price < L4 + Volume spike + Supertrend bearish

### Strategy 2: Trend Following

| Parameter | Value |
|-----------|-------|
| EMA Fast | 20 |
| EMA Slow | 50 |
| Supertrend Period | 10 |
| Supertrend Multiplier | 3 |

**Entry Rules:**
- **BUY**: EMA20 crosses above EMA50 OR Supertrend turns bullish
- **SELL**: EMA20 crosses below EMA50 OR Supertrend turns bearish

### Risk Management

| Parameter | Value |
|-----------|-------|
| Stop Loss | 0.8% |
| Target 1 (Partial) | 0.6% |
| Target 2 (Full) | 1.2% |
| Volume Spike | 1.5x average |

### Why It Works
Crude oil shows strong trending behavior. The combination of breakout and trend strategies captures both momentum moves and sustained trends.

---

## 📊 Commodity Scanner (`commodity_scanner.py`)

The unified scanner scans all three commodities simultaneously:

```python
from strategies import commodity_scanner

# Scan all commodities
signals = commodity_scanner.scan_all()

# Get market overview
overview = commodity_scanner.get_market_overview()

# Get combined stats
stats = commodity_scanner.get_combined_stats()
```

---

## ⏰ Trading Hours (MCX)

| Commodity | Trading Hours (IST) |
|-----------|---------------------|
| Gold | 9:00 AM - 11:30 PM |
| Silver | 9:00 AM - 11:30 PM |
| Crude Oil | 9:00 AM - 11:30 PM |

---

## 💰 Margin Requirements (Approximate)

| Commodity | Contract | Lot Size | Approx Margin |
|-----------|----------|----------|---------------|
| Gold Mini | GOLDM | 100 grams | ₹35,000-40,000 |
| Silver Mini | SILVERM | 5 kg | ₹25,000-30,000 |
| Crude Oil | CRUDEOIL | 100 barrels | ₹20,000-25,000 |

*Margins vary based on volatility and broker policies*

---

## 🚨 Risk Management Tips

1. **Never trade without stop-loss** - Commodities can gap violently
2. **Position sizing** - Risk max 2% of capital per trade
3. **Avoid news events** - Fed meetings, inventory reports, geopolitical events
4. **Watch for expiry** - Rollover before contract expiry
5. **Monitor global markets** - Crude follows WTI, Gold follows COMEX

---

## 📈 Usage Example

```python
from strategies import gold_strategy, silver_strategy, crude_strategy

# Individual signals
gold_signal = gold_strategy.generate_signal()
silver_signal = silver_strategy.generate_signal()
crude_signal = crude_strategy.generate_signal()

# Paper trade recording
if gold_signal:
    gold_strategy.record_paper_trade(gold_signal)

# Get stats
print(gold_strategy.get_paper_stats())
print(silver_strategy.get_paper_stats())
print(crude_strategy.get_stats())
```

---

## 🔄 Integration with Main Bot

The commodity strategies can be integrated into the main trading bot by:

1. Adding commodity symbols to the watchlist
2. Using the commodity scanner in the main loop
3. Implementing MCX-specific order logic (different exchange)

Note: Currently these use Yahoo Finance for data. For live MCX trading, you'll need to subscribe to MCX data feed through Zerodha.
