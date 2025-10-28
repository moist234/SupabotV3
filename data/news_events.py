"""
Supabot V2 - News & Events Module
Company news, press releases, and catalyst detection.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import functools
from typing import List, Dict
from datetime import datetime, timedelta
import requests

from config import MOCK_MODE

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")

# Catalyst keywords for detection
POSITIVE_KEYWORDS = [
    'beat', 'beats', 'exceed', 'upgrade', 'upgraded', 'raises', 'raised',
    'growth', 'expansion', 'partnership', 'acquisition', 'contract', 'deal',
    'approve', 'approved', 'breakthrough', 'strong', 'record'
]

NEGATIVE_KEYWORDS = [
    'miss', 'misses', 'downgrade', 'downgraded', 'cuts', 'cut',
    'weak', 'decline', 'layoff', 'lawsuit', 'investigation', 'warning',
    'delay', 'postpone', 'recall', 'violation'
]

NEUTRAL_KEYWORDS = [
    'announces', 'reports', 'files', 'schedules', 'updates'
]


@functools.lru_cache(maxsize=500)
def get_company_news(ticker: str, days: int = 7) -> List[Dict]:
    """
    Get recent company news using Finnhub.
    
    Args:
        ticker: Stock symbol
        days: Lookback period
    
    Returns:
        List of news articles with sentiment
    """
    
    if MOCK_MODE or not FINNHUB_API_KEY:
        # Mock news
        return [
            {
                'headline': f'{ticker} reports strong quarterly results',
                'summary': 'Company beats expectations',
                'source': 'Reuters',
                'url': 'https://example.com',
                'datetime': int(datetime.now().timestamp()),
                'sentiment': 'positive'
            },
            {
                'headline': f'{ticker} announces new partnership',
                'summary': 'Strategic deal signed',
                'source': 'Bloomberg',
                'url': 'https://example.com',
                'datetime': int((datetime.now() - timedelta(days=2)).timestamp()),
                'sentiment': 'positive'
            }
        ]
    
    try:
        import finnhub
        fc = finnhub.Client(api_key=FINNHUB_API_KEY)
        
        from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        
        news = fc.company_news(ticker, _from=from_date, to=to_date)
        
        results = []
        for article in news[:15]:  # Limit to 15 most recent
            headline = article.get('headline', '')
            
            results.append({
                'headline': headline,
                'summary': article.get('summary', ''),
                'source': article.get('source', ''),
                'url': article.get('url', ''),
                'datetime': article.get('datetime', 0),
                'sentiment': analyze_sentiment(headline)
            })
        
        return results
    
    except Exception as e:
        print(f"Finnhub news error for {ticker}: {e}")
        return []


def analyze_sentiment(text: str) -> str:
    """
    Analyze news sentiment (positive/neutral/negative).
    
    Args:
        text: News headline or summary
    
    Returns:
        'positive', 'neutral', or 'negative'
    """
    
    text_lower = text.lower()
    
    pos_count = sum(1 for word in POSITIVE_KEYWORDS if word in text_lower)
    neg_count = sum(1 for word in NEGATIVE_KEYWORDS if word in text_lower)
    
    if pos_count > neg_count and pos_count > 0:
        return 'positive'
    elif neg_count > pos_count and neg_count > 0:
        return 'negative'
    else:
        return 'neutral'


def detect_catalysts(news: List[Dict]) -> Dict:
    """
    Detect catalysts from news.
    
    Returns:
        {
            'has_catalysts': bool,
            'catalyst_count': int,
            'catalyst_types': list,
            'catalyst_score': float (0-1)
        }
    """
    
    catalysts = []
    
    for article in news:
        headline = article.get('headline', '').lower()
        sentiment = article.get('sentiment', 'neutral')
        
        # Earnings catalyst
        if any(word in headline for word in ['earnings', 'beat', 'exceed', 'revenue']):
            if sentiment == 'positive':
                catalysts.append('earnings_beat')
        
        # Guidance catalyst
        if any(word in headline for word in ['guidance', 'raises', 'outlook', 'forecast']):
            if sentiment == 'positive':
                catalysts.append('guidance_raise')
        
        # Business development
        if any(word in headline for word in ['partnership', 'deal', 'contract', 'acquisition']):
            catalysts.append('business_development')
        
        # Product/approval
        if any(word in headline for word in ['approve', 'launch', 'product', 'patent']):
            catalysts.append('product_milestone')
        
        # Analyst upgrade
        if any(word in headline for word in ['upgrade', 'price target', 'buy rating']):
            catalysts.append('analyst_upgrade')
    
    # Remove duplicates
    unique_catalysts = list(set(catalysts))
    
    # Calculate score
    catalyst_score = min(len(unique_catalysts) / 3.0, 1.0)  # Max at 3+ catalysts
    
    return {
        'has_catalysts': len(unique_catalysts) > 0,
        'catalyst_count': len(unique_catalysts),
        'catalyst_types': unique_catalysts,
        'catalyst_score': round(catalyst_score, 2)
    }


@functools.lru_cache(maxsize=500)
@functools.lru_cache(maxsize=500)
def get_earnings_date(ticker: str) -> Dict:
    """
    Get next earnings date from Yahoo Finance.
    
    Returns:
        {
            'earnings_date': str,
            'days_until_earnings': int,
            'is_before_earnings': bool,
            'is_earnings_week': bool
        }
    """
    
    if MOCK_MODE:
        future_date = datetime.now() + timedelta(days=15)
        return {
            'earnings_date': future_date.strftime('%Y-%m-%d'),
            'days_until_earnings': 15,
            'is_before_earnings': True,
            'is_earnings_week': False,
        }
    
    try:
        import yfinance as yf
        import pandas as pd
        
        stock = yf.Ticker(ticker)
        
        # Try to get earnings date from calendar
        try:
            calendar = stock.calendar
            
            if calendar is None:
                return {}
            
            # Calendar can be dict or DataFrame
            if isinstance(calendar, dict):
                earnings_date_raw = calendar.get('Earnings Date')
            elif isinstance(calendar, pd.DataFrame):
                if 'Earnings Date' in calendar.index:
                    earnings_date_raw = calendar.loc['Earnings Date']
                else:
                    return {}
            else:
                return {}
            
            # Handle different date formats
            if earnings_date_raw is None:
                return {}
            
            # Could be a list, Series, or single value
            if isinstance(earnings_date_raw, list):
                earnings_date = earnings_date_raw[0]
            elif isinstance(earnings_date_raw, pd.Series):
                earnings_date = earnings_date_raw.iloc[0]
            else:
                earnings_date = earnings_date_raw
            
            # Convert to datetime if needed
            if not isinstance(earnings_date, datetime):
                earnings_date = pd.to_datetime(earnings_date)
            
            days_until = (earnings_date - datetime.now()).days
            
            return {
                'earnings_date': earnings_date.strftime('%Y-%m-%d'),
                'days_until_earnings': int(days_until),
                'is_before_earnings': days_until < 14,
                'is_earnings_week': 0 < days_until < 7,
            }
        
        except Exception:
            # If calendar fails, try earnings_dates attribute
            if hasattr(stock, 'earnings_dates') and stock.earnings_dates is not None:
                next_date = stock.earnings_dates.index[0]
                days_until = (next_date - datetime.now()).days
                
                return {
                    'earnings_date': next_date.strftime('%Y-%m-%d'),
                    'days_until_earnings': int(days_until),
                    'is_before_earnings': days_until < 14,
                    'is_earnings_week': 0 < days_until < 7,
                }
        
        return {}
    
    except Exception as e:
        # Silently fail - earnings date is nice-to-have, not critical
        return {}


def get_catalyst_summary(ticker: str) -> Dict:
    """
    Comprehensive catalyst analysis.
    
    Combines: news sentiment, upcoming earnings, recent events.
    
    Returns:
        {
            'catalyst_score': float (0-1),
            'has_positive_catalysts': bool,
            'upcoming_earnings': dict,
            'recent_news_sentiment': str,
            'catalyst_summary': str
        }
    """
    
    # Get data
    news = get_company_news(ticker, days=7)
    catalysts = detect_catalysts(news)
    earnings = get_earnings_date(ticker)
    
    # Aggregate sentiment
    positive_news = [n for n in news if n['sentiment'] == 'positive']
    negative_news = [n for n in news if n['sentiment'] == 'negative']
    
    if len(positive_news) > len(negative_news):
        news_sentiment = 'positive'
    elif len(negative_news) > len(positive_news):
        news_sentiment = 'negative'
    else:
        news_sentiment = 'neutral'
    
    # Calculate overall catalyst score
    catalyst_score = catalysts.get('catalyst_score', 0)
    
    # Boost if earnings coming up with positive news
    if earnings.get('is_before_earnings', False) and news_sentiment == 'positive':
        catalyst_score = min(catalyst_score + 0.2, 1.0)
    
    # Build summary
    summary_parts = []
    if catalysts['has_catalysts']:
        summary_parts.append(f"{catalysts['catalyst_count']} catalysts")
    if news_sentiment == 'positive':
        summary_parts.append(f"{len(positive_news)} positive news")
    if earnings.get('is_earnings_week', False):
        summary_parts.append(f"Earnings in {earnings['days_until_earnings']} days")
    
    catalyst_summary = "; ".join(summary_parts) if summary_parts else "No significant catalysts"
    
    return {
        'catalyst_score': round(catalyst_score, 2),
        'has_positive_catalysts': catalyst_score > 0.3,
        'upcoming_earnings': earnings,
        'recent_news_sentiment': news_sentiment,
        'positive_news_count': len(positive_news),
        'negative_news_count': len(negative_news),
        'catalyst_types': catalysts.get('catalyst_types', []),
        'catalyst_summary': catalyst_summary
    }


if __name__ == "__main__":
    # Test
    import pandas as pd
    
    print("\nTesting News & Events Module...\n")
    
    test_ticker = "NVDA"
    
    news = get_company_news(test_ticker, days=7)
    print(f"Recent News for {test_ticker}:")
    for i, article in enumerate(news[:5], 1):
        print(f"  {i}. [{article['sentiment'].upper()}] {article['headline'][:80]}...")
    
    catalysts = get_catalyst_summary(test_ticker)
    print(f"\nCatalyst Analysis:")
    print(f"  Catalyst Score: {catalysts['catalyst_score']:.2f}/1.0")
    print(f"  News Sentiment: {catalysts['recent_news_sentiment'].upper()}")
    print(f"  Summary: {catalysts['catalyst_summary']}")
    
    if catalysts['upcoming_earnings']:
        print(f"  Next Earnings: {catalysts['upcoming_earnings'].get('earnings_date', 'Unknown')}")