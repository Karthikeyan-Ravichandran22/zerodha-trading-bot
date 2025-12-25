# 🏆 BEST STRATEGIES - BACKTESTED & VERIFIED

This folder contains our best performing strategies that have been thoroughly backtested.

---

## 📊 GOLD 93% WIN RATE STRATEGY

**File:** `gold_93_winrate_strategy.py`

### 🎯 PERFORMANCE SUMMARY

| Metric | Value |
|--------|-------|
| **Win Rate** | 93.2% |
| **Total Profit** | Rs +3,12,847 |
| **ROI on Margin** | +508% |
| **Total Trades** | 88 |
| **Winning Trades** | 82 ✅ |
| **Losing Trades** | 6 ❌ |

---

### 💰 INVESTMENT DETAILS

| Parameter | Value |
|-----------|-------|
| **Symbol** | GOLDM (MCX Gold Mini) |
| **Lot Size** | 100 grams |
| **Price** | ~Rs 1,15,000 per 10 grams |
| **Contract Value** | ~Rs 12,30,000 |
| **Margin (5%)** | ~Rs 61,500 |
| **Brokerage** | Rs 100/trade |

---

### 📋 STRATEGY RULES

#### ENTRY CONDITIONS (All must be met):
1. **Higher TF Direction:** 5/8 candles must be RED (bearish)
2. **Lower TF Alignment:** 3/4 recent candles must be RED
3. **Indicators (3/4 must be bearish):**
   - RSI(2) < 50
   - Stochastic K < D
   - CCI(20) < 0
   - MACD < Signal line

#### EXIT (Trailing Stop):
- **Type:** Trailing Stop (NOT fixed SL)
- **Offset:** Rs 30
- **How it works:**
  1. Entry at SELL signal price
  2. Trail SL activates when price drops Rs 30 from entry
  3. Trail SL follows price down (always Rs 30 above lowest low)
  4. Exit when price bounces up Rs 30 to hit Trail SL

---

### ❌ LOSS ANALYSIS

All 6 losses were **very small** (Rs 17-99 each):

| Trade # | Entry | Exit | Points | Loss |
|---------|-------|------|--------|------|
| #21 | 1,16,089 | 1,16,086 | +2.80 | Rs -72 |
| #22 | 1,16,081 | 1,16,075 | +5.52 | Rs -45 |
| #29 | 1,16,196 | 1,16,193 | +2.80 | Rs -72 |
| #38 | 1,15,384 | 1,15,376 | +8.26 | Rs -17 |
| #71 | 1,15,821 | 1,15,813 | +8.26 | Rs -17 |
| #83 | 1,15,171 | 1,15,171 | +0.07 | Rs -99 |

**Total Loss:** Rs -322.90 (only 0.1% of gross profit!)

---

### 📈 BEST TRADES

| Trade # | Entry | Exit | Points | Profit |
|---------|-------|------|--------|--------|
| #42 | 1,15,146 | 1,14,132 | +1,014 | Rs +10,040 |
| #66 | 1,15,603 | 1,14,665 | +937 | Rs +9,274 |
| #33 | 1,15,674 | 1,14,829 | +844 | Rs +8,345 |
| #75 | 1,15,534 | 1,14,687 | +847 | Rs +8,372 |
| #62 | 1,15,764 | 1,14,955 | +809 | Rs +7,990 |

---

### 📁 FILES

| File | Description |
|------|-------------|
| `gold_93_winrate_strategy.py` | Main strategy with backtest |
| `gold_93_winrate_trades.json` | All 88 trades in JSON format |

---

### 🚀 USAGE

```python
# Run backtest
python best_strategies/gold_93_winrate_strategy.py

# Import for live trading
from best_strategies.gold_93_winrate_strategy import run_backtest
```

---

### ⚠️ IMPORTANT NOTES

1. **SELL Only Strategy** - Works best in bearish/falling markets
2. **Market Hours:** MCX Gold trades 9:00 AM - 11:30 PM (Mon-Fri)
3. **MCX Subscription Required** - Need MCX data access in Angel One
4. **Trailing Stop** - No fixed SL, uses dynamic trailing stop
5. **Backtest Period** - Last 1 month data used

---

## 📊 STRATEGY COMPARISON

| Strategy | Win Rate | Profit | ROI | Status |
|----------|----------|--------|-----|--------|
| **Gold 93% WR** | 93.2% | Rs +3,12,847 | +508% | ✅ BEST |
| ORB Equity (77%) | 77% | Rs -960 | -9.6% | ⚠️ Needs work |
| VWAP Bounce | 60% | Break-even | ~0% | ⚠️ Needs work |

---

*Last Updated: 25-Dec-2024*
