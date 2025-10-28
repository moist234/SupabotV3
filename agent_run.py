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
        if row.get('squeeze_potential', False):
            flags.append("🚀")
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
    """Display detailed breakdown for each candidate."""
    
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
        
        # Scores breakdown
        console.print(f"\n[bold]🎯 Score Breakdown:[/bold]")
        console.print(f"  Technical: {row.get('technical_score', 0):.1f}/5.0 ({row.get('technical_outlook', 'neutral')})")
        console.print(f"  Social: {row.get('social_score', 0):.2f} ({row.get('social_strength', 'weak')})")
        
        # Price action
        console.print(f"\n[bold]📈 Price Action:[/bold]")
        console.print(f"  1-day: {row.get('change_1d', 0):+.1f}%")
        console.print(f"  7-day: {row.get('change_7d', 0):+.1f}%")
        console.print(f"  90-day: {row.get('change_90d', 0):+.1f}%")
        console.print(f"  RSI: {row.get('rsi', 50):.1f}")
        
        # Signals
        signals = []
        if row.get('is_fresh'):
            signals.append("✨ Fresh (best entry)")
        if row.get('is_accelerating'):
            signals.append("📈 Buzz accelerating")
        if row.get('has_catalysts'):
            signals.append("📰 Has catalysts")
        if row.get('parabolic_setup'):
            signals.append("💥 Parabolic setup")
        if row.get('squeeze_potential'):
            signals.append("🚀 Squeeze potential")
        
        if signals:
            console.print(f"\n[bold]🎪 Special Signals:[/bold]")
            for signal in signals:
                console.print(f"  {signal}")
        
        # Risk management
        console.print(f"\n[bold]🛡️  Risk Management:[/bold]")
        console.print(f"  Conviction: [yellow]{row.get('conviction', 'UNKNOWN')}[/yellow]")
        console.print(f"  Position Size: {row.get('position_size', 'unknown')}")
        console.print(f"  Stop Loss: ${row.get('stop_loss', 0):.2f}")
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
    
    console.print("\n[bold]Rating Guide:[/bold]")
    console.print("  [bold green]STRONG_BUY 🔥[/bold green] = High conviction, full position")
    console.print("  [green]BUY ⚡[/green] = Good setup, half position")
    console.print("  [yellow]HOLD[/yellow] = Wait for better entry")
    console.print("  [red]AVOID[/red] = Skip this trade")
    
    console.print("\n[bold]Best Combinations:[/bold]")
    console.print("  ✨ 📰 📈 = [bold green]JACKPOT[/bold green] - Fresh + Catalysts + Accelerating")
    console.print("  ✨ 📈     = [bold green]EXCELLENT[/bold green] - Early entry with momentum")
    console.print("  ✨ 📰     = [green]STRONG[/green] - Fresh with real catalyst")
    console.print("  📈 💥     = [yellow]VOLATILE[/yellow] - High risk/reward")
    
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