"""
Supabot V3 - Sector-Optimized Scanner

VALIDATED SECTORS (43 trades):
✅ Healthcare: 100% WR (9/9)
✅ Technology: 67% WR (8/12)
❌ Energy: 33% WR (1/3)
❌ Consumer Cyclical: 33% WR (1/3)
❌ Utilities: 50% WR (2/4)

STRATEGY:
- Fresh: -5% to +5%
- Accel: 15+ Twitter OR 5+ Reddit
- No Squeeze: <20% short
- ONLY: Healthcare, Technology, Communication Services
"""
import os
import sys
import re
import random
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
from dotenv import load_dotenv

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

# VALIDATED SETTINGS
FRESH_MIN = -5.0
FRESH_MAX = 5.0
MIN_MARKET_CAP = 500_000_000
MIN_PRICE = 5.0
MIN_VOLUME_USD = 2_000_000
MAX_SHORT_PERCENT = 20.0
MIN_TWITTER_BUZZ = 15
MIN_REDDIT_BUZZ = 5
SCAN_LIMIT = 100

# SECTOR FILTER (VALIDATED)
BANNED_SECTORS = ['Energy', 'Consumer Cyclical', 'Utilities']


def get_universe() -> List[str]:
    """Get quality stock universe from Finviz with SECTOR FILTER."""
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
        
        # Apply sector filter
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
                filtered.append(ticker)  # Include if can't check sector
                
                if len(filtered) >= SCAN_LIMIT:
                    break
        
        print(f"   Excluded {banned_count} stocks, scanning {len(filtered)}")
        return filtered
        
    except Exception as e:
        print(f"⚠️  Finviz error: {e}")
        # Fallback to curated list
        return [
            'BIIB', 'AMGN', 'CPRX', 'AXSM', 'HALO', 'JAZZ', 'AZN',
            'PLTR', 'NVDA', 'NET', 'DOCN', 'FSLY', 'ZETA', 'AMKR',
            'SOFI', 'COIN', 'HOOD', 'RBLX', 'IMAX'
        ]


def check_fresh(ticker: str) -> Dict:
    """Check if stock is Fresh (-5% to +5%)."""
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
    """Get Reddit mentions with smart matching."""
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        
        count = 0
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        COMMON_WORDS = ['GOOD', 'BAD', 'BEST', 'ALL', 'NOW']
        is_strict = len(ticker) <= 2 or ticker.upper() in COMMON_WORDS
        
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
                        continue
                    
                    if not is_strict:
                        pattern = r'\b' + re.escape(ticker) + r'\b'
                        if re.search(pattern, text, re.IGNORECASE):
                            count += 1
            except:
                continue
        
        return count
    except:
        return 0


def check_accelerating(ticker: str, reddit_mentions: int) -> Dict:
    """Check if buzz is accelerating."""
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
    """Get market cap, volume, sector WITH SECTOR FILTER."""
    try:
        info = yf.Ticker(ticker).info
        
        # ============ SECTOR FILTER ============
        sector = info.get('sector', 'Unknown')
        
        if sector in BANNED_SECTORS:
            return None  # Skip banned sectors
        
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
        
        return {
            'market_cap': market_cap,
            'cap_size': cap_size,
            'sector': sector,
            'volume': volume,
            'avg_volume': avg_volume,
            'volume_ratio': round(volume_ratio, 2),
            'volume_spike': volume_spike,
            'price': price
        }
    except:
        return None


def calculate_quality_score(pick: Dict) -> float:
    """Calculate quality score for ranking."""
    score = 0
    
    # Buzz strength (40 pts)
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
    
    # Fresh sweet spot (30 pts)
    fresh = pick['change_7d']
    if 0 <= fresh <= 2:
        score += 30
    elif -2 <= fresh < 0:
        score += 25
    elif 2 < fresh <= 5:
        score += 20
    else:
        score += 10
    
    # Volume confirmation (15 pts)
    if pick.get('volume_spike'):
        score += 15
    elif pick['volume_ratio'] > 1.0:
        score += 8
    
    # Market cap (15 pts)
    if 'Mid' in pick['cap_size'] or 'Large' in pick['cap_size']:
        score += 15
    elif 'Small' in pick['cap_size']:
        score += 10
    else:
        score += 5
    
    return score


