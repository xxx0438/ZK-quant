"""echo-cli submit — upload artifact + kit, submit for review."""
import json
import os
from pathlib import Path

import click
from rich.console import Console

from echo_quant.cli.commands._loader import load_model_from_file
from echo_quant.client.api import EchoClient
from echo_quant.exceptions import ApiError

console = Console()

@click.command("submit")
@click.argument("model_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--dist", default="./dist", help="Directory containing packaged artifact + kit")
@click.option("--api-key", envvar="ECHO_API_KEY",
              help="Echo API key (or set ECHO_API_KEY)")
@click.option("--api-url", envvar="ECHO_API_URL", default="https://api.echo.ai")
def cmd(model_file: str, dist: str, api_key: str, api_url: str):
    """Submit a packaged model to the Echo marketplace."""
    if not api_key:
        console.print("[red]Missing API key.[/red] Set [cyan]ECHO_API_KEY[/cyan] or use --api-key.")
        raise SystemExit(1)

    src = Path(model_file).resolve()
    model = load_model_from_file(src)
    dist_dir = Path(dist).resolve()

    manifest_path = dist_dir / f"{model.model_id}.manifest.json"
    artifact_path = dist_dir / f"{model.model_id}.onnx"
    kit_path = dist_dir / f"{model.model_id}.kit.tar.gz"

    for p in (manifest_path, artifact_path, kit_path):
        if not p.exists():
            console.print(f"[red]Missing:[/red] {p}")
            console.print("Run [cyan]echo-cli package[/cyan] first.")
            raise SystemExit(1)

    manifest = json.loads(manifest_path.read_text())

    with EchoClient(api_key=api_key, base_url=api_url) as client:
        # 1. Get upload URL for artifact
        console.print("[dim]Requesting artifact upload URL...[/dim]")
        try:
            artifact_resp = client.get_upload_url(model.model_id, "artifact")
            kit_resp = client.get_upload_url(model.model_id, "kit")
        except ApiError as e:
            console.print(f"[red]API error:[/red] {e}")
            raise SystemExit(1)

        # 2. Upload both
        console.print(f"[dim]Uploading artifact ({_size_mb(artifact_path):.1f} MB)...[/dim]")
        client.upload_file(artifact_resp["upload_url"], artifact_path)
        console.print(f"[dim]Uploading kit ({_size_mb(kit_path):.1f} MB)...[/dim]")
        client.upload_file(kit_resp["upload_url"], kit_path)

        # 3. Submit
        console.print("[dim]Submitting for review...[/dim]")
        try:
            result = client.submit_model(
                proposed_model_id=model.model_id,
                name=getattr(model, "display_name", None) or model.model_id,
                description=model.description,
                category=model.category,
                artifact_url=f"s3://{artifact_resp['key']}",
                artifact_sha256=manifest["artifact_sha256"],
                backtest_kit_url=f"s3://{kit_resp['key']}",
                backtest_kit_sha256=manifest["kit_sha256"],
            )
        except ApiError as e:
            console.print(f"[red]Submit failed:[/red] {e}")
            raise SystemExit(1)

    console.print()
    console.print(f"[green]✓ Submitted![/green] ID: [cyan]{result['submission_id']}[/cyan]")
    console.print(f"  Status: [yellow]{result['status']}[/yellow]")
    console.print(f"\nTrack at: https://echo.ai/quant/dashboard")

def _size_mb(p: Path) -> float:
    return p.stat().st_size / (1024 * 1024)
