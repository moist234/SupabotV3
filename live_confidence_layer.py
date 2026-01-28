"""
Live Confidence Score Layer for Supabot V4

Adds adaptive confidence scoring WITHOUT changing V4 weights.
Adjusts for regime, feature interactions, and recent drift.

Usage: python3 live_confidence_layer.py
"""
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION - EDIT THESE CONSTANTS TO TUNE
# ============================================================================

# Base confidence by V4 score
CONFIDENCE_MAP = {
    (0, 100): 45,
    (100, 110): 55,
    (110, 120): 62,
    (120, 130): 70,
    (130, 200): 75
}

# Institutional adjustments
INST_LOW_BONUS = 5          # inst <30% + Mid/Large cap
INST_HIGH_RISK_ON = -8      # Risk-On + inst >80%
INST_VERY_HIGH_RISK_ON = -12  # Risk-On + inst >90%

# Relative Fresh
REL_FRESH_FAIL = -20        # ≤1.0% (should be filtered but penalty if present)
REL_FRESH_STRONG = 6        # ≥2.0%

# Fresh toxic zone
FRESH_TOXIC = -10           # 3.0-4.0%

# Market cap
SMALL_CAP_PENALTY = -15
MEGA_CAP_PENALTY = -5

# Earnings
EARNINGS_SWEET_SPOT = 4     # 30-60d
EARNINGS_POST_PENALTY = -3  # <30d after earnings

# SI
SI_ELITE_BONUS = 5          # 0-1%
SI_HIGH_PENALTY = -6        # 10-15%
SI_VERY_HIGH_PENALTY = -10  # ≥15%

# Technicals
RSI_OVERBOUGHT = -4         # >70
VOL_WEAK_PENALTY = -2       # 1.0-1.5x

# Drift protection
DRIFT_LAST20_NEG_AVG = -8   # Last 20 avg <0
DRIFT_LAST20_WR_WEAK = -6   # Last 20 WR below historical
DRIFT_LAST50_NEG_AVG = -5   # Last 50 avg <0

# Action thresholds
ACTION_FULL = 70
ACTION_HALF = 60
ACTION_SMALL = 50

# Regime detection
VIX_RISK_OFF = 20
VIX_HIGH_VOL = 25
VIX_SPIKE_THRESHOLD = 15    # % change over 5d
SPY_SMA_WINDOW = 20

# ============================================================================
# REGIME DETECTION
# ============================================================================

def compute_regime(date=None):
    """
    Detect market regime using SPY/VIX (no ML, simple rules).
    
    Returns: 'Risk-On', 'Risk-Off', 'HighVol', 'Chop', or 'Unknown'
    """
    if date is None:
        date = datetime.now()
    
    # Download data
    end_date = date + timedelta(days=1)
    start_date = date - timedelta(days=60)
    
    try:
        spy = yf.download('SPY', start=start_date, end=end_date, progress=False)
        vix = yf.download('^VIX', start=start_date, end=end_date, progress=False)
        
        if len(spy) == 0 or len(vix) == 0:
            return 'Unknown'
        
        # Get latest values
        spy_price = spy['Close'].iloc[-1]
        spy_sma20 = spy['Close'].rolling(SPY_SMA_WINDOW).mean().iloc[-1]
        vix_level = vix['Close'].iloc[-1]
        
        # VIX 5d change
        if len(vix) >= 5:
            vix_5d_ago = vix['Close'].iloc[-5]
            vix_change = ((vix_level - vix_5d_ago) / vix_5d_ago) * 100
        else:
            vix_change = 0
        
        # Regime classification
        if vix_level > VIX_HIGH_VOL or vix_change > VIX_SPIKE_THRESHOLD:
            return 'HighVol'
        elif spy_price < spy_sma20 or vix_level > VIX_RISK_OFF:
            return 'Risk-Off'
        elif abs(spy_price - spy_sma20) / spy_sma20 < 0.005:  # Within 0.5%
            return 'Chop'
        else:
            return 'Risk-On'
    
    except Exception as e:
        print(f"⚠️ Regime detection failed: {e}")
        return 'Unknown'

