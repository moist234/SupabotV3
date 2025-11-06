"""
Supabot V2 - Main Runner with Beautiful Terminal UI
Production entry point with Rich terminal interface.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from pathlib import Path
import pandas as pd

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.progress import Progress

from scanner import run_scan
from config import SCANNER_CONFIG, ENABLE_AI_ANALYSIS, get_config_summary

console = Console()

def display_candidates_table(df: pd.DataFrame) -> Table:
    """Create beautiful table for candidates."""
    
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title="🎯 TOP CANDIDATES",
        title_style="bold magenta"
    )
    
    table.add_column("Rank", style="dim", width=4)
    table.add_column("Ticker", style="cyan bold", width=8)
    table.add_column("Price", justify="right", style="green", width=10)
    table.add_column("Rating", justify="center", width=12)
    table.add_column("Score", justify="right", style="yellow", width=8)
    table.add_column("7d%", justify="right", width=8)
    table.add_column("Signals", justify="center", width=15)
    
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        # Build signal flags
        flags = []
        if row.get('is_fresh', False):
            flags.append("✨")
        if row.get('parabolic_setup', False):
            flags.append("💥")
        if row.get('is_accelerating', False):
            flags.append("📈")
        if row.get('has_catalysts', False):
            flags.append("📰")
        
        signal_str = " ".join(flags) if flags else "—"
        
        # Color code 7d change
        chg_7d = row.get('change_7d', 0)
        if chg_7d > 15:
            chg_str = f"[red]+{chg_7d:.1f}%[/red]"
        elif chg_7d > 7:
            chg_str = f"[yellow]+{chg_7d:.1f}%[/yellow]"
        elif chg_7d >= 0:
            chg_str = f"[green]+{chg_7d:.1f}%[/green]"
        else:
            chg_str = f"[white]{chg_7d:.1f}%[/white]"
        
        # Color code rating
        rating = row.get('rating', 'HOLD')
        conviction = row.get('conviction', 'LOW')
        
        if rating == 'STRONG_BUY':
            rating_str = f"[bold green]{rating}[/bold green]"
        elif rating == 'BUY':
            rating_str = f"[green]{rating}[/green]"
        elif rating == 'HOLD':
            rating_str = f"[yellow]{rating}[/yellow]"
        else:
            rating_str = f"[red]{rating}[/red]"
        
        # Add conviction indicator
        if conviction == 'HIGH':
            rating_str += " 🔥"
        elif conviction == 'MEDIUM':
            rating_str += " ⚡"
        
        table.add_row(
            str(idx),
            row['ticker'],
            f"${row['price']:.2f}",
            rating_str,
            f"{row['composite_score']:.2f}",
            chg_str,
            signal_str
        )
    
    return table


def display_details(df: pd.DataFrame):
    """Display detailed breakdown for each candidate with ENHANCED data."""
    
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
        console.print(f"[bold white]#{idx}. {row['ticker']} - {row['rating']}[/bold white]")
        console.print(f"[bold cyan]{'='*70}[/bold cyan]")
        
        # Basic info
        console.print(f"\n[bold]📊 Overview:[/bold]")
        console.print(f"  Price: [green]${row['price']:.2f}[/green]")
        console.print(f"  Market Cap: ${row['market_cap']/1e9:.2f}B")
        console.print(f"  Sector: {row['sector']}")
        console.print(f"  Composite Score: [yellow]{row['composite_score']:.2f}/5.0[/yellow]")
        
        # ============ ENHANCED: Score Breakdown ============
        if 'base_score' in row and pd.notna(row.get('base_score')):
            console.print(f"\n[bold]🔢 Score Breakdown:[/bold]")
            console.print(f"  Base Score: {row['base_score']:.2f}")
            console.print(f"  + Quality Boost: +{row.get('quality_boost', 0):.2f}")
            console.print(f"  + Catalyst Boost: +{row.get('catalyst_boost', 0):.2f}")
            console.print(f"  [bold]= Final: {row['composite_score']:.2f}/5.0[/bold]")
        
        # Component scores
        console.print(f"\n[bold]🎯 Component Scores:[/bold]")
        console.print(f"  Technical: {row.get('technical_score', 0):.1f}/5.0 ({row.get('technical_outlook', 'neutral')})")
        console.print(f"  Social: {row.get('social_score', 0):.2f} ({row.get('social_strength', 'weak')})")
        
        # ============ ENHANCED: Fundamentals ============
        if row.get('revenue_millions', 0) > 0:
            console.print(f"\n[bold]💰 Fundamentals:[/bold]")
            console.print(f"  Revenue: ${row['revenue_millions']:.0f}M")
            console.print(f"  Gross Margin: {row.get('gross_margin', 0):.1f}%")
            console.print(f"  Operating Margin: {row.get('operating_margin', 0):.1f}%")
            console.print(f"  FCF Margin: {row.get('fcf_margin', 0):.1f}%")
            console.print(f"  Debt/Equity: {row.get('debt_to_equity', 0):.2f}")
            
            quality = row.get('fundamental_quality', 0)
            quality_rating = row.get('quality_rating', 'unknown')
            quality_color = "green" if quality > 0.7 else "yellow" if quality > 0.4 else "red"
            console.print(f"  Quality Score: [{quality_color}]{quality:.2f}/1.0 ({quality_rating})[/{quality_color}]")
        
        # ============ ENHANCED: Valuation ============
        if row.get('ev_to_ebitda', 0) > 0:
            console.print(f"\n[bold]📈 Valuation:[/bold]")
            
            ev_ebitda = row.get('ev_to_ebitda', 0)
            ev_color = "green" if ev_ebitda < 15 else "yellow" if ev_ebitda < 25 else "red"
            console.print(f"  EV/EBITDA: [{ev_color}]{ev_ebitda:.1f}x[/{ev_color}]")
            
            console.print(f"  P/FCF: {row.get('price_to_fcf', 0):.1f}x")
            console.print(f"  FCF Yield: {row.get('fcf_yield', 0):.2f}%")
            console.print(f"  P/E: {row.get('pe_ratio', 0):.1f}")
        
        # ============ ENHANCED: Catalysts & News ============
        catalyst_score = row.get('catalyst_score', 0)
        if catalyst_score > 0:
            console.print(f"\n[bold]🎪 Catalysts:[/bold]")
            
            catalyst_color = "green" if catalyst_score > 0.6 else "yellow" if catalyst_score > 0.3 else "white"
            console.print(f"  Catalyst Score: [{catalyst_color}]{catalyst_score:.2f}/1.0[/{catalyst_color}]")
            console.print(f"  Summary: {row.get('catalyst_summary', 'None')}")
            
            news_sentiment = row.get('news_sentiment', 'neutral')
            news_color = "green" if news_sentiment == 'positive' else "red" if news_sentiment == 'negative' else "yellow"
            console.print(f"  News Sentiment: [{news_color}]{news_sentiment.upper()}[/{news_color}]")
            
            pos_news = row.get('positive_news_count', 0)
            if pos_news > 0:
                console.print(f"  Positive Articles: {pos_news}")
            
            days_to_earnings = row.get('days_until_earnings', 999)
            if days_to_earnings < 30:
                earnings_date = row.get('earnings_date', 'Unknown')
                earnings_color = "yellow" if days_to_earnings < 7 else "white"
                console.print(f"  Next Earnings: [{earnings_color}]{earnings_date} ({days_to_earnings} days)[/{earnings_color}]")
        
        # Price action
        console.print(f"\n[bold]📈 Price Action:[/bold]")
        console.print(f"  1-day: {row.get('change_1d', 0):+.1f}%")
        console.print(f"  7-day: {row.get('change_7d', 0):+.1f}%")
        console.print(f"  90-day: {row.get('change_90d', 0):+.1f}%")
        console.print(f"  RSI: {row.get('rsi', 50):.1f}")
        
        # Special signals
        signals = []
        if row.get('is_fresh'):
            signals.append("✨ Fresh signal (best entry)")
        if row.get('is_accelerating'):
            signals.append("📈 Buzz accelerating")
        if row.get('has_catalysts'):
            signals.append(f"📰 {row.get('catalyst_count', 0)} social catalysts")
        if row.get('parabolic_setup'):
            signals.append("💥 Parabolic setup")
        if row.get('fundamental_quality', 0) > 0.7:
            signals.append("💎 High quality fundamentals")
        if row.get('ev_to_ebitda', 0) > 0 and row.get('ev_to_ebitda', 0) < 12:
            signals.append("💰 Undervalued (EV/EBITDA)")
        
        if signals:
            console.print(f"\n[bold]🎪 Special Signals:[/bold]")
            for signal in signals:
                console.print(f"  {signal}")
        
        # Risk management
        console.print(f"\n[bold]🛡️  Risk Management:[/bold]")
        
        conviction_color = "green" if row.get('conviction') == 'HIGH' else "yellow" if row.get('conviction') == 'MEDIUM' else "red"
        console.print(f"  Conviction: [{conviction_color}]{row.get('conviction', 'UNKNOWN')}[/{conviction_color}]")
        
        console.print(f"  Position Size: {row.get('position_size', 'unknown')}")
        console.print(f"  Stop Loss: ${row.get('stop_loss', 0):.2f} ({((row.get('stop_loss', 0) / row.get('price', 1) - 1) * 100):.1f}%)")
        console.print(f"  Hold Period: {row.get('hold_period', 'unknown')}")

def display_legend():
    """Display signal legend and action guide."""
    
    console.print("\n" + "="*70)
    console.print("[bold cyan]📖 SIGNAL LEGEND[/bold cyan]")
    console.print("="*70)
    
    console.print("\n[bold]Symbols:[/bold]")
    console.print("  ✨ = [green]FRESH[/green] - Getting buzz but hasn't moved yet (BEST ENTRY)")
    console.print("  📈 = [yellow]ACCELERATING[/yellow] - Buzz increasing rapidly")
    console.print("  📰 = [blue]CATALYSTS[/blue] - Real news/earnings driving interest")
    console.print("  💥 = [magenta]PARABOLIC[/magenta] - Low float + high rotation")
    console.print("  🚀 = [red]SQUEEZE[/red] - High short interest (>20%)")
    console.print("  👔💰 = [green]INSIDER BUYING[/green] - Cluster buying detected")
    
    console.print("\n[bold]Rating Guide:[/bold]")
    console.print("  [bold green]STRONG_BUY 🔥[/bold green] = High conviction, 10% position")
    console.print("  [green]BUY ⚡[/green] = Good setup, 5% position")
    console.print("  [yellow]HOLD[/yellow] = Okay setup, watch it")
    console.print("  [red]AVOID[/red] = Skip this trade")
    
    console.print("\n" + "="*70 + "\n")

def save_results(df: pd.DataFrame) -> str:
    """Save results to CSV."""
    
    if df.empty:
        return None
    
    # Create outputs directory
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Save with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"supabot_v2_scan_{timestamp}.csv"
    filepath = output_dir / filename
    
    df.to_csv(filepath, index=False)
    
    return str(filepath)


def main():
    """Main entry point."""
    
    # Show config summary
    console.print(Panel.fit(
        "[bold cyan]SUPABOT V2[/bold cyan]\n" +
        f"Quality-First AI Scanner\n" +
        f"Scanning {SCANNER_CONFIG.scan_limit} stocks for top {SCANNER_CONFIG.top_k}",
        border_style="cyan"
    ))
    
    # Run scan
    start_time = datetime.now()
    
    results = run_scan(top_k=SCANNER_CONFIG.top_k)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # Display results
    if not results.empty:
        # Main table
        console.print("\n")
        table = display_candidates_table(results)
        console.print(table)
        
        # Detailed breakdown
        console.print("\n[bold cyan]📋 DETAILED ANALYSIS[/bold cyan]")
        display_details(results)
        
        # Legend
        display_legend()
        
        # Save results
        filepath = save_results(results)
        if filepath:
            console.print(f"[bold green]✓ Results saved to:[/bold green] [cyan]{filepath}[/cyan]")
        
        # Summary stats
        fresh_count = len(results[results['is_fresh'] == True])
        high_conviction = len(results[results['conviction'] == 'HIGH'])
        
        console.print(f"\n[bold]📊 Summary:[/bold]")
        console.print(f"  • {len(results)} candidates found")
        console.print(f"  • {fresh_count} fresh signals")
        console.print(f"  • {high_conviction} high conviction plays")
        console.print(f"  • Scan time: {elapsed:.1f}s")

        console.print(f"\n[bold]🔔 Sending Discord notifications...[/bold]")
        from discord_notify import send_scan_results, send_high_conviction_alert
        
        send_scan_results(results, {'scanned': SCANNER_CONFIG.scan_limit})
        for _, row in results.iterrows():
            if row.get('conviction') == 'HIGH':
                send_high_conviction_alert(row)
    
    else:
        console.print("\n[bold red]❌ No candidates found this scan.[/bold red]")
        console.print("\n[yellow]💡 Try:[/yellow]")
        console.print(f"\n[bold]🔔 Sending Discord notification...[/bold]")
        from discord_notify import send_scan_results
        send_scan_results(pd.DataFrame(), {'scanned': SCANNER_CONFIG.scan_limit})
        console.print("  • Lower min_composite_score in config.py")
        console.print("  • Expand universe in data/social_signals.py")
        console.print("  • Check if market is quiet today")
    
    console.print("\n[bold green]✓ Scan complete![/bold green]\n")



if __name__ == "__main__":
    main()