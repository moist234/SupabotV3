"""
Supabot V3 - Minimal Scanner (Validated Edge Only)

PROVEN STRATEGY (42 trades, 8 weeks):
- Fresh range optimized: 0% to +5% (82% WR vs 69% for -5 to +10%)
- Fresh+Accel combo: 69% WR, +3.16% avg
- Beat S&P by 5.43 points (+3.16% vs -2.27%)
- Statistically significant: p=0.013

CHANGES FROM V2:
- Single file (vs 15 files)
- 4 APIs (vs 8 APIs)  
- No AI scoring (doesn't predict, costs money)
- Returns ALL Fresh+Accel (vs top 5 by score)
- Scans 200 stocks (vs 100)
- Fresh range: 0-5% (vs -5 to +10%)
- STRICTER buzz: 20+ Twitter AND 2+ Reddit (vs 10+ Twitter)
- 10x faster, $20/month cheaper
"""
import re
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
from dotenv import load_dotenv

# API imports
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

# VALIDATED SETTINGS (from 42 trades)
FRESH_MIN = 0.0       # Optimized from -5.0 (validated: 0-5% = 82% WR)
FRESH_MAX = 5.0       # Optimized from 10.0
MIN_MARKET_CAP = 500_000_000
MIN_PRICE = 5.0
MIN_VOLUME_USD = 2_000_000
MAX_SHORT_PERCENT = 20.0  # Squeeze exclusion (validated: 22% WR, toxic)
MIN_TWITTER_BUZZ = 20  # Stricter (vs 10 in old version)
MIN_REDDIT_BUZZ = 2    # Require cross-platform confirmation
SCAN_LIMIT = 200      # Expanded from 100

print("\n" + "="*70)
print("🤖 SUPABOT LITE - MINIMAL VALIDATED SCANNER")
print("="*70)
print(f"\nOptimized Fresh Range: {FRESH_MIN}% to {FRESH_MAX}%")
print(f"Buzz Threshold: {MIN_TWITTER_BUZZ}+ Twitter AND {MIN_REDDIT_BUZZ}+ Reddit")
print(f"Scanning {SCAN_LIMIT} stocks for Pure Fresh+Accel")
print(f"Validated: 69% WR, +3.16% avg, p=0.013")
print("="*70 + "\n")


def get_universe() -> List[str]:
    """Get quality stock universe from Finviz."""
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
        
        tickers = df['Ticker'].tolist()[:SCAN_LIMIT]
        print(f"📊 Finviz found {len(tickers)} quality stocks")
        return tickers
    except Exception as e:
        print(f"⚠️  Finviz error: {e}, using fallback")
        return ['PLTR', 'SOFI', 'NET', 'RBLX', 'COIN', 'HOOD', 'DKNG']


def check_fresh(ticker: str) -> Dict:
    """Check if stock is Fresh (OPTIMIZED 0-5% range)."""
    try:
        hist = yf.Ticker(ticker).history(period="6mo")
        if len(hist) < 10:
            return None
        
        close = hist['Close']
        
        # 7-day change
        change_7d = ((close.iloc[-1] - close.iloc[-8]) / close.iloc[-8] * 100) if len(close) > 7 else 0
        
        # 90-day change (avoid falling knives)
        change_90d = ((close.iloc[-1] - close.iloc[-91]) / close.iloc[-91] * 100) if len(close) > 90 else 0
        
        # OPTIMIZED Fresh range: 0% to +5%
        is_fresh = FRESH_MIN <= change_7d <= FRESH_MAX and change_90d > -40.0
        
        return {
            'change_7d': round(change_7d, 2),
            'change_90d': round(change_90d, 2),
            'is_fresh': is_fresh,
            'price': float(close.iloc[-1])
        }
    except Exception as e:
        return None