# ============================================================================
# CONFIDENCE CALCULATION
# ============================================================================

def base_confidence(v4_score):
    """Base confidence from V4 score (fixed mapping)."""
    for (min_score, max_score), conf in CONFIDENCE_MAP.items():
        if min_score <= v4_score < max_score:
            return conf
    
    # Default for very low scores
    if v4_score < 100:
        return 45
    # Default for very high scores
    return 75

def confidence_adjustments(row, regime):
    """
    Apply rule-based confidence adjustments.
    
    Returns: (total_adjustment, reasons_list)
    """
    adj = 0
    reasons = []
    
    # Extract values
    inst = row.get('inst', 100)
    cap = str(row.get('market_cap', '')).upper()
    rel_fresh = row.get('relative_fresh', 0)
    fresh = row.get('fresh', 0)
    si = row.get('si', 0)
    days_earn = row.get('days_to_earnings')
    rsi = row.get('rsi')
    vol_ratio = row.get('volume_ratio')
    
    # 1. Institutional logic
    if inst < 30 and ('MID' in cap or 'LARGE' in cap):
        adj += INST_LOW_BONUS
        reasons.append(f"LowInst<30 +{INST_LOW_BONUS}")
    
    if regime == 'Risk-On':
        if inst > 90:
            adj += INST_VERY_HIGH_RISK_ON
            reasons.append(f"RiskOn+Inst>90 {INST_VERY_HIGH_RISK_ON}")
        elif inst > 80:
            adj += INST_HIGH_RISK_ON
            reasons.append(f"RiskOn+Inst>80 {INST_HIGH_RISK_ON}")
    
    # 2. Relative Fresh
    if rel_fresh <= 1.0:
        adj += REL_FRESH_FAIL
        reasons.append(f"RelFresh≤1 {REL_FRESH_FAIL}")
    elif rel_fresh >= 2.0:
        adj += REL_FRESH_STRONG
        reasons.append(f"RelFresh≥2 +{REL_FRESH_STRONG}")
    
    # 3. Fresh toxic zone
    if 3.0 <= fresh < 4.0:
        adj += FRESH_TOXIC
        reasons.append(f"Fresh3-4% {FRESH_TOXIC}")
    
    # 4. Market cap
    if 'SMALL' in cap:
        adj += SMALL_CAP_PENALTY
        reasons.append(f"SmallCap {SMALL_CAP_PENALTY}")
    elif 'MEGA' in cap:
        adj += MEGA_CAP_PENALTY
        reasons.append(f"MegaCap {MEGA_CAP_PENALTY}")
    
    # 5. Earnings
    if pd.notna(days_earn):
        if 30 <= days_earn <= 60:
            adj += EARNINGS_SWEET_SPOT
            reasons.append(f"Earn30-60d +{EARNINGS_SWEET_SPOT}")
        elif -30 < days_earn < 0:
            adj += EARNINGS_POST_PENALTY
            reasons.append(f"PostEarn {EARNINGS_POST_PENALTY}")
    
    # 6. SI
    if 0 <= si < 1:
        adj += SI_ELITE_BONUS
        reasons.append(f"SI0-1% +{SI_ELITE_BONUS}")
    elif 10 <= si < 15:
        adj += SI_HIGH_PENALTY
        reasons.append(f"SI10-15% {SI_HIGH_PENALTY}")
    elif si >= 15:
        adj += SI_VERY_HIGH_PENALTY
        reasons.append(f"SI≥15% {SI_VERY_HIGH_PENALTY}")
    
    # 7. Technicals (optional)
    if pd.notna(rsi) and rsi > 70:
        adj += RSI_OVERBOUGHT
        reasons.append(f"RSI>70 {RSI_OVERBOUGHT}")
    
    if pd.notna(vol_ratio):
        if 1.0 <= vol_ratio <= 1.5:
            adj += VOL_WEAK_PENALTY
            reasons.append(f"VolWeak {VOL_WEAK_PENALTY}")
    
    return adj, reasons

