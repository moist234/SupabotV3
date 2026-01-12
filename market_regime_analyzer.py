"""
Market Regime × Relative Fresh Combo Analyzer

Tests: Does Relative Fresh threshold need to be different in Risk-On vs Risk-Off?

Hypothesis:
- Risk-Off: Relative Fresh >1% is sufficient (hard to fake)
- Risk-On: Relative Fresh >2% needed (filter weak outperformance)

This would explain:
- Why Risk-Off works so well (genuine strength easy to detect)
- Why Risk-On is weaker (diluted by false signals)
"""
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from scipy import stats as scipy_stats

def parse_percentage(val):
    if pd.isna(val) or val == '' or val == 'nan':
        return 0.0
    val_str = str(val).replace('%', '').replace('+', '').replace('$', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0


def load_data(csv_path="historical_trades.csv"):
    """Load trades."""
    
    print("📂 Loading trades...\n")
    
    df_raw = pd.read_csv(csv_path, header=None)
    
    header_rows = []
    for i, row in df_raw.iterrows():
        if row[0] == 'Date' or str(row[0]).strip() == 'Date':
            header_rows.append(i)
    
    headers = df_raw.iloc[header_rows[0]].tolist()
    
    data_rows = []
    for i, row in df_raw.iterrows():
        if i in header_rows:
            continue
        if pd.isna(row[0]) or str(row[0]).strip() == '':
            continue
        date_val = str(row[0]).strip()
        if 'Win Rate' in date_val or 'Average' in date_val:
            continue
        try:
            pd.to_datetime(date_val)
            data_rows.append(row.tolist())
        except:
            continue
    
    df = pd.DataFrame(data_rows, columns=headers)
    
    df['date'] = pd.to_datetime(df['Date'])
    df['ticker'] = df['Ticker']
    
    fresh_values = []
    for idx, row in df.iterrows():
        fresh_values.append(parse_percentage(row['Past week 7d%']))
    
    df['fresh'] = fresh_values
    
    cutoff = pd.to_datetime('2025-12-01')
    returns = []
    for idx, row in df.iterrows():
        try:
            if row['date'] >= cutoff:
                ret = row.iloc[17] if len(row) > 17 else ''
            else:
                ret = row.iloc[12] if len(row) > 12 else ''
            returns.append(parse_percentage(ret))
        except:
            returns.append(0.0)
    
    df['return_7d'] = returns
    df = df[df['return_7d'].notna()].copy()
    
    print(f"✅ {len(df)} trades loaded\n")
    
    return df


def get_regime_and_relative_fresh(date, stock_fresh):
    """Get both regime and relative fresh for a date."""
    
    try:
        start = date - timedelta(days=40)
        end = date + timedelta(days=2)
        
        spy = yf.download('SPY', start=start, end=end, progress=False, auto_adjust=True)
        
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.droplevel(1)
        
        if len(spy) < 20:
            return None, None
        
        # Find last trading day <= entry date
        valid_dates = [d for d in spy.index if d.date() <= date.date()]
        
        if len(valid_dates) < 20:
            return None, None
        
        # Get data up to entry date
        spy_to_entry = spy.loc[:valid_dates[-1]]
        
        # 20D SMA for regime
        sma_20 = spy_to_entry['Close'].rolling(20).mean().iloc[-1]
        current_price = float(spy_to_entry['Close'].iloc[-1])
        
        regime = 'Risk-On' if current_price > sma_20 else 'Risk-Off'
        
        # 7D return for relative fresh
        if len(spy_to_entry) >= 8:
            spy_7d = ((spy_to_entry['Close'].iloc[-1] / spy_to_entry['Close'].iloc[-8]) - 1) * 100
            relative_fresh = stock_fresh - spy_7d
        else:
            relative_fresh = None
        
        return regime, relative_fresh
    
    except:
        return None, None


def analyze_combo(df):
    """Analyze Regime × Relative Fresh combinations."""
    
    print("="*80)
    print("🔍 CLASSIFYING BY REGIME + RELATIVE FRESH")
    print("="*80 + "\n")
    
    print("⏳ Fetching SPY data...\n")
    
    regimes = []
    rel_fresh_values = []
    
    for idx, row in df.iterrows():
        regime, rel_fresh = get_regime_and_relative_fresh(row['date'], row['fresh'])
        regimes.append(regime)
        rel_fresh_values.append(rel_fresh)
        
        if idx % 50 == 0 and regime:
            print(f"   {row['date'].strftime('%Y-%m-%d')}: {regime} | Rel Fresh {rel_fresh:+.1f}%")
    
    df['regime'] = regimes
    df['relative_fresh'] = rel_fresh_values
    
    valid = df[(df['regime'].notna()) & (df['relative_fresh'].notna())]
    
    print(f"\n✅ Classified {len(valid)}/{len(df)} trades\n")
    
    return df


def test_regime_specific_thresholds(df):
    """Test if Relative Fresh thresholds should differ by regime."""
    
    print("="*80)
    print("📊 REGIME × RELATIVE FRESH PERFORMANCE")
    print("="*80 + "\n")
    
    valid = df[(df['regime'].notna()) & (df['relative_fresh'].notna())]
    
    # Test different thresholds in each regime
    thresholds = [0, 1, 2, 3]
    
    for regime_name in ['Risk-On', 'Risk-Off']:
        regime_df = valid[valid['regime'] == regime_name]
        
        if len(regime_df) < 20:
            continue
        
        print(f"{regime_name} (N={len(regime_df)}):")
        print(f"{'Threshold':<15} | {'Passes Filter':<15} | {'WR':<8} | {'Avg Ret':<10} | {'Improvement'}")
        print("-" * 75)
        
        baseline_wr = len(regime_df[regime_df['return_7d'] > 0]) / len(regime_df) * 100
        
        for threshold in thresholds:
            subset = regime_df[regime_df['relative_fresh'] > threshold]
            
            if len(subset) >= 10:
                wins = len(subset[subset['return_7d'] > 0])
                wr = wins / len(subset) * 100
                avg = subset['return_7d'].mean()
                improvement = wr - baseline_wr
                
                status = "🔥" if improvement > 8 else "✅" if improvement > 4 else "⚠️" if improvement > 0 else "❌"
                
                print(f"RelFresh >{threshold}%   | {len(subset):<15} | {wr:>6.1f}% | {avg:>+8.2f}% | {improvement:>+6.1f} pts {status}")
        
        print()


def generate_sophisticated_rule(df):
    """Generate regime-aware Relative Fresh rule."""
    
    print("="*80)
    print("🎯 SOPHISTICATED RULE RECOMMENDATION")
    print("="*80 + "\n")
    
    valid = df[(df['regime'].notna()) & (df['relative_fresh'].notna())]
    
    risk_on = valid[valid['regime'] == 'Risk-On']
    risk_off = valid[valid['regime'] == 'Risk-Off']
    
    if len(risk_on) < 20 or len(risk_off) < 20:
        print("⚠️  Insufficient data")
        return
    
    # Test >1% in Risk-Off, >2% in Risk-On
    risk_off_rf1 = risk_off[risk_off['relative_fresh'] > 1]
    risk_on_rf2 = risk_on[risk_on['relative_fresh'] > 2]
    
    # Test uniform >1% rule
    uniform_rf1 = valid[valid['relative_fresh'] > 1]
    
    if len(risk_off_rf1) >= 10 and len(risk_on_rf2) >= 10:
        riskoff_wr = len(risk_off_rf1[risk_off_rf1['return_7d'] > 0]) / len(risk_off_rf1) * 100
        riskon_wr = len(risk_on_rf2[risk_on_rf2['return_7d'] > 0]) / len(risk_on_rf2) * 100
        combined_wr = (len(risk_off_rf1[risk_off_rf1['return_7d'] > 0]) + len(risk_on_rf2[risk_on_rf2['return_7d'] > 0])) / (len(risk_off_rf1) + len(risk_on_rf2)) * 100
        
        uniform_wr = len(uniform_rf1[uniform_rf1['return_7d'] > 0]) / len(uniform_rf1) * 100
        
        print(f"OPTION A: Uniform Rule (RelFresh >1% always)")
        print(f"   Total trades: {len(uniform_rf1)}")
        print(f"   Win rate: {uniform_wr:.1f}%\n")
        
        print(f"OPTION B: Regime-Aware Rule")
        print(f"   Risk-Off: RelFresh >1% ({len(risk_off_rf1)} trades, {riskoff_wr:.1f}% WR)")
        print(f"   Risk-On: RelFresh >2% ({len(risk_on_rf2)} trades, {riskon_wr:.1f}% WR)")
        print(f"   Combined: {len(risk_off_rf1) + len(risk_on_rf2)} trades, {combined_wr:.1f}% WR\n")
        
        if combined_wr > uniform_wr + 3:
            print("✅ DEPLOY REGIME-AWARE RULE")
            print(f"   Improves WR by {combined_wr - uniform_wr:+.1f} points")
            print(f"\n   Implementation:")
            print(f"   if SPY > 20D SMA: require RelFresh >2%")
            print(f"   if SPY < 20D SMA: require RelFresh >1%")
        else:
            print("⚠️  UNIFORM RULE IS SIMPLER")
            print(f"   Regime-aware only adds {combined_wr - uniform_wr:+.1f} points")
            print(f"   Keep simple: RelFresh >1% always")


def main():
    print("\n" + "="*80)
    print("🔬 REGIME × RELATIVE FRESH COMBO ANALYZER")
    print("="*80 + "\n")
    
    print("Question: Should Relative Fresh threshold vary by market regime?")
    print("Hypothesis: Tighten in Risk-On, keep loose in Risk-Off\n")
    
    try:
        df = load_data("historical_trades.csv")
        df = analyze_combo(df)
        test_regime_specific_thresholds(df)
        generate_sophisticated_rule(df)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("✅ COMBO ANALYSIS COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()