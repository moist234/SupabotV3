"""
Supabot V2 - Technical Analysis Module
RSI, moving averages, volume analysis, support/resistance, patterns.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import functools
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

from data.market_data import get_price_history
from config import MOCK_MODE, SCANNER_CONFIG

# ============ Technical Indicators ============

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index.
    
    Args:
        prices: Series of closing prices
        period: RSI period (default 14)
    
    Returns:
        Series of RSI values (0-100)
    """
    delta = prices.diff()
    
    gains = delta.clip(lower=0)
    losses = (-delta.clip(upper=0))
    
    avg_gains = gains.rolling(window=period, min_periods=period).mean()
    avg_losses = losses.rolling(window=period, min_periods=period).mean()
    
    rs = avg_gains / avg_losses.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.fillna(50)


def calculate_moving_averages(prices: pd.Series) -> Dict[str, float]:
    """
    Calculate key moving averages.
    
    Returns:
        {
            'sma_20': float,
            'sma_50': float,
            'sma_200': float,
            'ema_9': float,
            'ema_21': float
        }
    """
    return {
        'sma_20': float(prices.rolling(20).mean().iloc[-1]) if len(prices) >= 20 else 0.0,
        'sma_50': float(prices.rolling(50).mean().iloc[-1]) if len(prices) >= 50 else 0.0,
        'sma_200': float(prices.rolling(200).mean().iloc[-1]) if len(prices) >= 200 else 0.0,
        'ema_9': float(prices.ewm(span=9).mean().iloc[-1]) if len(prices) >= 9 else 0.0,
        'ema_21': float(prices.ewm(span=21).mean().iloc[-1]) if len(prices) >= 21 else 0.0,
    }


