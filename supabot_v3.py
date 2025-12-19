"""
Supabot V3 - With V4 Score Display

SELECTION: V3 scoring (unchanged - proven to work)
DISPLAY: V4 scoring (for tracking/validation)

V4 scoring based on 50-trade validated patterns:
- Sector + Market Cap combo (Healthcare Mid = best)
- Short Interest 5-15% optimal
- Fresh % negative preferred
- 52w positioning -30% to -10% best
"""
import os
import sys
import re
import random
import json
try:
    import alpaca_trade_api as tradeapi
except:
    tradeapi = None
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import pandas as pd
from dotenv import load_dotenv
import numpy as np

import yfinance as yf
import praw
import requests
from finvizfinance.screener.overview import Overview

load_dotenv()

# API Keys
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "supabot/3.0")
TWITTER_API_KEY = os.getenv("TWITTERAPI_IO_KEY")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"
POSITIONS_FILE = "alpaca_positions.json"

# Settings
FRESH_MIN = -5.0
FRESH_MAX = 5.0
MIN_MARKET_CAP = 500_000_000
MIN_PRICE = 5.0
MIN_VOLUME_USD = 2_000_000
MAX_SHORT_PERCENT = 20.0
MIN_TWITTER_BUZZ = 15
MIN_REDDIT_BUZZ = 5
SCAN_LIMIT = 100

BANNED_SECTORS = ['Energy', 'Consumer Cyclical', 'Utilities', 'Financial Services']


# ============ METRIC CALCULATORS ============

def calculate_bollinger_position(ticker: str) -> float:
    """Calculate where price is within Bollinger Bands (0-1 scale)."""
    try:
        hist = yf.Ticker(ticker).history(period="3mo")
        if len(hist) < 20:
            return 0.5
        
        close = hist['Close']
        sma_20 = close.rolling(20).mean().iloc[-1]
        std_20 = close.rolling(20).std().iloc[-1]
        
        bb_upper = sma_20 + (2 * std_20)
        bb_lower = sma_20 - (2 * std_20)
        current = close.iloc[-1]
        
        if bb_upper == bb_lower:
            return 0.5
        
        position = (current - bb_lower) / (bb_upper - bb_lower)
        return round(float(np.clip(position, 0, 1)), 3)
    except:
        return 0.5


def calculate_atr_normalized(ticker: str) -> float:
    """Calculate ATR as % of price (volatility measure)."""
    try:
        hist = yf.Ticker(ticker).history(period="2mo")
        if len(hist) < 14:
            return 0.0
        
        high = hist['High']
        low = hist['Low']
        close = hist['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        current_price = close.iloc[-1]
        atr_pct = (atr / current_price * 100) if current_price > 0 else 0
        
        return round(float(atr_pct), 2)
    except:
        return 0.0


def calculate_volume_trend(ticker: str) -> float:
    """Calculate volume acceleration (recent vs baseline)."""
    try:
        hist = yf.Ticker(ticker).history(period="1mo")
        if len(hist) < 20:
            return 1.0
        
        volume = hist['Volume']
        recent_5d = volume.tail(5).mean()
        baseline_15d = volume.tail(20).head(15).mean()
        
        trend = recent_5d / baseline_15d if baseline_15d > 0 else 1.0
        return round(float(trend), 2)
    except:
        return 1.0


def get_rsi(ticker: str) -> float:
    """Get current RSI value."""
    try:
        hist = yf.Ticker(ticker).history(period="2mo")
        if len(hist) < 14:
            return 50.0
        
        close = hist['Close']
        delta = close.diff()
        
        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)
        
        avg_gains = gains.rolling(14).mean()
        avg_losses = losses.rolling(14).mean()
        
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return round(float(rsi.iloc[-1]), 1)
    except:
        return 50.0


def calculate_52w_positioning(ticker: str) -> Dict:
    """Calculate distance to 52-week high/low."""
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if len(hist) < 200:
            return {'dist_52w_high': 0.0, 'dist_52w_low': 0.0}
        
        high_52w = hist['High'].max()
        low_52w = hist['Low'].min()
        current = hist['Close'].iloc[-1]
        
        dist_high = ((current / high_52w) - 1) * 100
        dist_low = ((current / low_52w) - 1) * 100
        
        return {
            'dist_52w_high': round(float(dist_high), 2),
            'dist_52w_low': round(float(dist_low), 2),
        }
    except:
        return {'dist_52w_high': 0.0, 'dist_52w_low': 0.0}


