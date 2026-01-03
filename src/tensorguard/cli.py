"""
TensorGuard CLI
Main entry point for the TensorGuard Unified Trust Fabric.
"""

import click
import logging
import sys
import importlib.util
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_project_root() -> Path:
    """Get the project root directory."""
    # cli.py is at src/tensorguard/cli.py, so project root is 3 levels up
    return Path(__file__).resolve().parent.parent.parent


def _load_script_module(script_name: str):
    """
    Dynamically load a module from the scripts directory.

    Args:
        script_name: Name of the script file (without .py extension)

    Returns:
        Loaded module object
    """
    project_root = _get_project_root()
    script_path = project_root / "scripts" / f"{script_name}.py"

    if not script_path.exists():
        raise ImportError(f"Script not found: {script_path}")

    spec = importlib.util.spec_from_file_location(script_name, script_path)
    module = importlib.util.module_from_spec(spec)

    # Add src to path temporarily for script imports
    src_path = str(project_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    spec.loader.exec_module(module)
    return module


@click.group()
def cli():
    """TensorGuard Trust Fabric CLI."""
    pass


# === DAEMON ===
@cli.command()
def agent():
    """Start the Unified Edge Daemon (Identity, Network, ML)."""
    from .agent.daemon import main as agent_main
    agent_main()


# === PLATFORM ===
@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to listen on")
def server(host, port):
    """Start the Control Plane Server (Platform + UI)."""
    import uvicorn
    uvicorn.run("tensorguard.platform.main:app", host=host, port=port, reload=False)


# === ROBOTICS TOOLS ===
@cli.command()
@click.argument("input_path")
@click.option("--output-dir", default="./dataset", help="Output directory")
def ingest(input_path, output_dir):
    """Ingest a rosbag2 or MCAP file."""
    # Load the script dynamically using robust path resolution
    ingest_module = _load_script_module("tgflow_ros2_ingest")

    # Set sys.argv for the script's argument parser
    sys.argv = ["tgflow_ros2_ingest.py", input_path, "--output-dir", output_dir]
    ingest_module.main()


# === SECURE PACKAGE (TGSP) ===
@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("subcommand_args", nargs=-1, type=click.UNPROCESSED)
def pkg(subcommand_args):
    """TGSP Package Management (Create, Verify, Decrypt)."""
    from .tgsp.cli import main as tgsp_main
    sys.argv = ["tgsp"] + list(subcommand_args)
    tgsp_main()


# === BENCHMARK ===
@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("subcommand_args", nargs=-1, type=click.UNPROCESSED)
def bench(subcommand_args):
    """Run TensorGuard Benchmarks."""
    from .bench.cli import main as bench_main
    sys.argv = ["bench"] + list(subcommand_args)
    bench_main()


# === COMPLIANCE ===
@cli.command("compliance")
@click.option("--evidence-dir", default="./artifacts/evidence", help="Directory containing .tge.json files")
@click.option("--output", "-o", default="./compliance_bundle.zip", help="Output ZIP file path")
def compliance_export(evidence_dir, output):
    """Export compliance evidence bundle for ISO 27001 / NIST CSF audit."""
    from .compliance.export import export_compliance_bundle
    result = export_compliance_bundle(evidence_dir, output)
    click.echo(f"Compliance bundle exported: {result}")


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
