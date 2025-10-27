"""
Supabot V2 - Social Signals Module (Quality-First Edition)
Smart social intelligence: buzz acceleration + quality filters.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import functools
import time
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import requests

from config import (
    MOCK_MODE,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET, 
    REDDIT_USER_AGENT,
    TWITTER_API_KEY,
    USE_X_SIGNAL,
    SCANNER_CONFIG
)

# ============ Quality-Focused Subreddits ============
# Removed penny stock subreddits, focus on serious investors

QUALITY_SUBREDDITS = [
    "wallstreetbets",    # Still useful for momentum (1.0 weight)
    "stocks",            # More serious discussion (0.8 weight)
    "investing",         # Long-term focus (0.7 weight)
    "options",           # Smart money derivatives (0.9 weight)
    "StockMarket",       # General market (0.6 weight)
    "SecurityAnalysis",  # Fundamentals (0.8 weight)
    "ValueInvesting",    # NEW: Value-focused analysis (0.9 weight)
]

SUBREDDIT_QUALITY_WEIGHTS = {
    "wallstreetbets": 1.0,
    "options": 0.9,
    "ValueInvesting": 0.9,     # NEW: High quality weight
    "stocks": 0.8,
    "SecurityAnalysis": 0.8,
    "investing": 0.7,
    "StockMarket": 0.6,
}

# Catalyst keywords (real reasons to buy, not just hype)
CATALYST_KEYWORDS = [
    'earnings', 'beat', 'guidance', 'upgrade', 'revenue',
    'contract', 'partnership', 'acquisition', 'merger',
    'approval', 'fda', 'patent', 'expansion', 'growth',
    'institutional', 'analyst', 'price target'
]

# Hype keywords (filter these out or downweight)
HYPE_KEYWORDS = [
    'moon', 'rocket', 'yolo', 'diamond hands', 'ape',
    'squeeze', 'gamma', 'short ladder', 'hedgies'
]


# ============ Curated Quality Universe ============

def get_quality_universe() -> List[str]:
    """
    Get quality universe using Finviz screener.
    Scans for stocks with: volume spike, uptrend, quality market cap.
    """
    
    try:
        from finvizfinance.screener.overview import Overview
        
        print("   Using Finviz screener...")
        
        fviz = Overview()
        
        # Set quality filters
        filters_dict = {
            'Market Cap.': '+Small (over $300mln)',     # $300M+ only
            'Average Volume': 'Over 500K',              # Liquid stocks
            'Relative Volume': 'Over 1',              # Some activity
            'Price': 'Over $5',                         # No penny stocks
            '20-Day Simple Moving Average': 'Price above SMA20',  # Uptrend
        }
        
        fviz.set_filter(filters_dict=filters_dict)
        df = fviz.screener_view()
        
        if df is not None and not df.empty:
            tickers = df['Ticker'].tolist()
            print(f"   Finviz found {len(tickers)} quality stocks")
            return tickers[:200]  # Limit to 200
        else:
            print("   Finviz returned no results, using fallback")
    
    except ImportError:
        print("   ⚠️  finvizfinance not installed. Run: pip3 install finvizfinance")
        print("   Using curated fallback list...")
    
    except Exception as e:
        print(f"   Finviz screener error: {e}")
        print("   Using curated fallback list...")
    
    # Fallback: curated list of quality stocks
    return [
        # Fintech & Payments
        "SOFI", "AFRM", "UPST", "COIN", "HOOD", "SQ",
        
        # Cloud & SaaS
        "NET", "DDOG", "SNOW", "MDB", "CRWD", "ZS",
        "ESTC", "DOCN", "FSLY",
        
        # AI & Data
        "PLTR", "AI", "BBAI", "SOUN",
        
        # Quantum & Advanced Tech
        "IONQ", "RGTI", "QUBT",
        
        # Gaming & Entertainment
        "RBLX", "DKNG", "U", "PINS",
        
        # E-commerce & Digital
        "SHOP", "ETSY", "W", "CHWY",
        
        # Cybersecurity
        "S", "TENB", "PANW",
        
        # Enterprise Software
        "DOMO", "BILL", "HUBS", "ZM", "DOCU",
        
        # Electric Vehicles & Clean Tech
        "RIVN", "LCID", "CHPT", "BLNK", "QS",
        
        # Biotech (selective)
        "BEAM", "CRSP", "EDIT", "NTLA",
    ]

# ============ X/Twitter with Acceleration ============

@functools.lru_cache(maxsize=500, typed=True)
def get_x_mentions(ticker: str, hours: int = 12) -> int:
    """
    Get X/Twitter mentions with caching.
    
    Args:
        ticker: Stock symbol (without $)
        hours: Lookback period
    
    Returns:
        Number of mentions
    """
    if MOCK_MODE:
        # Simulate realistic buzz patterns
        base = (abs(hash(ticker)) % 40) + 3
        # Add some time-based variation
        time_factor = 1.0 + 0.3 * ((int(time.time()) // 3600) % 3)
        return int(base * hours / 12 * time_factor)
    
    if not USE_X_SIGNAL or not TWITTER_API_KEY:
        return 0
    
    url = "https://api.twitterapi.io/twitter/community/get_tweets_from_all_community"
    params = {
        "query": f"${ticker}",
        "queryType": "Latest",
        "cursor": ""
    }
    headers = {"X-API-Key": TWITTER_API_KEY}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return 0
        
        data = response.json() or {}
        tweets = data.get("tweets", [])
        
        return len(tweets)
    
    except Exception as e:
        print(f"X API error for {ticker}: {e}")
        return 0


def get_buzz_acceleration(ticker: str) -> Dict[str, float]:
    """
    Calculate buzz acceleration (CRITICAL - finds stocks BEFORE pumps).
    
    Compares recent buzz to baseline. High acceleration = fresh interest.
    
    Returns:
        {
            'recent_mentions': int,
            'baseline_mentions': int,
            'acceleration': float (0-1),
            'is_accelerating': bool
        }
    """
    
    # Recent: last 6 hours
    recent = get_x_mentions(ticker, hours=6)
    
    # Baseline: previous 18 hours (for 24hr total)
    total_24h = get_x_mentions(ticker, hours=24)
    baseline = total_24h - recent
    
    # Calculate acceleration
    if baseline == 0:
        # New buzz from nothing = highest signal
        acceleration = 1.0 if recent > 5 else 0.0
    else:
        # Normalize: 2x increase in 6hrs = high acceleration
        baseline_normalized = baseline / 3  # Adjust for time period
        ratio = recent / max(baseline_normalized, 1)
        acceleration = min(ratio / 2.0, 1.0)
    
    is_accelerating = acceleration > 0.5 and recent > 10
    
    return {
        'recent_mentions': recent,
        'baseline_mentions': baseline,
        'acceleration': round(float(acceleration), 3),
        'is_accelerating': bool(is_accelerating)
    }


# ============ Reddit with Quality Filters ============

def get_reddit_quality_mentions(ticker: str, hours: int = 24) -> Dict:
    """
    Scan Reddit with quality filters.
    
    Only counts posts with:
    - Meaningful content (>100 chars)
    - Real engagement (>5 comments)
    - Catalyst discussion (earnings, guidance, etc.)
    
    Returns:
        {
            'total_quality_mentions': int,
            'catalyst_mentions': int,
            'hype_mentions': int,
            'weighted_score': float,
            'top_subreddit': str,
            'per_subreddit': dict
        }
    """
    
    if MOCK_MODE:
        # Simulate quality mentions
        total = (abs(hash(ticker)) % 15) + 2
        catalyst_ratio = 0.6
        
        return {
            'total_quality_mentions': total,
            'catalyst_mentions': int(total * catalyst_ratio),
            'hype_mentions': int(total * (1 - catalyst_ratio)),
            'weighted_score': round(total * 0.8, 2),
            'top_subreddit': 'stocks',
            'per_subreddit': {sub: {'mentions': total // len(QUALITY_SUBREDDITS), 'quality_score': 0.7} 
                             for sub in QUALITY_SUBREDDITS}
        }
    
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return {
            'total_quality_mentions': 0,
            'catalyst_mentions': 0,
            'hype_mentions': 0,
            'weighted_score': 0.0,
            'top_subreddit': None,
            'per_subreddit': {}
        }
    
    try:
        import praw
        
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            ratelimit_seconds=5
        )
        reddit.read_only = True
        
        since = datetime.utcnow() - timedelta(hours=hours)
        
        total_quality = 0
        catalyst_count = 0
        hype_count = 0
        per_subreddit = {}
        
        for sub_name in QUALITY_SUBREDDITS:
            try:
                subreddit = reddit.subreddit(sub_name)
                quality_mentions = 0
                sub_catalyst = 0
                sub_hype = 0
                
                for post in subreddit.new(limit=100):
                    post_time = datetime.utcfromtimestamp(post.created_utc)
                    
                    if post_time < since:
                        break
                    
                    # Check if ticker mentioned
                    text_upper = f"{post.title} {post.selftext}".upper()
                    if f"${ticker}" not in text_upper and f" {ticker} " not in text_upper:
                        continue
                    
                    # Quality filters
                    if len(post.selftext) < 100:  # Too short
                        continue
                    
                    if post.num_comments < 5:  # Low engagement
                        continue
                    
                    # Analyze content quality
                    text_lower = (post.title + " " + post.selftext).lower()
                    
                    has_catalyst = any(keyword in text_lower for keyword in CATALYST_KEYWORDS)
                    has_hype = any(keyword in text_lower for keyword in HYPE_KEYWORDS)
                    
                    if has_catalyst:
                        quality_mentions += 1
                        sub_catalyst += 1
                    elif not has_hype:
                        # Neutral mention (no catalyst, no hype)
                        quality_mentions += 0.5
                    else:
                        # Pure hype
                        sub_hype += 1
                
                # Weight by subreddit quality
                weight = SUBREDDIT_QUALITY_WEIGHTS.get(sub_name, 0.5)
                weighted_mentions = quality_mentions * weight
                
                total_quality += quality_mentions
                catalyst_count += sub_catalyst
                hype_count += sub_hype
                
                per_subreddit[sub_name] = {
                    'mentions': int(quality_mentions),
                    'catalyst_mentions': sub_catalyst,
                    'quality_score': weight
                }
            
            except Exception as e:
                print(f"Error scanning r/{sub_name}: {e}")
                continue
        
        # Find top subreddit
        top_sub = max(per_subreddit.items(), key=lambda x: x[1]['mentions'])[0] if per_subreddit else None
        
        # Calculate weighted score
        weighted_score = sum(
            data['mentions'] * data['quality_score']
            for data in per_subreddit.values()
        )
        
        return {
            'total_quality_mentions': int(total_quality),
            'catalyst_mentions': catalyst_count,
            'hype_mentions': hype_count,
            'weighted_score': round(float(weighted_score), 2),
            'top_subreddit': top_sub,
            'per_subreddit': per_subreddit
        }
    
    except Exception as e:
        print(f"Reddit API error: {e}")
        return {
            'total_quality_mentions': 0,
            'catalyst_mentions': 0,
            'hype_mentions': 0,
            'weighted_score': 0.0,
            'top_subreddit': None,
            'per_subreddit': {}
        }


# ============ Composite Social Score ============

def get_social_intelligence(ticker: str) -> Dict:
    """
    Complete social intelligence analysis for a ticker.
    
    Combines X acceleration + Reddit quality mentions.
    
    Returns:
        {
            'ticker': str,
            'x_acceleration': float,
            'is_accelerating': bool,
            'reddit_quality_score': float,
            'has_catalysts': bool,
            'composite_score': float (0-1),
            'signal_strength': str ('strong', 'medium', 'weak'),
            'reason': str
        }
    """
    
    # Get X buzz acceleration
    x_data = get_buzz_acceleration(ticker)
    
    # Get Reddit quality mentions
    reddit_data = get_reddit_quality_mentions(ticker, hours=24)
    
    # Calculate composite score (0-1 scale)
    # 60% weight to X acceleration (leading indicator)
    # 40% weight to Reddit quality (confirmation)
    
    x_score = x_data['acceleration']
    reddit_score = min(reddit_data['weighted_score'] / 20.0, 1.0)  # Normalize
    
    composite = (0.6 * x_score) + (0.4 * reddit_score)
    
    # Boost if catalysts present
    if reddit_data['catalyst_mentions'] > 2:
        composite = min(composite * 1.2, 1.0)
    
    # Penalize if too much hype
    if reddit_data['hype_mentions'] > reddit_data['catalyst_mentions'] * 2:
        composite *= 0.8
    
    # Determine signal strength
    if composite >= 0.7 and x_data['is_accelerating']:
        strength = 'strong'
        reason = f"Accelerating buzz ({x_data['recent_mentions']} recent X posts)"
    elif composite >= 0.5:
        strength = 'medium'
        reason = f"Growing interest ({reddit_data['total_quality_mentions']} quality Reddit posts)"
    else:
        strength = 'weak'
        reason = "Low social activity"
    
    if reddit_data['catalyst_mentions'] > 0:
        reason += f" + {reddit_data['catalyst_mentions']} catalyst mentions"
    
    return {
        'ticker': ticker,
        'x_acceleration': x_data['acceleration'],
        'x_recent_mentions': x_data['recent_mentions'],
        'is_accelerating': x_data['is_accelerating'],
        'reddit_quality_score': reddit_data['weighted_score'],
        'reddit_total_mentions': reddit_data['total_quality_mentions'],
        'has_catalysts': reddit_data['catalyst_mentions'] > 0,
        'catalyst_count': reddit_data['catalyst_mentions'],
        'composite_score': round(float(composite), 3),
        'signal_strength': strength,
        'reason': reason,
        'raw_data': {
            'x': x_data,
            'reddit': reddit_data
        }
    }


# ============ Batch Quality Screening ============

def scan_quality_universe(custom_tickers: List[str] = None) -> List[Dict]:
    """
    Scan quality universe for social signals.
    
    Args:
        custom_tickers: Optional list of tickers to scan (overrides default)
    
    Returns:
        List of dicts sorted by composite_score (highest first)
    """
    
    tickers = custom_tickers if custom_tickers else get_quality_universe()
    
    results = []
    
    print(f"Scanning {len(tickers)} quality stocks for social signals...")
    
    for ticker in tickers:
        try:
            intel = get_social_intelligence(ticker)
            
            # Only include if there's meaningful activity
            if intel['composite_score'] > 0.2:
                results.append(intel)
        
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            continue
    
    # Sort by composite score (best first)
    results.sort(key=lambda x: x['composite_score'], reverse=True)
    
    return results


if __name__ == "__main__":
    # Test the module
    print(f"\n{'='*60}")
    print("Testing social_signals.py (Quality-First Edition)")
    print(f"{'='*60}\n")
    
    # Test single ticker
    test_ticker = "PLTR"
    print(f"Analyzing {test_ticker}...")
    
    intel = get_social_intelligence(test_ticker)
    
    print(f"\nResults for {test_ticker}:")
    print(f"  Composite Score: {intel['composite_score']:.3f}")
    print(f"  Signal Strength: {intel['signal_strength'].upper()}")
    print(f"  X Acceleration: {intel['x_acceleration']:.3f} ({'ACCELERATING' if intel['is_accelerating'] else 'stable'})")
    print(f"  Reddit Quality Score: {intel['reddit_quality_score']:.2f}")
    print(f"  Catalysts: {'YES' if intel['has_catalysts'] else 'NO'}")
    print(f"  Reason: {intel['reason']}")
    
    # Test batch scan (top 5 for demo)
    print(f"\n{'='*60}")
    print("Scanning quality universe (top 10 shown)...")
    print(f"{'='*60}\n")
    
    test_universe = ["PLTR", "SOFI", "RBLX", "NET", "DDOG", "COIN", "HOOD", "IONQ", "SNOW", "CRWD"]
    results = scan_quality_universe(test_universe)
    
    print(f"Found {len(results)} stocks with social activity:\n")
    
    for i, stock in enumerate(results[:10], 1):
        print(f"{i}. {stock['ticker']}: {stock['composite_score']:.3f} - {stock['signal_strength'].upper()} - {stock['reason']}")