# ============ SCORING FUNCTIONS ============

def calculate_quality_score(pick: Dict) -> float:
    """
    V3 scoring - FOR SELECTION ONLY (internal use).
    Based on buzz, fresh, volume, cap.
    """
    score = 0
    
    # Buzz (10-40 points)
    twitter = pick['twitter_mentions']
    reddit = pick['reddit_mentions']
    total_buzz = twitter + (reddit * 2)
    
    if total_buzz >= 50:
        score += 40
    elif total_buzz >= 30:
        score += 30
    elif total_buzz >= 20:
        score += 20
    else:
        score += 10
    
    # Fresh position (10-30 points)
    fresh = pick['change_7d']
    if 0 <= fresh <= 2:
        score += 30
    elif -2 <= fresh < 0:
        score += 25
    elif 2 < fresh <= 5:
        score += 20
    else:
        score += 10
    
    # Volume spike (0-15 points)
    if pick.get('volume_spike'):
        score += 15
    elif pick['volume_ratio'] > 1.0:
        score += 8
    
    # Market cap (5-15 points)
    if 'Mid' in pick['cap_size'] or 'Large' in pick['cap_size']:
        score += 15
    elif 'Small' in pick['cap_size']:
        score += 10
    else:
        score += 5
    
    return score


def calculate_quality_score_v4(pick: Dict) -> float:
    """
    V4 scoring - FOR DISPLAY/TRACKING ONLY
    Based on CORRECT 121-trade data (71.9% WR)
    
    Key findings from winner_pattern_discovery.py:
    - Fresh 0-3% = sweet spot (78-100% WR on 40 trades)
    - SI 3-7% = golden zone (80.9% WR on 38 trades)
    - SI 1-2% = dead zone (60% WR)
    - Large-cap > Mid-cap (78.9% vs 72.4% WR)
    - Basic Materials = best sector (90.9% WR, 10-1)
    
    Backtest results: 19.3 point gap (p=0.0001)
    - Winners avg: 101.5
    - Losers avg: 82.2
    
    STILL TRACKING ONLY - NOT USED FOR SELECTION
    """
    score = 0
    
    # 1. FRESH % SWEET SPOT (0-50 points)
    # Fresh 0-3% validated on 40 trades with 78-100% WR
    fresh = pick['change_7d']
    if 1.0 <= fresh <= 2.0:
        score += 50  # 80.6% WR (25-6 validated)
    elif 0 <= fresh < 1.0:
        score += 45  # 76.5% WR (26-8 validated)
    elif 2.0 < fresh <= 3.0:
        score += 45  # 100% WR (7-0, small sample)
    elif -2.0 <= fresh < 0:
        score += 20  # 58.6% WR (17-12, weak)
    elif fresh > 3.0:
        score += 15  # 57.9% WR (11-8, weak)
    else:  # fresh < -2.0
        score += 10
    
    # 2. SHORT INTEREST ZONES (0-40 points)
    # SI 3-7% validated as golden zone (80.9% WR on 38 trades)
    si = pick.get('short_percent', 0)
    if 3.0 <= si <= 7.0:
        score += 40  # 80.9% WR combined (3-5%: 80.6%, 5-7%: 81.2%)
    elif 0 <= si < 1.0:
        score += 35  # 75.0% WR (15-5)
    elif 7.0 < si < 10.0:
        score += 30  # 75.0% WR (9-3)
    elif 2.0 <= si < 3.0:
        score += 25  # 66.7% WR (8-4)
    elif 1.0 <= si < 2.0:
        score += 15  # 60.0% WR (6-4) - DEAD ZONE!
    elif 10.0 <= si < 15.0:
        score += 10  # 53.3% WR (8-7) - HIGH RISK!
    # SI ≥15% gets 0 (60% WR, very high risk)
    
    # 3. MARKET CAP (0-30 points)
    # Large-cap outperforms! (78.9% vs 72.4% for Mid)
    cap_size = pick['cap_size']
    if 'LARGE' in cap_size.upper():
        score += 30  # 78.9% WR (30-8 validated)
    elif 'MID' in cap_size.upper():
        score += 25  # 72.4% WR (42-16 validated)
    elif 'SMALL' in cap_size.upper():
        score += 15  # 63.2% WR (12-7)
    # MEGA gets 0 (50% WR, 3-3)
    
    # 4. SECTOR PERFORMANCE (0-20 points)
    sector = pick['sector']
    if sector == 'Basic Materials':
        score += 20  # 90.9% WR (10-1) - BEST!
    elif sector == 'Communication Services':
        score += 15  # 77.8% WR (7-2)
    elif sector == 'Technology':
        score += 10  # 73.3% WR (11-4)
    elif sector == 'Healthcare':
        score += 10  # 72.7% WR (16-6)
    # Real Estate, Financial Services, Industrials get 0 (66.7% WR)
    # Consumer Defensive = 0 (50% WR, should be banned!)
    
    # 5. COMBINATION BONUSES (0-10 points)
    # Top validated combinations
    if 1.0 <= fresh <= 3.0 and 2.0 <= si <= 5.0:
        score += 10  # Fresh 1-3% + SI 2-5% = 90.9% WR (10-1)
    elif 1.0 <= fresh <= 3.0 and 5.0 <= si <= 10.0:
        score += 8   # Fresh 1-3% + SI 5-10% = 83.3% WR (10-2)
    
    return score

