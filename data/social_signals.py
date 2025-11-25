"""
Supabot V2 - Social Signals Module (Quality-First Edition with Sector Filter)
Smart social intelligence: buzz acceleration + quality filters + SECTOR VALIDATION
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

import yfinance as yf

# ============ Quality-Focused Subreddits ============
QUALITY_SUBREDDITS = [
    "wallstreetbets",
    "stocks",
    "investing",
    "options",
    "StockMarket",
    "SecurityAnalysis",
    "ValueInvesting",
]

SUBREDDIT_QUALITY_WEIGHTS = {
    "wallstreetbets": 1.0,
    "options": 0.9,
    "ValueInvesting": 0.9,
    "stocks": 0.8,
    "SecurityAnalysis": 0.8,
    "investing": 0.7,
    "StockMarket": 0.6,
}

CATALYST_KEYWORDS = [
    'earnings', 'beat', 'guidance', 'upgrade', 'revenue',
    'contract', 'partnership', 'acquisition', 'merger',
    'approval', 'fda', 'patent', 'expansion', 'growth',
    'institutional', 'analyst', 'price target'
]

HYPE_KEYWORDS = [
    'moon', 'rocket', 'yolo', 'diamond hands', 'ape',
    'squeeze', 'gamma', 'short ladder', 'hedgies'
]


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
        
        filters_dict = {
            'Market Cap.': '+Small (over $300mln)',
            'Average Volume': 'Over 500K',
            'Relative Volume': 'Over 1',
            'Price': 'Over $5',
            '20-Day Simple Moving Average': 'Price above SMA20',
        }
        
        fviz.set_filter(filters_dict=filters_dict)
        df = fviz.screener_view()
        
        if df is not None and not df.empty:
            tickers = df['Ticker'].tolist()
            print(f"   Finviz found {len(tickers)} quality stocks")
            
            # ============ SECTOR FILTER (VALIDATED) ============
            BANNED_SECTORS = [
                'Energy',              # 33% WR (1/3)
                'Consumer Cyclical',   # 33% WR (1/3)
                'Utilities',           # 50% WR (2/4)
            ]
            
            print(f"   Filtering out: {', '.join(BANNED_SECTORS)}...")
            
            filtered_tickers = []
            banned_count = 0
            
            for ticker in tickers:
                try:
                    stock = yf.Ticker(ticker)
                    sector = stock.info.get('sector', 'Unknown')
                    
                    if sector in BANNED_SECTORS:
                        banned_count += 1
                        continue
                    
                    filtered_tickers.append(ticker)
                    
                    if len(filtered_tickers) >= 200:
                        break
                except:
                    filtered_tickers.append(ticker)
                    if len(filtered_tickers) >= 200:
                        break
            
            print(f"   Excluded {banned_count} banned sectors, final: {len(filtered_tickers)}")
            return filtered_tickers[:200]
        else:
            print("   Finviz returned no results, using fallback")
    
    except ImportError:
        print("   ⚠️  finvizfinance not installed")
        print("   Using curated fallback list...")
    except Exception as e:
        print(f"   Finviz error: {e}")
        print("   Using fallback...")
    
    # Fallback
    return [
        "BIIB", "AMGN", "CPRX", "AXSM", "HALO", "JAZZ", "AZN",
        "PLTR", "NVDA", "NET", "DOCN", "FSLY", "ZETA", "AMKR",
        "SOFI", "COIN", "HOOD", "RBLX", "IMAX"
    ]


@functools.lru_cache(maxsize=500, typed=True)
def get_x_mentions(ticker: str, hours: int = 12) -> int:
    """Get X/Twitter mentions with caching."""
    if MOCK_MODE:
        base = (abs(hash(ticker)) % 40) + 3
        time_factor = 1.0 + 0.3 * ((int(time.time()) // 3600) % 3)
        return int(base * hours / 12 * time_factor)
    
    if not USE_X_SIGNAL or not TWITTER_API_KEY:
        return 0
    
    url = "https://api.twitterapi.io/twitter/community/get_tweets_from_all_community"
    params = {"query": f"${ticker}", "queryType": "Latest", "cursor": ""}
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
    """Calculate buzz acceleration."""
    recent = get_x_mentions(ticker, hours=6)
    total_24h = get_x_mentions(ticker, hours=24)
    baseline = total_24h - recent
    
    if baseline == 0:
        acceleration = 1.0 if recent > 5 else 0.0
    else:
        baseline_normalized = baseline / 3
        ratio = recent / max(baseline_normalized, 1)
        acceleration = min(ratio / 2.0, 1.0)
    
    is_accelerating = acceleration > 0.5 and recent > 10
    
    return {
        'recent_mentions': recent,
        'baseline_mentions': baseline,
        'acceleration': round(float(acceleration), 3),
        'is_accelerating': bool(is_accelerating)
    }


def get_reddit_quality_mentions(ticker: str, hours: int = 24) -> Dict:
    """Scan Reddit with quality filters."""
    if MOCK_MODE:
        total = (abs(hash(ticker)) % 15) + 2
        catalyst_ratio = 0.6
        
        return {
            'total_quality_mentions': total,
            'catalyst_mentions': int(total * catalyst_ratio),
            'hype_mentions': int(total * (1 - catalyst_ratio)),
            'weighted_score': round(total * 0.8, 2),
            'top_subreddit': 'stocks',
            'per_subreddit': {}
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
                    
                    text_upper = f"{post.title} {post.selftext}".upper()
                    if f"${ticker}" not in text_upper and f" {ticker} " not in text_upper:
                        continue
                    
                    if len(post.selftext) < 100:
                        continue
                    
                    if post.num_comments < 5:
                        continue
                    
                    text_lower = (post.title + " " + post.selftext).lower()
                    
                    has_catalyst = any(keyword in text_lower for keyword in CATALYST_KEYWORDS)
                    has_hype = any(keyword in text_lower for keyword in HYPE_KEYWORDS)
                    
                    if has_catalyst:
                        quality_mentions += 1
                        sub_catalyst += 1
                    elif not has_hype:
                        quality_mentions += 0.5
                    else:
                        sub_hype += 1
                
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
        
        top_sub = max(per_subreddit.items(), key=lambda x: x[1]['mentions'])[0] if per_subreddit else None
        
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


def get_social_intelligence(ticker: str) -> Dict:
    """
    Complete social intelligence analysis for a ticker.
    Combines X acceleration + Reddit quality mentions.
    """
    
    x_data = get_buzz_acceleration(ticker)
    reddit_data = get_reddit_quality_mentions(ticker, hours=24)
    
    x_score = x_data['acceleration']
    reddit_score = min(reddit_data['weighted_score'] / 20.0, 1.0)
    
    composite = (0.6 * x_score) + (0.4 * reddit_score)
    
    if reddit_data['catalyst_mentions'] > 2:
        composite = min(composite * 1.2, 1.0)
    
    if reddit_data['hype_mentions'] > reddit_data['catalyst_mentions'] * 2:
        composite *= 0.8
    
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


def scan_quality_universe(custom_tickers: List[str] = None) -> List[Dict]:
    """Scan quality universe for social signals."""
    
    tickers = custom_tickers if custom_tickers else get_quality_universe()
    
    results = []
    
    print(f"Scanning {len(tickers)} quality stocks for social signals...")
    
    for ticker in tickers:
        try:
            intel = get_social_intelligence(ticker)
            
            if intel['composite_score'] > 0.2:
                results.append(intel)
        
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            continue
    
    results.sort(key=lambda x: x['composite_score'], reverse=True)
    
    return results


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("Testing social_signals.py (Sector-Optimized Edition)")
    print(f"{'='*60}\n")
    
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
    
    print(f"\n{'='*60}")
    print("Scanning quality universe (top 10 shown)...")
    print(f"{'='*60}\n")
    
    test_universe = ["PLTR", "SOFI", "RBLX", "NET", "DDOG", "COIN", "HOOD", "NVDA", "BIIB", "AMGN"]
    results = scan_quality_universe(test_universe)
    
    print(f"Found {len(results)} stocks with social activity:\n")
    
    for i, stock in enumerate(results[:10], 1):
        print(f"{i}. {stock['ticker']}: {stock['composite_score']:.3f} - {stock['signal_strength'].upper()} - {stock['reason']}")