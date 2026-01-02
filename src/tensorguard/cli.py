"""
TensorGuard CLI
Main entry point for the TensorGuard Unified Trust Fabric.
"""

import click
import logging
import sys
import os

# Ensure src is in path for scripts
sys.path.append(os.path.join(os.getcwd(), "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    # Importing from scripts as they are curated entrypoints
    from scripts.tgflow_ros2_ingest import main as ingest_main
    
    # Mocking sys.argv for the script
    sys.argv = ["tgflow_ros2_ingest.py", input_path, "--output-dir", output_dir]
    ingest_main()

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
    click.echo(f"✅ Compliance bundle exported: {result}")

if __name__ == "__main__":
    cli()