# MAX POSSIBLE: 155 points
# Expected quality picks: 110-145 points
# Expected weak picks: 40-90 points
#
# Backtest validation (121 trades):
# - Winners avg: 101.5, Losers avg: 82.2 (19.3 point gap)
# - V4 ≥100: 81.7% WR (49-11)
# - V4 <100: 62.3% WR (38-23)
# - Correlation: r=0.088 (weak linear, but strong binary threshold)

# ============ UNIVERSE & SIGNAL FUNCTIONS ============

def get_universe() -> List[str]:
    """Get stock universe with sector filter."""
    try:
        fviz = Overview()
        filters = {
            'Market Cap.': '+Small (over $300mln)',
            'Average Volume': 'Over 500K',
            'Price': 'Over $5',
            'Relative Volume': 'Over 0.5',
        }
        fviz.set_filter(filters_dict=filters)
        df = fviz.screener_view()
        
        all_tickers = df['Ticker'].tolist()
        random.shuffle(all_tickers)
        
        print(f"📊 Finviz: {len(all_tickers)} total")
        print(f"   Filtering out: {', '.join(BANNED_SECTORS)}...")
        
        filtered = []
        banned_count = 0
        
        for ticker in all_tickers:
            try:
                info = yf.Ticker(ticker).info
                sector = info.get('sector', 'Unknown')
                
                if sector in BANNED_SECTORS:
                    banned_count += 1
                    continue
                
                filtered.append(ticker)
                if len(filtered) >= SCAN_LIMIT:
                    break
            except:
                filtered.append(ticker)
                if len(filtered) >= SCAN_LIMIT:
                    break
        
        print(f"   Excluded {banned_count} stocks, scanning {len(filtered)}")
        return filtered
        
    except Exception as e:
        print(f"⚠️  Finviz error: {e}")
        return ['BIIB', 'AMGN', 'PLTR', 'NVDA', 'SOFI', 'COIN']


def check_fresh(ticker: str) -> Dict:
    """Check if Fresh."""
    try:
        hist = yf.Ticker(ticker).history(period="6mo")
        if len(hist) < 10:
            return None
        
        close = hist['Close']
        change_7d = ((close.iloc[-1] - close.iloc[-8]) / close.iloc[-8] * 100) if len(close) > 7 else 0
        change_90d = ((close.iloc[-1] - close.iloc[-91]) / close.iloc[-91] * 100) if len(close) > 90 else 0
        
        is_fresh = FRESH_MIN <= change_7d <= FRESH_MAX and change_90d > -40.0
        
        return {
            'change_7d': round(change_7d, 2),
            'change_90d': round(change_90d, 2),
            'is_fresh': is_fresh,
            'price': float(close.iloc[-1])
        }
    except:
        return None


