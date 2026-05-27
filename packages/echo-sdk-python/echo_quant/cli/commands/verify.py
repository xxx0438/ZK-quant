"""echo-cli verify — full verification using echo-verify."""
import json
import sys

import click
import httpx
from rich.console import Console

console = Console()

@click.command("verify")
@click.argument("cert_id_or_path")
@click.option("--api-url", envvar="ECHO_API_URL", default="https://api.echo.ai")
@click.option("--check-reproducibility", is_flag=True,
              help="Download artifact + kit and verify hashes")
def cmd(cert_id_or_path: str, api_url: str, check_reproducibility: bool):
    """Verify an Echo cert by ID or local file path."""
    try:
        from echo_verify import CertVerifier
    except ImportError:
        console.print("[red]Install with: pip install echo-verify[/red]")
        sys.exit(1)

    # Load cert
    cert: dict
    if cert_id_or_path.startswith("cert_"):
        r = httpx.get(f"{api_url}/v1/certs/{cert_id_or_path}", timeout=15.0)
        if r.status_code != 200:
            console.print(f"[red]Cert lookup failed ({r.status_code})[/red]")
            sys.exit(1)
        cert = r.json()
    else:
        with open(cert_id_or_path) as f:
            cert = json.load(f)

    # Verify
    result = CertVerifier().verify(cert)

    if result.ok:
        console.print(f"[green]✓ Cert {result.cert_id} verified[/green]")
        console.print(f"  Signed by: [cyan]{result.issuer_key_id}[/cyan]")
        if result.warnings:
            for w in result.warnings:
                console.print(f"  [yellow]⚠ {w}[/yellow]")
    else:
        console.print(f"[red]✗ Verification failed[/red]")
        console.print(json.dumps(result.to_dict(), indent=2))
        sys.exit(2)

    if check_reproducibility:
        console.print("\n[dim]Reproducibility check coming in v0.4.4[/dim]")
        # TODO v0.4.4: download artifact + kit + replay backtest
