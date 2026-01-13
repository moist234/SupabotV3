"""
Auto-fill Google Sheets from Supabot V3 CSV output
Updated: Removed 30d tracking and control group, added filter tracking
Now tracks: Inst %, Relative Fresh, Regime, Days to Earnings
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
    """Calculate summary stats for a completed batch."""
    
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
    return_col = headers.index("7d %")  # Column V (index 21)
    
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
    returns = []
    
    for i, row in batch_rows:
        if row[return_col]:
            try:
                ret = float(row[return_col].replace('%', '').replace('+', ''))
                returns.append(ret)
            except:
                pass
    
    # If not all exits filled, skip
    total_picks = len(batch_rows)
    if len(returns) < total_picks:
        print(f"  📝 Only {len(returns)}/{total_picks} exits filled - waiting for completion")
        return
    
    # Calculate stats
    win_rate = (sum(1 for r in returns if r > 0) / len(returns)) * 100
    avg_return = sum(returns) / len(returns)
    
    # Calculate S&P 7d %
    try:
        entry_date = datetime.strptime(batch_date, '%Y-%m-%d')
        exit_date = entry_date + timedelta(days=7)
        
        spy = yf.Ticker('SPY')
        hist = spy.history(start=entry_date.strftime('%Y-%m-%d'), 
                          end=(exit_date + timedelta(days=3)).strftime('%Y-%m-%d'))
        
        if len(hist) >= 2:
            entry_price = hist['Close'].iloc[0]
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
    
    # Write summary to last pick's row (columns W, X, Y)
    last_row_num = batch_rows[-1][0] + 1
    
    summary_values = [
        [f'{win_rate:.1f}%', f'{avg_return:+.2f}%', f'{spy_return:+.2f}%']
    ]
    
    sheet.update(values=summary_values, range_name=f'W{last_row_num}:Y{last_row_num}')
    
    print(f"  ✅ Summary added to row {last_row_num}:")
    print(f"     Win Rate: {win_rate:.1f}% | Avg Return: {avg_return:+.2f}% | S&P: {spy_return:+.2f}%")

def fill_sheet(sheet, csv_path):
    """Fill Google Sheet from CSV."""
    
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Only V4 picks (no control group)
    v4_picks = df[df['group'].isin(['V3', 'V4'])].copy()
    
    print(f"\n✍️  Writing {len(v4_picks)} V4 picks...")
    
    # Find next empty row (2 rows down from last data)
    all_values = sheet.get_all_values()
    last_data_row = len(all_values)
    
    for i in range(len(all_values) - 1, -1, -1):
        if any(cell.strip() for cell in all_values[i]):
            last_data_row = i + 1
            break
    
    next_row = last_data_row + 2
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    print(f"📍 Starting at row {next_row}")
    
    # Updated headers (25 columns, no 30d, no control)
    headers = [
        "Date", "Ticker", "V4Score", "Entry Price", "Buzz", "Twitter", "Reddit",
        "Market Cap", "Short Interest", "Past week 7d%", "Sector",
        "BB", "ATR", "Vol Trend", "RSI", "52w from high",
        "Inst %", "Relative Fresh", "Regime", "Days to Earnings",
        "Exit Price (7d)", "7d %",
        "7d Win Rate %", "7d Average Return %", "S&P 7d %"
    ]
    
    # Write headers
    sheet.update(values=[headers], range_name=f'A{next_row}:Y{next_row}')
    
    # Format headers
    sheet.format(f'A{next_row}:Y{next_row}', {
        "textFormat": {
            "bold": True,
            "fontFamily": "Cambria",
            "fontSize": 12
        }
    })
    
    print(f"✅ Headers added at row {next_row}")
    
    data_start_row = next_row + 1
    
    # Format data rows
    sheet.format(f'A{data_start_row}:Y{data_start_row + len(v4_picks)}', {
        "textFormat": {
            "fontFamily": "Cambria",
            "fontSize": 12
        }
    })
    
    # Write each pick
    for i in range(len(v4_picks)):
        pick = v4_picks.iloc[i]
        
        # Extract market cap size only
        cap_text = pick.get('cap_size', 'N/A')
        if '(' in cap_text:
            cap_size = cap_text.split('(')[0].strip().upper()
        else:
            cap_size = cap_text.upper()
        
        row_data = [
            today,                                      # A: Date
            pick['ticker'],                             # B: Ticker
            int(pick.get('v4_score', 0)),               # C: V4Score
            f"${pick['price']:.2f}",                    # D: Entry Price
            pick.get('buzz_level', 'N/A').upper(),      # E: Buzz
            int(pick.get('twitter_mentions', 0)),       # F: Twitter
            int(pick.get('reddit_mentions', 0)),        # G: Reddit
            cap_size,                                    # H: Market Cap
            f"{pick.get('short_percent', 0):.1f}%",     # I: Short Interest
            f"{pick.get('change_7d', 0):+.1f}%",        # J: Past week 7d% (Absolute Fresh)
            pick.get('sector', 'N/A'),                  # K: Sector
            f"{pick.get('bb_position', 0):.2f}",        # L: BB
            f"{pick.get('atr_pct', 0):.1f}%",           # M: ATR
            f"{pick.get('volume_trend', 0):.2f}",       # N: Vol Trend
            int(pick.get('rsi', 0)),                    # O: RSI
            f"{pick.get('dist_52w_high', 0):+.1f}%",    # P: 52w from high
            f"{pick.get('inst_ownership', 0):.1f}%",    # Q: Inst %
            f"{pick.get('relative_fresh', 0):+.1f}%",   # R: Relative Fresh
            pick.get('regime', 'N/A'),                  # S: Regime
            str(pick.get('days_to_earnings', 'N/A')),   # T: Days to Earnings
            "",                                          # U: Exit Price (7d)
            "",                                          # V: 7d %
            "",                                          # W: 7d Win Rate %
            "",                                          # X: 7d Average Return %
            "",                                          # Y: S&P 7d %
        ]
        
        # Write row
        sheet.update(values=[row_data], range_name=f'A{data_start_row + i}:Y{data_start_row + i}')
        
        print(f"  ✅ Row {data_start_row + i}: {pick['ticker']}")
    
    print(f"\n🎉 Done! Added {len(v4_picks)} picks")

def update_exit_prices(sheet):
    """Auto-fill exit prices for 7-day-old trades."""
    
    print("\n🔄 Checking for trades ready to exit...")
    
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
    ticker_col = headers.index("Ticker")
    entry_price_col = headers.index("Entry Price")
    exit_price_col = headers.index("Exit Price (7d)")  # Column U (index 20)
    return_col = headers.index("7d %")                  # Column V (index 21)
    
    today = datetime.now().date()
    updates = []
    
    # Check each data row
    for i in range(header_row + 1, len(all_values)):
        row = all_values[i]
        
        # Parse entry date
        try:
            entry_date = datetime.strptime(row[date_col], '%Y-%m-%d').date()
        except:
            continue
        
        # Calculate target exit date
        target_exit_date = entry_date + timedelta(days=7)
        
        # Only process if we're past exit date
        if today <= target_exit_date:
            continue
        
        # Only process if exit not already filled
        if row[ticker_col] and not row[exit_price_col]:
            ticker = row[ticker_col]
            entry_price_str = row[entry_price_col].replace('$', '')
            
            try:
                entry_price = float(entry_price_str)
                
                # Fetch historical data
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
                        
                        # Update Exit Price (column U)
                        sheet.update(values=[[f'${exit_price:.2f}']], range_name=f'U{row_num}')
                        
                        # Update 7d % (column V)
                        sheet.update(values=[[f'{return_pct:+.2f}%']], range_name=f'V{row_num}')
                        
                        days_held = (datetime.strptime(actual_exit_date, '%Y-%m-%d').date() - entry_date).days
                        
                        updates.append({
                            'ticker': ticker,
                            'entry_date': str(entry_date),
                            'exit_date': actual_exit_date,
                            'days_held': days_held,
                            'return': return_pct
                        })
                        
                        print(f"  ✅ {ticker}: {entry_date} → {actual_exit_date} ({days_held}d) | "
                              f"${entry_price:.2f} → ${exit_price:.2f} ({return_pct:+.2f}%)")
            
            except Exception as e:
                print(f"  ⚠️  {ticker}: Error - {e}")
    
    # Calculate batch summaries
    if updates:
        print(f"\n✅ Updated {len(updates)} exits!")
        
        print(f"\n{'='*60}")
        print("📊 CALCULATING BATCH SUMMARIES...")
        print(f"{'='*60}")
        
        # Get unique entry dates
        unique_dates = set(upd['entry_date'] for upd in updates)
        
        # Calculate summary for each completed batch
        for batch_date in unique_dates:
            calculate_batch_summary(sheet, batch_date)
        
        print(f"{'='*60}\n")
    else:
        print(f"\n📝 No trades ready for exit update")
    
    return updates

def fill_sheet(sheet, csv_path):
    """Fill Google Sheet from CSV."""
    
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Only V4 picks (filter out control group if exists)
    v4_picks = df[df['group'].isin(['V3', 'V4'])].copy()
    
    # Find next empty row
    all_values = sheet.get_all_values()
    last_data_row = len(all_values)
    
    for i in range(len(all_values) - 1, -1, -1):
        if any(cell.strip() for cell in all_values[i]):
            last_data_row = i + 1
            break
    
    next_row = last_data_row + 2
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\n✍️  Writing {len(v4_picks)} V4 picks...")
    print(f"📍 Starting at row {next_row}")
    
    # Headers (25 columns A-Y)
    headers = [
        "Date", "Ticker", "V4Score", "Entry Price", "Buzz", "Twitter", "Reddit",
        "Market Cap", "Short Interest", "Past week 7d%", "Sector",
        "BB", "ATR", "Vol Trend", "RSI", "52w from high",
        "Inst %", "Relative Fresh", "Regime", "Days to Earnings",
        "Exit Price (7d)", "7d %",
        "7d Win Rate %", "7d Average Return %", "S&P 7d %"
    ]
    
    # Write headers
    sheet.update(values=[headers], range_name=f'A{next_row}:Y{next_row}')
    
    # Format headers (bold, Cambria 12)
    sheet.format(f'A{next_row}:Y{next_row}', {
        "textFormat": {
            "bold": True,
            "fontFamily": "Cambria",
            "fontSize": 12
        }
    })
    
    print(f"✅ Headers added at row {next_row}")
    
    data_start_row = next_row + 1
    
    # Format data rows (Cambria 12)
    sheet.format(f'A{data_start_row}:Y{data_start_row + len(v4_picks)}', {
        "textFormat": {
            "fontFamily": "Cambria",
            "fontSize": 12
        }
    })
    
    # Write each pick
    for i in range(len(v4_picks)):
        pick = v4_picks.iloc[i]
        
        # Extract market cap size
        cap_text = pick.get('cap_size', 'N/A')
        if '(' in cap_text:
            cap_size = cap_text.split('(')[0].strip().upper()
        else:
            cap_size = cap_text.upper()
        
        row_data = [
            today,                                      # A: Date
            pick['ticker'],                             # B: Ticker
            int(pick.get('v4_score', 0)),               # C: V4Score
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
            f"{pick.get('inst_ownership', 0):.1f}%",    # Q: Inst %
            f"{pick.get('relative_fresh', 0):+.1f}%",   # R: Relative Fresh
            pick.get('regime', 'N/A'),                  # S: Regime
            str(pick.get('days_to_earnings', 'N/A')),   # T: Days to Earnings
            "",                                          # U: Exit Price (7d)
            "",                                          # V: 7d %
            "",                                          # W: 7d Win Rate %
            "",                                          # X: 7d Average Return %
            "",                                          # Y: S&P 7d %
        ]
        
        # Write row
        sheet.update(values=[row_data], range_name=f'A{data_start_row + i}:Y{data_start_row + i}')
        
        print(f"  ✅ Row {data_start_row + i}: {pick['ticker']}")
    
    print(f"\n🎉 Done! Added {len(v4_picks)} picks starting at row {data_start_row}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 SUPABOT V4 → GOOGLE SHEETS AUTO-FILL")
    print("📊 Updated: No Control Group, New Filter Tracking")
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
    
    # Update exit prices
    try:
        update_exit_prices(sheet)
    except Exception as e:
        print(f"❌ Exit price update failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)