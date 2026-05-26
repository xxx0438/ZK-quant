"""echo-cli dataset — pull / list canonical datasets."""
import json
import os
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

console = Console()

@click.group("dataset")
def cmd():
    """Manage canonical datasets for backtesting."""
    pass

@cmd.command("list")
@click.option("--api-url", envvar="ECHO_API_URL", default="https://api.echo.ai")
def list_cmd(api_url: str):
    """List available canonical datasets."""
    r = httpx.get(f"{api_url}/v1/datasets", timeout=10.0)
    r.raise_for_status()
    items = r.json().get("datasets", [])

    t = Table(show_header=True, header_style="bold")
    t.add_column("Name")
    t.add_column("Asset")
    t.add_column("Period")
    t.add_column("Snapshots", justify="right")
    t.add_column("Size", justify="right")
    for d in items:
        t.add_row(
            d["name"], d["asset"],
            f"{d['period_start_date']} → {d['period_end_date']}",
            str(d.get("n_snapshots", "?")),
            d.get("size_human", "?"),
        )
    console.print(t)

@cmd.command("pull")
@click.argument("dataset_name")
@click.option("--out", default=None, help="Output dir (defaults to ~/.echo/datasets/<name>)")
@click.option("--api-url", envvar="ECHO_API_URL", default="https://api.echo.ai")
def pull_cmd(dataset_name: str, out: str, api_url: str):
    """Download a canonical dataset locally."""
    out_dir = Path(out) if out else Path.home() / ".echo" / "datasets" / dataset_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Get download URL
    r = httpx.get(f"{api_url}/v1/datasets/{dataset_name}", timeout=10.0)
    r.raise_for_status()
    meta = r.json()
    download_url = meta["download_url"]

    console.print(f"[dim]Downloading {dataset_name}...[/dim]")
    with httpx.stream("GET", download_url, timeout=600.0) as resp:
        resp.raise_for_status()
        tarball = out_dir / "_dl.tar.gz"
        with tarball.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)

    # Untar
    import tarfile
    with tarfile.open(tarball) as t:
        t.extractall(out_dir)
    tarball.unlink()
    console.print(f"[green]✓[/green] Pulled to {out_dir}")