def calculate_macd(prices: pd.Series) -> Dict[str, float]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Returns:
        {
            'macd': float,
            'signal': float,
            'histogram': float
        }
    """
    if len(prices) < 26:
        return {'macd': 0.0, 'signal': 0.0, 'histogram': 0.0}
    
    ema_12 = prices.ewm(span=12).mean()
    ema_26 = prices.ewm(span=26).mean()
    
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9).mean()
    histogram = macd - signal
    
    return {
        'macd': float(macd.iloc[-1]),
        'signal': float(signal.iloc[-1]),
        'histogram': float(histogram.iloc[-1])
    }


def calculate_volume_analysis(hist: pd.DataFrame) -> Dict[str, float]:
    """
    Analyze volume patterns.
    
    Returns:
        {
            'volume_ratio': float,     # Today vs 20-day average
            'volume_trend': str,       # 'increasing' or 'decreasing'
            'avg_volume_20d': float,
            'volume_spike': bool       # True if >2x average
        }
    """
    if hist.empty or 'Volume' not in hist.columns or len(hist) < 20:
        return {
            'volume_ratio': 1.0,
            'volume_trend': 'neutral',
            'avg_volume_20d': 0.0,
            'volume_spike': False
        }
    
    vol = hist['Volume']
    current_vol = float(vol.iloc[-1])
    avg_20d = float(vol.tail(20).mean())
    
    ratio = current_vol / avg_20d if avg_20d > 0 else 1.0
    
    # Trend: compare recent 5 days to previous 15 days
    recent_avg = float(vol.tail(5).mean())
    prev_avg = float(vol.tail(20).head(15).mean())
    trend = 'increasing' if recent_avg > prev_avg * 1.2 else 'decreasing' if recent_avg < prev_avg * 0.8 else 'neutral'
    
    return {
        'volume_ratio': round(float(ratio), 2),
        'volume_trend': trend,
        'avg_volume_20d': round(float(avg_20d), 0),
        'volume_spike': bool(ratio > 2.0)
    }


def find_support_resistance(hist: pd.DataFrame, lookback: int = 60) -> Dict[str, List[float]]:
    """
    Find key support and resistance levels using pivot points.
    
    Returns:
        {
            'support_levels': [float, float, float],
            'resistance_levels': [float, float, float]
        }
    """
    if hist.empty or len(hist) < lookback:
        return {'support_levels': [], 'resistance_levels': []}
    
    recent = hist.tail(lookback)
    
    # Find local minima (support)
    lows = recent['Low']
    supports = []
    for i in range(2, len(lows) - 2):
        if lows.iloc[i] < lows.iloc[i-1] and lows.iloc[i] < lows.iloc[i-2] and \
           lows.iloc[i] < lows.iloc[i+1] and lows.iloc[i] < lows.iloc[i+2]:
            supports.append(float(lows.iloc[i]))
    
    # Find local maxima (resistance)
    highs = recent['High']
    resistances = []
    for i in range(2, len(highs) - 2):
        if highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i-2] and \
           highs.iloc[i] > highs.iloc[i+1] and highs.iloc[i] > highs.iloc[i+2]:
            resistances.append(float(highs.iloc[i]))
    
    # Return top 3 strongest levels
    supports.sort(reverse=True)
    resistances.sort()
    
    return {
        'support_levels': supports[:3] if supports else [],
        'resistance_levels': resistances[:3] if resistances else []
    }


def detect_chart_patterns(hist: pd.DataFrame) -> Dict[str, bool]:
    """
    Detect common chart patterns.
    
    Returns:
        {
            'bull_flag': bool,
            'ascending_triangle': bool,
            'breakout': bool,
            'consolidation': bool,
            'golden_cross': bool,
            'death_cross': bool
        }
    """
    if hist.empty or len(hist) < 50:
        return {
            'bull_flag': False,
            'ascending_triangle': False,
            'breakout': False,
            'consolidation': False,
            'golden_cross': False,
            'death_cross': False
        }
    
    close = hist['Close']
    high = hist['High']
    
    # Golden Cross / Death Cross (50 vs 200 MA)
    sma_50 = close.rolling(50).mean()
    sma_200 = close.rolling(200).mean() if len(close) >= 200 else None
    
    golden_cross = False
    death_cross = False
    if sma_200 is not None and len(sma_50) >= 200:
        # Check if 50 recently crossed 200
        if sma_50.iloc[-1] > sma_200.iloc[-1] and sma_50.iloc[-5] <= sma_200.iloc[-5]:
            golden_cross = True
        elif sma_50.iloc[-1] < sma_200.iloc[-1] and sma_50.iloc[-5] >= sma_200.iloc[-5]:
            death_cross = True
    
    # Breakout (price above recent high)
    recent_high = high.tail(20).iloc[:-1].max()
    breakout = bool(close.iloc[-1] > recent_high)
    
    # Consolidation (low volatility)
    volatility = close.pct_change().tail(20).std()
    consolidation = bool(volatility < 0.015)  # Less than 1.5% daily moves
    
    # Bull Flag (simplified detection)
    # Strong move up, then tight consolidation
    change_20d = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]
    recent_range = (high.tail(10).max() - high.tail(10).min()) / close.iloc[-1]
    bull_flag = bool(change_20d > 0.10 and recent_range < 0.05)
    
    # Ascending Triangle (higher lows, flat top)
    lows = hist['Low'].tail(20)
    highs_top = hist['High'].tail(20)
    
    low_trend = np.polyfit(range(len(lows)), lows, 1)[0]  # Slope
    high_var = highs_top.std() / highs_top.mean()
    
    ascending_triangle = bool(low_trend > 0 and high_var < 0.02)
    
    return {
        'bull_flag': bull_flag,
        'ascending_triangle': ascending_triangle,
        'breakout': breakout,
        'consolidation': consolidation,
        'golden_cross': golden_cross,
        'death_cross': death_cross
    }


# ============ Composite Technical Analysis ============

@functools.lru_cache(maxsize=500)
def get_technical_analysis(ticker: str) -> Dict:
    """
    Complete technical analysis for a ticker.
    
    Returns comprehensive dict with all indicators, patterns, and a technical score.
    """
    hist = get_price_history(ticker, period="6mo")
    
    if hist.empty or len(hist) < 50:
        return {
            'ticker': ticker,
            'rsi': 50.0,
            'macd': {},
            'moving_averages': {},
            'volume_analysis': {},
            'support_resistance': {},
            'patterns': {},
            'technical_score': 3.0,
            'technical_outlook': 'neutral',
            'reason': 'Insufficient data'
        }
    
    close = hist['Close']
    
    # Calculate all indicators
    rsi_series = calculate_rsi(close)
    current_rsi = float(rsi_series.iloc[-1])
    
    mas = calculate_moving_averages(close)
    macd = calculate_macd(close)
    volume = calculate_volume_analysis(hist)
    levels = find_support_resistance(hist)
    patterns = detect_chart_patterns(hist)
    
    # Score technical setup (1-5 scale)
    score = 3.0  # Start neutral
    reasons = []
    
    # RSI analysis (20% weight)
    if 40 < current_rsi < 60:
        score += 0.4
        reasons.append("Healthy RSI")
    elif current_rsi > 70:
        score -= 0.3
        reasons.append("Overbought")
    elif current_rsi < 30:
        score += 0.2  # Oversold can be bullish
        reasons.append("Oversold")
    
    # Moving average alignment (30% weight)
    current_price = float(close.iloc[-1])
    if mas['sma_20'] > 0 and mas['sma_50'] > 0:
        if current_price > mas['sma_20'] > mas['sma_50']:
            score += 0.6
            reasons.append("Price above MAs")
        elif current_price < mas['sma_20'] < mas['sma_50']:
            score -= 0.6
            reasons.append("Price below MAs")
    
    # Volume (20% weight)
    if volume['volume_spike']:
        score += 0.4
        reasons.append("Volume spike")
    elif volume['volume_trend'] == 'increasing':
        score += 0.2
        reasons.append("Rising volume")
    
    # Patterns (30% weight)
    if patterns['golden_cross']:
        score += 0.5
        reasons.append("Golden cross")
    if patterns['death_cross']:
        score -= 0.5
        reasons.append("Death cross")
    if patterns['breakout']:
        score += 0.3
        reasons.append("Breakout")
    if patterns['bull_flag']:
        score += 0.4
        reasons.append("Bull flag")
    if patterns['ascending_triangle']:
        score += 0.3
        reasons.append("Ascending triangle")
    
    # MACD confirmation
    if macd['histogram'] > 0 and macd['macd'] > macd['signal']:
        score += 0.2
        reasons.append("MACD bullish")
    elif macd['histogram'] < 0 and macd['macd'] < macd['signal']:
        score -= 0.2
        reasons.append("MACD bearish")
    
    # Cap score
    score = max(1.0, min(5.0, score))
    
    # Determine outlook
    if score >= 4.0:
        outlook = 'bullish'
    elif score <= 2.5:
        outlook = 'bearish'
    else:
        outlook = 'neutral'
    
    return {
        'ticker': ticker,
        'rsi': round(current_rsi, 2),
        'macd': macd,
        'moving_averages': mas,
        'volume_analysis': volume,
        'support_resistance': levels,
        'patterns': patterns,
        'technical_score': round(float(score), 2),
        'technical_outlook': outlook,
        'reason': "; ".join(reasons) if reasons else "Neutral setup"
    }


if __name__ == "__main__":
    # Test the module
    test_ticker = "AAPL"
    
    print(f"\n{'='*60}")
    print(f"Testing technical_analysis.py with {test_ticker}")
    print(f"{'='*60}\n")
    
    analysis = get_technical_analysis(test_ticker)
    
    print(f"RSI: {analysis['rsi']:.2f}")
    print(f"Technical Score: {analysis['technical_score']}/5.0")
    print(f"Outlook: {analysis['technical_outlook'].upper()}")
    print(f"Reason: {analysis['reason']}")
    
    print(f"\nMoving Averages:")
    mas = analysis['moving_averages']
    for ma, value in mas.items():
        if value > 0:
            print(f"  {ma.upper()}: ${value:.2f}")
    
    print(f"\nVolume Analysis:")
    vol = analysis['volume_analysis']
    print(f"  Ratio: {vol['volume_ratio']:.2f}x")
    print(f"  Trend: {vol['volume_trend']}")
    print(f"  Spike: {vol['volume_spike']}")
    
    print(f"\nPatterns Detected:")
    for pattern, detected in analysis['patterns'].items():
        if detected:
            print(f"  ✓ {pattern.replace('_', ' ').title()}")