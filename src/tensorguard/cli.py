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
    """Start the Unified Edge Daemon (Identity, Network, ROS2 Logs)."""
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

@cli.command()
@click.option("--port", default=8080, help="Port to listen on")
def sidecar(port):
    """Start the Enablement Sidecar API."""
    import uvicorn
    uvicorn.run("api.enablement_service:app", host="0.0.0.0", port=port, reload=False)

# === ROBOTICS TOOLS ===
@cli.command()
@click.argument("input_path")
@click.option("--output-dir", default="./dataset", help="Output directory")
def ingest(input_path, output_dir):
    """Ingest a rosbag2 or MCAP file."""
    # We can invoke the script logic directly or via subprocess
    # Invoking script logic directly is cleaner if possible, or exposing main
    from ..scripts.tgflow_ros2_ingest import main as ingest_main
    
    # Mocking sys.argv for the script
    sys.argv = ["tgflow_ros2_ingest.py", input_path, "--output-dir", output_dir]
    ingest_main()

@cli.command()
@click.argument("dataset_dir")
def slice(dataset_dir):
    """Slice a normalized dataset."""
    from ..scripts.tgflow_slice import main as slice_main
    sys.argv = ["tgflow_slice.py", dataset_dir]
    slice_main()

@cli.command()
@click.argument("input_path")
def run_job(input_path):
    """Run a Trust Pipeline Job (Local)."""
    from .enablement.pipelines.run_job import run_pipeline, RunContext
    from .enablement.external_platform.adapters.filesystem import FilesystemAdapter
    from .enablement.governance.policy import GovernanceEngine
    import uuid
    
    ctx = RunContext(
        run_id=str(uuid.uuid4())[:8],
        robot_id="cli_runner",
        job_type="local_run",
        config={"input_path": input_path}
    )
    adapter = FilesystemAdapter("./runs")
    gov = GovernanceEngine({"dp_budget_limit": 100.0})
    
    run_pipeline(adapter, ctx, gov)

if __name__ == "__main__":
    cli()
