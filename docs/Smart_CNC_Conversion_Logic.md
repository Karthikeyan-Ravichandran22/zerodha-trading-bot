# 🔄 Smart CNC Conversion Logic Explained

## What is MIS vs CNC?

| Type | Full Name | Meaning | Auto Square-off |
|------|-----------|---------|-----------------|
| **MIS** | Margin Intraday Square-off | Intraday position | ✅ Yes, at 3:20 PM |
| **CNC** | Cash & Carry | Delivery position | ❌ No, holds overnight |

---

## When Does Conversion Run?

The bot checks for CNC conversion at **2:30 PM** and **3:00 PM** (before market close).

```
┌────────────────────────────────────────────────────────────────┐
│  9:45 ──► Trading ──► 14:15 ──► 14:30 ──► 15:00 ──► 15:30     │
│                          │        │         │          │       │
│                     No new      CNC       CNC      Market      │
│                     trades    Check 1   Check 2    Close       │
│                                  ↓         ↓                   │
│                            Convert?   Convert?                 │
└────────────────────────────────────────────────────────────────┘
```

---

## 📋 The Decision Logic (3 Conditions)

### Condition 1: Is position in PROFIT?

```
Current P&L = (LTP - Entry Price) × Quantity

Example: BPCL
  Entry: ₹364.75
  LTP:   ₹366.50
  Qty:   27
  P&L:   (366.50 - 364.75) × 27 = ₹47.25

  Current P&L > 0?  → ₹47.25 > 0?  → ✅ YES, in profit!

  If NO → Skip this position (don't convert losing positions)
```

### Condition 2: Potential additional profit > ₹100?

Why ₹100? Because CNC has extra costs (~₹40-50 per trade).

```
Potential Profit = (Target - LTP) × Quantity

Example: BPCL
  Target: ₹375.69
  LTP:    ₹366.50
  Qty:    27
  Potential = (375.69 - 366.50) × 27 = ₹248.13

  ₹248.13 > ₹100?  → ✅ YES, worth the extra CNC cost!

  If < ₹100 → Skip (not worth paying extra charges)
```

### Condition 3: Distance to target > 0.5%?

If we're almost at target, no point converting!

```
Distance = ((Target - LTP) / LTP) × 100

Example: BPCL
  Target: ₹375.69
  LTP:    ₹366.50
  Distance = ((375.69 - 366.50) / 366.50) × 100 = 2.5%

  2.5% > 0.5%?  → ✅ YES, still room to grow!

  If < 0.5% → Skip (too close to target, MIS will hit it today)
```

---

## 📊 Visual Decision Tree

```
                    ┌──────────────────┐
                    │  MIS Position    │
                    │  (e.g., BPCL)    │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Is it in PROFIT? │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              │ NO                          │ YES
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │ ❌ SKIP         │           │ Potential > ₹100│
    │ Don't convert   │           │ to target?      │
    │ losing position │           └────────┬────────┘
    └─────────────────┘                    │
                              ┌────────────┴────────────┐
                              │ NO                      │ YES
                              ▼                         ▼
                    ┌─────────────────┐       ┌─────────────────┐
                    │ ❌ SKIP         │       │ Distance > 0.5%?│
                    │ Not worth cost  │       └────────┬────────┘
                    └─────────────────┘                │
                                          ┌────────────┴────────────┐
                                          │ NO                      │ YES
                                          ▼                         ▼
                                ┌─────────────────┐       ┌─────────────────┐
                                │ ❌ SKIP         │       │ ✅ CONVERT!     │
                                │ Too close       │       │ MIS → CNC       │
                                └─────────────────┘       │ Hold overnight  │
                                                          └─────────────────┘
```

---

## 💰 Real Example Scenarios

### Scenario A: Convert ✅

```
BPCL @ 2:30 PM:
  Entry:     ₹364.75
  LTP:       ₹368.00 (+0.9%)
  Target:    ₹375.69
  Qty:       27

  Current P&L:      ₹87.75    → In profit ✅
  Potential Extra:  ₹207.63   → > ₹100 ✅
  Distance:         2.1%      → > 0.5% ✅

  Decision: CONVERT TO CNC! 🔄
```

