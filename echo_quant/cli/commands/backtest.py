"""echo-cli backtest — run a local backtest."""
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from echo_quant.backtest.dataset import CanonicalDataset
from echo_quant.backtest.runner import run_backtest
from echo_quant.cli.commands._loader import load_model_from_file

console = Console()

@click.command("backtest")
@click.argument("model_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--dataset", "-d", required=False,
    help="Path to canonical dataset directory (defaults to ~/.echo/datasets/<asset>-default)",
)
@click.option("--slippage-bps", default=5.0, help="Per-side slippage in bps")
@click.option("--fee-bps", default=3.5, help="Round-trip fees in bps")
@click.option("--min-edge-bps", default=2.0, help="Skip trades below this predicted edge")
@click.option("--save", type=click.Path(), default=None, help="Save full backtest_result.json")
@click.option("--max-predictions", type=int, default=None)
def cmd(model_file: str, dataset: str, slippage_bps: float, fee_bps: float,
        min_edge_bps: float, save: str, max_predictions: int):
    """Run a local backtest against a canonical dataset."""
    model = load_model_from_file(Path(model_file))

    if not dataset:
        default = Path.home() / ".echo" / "datasets" / f"{model.asset.lower()}-default"
        if not default.exists():
            console.print(f"[red]No dataset specified and no default at {default}.[/red]")
            console.print("Hint: [cyan]echo-cli dataset pull eth-default[/cyan]")
            raise SystemExit(1)
        dataset = str(default)

    ds = CanonicalDataset.load(dataset)
    console.print(f"[dim]Dataset:[/dim] {ds.name} ({ds.asset}) hash={ds.dataset_hash[:12]}…")

    result = run_backtest(
        model, ds,
        slippage_bps=slippage_bps,
        fee_bps=fee_bps,
        min_edge_bps=min_edge_bps,
        max_predictions=max_predictions,
    )

    m = result.metrics
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Predictions", str(result.n_predictions))
    table.add_row("Trades", str(result.n_trades))
    table.add_row("Sharpe", _color(m.get("sharpe", 0), good=1.0))
    table.add_row("Sortino", str(m.get("sortino")))
    table.add_row("Win rate", f"{m.get('win_rate', 0) * 100:.1f}%")
    table.add_row("Avg PnL (bps)", str(m.get("avg_pnl_bps")))
    table.add_row("Total PnL (bps)", str(m.get("total_pnl_bps")))
    table.add_row("Max DD (%)", _color(m.get("max_drawdown_pct", 0) * 100, good=-20, lower=True))
    table.add_row("Profit factor", str(m.get("profit_factor")))
    table.add_row("Runtime", f"{result.runtime_ms} ms")
    console.print(table)

    # Marketplace gate check
    sharpe = m.get("sharpe", 0) or 0
    dd_pct = m.get("max_drawdown_pct", 0) or 0
    if sharpe >= 1.0 and dd_pct <= 0.20:
        console.print("\n[green]✓ Passes auto-list thresholds (Sharpe ≥ 1.0, DD ≤ 20%).[/green]")
    else:
        console.print("\n[yellow]⚠ Below auto-list thresholds. Will require manual review.[/yellow]")

    if save:
        result.save(save)
        console.print(f"\nSaved to [cyan]{save}[/cyan]")

def _color(val: float, good: float = 0, lower: bool = False) -> str:
    """Color a number green/red based on threshold."""
    if lower:
        return f"[green]{val:.2f}[/green]" if val >= good else f"[red]{val:.2f}[/red]"
    return f"[green]{val:.2f}[/green]" if val >= good else f"[yellow]{val:.2f}[/yellow]"
