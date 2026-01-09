"""
Update Google Sheets with NEW V4 Scores for Dec 9-19 trades

Uses batch update to avoid rate limits
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
from typing import Dict
import time

# Google Sheets setup
SHEET_NAME = "SupabotV3"
TAB_NAME = "Sheet1"
SERVICE_ACCOUNT_FILE = "service_account.json"


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
    """
    V4 scoring - Updated Jan 7, 2025
    Based on 238-trade validation (67.2% WR)
    
    Changes from original V4:
    1. Fresh 1-2% boosted (80.4% WR on 51 trades)
    2. Fresh 4-5% separated (87.5% WR on 16 trades)
    3. Small-cap penalized (46.2% WR, 18-21 record)
    4. Large-cap boosted (77.1% WR, 64-19 record)
    
    Gap: 16.2 points (p<0.0001)
    V4 ≥120: 85.2% WR on 61 trades
    """
    score = 0
    
    # 1. FRESH % (0-50 points) - UPDATED WITH 4-5% SPLIT
    fresh = pick['change_7d']
    if 1.0 <= fresh <= 2.0:
        score += 50  # 80.4% WR (41-10 on 51 trades) - VALIDATED!
    elif 4.0 <= fresh <= 5.0:
        score += 45  # 87.5% WR (14-2 on 16 trades) - STRONG!
    elif 0 <= fresh < 1.0:
        score += 40  # 71.2% WR (47-19 on 66 trades)
    elif 2.0 < fresh <= 3.0:
        score += 35  # 71.4% WR (15-6 on 21 trades)
    elif -2.0 <= fresh < 0:
        score += 20  # 59.5% WR (25-17 on 42 trades)
    elif 3.0 < fresh < 4.0:
        score += 5   # 38.1% WR (8-13 on 21 trades) - TOXIC!
    elif fresh > 5.0:
        score += 10
    else:  # fresh < -2.0
        score += 10
    
    # 2. SHORT INTEREST (0-40 points) - UNCHANGED
    si = pick.get('short_percent', 0)
    if 3.0 <= si <= 7.0:
        score += 40  # 71.9-73.3% WR
    elif 0 <= si < 1.0:
        score += 35  # 78.9% WR (30-8 on 38 trades)
    elif 7.0 < si < 10.0:
        score += 30  # 72.0% WR
    elif 2.0 <= si < 3.0:
        score += 25  # 60.7% WR
    elif 1.0 <= si < 2.0:
        score += 15  # 61.1% WR
    elif 10.0 <= si < 15.0:
        score += 10  # 51.7% WR
    # SI ≥15% gets 0
    
    # 3. MARKET CAP (0-35 points) - UPDATED: LARGE BOOSTED, SMALL PENALIZED
    cap_size = pick['cap_size']
    if 'LARGE' in cap_size.upper():
        score += 35  # 77.1% WR (64-19 on 83 trades) - DOMINANT!
    elif 'MID' in cap_size.upper():
        score += 25  # 67.3% WR (70-34 on 104 trades)
    elif 'MEGA' in cap_size.upper():
        score += 15  # 66.7% WR (8-4 on 12 trades)
    # SMALL gets 0 - 46.2% WR (18-21) LOSES MONEY!
    
    # 4. SECTOR PERFORMANCE (0-25 points) - UPDATED WEIGHTS
    sector = pick['sector']
    if sector == 'Basic Materials':
        score += 25  # 81.5% WR (22-5 on 27 trades)
    elif sector == 'Communication Services':
        score += 20  # 76.0% WR (19-6 on 25 trades)
    elif sector == 'Technology':
        score += 10  # 65.6% WR (21-11)
    elif sector == 'Healthcare':
        score += 10  # 65.0% WR (26-14)
    # Financial Services, Real Estate, Industrials get 0 (~60% WR)
    # Consumer Defensive gets 0 (57% WR, should be banned)
    
    # 5. COMBINATION BONUSES (0-10 points) - UNCHANGED
    if 1.0 <= fresh <= 3.0 and 2.0 <= si <= 5.0:
        score += 10  # Strong validated combo
    elif 1.0 <= fresh <= 3.0 and 5.0 <= si <= 10.0:
        score += 8
     # Volume spike (0-15 points)
    if pick.get('volume_spike'):
        score += 15
    elif pick['volume_ratio'] > 1.0:
        score += 8

    if pick.get('earnings_sweet_spot', False):
        score += 15  # 30-60d window: 88.9% WR
    
    # Market cap (5-15 points)
    if 'Mid' in pick['cap_size'] or 'Large' in pick['cap_size']:
        score += 15
    elif 'Small' in pick['cap_size']:
        score += 10
    else:
        score += 5
        # 7. INSTITUTIONAL OWNERSHIP BOOST (0-10 points)
    inst = pick.get('inst_ownership', 100)
    cap_size = pick['cap_size']

    if inst < 30:
        if 'LARGE' in cap_size.upper() or 'MID' in cap_size.upper():
            score += 10  # Low inst + quality cap = 84-89% WR
        elif 'SMALL' in cap_size.upper():
            score += 5   # Low inst + small cap = still risky
        # MEGA gets 0 even with low inst
    # Inst ≥30% gets 0 (neutral, no penalty)
    
    
    return score


def connect_to_sheet():
    """Connect to Google Sheets."""
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
    return sheet


def find_column_index(headers, search_terms):
    """Find column index by searching for any of the search terms."""
    for i, header in enumerate(headers):
        header_lower = str(header).lower().strip()
        for term in search_terms:
            if term.lower() in header_lower:
                return i
    return None


def update_v4_scores(sheet):
    """Update V4 scores for Dec 9-19 trades using BATCH update."""
    
    print("\n" + "="*70)
    print("🔄 UPDATING V4 SCORES FOR DEC 9-19 TRADES")
    print("="*70 + "\n")
    
    # Get all data
    all_values = sheet.get_all_values()
    
    # Find header row
    header_row = 0
    for i, row in enumerate(all_values):
        if row[0] == 'Date':
            header_row = i
            break
    
    headers = all_values[header_row]
    
    # Find column indices
    date_col = find_column_index(headers, ['Date'])
    ticker_col = find_column_index(headers, ['Ticker'])
    v4_col = find_column_index(headers, ['V4Score', 'V3Score', 'Score'])
    sector_col = find_column_index(headers, ['Sector'])
    cap_col = find_column_index(headers, ['Market Cap', 'Cap'])
    si_col = find_column_index(headers, ['Short Interest', 'SI'])
    fresh_col = find_column_index(headers, ['Past week', '7d%'])
    
    print(f"✅ Found V4 column at position {v4_col+1} ('{headers[v4_col]}')\n")
    
    # Target date range
    start_date = datetime(2025, 12, 9)
    end_date = datetime(2025, 12, 19)
    
    updates = []
    batch_updates = []
    
    print(f"📅 Scanning for trades between {start_date.date()} and {end_date.date()}...\n")
    
    # Collect all updates first
    for i in range(header_row + 1, len(all_values)):
        row = all_values[i]
        
        if not row[date_col]:
            continue
        
        try:
            trade_date = datetime.strptime(row[date_col], '%Y-%m-%d')
        except:
            continue
        
        if start_date <= trade_date <= end_date:
            ticker = row[ticker_col]
            old_v4 = row[v4_col]
            
            pick = {
                'sector': row[sector_col],
                'cap_size': row[cap_col],
                'short_percent': parse_percentage(row[si_col]),
                'change_7d': parse_percentage(row[fresh_col])
            }
            
            new_v4 = calculate_quality_score_v4_new(pick)
            
            row_num = i + 1
            col_letter = chr(65 + v4_col)  # Convert to A, B, C, etc.
            cell_ref = f"{col_letter}{row_num}"
            
            old_v4_num = int(old_v4) if old_v4.isdigit() else 0
            change = new_v4 - old_v4_num
            
            updates.append({
                'date': trade_date.date(),
                'ticker': ticker,
                'old': old_v4_num,
                'new': new_v4,
                'change': change
            })
            
            batch_updates.append({
                'range': cell_ref,
                'values': [[int(new_v4)]]
            })
            
            change_marker = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            print(f"{change_marker} {ticker:6} ({trade_date.date()}) | "
                  f"Old: {old_v4_num:3} → New: {new_v4:3} ({change:+3})")
    
    # Perform batch update
    if batch_updates:
        print(f"\n🔄 Performing batch update of {len(batch_updates)} cells...")
        
        try:
            sheet.batch_update(batch_updates)
            print(f"✅ Batch update complete!")
        except Exception as e:
            print(f"❌ Batch update failed: {e}")
            print(f"   Attempting slower individual updates...")
            
            # Fallback to individual updates with delay
            for i, update in enumerate(batch_updates):
                try:
                    sheet.update(update['range'], update['values'])
                    if (i + 1) % 10 == 0:
                        print(f"   Updated {i+1}/{len(batch_updates)} cells...")
                        time.sleep(1)  # Pause every 10 updates
                except Exception as e2:
                    print(f"   ⚠️  Failed to update {update['range']}: {e2}")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"📊 UPDATE SUMMARY")
    print(f"{'='*70}\n")
    
    if updates:
        print(f"✅ Updated {len(updates)} trades\n")
        
        avg_old = sum(u['old'] for u in updates) / len(updates)
        avg_new = sum(u['new'] for u in updates) / len(updates)
        avg_change = avg_new - avg_old
        
        print(f"Average scores:")
        print(f"   Old V4: {avg_old:.1f}")
        print(f"   New V4: {avg_new:.1f}")
        print(f"   Change: {avg_change:+.1f}")
        
        # Biggest changes
        increases = sorted([u for u in updates if u['change'] > 0], 
                          key=lambda x: x['change'], reverse=True)[:5]
        if increases:
            print(f"\n📈 Biggest increases:")
            for u in increases:
                print(f"   {u['ticker']:6} | {u['old']:3} → {u['new']:3} ({u['change']:+3})")
        
        decreases = sorted([u for u in updates if u['change'] < 0], 
                          key=lambda x: x['change'])[:5]
        if decreases:
            print(f"\n📉 Biggest decreases:")
            for u in decreases:
                print(f"   {u['ticker']:6} | {u['old']:3} → {u['new']:3} ({u['change']:+3})")
        
        # Distribution
        print(f"\n📊 New V4 Score Distribution:")
        high = sum(1 for u in updates if u['new'] >= 100)
        mid = sum(1 for u in updates if 80 <= u['new'] < 100)
        low = sum(1 for u in updates if u['new'] < 80)
        
        print(f"   V4 ≥100: {high} trades ({high/len(updates)*100:.1f}%)")
        print(f"   V4 80-99: {mid} trades ({mid/len(updates)*100:.1f}%)")
        print(f"   V4 <80: {low} trades ({low/len(updates)*100:.1f}%)")
        
    else:
        print("⚠️  No trades found in date range")
    
    print(f"\n{'='*70}")
    print("✅ UPDATE COMPLETE")
    print("="*70 + "\n")


def main():
    print("\n" + "="*70)
    print("🔄 V4 SCORE UPDATER FOR GOOGLE SHEETS")
    print("="*70 + "\n")
    
    print("🔗 Connecting to Google Sheets...")
    try:
        sheet = connect_to_sheet()
        print(f"✅ Connected to: {SHEET_NAME} / {TAB_NAME}\n")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return
    
    try:
        update_v4_scores(sheet)
    except Exception as e:
        print(f"❌ Update failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()