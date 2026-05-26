"""echo-cli verify — fetch + validate a performance certificate."""
import click
from rich.console import Console
from rich.table import Table

from echo_quant.client.api import EchoClient

console = Console()

@click.command("verify")
@click.argument("cert_id")
@click.option("--api-url", envvar="ECHO_API_URL", default="https://api.echo.ai")
@click.option("--api-key", envvar="ECHO_API_KEY", default="")
def cmd(cert_id: str, api_url: str, api_key: str):
    """Fetch and display a performance certificate.

    In v4.4 this will also verify the ed25519 signature locally.
    """
    # Use a throwaway key if none provided — verify is public
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    import httpx
    r = httpx.get(f"{api_url}/v1/certs/{cert_id}", headers=headers, timeout=15.0)
    if r.status_code != 200:
        console.print(f"[red]Cert not found ({r.status_code}):[/red] {r.text[:200]}")
        raise SystemExit(1)
    cert = r.json()

    table = Table(show_header=False)
    table.add_column("Field", style="dim")
    table.add_column("Value")
    table.add_row("cert_id", cert.get("id", cert.get("cert_id", "")))
    table.add_row("model_id", cert.get("model_id", ""))
    table.add_row("version", cert.get("model_version", ""))
    table.add_row("signed_at", str(cert.get("signed_at", "")))
    table.add_row("dataset_hash", str(cert.get("dataset_hash", ""))[:32] + "…")
    table.add_row("source", cert.get("attestation", {}).get("source", "unknown"))
    console.print(table)

    metrics = cert.get("backtest_metrics") or {}
    if metrics:
        m_table = Table(title="Backtest metrics", show_header=True, header_style="bold")
        m_table.add_column("Metric")
        m_table.add_column("Value", justify="right")
        for k in ("sharpe", "sortino", "max_drawdown_pct", "win_rate", "n_trades"):
            if k in metrics:
                m_table.add_row(k, str(metrics[k]))
        console.print(m_table)

    console.print("\n[yellow]Signature verification: planned for v4.4 (verify-cert package).[/yellow]")
