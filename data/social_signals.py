"""
Replace the get_quality_universe() function in data/social_signals.py
with this version that includes sector filtering
"""

import yfinance as yf
from typing import List

def get_quality_universe() -> List[str]:
    """
    Get quality universe using Finviz screener WITH SECTOR FILTER.
    
    VALIDATED SECTOR PERFORMANCE (43 trades):
    - Healthcare: 100% WR (9/9) ✅
    - Technology: 67% WR (8/12) ✅
    - Energy: 33% WR (1/3) ❌
    - Consumer Cyclical: 33% WR (1/3) ❌
    - Utilities: 50% WR (2/4) ❌
    """
    
    try:
        from finvizfinance.screener.overview import Overview
        
        print("   Using Finviz screener...")
        
        fviz = Overview()
        
        # Set quality filters
        filters_dict = {
            'Market Cap.': '+Small (over $300mln)',     # $300M+ only
            'Average Volume': 'Over 500K',              # Liquid stocks
            'Relative Volume': 'Over 1',                # Some activity
            'Price': 'Over $5',                         # No penny stocks
            '20-Day Simple Moving Average': 'Price above SMA20',  # Uptrend
        }
        
        fviz.set_filter(filters_dict=filters_dict)
        df = fviz.screener_view()
        
        if df is not None and not df.empty:
            tickers = df['Ticker'].tolist()
            print(f"   Finviz found {len(tickers)} quality stocks")
            
            # ============ SECTOR FILTER (VALIDATED) ============
            BANNED_SECTORS = [
                'Energy',              # 33% WR (1/3) - boring sector
                'Consumer Cyclical',   # 33% WR (1/3) - unpredictable
                'Utilities',           # 50% WR (2/4) - no retail interest
            ]
            
            print(f"   Applying sector filter (banning: {', '.join(BANNED_SECTORS)})...")
            
            filtered_tickers = []
            banned_count = 0
            checked_count = 0
            
            for ticker in tickers:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    
                    sector = info.get('sector', 'Unknown')
                    
                    checked_count += 1
                    
                    # Skip banned sectors
                    if sector in BANNED_SECTORS:
                        banned_count += 1
                        continue
                    
                    # Keep this stock
                    filtered_tickers.append(ticker)
                    
                    # Stop when we have enough
                    if len(filtered_tickers) >= 200:
                        break
                
                except Exception as e:
                    # If can't get sector info, include it (benefit of doubt)
                    filtered_tickers.append(ticker)
                    
                    if len(filtered_tickers) >= 200:
                        break
            
            print(f"   Checked {checked_count} stocks, excluded {banned_count} from banned sectors")
            print(f"   Final universe: {len(filtered_tickers)} stocks")
            
            return filtered_tickers[:200]
        
        else:
            print("   Finviz returned no results, using fallback")
    
    except ImportError:
        print("   ⚠️  finvizfinance not installed. Run: pip3 install finvizfinance")
        print("   Using curated fallback list...")
    
    except Exception as e:
        print(f"   Finviz screener error: {e}")
        print("   Using curated fallback list...")
    
    # Fallback: curated list (NO UTILITIES/ENERGY/CONSUMER)
    return [
        # Healthcare (100% WR validated!)
        "BIIB", "AMGN", "VRTX", "REGN", "CPRX", "AMRX", 
        "AXSM", "GSK", "AZN", "HALO", "JAZZ",
        
        # Technology (67% WR)
        "PLTR", "NVDA", "AMD", "NET", "DDOG", "SNOW", "MDB",
        "DOCN", "FSLY", "ZETA", "AMKR", "COHU", "ACIW",
        
        # Communication Services
        "IMAX", "PINS", "RBLX",
        
        # Fintech
        "SOFI", "COIN", "HOOD", "AFRM",
    ]