def drift_protection(historical_df, current_date):
    """
    Check recent performance and apply global drift penalties.
    
    Returns: (drift_adjustment, drift_reasons)
    """
    adj = 0
    reasons = []
    
    # Get recent trades (before current date)
    recent = historical_df[historical_df['date'] < current_date].copy()
    recent = recent.sort_values('date', ascending=False)
    
    if len(recent) == 0:
        return adj, reasons
    
    # Overall WR for comparison
    overall_wr = historical_df['win'].mean() * 100
    
    # Last 20 trades
    if len(recent) >= 20:
        last20 = recent.head(20)
        last20_avg = last20['return'].mean()
        last20_wr = last20['win'].mean() * 100
        
        if last20_avg < 0:
            adj += DRIFT_LAST20_NEG_AVG
            reasons.append(f"Last20Avg<0 {DRIFT_LAST20_NEG_AVG}")
        
        if last20_wr < (overall_wr - 5):
            adj += DRIFT_LAST20_WR_WEAK
            reasons.append(f"Last20WR-weak {DRIFT_LAST20_WR_WEAK}")
    
    # Last 50 trades
    if len(recent) >= 50:
        last50 = recent.head(50)
        last50_avg = last50['return'].mean()
        
        if last50_avg < 0:
            adj += DRIFT_LAST50_NEG_AVG
            reasons.append(f"Last50Avg<0 {DRIFT_LAST50_NEG_AVG}")
    
    return adj, reasons

def calculate_live_confidence(row, regime, historical_df, current_date):
    """
    Calculate final confidence score and recommended action.
    
    Returns: dict with confidence, action, reasons
    """
    v4 = row.get('v4_score', 0)
    
    # Base confidence
    base = base_confidence(v4)
    
    # Feature adjustments
    feature_adj, feature_reasons = confidence_adjustments(row, regime)
    
    # Drift protection
    drift_adj, drift_reasons = drift_protection(historical_df, current_date)
    
    # Final confidence
    final = max(0, min(100, base + feature_adj + drift_adj))
    
    # Combine reasons
    all_reasons = [f"Base={base}"] + feature_reasons + drift_reasons
    
    # Determine action
    if final >= ACTION_FULL:
        action = "FULL"
    elif final >= ACTION_HALF:
        action = "HALF"
    elif final >= ACTION_SMALL:
        action = "SMALL"
    else:
        action = "SKIP"
    
    # Override: Force SKIP for dangerous combos
    inst = row.get('inst', 100)
    cap = str(row.get('market_cap', '')).upper()
    rel_fresh = row.get('relative_fresh', 0)
    
    if 'SMALL' in cap:
        action = "SKIP"
        all_reasons.append("OVERRIDE: SmallCap→SKIP")
    elif regime == 'Risk-On' and inst > 90 and rel_fresh < 2.0:
        action = "SKIP"
        all_reasons.append("OVERRIDE: RiskOn+Inst>90+WeakRF→SKIP")
    
    return {
        'v4_score': v4,
        'regime': regime,
        'base_confidence': base,
        'final_confidence': final,
        'action': action,
        'reasons': ' | '.join(all_reasons)
    }

# ============================================================================
# DATA LOADING
# ============================================================================

def parse_percentage(val):
    """Parse percentage string to float."""
    if pd.isna(val) or val == '' or val == 'nan':
        return None
    val_str = str(val).replace('%', '').replace('+', '').strip()
    try:
        return float(val_str)
    except:
        return None

