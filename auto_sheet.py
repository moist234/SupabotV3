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
SERVICE_ACCOUNT_FILE = "caramel-granite-479920-g0-d3843370b463.json"

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
    
    # Find next empty row
    all_values = sheet.get_all_values()
    next_row = len(all_values) + 1
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\n✍️  Writing {len(v3_picks)} V3 picks + {len(control_picks)} control stocks...")
    
    # Determine how many rows to write (max of V3 or control)
    max_rows = max(len(v3_picks), len(control_picks))
    
    for i in range(max_rows):
        row_data = []
        
        # V3 Pick data (Columns A-T)
        if i < len(v3_picks):
            pick = v3_picks.iloc[i]
            row_data = [
                today,                                      # A: Date
                pick['ticker'],                             # B: Ticker
                int(pick.get('quality_score', 0)),          # C: Score
                f"${pick['price']:.2f}",                    # D: Entry Price
                pick.get('buzz_level', 'N/A'),              # E: Buzz
                int(pick.get('twitter_mentions', 0)),       # F: Twitter
                int(pick.get('reddit_mentions', 0)),        # G: Reddit
                pick.get('cap_size', 'N/A'),                # H: Market Cap
                f"{pick.get('short_percent', 0):.1f}%",     # I: Short Interest
                f"{pick.get('change_7d', 0):+.1f}%",        # J: Past week 7d%
                pick.get('sector', 'N/A'),                  # K: Sector
                f"{pick.get('bb_position', 0):.2f}",        # L: BB
                f"{pick.get('atr_pct', 0):.1f}%",           # M: ATR
                f"{pick.get('volume_trend', 0):.2f}",       # N: Vol Trend
                int(pick.get('rsi', 0)),                    # O: RSI
                f"{pick.get('dist_52w_high', 0):+.1f}%",    # P: 52w from high
                "",                                          # Q: Exit Price (7d) - empty
                "",                                          # R: 7d % - empty
                "",                                          # S: Exit Price (30d) - empty
                "",                                          # T: 30d % - empty
            ]
        else:
            # Empty V3 columns if no more V3 picks
            row_data = [""] * 20
        
        # Summary columns (U-W) - leave empty for manual calculation
        row_data.extend(["", "", ""])  # U: 7d Win Rate %, V: 7d Avg Return %, W: S&P 7d %
        
        # X: Blank
        row_data.append("")
        
        # Control Group data (Columns Y-AB)
        if i < len(control_picks):
            control = control_picks.iloc[i]
            row_data.extend([
                control['ticker'],                           # Y: Control Group Ticker
                f"${control['price']:.2f}",                  # Z: Entry Price (control)
                "",                                           # AA: Exit Price (7d) (control) - empty
                "",                                           # AB: 7d % (control) - empty
            ])
        else:
            # Empty control columns if no more control picks
            row_data.extend(["", "", "", ""])
        
        # Write row (A through AB = 28 columns)
        sheet.update(f'A{next_row + i}:AB{next_row + i}', [row_data])
        
        ticker_name = ""
        if i < len(v3_picks):
            ticker_name = v3_picks.iloc[i]['ticker']
            if i < len(control_picks):
                ticker_name += f" + {control_picks.iloc[i]['ticker']} (control)"
        elif i < len(control_picks):
            ticker_name = f"{control_picks.iloc[i]['ticker']} (control only)"
        
        print(f"  ✅ Row {next_row + i}: {ticker_name}")
    
    # Add 3 empty rows after last ticker
    empty_start = next_row + max_rows
    print(f"\n📝 Added 3 empty separator rows starting at row {empty_start}")
    
    print(f"\n🎉 Done! Added to sheet starting at row {next_row}")
    print(f"📝 Note: Columns U-W (Win Rate/Avg Return/S&P %) left empty for your formulas")

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