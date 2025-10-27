"""
Supabot V2 - Market Data Layer
Clean interface for prices, fundamentals, and company info.
"""
import functools
from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

import os
import sys
# Add parent directory to Python path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from config import MOCK_MODE, SCANNER_CONFIG

# Silence yfinance warnings
import logging
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ============ Core Data Functions ============

@functools.lru_cache(maxsize=2000)
def get_stock_info(ticker: str) -> Dict:
    """
    Get comprehensive stock information.
    
    Returns dict with: price, market_cap, volume, pe_ratio, sector, etc.
    Returns empty dict on error.
    """
    if MOCK_MODE:
        # Mock data for testing
        return {
            'ticker': ticker,
            'price': 50.0 + (hash(ticker) % 50),
            'market_cap': 2_000_000_000,
            'volume': 5_000_000,
            'avg_volume': 4_000_000,
            'pe_ratio': 20.0,
            'forward_pe': 18.0,
            'peg_ratio': 1.5,
            'price_to_book': 3.0,
            'sector': 'Technology',
            'industry': 'Software',
            'float_shares': 80_000_000,
            'shares_outstanding': 100_000_000,
            'short_percent': 10.0,
            'short_ratio': 2.5,
            'revenue_growth': 15.0,
            'profit_margin': 12.0,
            'debt_to_equity': 30.0,
            'beta': 1.2,
        }
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        
        # Extract and clean data
        result = {
            'ticker': ticker,
            'price': float(info.get('currentPrice', 0) or info.get('regularMarketPrice', 0) or 0),
            'market_cap': float(info.get('marketCap', 0) or 0),
            'volume': float(info.get('volume', 0) or 0),
            'avg_volume': float(info.get('averageVolume', 0) or 0),
            'pe_ratio': float(info.get('trailingPE', 0) or 0),
            'forward_pe': float(info.get('forwardPE', 0) or 0),
            'peg_ratio': float(info.get('pegRatio', 0) or 0),
            'price_to_book': float(info.get('priceToBook', 0) or 0),
            'sector': str(info.get('sector', 'Unknown')),
            'industry': str(info.get('industry', 'Unknown')),
            'float_shares': float(info.get('floatShares', 0) or 0),
            'shares_outstanding': float(info.get('sharesOutstanding', 0) or 0),
            'short_percent': float(info.get('shortPercentOfFloat', 0) or 0) * 100,
            'short_ratio': float(info.get('shortRatio', 0) or 0),
            'revenue_growth': float(info.get('revenueGrowth', 0) or 0) * 100,
            'profit_margin': float(info.get('profitMargins', 0) or 0) * 100,
            'debt_to_equity': float(info.get('debtToEquity', 0) or 0),
            'beta': float(info.get('beta', 0) or 0),
            'fifty_two_week_high': float(info.get('fiftyTwoWeekHigh', 0) or 0),
            'fifty_two_week_low': float(info.get('fiftyTwoWeekLow', 0) or 0),
        }
        
        return result
    
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return {}


@functools.lru_cache(maxsize=1000)
def get_price_history(ticker: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    """
    Get historical price data.
    
    Args:
        ticker: Stock symbol
        period: '1mo', '3mo', '6mo', '1y', etc.
        interval: '1d', '1h', '5m', etc.
    
    Returns:
        DataFrame with OHLCV data
    """
    if MOCK_MODE:
        # Generate realistic mock data
        periods_map = {'1mo': 30, '3mo': 90, '6mo': 180, '1y': 365}
        days = periods_map.get(period, 90)
        
        dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq='D')
        base_price = 50.0
        
        # Random walk with slight uptrend
        returns = np.random.randn(days) * 0.02 + 0.001
        prices = base_price * (1 + returns).cumprod()
        
        return pd.DataFrame({
            'Open': prices * (1 + np.random.randn(days) * 0.005),
            'High': prices * (1 + np.abs(np.random.randn(days) * 0.01)),
            'Low': prices * (1 - np.abs(np.random.randn(days) * 0.01)),
            'Close': prices,
            'Volume': np.random.randint(1_000_000, 10_000_000, days)
        }, index=dates)
    
    try:
        hist = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
        return hist if isinstance(hist, pd.DataFrame) and not hist.empty else pd.DataFrame()
    except Exception as e:
        print(f"Error fetching history for {ticker}: {e}")
        return pd.DataFrame()


