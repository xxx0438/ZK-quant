"""echo-cli validate — interface + schema checks."""
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from echo_quant.cli.commands._loader import load_model_from_file
from echo_quant.exceptions import ValidationError
from echo_quant.model import Inputs, Signal

console = Console()

@click.command("validate")
@click.argument("model_file", type=click.Path(exists=True, dir_okay=False))
def cmd(model_file: str):
    """Validate a model's interface, schema, and determinism."""
    path = Path(model_file)
    checks = []

    try:
        model = load_model_from_file(path)
        checks.append(("Import + instantiate", True, ""))
    except Exception as e:
        console.print(f"[red]✗ Import failed:[/red] {e}")
        raise SystemExit(1)

    # Required attrs
    for attr in ("model_id", "asset", "version"):
        val = getattr(model, attr, None)
        ok = bool(val)
        checks.append((f"Has {attr}", ok, str(val)))

    # Schema sanity
    try:
        from echo_quant.cli.commands._fixtures import sample_inputs
        ins = sample_inputs(model.asset)
        out = model.predict(ins)
        ok = isinstance(out, Signal)
        checks.append(("predict() returns Signal", ok, type(out).__name__))
    except Exception as e:
        checks.append(("predict() runs", False, str(e)))

    # Determinism
    try:
        from echo_quant.cli.commands._fixtures import sample_inputs
        ins = sample_inputs(model.asset)
        out1 = model.predict(ins)
        out2 = model.predict(ins)
        ok = out1.model_dump() == out2.model_dump()
        checks.append((
            "Deterministic (same input → same output)",
            ok,
            "" if ok else "Outputs differ on second call",
        ))
    except Exception as e:
        checks.append(("Determinism check", False, str(e)))

    # required_data declared correctly
    try:
        rd = model.required_data()
        ok = isinstance(rd, list) and all(isinstance(x, str) for x in rd)
        checks.append(("required_data() returns list[str]", ok, str(rd)))
    except Exception as e:
        checks.append(("required_data()", False, str(e)))

    # Print results
    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Result")
    table.add_column("Detail", overflow="fold")

    n_failed = 0
    for name, ok, detail in checks:
        mark = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(name, mark, detail)
        if not ok:
            n_failed += 1
    console.print(table)

    if n_failed:
        console.print(f"\n[red]{n_failed} check(s) failed.[/red]")
        raise SystemExit(1)
    console.print(f"\n[green]All checks passed for {model.model_id} v{model.version}.[/green]")