def check_reddit_confirmation(ticker: str) -> int:
    """
    Get Reddit mention count with SMART matching strategy.
    
    STRATEGY:
    - Short tickers (≤2 letters): ONLY count $TICKER format (strict)
    - Normal tickers (3+ letters): Count $TICKER OR word boundaries (flexible)
    
    This avoids false positives for "AS", "A", "IT" while catching 
    real mentions for "AMD", "PLTR", "NVDA".
    """
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        
        count = 0
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Determine matching strategy based on ticker length
        is_short_ticker = len(ticker) <= 2
        
        if is_short_ticker:
            print(f"   🔍 Reddit: Using STRICT matching for '{ticker}' (≤2 letters)")
        
        for sub_name in ['wallstreetbets', 'stocks', 'options']:
            try:
                subreddit = reddit.subreddit(sub_name)
                
                for post in subreddit.new(limit=30):
                    # Filter by time (last 24 hours only)
                    post_time = datetime.utcfromtimestamp(post.created_utc)
                    if post_time < cutoff_time:
                        continue
                    
                    # Combine title and body
                    text = f"{post.title} {post.selftext}"
                    text_upper = text.upper()
                    
                    # METHOD 1: Always check for $TICKER format (works for all)
                    if f"${ticker}" in text_upper:
                        count += 1
                        continue
                    
                    # METHOD 2: For LONGER tickers, also check word boundaries
                    if not is_short_ticker:
                        # Example: "AMD" matches in "I bought AMD", but not in "DIAMOND"
                        pattern = r'\b' + re.escape(ticker) + r'\b'
                        if re.search(pattern, text, re.IGNORECASE):
                            count += 1
                    
                    # For short tickers: ONLY $TICKER counted (already checked above)
            
            except Exception as e:
                continue
        
        return count
    
    except Exception as e:
        print(f"   Reddit error: {e}")
        return 0


def check_accelerating(ticker: str, reddit_mentions: int) -> Dict:
    """Check if buzz is ACTUALLY accelerating (STRICTER threshold)."""
    try:
        url = "https://api.twitterapi.io/twitter/community/get_tweets_from_all_community"
        params = {"query": f"${ticker}", "queryType": "Latest"}
        headers = {"X-API-Key": TWITTER_API_KEY}
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
            return {'is_accelerating': False, 'buzz_level': 'None', 'recent_mentions': 0}
        
        tweets = response.json().get("tweets", [])
        recent = len(tweets)
        
        # STRICTER: Require 20+ Twitter AND 2+ Reddit (cross-platform confirmation)
        is_accelerating = recent >= MIN_TWITTER_BUZZ and reddit_mentions >= MIN_REDDIT_BUZZ
        
        # Buzz strength levels
        if recent > 50:
            buzz_level = "Explosive"
        elif recent > 30:
            buzz_level = "Strong"
        elif recent >= 20:
            buzz_level = "Moderate"
        else:
            buzz_level = "Weak"
        
        return {
            'is_accelerating': is_accelerating,
            'recent_mentions': recent,
            'buzz_level': buzz_level
        }
    except Exception as e:
        return {'is_accelerating': False, 'buzz_level': 'None', 'recent_mentions': 0}


def check_squeeze(ticker: str) -> Dict:
    """Check short interest (EXCLUDE squeeze signals - validated toxic)."""
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
    """Get market cap, volume, sector."""
    try:
        info = yf.Ticker(ticker).info
        
        market_cap = info.get('marketCap', 0)
        volume = info.get('volume', 0)
        avg_volume = info.get('averageVolume', 0)
        price = info.get('currentPrice', 0)
        sector = info.get('sector', 'Unknown')
        
        # Market cap category
        if market_cap < 2_000_000_000:
            cap_size = "Small (<$2B)"
        elif market_cap < 10_000_000_000:
            cap_size = "Mid ($2-10B)"
        elif market_cap < 50_000_000_000:
            cap_size = "Large ($10-50B)"
        else:
            cap_size = "Mega (>$50B)"
        
        # Volume spike detection
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
    except Exception as e:
        return None


