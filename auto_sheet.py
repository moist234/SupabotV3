"""
Auto-fill Google Sheets from Supabot V3 CSV output
With automatic exit price filling and batch summary calculations
Now displays V4 Score instead of V3 Score
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, timedelta
import glob
import os
import yfinance as yf

# Google Sheets setup
SHEET_NAME = "SupabotV3"
TAB_NAME = "Sheet1"
SERVICE_ACCOUNT_FILE = "service_account.json"

def connect_to_sheet():
    """Connect to Google Sheets."""
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
    return sheet

def get_latest_csv():
    """Get most recent V3 scan CSV."""
    csv_files = glob.glob("outputs/supabot_v3_scan_*.csv")
    if not csv_files:
        print("❌ No CSV files found!")
        return None
    
    latest = max(csv_files, key=os.path.getctime)
    print(f"📄 Found: {latest}")
    return latest

def calculate_batch_summary(sheet, batch_date: str):
    """Calculate summary stats for a completed batch (V3 + Control)."""
    
    print(f"\n📊 Calculating summary for {batch_date} batch...")
    
    # Get all data
    all_values = sheet.get_all_values()
    
    # Find header row
    header_row = 0
    for i, row in enumerate(all_values):
        if row[0] == "Date":
            header_row = i
            break
    
    headers = all_values[header_row]
    
    # Find column indices
    date_col = headers.index("Date")
    return_col = headers.index("7d %")
    control_return_col = 27  # Column AB (0-indexed)
    
    # Find rows for this batch date
    batch_rows = []
    for i in range(header_row + 1, len(all_values)):
        row = all_values[i]
        if row[date_col] == batch_date:
            batch_rows.append((i, row))
    
    if not batch_rows:
        print(f"  ⚠️  No rows found for {batch_date}")
        return
    
    # Check if all exits are filled
    v3_returns = []
    control_returns = []
    
    for i, row in batch_rows:
        # V3 return
        if row[return_col]:
            try:
                ret = float(row[return_col].replace('%', '').replace('+', ''))
                v3_returns.append(ret)
            except:
                pass
        
        # Control return
        if len(row) > control_return_col and row[control_return_col]:
            try:
                ret = float(row[control_return_col].replace('%', '').replace('+', ''))
                control_returns.append(ret)
            except:
                pass
    
    # If not all exits filled, skip
    total_picks = len(batch_rows)
    if len(v3_returns) < total_picks:
        print(f"  📝 Only {len(v3_returns)}/{total_picks} V3 exits filled - waiting for completion")
        return
    
    # Calculate V3 stats
    win_rate = (sum(1 for r in v3_returns if r > 0) / len(v3_returns)) * 100
    avg_return = sum(v3_returns) / len(v3_returns)
    
    # Calculate S&P 7d %
    try:
        entry_date = datetime.strptime(batch_date, '%Y-%m-%d')
        exit_date = entry_date + timedelta(days=7)
        
        spy = yf.Ticker('SPY')
        hist = spy.history(start=entry_date.strftime('%Y-%m-%d'), 
                          end=(exit_date + timedelta(days=3)).strftime('%Y-%m-%d'))
        
        if len(hist) >= 2:
            entry_price = hist['Close'].iloc[0]
            
            # Find close on or after day 7
            exit_prices = hist[hist.index.date >= exit_date.date()]
            if len(exit_prices) > 0:
                exit_price = exit_prices['Close'].iloc[0]
                spy_return = ((exit_price - entry_price) / entry_price) * 100
            else:
                spy_return = 0
        else:
            spy_return = 0
    except Exception as e:
        print(f"  ⚠️  S&P calculation error: {e}")
        spy_return = 0
    
    # Write summary to last pick's row (columns U, V, W)
    last_row_num = batch_rows[-1][0] + 1  # Sheet is 1-indexed
    
    summary_values = [
        [f'{win_rate:.1f}%', f'{avg_return:+.2f}%', f'{spy_return:+.2f}%']
    ]
    
    sheet.update(values=summary_values, range_name=f'U{last_row_num}:W{last_row_num}')
    
    print(f"  ✅ Summary added to row {last_row_num}:")
    print(f"     Win Rate: {win_rate:.1f}% | Avg Return: {avg_return:+.2f}% | S&P: {spy_return:+.2f}%")
    
    return {
        'win_rate': win_rate,
        'avg_return': avg_return,
        'spy_return': spy_return
    }

def fill_sheet(sheet, csv_path):
    """Fill Google Sheet from CSV."""
    
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Separate V3 picks and control
    v3_picks = df[df['group'] == 'V3'].copy()
    control_picks = df[df['group'] == 'CONTROL'].copy()
    
    # Find next empty row (2 rows down from last data)
    all_values = sheet.get_all_values()
    last_data_row = len(all_values)
    
    # Find last non-empty row
    for i in range(len(all_values) - 1, -1, -1):
        if any(cell.strip() for cell in all_values[i]):
            last_data_row = i + 1
            break
    
    next_row = last_data_row + 2  # 2 rows down
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\n✍️  Writing {len(v3_picks)} V3 picks + {len(control_picks)} control stocks...")
    print(f"📍 Starting at row {next_row}")
    
    # WRITE HEADERS FIRST (bolded)
    headers = [
        "Date", "Ticker", "V4Score", "Entry Price", "Buzz", "Twitter", "Reddit",
        "Market Cap", "Short Interest", "Past week 7d%", "Sector", "BB", "ATR",
        "Vol Trend", "RSI", "52w from high", "Exit Price (7d)", "7d %",
        "Exit Price (30d)", "30d %", "7d Win Rate %", "7d Average Return %",
        "S&P 7d %", "", "Control Group", "Entry Price", "Exit Price (7d)", "7d %"
    ]
    
    # Write headers
    sheet.update(values=[headers], range_name=f'A{next_row}:AB{next_row}')
    
    # Format headers as bold
    sheet.format(f'A{next_row}:AB{next_row}', {
        "textFormat": {"bold": True}
    })
    
    print(f"✅ Headers added at row {next_row}")
    
    # Start data at next row
    data_start_row = next_row + 1
    
    # Determine how many rows to write
    max_rows = max(len(v3_picks), len(control_picks))
    
    for i in range(max_rows):
        row_data = []
        
        # V3 Pick data (Columns A-T)
        if i < len(v3_picks):
            pick = v3_picks.iloc[i]
            
            # Extract market cap size only (remove parentheses text)
            cap_text = pick.get('cap_size', 'N/A')
            if '(' in cap_text:
                cap_size = cap_text.split('(')[0].strip().upper()
            else:
                cap_size = cap_text.upper()
            
            row_data = [
                today,                                      # A: Date
                pick['ticker'],                             # B: Ticker
                int(pick.get('v4_score', 0)),               # C: Score (V4) ← CHANGED
                f"${pick['price']:.2f}",                    # D: Entry Price
                pick.get('buzz_level', 'N/A').upper(),      # E: Buzz
                int(pick.get('twitter_mentions', 0)),       # F: Twitter
                int(pick.get('reddit_mentions', 0)),        # G: Reddit
                cap_size,                                    # H: Market Cap
                f"{pick.get('short_percent', 0):.1f}%",     # I: Short Interest
                f"{pick.get('change_7d', 0):+.1f}%",        # J: Past week 7d%
                pick.get('sector', 'N/A'),                  # K: Sector
                f"{pick.get('bb_position', 0):.2f}",        # L: BB
                f"{pick.get('atr_pct', 0):.1f}%",           # M: ATR
                f"{pick.get('volume_trend', 0):.2f}",       # N: Vol Trend
                int(pick.get('rsi', 0)),                    # O: RSI
                f"{pick.get('dist_52w_high', 0):+.1f}%",    # P: 52w from high
                "",                                          # Q: Exit Price (7d)
                "",                                          # R: 7d %
                "",                                          # S: Exit Price (30d)
                "",                                          # T: 30d %
            ]
        else:
            row_data = [""] * 20
        
        # Summary columns (U-W) - will be filled later by calculate_batch_summary
        row_data.extend(["", "", ""])
        
        # X: Blank
        row_data.append("")
        
        # Control Group data (Columns Y-AB)
        if i < len(control_picks):
            control = control_picks.iloc[i]
            row_data.extend([
                control['ticker'],                           # Y: Control Group Ticker
                f"${control['price']:.2f}",                  # Z: Entry Price
                "",                                           # AA: Exit Price (7d)
                "",                                           # AB: 7d %
            ])
        else:
            row_data.extend(["", "", "", ""])
        
        # Write row
        sheet.update(values=[row_data], range_name=f'A{data_start_row + i}:AB{data_start_row + i}')
        
        ticker_name = ""
        if i < len(v3_picks):
            ticker_name = v3_picks.iloc[i]['ticker']
            if i < len(control_picks):
                ticker_name += f" + {control_picks.iloc[i]['ticker']} (control)"
        elif i < len(control_picks):
            ticker_name = f"{control_picks.iloc[i]['ticker']} (control only)"
        
        print(f"  ✅ Row {data_start_row + i}: {ticker_name}")
    
    print(f"\n🎉 Done! Added headers at row {next_row}, data starts at row {data_start_row}")
    print(f"📝 Note: Columns U-W will be auto-filled when exits complete")
    print(f"📊 V4 Scores now displayed in Score column")

def update_exit_prices(sheet):
    """Auto-fill exit prices for V3 picks AND control group using close on day 7."""
    
    print("\n🔄 Checking for trades ready to exit...")
    
    # Get all data
    all_values = sheet.get_all_values()
    
    # Find header row
    header_row = 0
    for i, row in enumerate(all_values):
        if row[0] == "Date":
            header_row = i
            break
    
    headers = all_values[header_row]
    
    # Find column indices for V3 picks
    date_col = headers.index("Date")
    ticker_col = headers.index("Ticker")
    entry_price_col = headers.index("Entry Price")
    exit_price_col = headers.index("Exit Price (7d)")
    return_col = headers.index("7d %")
    
    # Find column indices for Control Group
    try:
        control_ticker_col = headers.index("Control Group")
        control_entry_col = 25  # Column Z (0-indexed: A=0, B=1... Z=25)
        control_exit_col = 26   # Column AA
        control_return_col = 27  # Column AB
        has_control_group = True
    except ValueError:
        has_control_group = False
        print("  ⚠️  No Control Group columns (old format)")
    
    today = datetime.now().date()
    v3_updates = []
    control_updates = []
    
    print("\n📊 V3 PICKS:")
    # Check each data row
    for i in range(header_row + 1, len(all_values)):
        row = all_values[i]
        
        # Parse entry date
        try:
            entry_date = datetime.strptime(row[date_col], '%Y-%m-%d').date()
        except:
            continue
        
        # Calculate target exit date (entry + 7 days)
        target_exit_date = entry_date + timedelta(days=7)
        
        # Only process if we're past the exit date
        if today <= target_exit_date:
            continue
        
        # ============ PROCESS V3 PICK ============
        if row[ticker_col] and not row[exit_price_col]:
            ticker = row[ticker_col]
            entry_price_str = row[entry_price_col].replace('$', '')
            
            try:
                entry_price = float(entry_price_str)
                
                # Fetch historical data covering the exit date
                stock = yf.Ticker(ticker)
                start_date = entry_date
                end_date = today + timedelta(days=1)
                
                hist = stock.history(start=start_date.strftime('%Y-%m-%d'), 
                                    end=end_date.strftime('%Y-%m-%d'))
                
                if len(hist) > 0:
                    # Find close on or after target exit date
                    exit_prices = hist[hist.index.date >= target_exit_date]
                    
                    if len(exit_prices) > 0:
                        exit_price = float(exit_prices['Close'].iloc[0])
                        actual_exit_date = exit_prices.index[0].strftime('%Y-%m-%d')
                        return_pct = ((exit_price - entry_price) / entry_price) * 100
                        
                        row_num = i + 1
                        
                        # Update Exit Price (7d)
                        exit_col_letter = chr(65 + exit_price_col)
                        sheet.update(values=[[f'${exit_price:.2f}']], range_name=f'{exit_col_letter}{row_num}')
                        
                        # Update 7d %
                        return_col_letter = chr(65 + return_col)
                        sheet.update(values=[[f'{return_pct:+.2f}%']], range_name=f'{return_col_letter}{row_num}')
                        
                        days_held = (datetime.strptime(actual_exit_date, '%Y-%m-%d').date() - entry_date).days
                        
                        v3_updates.append({
                            'ticker': ticker,
                            'entry_date': str(entry_date),
                            'exit_date': actual_exit_date,
                            'days_held': days_held,
                            'return': return_pct
                        })
                        
                        print(f"  ✅ {ticker}: {entry_date} → {actual_exit_date} ({days_held}d) | ${entry_price:.2f} → ${exit_price:.2f} ({return_pct:+.2f}%)")
            except Exception as e:
                print(f"  ⚠️  {ticker}: Error - {e}")
        
        # ============ PROCESS CONTROL GROUP ============
        if has_control_group and len(row) > control_ticker_col and row[control_ticker_col]:
            control_exit_value = row[control_exit_col] if len(row) > control_exit_col else ""
            
            if not control_exit_value:
                control_ticker = row[control_ticker_col]
                control_entry_str = row[control_entry_col].replace('$', '') if len(row) > control_entry_col else ""
                
                if control_entry_str:
                    try:
                        control_entry_price = float(control_entry_str)
                        
                        # Fetch historical data
                        stock = yf.Ticker(control_ticker)
                        start_date = entry_date
                        end_date = today + timedelta(days=1)
                        
                        hist = stock.history(start=start_date.strftime('%Y-%m-%d'), 
                                            end=end_date.strftime('%Y-%m-%d'))
                        
                        if len(hist) > 0:
                            exit_prices = hist[hist.index.date >= target_exit_date]
                            
                            if len(exit_prices) > 0:
                                control_exit_price = float(exit_prices['Close'].iloc[0])
                                actual_exit_date = exit_prices.index[0].strftime('%Y-%m-%d')
                                control_return_pct = ((control_exit_price - control_entry_price) / control_entry_price) * 100
                                
                                row_num = i + 1
                                
                                # Update control exit price (column AA)
                                sheet.update(values=[[f'${control_exit_price:.2f}']], range_name=f'AA{row_num}')
                                
                                # Update control return (column AB)
                                sheet.update(values=[[f'{control_return_pct:+.2f}%']], range_name=f'AB{row_num}')
                                
                                days_held = (datetime.strptime(actual_exit_date, '%Y-%m-%d').date() - entry_date).days
                                
                                control_updates.append({
                                    'ticker': control_ticker,
                                    'entry_date': str(entry_date),
                                    'exit_date': actual_exit_date,
                                    'days_held': days_held,
                                    'return': control_return_pct
                                })
                                
                                if not v3_updates:
                                    print("\n🎲 CONTROL GROUP:")
                                print(f"  ✅ {control_ticker}: {entry_date} → {actual_exit_date} ({days_held}d) | ${control_entry_price:.2f} → ${control_exit_price:.2f} ({control_return_pct:+.2f}%)")
                    except Exception as e:
                        if not v3_updates:
                            print("\n🎲 CONTROL GROUP:")
                        print(f"  ⚠️  {control_ticker}: Error - {e}")
    
    updates = {'v3': v3_updates, 'control': control_updates}
    
    # Summary
    if v3_updates or control_updates:
        print(f"\n✅ Updated {len(v3_updates)} V3 picks + {len(control_updates)} control stocks (7-day holding period)!")
        
        # NEW: Calculate batch summaries for completed batches
        print(f"\n{'='*60}")
        print("📊 CALCULATING BATCH SUMMARIES...")
        print(f"{'='*60}")
        
        # Get unique entry dates from updated trades
        unique_dates = set()
        for upd in v3_updates:
            unique_dates.add(upd['entry_date'])
        
        # Calculate summary for each completed batch
        for batch_date in unique_dates:
            calculate_batch_summary(sheet, batch_date)
        
        print(f"{'='*60}\n")
    
    else:
        print(f"\n📝 No trades ready for exit update")
    
    return updates

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 SUPABOT V3 → GOOGLE SHEETS AUTO-FILL")
    print("📊 Now Showing V4 Scores")
    print("="*60 + "\n")
    
    # Get latest CSV
    csv_path = get_latest_csv()
    if not csv_path:
        exit(1)
    
    # Connect to sheet
    print("\n🔗 Connecting to Google Sheets...")
    try:
        sheet = connect_to_sheet()
        print(f"✅ Connected to: {SHEET_NAME} / {TAB_NAME}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nMake sure:")
        print("1. service_account.json exists")
        print("2. Sheet is shared with service account email")
        exit(1)
    
    # Fill new picks
    try:
        fill_sheet(sheet, csv_path)
    except Exception as e:
        print(f"❌ Fill failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    
    # Update exit prices for old trades
    try:
        update_exit_prices(sheet)
    except Exception as e:
        print(f"❌ Exit price update failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)