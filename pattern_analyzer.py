"""
Supabot V3: Advanced Pattern Analyzer
Finds optimal thresholds, factor combinations, and trading rules
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from itertools import combinations
from scipy import stats

def parse_percentage(val):
    """Convert percentage string to float."""
    if pd.isna(val) or val == '':
        return 0.0
    val_str = str(val).replace('%', '').replace('+', '').replace('$', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0


def find_optimal_threshold(df, column, return_col='return_num', step=1.0):
    """
    Find optimal threshold for a numeric column.
    Returns threshold that maximizes win rate or return.
    """
    if column not in df.columns:
        return None
    
    values = df[column].dropna()
    if len(values) == 0:
        return None
    
    min_val = values.min()
    max_val = values.max()
    
    best_threshold = None
    best_metric = -999
    
    results = []
    
    for threshold in np.arange(min_val, max_val, step):
        above = df[df[column] >= threshold]
        below = df[df[column] < threshold]
        
        if len(above) >= 5 and len(below) >= 5:  # Need meaningful samples
            above_wr = (above[return_col] > 0).sum() / len(above) * 100
            below_wr = (below[return_col] > 0).sum() / len(below) * 100
            above_avg = above[return_col].mean()
            below_avg = below[return_col].mean()
            
            # Metric: Maximize WR difference + return difference
            metric = (above_wr - below_wr) + (above_avg - below_avg) * 10
            
            results.append({
                'threshold': threshold,
                'above_trades': len(above),
                'below_trades': len(below),
                'above_wr': above_wr,
                'below_wr': below_wr,
                'above_avg': above_avg,
                'below_avg': below_avg,
                'metric': metric
            })
            
            if metric > best_metric:
                best_metric = metric
                best_threshold = threshold
    
    return {
        'best_threshold': best_threshold,
        'all_thresholds': results
    }


def analyze_two_factor_combos(df, return_col='return_num'):
    """
    Find best two-factor combinations.
    """
    factors = {
        'sector': 'categorical',
        'cap': 'categorical',
        'short_interest_num': 'numeric',
        'fresh_num': 'numeric'
    }
    
    results = []
    
    # Get unique values for categoricals
    sectors = df['sector'].unique()
    caps = df['cap'].unique()
    
    # Test sector + cap combos
    for sector in sectors:
        for cap in caps:
            subset = df[(df['sector'] == sector) & (df['cap'] == cap)]
            
            if len(subset) >= 3:  # Need at least 3 trades
                wins = (subset[return_col] > 0).sum()
                wr = wins / len(subset) * 100
                avg = subset[return_col].mean()
                
                results.append({
                    'combo': f"{sector} + {cap}",
                    'trades': len(subset),
                    'wr': wr,
                    'avg': avg,
                    'sharpe': avg / subset[return_col].std() if subset[return_col].std() > 0 else 0
                })
    
    # Test SI ranges + cap
    si_ranges = [(0, 2), (2, 5), (5, 10), (10, 15), (15, 20)]
    
    for si_min, si_max in si_ranges:
        for cap in caps:
            subset = df[(df['short_interest_num'] >= si_min) & 
                       (df['short_interest_num'] < si_max) & 
                       (df['cap'] == cap)]
            
            if len(subset) >= 3:
                wins = (subset[return_col] > 0).sum()
                wr = wins / len(subset) * 100
                avg = subset[return_col].mean()
                
                results.append({
                    'combo': f"SI {si_min}-{si_max}% + {cap}",
                    'trades': len(subset),
                    'wr': wr,
                    'avg': avg,
                    'sharpe': avg / subset[return_col].std() if subset[return_col].std() > 0 else 0
                })
    
    # Sort by Sharpe ratio
    results.sort(key=lambda x: x['sharpe'], reverse=True)
    
    return results


def analyze_three_factor_combos(df, return_col='return_num'):
    """
    Find best three-factor combinations.
    """
    results = []
    
    sectors = df['sector'].unique()
    caps = df['cap'].unique()
    si_ranges = [(0, 2), (2, 5), (5, 10), (10, 15)]
    
    for sector in sectors:
        for cap in caps:
            for si_min, si_max in si_ranges:
                subset = df[(df['sector'] == sector) & 
                           (df['cap'] == cap) & 
                           (df['short_interest_num'] >= si_min) & 
                           (df['short_interest_num'] < si_max)]
                
                if len(subset) >= 3:
                    wins = (subset[return_col] > 0).sum()
                    wr = wins / len(subset) * 100
                    avg = subset[return_col].mean()
                    
                    results.append({
                        'combo': f"{sector} + {cap} + SI {si_min}-{si_max}%",
                        'trades': len(subset),
                        'wr': wr,
                        'avg': avg,
                        'best_trade': subset[return_col].max(),
                        'worst_trade': subset[return_col].min()
                    })
    
    # Sort by WR then avg return
    results.sort(key=lambda x: (x['wr'], x['avg']), reverse=True)
    
    return results


def find_loss_patterns(df, return_col='return_num'):
    """
    Analyze all losses to find common patterns.
    """
    losers = df[df[return_col] <= 0]
    
    if len(losers) == 0:
        return None
    
    patterns = {
        'sectors': {},
        'caps': {},
        'si_ranges': {},
        'fresh_ranges': {}
    }
    
    # Sector distribution
    for sector in losers['sector'].unique():
        count = (losers['sector'] == sector).sum()
        total_sector = (df['sector'] == sector).sum()
        loss_rate = count / total_sector * 100 if total_sector > 0 else 0
        patterns['sectors'][sector] = {
            'count': count,
            'total': total_sector,
            'loss_rate': loss_rate
        }
    
    # Cap distribution
    for cap in losers['cap'].unique():
        count = (losers['cap'] == cap).sum()
        total_cap = (df['cap'] == cap).sum()
        loss_rate = count / total_cap * 100 if total_cap > 0 else 0
        patterns['caps'][cap] = {
            'count': count,
            'total': total_cap,
            'loss_rate': loss_rate
        }
    
    # SI ranges
    si_ranges = [(0, 2, "0-2%"), (2, 5, "2-5%"), (5, 10, "5-10%"), (10, 15, "10-15%"), (15, 20, "15-20%")]
    for si_min, si_max, label in si_ranges:
        in_range = losers[(losers['short_interest_num'] >= si_min) & (losers['short_interest_num'] < si_max)]
        total_range = df[(df['short_interest_num'] >= si_min) & (df['short_interest_num'] < si_max)]
        
        if len(total_range) > 0:
            patterns['si_ranges'][label] = {
                'count': len(in_range),
                'total': len(total_range),
                'loss_rate': len(in_range) / len(total_range) * 100
            }
    
    return patterns


def main():
    print("\n" + "="*70)
    print("🔬 SUPABOT V3: ADVANCED PATTERN ANALYZER")
    print("="*70 + "\n")
    
    # Load data
    print("📂 Loading historical trades...")
    try:
        df = pd.read_csv("historical_trades.csv")
        print(f"✅ Loaded {len(df)} total rows\n")
        
        # Find return column - be VERY specific
        # Look for column that has "7d" and "%" but NOT "past week" and comes AFTER "Exit Price"
        return_col = None
        exit_col_idx = None
        
        # First find Exit Price column
        for i, col in enumerate(df.columns):
            if 'exit price' in col.lower() and '7d' in col.lower():
                exit_col_idx = i
                break
        
        # Then find 7d % column that comes AFTER Exit Price
        if exit_col_idx is not None:
            for i, col in enumerate(df.columns):
                if i > exit_col_idx and '7d' in col.lower() and '%' in col.lower():
                    return_col = col
                    break
        
        # Fallback: just find any 7d % column
        if return_col is None:
            for col in df.columns:
                col_lower = col.lower()
                # Must have 7d and %, but NOT be "past week" and NOT be part of summary stats
                if ('7d' in col_lower and '%' in col_lower and 
                    'past' not in col_lower and 'week' not in col_lower and
                    'win rate' not in col_lower and 'average' not in col_lower and
                    's&p' not in col_lower):
                    return_col = col
                    break
        
        if return_col is None:
            print("❌ Could not find return column!")
            print(f"Columns: {list(df.columns)}")
            return
        
        print(f"✅ Using return column: '{return_col}' (column index: {df.columns.get_loc(return_col)})")
        
        print(f"✅ Using return column: '{return_col}' (column index: {df.columns.get_loc(return_col)})")
        
        # Find columns
        ticker_col = [c for c in df.columns if 'ticker' in c.lower()][0]
        sector_col = [c for c in df.columns if 'sector' in c.lower()][0]
        cap_col = [c for c in df.columns if 'market cap' in c.lower()][0]
        si_col = [c for c in df.columns if 'short interest' in c.lower()][0]
        fresh_col = [c for c in df.columns if 'past week' in c.lower()][0]
        
        # Filter to completed trades
        df = df[df[return_col].notna() & (df[return_col] != '')]
        df = df[df[ticker_col].notna() & (df[ticker_col] != '')]
        
        print(f"✅ Analyzing {len(df)} completed trades\n")
        
        # Parse numeric fields
        df['return_num'] = df[return_col].apply(parse_percentage)
        df['short_interest_num'] = df[si_col].apply(parse_percentage)
        df['fresh_num'] = df[fresh_col].apply(parse_percentage)
        df['sector'] = df[sector_col]
        df['cap'] = df[cap_col]
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Analysis sections
    print("="*70)
    print("📊 1. OVERALL PORTFOLIO STATISTICS")
    print("="*70 + "\n")
    
    # Overall stats
    total_trades = len(df)
    total_wins = (df['return_num'] > 0).sum()
    total_losses = (df['return_num'] <= 0).sum()
    overall_wr = total_wins / total_trades * 100
    avg_return = df['return_num'].mean()
    median_return = df['return_num'].median()
    std_return = df['return_num'].std()
    
    # Calculate additional metrics
    avg_win = df[df['return_num'] > 0]['return_num'].mean()
    avg_loss = df[df['return_num'] <= 0]['return_num'].mean()
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    max_win = df['return_num'].max()
    max_loss = df['return_num'].min()
    
    # Calculate Sharpe ratio (annualized approximation)
    sharpe = (avg_return / std_return) * np.sqrt(52) if std_return > 0 else 0
    
    print(f"📈 Performance Metrics:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Wins: {total_wins} ({overall_wr:.1f}%)")
    print(f"   Losses: {total_losses} ({100-overall_wr:.1f}%)")
    print(f"\n💰 Return Statistics:")
    print(f"   Average Return: {avg_return:+.2f}%")
    print(f"   Median Return: {median_return:+.2f}%")
    print(f"   Std Deviation: {std_return:.2f}%")
    print(f"   Best Trade: {max_win:+.2f}%")
    print(f"   Worst Trade: {max_loss:+.2f}%")
    print(f"\n📊 Risk Metrics:")
    print(f"   Avg Win: {avg_win:+.2f}%")
    print(f"   Avg Loss: {avg_loss:+.2f}%")
    print(f"   Win/Loss Ratio: {win_loss_ratio:.2f}x")
    print(f"   Sharpe Ratio (annualized): {sharpe:.2f}")
    
    # Statistical significance
    from scipy import stats
    t_stat, p_value = stats.ttest_1samp(df['return_num'], 0)
    print(f"\n🔬 Statistical Significance:")
    print(f"   t-statistic: {t_stat:.2f}")
    print(f"   p-value: {p_value:.4f}")
    
    if p_value < 0.01:
        print(f"   ✅ Highly significant (p<0.01) - Edge is REAL")
    elif p_value < 0.05:
        print(f"   ✅ Significant (p<0.05) - Edge exists")
    else:
        print(f"   ⚠️  Not significant (p>{p_value:.2f}) - Could be luck")
    
    # Confidence interval
    confidence = 0.95
    margin = stats.t.ppf((1 + confidence) / 2, len(df) - 1) * (std_return / np.sqrt(len(df)))
    ci_lower = avg_return - margin
    ci_upper = avg_return + margin
    
    print(f"   95% Confidence Interval: [{ci_lower:+.2f}%, {ci_upper:+.2f}%]")
    
    if ci_lower > 0:
        print(f"   ✅ Lower bound positive - Consistent edge")
    
    print(f"\n{'='*70}")
    print("📊 2. OPTIMAL THRESHOLD ANALYSIS")
    print("="*70 + "\n")
    
    # Find optimal SI threshold
    print("🎯 Short Interest Optimal Threshold:\n")
    si_analysis = find_optimal_threshold(df, 'short_interest_num', step=0.5)
    
    if si_analysis:
        best = si_analysis['best_threshold']
        best_result = [r for r in si_analysis['all_thresholds'] if r['threshold'] == best][0]
        
        print(f"📈 Best threshold: SI ≥ {best:.1f}%")
        print(f"   Above {best:.1f}%: {best_result['above_wr']:.1f}% WR, {best_result['above_avg']:+.2f}% avg ({best_result['above_trades']} trades)")
        print(f"   Below {best:.1f}%: {best_result['below_wr']:.1f}% WR, {best_result['below_avg']:+.2f}% avg ({best_result['below_trades']} trades)")
        print(f"   Gap: {best_result['above_wr'] - best_result['below_wr']:+.1f} points WR, {best_result['above_avg'] - best_result['below_avg']:+.2f}% return\n")
        
        # Show top 5 thresholds
        print("   Top 5 SI thresholds by performance gap:")
        top_5 = sorted(si_analysis['all_thresholds'], key=lambda x: x['metric'], reverse=True)[:5]
        for i, r in enumerate(top_5, 1):
            print(f"   {i}. SI ≥{r['threshold']:.1f}%: Above {r['above_wr']:.1f}% WR vs Below {r['below_wr']:.1f}% WR")
    
    # Find optimal Fresh threshold
    print(f"\n🎯 Fresh % Optimal Threshold:\n")
    fresh_analysis = find_optimal_threshold(df, 'fresh_num', step=0.5)
    
    if fresh_analysis:
        best = fresh_analysis['best_threshold']
        best_result = [r for r in fresh_analysis['all_thresholds'] if r['threshold'] == best][0]
        
        print(f"📈 Best threshold: Fresh ≤ {best:.1f}%")
        print(f"   Below {best:.1f}%: {best_result['below_wr']:.1f}% WR, {best_result['below_avg']:+.2f}% avg ({best_result['below_trades']} trades)")
        print(f"   Above {best:.1f}%: {best_result['above_wr']:.1f}% WR, {best_result['above_avg']:+.2f}% avg ({best_result['above_trades']} trades)")
        print(f"   Gap: {best_result['below_wr'] - best_result['above_wr']:+.1f} points WR\n")
    
    # Two-factor combos
    print("="*70)
    print("📊 2. BEST TWO-FACTOR COMBINATIONS")
    print("="*70 + "\n")
    
    two_factor = analyze_two_factor_combos(df)
    
    print(f"\n🔥 Top 10 Two-Factor Combinations (by Sharpe Ratio):\n")
    print(f"{'Rank':<5} {'Combination':<45} {'N':<6} {'WR':<9} {'Avg Return':<12} {'Sharpe':<8} {'Confidence'}")
    print("-" * 100)
    
    for i, combo in enumerate(two_factor[:15], 1):  # Show top 15
        # Confidence assessment based on sample size
        n = combo['trades']
        if n >= 20:
            confidence = "✅ High"
        elif n >= 10:
            confidence = "⚠️  Medium"
        elif n >= 5:
            confidence = "⚠️  Low"
        else:
            confidence = "❌ Tiny (unreliable)"
        
        print(f"{i:<5} {combo['combo']:<45} {combo['trades']:<6} "
              f"{combo['wr']:>6.1f}% {combo['avg']:>+10.2f}% {combo['sharpe']:>7.2f}  {confidence}")
    
    # Three-factor combos
    print(f"\n{'='*70}")
    print("📊 3. BEST THREE-FACTOR COMBINATIONS")
    print("="*70 + "\n")
    
    three_factor = analyze_three_factor_combos(df)
    
    print(f"🔥 Top 10 Three-Factor Combinations (by Win Rate):\n")
    print(f"{'Rank':<5} {'Combination':<55} {'N':<6} {'WR':<9} {'Avg':<12} {'Confidence'}")
    print("-" * 100)
    
    shown = 0
    for combo in three_factor:
        if combo['wr'] >= 80 and shown < 15:  # Show top 15 with WR ≥80%
            n = combo['trades']
            
            # Confidence based on sample size
            if n >= 10:
                confidence = "✅ Validated"
            elif n >= 5:
                confidence = "⚠️  Small sample"
            else:
                confidence = "❌ Tiny (luck?)"
            
            shown += 1
            print(f"{shown:<5} {combo['combo']:<55} {combo['trades']:<6} "
                  f"{combo['wr']:>6.1f}% {combo['avg']:>+10.2f}% {confidence}")
            
            if n < 10:
                print(f"      ⚠️  Sample too small - could be luck! Best: {combo['best_trade']:+.2f}% | Worst: {combo['worst_trade']:+.2f}%")
    
    # Loss pattern analysis
    print(f"\n{'='*70}")
    print("📊 4. LOSS PATTERN ANALYSIS")
    print("="*70 + "\n")
    
    loss_patterns = find_loss_patterns(df)
    
    if loss_patterns:
        print("🚨 Sectors with Highest Loss Rates:\n")
        sector_losses = sorted(loss_patterns['sectors'].items(), 
                              key=lambda x: x[1]['loss_rate'], 
                              reverse=True)[:5]
        
        for sector, stats in sector_losses:
            if stats['total'] >= 3:
                print(f"   {sector:25} | {stats['count']}/{stats['total']} losses | "
                      f"Loss rate: {stats['loss_rate']:.1f}%")
        
        print(f"\n🚨 Market Caps with Highest Loss Rates:\n")
        cap_losses = sorted(loss_patterns['caps'].items(), 
                           key=lambda x: x[1]['loss_rate'], 
                           reverse=True)
        
        for cap, stats in cap_losses:
            if stats['total'] >= 3:
                print(f"   {cap:10} | {stats['count']}/{stats['total']} losses | "
                      f"Loss rate: {stats['loss_rate']:.1f}%")
        
        print(f"\n🚨 SI Ranges with Highest Loss Rates:\n")
        si_losses = sorted(loss_patterns['si_ranges'].items(), 
                          key=lambda x: x[1]['loss_rate'], 
                          reverse=True)
        
        for si_range, stats in si_losses:
            print(f"   SI {si_range:8} | {stats['count']}/{stats['total']} losses | "
                  f"Loss rate: {stats['loss_rate']:.1f}%")
    
    # Detailed SI bucket analysis
    print(f"\n{'='*70}")
    print("📊 5. DETAILED SHORT INTEREST ANALYSIS")
    print("="*70 + "\n")
    
    si_buckets = [
        (0, 1, "0-1%"),
        (1, 2, "1-2%"),
        (2, 3, "2-3%"),
        (3, 5, "3-5%"),
        (5, 7, "5-7%"),
        (7, 10, "7-10%"),
        (10, 12, "10-12%"),
        (12, 15, "12-15%"),
        (15, 20, "15-20%")
    ]
    
    print("SI Range     | Trades | Win Rate | Avg Return | Best Trade | Worst Trade | Std Dev | Assessment")
    print("-" * 110)
    
    for si_min, si_max, label in si_buckets:
        bucket = df[(df['short_interest_num'] >= si_min) & (df['short_interest_num'] < si_max)]
        
        if len(bucket) > 0:
            wins = (bucket['return_num'] > 0).sum()
            wr = wins / len(bucket) * 100
            avg = bucket['return_num'].mean()
            best = bucket['return_num'].max()
            worst = bucket['return_num'].min()
            std = bucket['return_num'].std()
            
            # Assessment with sample size consideration
            if wr >= 90 and len(bucket) >= 10:
                assessment = "🔥 GOLDEN (validated)"
            elif wr >= 90 and len(bucket) >= 5:
                assessment = "✅ STRONG (small sample)"
            elif wr >= 90 and len(bucket) < 5:
                assessment = "⚠️  HIGH WR (tiny sample!)"
            elif wr >= 80:
                assessment = "✅ GOOD"
            elif wr >= 70:
                assessment = "⚠️  OKAY"
            else:
                assessment = "❌ WEAK"
            
            # Add warning for small samples
            if len(bucket) < 5:
                assessment += " ⚡N<5"
            elif len(bucket) < 10:
                assessment += " ⚡N<10"
            
            print(f"{label:12} | {len(bucket):6} | {wr:8.1f}% | {avg:+10.2f}% | "
                  f"{best:+10.2f}% | {worst:+11.2f}% | {std:7.2f}% | {assessment}")
    
    # Fresh % detailed analysis
    print(f"\n{'='*70}")
    print("📊 6. DETAILED FRESH % ANALYSIS")
    print("="*70 + "\n")
    
    fresh_buckets = [
        (-10, -5, "<-5%"),
        (-5, -3, "-5 to -3%"),
        (-3, -1, "-3 to -1%"),
        (-1, 0, "-1 to 0%"),
        (0, 1, "0 to 1%"),
        (1, 2, "1 to 2%"),
        (2, 3, "2 to 3%"),
        (3, 5, "3 to 5%"),
        (5, 10, ">5%")
    ]
    
    print("Fresh Range  | Trades | Win Rate | Avg Return | Median | Std Dev | Assessment")
    print("-" * 85)
    
    for f_min, f_max, label in fresh_buckets:
        bucket = df[(df['fresh_num'] >= f_min) & (df['fresh_num'] < f_max)]
        
        if len(bucket) > 0:
            wins = (bucket['return_num'] > 0).sum()
            wr = wins / len(bucket) * 100
            avg = bucket['return_num'].mean()
            median = bucket['return_num'].median()
            std = bucket['return_num'].std()
            
            # Assessment with sample size
            if wr >= 90 and len(bucket) >= 10:
                assessment = "🔥 BEST (validated)"
            elif wr >= 85 and len(bucket) >= 5:
                assessment = "✅ GOOD"
            elif wr >= 85 and len(bucket) < 5:
                assessment = "⚠️  HIGH WR (tiny!)"
            elif wr >= 75:
                assessment = "⚠️  OKAY"
            elif wr >= 65:
                assessment = "⚠️  RISKY"
            else:
                assessment = "❌ AVOID"
            
            # Sample size warnings
            if len(bucket) < 5:
                assessment += " ⚡N<5"
            elif len(bucket) < 10:
                assessment += " ⚡N<10"
            
            print(f"{label:12} | {len(bucket):6} | {wr:8.1f}% | {avg:+10.2f}% | {median:+6.2f}% | {std:7.2f}% | {assessment}")
    
    # Actionable filters
    print(f"\n{'='*70}")
    print("📋 7. RECOMMENDED FILTERS (Based on Analysis)")
    print("="*70 + "\n")
    
    # Calculate what filters would improve
    current_wr = (df['return_num'] > 0).sum() / len(df) * 100
    
    # Test SI ≥2% filter
    si_filtered = df[df['short_interest_num'] >= 2.0]
    si_filtered_wr = (si_filtered['return_num'] > 0).sum() / len(si_filtered) * 100
    si_improvement = si_filtered_wr - current_wr
    
    # Test SI ≥5% filter
    si_filtered_5 = df[df['short_interest_num'] >= 5.0]
    si_filtered_5_wr = (si_filtered_5['return_num'] > 0).sum() / len(si_filtered_5) * 100 if len(si_filtered_5) > 0 else 0
    si_improvement_5 = si_filtered_5_wr - current_wr
    
    # Test Fresh ≤2% filter
    fresh_filtered = df[df['fresh_num'] <= 2.0]
    fresh_filtered_wr = (fresh_filtered['return_num'] > 0).sum() / len(fresh_filtered) * 100
    fresh_improvement = fresh_filtered_wr - current_wr
    
    # Test Mid-cap only filter
    mid_only = df[df['cap'].str.contains('MID', na=False)]
    mid_only_wr = (mid_only['return_num'] > 0).sum() / len(mid_only) * 100 if len(mid_only) > 0 else 0
    mid_improvement = mid_only_wr - current_wr
    
    print(f"Current Win Rate: {current_wr:.1f}% ({(df['return_num'] > 0).sum()}/{len(df)} wins)\n")
    print(f"Filter Options:\n")
    print(f"1. Add SI ≥2.0% filter:")
    print(f"   New WR: {si_filtered_wr:.1f}% ({(si_filtered['return_num'] > 0).sum()}/{len(si_filtered)} wins)")
    print(f"   Improvement: {si_improvement:+.1f} points | Removes {len(df) - len(si_filtered)} weak trades")
    
    print(f"\n2. Add SI ≥5.0% filter (stricter):")
    print(f"   New WR: {si_filtered_5_wr:.1f}% ({(si_filtered_5['return_num'] > 0).sum() if len(si_filtered_5) > 0 else 0}/{len(si_filtered_5)} wins)")
    print(f"   Improvement: {si_improvement_5:+.1f} points | Removes {len(df) - len(si_filtered_5)} trades")
    print(f"   ⚠️  Trade-off: Fewer picks ({len(si_filtered_5)} vs {len(df)}), but higher quality")
    
    print(f"\n3. Add Fresh ≤2.0% filter:")
    print(f"   New WR: {fresh_filtered_wr:.1f}% ({(fresh_filtered['return_num'] > 0).sum()}/{len(fresh_filtered)} wins)")
    print(f"   Improvement: {fresh_improvement:+.1f} points")
    
    if fresh_improvement < 0:
        print(f"   ❌ HURTS PERFORMANCE - Don't add this filter!")
    
    print(f"\n4. Mid-cap only:")
    print(f"   New WR: {mid_only_wr:.1f}% ({(mid_only['return_num'] > 0).sum() if len(mid_only) > 0 else 0}/{len(mid_only)} wins)")
    print(f"   Improvement: {mid_improvement:+.1f} points | Removes {len(df) - len(mid_only)} trades")
    print(f"   ⚠️  Trade-off: Significantly fewer picks per day")
    
    # Combined filters
    combined = df[(df['short_interest_num'] >= 2.0) & 
                  (df['fresh_num'] <= 2.0) & 
                  (df['cap'].str.contains('MID|SMALL', na=False))]
    
    if len(combined) > 0:
        combined_wr = (combined['return_num'] > 0).sum() / len(combined) * 100
        combined_improvement = combined_wr - current_wr
        
        print(f"\n5. COMBINED (SI≥2% + Fresh≤2% + Mid/Small only):")
        print(f"   New WR: {combined_wr:.1f}% ({(combined['return_num'] > 0).sum()}/{len(combined)} wins)")
        print(f"   Improvement: {combined_improvement:+.1f} points | Removes {len(df) - len(combined)} trades")
    
    # Show what you'd be filtering OUT
    print(f"\n{'='*70}")
    print(f"📉 WHAT GETS FILTERED BY SI ≥2%")
    print(f"{'='*70}\n")
    
    filtered_out = df[df['short_interest_num'] < 2.0]
    if len(filtered_out) > 0:
        filtered_wins = (filtered_out['return_num'] > 0).sum()
        filtered_wr = filtered_wins / len(filtered_out) * 100
        filtered_avg = filtered_out['return_num'].mean()
        
        print(f"Trades removed: {len(filtered_out)}")
        print(f"Their performance: {filtered_wr:.1f}% WR, {filtered_avg:+.2f}% avg")
        print(f"Losses prevented: {len(filtered_out) - filtered_wins}")
        print(f"\nWhy this helps: You're removing {len(filtered_out)} trades with only {filtered_wr:.1f}% WR")
        print(f"Net effect: Portfolio WR increases from {current_wr:.1f}% to {si_filtered_wr:.1f}%")
    
    # Final recommendations
    print(f"\n{'='*70}")
    print("💡 ACTIONABLE RECOMMENDATIONS")
    print("="*70 + "\n")
    
    recommendations = []
    
    if si_improvement > 5:
        conf = "HIGH confidence" if len(filtered_out) >= 20 else "MEDIUM confidence"
        recommendations.append(f"✅ ADD SI ≥2% filter (improves WR by {si_improvement:+.1f} points) - {conf}")
    
    if fresh_improvement > 2:
        recommendations.append(f"✅ ADD Fresh ≤2% filter (improves WR by {fresh_improvement:+.1f} points)")
    elif fresh_improvement < -2:
        recommendations.append(f"❌ DON'T add Fresh ≤2% filter (hurts WR by {fresh_improvement:.1f} points)")
    
    if mid_improvement > 8:
        conf = "HIGH confidence" if len(mid_only) >= 30 else "MEDIUM confidence"
        recommendations.append(f"✅ PRIORITIZE Mid-cap heavily (improves WR by {mid_improvement:+.1f} points) - {conf}")
    
    # Add statistical confidence notes
    print("\n📊 Statistical Confidence Notes:\n")
    print(f"   Sample size guidelines:")
    print(f"   • N ≥30: High confidence in patterns")
    print(f"   • N 10-29: Medium confidence")
    print(f"   • N 5-9: Low confidence (could be luck)")
    print(f"   • N <5: Very low confidence (likely noise)")
    print(f"\n   Your total sample: {len(df)} trades")
    print(f"   • SI 5-12% zone: {len(df[(df['short_interest_num'] >= 5) & (df['short_interest_num'] < 12)])} trades")
    print(f"   • Mid-cap: {len(mid_only)} trades")
    print(f"   • SI <2%: {len(filtered_out)} trades")
    
    if len(recommendations) > 0:
        print("Recommended Filter Changes:\n")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("✅ Current filters are near-optimal. Continue tracking V4 validation.")
    
    print("\n" + "="*70)
    print("✅ PATTERN ANALYSIS COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()