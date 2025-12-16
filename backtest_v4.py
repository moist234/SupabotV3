"""
Backtest V4 Optimized Scores on Historical Trades
Calculates what V4 scores would have been for all past trades
"""
import pandas as pd
import numpy as np
from typing import Dict

def calculate_quality_score_v4(pick: Dict) -> float:
    """
    V4 Optimized scoring - same as in supabot_v3.py
    """
    score = 0
    
    # 1. SECTOR (0-40 points)
    sector = pick.get('sector', 'Unknown')
    cap_size = pick.get('cap_size', 'UNKNOWN')
    
    if sector == 'Healthcare':
        score += 40 if 'MID' in cap_size else 25
    elif sector == 'Industrials':
        score += 35
    elif sector == 'Real Estate':
        score += 30
    elif sector == 'Basic Materials':
        score += 25
    elif sector == 'Communication Services':
        score += 20
    elif sector == 'Technology':
        score += 15
    # Financial Services & Consumer Defensive = 0
    
    # 2. MARKET CAP (0-25 points)
    if 'MID' in cap_size:
        score += 25
    elif 'SMALL' in cap_size:
        score += 15
    elif 'LARGE' in cap_size:
        score += 8
    # MEGA = 0
    
    # 3. SHORT INTEREST (0-25 points)
    si = pick.get('short_percent', 0)
    if 5.0 <= si <= 10.0:
        score += 25  # Golden zone
    elif 2.0 <= si < 5.0:
        score += 20
    elif 10.0 < si <= 15.0:
        score += 10  # Spicy but not core
    # 0-2% and >15% = 0
    
    # 4. FRESH % (0-20 points)
    fresh = pick.get('change_7d', 0)
    if fresh < 0:
        score += 20
    elif 0 <= fresh <= 2:
        score += 18
    elif 2 < fresh <= 4:
        score += 12
    # >4% = 0
    
    # 5. 52W POSITION (0-15 points)
    dist = pick.get('dist_52w_high', 0)
    if -40 <= dist <= -10:
        score += 15
    elif -50 <= dist < -40:
        score += 8
    # Near highs or deep value = 0
    
    # 6. VOLUME TREND (0-15 points)
    vol = pick.get('volume_trend', 1.0)
    if vol >= 1.0:
        score += 15
    elif vol >= 0.7:
        score += 10
    # <0.7 = 0
    
    # 7. TWITTER (0-5 points)
    twitter = pick.get('twitter_mentions', 0)
    if twitter >= 25:
        score += 5
    elif twitter >= 20:
        score += 3
    
    return score