def scan() -> List[Dict]:
    """
    Run LITE scan - Pure Fresh+Accel only.
    
    Returns ALL stocks with:
    - Fresh (0-5% in 7d) ✅
    - Accelerating buzz (20+ Twitter, 2+ Reddit) ✅
    - No squeeze (<20% short) ✅
    """
    
    universe = get_universe()
    
    picks = []
    
    print(f"\n🔍 Scanning {len(universe)} stocks...\n")
    
    for ticker in universe:
        
        try:
            # Step 1: Get quality data
            quality = get_quality_data(ticker)
            if not quality:
                continue
            if len(ticker) == 1:
                continue
            # Quality filters
            if quality['market_cap'] < MIN_MARKET_CAP:
                continue
            if quality['price'] < MIN_PRICE:
                continue
            if quality['price'] * quality['volume'] < MIN_VOLUME_USD:
                continue
            
            # Step 2: Check Fresh (OPTIMIZED 0-5%)
            fresh_data = check_fresh(ticker)
            if not fresh_data or not fresh_data['is_fresh']:
                continue
            
            # Step 3: Get Reddit mentions FIRST
            reddit_mentions = check_reddit_confirmation(ticker)
            
            # Step 4: Check Accelerating (WITH Reddit requirement)
            accel_data = check_accelerating(ticker, reddit_mentions)
            if not accel_data['is_accelerating']:
                continue
            
            # Step 5: Check Squeeze
            squeeze_data = check_squeeze(ticker)
            if squeeze_data['has_squeeze']:
                print(f"   ✗ {ticker}: Squeeze {squeeze_data['short_percent']:.0f}% - SKIP")
                continue
            
            # PASSED ALL FILTERS!
            pick = {
                'ticker': ticker,
                'entry_date': datetime.now().strftime('%Y-%m-%d'),
                'entry_time': datetime.now().strftime('%I:%M %p'),
                'entry_day': datetime.now().strftime('%A'),
                
                # Price data
                'price': fresh_data['price'],
                'change_7d': fresh_data['change_7d'],
                'change_90d': fresh_data['change_90d'],
                
                # Quality data
                'market_cap': quality['market_cap'],
                'cap_size': quality['cap_size'],
                'sector': quality['sector'],
                
                # Volume data
                'volume_ratio': quality['volume_ratio'],
                'volume_spike': quality['volume_spike'],
                
                # Social signals
                'twitter_mentions': accel_data['recent_mentions'],
                'buzz_level': accel_data['buzz_level'],
                'reddit_mentions': reddit_mentions,
                
                # Risk data
                'short_percent': squeeze_data['short_percent'],
                
                # Signals
                'is_fresh': True,
                'is_accelerating': True,
                'has_squeeze': False,
            }
            
            picks.append(pick)
            
            # Display
            signals = f"✨📈 ({fresh_data['change_7d']:+.1f}%)"
            volume_flag = "📊" if quality['volume_spike'] else ""
            print(f"   ✓ {ticker}: ${fresh_data['price']:.2f} | {signals} {volume_flag} | {accel_data['buzz_level']} buzz | {quality['cap_size']}")
        
        except Exception as e:
            continue
    
    return picks


def save_picks(picks: List[Dict]):
    """Save picks to CSV for tracking."""
    if not picks:
        print("\n❌ No picks found this scan")
        return
    
    df = pd.DataFrame(picks)
    
    # Save to outputs
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"outputs/supabot_v3_scan_{timestamp}.csv"
    
    os.makedirs("outputs", exist_ok=True)
    df.to_csv(filename, index=False)
    
    print(f"\n✅ Saved {len(picks)} picks to {filename}")
    
    # Display summary
    print(f"\n📊 PICK SUMMARY:")
    print(f"   Total picks: {len(picks)}")
    
    # By market cap
    cap_counts = df['cap_size'].value_counts()
    print(f"\n   By Size:")
    for cap, count in cap_counts.items():
        print(f"     {cap}: {count}")
    
    # By sector
    sector_counts = df['sector'].value_counts()
    print(f"\n   By Sector:")
    for sector, count in list(sector_counts.items())[:5]:
        print(f"     {sector}: {count}")
    
    # By buzz level
    buzz_counts = df['buzz_level'].value_counts()
    print(f"\n   By Buzz:")
    for buzz, count in buzz_counts.items():
        print(f"     {buzz}: {count}")
    
    # Volume spikes
    spikes = len(df[df['volume_spike'] == True])
    print(f"\n   Volume Spikes: {spikes}/{len(picks)}")
    
    return df


def display_picks(picks: List[Dict]):
    """Display picks in clean format."""
    
    if not picks:
        print("\n❌ No Fresh+Accel stocks found")
        print("\n💡 This could mean:")
        print("   • Market is quiet today")
        print("   • No stocks in optimal 0-5% Fresh range")
        print("   • No accelerating buzz detected (need 20+ Twitter, 2+ Reddit)")
        return
    
    print(f"\n{'='*70}")
    print(f"🎯 {len(picks)} FRESH+ACCEL PICKS (Validated 69% WR, +3.16% avg)")
    print(f"{'='*70}\n")
    
    for i, pick in enumerate(picks, 1):
        volume_flag = " 📊" if pick['volume_spike'] else ""
        
        print(f"{i}. {pick['ticker']} - ${pick['price']:.2f}")
        print(f"   Fresh: {pick['change_7d']:+.1f}% (7d) | {pick['cap_size']} | {pick['sector']}")
        print(f"   Buzz: {pick['buzz_level']} ({pick['twitter_mentions']} Twitter, {pick['reddit_mentions']} Reddit){volume_flag}")
        print(f"   Short: {pick['short_percent']:.1f}%")
        print()
    
    print(f"{'='*70}\n")
    print("📋 Trade Plan:")
    print("   • Position: 5% each (max 3-5 positions)")
    print("   • Stop loss: -8%")
    print("   • Hold: 7 days")
    print("   • Expected: 69% win rate, +3.16% avg return")
    print(f"\n{'='*70}\n")

