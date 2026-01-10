"""
Small-Cap Performance Analyzer

Tests: Under what conditions do small-cap stocks actually work?

Analyzes:
- Fresh % ranges (sweet spots for small-caps)
- SI zones (do high SI small-caps work?)
- Sector combos (Healthcare small vs Tech small)
- Institutional ownership (low inst small-caps better?)
- Buzz levels (explosive buzz small-caps)

Goal: Find if there's a subset of small-caps worth keeping.
"""
import pandas as pd
import numpy as np

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
    
    df['date'] = pd.to_datetime(df['Date'])
    df['ticker'] = df['Ticker']
    df['sector'] = df['Sector']
    df['cap'] = df['Market Cap']
    
    # Parse SI and Fresh column by column (not whole series)
    si_values = []
    fresh_values = []
    
    for idx, row in df.iterrows():
        si_values.append(parse_percentage(row['Short Interest']))
        fresh_values.append(parse_percentage(row['Past week 7d%']))
    
    df['si'] = si_values
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
    df = df[df['return_7d'] != 0].copy()
    
    print(f"✅ {len(df)} trades loaded\n")
    
    return df


def analyze_small_caps(df):
    """Deep dive into small-cap performance."""
    
    print("="*80)
    print("🔬 SMALL-CAP DEEP DIVE (What Makes Them Work?)")
    print("="*80 + "\n")
    
    # Filter to small-caps only
    small = df[df['cap'].str.contains('SMALL', na=False, case=False)].copy()
    
    if len(small) < 10:
        print("⚠️  Insufficient small-cap data (N<10)")
        return
    
    wins = len(small[small['return_7d'] > 0])
    losses = len(small) - wins
    wr = wins / len(small) * 100
    avg = small['return_7d'].mean()
    
    print(f"Small-Cap Overall: {len(small)} trades | {wins}-{losses} ({wr:.1f}% WR) | {avg:+.2f}% avg\n")
    
    # Test 1: Fresh % ranges
    print("="*80)
    print("📊 SMALL-CAP BY FRESH %")
    print("="*80 + "\n")
    
    fresh_buckets = [
        (-5, -2, "Very Negative"),
        (-2, 0, "Slightly Negative"),
        (0, 1, "Flat to +1%"),
        (1, 2, "Sweet Spot 1-2%"),
        (2, 3, "2-3%"),
        (3, 5, "Hot 3-5%")
    ]
    
    print(f"{'Fresh Range':<20} | {'N':<4} | {'W-L':<7} | {'WR':<8} | {'Avg Ret'}")
    print("-" * 65)
    
    for min_f, max_f, label in fresh_buckets:
        bucket = small[(small['fresh'] >= min_f) & (small['fresh'] < max_f)]
        
        if len(bucket) >= 3:
            w = len(bucket[bucket['return_7d'] > 0])
            wr_b = w / len(bucket) * 100
            avg_b = bucket['return_7d'].mean()
            
            status = "✅" if wr_b > 65 else "⚠️" if wr_b > 55 else "❌"
            
            print(f"{label:<20} | {len(bucket):<4} | {w}-{len(bucket)-w:<4} | {wr_b:>6.0f}% | {avg_b:>+7.2f}% {status}")
    
    # Test 2: Short Interest
    print(f"\n{'='*80}")
    print("📊 SMALL-CAP BY SHORT INTEREST")
    print("="*80 + "\n")
    
    si_buckets = [
        (0, 2, "Very Low <2%"),
        (2, 5, "Low 2-5%"),
        (5, 10, "Medium 5-10%"),
        (10, 20, "High 10-20%")
    ]
    
    print(f"{'SI Range':<20} | {'N':<4} | {'W-L':<7} | {'WR':<8} | {'Avg Ret'}")
    print("-" * 65)
    
    for min_si, max_si, label in si_buckets:
        bucket = small[(small['si'] >= min_si) & (small['si'] < max_si)]
        
        if len(bucket) >= 3:
            w = len(bucket[bucket['return_7d'] > 0])
            wr_b = w / len(bucket) * 100
            avg_b = bucket['return_7d'].mean()
            
            status = "✅" if wr_b > 65 else "⚠️" if wr_b > 55 else "❌"
            
            print(f"{label:<20} | {len(bucket):<4} | {w}-{len(bucket)-w:<4} | {wr_b:>6.0f}% | {avg_b:>+7.2f}% {status}")
    
    # Test 3: Sector combos
    print(f"\n{'='*80}")
    print("📊 SMALL-CAP BY SECTOR")
    print("="*80 + "\n")
    
    sectors = small.groupby('sector').size().sort_values(ascending=False)
    
    print(f"{'Sector':<25} | {'N':<4} | {'W-L':<7} | {'WR':<8} | {'Avg Ret'}")
    print("-" * 70)
    
    for sector in sectors.index:
        bucket = small[small['sector'] == sector]
        
        if len(bucket) >= 2:
            w = len(bucket[bucket['return_7d'] > 0])
            wr_b = w / len(bucket) * 100
            avg_b = bucket['return_7d'].mean()
            
            status = "✅" if wr_b > 65 else "⚠️" if wr_b > 55 else "❌"
            
            print(f"{sector:<25} | {len(bucket):<4} | {w}-{len(bucket)-w:<4} | {wr_b:>6.0f}% | {avg_b:>+7.2f}% {status}")
    
    # Test 4: Golden combo (if exists)
    print(f"\n{'='*80}")
    print("🔍 SMALL-CAP GOLDEN COMBINATIONS")
    print("="*80 + "\n")
    
    # Test specific combos
    combos = [
        ("Fresh 1-2% + SI 5-10%", (small['fresh'] >= 1) & (small['fresh'] <= 2) & (small['si'] >= 5) & (small['si'] <= 10)),
        ("Fresh 0-1% + SI 3-7%", (small['fresh'] >= 0) & (small['fresh'] <= 1) & (small['si'] >= 3) & (small['si'] <= 7)),
        ("Basic Materials sector", small['sector'] == 'Basic Materials'),
        ("Healthcare sector", small['sector'] == 'Healthcare'),
    ]
    
    found_golden = False
    
    for combo_name, condition in combos:
        bucket = small[condition]
        
        if len(bucket) >= 3:
            w = len(bucket[bucket['return_7d'] > 0])
            wr_b = w / len(bucket) * 100
            avg_b = bucket['return_7d'].mean()
            
            print(f"{combo_name}:")
            print(f"   {len(bucket)} trades | {w}-{len(bucket)-w} ({wr_b:.0f}% WR) | {avg_b:+.2f}% avg")
            
            if wr_b >= 70:
                print(f"   🟢 FOUND: This combo works for small-caps!\n")
                found_golden = True
            else:
                print(f"   ❌ Still weak\n")
    
    if not found_golden:
        print("❌ No golden combination found for small-caps")
        print("   Recommendation: BAN ENTIRELY\n")