def get_price_changes(ticker: str) -> Dict[str, float]:
    """
    Calculate price changes over multiple timeframes.
    
    Returns:
        {
            'change_1d': float,   # 1-day % change
            'change_7d': float,   # 7-day % change  
            'change_30d': float,  # 30-day % change
            'change_90d': float,  # 90-day % change
            'is_fresh': bool,     # True if in "fresh" range
            'too_hot': bool       # True if already pumped
        }
    """
    try:
        hist = get_price_history(ticker, period="6mo")
        
        if hist.empty or len(hist) < 10:
            return {
                'change_1d': 0.0,
                'change_7d': 0.0,
                'change_30d': 0.0,
                'change_90d': 0.0,
                'is_fresh': False,
                'too_hot': False
            }
        
        close = hist['Close']
        
        # Calculate changes
        change_1d = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) > 1 else 0.0
        change_7d = ((close.iloc[-1] - close.iloc[-8]) / close.iloc[-8] * 100) if len(close) > 7 else 0.0
        change_30d = ((close.iloc[-1] - close.iloc[-31]) / close.iloc[-31] * 100) if len(close) > 30 else 0.0
        change_90d = ((close.iloc[-1] - close.iloc[-91]) / close.iloc[-91] * 100) if len(close) > 90 else 0.0
        
        # Fresh = getting buzz but hasn't moved yet
        is_fresh = (
            SCANNER_CONFIG.fresh_min <= change_7d <= SCANNER_CONFIG.fresh_max and
            change_90d > -40.0  # Not a falling knife
        )
        
        # Too hot = already pumped
        too_hot = (
            change_7d > SCANNER_CONFIG.max_7d_change or
            change_1d > SCANNER_CONFIG.max_1d_change
        )
        
        return {
            'change_1d': round(float(change_1d), 2),
            'change_7d': round(float(change_7d), 2),
            'change_30d': round(float(change_30d), 2),
            'change_90d': round(float(change_90d), 2),
            'is_fresh': bool(is_fresh),
            'too_hot': bool(too_hot)
        }
    
    except Exception as e:
        print(f"Error calculating price changes for {ticker}: {e}")
        return {
            'change_1d': 0.0,
            'change_7d': 0.0,
            'change_30d': 0.0,
            'change_90d': 0.0,
            'is_fresh': False,
            'too_hot': False
        }


def get_float_analysis(ticker: str) -> Dict:
    """
    Analyze float and volume rotation.
    
    Returns:
        {
            'float_millions': float,      # Float shares in millions
            'rotation_pct': float,        # % of float traded today
            'parabolic_setup': bool,      # True if low float + high rotation
            'float_to_outstanding': float # Float as % of shares outstanding
        }
    """
    info = get_stock_info(ticker)
    
    if not info:
        return {
            'float_millions': 0.0,
            'rotation_pct': 0.0,
            'parabolic_setup': False,
            'float_to_outstanding': 0.0
        }
    
    float_shares = info.get('float_shares', 0)
    shares_out = info.get('shares_outstanding', 0)
    volume = info.get('volume', 0)
    
    # Estimate float if missing
    if float_shares <= 0 and shares_out > 0:
        float_shares = shares_out * 0.70  # Assume 70% is float
    
    if float_shares <= 0:
        return {
            'float_millions': 0.0,
            'rotation_pct': 0.0,
            'parabolic_setup': False,
            'float_to_outstanding': 0.0
        }
    
    float_millions = float_shares / 1_000_000
    rotation_pct = (volume / float_shares * 100) if volume > 0 else 0.0
    
    # Parabolic = low float + high rotation
    parabolic_setup = (
        (float_shares < 20_000_000 and rotation_pct > 50.0) or
        (float_shares < 50_000_000 and rotation_pct > 100.0)
    )
    
    float_to_outstanding = (float_shares / shares_out * 100) if shares_out > 0 else 0.0
    
    return {
        'float_millions': round(float(float_millions), 1),
        'rotation_pct': round(float(rotation_pct), 1),
        'parabolic_setup': bool(parabolic_setup),
        'float_to_outstanding': round(float(float_to_outstanding), 1)
    }


def get_short_interest(ticker: str) -> Dict:
    """
    Get short interest data.
    
    Returns:
        {
            'short_percent': float,       # % of float shorted
            'short_ratio': float,         # Days to cover
            'squeeze_potential': bool     # True if >20% short
        }
    """
    info = get_stock_info(ticker)
    
    short_percent = info.get('short_percent', 0.0)
    short_ratio = info.get('short_ratio', 0.0)
    
    return {
        'short_percent': round(float(short_percent), 2),
        'short_ratio': round(float(short_ratio), 2),
        'squeeze_potential': bool(short_percent > 20.0)
    }


# ============ Fundamental Scoring ============