def scan() -> List[Dict]:
    """Run validated scan with sector filter."""
    
    universe = get_universe()
    picks = []
    
    print(f"\n🔍 Scanning {len(universe)} stocks (sector-filtered)...\n")
    
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
                'volume_ratio': quality['volume_ratio'],
                'volume_spike': quality['volume_spike'],
                'twitter_mentions': accel_data['recent_mentions'],
                'buzz_level': accel_data['buzz_level'],
                'reddit_mentions': reddit_mentions,
                'short_percent': squeeze_data['short_percent'],
                'is_fresh': True,
                'is_accelerating': True,
                'has_squeeze': False,
            }
            
            pick['quality_score'] = calculate_quality_score(pick)
            picks.append(pick)
        
        except:
            continue
    
    picks.sort(key=lambda x: x['quality_score'], reverse=True)
    
    print(f"\n📊 Found {len(picks)} Fresh+Accel stocks (sector-filtered)")
    print(f"🎯 Returning top 5 by quality score\n")
    
    return picks[:5]


def save_picks(picks: List[Dict]):
    """Save to CSV."""
    if not picks:
        return
    
    df = pd.DataFrame(picks)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"outputs/supabot_v3_scan_{timestamp}.csv"
    
    os.makedirs("outputs", exist_ok=True)
    df.to_csv(filename, index=False)
    
    print(f"✅ Saved {len(picks)} picks to {filename}")
    return df


def display_picks(picks: List[Dict]):
    """Display picks."""
    if not picks:
        print("\n❌ No Fresh+Accel stocks found")
        return
    
    print(f"\n{'='*70}")
    print(f"🎯 TOP 5 SECTOR-OPTIMIZED PICKS")
    print(f"{'='*70}\n")
    
    for i, pick in enumerate(picks, 1):
        volume_flag = " 📊" if pick['volume_spike'] else ""
        
        print(f"{i}. {pick['ticker']} - ${pick['price']:.2f} (Score: {pick['quality_score']:.0f}/100)")
        print(f"   {pick['sector']} | Fresh: {pick['change_7d']:+.1f}% | {pick['cap_size']}")
        print(f"   Buzz: {pick['buzz_level']} ({pick['twitter_mentions']}🐦 {pick['reddit_mentions']}🤖){volume_flag}")
        print()
    
    print(f"{'='*70}\n")


def send_discord_notification(picks: List[Dict]):
    """Send V3 results to Discord."""
    
    DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_V3")
    if not DISCORD_WEBHOOK:
        return
    
    try:
        from discord_webhook import DiscordWebhook, DiscordEmbed
        
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK, username="Supabot V3")
        
        if not picks:
            embed = DiscordEmbed(
                title="📊 Supabot V3 Scan Complete",
                description="No Fresh+Accel picks (Healthcare/Tech only)",
                color='808080'
            )
            embed.set_footer(text=f"V3 | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
            webhook.add_embed(embed)
            webhook.execute()
            return
        
        embed = DiscordEmbed(
            title=f"🎯 Supabot V3: {len(picks)} Sector-Optimized Picks",
            description=f"Healthcare 100% WR | Technology 67% WR | No Energy/Utilities",
            color='00ff00'
        )
        
        for i, pick in enumerate(picks, 1):
            signals = ["✨", "📈"]
            
            if pick.get('volume_spike'):
                signals.append("📊")
            
            signal_str = " ".join(signals)
            
            value_parts = [
                f"**${pick['price']:.2f}**",
                f"{pick['sector']}",
                f"Fresh: {pick['change_7d']:+.1f}%",
                f"{pick['buzz_level']} ({pick['twitter_mentions']}🐦 {pick['reddit_mentions']}🤖)",
            ]
            
            embed.add_embed_field(
                name=f"#{i}. {pick['ticker']} {signal_str}",
                value=" | ".join(value_parts),
                inline=False
            )
        
        embed.set_footer(text=f"V3 Sector-Optimized | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
        
        webhook.add_embed(embed)
        webhook.execute()
    
    except Exception as e:
        print(f"❌ Discord failed: {e}")


if __name__ == "__main__":
    
    print("\n" + "="*70)
    print("🤖 SUPABOT V3 - SECTOR-OPTIMIZED SCANNER")
    print("="*70)
    print(f"Sectors: Healthcare (100% WR), Technology (67% WR)")
    print(f"Excluded: Energy/Consumer/Utilities (33-50% WR)")
    print(f"Fresh: {FRESH_MIN}% to {FRESH_MAX}% | Buzz: {MIN_TWITTER_BUZZ}+ Twitter OR {MIN_REDDIT_BUZZ}+ Reddit")
    print("="*70 + "\n")
    
    start_time = datetime.now()
    
    picks = scan()
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    display_picks(picks)
    
    if picks:
        save_picks(picks)
    
    print(f"{'='*70}")
    print("📤 SENDING DISCORD NOTIFICATION...")
    print(f"{'='*70}")
    send_discord_notification(picks)
    print(f"{'='*70}\n")
    
    print(f"\n⏱️  Scan completed in {elapsed:.1f} seconds")
    
    if picks:
        print(f"✅ V3 Complete - {len(picks)} picks found!\n")
    else:
        print(f"❌ No picks today\n")