def load_historical_trades(csv_path="historical_trades.csv"):
    """Load historical trades for drift detection."""
    df_raw = pd.read_csv(csv_path, header=None)
    
    # Find header rows
    header_rows = []
    for i, row in df_raw.iterrows():
        if row[0] == 'Date' or str(row[0]).strip() == 'Date':
            header_rows.append(i)
    
    # Use most complete header
    best_idx = header_rows[0]
    max_cols = 0
    for idx in header_rows:
        row = df_raw.iloc[idx]
        non_empty = sum(1 for val in row if pd.notna(val) and str(val).strip())
        if non_empty > max_cols:
            max_cols = non_empty
            best_idx = idx
    
    headers = df_raw.iloc[best_idx].tolist()
    
    # Collect data
    data_rows = []
    for i, row in df_raw.iterrows():
        if i in header_rows:
            continue
        if pd.isna(row[0]) or str(row[0]).strip() == '':
            continue
        date_val = str(row[0]).strip()
        if 'Win Rate' in date_val:
            continue
        try:
            pd.to_datetime(date_val)
            data_rows.append(row.tolist())
        except:
            continue
    
    df = pd.DataFrame(data_rows, columns=headers)
    
    # Parse
    df['date'] = pd.to_datetime(df['Date'])
    
    # Parse returns
    return_col = None
    if '7d %' in df.columns:
        return_col = '7d %'
    else:
        for col in df.columns:
            col_str = str(col).lower()
            if ('7d' in col_str and '%' in col_str and 
                'past' not in col_str and 'week' not in col_str and 
                's&p' not in col_str):
                return_col = col
                break
    
    if return_col:
        df['return'] = df[return_col].apply(parse_percentage)
        df['win'] = (df['return'] > 0).astype(int)
    
    return df

# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def process_picks(picks_df, historical_df, current_date=None):
    """
    Process today's picks and add confidence layer.
    
    Args:
        picks_df: DataFrame with today's candidate picks
        historical_df: Historical trades for drift detection
        current_date: Date of analysis (default: today)
    
    Returns:
        DataFrame with confidence scores and actions
    """
    if current_date is None:
        current_date = datetime.now()
    
    # Detect regime
    regime = compute_regime(current_date)
    print(f"Current regime: {regime}\n")
    
    # Calculate confidence for each pick
    results = []
    
    for idx, row in picks_df.iterrows():
        conf_result = calculate_live_confidence(row, regime, historical_df, current_date)
        
        result = {
            'ticker': row.get('ticker'),
            'v4_score': conf_result['v4_score'],
            'regime': conf_result['regime'],
            'base_conf': conf_result['base_confidence'],
            'final_conf': conf_result['final_confidence'],
            'action': conf_result['action'],
            'reasons': conf_result['reasons']
        }
        
        results.append(result)
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('final_conf', ascending=False)
    
    return results_df