def recommendation(df):
    """Final recommendation."""
    
    print("="*80)
    print("🎯 RECOMMENDATION")
    print("="*80 + "\n")
    
    small = df[df['cap'].str.contains('SMALL', na=False, case=False)]
    
    if len(small) == 0:
        print("⚠️  No small-cap data to analyze")
        return
    
    wr = len(small[small['return_7d'] > 0]) / len(small) * 100
    
    # Check if ANY condition produces >70% WR
    best_condition = None
    best_wr = 0
    
    # Test various conditions
    conditions = {
        'Fresh 1-2%': (small['fresh'] >= 1) & (small['fresh'] <= 2),
        'SI 5-10%': (small['si'] >= 5) & (small['si'] <= 10),
        'Basic Materials': small['sector'] == 'Basic Materials',
    }
    
    for name, cond in conditions.items():
        subset = small[cond]
        if len(subset) >= 3:
            subset_wr = len(subset[subset['return_7d'] > 0]) / len(subset) * 100
            if subset_wr > best_wr:
                best_wr = subset_wr
                best_condition = name
    
    print(f"Small-Cap Overall WR: {wr:.1f}%")
    
    if best_wr >= 70:
        print(f"\n✅ KEEP SMALL-CAPS with condition: {best_condition} ({best_wr:.0f}% WR)")
        print(f"   Add filter: Only small-caps that meet this condition")
    else:
        print(f"\n❌ BAN SMALL-CAPS ENTIRELY")
        print(f"   Best condition ({best_condition}) only achieves {best_wr:.0f}% WR")
        print(f"   Not worth the complexity")
        print(f"\n   Implementation:")
        print(f"   MIN_MARKET_CAP = 2_000_000_000  # $2B minimum (Mid-cap+)")


def main():
    print("\n" + "="*80)
    print("🔬 SMALL-CAP PERFORMANCE ANALYZER")
    print("="*80 + "\n")
    
    print("Question: Do small-caps work under ANY conditions?")
    print("Goal: Find if there's a profitable small-cap subset\n")
    
    try:
        df = load_data("historical_trades.csv")
        analyze_small_caps(df)
        recommendation(df)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()