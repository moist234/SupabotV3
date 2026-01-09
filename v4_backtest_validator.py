"""
V4 Score Backtest Validator

Tests how well the NEW V4 scoring (based on 121 trades) 
would have predicted winners vs losers.
"""
import pandas as pd
import numpy as np
from typing import Dict
from scipy import stats

def parse_percentage(val):
    """Convert percentage string to float."""
    if pd.isna(val) or val == '' or val == 'nan':
        return 0.0
    val_str = str(val).replace('%', '').replace('+', '').replace('$', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0


def calculate_quality_score_v4_new(pick: Dict) -> float:
    """NEW V4 scoring based on validated 121-trade patterns."""
    score = 0
    
    # 1. FRESH % SWEET SPOT (0-50 points)
    fresh = pick['change_7d']
    if 1.0 <= fresh <= 2.0:
        score += 50  # 80.6% WR
    elif 0 <= fresh < 1.0:
        score += 45  # 76.5% WR
    elif 2.0 < fresh <= 3.0:
        score += 45  # 100% WR
    elif -2.0 <= fresh < 0:
        score += 20  # 58.6% WR
    elif fresh > 3.0:
        score += 15  # 57.9% WR
    else:
        score += 10
    
    # 2. SHORT INTEREST ZONES (0-40 points)
    si = pick.get('short_percent', 0)
    if 3.0 <= si <= 7.0:
        score += 40  # 80.9% WR
    elif 0 <= si < 1.0:
        score += 35  # 75.0% WR
    elif 7.0 < si < 10.0:
        score += 30  # 75.0% WR
    elif 2.0 <= si < 3.0:
        score += 25  # 66.7% WR
    elif 1.0 <= si < 2.0:
        score += 15  # 60.0% WR - DEAD ZONE
    elif 10.0 <= si < 15.0:
        score += 10  # 53.3% WR - HIGH RISK
    
    # 3. MARKET CAP (0-30 points)
    cap_size = pick['cap_size']
    if 'LARGE' in cap_size.upper():
        score += 30  # 78.9% WR
    elif 'MID' in cap_size.upper():
        score += 25  # 72.4% WR
    elif 'SMALL' in cap_size.upper():
        score += 15  # 63.2% WR
    
    # 4. SECTOR PERFORMANCE (0-20 points)
    sector = pick['sector']
    if sector == 'Basic Materials':
        score += 20  # 90.9% WR
    elif sector == 'Communication Services':
        score += 15  # 77.8% WR
    elif sector == 'Technology':
        score += 10  # 73.3% WR
    elif sector == 'Healthcare':
        score += 10  # 72.7% WR
    
    # 5. COMBINATION BONUSES (0-10 points)
    if 1.0 <= fresh <= 3.0 and 2.0 <= si <= 5.0:
        score += 10  # 90.9% WR combo
    elif 1.0 <= fresh <= 3.0 and 5.0 <= si <= 10.0:
        score += 8   # 83.3% WR combo
    
    return score


def load_and_parse_data(csv_path="historical_trades.csv"):
    """Load and parse historical trades."""
    
    print("📂 Loading historical trades...")
    
    df_raw = pd.read_csv(csv_path, header=None)
    
    # Find header rows
    header_rows = []
    for i, row in df_raw.iterrows():
        if row[0] == 'Date' or str(row[0]).strip() == 'Date':
            header_rows.append(i)
    
    headers = df_raw.iloc[header_rows[0]].tolist()
    
    # Collect data rows
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
    
    # Parse dates
    df['date_parsed'] = pd.to_datetime(df['Date'])
    cutoff_date = pd.to_datetime('2025-12-01')
    
    # Parse fields
    df['ticker'] = df['Ticker']
    df['sector'] = df['Sector']
    df['cap_size'] = df['Market Cap']
    df['short_percent'] = df['Short Interest'].apply(parse_percentage)
    df['change_7d'] = df['Past week 7d%'].apply(parse_percentage)
    
    # Parse returns with date-based column selection
    returns_list = []
    for idx, row in df.iterrows():
        try:
            if row['date_parsed'] >= cutoff_date:
                return_val = row.iloc[17] if len(row) > 17 else ''
            else:
                return_val = row.iloc[12] if len(row) > 12 else ''
            returns_list.append(parse_percentage(return_val))
        except:
            returns_list.append(0.0)
    
    df['return_num'] = returns_list
    
    # Filter completed trades
    df = df[df['return_num'] != 0].copy()
    
    print(f"✅ Loaded {len(df)} completed trades\n")
    
    return df


def calculate_v4_scores(df):
    """Calculate V4 scores for all trades."""
    
    print("🔄 Calculating V4 scores...")
    
    v4_scores = []
    
    for idx, row in df.iterrows():
        pick = {
            'sector': row['sector'],
            'cap_size': row['cap_size'],
            'short_percent': row['short_percent'],
            'change_7d': row['change_7d']
        }
        
        v4_scores.append(calculate_quality_score_v4_new(pick))
    
    df['v4_score'] = v4_scores
    
    print(f"✅ Calculated V4 scores\n")
    
    return df


def analyze_v4_performance(df):
    """Analyze how well V4 predicts winners."""
    
    print("="*70)
    print("📊 V4 SCORE BACKTEST RESULTS")
    print("="*70 + "\n")
    
    winners = df[df['return_num'] > 0]
    losers = df[df['return_num'] <= 0]
    
    # Overall stats
    print(f"📈 Overall Performance:")
    print(f"   Total trades: {len(df)}")
    print(f"   Winners: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
    print(f"   Losers: {len(losers)} ({len(losers)/len(df)*100:.1f}%)\n")
    
    # V4 Score comparison
    winners_avg_v4 = winners['v4_score'].mean()
    losers_avg_v4 = losers['v4_score'].mean()
    v4_gap = winners_avg_v4 - losers_avg_v4
    
    print(f"📊 V4 Score Analysis:")
    print(f"   Winners avg V4: {winners_avg_v4:.1f}")
    print(f"   Losers avg V4: {losers_avg_v4:.1f}")
    print(f"   Gap: {v4_gap:+.1f} points")
    
    # Statistical test
    t_stat, p_val = stats.ttest_ind(winners['v4_score'], losers['v4_score'])
    print(f"\n   t-statistic: {t_stat:.2f}")
    print(f"   p-value: {p_val:.4f}")
    
    if p_val < 0.05:
        print(f"   ✅ Statistically significant (p<0.05)")
        print(f"   V4 DOES differentiate winners from losers!")
    else:
        print(f"   ⚠️  Not statistically significant (p={p_val:.4f})")
        print(f"   V4 has weak predictive power")
    
    # Correlation
    corr = df['v4_score'].corr(df['return_num'])
    print(f"\n   Correlation with returns: r = {corr:.3f}")
    
    if corr > 0.2:
        print(f"   ✅ STRONG positive correlation")
    elif corr > 0.1:
        print(f"   ⚠️  WEAK positive correlation")
    elif corr > 0:
        print(f"   ⚠️  MINIMAL positive correlation")
    else:
        print(f"   ❌ NEGATIVE or ZERO correlation")
    
    # V4 Score buckets
    print(f"\n{'='*70}")
    print(f"📊 V4 SCORE BUCKETS")
    print(f"{'='*70}\n")
    
    buckets = [
        (130, 999, ">130"),
        (120, 130, "120-130"),
        (110, 120, "110-120"),
        (100, 110, "100-110"),
        (90, 100, "90-100"),
        (80, 90, "80-90"),
        (0, 80, "<80")
    ]
    
    print(f"{'V4 Range':<12} | {'N':<5} | {'WR':<8} | {'W-L':<8} | {'Avg Ret':<10} | {'Assessment'}")
    print("-" * 75)
    
    for min_score, max_score, label in buckets:
        bucket = df[(df['v4_score'] >= min_score) & (df['v4_score'] < max_score)]
        
        if len(bucket) > 0:
            wins = (bucket['return_num'] > 0).sum()
            wr = wins / len(bucket) * 100
            avg = bucket['return_num'].mean()
            
            if wr >= 80:
                assess = "🔥 STRONG"
            elif wr >= 75:
                assess = "✅ GOOD"
            elif wr >= 70:
                assess = "⚠️  OKAY"
            else:
                assess = "❌ WEAK"
            
            print(f"V4 {label:<8} | {len(bucket):<5} | {wr:>6.1f}% | "
                  f"{wins:>2}-{len(bucket)-wins:<2} | {avg:>+8.2f}% | {assess}")
    
    # Show top and bottom V4 performers
    print(f"\n{'='*70}")
    print(f"🏆 TOP 10 V4 SCORES (Actual Performance)")
    print(f"{'='*70}\n")
    
    top_10 = df.nlargest(10, 'v4_score')
    
    for _, row in top_10.iterrows():
        result = "✅" if row['return_num'] > 0 else "❌"
        print(f"{result} {row['ticker']:6} | V4: {row['v4_score']:3.0f} | "
              f"{row['sector']:25} | {row['cap_size']:6} | "
              f"Return: {row['return_num']:+6.2f}%")
    
    print(f"\n{'='*70}")
    print(f"❌ BOTTOM 10 V4 SCORES (Actual Performance)")
    print(f"{'='*70}\n")
    
    bottom_10 = df.nsmallest(10, 'v4_score')
    
    for _, row in bottom_10.iterrows():
        result = "✅" if row['return_num'] > 0 else "❌"
        print(f"{result} {row['ticker']:6} | V4: {row['v4_score']:3.0f} | "
              f"{row['sector']:25} | {row['cap_size']:6} | "
              f"Return: {row['return_num']:+6.2f}%")
    
    # Show all losses with V4 scores
    print(f"\n{'='*70}")
    print(f"❌ ALL LOSSES WITH V4 SCORES ({len(losers)} losses)")
    print(f"{'='*70}\n")
    
    for _, row in losers.sort_values('v4_score', ascending=False).iterrows():
        print(f"❌ {row['ticker']:6} | V4: {row['v4_score']:3.0f} | "
              f"Return: {row['return_num']:+6.2f}% | {row['sector']:25} | "
              f"Fresh: {row['change_7d']:+5.1f}% | SI: {row['short_percent']:4.1f}%")
    
    # Recommendation
    print(f"\n{'='*70}")
    print(f"🎯 RECOMMENDATION")
    print(f"{'='*70}\n")
    
    if p_val < 0.05 and v4_gap > 5:
        print(f"✅ V4 IS READY FOR SELECTION")
        print(f"   - Statistically significant (p={p_val:.4f})")
        print(f"   - Winners score {v4_gap:.1f} points higher")
        print(f"   - Can switch to V4 selection now")
    elif corr > 0.1 and v4_gap > 3:
        print(f"⚠️  V4 SHOWS PROMISE BUT NEEDS MORE VALIDATION")
        print(f"   - Positive correlation (r={corr:.3f})")
        print(f"   - Winners score {v4_gap:.1f} points higher")
        print(f"   - Collect 20+ more V4-tracked trades")
    else:
        print(f"❌ V4 NOT READY FOR SELECTION")
        print(f"   - Weak predictive power (r={corr:.3f}, gap={v4_gap:.1f})")
        print(f"   - Keep using V3 for selection")
        print(f"   - Continue tracking V4 through Dec 30")


def main():
    print("\n" + "="*70)
    print("🔬 V4 SCORE BACKTEST VALIDATOR")
    print("="*70 + "\n")
    
    # Load data
    try:
        df = load_and_parse_data("historical_trades.csv")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Calculate V4 scores
    df = calculate_v4_scores(df)
    
    # Analyze performance
    analyze_v4_performance(df)
    
    print("\n" + "="*70)
    print("✅ BACKTEST COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()