"""
Supabot V2 - Main Scanner (SECTOR-OPTIMIZED)
REQUIRES: Fresh + Accelerating (validated 60% WR overall)
EXCLUDES: Squeeze signals (22% WR, toxic)
EXCLUDES: Energy/Consumer/Utilities sectors (33-50% WR vs 100% Healthcare)
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
from typing import List, Dict
from datetime import datetime
import pandas as pd

from config import SCANNER_CONFIG, ENABLE_AI_ANALYSIS
from data.market_data import get_stock_info, get_price_changes, get_float_analysis, get_short_interest
from data.technical_analysis import get_technical_analysis
from data.social_signals import get_quality_universe, get_social_intelligence
from filters.quality_filter import passes_all_quality_filters
from filters.price_action_filter import passes_all_price_action_filters, is_fresh_signal
from analysis.ai_analyzer import AIAnalyzer


class SupabotScanner:
    """Main scanner with sector filtering."""
    
    def __init__(self):
        self.ai_analyzer = AIAnalyzer() if ENABLE_AI_ANALYSIS else None
        self.scan_results = []
        self.filtered_results = []
    
    def scan(self, custom_tickers: List[str] = None, top_k: int = None) -> pd.DataFrame:
        """Run scan with sector filter (no regime check)."""
        
        top_k = top_k or SCANNER_CONFIG.top_k
        
        print("\n" + "="*70)
        print("🤖 SUPABOT V2 - SECTOR-OPTIMIZED SCANNER")
        print("="*70)
        print("Validated: Healthcare 100% WR, Technology 67% WR")
        print("Excluding: Energy/Consumer/Utilities (33-50% WR)")
        print("="*70 + "\n")
        
        print(f"📊 Step 1: Getting quality universe...")
        universe = custom_tickers if custom_tickers else get_quality_universe()
        universe = universe[:SCANNER_CONFIG.scan_limit]
        print(f"   → {len(universe)} stocks in universe (sector-filtered)")
        
        print(f"\n🔍 Step 2: Quality filtering...")
        quality_passed = self._filter_by_quality(universe)
        print(f"   → {len(quality_passed)} passed quality filters")
        
        if len(quality_passed) == 0:
            print("\n❌ No stocks passed quality filters!")
            return pd.DataFrame()
        
        print(f"\n📈 Step 3: Price action filtering...")
        price_action_passed = self._filter_by_price_action(quality_passed)
        print(f"   → {len(price_action_passed)} passed price action filters")
        
        if len(price_action_passed) == 0:
            print("\n❌ No stocks passed price action filters!")
            return pd.DataFrame()
        
        print(f"\n🌐 Step 4: Analyzing social signals...")
        social_scored = self._analyze_social_signals(price_action_passed)
        print(f"   → {len(social_scored)} stocks with social activity")
        
        print(f"\n📊 Step 5: Running technical analysis...")
        technical_scored = self._analyze_technicals(social_scored)
        
        if ENABLE_AI_ANALYSIS and self.ai_analyzer:
            print(f"\n🤖 Step 6: Running AI analysis...")
            ai_analyzed = self._run_ai_analysis(technical_scored)
        else:
            print(f"\n⚠️  Step 6: AI analysis disabled")
            ai_analyzed = technical_scored
        
        print(f"\n🏆 Step 7: Scoring and ranking...")
        final_scores = self._calculate_final_scores(ai_analyzed)
        print(f"\n   🔍 final_scores returned: {len(final_scores)} items")  # ← ADD THIS

        df = pd.DataFrame(final_scores)
        print(f"   🔍 DataFrame created: {len(df)} rows")  # ← ADD THIS
        print(f"   🔍 DataFrame columns: {df.columns.tolist() if not df.empty else 'EMPTY'}")  # ← ADD THIS

        if df.empty:
            print("\n❌ No candidates after scoring!")
            return pd.DataFrame()
        
        df = df.sort_values('composite_score', ascending=False)
        df = df[df['composite_score'] >= SCANNER_CONFIG.min_composite_score]
        
        if df.empty:
            print("   ⚠️  No fresh signals found")
            return pd.DataFrame()
        
        top_candidates = df.head(top_k)
        
        print(f"\n✅ Found {len(top_candidates)} high-quality candidates!")
        print("="*70 + "\n")
        
        return top_candidates
    
    def _filter_by_quality(self, tickers: List[str]) -> List[Dict]:
        """Filter tickers by fundamental quality."""
        passed = []
        
        for ticker in tickers:
            try:
                stock_data = get_stock_info(ticker)
                if not stock_data:
                    continue
                
                passes, reason = passes_all_quality_filters(stock_data)
                
                if passes:
                    passed.append({
                        'ticker': ticker,
                        'stock_data': stock_data
                    })
            except Exception as e:
                continue
        
        return passed
    
    def _filter_by_price_action(self, stocks: List[Dict]) -> List[Dict]:
        """Filter by price action."""
        passed = []
        
        for stock in stocks:
            try:
                ticker = stock['ticker']
                stock_data = stock['stock_data']
                
                price_changes = get_price_changes(ticker)
                stock_data.update(price_changes)
                
                technical = get_technical_analysis(ticker)
                
                passes, reason = passes_all_price_action_filters(price_changes, technical)
                
                if not passes:
                    print(f"   ✗ {ticker}: {reason}")
                
                if passes:
                    is_fresh = is_fresh_signal(
                        price_changes.get('change_7d', 0),
                        price_changes.get('change_90d', 0)
                    )
                    
                    passed.append({
                        'ticker': ticker,
                        'stock_data': stock_data,
                        'price_changes': price_changes,
                        'technical': technical,
                        'is_fresh': is_fresh
                    })
            except Exception as e:
                continue
        
        return passed
    
    def _analyze_social_signals(self, stocks: List[Dict]) -> List[Dict]:
        """Analyze social signals."""
        results = []
        
        for stock in stocks:
            try:
                ticker = stock['ticker']
                social = get_social_intelligence(ticker)
                
                if social.get('composite_score', 0) > 0.2:
                    stock['social'] = social
                    results.append(stock)
            except Exception as e:
                stock['social'] = {'composite_score': 0.0}
                results.append(stock)
        
        return results
    
    def _analyze_technicals(self, stocks: List[Dict]) -> List[Dict]:
        """Run technical analysis."""
        for stock in stocks:
            if 'technical' not in stock:
                try:
                    stock['technical'] = get_technical_analysis(stock['ticker'])
                except:
                    stock['technical'] = {'technical_score': 3.0}
        return stocks
    
    def _run_ai_analysis(self, stocks: List[Dict]) -> List[Dict]:
        """Run AI analysis."""
        for stock in stocks:
            try:
                ticker = stock['ticker']
                ai_result = self.ai_analyzer.analyze_stock(
                    ticker,
                    stock['stock_data'],
                    stock['social'],
                    stock['technical']
                )
                stock['ai_analysis'] = ai_result
            except Exception as e:
                stock['ai_analysis'] = {
                    'rating': 'HOLD',
                    'composite_score': 3.0
                }
        return stocks
    
    def _calculate_final_scores(self, stocks: List[Dict]) -> List[Dict]:
        """Calculate final scores."""
        
        # Import enhanced modules
        try:
            from data.fundamentals import get_financial_statements, calculate_advanced_valuation, calculate_quality_score
            from data.news_events import get_catalyst_summary
            has_enhanced_data = True
        except:
            has_enhanced_data = False
        
        results = []
        
        for stock in stocks:
            try:
                ticker = stock['ticker']
                stock_data = stock['stock_data']
                price_changes = stock.get('price_changes', {})
                social = stock.get('social', {})
                technical = stock.get('technical', {})
                ai_analysis = stock.get('ai_analysis', {})
                
                is_fresh = stock.get('is_fresh', False)
                is_accelerating = social.get('is_accelerating', False)
                print(f"   DEBUG {ticker}: is_fresh={is_fresh}, is_accelerating={is_accelerating}")

                if not (is_fresh and is_accelerating):
                    print(f"   ✗ {ticker}: Filtered (fresh={is_fresh}, accel={is_accelerating})")

                    continue
                
                float_data = get_float_analysis(ticker)
                short_data = get_short_interest(ticker)
                
                has_squeeze = short_data.get('squeeze_potential', False)
                short_percent = short_data.get('short_percent', 0)
                
                if has_squeeze or short_percent > 20:
                    print(f"   ✗ {ticker}: Squeeze {short_percent:.0f}% - EXCLUDED")
                    continue

                if ENABLE_AI_ANALYSIS and 'composite_score' in ai_analysis:
                    base_composite = ai_analysis['composite_score']
                else:
                    base_composite = 3.5
                
                result = {
                    'ticker': ticker,
                    'price': stock_data.get('price', 0),
                    'market_cap': stock_data.get('market_cap', 0),
                    'sector': stock_data.get('sector', 'Unknown'),
                    'change_7d': price_changes.get('change_7d', 0),
                    'is_fresh': is_fresh,
                    'is_accelerating': is_accelerating,
                    'x_mentions': social.get('x_recent_mentions', 0),
                    'reddit_mentions': social.get('reddit_total_mentions', 0),
                    'composite_score': base_composite,
                    'rating': ai_analysis.get('rating', 'HOLD'),
                    'conviction': ai_analysis.get('conviction', 'MEDIUM'),
                    'position_size': 'half',
                    'stop_loss': stock_data.get('price', 0) * 0.92,
                    'hold_period': '7 days',
                }
                
                results.append(result)
                print(f"   ✅ {ticker}: Added to results! Score: {base_composite}")  # ← MOVE IT HERE

            except Exception as e:
                print(f"   ❌ {ticker}: ERROR creating result - {e}")
                continue
        
        return results


def run_scan(custom_tickers: List[str] = None, top_k: int = None) -> pd.DataFrame:
    """Convenience function to run a scan."""
    scanner = SupabotScanner()
    return scanner.scan(custom_tickers=custom_tickers, top_k=top_k)


if __name__ == "__main__":
    print("\n🤖 Supabot V2 - Sector-Optimized Scanner\n")
    
    # Run scan (no regime check, sector-filtered universe)
    results = run_scan(top_k=5)
    
    if not results.empty:
        print("\n✅ V2 scan complete - sending to Discord...")
        
        from discord_notify import send_scan_results
        send_scan_results(results, {'scanned': SCANNER_CONFIG.scan_limit})
    else:
        print("\n❌ No picks found\n")