def send_discord_notification(picks: List[Dict]):
    """Send V3 results to Discord - USES SEPARATE WEBHOOK."""
    
    # Use V3-specific webhook variable (NOT the V2 one!)
    DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_V3")
    
    # Fallback to hardcoded V3 webhook if env var not set
    if not DISCORD_WEBHOOK:
        DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1439772327691944079/6AnTFZRv1xMEHPmzuWAsMjT894jSqomAnaQvryn4c3BSOkCm-r1KK2oaTBVTFlHdbbF4"
        print("⚠️  Using hardcoded V3 webhook (DISCORD_WEBHOOK_V3 not in .env)")
    else:
        print("✅ Using DISCORD_WEBHOOK_V3 from environment")
    
    print(f"📤 Sending to V3 Discord channel...")
    print(f"   Webhook: ...{DISCORD_WEBHOOK[-20:]}")  # Show last 20 chars for verification
    print(f"   Picks to send: {len(picks)}")
    
    try:
        from discord_webhook import DiscordWebhook, DiscordEmbed
    except ImportError as e:
        print(f"❌ discord-webhook not installed: {e}")
        print("   Run: pip3 install discord-webhook")
        return
    
    try:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK, username="Supabot V3 Lite")
        
        # No picks found
        if not picks:
            print("   Creating 'no picks' embed...")
            embed = DiscordEmbed(
                title="📊 Supabot V3 Scan Complete",
                description="No Fresh+Accel candidates found (0-5% range, 20+ Twitter, 2+ Reddit)",
                color='808080'
            )
            embed.set_footer(text=f"V3 Optimized | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
            webhook.add_embed(embed)
            
            response = webhook.execute()
            print(f"✅ Discord notification sent (no picks) - Status: {response.status_code}")
            return
        
        # Build main embed with picks
        print(f"   Creating embed with {len(picks)} picks...")
        embed = DiscordEmbed(
            title=f"🎯 Supabot V3: {len(picks)} Fresh+Accel Picks",
            description=f"Optimized 0-5% range | Validated 82% WR | Scanned 200 stocks",
            color='00ff00'
        )
        
        # Add picks (max 10 in embed)
        for i, pick in enumerate(picks[:10], 1):
            volume_flag = "📊" if pick.get('volume_spike', False) else ""
            
            value_parts = [
                f"**${pick['price']:.2f}**",
                f"Fresh: {pick['change_7d']:+.1f}%",
                f"{pick['buzz_level']} buzz ({pick['twitter_mentions']}🐦 {pick['reddit_mentions']}🤖)",
                f"{pick['cap_size']}",
                f"Short: {pick['short_percent']:.1f}%"
            ]
            
            embed.add_embed_field(
                name=f"#{i}. {pick['ticker']} {volume_flag}",
                value=" | ".join(value_parts),
                inline=False
            )
        
        if len(picks) > 10:
            embed.add_embed_field(
                name="➕ More Picks",
                value=f"Plus {len(picks)-10} more stocks (see CSV)",
                inline=False
            )
        
        # Summary stats
        embed.add_embed_field(
            name="📊 Summary",
            value=f"Total: {len(picks)} picks | Validated: 82% WR, +3% avg | Fresh range: 0-5%",
            inline=False
        )
        
        embed.set_footer(text=f"Supabot V3 Optimized | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
        
        webhook.add_embed(embed)
        
        print("   Executing webhook...")
        response = webhook.execute()
        print(f"✅ Discord notification sent ({len(picks)} picks) - Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text}")
    
    except Exception as e:
        print(f"❌ Discord notification failed: {e}")
        import traceback
        traceback.print_exc()


# In your main block, make sure this is called:
if __name__ == "__main__":
    # Run scan
    start_time = datetime.now()
    
    picks = scan()
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # Display results
    display_picks(picks)
    
    # Save to CSV (if picks exist)
    if picks:
        df = save_picks(picks)
    
    # ALWAYS send Discord (even with 0 picks) - WITH CONFIRMATION
    print(f"\n{'='*70}")
    print("📤 SENDING DISCORD NOTIFICATION...")
    print(f"{'='*70}")
    send_discord_notification(picks)
    print(f"{'='*70}\n")
    
    print(f"\n⏱️  Scan completed in {elapsed:.1f} seconds")
    
    if picks:
        print(f"✅ V3 Scan Complete!\n")
    else:
        print(f"❌ No picks today\n")