def check_reddit_confirmation(ticker: str) -> int:
    """Get Reddit mentions - STRICT MODE."""
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        
        count = 0
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        for sub_name in ['wallstreetbets', 'stocks', 'options']:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.new(limit=30):
                    post_time = datetime.utcfromtimestamp(post.created_utc)
                    if post_time < cutoff_time:
                        continue
                    
                    text = f"{post.title} {post.selftext}"
                    text_upper = text.upper()
                    
                    if f"${ticker}" in text_upper:
                        count += 1
            except:
                continue
        
        return count
    except:
        return 0


def check_accelerating(ticker: str, reddit_mentions: int) -> Dict:
    """Check Twitter buzz."""
    try:
        url = "https://api.twitterapi.io/twitter/community/get_tweets_from_all_community"
        params = {"query": f"${ticker}", "queryType": "Latest"}
        headers = {"X-API-Key": TWITTER_API_KEY}
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
            return {'is_accelerating': False, 'buzz_level': 'None', 'recent_mentions': 0}
        
        tweets = response.json().get("tweets", [])
        recent = len(tweets)
        
        is_accelerating = recent >= MIN_TWITTER_BUZZ or reddit_mentions >= MIN_REDDIT_BUZZ
        
        if recent > 50:
            buzz_level = "Explosive"
        elif recent > 30:
            buzz_level = "Strong"
        elif recent >= 15:
            buzz_level = "Moderate"
        else:
            buzz_level = "Weak"
        
        return {
            'is_accelerating': is_accelerating,
            'recent_mentions': recent,
            'buzz_level': buzz_level
        }
    except:
        return {'is_accelerating': False, 'buzz_level': 'None', 'recent_mentions': 0}


def check_squeeze(ticker: str) -> Dict:
    """Check short interest."""
    try:
        info = yf.Ticker(ticker).info
        short_percent = info.get('shortPercentOfFloat', 0) * 100
        has_squeeze = short_percent > MAX_SHORT_PERCENT
        
        return {
            'short_percent': round(short_percent, 2),
            'has_squeeze': has_squeeze
        }
    except:
        return {'short_percent': 0, 'has_squeeze': False}


def get_quality_data(ticker: str) -> Dict:
    """Get stock data with all metrics."""
    try:
        info = yf.Ticker(ticker).info
        
        sector = info.get('sector', 'Unknown')
        if sector in BANNED_SECTORS:
            return None
        
        market_cap = info.get('marketCap', 0)
        volume = info.get('volume', 0)
        avg_volume = info.get('averageVolume', 0)
        price = info.get('currentPrice', 0)
        
        if market_cap < 2_000_000_000:
            cap_size = "Small (<$2B)"
        elif market_cap < 10_000_000_000:
            cap_size = "Mid ($2-10B)"
        elif market_cap < 50_000_000_000:
            cap_size = "Large ($10-50B)"
        else:
            cap_size = "Mega (>$50B)"
        
        volume_ratio = volume / avg_volume if avg_volume > 0 else 0
        volume_spike = volume_ratio > 1.5
        
        bb_position = calculate_bollinger_position(ticker)
        atr_pct = calculate_atr_normalized(ticker)
        vol_trend = calculate_volume_trend(ticker)
        rsi = get_rsi(ticker)
        positioning = calculate_52w_positioning(ticker)
        
        return {
            'market_cap': market_cap,
            'cap_size': cap_size,
            'sector': sector,
            'volume': volume,
            'avg_volume': avg_volume,
            'volume_ratio': round(volume_ratio, 2),
            'volume_spike': volume_spike,
            'price': price,
            'bb_position': bb_position,
            'atr_pct': atr_pct,
            'volume_trend': vol_trend,
            'rsi': rsi,
            'dist_52w_high': positioning['dist_52w_high'],
            'dist_52w_low': positioning['dist_52w_low'],
        }
    except:
        return None


def save_entry_dates(orders):
    """Save entry dates for 7-day tracking."""
    try:
        with open(POSITIONS_FILE, 'r') as f:
            data = json.load(f)
    except:
        data = {}
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    for order in orders:
        data[order['ticker']] = {
            'entry_date': today,
            'shares': order['shares'],
            'entry_price': order['entry_price']
        }
    
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"💾 Saved entry dates for {len(orders)} positions")