### Scenario B: Skip - Not In Profit ❌

```
SAIL @ 2:30 PM:
  Entry:     ₹132.19
  LTP:       ₹131.50 (-0.5%)
  Target:    ₹136.15
  Qty:       75

  Current P&L:      -₹51.75   → LOSS ❌

  Decision: SKIP (Converting a losing position is bad!)
```

### Scenario C: Skip - Too Close to Target ❌

```
HDFC @ 2:30 PM:
  Entry:     ₹1,680
  LTP:       ₹1,725 (+2.7%)
  Target:    ₹1,730
  Qty:       5

  Current P&L:      ₹225      → In profit ✅
  Potential Extra:  ₹25       → < ₹100 ❌

  Decision: SKIP (Only ₹25 more to gain, not worth CNC cost)
```

### Scenario D: Skip - Already Near Target ❌

```
TATAMOTORS @ 3:00 PM:
  Entry:     ₹780.00
  LTP:       ₹800.00 (+2.5%)
  Target:    ₹803.00
  Qty:       12

  Current P&L:      ₹240      → In profit ✅
  Potential Extra:  ₹36       → < ₹100 ❌
  Distance:         0.37%     → < 0.5% ❌

  Decision: SKIP (Too close to target, will hit today)
```

---

## 🔧 Angel One API Call

When all conditions are met, the bot calls:

```python
convert_params = {
    "exchange": "NSE",
    "symboltoken": "526",
    "producttype": "DELIVERY",      # CNC in Angel One terminology
    "newproducttype": "DELIVERY",
    "tradingsymbol": "BPCL-EQ",
    "transactiontype": "BUY",
    "quantity": 27,
    "type": "DAY"
}

response = angel_client.convertPosition(convert_params)
```

---

## 📤 After Conversion

When converted to CNC:

| Action | Status |
|--------|--------|
| Position holds overnight | ✅ Yes |
| No forced square-off at 3:20 PM | ✅ Yes |
| Target order remains active | ✅ Yes |
| Stop-loss order | ⚠️ Needs re-placement next day |
| Telegram notification | ✅ Sent |
| Database updated | ✅ product_type = 'CNC' |

---

## 💵 CNC Extra Costs

Converting MIS to CNC incurs additional charges:

| Charge Type | MIS | CNC | Difference |
|-------------|-----|-----|------------|
| Brokerage | ₹20 | ₹20 | ₹0 |
| STT | 0.025% (sell) | 0.1% (buy+sell) | ~₹35 |
| DP Charges | ₹0 | ₹15-20 | ~₹18 |
| **Total Extra** | - | - | **~₹40-50** |

**That's why we require potential profit > ₹100** - to cover these extra costs and still make profit!

---

## 📝 Summary Table

| Condition | Check | Why |
|-----------|-------|-----|
| **In Profit** | P&L > 0 | Don't hold losers overnight |
| **Potential > ₹100** | (Target - LTP) × Qty > 100 | Cover extra CNC charges |
| **Distance > 0.5%** | Still room to grow | Don't convert if target is near |

---

## 🎯 When is CNC Conversion Beneficial?

| Situation | Convert? | Reason |
|-----------|----------|--------|
| Stock is in strong uptrend | ✅ Yes | Will likely continue next day |
| Market is bullish overall | ✅ Yes | Favorable conditions |
| Stock consolidated near target | ❌ No | Might hit target today |
| Stock is losing | ❌ No | Don't carry losses overnight |
| Potential gain < ₹100 | ❌ No | Not worth the extra cost |

---

## 🔔 Telegram Notification Example

When a position is converted, you receive:

```
🔄 POSITION CONVERTED TO CNC

📈 BPCL
Qty: 27 shares
Entry: ₹364.75
LTP: ₹368.00
Target: ₹375.69

💰 Current Profit: ₹87.75
🎯 Potential Extra: ₹207.63

⏰ Will hold overnight for target
```

---

*Last Updated: December 27, 2025*
