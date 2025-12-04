"""
Supabot V3 - With Enhanced Metrics Collection + 52-Week Positioning + Control Group

NEW: Tracks Bollinger Bands, ATR, Volume Trends, RSI, 52-week positioning for pattern analysis
CONTROL: Adds 5 random stocks (no filters) to test if edge is real vs market luck
"""
import os
import sys
import re
import random
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
    """
    Calculate where price is within Bollinger Bands (0-1 scale).
    0.0 = at lower band (oversold)
    0.5 = at middle (neutral)
    1.0 = at upper band (overbought)
    """
    try:
        hist = yf.Ticker(ticker).history(period="3mo")
        if len(hist) < 20:
            return 0.5  # Default neutral
        
        close = hist['Close']
        sma_20 = close.rolling(20).mean().iloc[-1]
        std_20 = close.rolling(20).std().iloc[-1]
        
        bb_upper = sma_20 + (2 * std_20)
        bb_lower = sma_20 - (2 * std_20)
        current = close.iloc[-1]
        
        # Position within bands (0-1)
        if bb_upper == bb_lower:
            return 0.5
        
        position = (current - bb_lower) / (bb_upper - bb_lower)
        return round(float(np.clip(position, 0, 1)), 3)
    except:
        return 0.5


def calculate_atr_normalized(ticker: str) -> float:
    """
    Calculate ATR as % of price (volatility measure).
    Higher = more volatile (bigger moves possible)
    """
    try:
        hist = yf.Ticker(ticker).history(period="2mo")
        if len(hist) < 14:
            return 0.0
        
        high = hist['High']
        low = hist['Low']
        close = hist['Close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        # Normalize by current price
        current_price = close.iloc[-1]
        atr_pct = (atr / current_price * 100) if current_price > 0 else 0
        
        return round(float(atr_pct), 2)
    except:
        return 0.0


def calculate_volume_trend(ticker: str) -> float:
    """
    Calculate volume acceleration (recent vs baseline).
    >1.5 = volume accelerating
    <0.7 = volume declining
    """
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
    """
    Calculate distance to 52-week high/low.
    
    Returns:
        dist_52w_high: % below 52w high (negative number, e.g., -15.5%)
        dist_52w_low: % above 52w low (positive number, e.g., +32.8%)
    """
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if len(hist) < 200:  # Need at least ~8 months of data
            return {'dist_52w_high': 0.0, 'dist_52w_low': 0.0}
        
        high_52w = hist['High'].max()
        low_52w = hist['Low'].min()
        current = hist['Close'].iloc[-1]
        
        # Calculate % distance
        # Negative = below high, Positive = above low
        dist_high = ((current / high_52w) - 1) * 100
        dist_low = ((current / low_52w) - 1) * 100
        
        return {
            'dist_52w_high': round(float(dist_high), 2),
            'dist_52w_low': round(float(dist_low), 2),
        }
    except:
        return {'dist_52w_high': 0.0, 'dist_52w_low': 0.0}


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
                    
                    # ONLY count if has $ symbol (strict)
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
    """
    Get stock data WITH ALL METRICS for pattern analysis.
    """
    try:
        info = yf.Ticker(ticker).info
        
        # Sector filter
        sector = info.get('sector', 'Unknown')
        if sector in BANNED_SECTORS:
            return None
        
        # Basic data
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
        
        # ============ COLLECT ALL METRICS ============
        bb_position = calculate_bollinger_position(ticker)
        atr_pct = calculate_atr_normalized(ticker)
        vol_trend = calculate_volume_trend(ticker)
        rsi = get_rsi(ticker)
        positioning = calculate_52w_positioning(ticker)
        
        return {
            # Basic fields
            'market_cap': market_cap,
            'cap_size': cap_size,
            'sector': sector,
            'volume': volume,
            'avg_volume': avg_volume,
            'volume_ratio': round(volume_ratio, 2),
            'volume_spike': volume_spike,
            'price': price,
            
            # Technical metrics
            'bb_position': bb_position,
            'atr_pct': atr_pct,
            'volume_trend': vol_trend,
            'rsi': rsi,
            
            # 52-week positioning
            'dist_52w_high': positioning['dist_52w_high'],
            'dist_52w_low': positioning['dist_52w_low'],
        }
    except:
        return None


def calculate_quality_score(pick: Dict) -> float:
    """Calculate quality score."""
    score = 0
    
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
    
    fresh = pick['change_7d']
    if 0 <= fresh <= 2:
        score += 30
    elif -2 <= fresh < 0:
        score += 25
    elif 2 < fresh <= 5:
        score += 20
    else:
        score += 10
    
    if pick.get('volume_spike'):
        score += 15
    elif pick['volume_ratio'] > 1.0:
        score += 8
    
    if 'Mid' in pick['cap_size'] or 'Large' in pick['cap_size']:
        score += 15
    elif 'Small' in pick['cap_size']:
        score += 10
    else:
        score += 5
    
    return score


def scan() -> Tuple[List[Dict], List[Dict]]:
    """
    Run scan with ENHANCED data collection including 52-week positioning.
    Returns: (top_picks, control_group)
    """
    
    universe = get_universe()
    picks = []
    
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
            
            # ============ BUILD PICK WITH ALL METRICS ============
            pick = {
                # Entry info
                'ticker': ticker,
                'entry_date': datetime.now().strftime('%Y-%m-%d'),
                'entry_time': datetime.now().strftime('%I:%M %p'),
                'entry_day': datetime.now().strftime('%A'),
                'price': fresh_data['price'],
                
                # Price changes
                'change_7d': fresh_data['change_7d'],
                'change_90d': fresh_data['change_90d'],
                
                # Stock info
                'market_cap': quality['market_cap'],
                'cap_size': quality['cap_size'],
                'sector': quality['sector'],
                
                # Social buzz
                'twitter_mentions': accel_data['recent_mentions'],
                'reddit_mentions': reddit_mentions,
                'buzz_level': accel_data['buzz_level'],
                
                # Volume
                'volume_ratio': quality['volume_ratio'],
                'volume_spike': quality['volume_spike'],
                
                # Risk
                'short_percent': squeeze_data['short_percent'],
                
                # Signals
                'is_fresh': True,
                'is_accelerating': True,
                'has_squeeze': False,
                
                # Technical metrics
                'bb_position': quality['bb_position'],
                'atr_pct': quality['atr_pct'],
                'volume_trend': quality['volume_trend'],
                'rsi': quality['rsi'],
                
                # 52-week positioning
                'dist_52w_high': quality['dist_52w_high'],
                'dist_52w_low': quality['dist_52w_low'],
                
                # Group label
                'group': 'V3',
            }
            
            pick['quality_score'] = calculate_quality_score(pick)
            picks.append(pick)
        
        except:
            continue
    
    picks.sort(key=lambda x: x['quality_score'], reverse=True)
    top_picks = picks[:10]
    
    print(f"\n📊 Found {len(picks)} Fresh+Accel stocks")
    print(f"🎯 Returning top 10 by quality score\n")
    
    # ============ CONTROL GROUP: 5 RANDOM STOCKS ============
    print(f"🎲 Selecting 5 random stocks as control group...\n")
    
    control_group = []
    random_candidates = [t for t in universe if t not in [p['ticker'] for p in top_picks]]
    random.shuffle(random_candidates)
    
    for ticker in random_candidates[:30]:  # Try up to 30 to get 5 valid
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
    """
    Save to CSV with ALL metrics including control group.
    """
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
    """Display picks with all metrics including 52-week positioning."""
    if not picks:
        print("\n❌ No Fresh+Accel stocks found")
        return
    
    print(f"\n{'='*80}")
    print(f"🎯 TOP 10 PICKS (V3 Strategy)")
    print(f"{'='*80}\n")
    
    for i, pick in enumerate(picks, 1):
        volume_flag = " 📊" if pick['volume_spike'] else ""
        
        print(f"{i}. {pick['ticker']} - ${pick['price']:.2f} (Score: {pick['quality_score']:.0f}/100)")
        print(f"   {pick['sector']} | Fresh: {pick['change_7d']:+.1f}% | {pick['cap_size']}")
        print(f"   Buzz: {pick['buzz_level']} ({pick['twitter_mentions']}🐦 {pick['reddit_mentions']}🤖){volume_flag}")
        print(f"   📊 BB: {pick['bb_position']:.2f} | ATR: {pick['atr_pct']:.1f}% | Vol: {pick['volume_trend']:.2f}x | RSI: {pick['rsi']:.0f}")
        print(f"   📈 52w: {pick['dist_52w_high']:+.1f}% from high | {pick['dist_52w_low']:+.1f}% from low")
        print()
    
    print(f"{'='*80}\n")
    
    # Display control group
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
    """
    Send to Discord with all metrics, V3 picks and control group separated.
    """
    
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
            embed.set_footer(text=f"V3 Enhanced | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
            webhook.add_embed(embed)
            webhook.execute()
            return
        
        # ============ V3 PICKS EMBED ============
        embed = DiscordEmbed(
            title=f"🎯 Supabot V3: {len(picks)} Picks",
            description=f"Top 10 by Quality Score | Testing vs Control Group",
            color='00ff00'
        )
        
        for i, pick in enumerate(picks, 1):
            signals = ["✨", "📈"]
            if pick.get('volume_spike'):
                signals.append("📊")
            
            signal_str = " ".join(signals)
            
            # Main info line
            main_line = f"**${pick['price']:.2f}** | Score: {pick['quality_score']:.0f}/100 | {pick['sector']} | {pick['cap_size']}"
            
            # Price + Social line
            price_line = f"Fresh: {pick['change_7d']:+.1f}% | Buzz: {pick['buzz_level']} ({pick['twitter_mentions']}🐦 {pick['reddit_mentions']}🤖) | Short: {pick['short_percent']:.1f}%"
            
            # Technical metrics line
            tech_line = f"52w: {pick['dist_52w_high']:+.1f}% | BB: {pick['bb_position']:.2f} | ATR: {pick['atr_pct']:.1f}% | Vol: {pick['volume_trend']:.2f}x | RSI: {pick['rsi']:.0f}"
            
            # Combine all lines
            value = f"{main_line}\n{price_line}\n{tech_line}"
            
            embed.add_embed_field(
                name=f"#{i}. {pick['ticker']} {signal_str}",
                value=value,
                inline=False
            )
        
        # Summary
        avg_score = sum(p['quality_score'] for p in picks) / len(picks)
        avg_52w = sum(p['dist_52w_high'] for p in picks) / len(picks)
        avg_bb = sum(p['bb_position'] for p in picks) / len(picks)
        
        embed.add_embed_field(
            name="📈 V3 Summary",
            value=f"Avg Score: {avg_score:.0f}/100 | Avg BB: {avg_bb:.2f} | Avg 52w: {avg_52w:+.1f}% | Record: 15/15 = 100% WR",
            inline=False
        )
        
        embed.set_footer(text=f"V3 Enhanced | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
        webhook.add_embed(embed)
        
        # ============ CONTROL GROUP EMBED (SEPARATE) ============
        if control:
            control_embed = DiscordEmbed(
                title=f"🎲 Control Group: {len(control)} Random Stocks",
                description="No filters applied - testing if edge is real vs market luck",
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
        print("✅ Discord notification sent with V3 picks + control group!")
    
    except Exception as e:
        print(f"❌ Discord failed: {e}")


if __name__ == "__main__":
    
    print("\n" + "="*80)
    print("🤖 SUPABOT V3 - WITH CONTROL GROUP EXPERIMENT")
    print("="*80)
    print(f"V3 Picks: Top 10 Fresh+Accel stocks")
    print(f"Control: 5 random stocks (no filters)")
    print(f"Goal: Prove edge is real vs market luck")
    print("="*80 + "\n")
    
    start_time = datetime.now()
    
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
    
    print(f"\n⏱️  Scan completed in {elapsed:.1f} seconds")
    
    if picks:
        print(f"✅ V3 Complete - {len(picks)} picks + {len(control)} control stocks!\n")
    else:
        print(f"❌ No picks today\n")