def sell_seven_day_positions():
    """Sell positions that are 7+ days old."""
    
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("⚠️  Alpaca not configured - skipping auto-sell")
        return []
    
    try:
        try:
            with open(POSITIONS_FILE, 'r') as f:
                tracked_positions = json.load(f)
        except:
            print("📝 No tracked positions yet")
            return []
        
        api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url=ALPACA_BASE_URL)
        
        today = datetime.now().date()
        positions = api.list_positions()
        sells = []
        
        print("\n🔄 Checking positions for 7-day exit...")
        
        for position in positions:
            ticker = position.symbol
            
            if ticker not in tracked_positions:
                print(f"  ⚠️  {ticker}: Not in tracker (manual position?)")
                continue
            
            entry_date = datetime.strptime(tracked_positions[ticker]['entry_date'], '%Y-%m-%d').date()
            days_held = (today - entry_date).days
            
            if days_held >= 7:
                qty = int(position.qty)
                current_price = float(position.current_price)
                entry_price = tracked_positions[ticker]['entry_price']
                
                try:
                    order = api.submit_order(
                        symbol=ticker,
                        qty=qty,
                        side='sell',
                        type='market',
                        time_in_force='day'
                    )
                    
                    return_pct = ((current_price - entry_price) / entry_price) * 100
                    profit = (current_price - entry_price) * qty
                    
                    sells.append({
                        'ticker': ticker,
                        'days_held': days_held,
                        'return_pct': return_pct,
                        'profit': profit
                    })
                    
                    print(f"  ✅ SELL {qty} {ticker} (Day {days_held}) @ ${current_price:.2f} ({return_pct:+.2f}%) | P&L: ${profit:+,.2f}")
                    
                    del tracked_positions[ticker]
                
                except Exception as e:
                    print(f"  ❌ {ticker} sell failed: {e}")
            else:
                print(f"  📅 {ticker}: Day {days_held}/7 (hold)")
        
        with open(POSITIONS_FILE, 'w') as f:
            json.dump(tracked_positions, f, indent=2)
        
        if sells:
            total_profit = sum(s['profit'] for s in sells)
            avg_return = sum(s['return_pct'] for s in sells) / len(sells)
            print(f"\n✅ Closed {len(sells)} positions | Avg: {avg_return:+.2f}% | Total P&L: ${total_profit:+,.2f}")
        else:
            print("\n📝 No positions ready to exit")
        
        return sells
    
    except Exception as e:
        print(f"❌ Alpaca sell failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def place_paper_trades(picks: List[Dict]):
    """Place paper trades on Alpaca ($500 per stock)."""
    
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("⚠️  Alpaca credentials not set")
        return []
    
    try:
        api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url=ALPACA_BASE_URL)
        
        account = api.get_account()
        print(f"\n💰 Alpaca: ${float(account.cash):,.2f} cash, ${float(account.portfolio_value):,.2f} portfolio")
        
        position_value = 500.0
        orders_placed = []
        
        for pick in picks:
            ticker = pick['ticker']
            price = pick['price']
            
            # Calculate shares to get closest to $500
            shares_floor = int(position_value / price)
            shares_ceil = shares_floor + 1
            
            # Calculate how close each option is to $500
            cost_floor = shares_floor * price
            cost_ceil = shares_ceil * price
            
            # Pick whichever is closer to $500
            if abs(cost_ceil - position_value) < abs(cost_floor - position_value):
                shares = shares_ceil
            else:
                shares = shares_floor
            
            if shares < 1:
                shares = 1
            
            try:
                order = api.submit_order(
                    symbol=ticker,
                    qty=shares,
                    side='buy',
                    type='market',
                    time_in_force='day'
                )
                
                cost = shares * price
                
                orders_placed.append({
                    'ticker': ticker,
                    'shares': shares,
                    'entry_price': price,
                    'estimated_value': cost
                })
                
                print(f"  ✅ BUY {shares} {ticker} @ ${price:.2f} (${cost:.2f})")
            
            except Exception as e:
                print(f"  ❌ {ticker}: {e}")
        
        total = sum(o['estimated_value'] for o in orders_placed)
        print(f"\n✅ Placed {len(orders_placed)} orders (${total:,.2f} total)")
        
        if orders_placed:
            save_entry_dates(orders_placed)
        
        return orders_placed
    
    except Exception as e:
        print(f"❌ Alpaca failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def scan() -> Tuple[List[Dict], List[Dict]]:
    """
    Run scan.
    - V3 scoring for SELECTION (internal)
    - V4 scoring for DISPLAY (external)
    - Prevents same stock being picked twice in same week
    """
    
    universe = get_universe()
    picks = []
    
    # Track this week's picks to avoid repeats
    this_week_file = "this_week_picks.json"
    try:
        with open(this_week_file, 'r') as f:
            week_data = json.load(f)
            # Check if it's a new week (reset on Monday)
            today = datetime.now()
            last_week = week_data.get('week_number', 0)
            current_week = today.isocalendar()[1]  # ISO week number
            
            if current_week != last_week:
                # New week - reset picks
                this_week_picks = set()
                print(f"📅 New week detected (Week {current_week}) - Reset weekly tracker")
            else:
                # Same week - load existing picks
                this_week_picks = set(week_data.get('tickers', []))
                print(f"📅 Same week (Week {current_week}) - Loaded {len(this_week_picks)} already-picked tickers")
    except:
        # File doesn't exist - first run
        this_week_picks = set()
        current_week = datetime.now().isocalendar()[1]
        print(f"📅 First run of week {current_week}")
    
    print(f"\n🔍 Scanning {len(universe)} stocks...\n")
    
    for ticker in universe:
        try:
            quality = get_quality_data(ticker)
            if not quality or len(ticker) == 1:
                continue
            
            if quality['market_cap'] < MIN_MARKET_CAP:
                continue
            if quality['price'] < MIN_PRICE:
                continue
            if quality['price'] * quality['volume'] < MIN_VOLUME_USD:
                continue
            
            fresh_data = check_fresh(ticker)
            if not fresh_data or not fresh_data['is_fresh']:
                continue
            
            reddit_mentions = check_reddit_confirmation(ticker)
            accel_data = check_accelerating(ticker, reddit_mentions)
            if not accel_data['is_accelerating']:
                continue
            
            squeeze_data = check_squeeze(ticker)
            if squeeze_data['has_squeeze']:
                continue
            
            # Skip if already picked this week
            if ticker in this_week_picks:
                print(f"  ⏭️  Skipping {ticker} (already picked this week)")
                continue
            
            pick = {
                'ticker': ticker,
                'entry_date': datetime.now().strftime('%Y-%m-%d'),
                'entry_time': datetime.now().strftime('%I:%M %p'),
                'entry_day': datetime.now().strftime('%A'),
                'price': fresh_data['price'],
                'change_7d': fresh_data['change_7d'],
                'change_90d': fresh_data['change_90d'],
                'market_cap': quality['market_cap'],
                'cap_size': quality['cap_size'],
                'sector': quality['sector'],
                'twitter_mentions': accel_data['recent_mentions'],
                'reddit_mentions': reddit_mentions,
                'buzz_level': accel_data['buzz_level'],
                'volume_ratio': quality['volume_ratio'],
                'volume_spike': quality['volume_spike'],
                'short_percent': squeeze_data['short_percent'],
                'is_fresh': True,
                'is_accelerating': True,
                'has_squeeze': False,
                'bb_position': quality['bb_position'],
                'atr_pct': quality['atr_pct'],
                'volume_trend': quality['volume_trend'],
                'rsi': quality['rsi'],
                'dist_52w_high': quality['dist_52w_high'],
                'dist_52w_low': quality['dist_52w_low'],
                'group': 'V3',
            }
            
            # V3 score for SELECTION
            pick['quality_score'] = calculate_quality_score(pick)
            
            # V4 score for DISPLAY
            pick['v4_score'] = calculate_quality_score_v4(pick)
            
            picks.append(pick)
        
        except:
            continue
    
    # Sort by V3 score (selection unchanged)
    picks.sort(key=lambda x: x['quality_score'], reverse=True)
    top_picks = picks[:10]
    
    # Save this week's picks to tracker
    for pick in top_picks:
        this_week_picks.add(pick['ticker'])
    
    # Write to file
    week_data = {
        'week_number': current_week,
        'tickers': list(this_week_picks),
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    with open(this_week_file, 'w') as f:
        json.dump(week_data, f, indent=2)
    
    print(f"\n📊 Found {len(picks)} Fresh+Accel stocks")
    print(f"🎯 Returning top 10 by V3 quality score")
    print(f"📈 Displaying V4 scores for tracking")
    print(f"🔒 Weekly tracker: {len(this_week_picks)} unique tickers this week\n")
    
    # Control group
    print(f"🎲 Selecting 5 random stocks as control group...\n")
    
    control_group = []
    random_candidates = [t for t in universe if t not in [p['ticker'] for p in top_picks]]
    random.shuffle(random_candidates)
    
    for ticker in random_candidates[:30]:
        try:
            info = yf.Ticker(ticker).info
            sector = info.get('sector', 'Unknown')
            market_cap = info.get('marketCap', 0)
            
            if market_cap < MIN_MARKET_CAP:
                continue
            
            fresh_data = check_fresh(ticker)
            if not fresh_data:
                continue
            
            positioning = calculate_52w_positioning(ticker)
            
            control = {
                'ticker': ticker,
                'entry_date': datetime.now().strftime('%Y-%m-%d'),
                'entry_time': datetime.now().strftime('%I:%M %p'),
                'entry_day': datetime.now().strftime('%A'),
                'price': fresh_data['price'],
                'change_7d': fresh_data['change_7d'],
                'sector': sector,
                'market_cap': market_cap,
                'dist_52w_high': positioning['dist_52w_high'],
                'dist_52w_low': positioning['dist_52w_low'],
                'group': 'CONTROL',
            }
            
            control_group.append(control)
            
            if len(control_group) >= 5:
                break
        except:
            continue
    
    print(f"✅ Control group: {len(control_group)} random stocks\n")
    
    return top_picks, control_group

def save_picks(all_picks: List[Dict]):
    """Save to CSV."""
    if not all_picks:
        return
    
    df = pd.DataFrame(all_picks)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"outputs/supabot_v3_scan_{timestamp}.csv"
    
    os.makedirs("outputs", exist_ok=True)
    df.to_csv(filename, index=False)
    
    print(f"✅ Saved {len(all_picks)} picks (including control) to {filename}")
    return df


def display_picks(picks: List[Dict], control: List[Dict]):
    """Display picks with V4 scores."""
    if not picks:
        print("\n❌ No Fresh+Accel stocks found")
        return
    
    print(f"\n{'='*80}")
    print(f"🎯 TOP 10 PICKS (V3 Strategy)")
    print(f"{'='*80}\n")
    
    for i, pick in enumerate(picks, 1):
        volume_flag = " 📊" if pick['volume_spike'] else ""
        
        print(f"{i}. {pick['ticker']} - ${pick['price']:.2f} (V4 Score: {pick['v4_score']:.0f})")
        print(f"   {pick['sector']} | Fresh: {pick['change_7d']:+.1f}% | {pick['cap_size']}")
        print(f"   Buzz: {pick['buzz_level']} ({pick['twitter_mentions']}🐦 {pick['reddit_mentions']}🤖){volume_flag}")
        print(f"   📊 SI: {pick['short_percent']:.1f}% | 52w: {pick['dist_52w_high']:+.1f}%")
        print()
    
    print(f"{'='*80}\n")
    
    if control:
        print(f"\n{'='*80}")
        print(f"🎲 CONTROL GROUP (5 Random Stocks)")
        print(f"{'='*80}\n")
        
        for i, stock in enumerate(control, 1):
            print(f"{i}. {stock['ticker']} - ${stock['price']:.2f}")
            print(f"   {stock['sector']} | Fresh: {stock['change_7d']:+.1f}%")
            print(f"   52w: {stock['dist_52w_high']:+.1f}% from high\n")
        
        print(f"{'='*80}\n")


def send_discord_notification(picks: List[Dict], control: List[Dict]):
    """Send to Discord with V4 scores."""
    
    DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_V3")
    if not DISCORD_WEBHOOK:
        print("⚠️  DISCORD_WEBHOOK_V3 not set")
        return
    
    try:
        from discord_webhook import DiscordWebhook, DiscordEmbed
        
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK, username="Supabot V3")
        
        if not picks:
            embed = DiscordEmbed(
                title="📊 Supabot V3 Scan Complete",
                description="No Fresh+Accel picks today",
                color='808080'
            )
            embed.set_footer(text=f"V3 + V4 Scoring | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
            webhook.add_embed(embed)
            webhook.execute()
            return
        
        embed = DiscordEmbed(
            title=f"🎯 Supabot V3: {len(picks)} Picks",
            description=f"V4 Scores Shown (V3 selection) | Testing V4 Scoring System",
            color='00ff00'
        )
        
        for i, pick in enumerate(picks, 1):
            signals = ["✨", "📈"]
            if pick.get('volume_spike'):
                signals.append("📊")
            
            signal_str = " ".join(signals)
            
            main_line = f"**${pick['price']:.2f}** | V4: {pick['v4_score']:.0f} | {pick['sector']} | {pick['cap_size']}"
            price_line = f"Fresh: {pick['change_7d']:+.1f}% | Buzz: {pick['buzz_level']} ({pick['twitter_mentions']}🐦 {pick['reddit_mentions']}🤖) | SI: {pick['short_percent']:.1f}%"
            tech_line = f"52w: {pick['dist_52w_high']:+.1f}% | BB: {pick['bb_position']:.2f} | ATR: {pick['atr_pct']:.1f}% | Vol: {pick['volume_trend']:.2f}x | RSI: {pick['rsi']:.0f}"
            
            value = f"{main_line}\n{price_line}\n{tech_line}"
            
            embed.add_embed_field(
                name=f"#{i}. {pick['ticker']} {signal_str}",
                value=value,
                inline=False
            )
        
        avg_v4 = sum(p['v4_score'] for p in picks) / len(picks)
        avg_52w = sum(p['dist_52w_high'] for p in picks) / len(picks)
        avg_bb = sum(p['bb_position'] for p in picks) / len(picks)
        
        embed.add_embed_field(
            name="📈 Summary",
            value=f"Avg V4 Score: {avg_v4:.0f} | Avg BB: {avg_bb:.2f} | Avg 52w: {avg_52w:+.1f}%",
            inline=False
        )
        
        embed.set_footer(text=f"V3 Selection + V4 Display | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
        webhook.add_embed(embed)
        
        if control:
            control_embed = DiscordEmbed(
                title=f"🎲 Control Group: {len(control)} Random Stocks",
                description="No filters applied - testing if edge is real",
                color='808080'
            )
            
            control_lines = []
            for c in control:
                control_lines.append(f"**{c['ticker']}** (${c['price']:.2f}) | {c['sector']} | Fresh: {c['change_7d']:+.1f}%")
            
            control_embed.add_embed_field(
                name="Random Picks",
                value="\n".join(control_lines),
                inline=False
            )
            
            control_embed.set_footer(text="Compare performance vs V3 picks after 7 days")
            webhook.add_embed(control_embed)
        
        webhook.execute()
        print("✅ Discord notification sent with V4 scores!")
    
    except Exception as e:
        print(f"❌ Discord failed: {e}")


if __name__ == "__main__":
    
    print("\n" + "="*80)
    print("🤖 SUPABOT V3 - V4 SCORE TRACKING")
    print("="*80)
    
    start_time = datetime.now()
    
    print(f"{'='*80}")
    print("📤 CHECKING FOR 7-DAY EXITS...")
    print(f"{'='*80}")
    sell_seven_day_positions()
    print(f"{'='*80}\n")
    
    picks, control = scan()
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    display_picks(picks, control)
    
    if picks or control:
        all_picks = picks + control
        save_picks(all_picks)
    
    print(f"{'='*80}")
    print("📤 SENDING DISCORD NOTIFICATION...")
    print(f"{'='*80}")
    send_discord_notification(picks, control)
    print(f"{'='*80}\n")
    
    print(f"{'='*80}")
    print("📈 PLACING ALPACA PAPER TRADES ($500/stock)...")
    print(f"{'='*80}")
    place_paper_trades(picks)
    print(f"{'='*80}\n")
    
    print(f"\n⏱️  Scan completed in {elapsed:.1f} seconds")
    print(f"✅ Complete - {len(picks)} V3 picks + {len(control)} control + V4 scoring!\n")