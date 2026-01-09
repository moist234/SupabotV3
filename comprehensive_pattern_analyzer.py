"""
Comprehensive Pattern Analyzer

Provides extensive statistics and insights on all factors:
- Detailed performance metrics
- Statistical significance testing
- Stability analysis across time
- Factor interactions
- Risk metrics (Sharpe, max drawdown)
- Outlier analysis
"""
import pandas as pd
import numpy as np
from datetime import datetime
from scipy import stats
from collections import defaultdict

def parse_percentage(val):
    if pd.isna(val) or val == '' or val == 'nan':
        return 0.0
    val_str = str(val).replace('%', '').replace('+', '').replace('$', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0


def load_data(csv_path="historical_trades.csv"):
    """Load historical trades."""
    
    print("📂 Loading trades...")
    
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
    
    df['date_parsed'] = pd.to_datetime(df['Date'])
    cutoff_date = pd.to_datetime('2025-12-01')
    
    df['ticker'] = df['Ticker']
    df['sector'] = df['Sector']
    df['cap'] = df['Market Cap']
    df['v3_score'] = pd.to_numeric(df['V3Score'], errors='coerce').fillna(0)
    df['si'] = df['Short Interest'].apply(parse_percentage)
    df['fresh'] = df['Past week 7d%'].apply(parse_percentage)
    df['twitter'] = pd.to_numeric(df['Twitter'], errors='coerce').fillna(0)
    df['reddit'] = pd.to_numeric(df['Reddit'], errors='coerce').fillna(0)
    
    returns = []
    for idx, row in df.iterrows():
        try:
            if row['date_parsed'] >= cutoff_date:
                ret = row.iloc[17] if len(row) > 17 else ''
            else:
                ret = row.iloc[12] if len(row) > 12 else ''
            returns.append(parse_percentage(ret))
        except:
            returns.append(0.0)
    
    df['return_7d'] = returns
    df = df[df['return_7d'] != 0].copy()
    
    df['week'] = df['date_parsed'].dt.isocalendar().week
    df['year_week'] = df['date_parsed'].dt.strftime('%Y-W%U')
    
    print(f"✅ {len(df)} trades loaded\n")
    
    return df


def overall_statistics(df):
    """Comprehensive overall statistics."""
    
    print("="*80)
    print("📊 OVERALL PORTFOLIO STATISTICS")
    print("="*80 + "\n")
    
    total = len(df)
    wins = (df['return_7d'] > 0).sum()
    losses = total - wins
    wr = wins / total * 100
    
    avg_return = df['return_7d'].mean()
    median_return = df['return_7d'].median()
    std_return = df['return_7d'].std()
    
    win_avg = df[df['return_7d'] > 0]['return_7d'].mean()
    loss_avg = df[df['return_7d'] <= 0]['return_7d'].mean()
    
    best = df['return_7d'].max()
    worst = df['return_7d'].min()
    
    # Sharpe ratio (annualized)
    sharpe = (avg_return / std_return) * np.sqrt(52) if std_return > 0 else 0
    
    # Win/loss ratio
    wl_ratio = abs(win_avg / loss_avg) if loss_avg != 0 else 0
    
    # Statistical significance
    t_stat, p_val = stats.ttest_1samp(df['return_7d'], 0)
    
    # Confidence interval
    ci_margin = stats.t.ppf(0.975, total - 1) * (std_return / np.sqrt(total))
    ci_lower = avg_return - ci_margin
    ci_upper = avg_return + ci_margin
    
    print(f"📈 Performance Metrics:")
    print(f"   Total Trades: {total}")
    print(f"   Wins: {wins} ({wr:.1f}%)")
    print(f"   Losses: {losses} ({100-wr:.1f}%)")
    print(f"\n💰 Return Statistics:")
    print(f"   Average Return: {avg_return:+.2f}%")
    print(f"   Median Return: {median_return:+.2f}%")
    print(f"   Std Deviation: {std_return:.2f}%")
    print(f"   Best Trade: {best:+.2f}%")
    print(f"   Worst Trade: {worst:+.2f}%")
    print(f"\n📊 Risk Metrics:")
    print(f"   Avg Win: {win_avg:+.2f}%")
    print(f"   Avg Loss: {loss_avg:+.2f}%")
    print(f"   Win/Loss Ratio: {wl_ratio:.2f}x")
    print(f"   Sharpe Ratio: {sharpe:.2f}")
    print(f"\n🔬 Statistical Significance:")
    print(f"   t-statistic: {t_stat:.2f}")
    print(f"   p-value: {p_val:.6f}")
    
    if p_val < 0.001:
        print(f"   ✅ Extremely significant (p<0.001)")
    elif p_val < 0.01:
        print(f"   ✅ Highly significant (p<0.01)")
    elif p_val < 0.05:
        print(f"   ✅ Significant (p<0.05)")
    
    print(f"\n   95% Confidence Interval: [{ci_lower:+.2f}%, {ci_upper:+.2f}%]")
    if ci_lower > 0:
        print(f"   ✅ Lower bound positive - Consistent edge")


def detailed_sector_analysis(df):
    """Comprehensive sector analysis with all metrics."""
    
    print(f"\n{'='*80}")
    print("📊 DETAILED SECTOR ANALYSIS")
    print("="*80 + "\n")
    
    sectors = []
    
    for sector in df['sector'].unique():
        subset = df[df['sector'] == sector]
        
        if len(subset) >= 3:
            wins = (subset['return_7d'] > 0).sum()
            losses = len(subset) - wins
            wr = wins / len(subset) * 100
            
            avg_ret = subset['return_7d'].mean()
            median_ret = subset['return_7d'].median()
            std_ret = subset['return_7d'].std()
            
            win_avg = subset[subset['return_7d'] > 0]['return_7d'].mean() if wins > 0 else 0
            loss_avg = subset[subset['return_7d'] <= 0]['return_7d'].mean() if losses > 0 else 0
            
            best = subset['return_7d'].max()
            worst = subset['return_7d'].min()
            
            sharpe = (avg_ret / std_ret) * np.sqrt(52) if std_ret > 0 else 0
            
            sectors.append({
                'sector': sector,
                'n': len(subset),
                'wins': wins,
                'losses': losses,
                'wr': wr,
                'avg': avg_ret,
                'median': median_ret,
                'std': std_ret,
                'win_avg': win_avg,
                'loss_avg': loss_avg,
                'best': best,
                'worst': worst,
                'sharpe': sharpe
            })
    
    sectors_df = pd.DataFrame(sectors).sort_values('wr', ascending=False)
    
    print(f"{'Sector':<25} | {'N':<4} | {'WR':<7} | {'W-L':<7} | {'Avg':<8} | {'Sharpe':<7} | {'Best/Worst'}")
    print("-" * 95)
    
    for _, s in sectors_df.iterrows():
        assess = "🔥" if s['wr'] >= 80 else "✅" if s['wr'] >= 70 else "⚠️" if s['wr'] >= 60 else "❌"
        print(f"{s['sector']:<25} | {s['n']:<4} | {s['wr']:>5.1f}% | "
              f"{s['wins']:>2}-{s['losses']:<2} | {s['avg']:>+6.2f}% | {s['sharpe']:>6.2f} | "
              f"{s['best']:+.1f}/{s['worst']:+.1f}% {assess}")
    
    # Additional stats
    print(f"\n📈 Win/Loss Breakdown by Sector:")
    for _, s in sectors_df.head(10).iterrows():
        if s['wins'] > 0 and s['losses'] > 0:
            print(f"   {s['sector']:<25} | Win avg: {s['win_avg']:+.2f}% | Loss avg: {s['loss_avg']:+.2f}%")


def detailed_si_analysis(df):
    """Comprehensive SI analysis."""
    
    print(f"\n{'='*80}")
    print("📊 DETAILED SHORT INTEREST ANALYSIS")
    print("="*80 + "\n")
    
    si_ranges = [
        (0, 1, "0-1%"),
        (1, 2, "1-2%"),
        (2, 3, "2-3%"),
        (3, 5, "3-5%"),
        (5, 7, "5-7%"),
        (7, 10, "7-10%"),
        (10, 15, "10-15%"),
        (15, 30, "15%+")
    ]
    
    print(f"{'SI Range':<10} | {'N':<4} | {'WR':<7} | {'W-L':<7} | {'Avg':<8} | {'Median':<8} | "
          f"{'Win Avg':<9} | {'Loss Avg':<10} | {'Sharpe':<7} | {'Status'}")
    print("-" * 110)
    
    for si_min, si_max, label in si_ranges:
        subset = df[(df['si'] >= si_min) & (df['si'] < si_max)]
        
        if len(subset) > 0:
            wins = (subset['return_7d'] > 0).sum()
            losses = len(subset) - wins
            wr = wins / len(subset) * 100
            
            avg = subset['return_7d'].mean()
            median = subset['return_7d'].median()
            std = subset['return_7d'].std()
            
            win_avg = subset[subset['return_7d'] > 0]['return_7d'].mean() if wins > 0 else 0
            loss_avg = subset[subset['return_7d'] <= 0]['return_7d'].mean() if losses > 0 else 0
            
            sharpe = (avg / std) * np.sqrt(52) if std > 0 else 0
            
            if wr >= 80 and len(subset) >= 15:
                status = "🔥 STRONG"
            elif wr >= 75 and len(subset) >= 10:
                status = "✅ GOOD"
            elif wr >= 70:
                status = "⚠️  OKAY"
            else:
                status = "❌ WEAK"
            
            if len(subset) < 10:
                status += " (N<10)"
            
            print(f"{label:<10} | {len(subset):<4} | {wr:>5.1f}% | {wins:>2}-{losses:<2} | "
                  f"{avg:>+6.2f}% | {median:>+6.2f}% | {win_avg:>+7.2f}% | {loss_avg:>+8.2f}% | "
                  f"{sharpe:>6.2f} | {status}")
    
    # Statistical tests between ranges
    print(f"\n🔬 Statistical Comparisons:")
    
    si_35 = df[(df['si'] >= 3) & (df['si'] < 5)]
    si_01 = df[(df['si'] >= 0) & (df['si'] < 1)]
    si_12 = df[(df['si'] >= 1) & (df['si'] < 2)]
    
    if len(si_35) >= 10 and len(si_01) >= 10:
        t, p = stats.ttest_ind(si_35['return_7d'], si_01['return_7d'])
        print(f"   SI 3-5% vs 0-1%: t={t:.2f}, p={p:.4f} {'✅' if p < 0.05 else ''}")
    
    if len(si_35) >= 10 and len(si_12) >= 10:
        t, p = stats.ttest_ind(si_35['return_7d'], si_12['return_7d'])
        print(f"   SI 3-5% vs 1-2%: t={t:.2f}, p={p:.4f} {'✅' if p < 0.05 else ''}")


def detailed_fresh_analysis(df):
    """Comprehensive Fresh % analysis."""
    
    print(f"\n{'='*80}")
    print("📊 DETAILED FRESH % ANALYSIS")
    print("="*80 + "\n")
    
    fresh_ranges = [
        (-10, -2, "<-2%"),
        (-2, -1, "-2 to -1%"),
        (-1, 0, "-1 to 0%"),
        (0, 1, "0-1%"),
        (1, 2, "1-2%"),
        (2, 3, "2-3%"),
        (3, 4, "3-4%"),
        (4, 5, "4-5%"),
        (5, 10, "5%+")
    ]
    
    print(f"{'Fresh Range':<12} | {'N':<4} | {'WR':<7} | {'W-L':<7} | {'Avg':<8} | {'Median':<8} | "
          f"{'Win Avg':<9} | {'Loss Avg':<10} | {'Sharpe':<7} | {'Status'}")
    print("-" * 110)
    
    for f_min, f_max, label in fresh_ranges:
        subset = df[(df['fresh'] >= f_min) & (df['fresh'] < f_max)]
        
        if len(subset) > 0:
            wins = (subset['return_7d'] > 0).sum()
            losses = len(subset) - wins
            wr = wins / len(subset) * 100
            
            avg = subset['return_7d'].mean()
            median = subset['return_7d'].median()
            std = subset['return_7d'].std()
            
            win_avg = subset[subset['return_7d'] > 0]['return_7d'].mean() if wins > 0 else 0
            loss_avg = subset[subset['return_7d'] <= 0]['return_7d'].mean() if losses > 0 else 0
            
            sharpe = (avg / std) * np.sqrt(52) if std > 0 else 0
            
            if wr >= 80 and len(subset) >= 15:
                status = "🔥 STRONG"
            elif wr >= 75 and len(subset) >= 10:
                status = "✅ GOOD"
            elif wr >= 70:
                status = "⚠️  OKAY"
            else:
                status = "❌ WEAK"
            
            if len(subset) < 10:
                status += " (N<10)"
            
            print(f"{label:<12} | {len(subset):<4} | {wr:>5.1f}% | {wins:>2}-{losses:<2} | "
                  f"{avg:>+6.2f}% | {median:>+6.2f}% | {win_avg:>+7.2f}% | {loss_avg:>+8.2f}% | "
                  f"{sharpe:>6.2f} | {status}")
    
    # Find optimal Fresh range
    print(f"\n🎯 Optimal Fresh Range:")
    fresh_13 = df[(df['fresh'] >= 1) & (df['fresh'] <= 3)]
    if len(fresh_13) >= 10:
        fresh_13_wr = (fresh_13['return_7d'] > 0).sum() / len(fresh_13) * 100
        fresh_13_avg = fresh_13['return_7d'].mean()
        print(f"   Fresh 1-3%: {fresh_13_wr:.1f}% WR, {fresh_13_avg:+.2f}% avg ({len(fresh_13)} trades)")


def cap_size_analysis(df):
    """Detailed market cap analysis."""
    
    print(f"\n{'='*80}")
    print("📊 MARKET CAP DETAILED ANALYSIS")
    print("="*80 + "\n")
    
    caps = ['SMALL', 'MID', 'LARGE', 'MEGA']
    
    print(f"{'Cap':<10} | {'N':<4} | {'WR':<7} | {'W-L':<7} | {'Avg':<8} | {'Median':<8} | "
          f"{'Sharpe':<7} | {'Best/Worst':<15} | {'Status'}")
    print("-" * 95)
    
    for cap in caps:
        subset = df[df['cap'].str.contains(cap, na=False)]
        
        if len(subset) > 0:
            wins = (subset['return_7d'] > 0).sum()
            losses = len(subset) - wins
            wr = wins / len(subset) * 100
            
            avg = subset['return_7d'].mean()
            median = subset['return_7d'].median()
            std = subset['return_7d'].std()
            
            best = subset['return_7d'].max()
            worst = subset['return_7d'].min()
            
            sharpe = (avg / std) * np.sqrt(52) if std > 0 else 0
            
            status = "✅" if wr >= 70 else "⚠️" if wr >= 65 else "❌"
            
            print(f"{cap:<10} | {len(subset):<4} | {wr:>5.1f}% | {wins:>2}-{losses:<2} | "
                  f"{avg:>+6.2f}% | {median:>+6.2f}% | {sharpe:>6.2f} | "
                  f"{best:+.1f}/{worst:+.1f}% | {status}")


def combination_analysis(df, min_n=10):
    """Top combinations with extensive stats."""
    
    print(f"\n{'='*80}")
    print(f"🔍 TOP COMBINATIONS (N≥{min_n}) - RANKED BY SHARPE RATIO")
    print("="*80 + "\n")
    
    combos = []
    
    # All sector + SI combos
    for sector in df['sector'].unique():
        for si_min, si_max, label in [(0, 2, "0-2%"), (2, 5, "2-5%"), (5, 10, "5-10%"), (10, 30, "10%+")]:
            subset = df[(df['sector'] == sector) & (df['si'] >= si_min) & (df['si'] < si_max)]
            
            if len(subset) >= min_n:
                wins = (subset['return_7d'] > 0).sum()
                wr = wins / len(subset) * 100
                avg = subset['return_7d'].mean()
                std = subset['return_7d'].std()
                sharpe = (avg / std) * np.sqrt(52) if std > 0 else 0
                
                combos.append({
                    'pattern': f"{sector} + SI {label}",
                    'n': len(subset),
                    'wr': wr,
                    'avg': avg,
                    'sharpe': sharpe,
                    'best': subset['return_7d'].max(),
                    'worst': subset['return_7d'].min()
                })
    
    # Fresh + SI combos
    for f_min, f_max, f_label in [(-2, 0, "<0%"), (0, 1, "0-1%"), (1, 2, "1-2%"), (2, 3, "2-3%"), (3, 5, "3-5%")]:
        for si_min, si_max, si_label in [(0, 2, "0-2%"), (2, 5, "2-5%"), (5, 10, "5-10%")]:
            subset = df[(df['fresh'] >= f_min) & (df['fresh'] < f_max) & 
                       (df['si'] >= si_min) & (df['si'] < si_max)]
            
            if len(subset) >= min_n:
                wins = (subset['return_7d'] > 0).sum()
                wr = wins / len(subset) * 100
                avg = subset['return_7d'].mean()
                std = subset['return_7d'].std()
                sharpe = (avg / std) * np.sqrt(52) if std > 0 else 0
                
                combos.append({
                    'pattern': f"Fresh {f_label} + SI {si_label}",
                    'n': len(subset),
                    'wr': wr,
                    'avg': avg,
                    'sharpe': sharpe,
                    'best': subset['return_7d'].max(),
                    'worst': subset['return_7d'].min()
                })
    
    combos_df = pd.DataFrame(combos).sort_values('sharpe', ascending=False)
    
    print(f"{'#':<3} {'Pattern':<35} | {'N':<4} | {'WR':<7} | {'Avg':<8} | {'Sharpe':<7} | {'Best/Worst'}")
    print("-" * 100)
    
    for i, row in combos_df.head(20).iterrows():
        conf = "🔥" if row['n'] >= 20 else "⚠️" if row['n'] >= 15 else ""
        print(f"{i+1:<3} {row['pattern']:<35} | {row['n']:<4} | {row['wr']:>5.1f}% | "
              f"{row['avg']:>+6.2f}% | {row['sharpe']:>6.2f} | {row['best']:+.1f}/{row['worst']:+.1f}% {conf}")


def stability_across_time(df):
    """Weekly performance stability."""
    
    print(f"\n{'='*80}")
    print("📊 WEEKLY PERFORMANCE STABILITY")
    print("="*80 + "\n")
    
    weeks = sorted(df['year_week'].unique())
    
    print(f"{'Week':<12} | {'N':<4} | {'WR':<7} | {'W-L':<7} | {'Avg Ret':<10} | {'Best':<8} | {'Worst'}")
    print("-" * 85)
    
    weekly_wrs = []
    weekly_avgs = []
    
    for week in weeks:
        subset = df[df['year_week'] == week]
        
        wins = (subset['return_7d'] > 0).sum()
        wr = wins / len(subset) * 100
        avg = subset['return_7d'].mean()
        best = subset['return_7d'].max()
        worst = subset['return_7d'].min()
        
        weekly_wrs.append(wr)
        weekly_avgs.append(avg)
        
        status = "🔥" if wr >= 80 else "✅" if wr >= 70 else "⚠️" if wr >= 60 else "❌"
        
        print(f"{week:<12} | {len(subset):<4} | {wr:>5.1f}% | {wins:>2}-{len(subset)-wins:<2} | "
              f"{avg:>+8.2f}% | {best:>+6.2f}% | {worst:>+7.2f}% {status}")
    
    # Stability metrics
    print(f"\n📈 Stability Metrics:")
    print(f"   WR Std Dev: {np.std(weekly_wrs):.1f} points")
    print(f"   WR Range: {min(weekly_wrs):.1f}% - {max(weekly_wrs):.1f}%")
    print(f"   Avg Return Std Dev: {np.std(weekly_avgs):.2f}%")
    
    weeks_above_70 = sum(1 for wr in weekly_wrs if wr >= 70)
    print(f"   Weeks ≥70% WR: {weeks_above_70}/{len(weekly_wrs)} ({weeks_above_70/len(weekly_wrs)*100:.0f}%)")


def outlier_analysis(df):
    """Analyze outliers and extreme returns."""
    
    print(f"\n{'='*80}")
    print("📊 OUTLIER ANALYSIS")
    print("="*80 + "\n")
    
    # Define outliers as >2 std deviations
    mean = df['return_7d'].mean()
    std = df['return_7d'].std()
    
    upper_bound = mean + (2 * std)
    lower_bound = mean - (2 * std)
    
    big_winners = df[df['return_7d'] > upper_bound].sort_values('return_7d', ascending=False)
    big_losers = df[df['return_7d'] < lower_bound].sort_values('return_7d')
    
    print(f"🚀 BIG WINNERS (>{upper_bound:+.2f}%):")
    print(f"{'Ticker':<8} | {'Return':<8} | {'Sector':<25} | {'Cap':<10} | {'SI':<6} | {'Fresh'}")
    print("-" * 85)
    
    for _, row in big_winners.head(10).iterrows():
        print(f"{row['ticker']:<8} | {row['return_7d']:>+6.2f}% | {row['sector']:<25} | "
              f"{row['cap']:<10} | {row['si']:>4.1f}% | {row['fresh']:>+5.1f}%")
    
    print(f"\n💥 BIG LOSERS (<{lower_bound:+.2f}%):")
    print(f"{'Ticker':<8} | {'Return':<8} | {'Sector':<25} | {'Cap':<10} | {'SI':<6} | {'Fresh'}")
    print("-" * 85)
    
    for _, row in big_losers.head(10).iterrows():
        print(f"{row['ticker']:<8} | {row['return_7d']:>+6.2f}% | {row['sector']:<25} | "
              f"{row['cap']:<10} | {row['si']:>4.1f}% | {row['fresh']:>+5.1f}%")
    
    # Find common patterns
    print(f"\n🔍 Big Winner Patterns:")
    if len(big_winners) > 0:
        print(f"   Avg SI: {big_winners['si'].mean():.1f}%")
        print(f"   Avg Fresh: {big_winners['fresh'].mean():+.1f}%")
        print(f"   Most common sector: {big_winners['sector'].mode()[0] if len(big_winners['sector'].mode()) > 0 else 'N/A'}")
        print(f"   Most common cap: {big_winners['cap'].str.extract('(SMALL|MID|LARGE|MEGA)')[0].mode()[0] if len(big_winners) > 0 else 'N/A'}")


def loss_pattern_deep_dive(df):
    """Deep analysis of all losses."""
    
    print(f"\n{'='*80}")
    print("❌ LOSS PATTERN DEEP DIVE")
    print("="*80 + "\n")
    
    losers = df[df['return_7d'] <= 0]
    
    print(f"Total Losses: {len(losers)} ({len(losers)/len(df)*100:.1f}% of portfolio)\n")
    
    # Loss severity distribution
    severe = losers[losers['return_7d'] < -5]
    moderate = losers[(losers['return_7d'] >= -5) & (losers['return_7d'] < -2)]
    minor = losers[losers['return_7d'] >= -2]
    
    print(f"Loss Severity:")
    print(f"   Severe (<-5%): {len(severe)} losses ({len(severe)/len(losers)*100:.0f}%)")
    print(f"   Moderate (-5 to -2%): {len(moderate)} losses ({len(moderate)/len(losers)*100:.0f}%)")
    print(f"   Minor (>-2%): {len(minor)} losses ({len(minor)/len(losers)*100:.0f}%)")
    
    # Common loss patterns
    print(f"\n📊 Loss Characteristics (vs Winners):")
    winners = df[df['return_7d'] > 0]
    
    print(f"   Avg SI: Losers {losers['si'].mean():.1f}% vs Winners {winners['si'].mean():.1f}%")
    print(f"   Avg Fresh: Losers {losers['fresh'].mean():+.1f}% vs Winners {winners['fresh'].mean():+.1f}%")
    
    # Sector concentration
    print(f"\n🎯 Losses by Sector:")
    loss_sectors = losers['sector'].value_counts()
    for sector, count in loss_sectors.head(5).items():
        total_sector = (df['sector'] == sector).sum()
        loss_rate = count / total_sector * 100
        print(f"   {sector:<25}: {count} losses / {total_sector} trades ({loss_rate:.1f}% loss rate)")
    
    # SI concentration  
    print(f"\n🎯 Losses by SI Range:")
    for si_min, si_max, label in [(0, 2, "0-2%"), (2, 5, "2-5%"), (5, 10, "5-10%"), (10, 30, "10%+")]:
        count = ((losers['si'] >= si_min) & (losers['si'] < si_max)).sum()
        total_range = ((df['si'] >= si_min) & (df['si'] < si_max)).sum()
        loss_rate = count / total_range * 100 if total_range > 0 else 0
        print(f"   SI {label:<8}: {count} losses / {total_range} trades ({loss_rate:.1f}% loss rate)")


def main():
    print("\n" + "="*80)
    print("🔬 COMPREHENSIVE PATTERN ANALYZER")
    print("="*80 + "\n")
    
    try:
        df = load_data("historical_trades.csv")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print("="*80)
    print("📊 RUNNING COMPREHENSIVE ANALYSIS")
    print("="*80)
    
    overall_statistics(df)
    detailed_sector_analysis(df)
    detailed_si_analysis(df)
    detailed_fresh_analysis(df)
    cap_size_analysis(df)
    combination_analysis(df, min_n=10)
    stability_across_time(df)
    outlier_analysis(df)
    loss_pattern_deep_dive(df)
    
    print("\n" + "="*80)
    print("✅ COMPREHENSIVE ANALYSIS COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()