"""
Supabot V2 - Insider Activity Module
Track insider buying/selling - the ultimate leading indicator.

Insiders know what's coming 1-3 months before the market.
Heavy buying = bullish signal. Heavy selling = warning sign.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import functools
from typing import Dict, List
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

from config import MOCK_MODE

@functools.lru_cache(maxsize=500)
def get_insider_trades(ticker: str, days: int = 90) -> Dict:
    """
    Get insider trades from SEC Edgar (official, free, reliable).
    
    Uses yfinance insider transactions (free, no API key needed).
    """
    
    if MOCK_MODE:
        # Simulate insider activity
        has_buying = (hash(ticker) % 3) == 0  # 33% have buying
        
        if has_buying:
            return {
                'buys': [
                    {'date': '2025-10-15', 'shares': 50000, 'value': 2500000, 'insider': 'CEO'},
                    {'date': '2025-10-20', 'shares': 25000, 'value': 1300000, 'insider': 'CFO'},
                ],
                'sells': [],
                'buy_count': 2,
                'sell_count': 0,
                'net_shares': 75000,
                'total_buy_value': 3800000,
                'has_cluster_buying': True,
                'insider_score': 0.8,
                'buy_sell_ratio': 99.0
            }
        else:
            return {
                'buys': [],
                'sells': [],
                'buy_count': 0,
                'sell_count': 0,
                'net_shares': 0,
                'total_buy_value': 0,
                'has_cluster_buying': False,
                'insider_score': 0.0,
                'buy_sell_ratio': 0.0
            }
    
    try:
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        
        # Get insider transactions
        insider_txns = stock.insider_transactions
        
        if insider_txns is None or insider_txns.empty:
            return {
                'buys': [],
                'sells': [],
                'buy_count': 0,
                'sell_count': 0,
                'net_shares': 0,
                'total_buy_value': 0,
                'has_cluster_buying': False,
                'insider_score': 0.0,
                'buy_sell_ratio': 0.0
            }
        
        # Filter to recent transactions
        cutoff_date = datetime.now() - timedelta(days=days)
        
        buys = []
        sells = []
        
        for idx, row in insider_txns.iterrows():
            try:
                # Parse transaction date
                start_date = row.get('Start Date', idx)
                if isinstance(start_date, str):
                    txn_date = datetime.strptime(start_date, '%Y-%m-%d')
                else:
                    txn_date = start_date
                
                if txn_date < cutoff_date:
                    continue
                
                shares = row.get('Shares', 0)
                value = row.get('Value', 0)
                insider_name = row.get('Insider Trading', 'Unknown')
                
                transaction = {
                    'date': txn_date.strftime('%Y-%m-%d'),
                    'insider': insider_name,
                    'shares': abs(int(shares)) if shares else 0,
                    'value': abs(float(value)) if value else 0,
                }
                
                # Classify as buy (positive shares) or sell (negative)
                if shares > 0:
                    buys.append(transaction)
                elif shares < 0:
                    sells.append(transaction)
            
            except Exception:
                continue
        
        # Calculate metrics
        buy_count = len(buys)
        sell_count = len(sells)
        net_shares = sum(b['shares'] for b in buys) - sum(s['shares'] for s in sells)
        total_buy_value = sum(b['value'] for b in buys)
        
        # Check for cluster buying (3+ purchases in 30 days)
        cutoff_30d = datetime.now() - timedelta(days=30)
        recent_buys = [b for b in buys if datetime.strptime(b['date'], '%Y-%m-%d') > cutoff_30d]
        has_cluster_buying = len(recent_buys) >= 3
        
        # Calculate insider score (0-1)
        score = 0.0
        if buy_count > 0:
            score += min(buy_count / 5.0, 0.4)  # Up to 0.4 for multiple buys
        if has_cluster_buying:
            score += 0.3  # Cluster buying is very bullish
        if net_shares > 0:
            score += 0.3  # Net buying
        
        # Penalize if heavy selling
        if sell_count > buy_count * 2:
            score *= 0.5  # Cut score in half if heavy selling
        
        return {
            'buys': buys,
            'sells': sells,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'net_shares': net_shares,
            'total_buy_value': total_buy_value,
            'has_cluster_buying': has_cluster_buying,
            'insider_score': round(min(score, 1.0), 2),
            'buy_sell_ratio': buy_count / max(sell_count, 1)
        }
    
    except Exception as e:
        print(f"Insider data error for {ticker}: {e}")
        return {
            'buys': [],
            'sells': [],
            'buy_count': 0,
            'sell_count': 0,
            'net_shares': 0,
            'total_buy_value': 0,
            'has_cluster_buying': False,
            'insider_score': 0.0,
            'buy_sell_ratio': 0.0
        }


def get_insider_summary(ticker: str) -> str:
    """
    Get human-readable insider activity summary.
    
    Returns:
        Summary string for display
    """
    data = get_insider_trades(ticker)
    
    if data['buy_count'] == 0 and data['sell_count'] == 0:
        return "No recent insider activity"
    
    parts = []
    
    if data['buy_count'] > 0:
        parts.append(f"{data['buy_count']} insider buys (${data['total_buy_value']/1e6:.1f}M)")
    
    if data['sell_count'] > 0:
        parts.append(f"{data['sell_count']} sells")
    
    if data['has_cluster_buying']:
        parts.append("CLUSTER BUYING ⚠️")
    
    return "; ".join(parts)


if __name__ == "__main__":
    # Test insider tracking
    print("\nTesting Insider Activity Module...\n")
    
    test_tickers = ["NVDA", "PLTR", "SOFI"]
    
    for ticker in test_tickers:
        print(f"\n{ticker}:")
        data = get_insider_trades(ticker, days=90)
        summary = get_insider_summary(ticker)
        
        print(f"  Summary: {summary}")
        print(f"  Insider Score: {data['insider_score']:.2f}/1.0")
        print(f"  Buy/Sell Ratio: {data['buy_sell_ratio']:.1f}")
        
        if data['has_cluster_buying']:
            print(f"  🚨 CLUSTER BUYING DETECTED!")
        
        if data['buys']:
            print(f"\n  Recent Buys:")
            for buy in data['buys'][:3]:
                print(f"    - {buy['date']}: {buy['insider']} bought {buy['shares']:,} shares")