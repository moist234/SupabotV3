"""
Supabot V2 - Fundamentals Module
Deep financial analysis: statements, ratios, quality scores.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import functools
from typing import Dict
import requests
from datetime import datetime

from data.market_data import get_stock_info
from config import MOCK_MODE

# Get API keys from environment
FMP_API_KEY = os.getenv("FMP_API_KEY", "")

@functools.lru_cache(maxsize=500)
def get_financial_statements(ticker: str) -> Dict:
    """
    Get complete financial statements from Financial Modeling Prep.
    
    Returns income statement, balance sheet, and cash flow data.
    Free tier: 250 API calls/day
    Sign up: https://financialmodelingprep.com
    """
    
    if MOCK_MODE or not FMP_API_KEY:
        # Mock data
        return {
            'revenue': 10_000_000_000,
            'gross_profit': 7_000_000_000,
            'operating_income': 2_000_000_000,
            'net_income': 1_500_000_000,
            'eps': 3.50,
            'ebitda': 2_500_000_000,
            'total_assets': 15_000_000_000,
            'total_debt': 3_000_000_000,
            'cash': 5_000_000_000,
            'shareholders_equity': 10_000_000_000,
            'operating_cash_flow': 2_000_000_000,
            'free_cash_flow': 1_500_000_000,
            'capex': 500_000_000,
            'gross_margin': 70.0,
            'operating_margin': 20.0,
            'fcf_margin': 15.0,
            'debt_to_equity': 0.3,
        }
    
    try:
        base_url = "https://financialmodelingprep.com/api/v3"
        
        # Get quarterly data (most recent)
        income_url = f"{base_url}/income-statement/{ticker}?period=quarter&limit=1&apikey={FMP_API_KEY}"
        balance_url = f"{base_url}/balance-sheet-statement/{ticker}?period=quarter&limit=1&apikey={FMP_API_KEY}"
        cashflow_url = f"{base_url}/cash-flow-statement/{ticker}?period=quarter&limit=1&apikey={FMP_API_KEY}"
        
        income_data = requests.get(income_url, timeout=10).json()
        balance_data = requests.get(balance_url, timeout=10).json()
        cashflow_data = requests.get(cashflow_url, timeout=10).json()
        
        if not income_data or not balance_data or not cashflow_data:
            return {}
        
        # Extract latest quarter
        income = income_data[0] if isinstance(income_data, list) else income_data
        balance = balance_data[0] if isinstance(balance_data, list) else balance_data
        cashflow = cashflow_data[0] if isinstance(cashflow_data, list) else cashflow_data
        
        revenue = income.get('revenue', 0)
        gross_profit = income.get('grossProfit', 0)
        operating_income = income.get('operatingIncome', 0)
        
        return {
            # Income Statement
            'revenue': revenue,
            'gross_profit': gross_profit,
            'operating_income': operating_income,
            'net_income': income.get('netIncome', 0),
            'eps': income.get('eps', 0),
            'ebitda': income.get('ebitda', 0),
            
            # Balance Sheet
            'total_assets': balance.get('totalAssets', 0),
            'total_debt': balance.get('totalDebt', 0),
            'cash': balance.get('cashAndCashEquivalents', 0),
            'shareholders_equity': balance.get('totalStockholdersEquity', 0),
            
            # Cash Flow
            'operating_cash_flow': cashflow.get('operatingCashFlow', 0),
            'free_cash_flow': cashflow.get('freeCashFlow', 0),
            'capex': cashflow.get('capitalExpenditure', 0),
            
            # Margins (calculated)
            'gross_margin': (gross_profit / revenue * 100) if revenue > 0 else 0,
            'operating_margin': (operating_income / revenue * 100) if revenue > 0 else 0,
            'fcf_margin': (cashflow.get('freeCashFlow', 0) / revenue * 100) if revenue > 0 else 0,
            'debt_to_equity': (balance.get('totalDebt', 0) / balance.get('totalStockholdersEquity', 1)),
        }
    
    except Exception as e:
        print(f"FMP API error for {ticker}: {e}")
        return {}


def calculate_advanced_valuation(ticker: str) -> Dict:
    """
    Calculate institutional valuation metrics.
    
    Returns EV/EBITDA, P/FCF, FCF yield, etc.
    """
    
    financials = get_financial_statements(ticker)
    info = get_stock_info(ticker)
    
    if not financials or not info:
        return {}
    
    market_cap = info.get('market_cap', 0)
    total_debt = financials.get('total_debt', 0)
    cash = financials.get('cash', 0)
    
    # Enterprise Value
    enterprise_value = market_cap + total_debt - cash
    
    # Key ratios
    ebitda = financials.get('ebitda', 0)
    fcf = financials.get('free_cash_flow', 0)
    revenue = financials.get('revenue', 0)
    
    return {
        'enterprise_value': enterprise_value,
        'ev_to_ebitda': round(enterprise_value / ebitda, 2) if ebitda > 0 else 0,
        'price_to_fcf': round(market_cap / fcf, 2) if fcf > 0 else 0,
        'fcf_yield': round((fcf / market_cap) * 100, 2) if market_cap > 0 else 0,
        'ev_to_revenue': round(enterprise_value / revenue, 2) if revenue > 0 else 0,
    }


def calculate_quality_score(financials: Dict) -> float:
    """
    Calculate fundamental quality score (0-1).
    
    Based on: margins, cash flow, debt level, growth.
    """
    
    if not financials:
        return 0.5
    
    score = 0.0
    
    # High margins (40% of score)
    gross_margin = financials.get('gross_margin', 0)
    fcf_margin = financials.get('fcf_margin', 0)
    
    if gross_margin > 60:
        score += 0.2
    elif gross_margin > 40:
        score += 0.1
    
    if fcf_margin > 15:
        score += 0.2
    elif fcf_margin > 5:
        score += 0.1
    
    # Strong cash flow (30% of score)
    fcf = financials.get('free_cash_flow', 0)
    if fcf > 0:
        score += 0.2
        if fcf > 500_000_000:  # $500M+ FCF
            score += 0.1
    
    # Low debt (30% of score)
    debt_to_equity = financials.get('debt_to_equity', 999)
    if debt_to_equity < 0.3:
        score += 0.3
    elif debt_to_equity < 0.7:
        score += 0.15
    
    return min(score, 1.0)


if __name__ == "__main__":
    # Test
    print("\nTesting Fundamentals Module...\n")
    
    test_ticker = "AAPL"
    
    financials = get_financial_statements(test_ticker)
    print(f"Financial Data for {test_ticker}:")
    print(f"  Revenue: ${financials.get('revenue', 0)/1e9:.2f}B")
    print(f"  Gross Margin: {financials.get('gross_margin', 0):.1f}%")
    print(f"  FCF: ${financials.get('free_cash_flow', 0)/1e9:.2f}B")
    print(f"  Debt/Equity: {financials.get('debt_to_equity', 0):.2f}")
    
    valuation = calculate_advanced_valuation(test_ticker)
    print(f"\nValuation Metrics:")
    print(f"  EV/EBITDA: {valuation.get('ev_to_ebitda', 0):.1f}")
    print(f"  P/FCF: {valuation.get('price_to_fcf', 0):.1f}")
    print(f"  FCF Yield: {valuation.get('fcf_yield', 0):.2f}%")
    
    quality = calculate_quality_score(financials)
    print(f"\nQuality Score: {quality:.2f}/1.0")