def get_fundamental_score(ticker: str) -> Tuple[float, str]:
    """
    Score company fundamentals on 1-5 scale.
    
    Based on: growth, profitability, valuation, debt.
    
    Returns:
        (score, explanation)
    """
    info = get_stock_info(ticker)
    
    if not info or info.get('price', 0) == 0:
        return 0.0, "No data available"
    
    score = 3.0  # Start neutral
    reasons = []
    
    # Revenue growth (25% of score)
    rev_growth = info.get('revenue_growth', 0)
    if rev_growth > 20:
        score += 0.5
        reasons.append(f"Strong growth ({rev_growth:.0f}%)")
    elif rev_growth > 10:
        score += 0.25
        reasons.append(f"Good growth ({rev_growth:.0f}%)")
    elif rev_growth < -10:
        score -= 0.5
        reasons.append(f"Declining revenue ({rev_growth:.0f}%)")
    
    # Profitability (25% of score)
    margin = info.get('profit_margin', 0)
    if margin > 15:
        score += 0.5
        reasons.append(f"High margin ({margin:.0f}%)")
    elif margin > 5:
        score += 0.25
        reasons.append(f"Profitable ({margin:.0f}%)")
    elif margin < 0:
        score -= 0.5
        reasons.append("Unprofitable")
    
    # Valuation (25% of score)
    pe = info.get('pe_ratio', 999)
    if 10 < pe < 25:
        score += 0.5
        reasons.append("Reasonable valuation")
    elif 5 < pe < 40:
        score += 0.25
        reasons.append("Fair valuation")
    elif pe > 100:
        score -= 0.5
        reasons.append(f"High P/E ({pe:.0f})")
    
    # Debt level (25% of score)
    debt = info.get('debt_to_equity', 999)
    if debt < 30:
        score += 0.5
        reasons.append("Low debt")
    elif debt < 70:
        score += 0.25
        reasons.append("Manageable debt")
    elif debt > 200:
        score -= 0.5
        reasons.append("High debt")
    
    score = max(1.0, min(5.0, score))
    explanation = "; ".join(reasons) if reasons else "Neutral fundamentals"
    
    return round(float(score), 2), explanation


# ============ Validation ============

def is_valid_ticker(ticker: str) -> bool:
    """
    Check if ticker exists and has valid data.
    
    Returns:
        True if ticker is tradeable, False otherwise
    """
    if MOCK_MODE:
        return True
    
    info = get_stock_info(ticker)
    return bool(info and info.get('price', 0) > 0 and info.get('market_cap', 0) > 0)


def passes_basic_filters(ticker: str) -> Tuple[bool, str]:
    """
    Check if stock passes basic quality filters.
    
    Returns:
        (passes, reason_if_failed)
    """
    info = get_stock_info(ticker)
    
    if not info:
        return False, "No data"
    
    price = info.get('price', 0)
    mcap = info.get('market_cap', 0)
    volume_usd = price * info.get('volume', 0)
    sector = info.get('sector', '')
    
    # Price filter
    if price < SCANNER_CONFIG.min_price:
        return False, f"Price ${price:.2f} below minimum"
    
    if price > SCANNER_CONFIG.max_price:
        return False, f"Price ${price:.2f} above maximum"
    
    # Market cap filter
    if mcap < SCANNER_CONFIG.min_market_cap:
        return False, f"Market cap ${mcap/1e6:.0f}M too small"
    
    if mcap > SCANNER_CONFIG.max_market_cap:
        return False, f"Market cap ${mcap/1e9:.1f}B too large"
    
    # Liquidity filter
    if volume_usd < SCANNER_CONFIG.min_daily_volume_usd:
        return False, f"Volume ${volume_usd/1e6:.1f}M too low"
    
    # Sector filter
    from config import BANNED_SECTORS
    if sector in BANNED_SECTORS:
        return False, f"Banned sector: {sector}"
    
    # Price action filter
    changes = get_price_changes(ticker)
    
    if changes['change_90d'] < SCANNER_CONFIG.min_90d_change:
        return False, f"Falling knife: {changes['change_90d']:.0f}% (90d)"
    
    if changes['too_hot']:
        return False, f"Already pumped: {changes['change_7d']:.0f}% (7d)"
    
    return True, "Pass"


# ============ Batch Operations ============

def get_batch_info(tickers: list) -> pd.DataFrame:
    """
    Get info for multiple tickers efficiently.
    
    Returns DataFrame with all stock info.
    """
    results = []
    
    for ticker in tickers:
        info = get_stock_info(ticker)
        if info:
            results.append(info)
    
    return pd.DataFrame(results) if results else pd.DataFrame()


if __name__ == "__main__":
    # Test the module
    test_ticker = "AAPL"
    
    print(f"\n{'='*60}")
    print(f"Testing market_data.py with {test_ticker}")
    print(f"{'='*60}\n")
    
    info = get_stock_info(test_ticker)
    print(f"Stock Info: {info.get('sector')} - ${info.get('price'):.2f}")
    
    changes = get_price_changes(test_ticker)
    print(f"Price Changes: 7d={changes['change_7d']:+.1f}%, 90d={changes['change_90d']:+.1f}%")
    print(f"Is Fresh: {changes['is_fresh']}, Too Hot: {changes['too_hot']}")
    
    fund_score, explanation = get_fundamental_score(test_ticker)
    print(f"Fundamental Score: {fund_score}/5.0 ({explanation})")
    
    passes, reason = passes_basic_filters(test_ticker)
    print(f"Passes Filters: {passes} ({reason})")