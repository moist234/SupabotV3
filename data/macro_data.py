"""
Supabot V2 - Macro Data Module
Track key macro indicators: VIX, rates, USD strength, China risk.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import functools
import requests
from datetime import datetime, timedelta

# Silence yfinance warnings
import logging
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

import yfinance as yf

from config import MOCK_MODE

FRED_API_KEY = os.getenv("FRED_API_KEY", "")


@functools.lru_cache(maxsize=1, typed=False)
def get_vix() -> float:
    """Get current VIX (market fear gauge)."""
    
    if MOCK_MODE:
        return 18.5
    
    try:
        vix = yf.Ticker("^VIX")
        data = vix.history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    
    return 0.0


@functools.lru_cache(maxsize=1, typed=False)
def get_treasury_yield() -> float:
    """Get 10-year treasury yield."""
    
    if MOCK_MODE:
        return 4.25
    
    try:
        tnx = yf.Ticker("^TNX")
        data = tnx.history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    
    return 0.0


@functools.lru_cache(maxsize=1, typed=False)
def get_usd_cny() -> float:
    """Get USD/CNY exchange rate (China trade risk indicator)."""
    
    if MOCK_MODE:
        return 7.25
    
    try:
        cny = yf.Ticker("CNY=X")
        data = cny.history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    
    return 0.0


@functools.lru_cache(maxsize=1, typed=False)
def get_usd_eur() -> float:
    """Get USD/EUR exchange rate."""
    
    if MOCK_MODE:
        return 1.08
    
    try:
        eur = yf.Ticker("EURUSD=X")
        data = eur.history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    
    return 0.0


def get_fred_indicator(series_id: str) -> dict:
    """Get latest value from FRED API."""
    
    if MOCK_MODE or not FRED_API_KEY:
        return {'value': 0.0, 'date': 'Unknown'}
    
    try:
        base_url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            'series_id': series_id,
            'api_key': FRED_API_KEY,
            'file_type': 'json',
            'limit': 1,
            'sort_order': 'desc'
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        data = response.json()
        
        if 'observations' in data and data['observations']:
            latest = data['observations'][0]
            return {
                'value': float(latest['value']),
                'date': latest['date']
            }
    except:
        pass
    
    return {'value': 0.0, 'date': 'Unknown'}


@functools.lru_cache(maxsize=1, typed=False)
def get_macro_summary() -> dict:
    """
    Get comprehensive macro snapshot.
    
    Returns key indicators that affect stock performance.
    """
    
    # Market volatility
    vix = get_vix()
    vix_level = 'high' if vix > 25 else 'elevated' if vix > 20 else 'moderate' if vix > 15 else 'low'
    
    # Rates
    ten_year = get_treasury_yield()
    rate_environment = 'rising' if ten_year > 4.5 else 'elevated' if ten_year > 4.0 else 'moderate' if ten_year > 3.5 else 'low'
    
    # Currency
    usd_cny = get_usd_cny()
    usd_eur = get_usd_eur()
    usd_strength = 'strong' if usd_cny > 7.3 else 'moderate' if usd_cny > 7.1 else 'weak'
    
    # China risk (higher CNY = more tension)
    china_risk = 'high' if usd_cny > 7.3 else 'moderate' if usd_cny > 7.15 else 'low'
    
    # Get FRED indicators if available
    fed_funds = get_fred_indicator('FEDFUNDS')
    cpi = get_fred_indicator('CPIAUCSL')
    unemployment = get_fred_indicator('UNRATE')
    gdp = get_fred_indicator('A191RL1Q225SBEA')
    
    return {
        # Market fear
        'vix': round(vix, 2),
        'vix_level': vix_level,
        'market_fear': 'Extreme' if vix > 30 else 'High' if vix > 25 else 'Elevated' if vix > 20 else 'Low',
        
        # Rates
        'ten_year_yield': round(ten_year, 2),
        'rate_environment': rate_environment,
        'fed_funds_rate': round(fed_funds.get('value', 0), 2),
        
        # Currency
        'usd_cny': round(usd_cny, 2),
        'usd_eur': round(usd_eur, 2),
        'usd_strength': usd_strength,
        'china_trade_risk': china_risk,
        
        # Economic indicators
        'inflation_rate': round(cpi.get('value', 0), 1),
        'unemployment_rate': round(unemployment.get('value', 0), 1),
        'gdp_growth': round(gdp.get('value', 0), 1),
        
        # Timestamp
        'updated_at': datetime.now().isoformat()
    }


def interpret_macro_for_sector(macro: dict, sector: str) -> str:
    """
    Interpret how macro conditions affect a specific sector.
    
    Args:
        macro: Dict from get_macro_summary()
        sector: Stock sector
    
    Returns:
        Brief interpretation string
    """
    
    vix = macro.get('vix', 0)
    ten_year = macro.get('ten_year_yield', 0)
    china_risk = macro.get('china_trade_risk', 'low')
    
    # Tech sector (most common)
    if sector in ['Technology', 'Software', 'Cloud', 'AI']:
        if ten_year > 4.5:
            return "High rates pressure tech valuations (headwind)"
        elif vix > 25:
            return "High volatility = risk-off rotation (headwind)"
        else:
            return "Stable macro environment (neutral to bullish)"
    
    # Industrials / Manufacturing
    elif sector in ['Industrials', 'Manufacturing', 'Materials']:
        if china_risk == 'high':
            return "China trade tensions = supply chain risk (headwind)"
        elif ten_year < 4.0:
            return "Lower rates support capex spending (tailwind)"
        else:
            return "Moderate macro conditions (neutral)"
    
    # Financials
    elif sector in ['Financials', 'Banking', 'Insurance']:
        if ten_year > 4.5:
            return "High rates expand net interest margin (tailwind)"
        else:
            return "Lower rates compress margins (headwind)"
    
    # Consumer
    elif sector in ['Consumer Cyclical', 'Retail', 'E-commerce']:
        unemployment = macro.get('unemployment_rate', 0)
        if unemployment < 4.0 and vix < 20:
            return "Strong employment + low volatility (tailwind)"
        else:
            return "Consumer uncertainty (headwind)"
    
    # Default
    else:
        if vix > 25:
            return "High market volatility (risk-off environment)"
        else:
            return "Stable macro conditions"


if __name__ == "__main__":
    # Test
    print("\nTesting Macro Data Module...\n")
    
    macro = get_macro_summary()
    
    print("Current Macro Snapshot:")
    print(f"  VIX: {macro['vix']} ({macro['vix_level']}) - {macro['market_fear']} fear")
    print(f"  10Y Yield: {macro['ten_year_yield']}% ({macro['rate_environment']} rates)")
    print(f"  USD/CNY: {macro['usd_cny']} ({macro['usd_strength']} dollar)")
    print(f"  China Risk: {macro['china_trade_risk'].upper()}")
    
    if macro.get('fed_funds_rate', 0) > 0:
        print(f"\n  Fed Funds: {macro['fed_funds_rate']}%")
        print(f"  Inflation: {macro['inflation_rate']}%")
        print(f"  Unemployment: {macro['unemployment_rate']}%")
    
    print("\nSector Interpretations:")
    for sector in ['Technology', 'Industrials', 'Financials', 'Consumer Cyclical']:
        interp = interpret_macro_for_sector(macro, sector)
        print(f"  {sector}: {interp}")