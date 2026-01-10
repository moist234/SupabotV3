"""
V4 Score Attribution Analyzer - Recent Picks Only

Analyzes your recent V4-selected picks (Dec 31, Jan 1, Jan 2)
to see which components are overweighted.
"""

def analyze_recent_picks():
    """Analyze the 17 V4 picks you've made so far."""
    
    print("="*80)
    print("🔬 V4 SCORE ATTRIBUTION - RECENT PICKS ANALYSIS")
    print("="*80 + "\n")
    
    # Your actual V4 picks with results
    picks = [
        # Dec 31 batch
        {'ticker': 'SKE', 'v4': 125, 'sector': 'Basic Materials', 'cap': 'MID', 'si': 0.0, 'fresh': 0.8, 'return': 5.50},
        {'ticker': 'XENE', 'v4': 123, 'sector': 'Healthcare', 'cap': 'MID', 'si': 8.2, 'fresh': 1.6, 'return': -6.00},
        {'ticker': 'AMRX', 'v4': 120, 'sector': 'Healthcare', 'cap': 'MID', 'si': 2.6, 'fresh': 1.4, 'return': 6.76},
        {'ticker': 'LINE', 'v4': 120, 'sector': 'Real Estate', 'cap': 'MID', 'si': 3.9, 'fresh': 2.9, 'return': 0.00},
        {'ticker': 'CEF', 'v4': 105, 'sector': 'Unknown', 'cap': 'MID', 'si': 0.0, 'fresh': 2.3, 'return': 5.57},
        {'ticker': 'CDE', 'v4': 100, 'sector': 'Basic Materials', 'cap': 'LARGE', 'si': 9.8, 'fresh': -1.8, 'return': 7.53},
        
        # Jan 1 batch
        {'ticker': 'AUGO', 'v4': 125, 'sector': 'Basic Materials', 'cap': 'MID', 'si': 0.0, 'fresh': 0.8, 'return': 1.55},
        {'ticker': 'TWLO', 'v4': 125, 'sector': 'Technology', 'cap': 'LARGE', 'si': 3.3, 'fresh': 0.3, 'return': -3.38},
        {'ticker': 'KTOS', 'v4': 115, 'sector': 'Industrials', 'cap': 'LARGE', 'si': 5.4, 'fresh': 0.7, 'return': 37.06},
        {'ticker': 'REG', 'v4': 115, 'sector': 'Real Estate', 'cap': 'LARGE', 'si': 4.0, 'fresh': 0.7, 'return': 2.29},
        {'ticker': 'ROKU', 'v4': 105, 'sector': 'Communication Services', 'cap': 'LARGE', 'si': 6.3, 'fresh': -0.3, 'return': 0.34},
        
        # Jan 2 batch
        {'ticker': 'JAZZ', 'v4': 128, 'sector': 'Healthcare', 'cap': 'LARGE', 'si': 9.6, 'fresh': 1.8, 'return': -6.74},
        {'ticker': 'AGNC', 'v4': 123, 'sector': 'Real Estate', 'cap': 'LARGE', 'si': 5.5, 'fresh': 2.2, 'return': 4.01},
        {'ticker': 'GRFS', 'v4': 120, 'sector': 'Healthcare', 'cap': 'MID', 'si': 0.0, 'fresh': 1.9, 'return': 3.14},
        {'ticker': 'TDIS', 'v4': 115, 'sector': 'Communication Services', 'cap': 'MID', 'si': 7.8, 'fresh': -0.8, 'return': 1.61},
        {'ticker': 'MIDD', 'v4': 110, 'sector': 'Industrials', 'cap': 'MID', 'si': 5.8, 'fresh': 0.1, 'return': 4.73},
        {'ticker': 'DOW', 'v4': 105, 'sector': 'Basic Materials', 'cap': 'LARGE', 'si': 4.8, 'fresh': 3.9, 'return': 8.22},
    ]
    
    winners = [p for p in picks if p['return'] > 0]
    losers = [p for p in picks if p['return'] < 0]
    
    print(f"Total: {len(picks)} picks | {len(winners)}-{len(losers)} ({len(winners)/len(picks)*100:.0f}% WR)\n")
    
    # SECTOR ANALYSIS
    print("="*80)
    print("📊 SECTOR PERFORMANCE")
    print("="*80 + "\n")
    
    sector_perf = {}
    for p in picks:
        s = p['sector']
        if s not in sector_perf:
            sector_perf[s] = {'wins': 0, 'losses': 0, 'v4s': [], 'returns': []}
        
        sector_perf[s]['v4s'].append(p['v4'])
        sector_perf[s]['returns'].append(p['return'])
        
        if p['return'] > 0:
            sector_perf[s]['wins'] += 1
        else:
            sector_perf[s]['losses'] += 1
    
    print(f"{'Sector':<25} | {'N':<4} | {'W-L':<7} | {'WR':<8} | {'Avg V4':<8} | {'Avg Ret':<10} | {'Status'}")
    print("-" * 90)
    
    for sector in sorted(sector_perf.keys(), key=lambda x: sector_perf[x]['wins'] + sector_perf[x]['losses'], reverse=True):
        stats = sector_perf[sector]
        total = stats['wins'] + stats['losses']
        wr = (stats['wins'] / total * 100) if total > 0 else 0
        avg_v4 = sum(stats['v4s']) / len(stats['v4s'])
        avg_ret = sum(stats['returns']) / len(stats['returns'])
        
        if wr == 0:
            status = "🔴 0% WR"
        elif wr < 50:
            status = "🔴 WEAK"
        elif wr < 75:
            status = "🟡 OKAY"
        else:
            status = "🟢 STRONG"
        
        print(f"{sector:<25} | {total:<4} | {stats['wins']}-{stats['losses']:<4} | {wr:>6.0f}% | {avg_v4:>6.1f} | {avg_ret:>+8.2f}% | {status}")
    
    # HIGH SCORER LOSSES
    print(f"\n{'='*80}")
    print("🔍 ALL LOSSES (What Went Wrong?)")
    print("="*80 + "\n")
    
    for p in losers:
        print(f"{p['ticker']} (V4 {p['v4']}):")
        print(f"   Sector: {p['sector']} ({'Healthcare/Tech gets +10' if p['sector'] in ['Healthcare', 'Technology'] else 'No special boost'})")
        print(f"   Cap: {p['cap']} ({'35 pts' if 'LARGE' in p['cap'] else '25 pts'})")
        print(f"   Fresh: {p['fresh']:+.1f}% | SI: {p['si']:.1f}%")
        print(f"   Return: {p['return']:+.2f}%\n")
    
    # Pattern check
    healthcare_tech_losses = [p for p in losers if p['sector'] in ['Healthcare', 'Technology']]
    
    if len(healthcare_tech_losses) == len(losers):
        print("🔴 SMOKING GUN: ALL 3 LOSSES ARE HEALTHCARE/TECH!")
        print("   These sectors get +10 boost but are causing ALL losses")
        print("   💡 STRONG RECOMMENDATION: Reduce to +5 points\n")
    
    # V4 BUCKETS
    print("="*80)
    print("📊 V4 SCORE BUCKET PERFORMANCE")
    print("="*80 + "\n")
    
    buckets = {
        '100-109': [p for p in picks if 100 <= p['v4'] < 110],
        '110-119': [p for p in picks if 110 <= p['v4'] < 120],
        '120-129': [p for p in picks if 120 <= p['v4'] < 130],
        '130+': [p for p in picks if p['v4'] >= 130]
    }
    
    print(f"{'Bucket':<12} | {'N':<4} | {'W-L':<7} | {'WR':<8} | {'Avg Ret':<12} | {'vs Backtest'}")
    print("-" * 75)
    
    backtest_wr = {
        '100-109': 76.2,
        '110-119': 63.0,
        '120-129': 86.5,
        '130+': 83.3
    }
    
    for name, picks_list in buckets.items():
        if len(picks_list) == 0:
            continue
        
        wins = len([p for p in picks_list if p['return'] > 0])
        losses = len(picks_list) - wins
        wr = wins / len(picks_list) * 100
        avg_ret = sum(p['return'] for p in picks_list) / len(picks_list)
        
        expected = backtest_wr.get(name, 0)
        diff = wr - expected
        
        status = "✅" if diff >= 0 else "❌"
        
        print(f"V4 {name:<9} | {len(picks_list):<4} | {wins}-{losses:<4} | {wr:>6.0f}% | {avg_ret:>+10.2f}% | {diff:>+5.1f} pts {status}")
    
    print(f"\n💡 INTERPRETATION:")
    print(f"   • V4 120-129 expected 86.5% WR, seeing {buckets['120-129'][0]['return'] if buckets['120-129'] else 'N/A'}")
    print(f"   • Sample size small (17 trades) but pattern emerging")
    print(f"   • Healthcare sector: 2-1 but both losses are Healthcare V4 ≥120")


def main():
    print("\n" + "="*80)
    print("🔬 V4 SCORE ATTRIBUTION ANALYZER")
    print("="*80 + "\n")
    
    analyze_recent_picks()
    
    print("\n" + "="*80)
    print("✅ ATTRIBUTION ANALYSIS COMPLETE")
    print("="*80 + "\n")
    
    print("💡 KEY FINDINGS:")
    print("   • Which sectors are underperforming at high V4 scores?")
    print("   • Are Healthcare/Tech +10 boosts causing issues?")
    print("   • Should sector weights be adjusted?")


if __name__ == "__main__":
    main()