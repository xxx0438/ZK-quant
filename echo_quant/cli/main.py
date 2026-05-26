"""echo-cli — Echo Protocol Quant SDK command-line tool."""
import logging
import sys

import click
from rich.console import Console
from rich.logging import RichHandler

from echo_quant.cli.commands import backtest, init, package, submit, validate, verify

console = Console()

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=False, show_path=False)],
)

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="echo-quant")
def cli():
    """Echo Protocol Quant SDK.

    Build, test, and ship quantitative trading models to the Echo marketplace.

    Typical workflow:

        \b
        echo-cli init my-model              # scaffold
        # ... edit my_model.py ...
        echo-cli validate ./my_model.py
        echo-cli backtest ./my_model.py
        echo-cli package ./my_model.py
        echo-cli submit ./my_model.py
    """
    pass

cli.add_command(init.cmd)
cli.add_command(validate.cmd)
cli.add_command(backtest.cmd)
cli.add_command(package.cmd)
cli.add_command(submit.cmd)
cli.add_command(verify.cmd)

if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        console.print("[red]Interrupted.[/red]")
        sys.exit(130)