def parse_percentage(val):
    """Convert percentage string to float."""
    if pd.isna(val) or val == '':
        return 0.0
    val_str = str(val).replace('%', '').replace('+', '').replace('$', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0


def main():
    print("\n" + "="*60)
    print("🔬 SUPABOT V3: V4 SCORE BACKTEST")
    print("="*60 + "\n")
    
    # Load historical data
    print("📂 Loading historical trades...")
    try:
        df = pd.read_csv("historical_trades.csv")
        print(f"✅ Loaded {len(df)} total rows")
        
        # Debug: Show first few column names
        print(f"\n📋 Detected columns:")
        for i, col in enumerate(df.columns[:15]):
            print(f"   {i}: '{col}'")
        
        # Find return column by searching
        return_col = None
        for col in df.columns:
            col_lower = col.lower()
            if '7d' in col_lower and '%' in col_lower and 'exit' not in col_lower and 'past' not in col_lower:
                return_col = col
                break
        
        if return_col is None:
            print("\n❌ Could not find 7d % return column!")
            print(f"\nAll columns: {list(df.columns)}")
            return
        
        print(f"\n✅ Using return column: '{return_col}'")
        
        # Find ticker column first (needed for filtering)
        ticker_col = [c for c in df.columns if 'ticker' in c.lower()][0]
        
        # Filter to only completed trades
        df_clean = df[df[return_col].notna() & (df[return_col] != '')]
        
        # Remove rows with missing ticker or sector (junk data)
        df_clean = df_clean[df_clean[ticker_col].notna() & (df_clean[ticker_col] != '')]
        df_clean = df_clean[df_clean[ticker_col] != 'Ticker']  # Remove header duplicates
        
        print(f"✅ Filtered to {len(df_clean)} completed trades\n")
        
        if len(df_clean) == 0:
            print("❌ No completed trades found!")
            return
        
        df = df_clean
        
    except FileNotFoundError:
        print("❌ Error: historical_trades.csv not found!")
        print("\n📝 To create it:")
        print("  1. Open your Google Sheet")
        print("  2. File → Download → CSV")
        print("  3. Save as 'historical_trades.csv' in SupabotV3 folder")
        return
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Find all required columns
    print("🔍 Detecting column names...")
    
    try:
        # Required columns
        ticker_col = [c for c in df.columns if 'ticker' in c.lower()][0]
        date_col = [c for c in df.columns if 'date' in c.lower()][0]
        sector_col = [c for c in df.columns if 'sector' in c.lower()][0]
        cap_col = [c for c in df.columns if 'market cap' in c.lower()][0]
        si_col = [c for c in df.columns if 'short interest' in c.lower()][0]
        fresh_col = [c for c in df.columns if 'past week' in c.lower()][0]
        twitter_col = [c for c in df.columns if 'twitter' in c.lower()][0]
        reddit_col = [c for c in df.columns if 'reddit' in c.lower()][0]
        score_col = [c for c in df.columns if 'score' in c.lower() and 'v4' not in c.lower() and 'win' not in c.lower() and 'average' not in c.lower()][0]
        
        print(f"✅ Column mapping complete\n")
        
    except IndexError as e:
        print(f"❌ Missing required column: {e}")
        print(f"\nRequired columns: Ticker, Date, Sector, Market Cap, Short Interest, Past week 7d%, Twitter, Reddit, Score")
        return
    
    # Parse numeric fields
    print("🔄 Parsing numeric data...")
    df['short_interest_num'] = df[si_col].apply(parse_percentage)
    df['fresh_num'] = df[fresh_col].apply(parse_percentage)
    df['return_num'] = df[return_col].apply(parse_percentage)
    df['twitter_num'] = pd.to_numeric(df[twitter_col], errors='coerce').fillna(0)
    df['reddit_num'] = pd.to_numeric(df[reddit_col], errors='coerce').fillna(0)
    df['score_v3'] = pd.to_numeric(df[score_col], errors='coerce').fillna(0)
    
    # Handle optional columns
    dist_col = [c for c in df.columns if '52w' in c.lower()]
    vol_col = [c for c in df.columns if 'vol trend' in c.lower()]
    
    if len(dist_col) > 0:
        df['dist_52w_num'] = df[dist_col[0]].apply(parse_percentage)
        print("✅ Found 52w positioning data")
    else:
        df['dist_52w_num'] = 0
        print("⚠️  No 52w data - using 0 for all trades")
    
    if len(vol_col) > 0:
        df['vol_trend_num'] = pd.to_numeric(df[vol_col[0]], errors='coerce').fillna(1.0)
        print("✅ Found volume trend data")
    else:
        df['vol_trend_num'] = 1.0
        print("⚠️  No Vol Trend data - using 1.0 for all trades")
    
    print()
    
    # Calculate V4 scores
    print("🔄 Calculating V4 scores for all historical trades...")
    v4_scores = []
    
    for idx, row in df.iterrows():
        pick = {
            'sector': row[sector_col],
            'cap_size': row[cap_col],
            'short_percent': row['short_interest_num'],
            'change_7d': row['fresh_num'],
            'dist_52w_high': row['dist_52w_num'],
            'volume_trend': row['vol_trend_num'],
            'twitter_mentions': int(row['twitter_num']),
            'reddit_mentions': int(row['reddit_num'])
        }
        
        v4_score = calculate_quality_score_v4(pick)
        v4_scores.append(v4_score)
    
    df['V4_Score'] = v4_scores
    print(f"✅ V4 scores calculated for {len(df)} trades\n")
    
    # Analysis
    print("="*60)
    print("📊 V4 SCORE ANALYSIS")
    print("="*60 + "\n")
    
    winners = df[df['return_num'] > 0]
    losers = df[df['return_num'] <= 0]
    
    print(f"🎯 Overall Statistics:")
    print(f"  Total Trades: {len(df)}")
    print(f"  Winners: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
    print(f"  Losers: {len(losers)} ({len(losers)/len(df)*100:.1f}%)")
    print(f"  Avg Return: {df['return_num'].mean():+.2f}%\n")
    
    print(f"📈 V4 Score Distribution:")
    print(f"  Winners avg V4 score: {winners['V4_Score'].mean():.1f}")
    print(f"  Losers avg V4 score: {losers['V4_Score'].mean():.1f}")
    print(f"  Difference: {winners['V4_Score'].mean() - losers['V4_Score'].mean():+.1f} points")
    
    # Calculate correlation
    correlation = df['V4_Score'].corr(df['return_num'])
    print(f"\n🔬 Correlation:")
    print(f"  V4 Score vs Returns: r = {correlation:.3f}")
    
    if correlation > 0.2:
        print(f"  ✅ STRONG positive correlation - V4 predicts well!")
    elif correlation > 0.1:
        print(f"  ✅ Moderate positive correlation - V4 has some predictive power")
    elif correlation > -0.1:
        print(f"  ⚠️  Weak/no correlation - V4 needs work")
    else:
        print(f"  ❌ Negative correlation - V4 is broken")
    
    # V3 vs V4 correlation comparison
    v3_correlation = df['score_v3'].corr(df['return_num'])
    print(f"\n📊 V3 vs V4 Comparison:")
    print(f"  V3 Score correlation: r = {v3_correlation:.3f}")
    print(f"  V4 Score correlation: r = {correlation:.3f}")
    print(f"  Improvement: {correlation - v3_correlation:+.3f}")
    
    if correlation > v3_correlation + 0.1:
        print(f"  🔥 V4 is SIGNIFICANTLY better than V3!")
    elif correlation > v3_correlation:
        print(f"  ✅ V4 is better than V3")
    else:
        print(f"  ⚠️  V4 is NOT better than V3")
    
    # Performance by V4 score buckets
    print(f"\n{'='*60}")
    print(f"📊 PERFORMANCE BY V4 SCORE BUCKET")
    print(f"{'='*60}\n")
    
    buckets = [
        ("Very High (>120)", 120, 999),
        ("High (100-120)", 100, 120),
        ("Medium (80-100)", 80, 100),
        ("Low (60-80)", 60, 80),
        ("Very Low (<60)", 0, 60)
    ]
    
    for label, min_score, max_score in buckets:
        bucket_df = df[(df['V4_Score'] > min_score) & (df['V4_Score'] <= max_score)]
        if len(bucket_df) > 0:
            wins = (bucket_df['return_num'] > 0).sum()
            wr = wins / len(bucket_df) * 100
            avg_return = bucket_df['return_num'].mean()
            median_return = bucket_df['return_num'].median()
            print(f"{label:20} | {len(bucket_df):2} trades | {wr:5.1f}% WR | {avg_return:+6.2f}% avg | {median_return:+6.2f}% median")
    
    # WEEKLY BREAKDOWN ANALYSIS
    print(f"\n{'='*60}")
    print(f"📅 WEEK-BY-WEEK V4 CORRELATION ANALYSIS")
    print(f"{'='*60}\n")
    
    # Convert date to datetime
    df[date_col] = pd.to_datetime(df[date_col])
    df['week'] = df[date_col].dt.to_period('W')
    
    weekly_stats = []
    
    for week in sorted(df['week'].unique()):
        week_df = df[df['week'] == week]
        
        if len(week_df) >= 3:  # Need at least 3 trades for meaningful correlation
            week_wins = (week_df['return_num'] > 0).sum()
            week_wr = week_wins / len(week_df) * 100
            week_avg = week_df['return_num'].mean()
            
            # V4 correlation for this week
            week_v4_corr = week_df['V4_Score'].corr(week_df['return_num'])
            week_v3_corr = week_df['score_v3'].corr(week_df['return_num'])
            
            # V4 score distribution
            week_winners = week_df[week_df['return_num'] > 0]
            week_losers = week_df[week_df['return_num'] <= 0]
            
            avg_v4_winners = week_winners['V4_Score'].mean() if len(week_winners) > 0 else 0
            avg_v4_losers = week_losers['V4_Score'].mean() if len(week_losers) > 0 else 0
            
            weekly_stats.append({
                'week': str(week),
                'trades': len(week_df),
                'wr': week_wr,
                'avg_return': week_avg,
                'v4_corr': week_v4_corr,
                'v3_corr': week_v3_corr,
                'v4_winners_avg': avg_v4_winners,
                'v4_losers_avg': avg_v4_losers,
                'start_date': week_df[date_col].min().strftime('%m/%d'),
                'end_date': week_df[date_col].max().strftime('%m/%d')
            })
    
    # Display weekly results
    for stat in weekly_stats:
        gap = stat['v4_winners_avg'] - stat['v4_losers_avg']
        
        # Assess correlation strength
        if abs(stat['v4_corr']) > 0.25:
            v4_status = "🔥 Strong"
        elif abs(stat['v4_corr']) > 0.15:
            v4_status = "✅ Moderate"
        elif abs(stat['v4_corr']) > 0.05:
            v4_status = "⚠️  Weak"
        else:
            v4_status = "❌ None"
        
        # Color code by correlation direction
        if stat['v4_corr'] < 0:
            corr_display = f"❌ {stat['v4_corr']:+.3f}"
        elif stat['v4_corr'] > 0.2:
            corr_display = f"✅ {stat['v4_corr']:+.3f}"
        else:
            corr_display = f"⚠️  {stat['v4_corr']:+.3f}"
        
        print(f"\n📆 Week of {stat['start_date']}-{stat['end_date']} ({stat['trades']} trades):")
        print(f"   Performance: {stat['wr']:.1f}% WR, {stat['avg_return']:+.2f}% avg")
        print(f"   V4 Correlation: {corr_display} | {v4_status}")
        print(f"   V3 Correlation: {stat['v3_corr']:+.3f}")
        print(f"   V4 Winners avg: {stat['v4_winners_avg']:.1f} | Losers avg: {stat['v4_losers_avg']:.1f} | Gap: {gap:+.1f}")
    
    # Summary of weekly consistency
    print(f"\n{'='*60}")
    print(f"📊 V4 CONSISTENCY SUMMARY")
    print(f"{'='*60}\n")
    
    strong_weeks = sum(1 for s in weekly_stats if abs(s['v4_corr']) > 0.2)
    weak_weeks = sum(1 for s in weekly_stats if abs(s['v4_corr']) < 0.1)
    positive_weeks = sum(1 for s in weekly_stats if s['v4_corr'] > 0)
    
    print(f"Total Weeks: {len(weekly_stats)}")
    print(f"Strong V4 correlation (r>0.2): {strong_weeks}/{len(weekly_stats)} weeks")
    print(f"Weak V4 correlation (r<0.1): {weak_weeks}/{len(weekly_stats)} weeks")
    print(f"Positive V4 correlation: {positive_weeks}/{len(weekly_stats)} weeks")
    
    avg_v4_corr = sum(s['v4_corr'] for s in weekly_stats) / len(weekly_stats)
    print(f"\nAverage V4 correlation across weeks: {avg_v4_corr:.3f}")
    
    if strong_weeks >= len(weekly_stats) * 0.7:
        print(f"\n✅ V4 is CONSISTENT - works on most weeks")
        print(f"   → Safe to deploy for selection")
    elif strong_weeks >= len(weekly_stats) * 0.5:
        print(f"\n⚠️  V4 is MIXED - works on some weeks, fails on others")
        print(f"   → Need more data or formula refinement")
    else:
        print(f"\n❌ V4 is UNRELIABLE - fails more than it works")
        print(f"   → Do NOT deploy, needs major revision")
    
    # Identify best V4-scored picks
    print(f"\n{'='*60}")
    print(f"🔥 TOP 10 HIGHEST V4-SCORED TRADES")
    print(f"{'='*60}\n")
    
    top_10_v4 = df.nlargest(10, 'V4_Score')
    for idx, row in top_10_v4.iterrows():
        win_flag = "✅" if row['return_num'] > 0 else "❌"
        print(f"{win_flag} {row[ticker_col]:6} | V4: {row['V4_Score']:3.0f} | V3: {row['score_v3']:3.0f} | "
              f"{row[sector_col]:20} | SI: {row['short_interest_num']:4.1f}% | Return: {row['return_num']:+6.2f}%")
    
    print(f"\n{'='*60}")
    print(f"❌ BOTTOM 10 LOWEST V4-SCORED TRADES")
    print(f"{'='*60}\n")
    
    bottom_10_v4 = df.nsmallest(10, 'V4_Score')
    for idx, row in bottom_10_v4.iterrows():
        win_flag = "✅" if row['return_num'] > 0 else "❌"
        print(f"{win_flag} {row[ticker_col]:6} | V4: {row['V4_Score']:3.0f} | V3: {row['score_v3']:3.0f} | "
              f"{row[sector_col]:20} | SI: {row['short_interest_num']:4.1f}% | Return: {row['return_num']:+6.2f}%")
    
    # Theoretical V4 performance
    print(f"\n{'='*60}")
    print(f"🎯 WHAT IF V4 HAD SELECTED STOCKS?")
    print(f"{'='*60}\n")
    
    print("(Simulating: Pick top 10 V4-scored stocks each day)\n")
    
    # Group by date
    dates = df[date_col].unique()
    print(f"📅 Analyzing {len(dates)} unique trading days...\n")
    
    v4_would_pick = []
    v3_actually_picked = []
    
    for date in dates:
        day_df = df[df[date_col] == date]
        
        if len(day_df) > 0:
            # What V4 would pick (top 10 by V4 score)
            v4_top = day_df.nlargest(min(10, len(day_df)), 'V4_Score')
            v4_would_pick.extend(v4_top.index.tolist())
            
            # What V3 actually picked (all trades from that day)
            v3_actually_picked.extend(day_df.index.tolist())
    
    # Calculate theoretical V4 performance
    v4_theoretical = df.loc[v4_would_pick]
    v3_actual = df.loc[v3_actually_picked]
    
    print("V4 SELECTION (Theoretical):")
    v4_wr = (v4_theoretical['return_num'] > 0).sum() / len(v4_theoretical) * 100
    v4_avg = v4_theoretical['return_num'].mean()
    print(f"  Trades: {len(v4_theoretical)}")
    print(f"  Win Rate: {v4_wr:.1f}%")
    print(f"  Avg Return: {v4_avg:+.2f}%")
    print(f"  Median Return: {v4_theoretical['return_num'].median():+.2f}%")
    
    print("\nV3 SELECTION (Actual):")
    v3_wr = (v3_actual['return_num'] > 0).sum() / len(v3_actual) * 100
    v3_avg = v3_actual['return_num'].mean()
    print(f"  Trades: {len(v3_actual)}")
    print(f"  Win Rate: {v3_wr:.1f}%")
    print(f"  Avg Return: {v3_avg:+.2f}%")
    print(f"  Median Return: {v3_actual['return_num'].median():+.2f}%")
    
    print("\n📈 V4 vs V3 IMPROVEMENT:")
    wr_improvement = v4_wr - v3_wr
    ret_improvement = v4_avg - v3_avg
    print(f"  Win Rate: {wr_improvement:+.1f} percentage points")
    print(f"  Avg Return: {ret_improvement:+.2f} percentage points")
    
    if wr_improvement > 5 or ret_improvement > 1:
        print(f"\n  🔥 V4 SIGNIFICANTLY OUTPERFORMS!")
        print(f"  → SWITCH TO V4 FOR SELECTION IMMEDIATELY")
    elif wr_improvement > 2 or ret_improvement > 0.5:
        print(f"\n  ✅ V4 shows improvement")
        print(f"  → Consider switching to V4 selection")
    else:
        print(f"\n  ⚠️  V4 doesn't significantly improve")
        print(f"  → Keep V3 for selection, continue tracking V4")
    
    # Detailed losers analysis
    print(f"\n{'='*60}")
    print(f"🔍 ALL LOSSES - V4 SCORE ANALYSIS")
    print(f"{'='*60}\n")
    
    losers_sorted = losers.sort_values('V4_Score', ascending=False)
    print(f"Total Losses: {len(losers)}\n")
    
    for idx, row in losers_sorted.iterrows():
        print(f"❌ {row[ticker_col]:6} | V4: {row['V4_Score']:3.0f} | V3: {row['score_v3']:3.0f} | "
              f"{row[sector_col]:20} | {row[cap_col]:6} | "
              f"SI: {row['short_interest_num']:4.1f}% | Fresh: {row['fresh_num']:+5.1f}% | "
              f"Loss: {row['return_num']:+6.2f}%")
    
    print(f"\n💡 Loss Analysis:")
    print(f"  Avg V4 Score of Losers: {losers['V4_Score'].mean():.1f}")
    print(f"  Avg V4 Score of Winners: {winners['V4_Score'].mean():.1f}")
    print(f"  Difference: {winners['V4_Score'].mean() - losers['V4_Score'].mean():+.1f} points")
    
    # Count how many losers would have been filtered by V4
    low_v4_losers = losers[losers['V4_Score'] < 80]
    print(f"\n  Losers with V4 <80: {len(low_v4_losers)}/{len(losers)} ({len(low_v4_losers)/len(losers)*100:.1f}%)")
    
    # Check if high V4 picks still lost
    high_v4_losers = losers[losers['V4_Score'] >= 100]
    if len(high_v4_losers) > 0:
        print(f"\n  ⚠️  High V4 scores (>100) that still lost:")
        for idx, row in high_v4_losers.iterrows():
            print(f"     {row[ticker_col]}: V4={row['V4_Score']:.0f}, {row['return_num']:+.2f}% | {row[sector_col]} | SI {row['short_interest_num']:.1f}%")
    else:
        print(f"\n  ✅ NO LOSSES with V4 score >100 (perfect filtering!)")
    
    # Save results
    output_file = "historical_with_v4_scores.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✅ Saved analysis to {output_file}")
    
    print("\n" + "="*60)
    print("✅ BACKTEST COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()