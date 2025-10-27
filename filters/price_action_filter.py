"""
Supabot V2 - Price Action Filter
Momentum and trend filters to avoid chasing pumps and catching falling knives.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Tuple
from config import SCANNER_CONFIG

def passes_momentum_filter(change_7d: float, change_1d: float) -> Tuple[bool, str]:
    """
    Check if stock hasn't already pumped too much.
    
    Args:
        change_7d: 7-day price change percentage
        change_1d: 1-day price change percentage
    
    Returns:
        (passes, reason_if_failed)
    """
    # Already pumped too much (chasing risk)
    if change_7d > SCANNER_CONFIG.max_7d_change:
        return False, f"Already up {change_7d:.1f}% in 7 days (chasing risk)"
    
    if change_1d > SCANNER_CONFIG.max_1d_change:
        return False, f"Already up {change_1d:.1f}% today (too hot)"
    
    return True, "Pass"


def passes_trend_filter(change_90d: float) -> Tuple[bool, str]:
    """
    Check if stock is in an uptrend (not a falling knife).
    
    Args:
        change_90d: 90-day price change percentage
    
    Returns:
        (passes, reason_if_failed)
    """
    if change_90d < SCANNER_CONFIG.min_90d_change:
        return False, f"Falling knife: down {change_90d:.1f}% over 90 days"
    
    return True, "Pass"


def is_fresh_signal(change_7d: float, change_90d: float) -> bool:
    """
    Determine if this is a "fresh" signal (BEST entry timing).
    
    Fresh = getting buzz but price hasn't moved much yet.
    
    Args:
        change_7d: 7-day price change percentage
        change_90d: 90-day price change percentage
    
    Returns:
        True if fresh signal (ideal entry)
    """
    return (
        SCANNER_CONFIG.fresh_min <= change_7d <= SCANNER_CONFIG.fresh_max and
        change_90d > -40.0  # Not in a major downtrend
    )


def passes_technical_thresholds(rsi: float, volume_ratio: float) -> Tuple[bool, str]:
    """
    Check if technical indicators are in acceptable ranges.
    
    Args:
        rsi: Relative Strength Index (0-100)
        volume_ratio: Today's volume vs average
    
    Returns:
        (passes, reason_if_failed)
    """
    # RSI check
    if rsi < SCANNER_CONFIG.min_rsi:
        return False, f"RSI {rsi:.0f} too low (oversold concern)"
    
    if rsi > SCANNER_CONFIG.max_rsi:
        return False, f"RSI {rsi:.0f} too high (overbought)"
    
    # Volume check
    if volume_ratio < SCANNER_CONFIG.min_volume_ratio:
        return False, f"Volume {volume_ratio:.2f}x too low (no interest)"
    
    return True, "Pass"


def passes_all_price_action_filters(price_data: dict, technical_data: dict) -> Tuple[bool, str]:
    """
    Run all price action filters.
    
    Args:
        price_data: Dict with change_7d, change_1d, change_90d
        technical_data: Dict with rsi, volume_ratio
    
    Returns:
        (passes, reason_if_failed)
    """
    # Momentum filter (not already pumped)
    change_7d = price_data.get('change_7d', 0)
    change_1d = price_data.get('change_1d', 0)
    
    passes, reason = passes_momentum_filter(change_7d, change_1d)
    if not passes:
        return False, reason
    
    # Trend filter (not falling knife)
    change_90d = price_data.get('change_90d', 0)
    
    passes, reason = passes_trend_filter(change_90d)
    if not passes:
        return False, reason
    
    # Technical thresholds
    rsi = technical_data.get('rsi', 50)
    volume_ratio = technical_data.get('volume_analysis', {}).get('volume_ratio', 1.0)
    
    passes, reason = passes_technical_thresholds(rsi, volume_ratio)
    if not passes:
        return False, reason
    
    # Check if fresh signal (bonus info, not a filter)
    is_fresh = is_fresh_signal(change_7d, change_90d)
    
    return True, f"Pass all filters (Fresh: {is_fresh})"


if __name__ == "__main__":
    # Test the filters
    print("\n" + "="*60)
    print("Testing Price Action Filters")
    print("="*60 + "\n")
    
    # Test case 1: Fresh signal (ideal)
    fresh_price = {
        'change_7d': 5.0,   # Up slightly
        'change_1d': 2.0,
        'change_90d': 20.0  # In uptrend
    }
    
    fresh_tech = {
        'rsi': 55.0,
        'volume_analysis': {'volume_ratio': 1.5}
    }
    
    passes, reason = passes_all_price_action_filters(fresh_price, fresh_tech)
    print(f"Fresh Signal: {passes} - {reason}")
    is_fresh = is_fresh_signal(fresh_price['change_7d'], fresh_price['change_90d'])
    print(f"  → Is Fresh: {is_fresh}\n")
    
    # Test case 2: Already pumped (avoid)
    pumped_price = {
        'change_7d': 35.0,  # Too hot!
        'change_1d': 8.0,
        'change_90d': 50.0
    }
    
    pumped_tech = {
        'rsi': 75.0,
        'volume_analysis': {'volume_ratio': 2.0}
    }
    
    passes, reason = passes_all_price_action_filters(pumped_price, pumped_tech)
    print(f"Pumped Stock: {passes} - {reason}\n")
    
    # Test case 3: Falling knife (avoid)
    falling_price = {
        'change_7d': -5.0,
        'change_1d': -2.0,
        'change_90d': -25.0  # Major downtrend
    }
    
    falling_tech = {
        'rsi': 35.0,
        'volume_analysis': {'volume_ratio': 1.2}
    }
    
    passes, reason = passes_all_price_action_filters(falling_price, falling_tech)
    print(f"Falling Knife: {passes} - {reason}\n")
    
    # Test case 4: Overbought (avoid)
    overbought_price = {
        'change_7d': 15.0,
        'change_1d': 5.0,
        'change_90d': 30.0
    }
    
    overbought_tech = {
        'rsi': 78.0,  # Too high
        'volume_analysis': {'volume_ratio': 1.5}
    }
    
    passes, reason = passes_all_price_action_filters(overbought_price, overbought_tech)
    print(f"Overbought: {passes} - {reason}")
    
    print("\n" + "="*60)