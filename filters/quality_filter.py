"""
Supabot V2 - Quality Filter
Fundamental quality gates to filter out low-quality stocks.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Tuple
from config import SCANNER_CONFIG, BANNED_SECTORS

def passes_market_cap_filter(market_cap: float) -> Tuple[bool, str]:
    """
    Check if market cap is within acceptable range.
    
    Args:
        market_cap: Market capitalization in dollars
    
    Returns:
        (passes, reason_if_failed)
    """
    if market_cap < SCANNER_CONFIG.min_market_cap:
        return False, f"Market cap ${market_cap/1e6:.0f}M too small (min ${SCANNER_CONFIG.min_market_cap/1e6:.0f}M)"
    
    if market_cap > SCANNER_CONFIG.max_market_cap:
        return False, f"Market cap ${market_cap/1e9:.1f}B too large (max ${SCANNER_CONFIG.max_market_cap/1e9:.1f}B)"
    
    return True, "Pass"


def passes_price_filter(price: float) -> Tuple[bool, str]:
    """
    Check if price is within acceptable range.
    
    Args:
        price: Current stock price
    
    Returns:
        (passes, reason_if_failed)
    """
    if price < SCANNER_CONFIG.min_price:
        return False, f"Price ${price:.2f} below minimum ${SCANNER_CONFIG.min_price:.2f}"
    
    if price > SCANNER_CONFIG.max_price:
        return False, f"Price ${price:.2f} above maximum ${SCANNER_CONFIG.max_price:.2f}"
    
    return True, "Pass"


def passes_liquidity_filter(volume_usd: float, avg_volume: int) -> Tuple[bool, str]:
    """
    Check if stock has sufficient liquidity.
    
    Args:
        volume_usd: Daily dollar volume
        avg_volume: Average daily volume (shares)
    
    Returns:
        (passes, reason_if_failed)
    """
    if volume_usd < SCANNER_CONFIG.min_daily_volume_usd:
        return False, f"Volume ${volume_usd/1e6:.1f}M too low (min ${SCANNER_CONFIG.min_daily_volume_usd/1e6:.1f}M)"
    
    if avg_volume < SCANNER_CONFIG.min_avg_volume:
        return False, f"Avg volume {avg_volume/1e3:.0f}k too low (min {SCANNER_CONFIG.min_avg_volume/1e3:.0f}k)"
    
    return True, "Pass"


def passes_sector_filter(sector: str) -> Tuple[bool, str]:
    """
    Check if sector is allowed.
    
    Args:
        sector: Stock sector
    
    Returns:
        (passes, reason_if_failed)
    """
    if sector in BANNED_SECTORS:
        return False, f"Banned sector: {sector}"
    
    return True, "Pass"


def passes_fundamental_quality(stock_data: dict) -> Tuple[bool, str]:
    """
    Check fundamental quality gates.
    
    Args:
        stock_data: Dict from get_stock_info()
    
    Returns:
        (passes, reason_if_failed)
    """
    revenue_growth = stock_data.get('revenue_growth', 0)
    profit_margin = stock_data.get('profit_margin', -999)
    pe_ratio = stock_data.get('pe_ratio', 999)
    
    # Revenue growth check (optional)
    if SCANNER_CONFIG.min_revenue_growth > 0:
        if revenue_growth < SCANNER_CONFIG.min_revenue_growth:
            return False, f"Revenue growth {revenue_growth:.1f}% below minimum {SCANNER_CONFIG.min_revenue_growth:.1f}%"
    
    # Profitability check (optional)
    if SCANNER_CONFIG.require_positive_earnings:
        if profit_margin < 0:
            return False, "Not profitable (required)"
    
    # Valuation check
    if pe_ratio > SCANNER_CONFIG.max_pe_ratio and pe_ratio < 999:
        return False, f"P/E ratio {pe_ratio:.0f} too high (max {SCANNER_CONFIG.max_pe_ratio:.0f})"
    
    return True, "Pass"


def passes_all_quality_filters(stock_data: dict) -> Tuple[bool, str]:
    """
    Run all quality filters on a stock.
    
    Args:
        stock_data: Dict from get_stock_info()
    
    Returns:
        (passes, reason_if_failed)
    """
    ticker = stock_data.get('ticker', 'Unknown')
    
    # Basic data check
    if not stock_data or stock_data.get('price', 0) == 0:
        return False, "No data available"
    
    # Market cap filter
    market_cap = stock_data.get('market_cap', 0)
    passes, reason = passes_market_cap_filter(market_cap)
    if not passes:
        return False, reason
    
    # Price filter
    price = stock_data.get('price', 0)
    passes, reason = passes_price_filter(price)
    if not passes:
        return False, reason
    
    # Liquidity filter
    volume_usd = price * stock_data.get('volume', 0)
    avg_volume = stock_data.get('avg_volume', 0)
    passes, reason = passes_liquidity_filter(volume_usd, avg_volume)
    if not passes:
        return False, reason
    
    # Sector filter
    sector = stock_data.get('sector', 'Unknown')
    passes, reason = passes_sector_filter(sector)
    if not passes:
        return False, reason
    
    # Fundamental quality
    passes, reason = passes_fundamental_quality(stock_data)
    if not passes:
        return False, reason
    
    return True, "Pass all filters"


if __name__ == "__main__":
    # Test the filters
    print("\n" + "="*60)
    print("Testing Quality Filters")
    print("="*60 + "\n")
    
    # Test case 1: Good stock
    good_stock = {
        'ticker': 'GOOD',
        'price': 50.0,
        'market_cap': 2_000_000_000,
        'volume': 5_000_000,
        'avg_volume': 4_000_000,
        'sector': 'Technology',
        'revenue_growth': 20.0,
        'profit_margin': 15.0,
        'pe_ratio': 25.0
    }
    
    passes, reason = passes_all_quality_filters(good_stock)
    print(f"Good Stock: {passes} - {reason}")
    
    # Test case 2: Penny stock
    penny_stock = {
        'ticker': 'PENNY',
        'price': 2.0,  # Below $5 minimum
        'market_cap': 100_000_000,
        'volume': 1_000_000,
        'avg_volume': 900_000,
        'sector': 'Biotechnology',
        'revenue_growth': 5.0,
        'profit_margin': -10.0,
        'pe_ratio': 0
    }
    
    passes, reason = passes_all_quality_filters(penny_stock)
    print(f"Penny Stock: {passes} - {reason}")
    
    # Test case 3: Low liquidity
    illiquid_stock = {
        'ticker': 'ILLIQ',
        'price': 25.0,
        'market_cap': 1_000_000_000,
        'volume': 10_000,  # Very low
        'avg_volume': 50_000,
        'sector': 'Technology',
        'revenue_growth': 15.0,
        'profit_margin': 10.0,
        'pe_ratio': 20.0
    }
    
    passes, reason = passes_all_quality_filters(illiquid_stock)
    print(f"Illiquid Stock: {passes} - {reason}")
    
    print("\n" + "="*60)