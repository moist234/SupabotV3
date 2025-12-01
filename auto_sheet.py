"""
Auto-fill Google Sheets from Supabot V3 CSV output
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import glob
import os

# Google Sheets setup
SHEET_NAME = "SupabotV3"  # Your sheet name
TAB_NAME = "Sheet1"  # Change if different
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
        "Date", "Ticker", "Score", "Entry Price", "Buzz", "Twitter", "Reddit",
        "Market Cap", "Short Interest", "Past week 7d%", "Sector", "BB", "ATR",
        "Vol Trend", "RSI", "52w from high", "Exit Price (7d)", "7d %",
        "Exit Price (30d)", "30d %", "7d Win Rate %", "7d Average Return %",
        "S&P 7d %", "", "Control Group", "Entry Price", "Exit Price (7d)", "7d %"
    ]
    
    # Write headers in bold
    sheet.update(f'A{next_row}:AB{next_row}', [headers])
    
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
                cap_size = cap_text.split('(')[0].strip().upper()  # Get "MID", "SMALL", etc.
            else:
                cap_size = cap_text.upper()
            
            row_data = [
                today,                                      # A: Date
                pick['ticker'],                             # B: Ticker
                int(pick.get('quality_score', 0)),          # C: Score
                f"${pick['price']:.2f}",                    # D: Entry Price
                pick.get('buzz_level', 'N/A').upper(),      # E: Buzz (ALL CAPS)
                int(pick.get('twitter_mentions', 0)),       # F: Twitter
                int(pick.get('reddit_mentions', 0)),        # G: Reddit
                cap_size,                                    # H: Market Cap (ALL CAPS, word only)
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
        
        # Summary columns (U-W)
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
        sheet.update(f'A{data_start_row + i}:AB{data_start_row + i}', [row_data])
        
        ticker_name = ""
        if i < len(v3_picks):
            ticker_name = v3_picks.iloc[i]['ticker']
            if i < len(control_picks):
                ticker_name += f" + {control_picks.iloc[i]['ticker']} (control)"
        elif i < len(control_picks):
            ticker_name = f"{control_picks.iloc[i]['ticker']} (control only)"
        
        print(f"  ✅ Row {data_start_row + i}: {ticker_name}")
    
    print(f"\n🎉 Done! Added headers at row {next_row}, data starts at row {data_start_row}")
    print(f"📝 Note: Columns U-W left empty for formulas")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 SUPABOT V3 → GOOGLE SHEETS AUTO-FILL")
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
    
    # Fill sheet
    try:
        fill_sheet(sheet, csv_path)
    except Exception as e:
        print(f"❌ Fill failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)