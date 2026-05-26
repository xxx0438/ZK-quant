"""echo-cli package — produce artifact + reproducibility kit."""
import json
from pathlib import Path

import click
from rich.console import Console

from echo_quant.backtest.runner import run_backtest
from echo_quant.backtest.dataset import CanonicalDataset
from echo_quant.cli.commands._fixtures import sample_inputs
from echo_quant.cli.commands._loader import load_model_from_file
from echo_quant.packaging.packager import package_model

console = Console()

@click.command("package")
@click.argument("model_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", default="./dist", help="Output directory")
@click.option("--dataset", "-d", default=None, help="Dataset to run a fresh backtest on")
@click.option("--skip-backtest", is_flag=True, help="Skip backtest step")
def cmd(model_file: str, output: str, dataset: str, skip_backtest: bool):
    """Package a model into artifact.onnx + kit.tar.gz."""
    src = Path(model_file).resolve()
    model = load_model_from_file(src)
    out_dir = Path(output).resolve()

    # Optional fresh backtest
    backtest_result = None
    if not skip_backtest:
        if not dataset:
            default = Path.home() / ".echo" / "datasets" / f"{model.asset.lower()}-default"
            if default.exists():
                dataset = str(default)
        if dataset:
            console.print("[dim]Running backtest for kit inclusion...[/dim]")
            ds = CanonicalDataset.load(dataset)
            backtest_result = run_backtest(model, ds).to_dict()
        else:
            console.print("[yellow]No dataset; kit will not include backtest_result.json.[/yellow]")

    console.print("[dim]Exporting to ONNX...[/dim]")
    pkg = package_model(
        model=model,
        source_path=src,
        sample_inputs=sample_inputs(model.asset),
        output_dir=out_dir,
        backtest_result=backtest_result,
    )

    console.print()
    console.print(f"[green]✓[/green] Artifact: [cyan]{pkg.artifact_path}[/cyan]")
    console.print(f"  sha256: [dim]{pkg.artifact_sha256}[/dim]")
    console.print(f"[green]✓[/green] Kit:      [cyan]{pkg.kit_path}[/cyan]")
    console.print(f"  sha256: [dim]{pkg.kit_sha256}[/dim]")

    manifest_path = out_dir / f"{model.model_id}.manifest.json"
    manifest_path.write_text(json.dumps(pkg.metadata, indent=2))
    console.print(f"[green]✓[/green] Manifest: [cyan]{manifest_path}[/cyan]")
