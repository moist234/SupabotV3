"""
Supabot V3: Winner Pattern Discovery Tool - FULL ANALYSIS

Complete pattern discovery on correct 71.9% WR data
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy import stats
from collections import defaultdict

def parse_percentage(val):
    """Convert percentage string to float."""
    if pd.isna(val) or val == '' or val == 'nan':
        return 0.0
    val_str = str(val).replace('%', '').replace('+', '').replace('$', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0


def load_and_clean_data(csv_path="historical_trades.csv"):
    """Load CSV using correct column parsing."""
    
    print("📂 Loading historical trades...")
    
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
        if 'Win Rate' in date_val or 'Average' in date_val or date_val == '':
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
    df['v3_score_num'] = pd.to_numeric(df['V3Score'], errors='coerce').fillna(0)
    df['short_interest_num'] = df['Short Interest'].apply(parse_percentage)
    df['fresh_num'] = df['Past week 7d%'].apply(parse_percentage)
    df['twitter_num'] = pd.to_numeric(df['Twitter'], errors='coerce').fillna(0)
    df['reddit_num'] = pd.to_numeric(df['Reddit'], errors='coerce').fillna(0)
    
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
    df = df[df['return_num'] != 0].copy()
    
    df['week'] = df['date_parsed'].dt.isocalendar().week
    df['year_week'] = df['date_parsed'].dt.strftime('%Y-W%U')
    
    wins = (df['return_num'] > 0).sum()
    losses = (df['return_num'] <= 0).sum()
    wr = wins / len(df) * 100
    
    print(f"✅ {len(df)} trades | {wr:.1f}% WR ({wins}W-{losses}L)\n")
    
    return df


def analyze_winners_vs_losers(df):
    """Compare winners vs losers."""
    
    print(f"{'='*70}")
    print(f"🎯 WINNERS VS LOSERS COMPARISON")
    print(f"{'='*70}\n")
    
    winners = df[df['return_num'] > 0]
    losers = df[df['return_num'] <= 0]
    
    print(f"Winners: {len(winners)} | Avg: {winners['return_num'].mean():+.2f}%")
    print(f"Losers:  {len(losers)} | Avg: {losers['return_num'].mean():+.2f}%\n")
    
    metrics = {
        'Short Interest': 'short_interest_num',
        'Fresh %': 'fresh_num',
        'Twitter': 'twitter_num',
        'V3 Score': 'v3_score_num'
    }
    
    print(f"{'Metric':<20} | {'Winners':<10} | {'Losers':<10} | {'Diff':<10} | p-value")
    print("-" * 70)
    
    for name, col in metrics.items():
        w_avg = winners[col].mean()
        l_avg = losers[col].mean()
        diff = w_avg - l_avg
        t_stat, p_val = stats.ttest_ind(winners[col], losers[col])
        sig = "✅" if p_val < 0.05 else ""
        print(f"{name:<20} | {w_avg:>9.2f} | {l_avg:>9.2f} | {diff:>+9.2f} | {p_val:.4f} {sig}")
    
    return winners, losers


def find_winning_combinations(df, min_trades=10):
    """Find high-WR combinations."""
    
    print(f"\n{'='*70}")
    print(f"🔍 WINNING COMBINATIONS (N≥{min_trades})")
    print(f"{'='*70}\n")
    
    combos = []
    
    # Sector + SI
    sectors = df['sector'].unique()
    si_ranges = [(0, 2, "0-2%"), (2, 5, "2-5%"), (5, 10, "5-10%"), (10, 20, "10%+")]
    
    for sector in sectors:
        for si_min, si_max, label in si_ranges:
            subset = df[(df['sector'] == sector) & 
                       (df['short_interest_num'] >= si_min) & 
                       (df['short_interest_num'] < si_max)]
            
            if len(subset) >= min_trades:
                wins = (subset['return_num'] > 0).sum()
                wr = wins / len(subset) * 100
                combos.append({
                    'pattern': f"{sector} + SI {label}",
                    'n': len(subset),
                    'wr': wr,
                    'wins': wins,
                    'avg': subset['return_num'].mean()
                })
    
    # Cap + SI
    for cap in ['SMALL', 'MID', 'LARGE', 'MEGA']:
        for si_min, si_max, label in si_ranges:
            subset = df[(df['cap'].str.contains(cap, na=False)) & 
                       (df['short_interest_num'] >= si_min) & 
                       (df['short_interest_num'] < si_max)]
            
            if len(subset) >= min_trades:
                wins = (subset['return_num'] > 0).sum()
                wr = wins / len(subset) * 100
                combos.append({
                    'pattern': f"{cap} + SI {label}",
                    'n': len(subset),
                    'wr': wr,
                    'wins': wins,
                    'avg': subset['return_num'].mean()
                })
    
    # Fresh + SI
    fresh_ranges = [(-5, 0, "<0%"), (0, 1, "0-1%"), (1, 3, "1-3%"), (3, 5, "3-5%")]
    
    for f_min, f_max, f_label in fresh_ranges:
        for si_min, si_max, si_label in si_ranges:
            subset = df[(df['fresh_num'] >= f_min) & (df['fresh_num'] < f_max) &
                       (df['short_interest_num'] >= si_min) & (df['short_interest_num'] < si_max)]
            
            if len(subset) >= min_trades:
                wins = (subset['return_num'] > 0).sum()
                wr = wins / len(subset) * 100
                combos.append({
                    'pattern': f"Fresh {f_label} + SI {si_label}",
                    'n': len(subset),
                    'wr': wr,
                    'wins': wins,
                    'avg': subset['return_num'].mean()
                })
    
    combos.sort(key=lambda x: (x['wr'], x['avg']), reverse=True)
    
    print(f"{'#':<3} {'Pattern':<35} {'N':<5} {'WR':<8} {'W-L':<8} {'Avg Ret':<10} {'Quality'}")
    print("-" * 85)
    
    for i, c in enumerate(combos[:20], 1):
        conf = "🔥" if c['n'] >= 20 else "⚠️" if c['n'] >= 15 else ""
        print(f"{i:<3} {c['pattern']:<35} {c['n']:<5} {c['wr']:>6.1f}% "
              f"{c['wins']:>2}-{c['n']-c['wins']:<2} {c['avg']:>+8.2f}% {conf}")
    
    return combos


def analyze_sector_performance(df):
    """Detailed sector analysis."""
    
    print(f"\n{'='*70}")
    print(f"📊 SECTOR PERFORMANCE")
    print(f"{'='*70}\n")
    
    sector_stats = []
    
    for sector in df['sector'].unique():
        subset = df[df['sector'] == sector]
        wins = (subset['return_num'] > 0).sum()
        losses = len(subset) - wins
        wr = wins / len(subset) * 100
        avg = subset['return_num'].mean()
        
        sector_stats.append({
            'sector': sector,
            'n': len(subset),
            'wins': wins,
            'losses': losses,
            'wr': wr,
            'avg': avg,
            'best': subset['return_num'].max(),
            'worst': subset['return_num'].min()
        })
    
    sector_stats.sort(key=lambda x: x['wr'], reverse=True)
    
    print(f"{'Sector':<25} | {'N':<5} | {'WR':<8} | {'W-L':<8} | {'Avg Ret':<10} | {'Best/Worst'}")
    print("-" * 90)
    
    for s in sector_stats:
        assess = "✅" if s['wr'] >= 75 else "⚠️" if s['wr'] >= 65 else "❌"
        print(f"{s['sector']:<25} | {s['n']:<5} | {s['wr']:>6.1f}% | "
              f"{s['wins']:>2}-{s['losses']:<2} | {s['avg']:>+8.2f}% | "
              f"{s['best']:+.1f}/{s['worst']:+.1f}% {assess}")
    
    return sector_stats


def analyze_si_ranges(df):
    """Detailed SI analysis."""
    
    print(f"\n{'='*70}")
    print(f"📊 SHORT INTEREST RANGES")
    print(f"{'='*70}\n")
    
    ranges = [
        (0, 1, "0-1%"),
        (1, 2, "1-2%"),
        (2, 3, "2-3%"),
        (3, 5, "3-5%"),
        (5, 7, "5-7%"),
        (7, 10, "7-10%"),
        (10, 15, "10-15%"),
        (15, 30, "15%+")
    ]
    
    print(f"{'SI Range':<10} | {'N':<5} | {'WR':<8} | {'W-L':<8} | {'Avg Ret':<10} | {'Status'}")
    print("-" * 70)
    
    for si_min, si_max, label in ranges:
        subset = df[(df['short_interest_num'] >= si_min) & (df['short_interest_num'] < si_max)]
        
        if len(subset) > 0:
            wins = (subset['return_num'] > 0).sum()
            wr = wins / len(subset) * 100
            avg = subset['return_num'].mean()
            
            if wr >= 80 and len(subset) >= 10:
                status = "🔥 STRONG"
            elif wr >= 75:
                status = "✅ GOOD"
            elif wr >= 65:
                status = "⚠️  OKAY"
            else:
                status = "❌ WEAK"
            
            if len(subset) < 10:
                status += " (small N)"
            
            print(f"{label:<10} | {len(subset):<5} | {wr:>6.1f}% | "
                  f"{wins:>2}-{len(subset)-wins:<2} | {avg:>+8.2f}% | {status}")


def analyze_fresh_ranges(df):
    """Detailed Fresh % analysis."""
    
    print(f"\n{'='*70}")
    print(f"📊 FRESH % RANGES")
    print(f"{'='*70}\n")
    
    ranges = [
        (-10, -2, "<-2%"),
        (-2, 0, "-2 to 0%"),
        (0, 1, "0-1%"),
        (1, 2, "1-2%"),
        (2, 3, "2-3%"),
        (3, 5, "3-5%"),
        (5, 10, "5%+")
    ]
    
    print(f"{'Fresh Range':<12} | {'N':<5} | {'WR':<8} | {'W-L':<8} | {'Avg Ret':<10} | {'Status'}")
    print("-" * 75)
    
    for f_min, f_max, label in ranges:
        subset = df[(df['fresh_num'] >= f_min) & (df['fresh_num'] < f_max)]
        
        if len(subset) > 0:
            wins = (subset['return_num'] > 0).sum()
            wr = wins / len(subset) * 100
            avg = subset['return_num'].mean()
            
            if wr >= 80 and len(subset) >= 10:
                status = "🔥 STRONG"
            elif wr >= 75:
                status = "✅ GOOD"
            elif wr >= 65:
                status = "⚠️  OKAY"
            else:
                status = "❌ WEAK"
            
            if len(subset) < 10:
                status += " (small N)"
            
            print(f"{label:<12} | {len(subset):<5} | {wr:>6.1f}% | "
                  f"{wins:>2}-{len(subset)-wins:<2} | {avg:>+8.2f}% | {status}")


def analyze_cap_performance(df):
    """Market cap analysis."""
    
    print(f"\n{'='*70}")
    print(f"📊 MARKET CAP PERFORMANCE")
    print(f"{'='*70}\n")
    
    caps = ['SMALL', 'MID', 'LARGE', 'MEGA']
    
    print(f"{'Cap':<10} | {'N':<5} | {'WR':<8} | {'W-L':<8} | {'Avg Ret':<10} | {'Status'}")
    print("-" * 70)
    
    for cap in caps:
        subset = df[df['cap'].str.contains(cap, na=False)]
        
        if len(subset) > 0:
            wins = (subset['return_num'] > 0).sum()
            wr = wins / len(subset) * 100
            avg = subset['return_num'].mean()
            
            if wr >= 80 and len(subset) >= 10:
                status = "🔥 STRONG"
            elif wr >= 75:
                status = "✅ GOOD"
            elif wr >= 65:
                status = "⚠️  OKAY"
            else:
                status = "❌ WEAK"
            
            print(f"{cap:<10} | {len(subset):<5} | {wr:>6.1f}% | "
                  f"{wins:>2}-{len(subset)-wins:<2} | {avg:>+8.2f}% | {status}")


def generate_recommendations(df):
    """Generate actionable recommendations."""
    
    print(f"\n{'='*70}")
    print(f"🎯 ACTIONABLE RECOMMENDATIONS")
    print(f"{'='*70}\n")
    
    overall_wr = (df['return_num'] > 0).sum() / len(df) * 100
    
    print(f"📊 Current: {overall_wr:.1f}% WR on {len(df)} trades\n")
    
    recommendations = []
    
    # Test Consumer Defensive ban
    cd_removed = df[df['sector'] != 'Consumer Defensive']
    cd_wr = (cd_removed['return_num'] > 0).sum() / len(cd_removed) * 100
    cd_improvement = cd_wr - overall_wr
    
    if cd_improvement > 1:
        recommendations.append({
            'priority': 1,
            'action': 'BAN Consumer Defensive sector',
            'impact': f'{cd_improvement:+.1f} points',
            'confidence': 'HIGH',
            'reason': f'50% loss rate (4/8 trades)'
        })
    
    # Test SI filters
    si_filtered = df[df['short_interest_num'] >= 2.0]
    si_wr = (si_filtered['return_num'] > 0).sum() / len(si_filtered) * 100
    si_improvement = si_wr - overall_wr
    
    si_removed = df[df['short_interest_num'] < 2.0]
    si_removed_losses = (si_removed['return_num'] <= 0).sum()
    
    if si_improvement > 3 and si_removed_losses >= 9:
        recommendations.append({
            'priority': 2,
            'action': 'ADD SI ≥2% filter',
            'impact': f'{si_improvement:+.1f} points',
            'confidence': 'MEDIUM',
            'reason': f'Removes {si_removed_losses} losses'
        })
    
    # Display recommendations
    if recommendations:
        print("🚀 RECOMMENDED CHANGES:\n")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['action']}")
            print(f"   Impact: {rec['impact']} WR improvement")
            print(f"   Confidence: {rec['confidence']}")
            print(f"   Reason: {rec['reason']}\n")
    else:
        print("✅ No high-confidence improvements identified")
        print("   Continue collecting data through Dec 30\n")
    
    print("⏱️  TIMELINE:")
    print("   Now (Dec 19): Deploy Consumer Defensive ban only")
    print("   Dec 30: Review with 150+ trades")
    print("   Jan 15: Test if patterns persist into new year")


def main():
    print("\n" + "="*70)
    print("🔬 SUPABOT V3: FULL PATTERN DISCOVERY")
    print("="*70 + "\n")
    
    try:
        df = load_and_clean_data("historical_trades.csv")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("="*70)
    print("📊 COMPREHENSIVE ANALYSIS")
    print("="*70)
    
    # Run all analyses
    analyze_winners_vs_losers(df)
    analyze_sector_performance(df)
    analyze_si_ranges(df)
    analyze_fresh_ranges(df)
    analyze_cap_performance(df)
    find_winning_combinations(df, min_trades=10)
    generate_recommendations(df)
    
    print("\n" + "="*70)
    print("✅ PATTERN DISCOVERY COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()