def historical_backtest(historical_df):
    """
    Run confidence layer on historical trades to validate.
    Shows what confidence scores WOULD have been.
    """
    print("="*80)
    print("HISTORICAL CONFIDENCE BACKTEST")
    print("="*80 + "\n")
    
    print("Applying confidence layer to all historical trades...")
    print("(As if the layer existed from day 1)\n")
    
    # Parse all needed columns from historical data
    historical_df['v4_score'] = pd.to_numeric(historical_df.get('V4Score', historical_df.get('V3Score', 0)), errors='coerce')
    historical_df['inst'] = historical_df.get('Inst %', pd.Series()).apply(parse_percentage)
    historical_df['market_cap'] = historical_df.get('Market Cap', 'MID')
    historical_df['relative_fresh'] = historical_df.get('Relative Fresh', pd.Series()).apply(parse_percentage)
    historical_df['fresh'] = historical_df.get('Past week 7d%', pd.Series()).apply(parse_percentage)
    historical_df['si'] = historical_df.get('Short Interest', pd.Series()).apply(parse_percentage)
    historical_df['days_to_earnings'] = pd.to_numeric(historical_df.get('Days to Earnings'), errors='coerce')
    historical_df['rsi'] = pd.to_numeric(historical_df.get('RSI'), errors='coerce')
    historical_df['volume_ratio'] = pd.to_numeric(historical_df.get('Vol Trend'), errors='coerce')
    historical_df['regime'] = historical_df.get('Regime', 'Risk-On')
    
    # For each trade, calculate what confidence would have been
    confidences = []
    actions = []
    all_reasons_list = []
    
    for idx, row in historical_df.iterrows():
        trade_date = row['date']
        
        # Use trades BEFORE this one for drift
        prior_trades = historical_df[historical_df['date'] < trade_date]
        
        # Detect regime for that date
        regime = row.get('regime', 'Risk-On')
        if pd.isna(regime):
            regime = 'Risk-On'
        
        # Calculate confidence
        conf_result = calculate_live_confidence(row, regime, prior_trades, trade_date)
        
        confidences.append(conf_result['final_confidence'])
        actions.append(conf_result['action'])
        all_reasons_list.append(conf_result['reasons'])
    
    historical_df['confidence'] = confidences
    historical_df['action'] = actions
    historical_df['reasons'] = all_reasons_list
    
    # Analyze by confidence bucket
    print("="*80)
    print("CONFIDENCE BUCKET PERFORMANCE")
    print("="*80 + "\n")
    
    buckets = [
        (0, 50, "0-49 (SKIP)"),
        (50, 60, "50-59 (SMALL)"),
        (60, 70, "60-69 (HALF)"),
        (70, 100, "70+ (FULL)")
    ]
    
    print(f"{'Bucket':<18} | {'N':>4} | {'WR':>7} | {'Avg':>8} | {'Sharpe':>7}")
    print("-"*60)
    
    for min_c, max_c, label in buckets:
        subset = historical_df[(historical_df['confidence'] >= min_c) & 
                               (historical_df['confidence'] < max_c)]
        
        if len(subset) == 0:
            continue
        
        n = len(subset)
        wr = subset['win'].mean() * 100
        avg = subset['return'].mean()
        sharpe = (avg / subset['return'].std()) * np.sqrt(52) if subset['return'].std() > 0 else 0
        
        status = "✅" if wr >= 75 else "⚠️" if wr >= 70 else "❌" if wr < 60 else ""
        
        print(f"{label:<18} | {n:>4} | {wr:>6.1f}% | {avg:>+7.2f}% | {sharpe:>7.2f} {status}")
    
    print()
    
    # Action-based performance
    print("="*80)
    print("ACTION-BASED PERFORMANCE")
    print("="*80 + "\n")
    
    print(f"{'Action':<10} | {'N':>4} | {'WR':>7} | {'Avg':>8}")
    print("-"*45)
    
    for action in ['FULL', 'HALF', 'SMALL', 'SKIP']:
        subset = historical_df[historical_df['action'] == action]
        
        if len(subset) == 0:
            continue
        
        wr = subset['win'].mean() * 100
        avg = subset['return'].mean()
        
        print(f"{action:<10} | {len(subset):>4} | {wr:>6.1f}% | {avg:>+7.2f}%")
    
    print()
    
    # Show sample reasons for SKIP
    skip_trades = historical_df[historical_df['action'] == 'SKIP'].head(5)
    if len(skip_trades) > 0:
        print("Sample SKIP reasons:")
        for _, t in skip_trades.iterrows():
            print(f"  {t.get('Ticker', 'N/A')}: {t['reasons'][:100]}...")
    
    print()

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("\n" + "="*80)
    print("LIVE CONFIDENCE SCORE LAYER")
    print("="*80 + "\n")
    
    # Load historical trades
    print("Loading historical trades...")
    historical_df = load_historical_trades("historical_trades.csv")
    
    if 'return' not in historical_df.columns:
        print("⚠️ No return data found - drift protection disabled")
    else:
        print(f"✓ Loaded {len(historical_df)} historical trades\n")
    
    # Run historical backtest
    historical_backtest(historical_df)
    
    print("="*80)
    print("✅ CONFIDENCE LAYER ANALYSIS COMPLETE")
    print("="*80 + "\n")
    
    print("USAGE FOR LIVE TRADING:")
    print("1. Load today's picks into DataFrame with columns:")
    print("   ticker, v4_score, market_cap, sector, inst, si, fresh, relative_fresh, etc.")
    print("2. Call: process_picks(picks_df, historical_df)")
    print("3. Get: Ranked list with confidence scores and actions")
    print()

if __name__ == "__main__":
    main()