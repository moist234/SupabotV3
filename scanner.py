"""
Supabot V2 - Main Scanner
Orchestrates all modules to find high-quality trading opportunities.
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
    """
    Main scanner class that orchestrates all analysis modules.
    """
    
    def __init__(self):
        self.ai_analyzer = AIAnalyzer() if ENABLE_AI_ANALYSIS else None
        self.scan_results = []
        self.filtered_results = []
    
    def scan(self, custom_tickers: List[str] = None, top_k: int = None) -> pd.DataFrame:
        """
        Run complete scan pipeline.
        
        Pipeline:
        1. Get quality universe (Finviz screener)
        2. Filter by quality (market cap, liquidity, fundamentals)
        3. Filter by price action (not pumped, not falling)
        4. Check social signals (buzz acceleration)
        5. Run technical analysis
        6. Run AI analysis (6 master prompts)
        7. Score and rank (with insider/catalyst boosts)
        8. Return top K candidates
        
        Args:
            custom_tickers: Optional list to scan instead of default universe
            top_k: Number of top candidates to return (default from config)
        
        Returns:
            DataFrame with top candidates, sorted by composite score
        """
        
        top_k = top_k or SCANNER_CONFIG.top_k
        
        print("\n" + "="*70)
        print("🤖 SUPABOT V2 - QUALITY-FIRST SCANNER")
        print("="*70)
        
        # Step 1: Get universe
        print(f"\n📊 Step 1: Getting quality universe...")
        universe = custom_tickers if custom_tickers else get_quality_universe()
        universe = universe[:SCANNER_CONFIG.scan_limit]
        print(f"   → {len(universe)} stocks in universe")
        
        # Step 2: Quality filtering
        print(f"\n🔍 Step 2: Quality filtering...")
        quality_passed = self._filter_by_quality(universe)
        print(f"   → {len(quality_passed)} passed quality filters")
        
        if len(quality_passed) == 0:
            print("\n❌ No stocks passed quality filters!")
            return pd.DataFrame()
        
        # Step 3: Price action filtering
        print(f"\n📈 Step 3: Price action filtering...")
        price_action_passed = self._filter_by_price_action(quality_passed)
        print(f"   → {len(price_action_passed)} passed price action filters")
        
        if len(price_action_passed) == 0:
            print("\n❌ No stocks passed price action filters!")
            return pd.DataFrame()
        
        # Step 4: Social signals analysis
        print(f"\n🌐 Step 4: Analyzing social signals...")
        social_scored = self._analyze_social_signals(price_action_passed)
        print(f"   → {len(social_scored)} stocks with social activity")
        
        # Step 5: Technical analysis
        print(f"\n📊 Step 5: Running technical analysis...")
        technical_scored = self._analyze_technicals(social_scored)
        print(f"   → Technical analysis complete")
        
        # Step 6: AI analysis (optional)
        if ENABLE_AI_ANALYSIS and self.ai_analyzer:
            print(f"\n🤖 Step 6: Running AI analysis...")
            ai_analyzed = self._run_ai_analysis(technical_scored)
            print(f"   → AI analysis complete")
        else:
            print(f"\n⚠️  Step 6: AI analysis disabled")
            ai_analyzed = technical_scored
        
        # Step 7: Score and rank
        print(f"\n🏆 Step 7: Scoring and ranking...")
        final_scores = self._calculate_final_scores(ai_analyzed)
        
        print(f"\n📊 SCORING SUMMARY:")
        for stock in final_scores:
            ticker = stock['ticker']
            score = stock['composite_score']
            rating = stock['rating']
            
            # Show insider activity if present
            insider_flag = " 👔💰" if stock.get('has_insider_buying', False) else ""
            
            if score >= SCANNER_CONFIG.min_composite_score:
                print(f"   ✓ {ticker}: {score}/5.0 - {rating}{insider_flag} (INCLUDED)")
            else:
                print(f"   ✗ {ticker}: {score}/5.0 - {rating}{insider_flag} (Below threshold {SCANNER_CONFIG.min_composite_score})")
        
        # Step 8: Select top K
        df = pd.DataFrame(final_scores)
        
        if df.empty:
            print("\n❌ No candidates after scoring!")
            return pd.DataFrame()
        
        # Sort by composite score
        df = df.sort_values('composite_score', ascending=False)
        
        # Apply minimum score threshold
        df = df[df['composite_score'] >= SCANNER_CONFIG.min_composite_score]
        
        df = df[df['is_fresh'] == True]
        if df.empty:
            print("   ⚠️  No fresh signals found - no recommendations")
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
                print(f"   Error filtering {ticker}: {e}")
                continue
        
        return passed
    
    def _filter_by_price_action(self, stocks: List[Dict]) -> List[Dict]:
        """Filter by price action and momentum."""
        
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
                print(f"   Error checking price action for {stock['ticker']}: {e}")
                continue
        
        return passed
    
    def _analyze_social_signals(self, stocks: List[Dict]) -> List[Dict]:
        """Analyze social signals for each stock."""
        
        results = []
        
        for stock in stocks:
            try:
                ticker = stock['ticker']
                social = get_social_intelligence(ticker)
                
                if social.get('composite_score', 0) > 0.2:
                    stock['social'] = social
                    results.append(stock)
            
            except Exception as e:
                print(f"   Error analyzing social for {stock['ticker']}: {e}")
                stock['social'] = {'composite_score': 0.0, 'signal_strength': 'weak'}
                results.append(stock)
        
        return results
    
    def _analyze_technicals(self, stocks: List[Dict]) -> List[Dict]:
        """Run technical analysis (if not already done)."""
        
        for stock in stocks:
            if 'technical' not in stock:
                try:
                    stock['technical'] = get_technical_analysis(stock['ticker'])
                except:
                    stock['technical'] = {'technical_score': 3.0, 'technical_outlook': 'neutral'}
        
        return stocks
    
    def _run_ai_analysis(self, stocks: List[Dict]) -> List[Dict]:
        """Run AI analysis on each stock."""
        
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
                print(f"   Error in AI analysis for {ticker}: {e}")
                stock['ai_analysis'] = {
                    'rating': 'HOLD',
                    'conviction': 'LOW',
                    'composite_score': 3.0,
                    'fundamental_score': 3.0,
                    'technical_score': 3.0,
                    'sentiment_score': 3.0,
                    'risk_score': 0.5
                }
        
        return stocks
    
    def _calculate_final_scores(self, stocks: List[Dict]) -> List[Dict]:
        """Calculate final composite scores with ALL enhancements."""
        
        # Import enhanced modules
        try:
            from data.fundamentals import get_financial_statements, calculate_advanced_valuation, calculate_quality_score
            from data.news_events import get_catalyst_summary
            from data.insider_activity import get_insider_trades
            has_enhanced_data = True
        except Exception as import_error:
            has_enhanced_data = False
            print(f"   ⚠️  Enhanced data modules not available: {import_error}")
            print("   Using basic scoring only")
        
        results = []
        
        for stock in stocks:
            try:
                ticker = stock['ticker']
                stock_data = stock['stock_data']
                price_changes = stock.get('price_changes', {})
                social = stock.get('social', {})
                technical = stock.get('technical', {})
                ai_analysis = stock.get('ai_analysis', {})
                
                # ============ GET ENHANCED DATA ============
                if has_enhanced_data:
                    try:
                        financials = get_financial_statements(ticker)
                        valuation = calculate_advanced_valuation(ticker)
                        catalysts = get_catalyst_summary(ticker)
                        quality_score = calculate_quality_score(financials)
                        insider = get_insider_trades(ticker, days=90)
                    except Exception as e:
                        financials = {}
                        valuation = {}
                        catalysts = {}
                        quality_score = 0.5
                        insider = {'insider_score': 0.0, 'has_cluster_buying': False}
                else:
                    financials = {}
                    valuation = {}
                    catalysts = {}
                    quality_score = 0.5
                    insider = {'insider_score': 0.0, 'has_cluster_buying': False}
                
                # ============ BASE COMPOSITE SCORE ============
                if ENABLE_AI_ANALYSIS and 'composite_score' in ai_analysis:
                    base_composite = ai_analysis['composite_score']
                    rating = ai_analysis.get('rating', 'HOLD')
                    conviction = ai_analysis.get('conviction', 'MEDIUM')
                else:
                    tech_score = technical.get('technical_score', 3.0)
                    social_score = social.get('composite_score', 0.3) * 5
                    base_composite = (tech_score * 0.6 + social_score * 0.4)
                    rating = "BUY" if base_composite >= 3.8 else "HOLD"
                    conviction = "MEDIUM"
                
                # ============ APPLY ALL ENHANCEMENTS ============
                enhanced_score = base_composite
                quality_boost = 0.0
                catalyst_boost = 0.0
                insider_boost = 0.0
                
                if has_enhanced_data:
                    # 1. Quality boost (up to +0.5)
                    quality_boost = quality_score * 0.5
                    
                    # 2. Catalyst boost (up to +0.4)
                    catalyst_boost = catalysts.get('catalyst_score', 0) * 0.4
                    
                    # 3. INSIDER BOOST (up to +0.6) - MAJOR SIGNAL!
                    insider_boost = insider.get('insider_score', 0) * 0.6

                    if stock.get('is_fresh', False):
                        enhanced_score += 0.5  # Fresh is proven edge
                    
                    enhanced_score += quality_boost + catalyst_boost + insider_boost
                    
                    # 4. Valuation adjustment
                    ev_ebitda = valuation.get('ev_to_ebitda', 0)
                    if ev_ebitda > 0:
                        if ev_ebitda < 10:
                            enhanced_score += 0.3
                        elif ev_ebitda > 30:
                            enhanced_score -= 0.3
                    
                    # 5. Earnings timing
                    days_to_earnings = catalysts.get('upcoming_earnings', {}).get('days_until_earnings', 999)
                    if days_to_earnings < 7:
                        enhanced_score -= 0.2
                
                # Cap at 5.0
                enhanced_score = min(enhanced_score, 5.0)
                
                # Upgrade rating if warranted
                if enhanced_score >= 4.5:
                    rating = "STRONG_BUY"
                    conviction = "HIGH"
                elif enhanced_score >= 3.8:
                    rating = "BUY"
                    conviction = "HIGH" if insider.get('has_cluster_buying', False) else "MEDIUM"
                elif enhanced_score >= 3.0:
                    rating = "HOLD"
                    conviction = "MEDIUM"
                
                # Get float & short data
                float_data = get_float_analysis(ticker)
                short_data = get_short_interest(ticker)
                
                # ============ BUILD COMPLETE RESULT ============
                result = {
                    # Basic info
                    'ticker': ticker,
                    'price': stock_data.get('price', 0),
                    'market_cap': stock_data.get('market_cap', 0),
                    'sector': stock_data.get('sector', 'Unknown'),
                    
                    # Price changes
                    'change_7d': price_changes.get('change_7d', 0),
                    'change_1d': price_changes.get('change_1d', 0),
                    'change_90d': price_changes.get('change_90d', 0),
                    'is_fresh': stock.get('is_fresh', False),
                    
                    # Technical
                    'rsi': technical.get('rsi', 50),
                    'technical_score': technical.get('technical_score', 3.0),
                    'technical_outlook': technical.get('technical_outlook', 'neutral'),
                    
                    # Social
                    'social_score': social.get('composite_score', 0),
                    'social_strength': social.get('signal_strength', 'weak'),
                    'x_mentions': social.get('x_recent_mentions', 0),
                    'is_accelerating': social.get('is_accelerating', False),
                    'has_catalysts': social.get('has_catalysts', False),
                    'catalyst_count': social.get('catalyst_count', 0),
                    
                    # Float & Short
                    'float_millions': float_data.get('float_millions', 0),
                    'rotation_pct': float_data.get('rotation_pct', 0),
                    'parabolic_setup': float_data.get('parabolic_setup', False),
                    'short_percent': short_data.get('short_percent', 0),
                    'squeeze_potential': short_data.get('squeeze_potential', False),
                    
                    # ============ ENHANCED DATA ============
                    # Fundamentals
                    'revenue_millions': financials.get('revenue', 0) / 1_000_000 if financials else 0,
                    'gross_margin': financials.get('gross_margin', 0) if financials else 0,
                    'operating_margin': financials.get('operating_margin', 0) if financials else 0,
                    'fcf_margin': financials.get('fcf_margin', 0) if financials else 0,
                    'debt_to_equity': financials.get('debt_to_equity', 0) if financials else 0,
                    'fundamental_quality': quality_score,
                    'quality_rating': 'high' if quality_score > 0.7 else 'medium' if quality_score > 0.4 else 'low',
                    
                    # Valuation
                    'ev_to_ebitda': valuation.get('ev_to_ebitda', 0) if valuation else 0,
                    'price_to_fcf': valuation.get('price_to_fcf', 0) if valuation else 0,
                    'fcf_yield': valuation.get('fcf_yield', 0) if valuation else 0,
                    
                    # Catalysts
                    'catalyst_score': catalysts.get('catalyst_score', 0) if catalysts else 0,
                    'catalyst_summary': catalysts.get('catalyst_summary', 'None') if catalysts else 'None',
                    'news_sentiment': catalysts.get('recent_news_sentiment', 'neutral') if catalysts else 'neutral',
                    'positive_news_count': catalysts.get('positive_news_count', 0) if catalysts else 0,
                    'earnings_date': catalysts.get('upcoming_earnings', {}).get('earnings_date', 'Unknown') if catalysts else 'Unknown',
                    'days_until_earnings': catalysts.get('upcoming_earnings', {}).get('days_until_earnings', 999) if catalysts else 999,
                    
                    # ============ INSIDER DATA (NEW!) ============
                    'insider_score': insider.get('insider_score', 0),
                    'insider_boost': round(float(insider_boost), 2),
                    'has_insider_buying': insider.get('has_cluster_buying', False),
                    'insider_buy_count': insider.get('buy_count', 0),
                    'insider_sell_count': insider.get('sell_count', 0),
                    'insider_summary': f"{insider.get('buy_count', 0)} buys, {insider.get('sell_count', 0)} sells" if insider.get('buy_count', 0) > 0 or insider.get('sell_count', 0) > 0 else 'None',
                    
                    # Scoring breakdown
                    'composite_score': round(float(enhanced_score), 2),
                    'base_score': round(float(base_composite), 2),
                    'quality_boost': round(float(quality_boost), 2),
                    'catalyst_boost': round(float(catalyst_boost), 2),
                    
                    # Final recommendation
                    'rating': rating,
                    'conviction': conviction,
                    'position_size': ai_analysis.get('position_size', 'half'),
                    'stop_loss': ai_analysis.get('stop_loss', stock_data.get('price', 0) * 0.92),
                    'hold_period': ai_analysis.get('hold_period', '2-4 weeks'),
                }
                
                results.append(result)
            
            except Exception as e:
                print(f"   Error scoring {stock['ticker']}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        return results


def run_scan(custom_tickers: List[str] = None, top_k: int = None) -> pd.DataFrame:
    """
    Convenience function to run a scan.
    
    Args:
        custom_tickers: Optional list of tickers to scan
        top_k: Number of top candidates to return
    
    Returns:
        DataFrame with top candidates
    """
    scanner = SupabotScanner()
    return scanner.scan(custom_tickers=custom_tickers, top_k=top_k)


if __name__ == "__main__":
    # Test the scanner
    print("\nTesting Scanner with insider tracking...\n")
    
    test_tickers = ["PLTR", "SOFI", "NET", "NVDA", "RBLX"]
    
    results = run_scan(custom_tickers=test_tickers, top_k=3)
    
    if not results.empty:
        print("\n" + "="*70)
        print("TOP CANDIDATES:")
        print("="*70 + "\n")
        
        for i, (_, row) in enumerate(results.iterrows(), 1):
            insider_flag = " 👔💰" if row.get('has_insider_buying', False) else ""
            
            print(f"{i}. {row['ticker']}{insider_flag} - {row['rating']} (Score: {row['composite_score']}/5.0)")
            print(f"   Price: ${row['price']:.2f} | 7d: {row['change_7d']:+.1f}% | Fresh: {row['is_fresh']}")
            print(f"   Base: {row['base_score']:.2f} + Insider: +{row['insider_boost']:.2f}")
            print(f"   Insider: {row['insider_summary']}")
            print(f"   Position: {row['position_size']} | Stop: ${row['stop_loss']:.2f}")
            print()
    else:
        print("\n❌ No candidates found!")