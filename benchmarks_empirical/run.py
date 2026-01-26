"""
Empirical Benchmark Runner CLI

Main entry point for running reproducible benchmarks on real public datasets.

Usage:
    python -m benchmarks_empirical.run --suite all --seeds 3 --output_dir reports
    python -m benchmarks_empirical.run --suite clvision --seeds 42 123 456
    python -m benchmarks_empirical.run --suite wilds --device cuda
    python -m benchmarks_empirical.run --suite peft --fail_on_mock true
"""

import argparse
import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any

from .runners import CLVisionRunner, WILDSRunner, PEFTRunner
from .reporting.artifacts import ArtifactManager, RunManifest
from .reporting.render_report import ReportRenderer


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="TensorGuardFlow Empirical Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all benchmarks with 3 seeds
    python -m benchmarks_empirical.run --suite all --seeds 3

    # Run only continual learning benchmarks
    python -m benchmarks_empirical.run --suite clvision --seeds 42 123 456

    # Run fast mode for development
    python -m benchmarks_empirical.run --suite all --fast

    # Specify output directory
    python -m benchmarks_empirical.run --suite all --output_dir reports
        """,
    )

    parser.add_argument(
        "--suite",
        type=str,
        choices=["clvision", "wilds", "peft", "all"],
        default="all",
        help="Benchmark suite to run",
    )

    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[42, 123, 456],
        help="Random seeds for reproducibility (default: 42 123 456)",
    )

    parser.add_argument(
        "--device",
        type=str,
        choices=["cuda", "cpu", "auto"],
        default="auto",
        help="Device to run on (default: auto)",
    )

    parser.add_argument(
        "--output_dir",
        type=str,
        default="reports",
        help="Output directory for results (default: reports)",
    )

    parser.add_argument(
        "--fail_on_mock",
        type=str,
        choices=["true", "false"],
        default="true",
        help="Fail if mock/simulated data is detected (default: true)",
    )

    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode: 1 seed, reduced epochs for quick testing",
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=None,
        help="Override epochs per task (default: suite-specific)",
    )

    parser.add_argument(
        "--batch_size",
        type=int,
        default=None,
        help="Override batch size (default: suite-specific)",
    )

    return parser.parse_args()


def detect_device(requested: str) -> str:
    """Detect available device."""
    if requested == "auto":
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"
    return requested


def run_benchmark(args) -> bool:
    """
    Run the complete benchmark suite.

    Returns:
        True if successful, False otherwise.
    """
    print("\n" + "=" * 70)
    print("TENSORGUARDFLOW EMPIRICAL BENCHMARK FRAMEWORK")
    print("=" * 70)
    print(f"Suite: {args.suite}")
    print(f"Seeds: {args.seeds}")
    print(f"Device: {args.device}")
    print(f"Output: {args.output_dir}")
    print(f"Fail on mock: {args.fail_on_mock}")
    print("=" * 70 + "\n")

    # Fast mode adjustments
    if args.fast:
        print("[FAST MODE] Reducing seeds and epochs for quick testing")
        args.seeds = [42]
        if args.epochs is None:
            args.epochs = 2
        if args.batch_size is None:
            args.batch_size = 128

    # Default values if not overridden
    epochs_clvision = args.epochs or 5
    epochs_wilds = args.epochs or 10
    epochs_peft = args.epochs or 10
    batch_size = args.batch_size or 64

    # Detect device
    device = detect_device(args.device)
    print(f"[Device] Using: {device}")

    # Initialize artifact manager
    artifacts = ArtifactManager(args.output_dir)

    # Create run manifest
    config = {
        "suite": args.suite,
        "seeds": args.seeds,
        "device": device,
        "epochs_clvision": epochs_clvision,
        "epochs_wilds": epochs_wilds,
        "epochs_peft": epochs_peft,
        "batch_size": batch_size,
        "fast_mode": args.fast,
    }
    manifest = RunManifest.create(args.suite, config, args.seeds)

    # Track all results
    all_metrics = {}
    all_results = []
    fail_on_mock = args.fail_on_mock.lower() == "true"

    start_time = time.time()
    success = True
    error_message = None

    try:
        # Run CLVision benchmarks
        if args.suite in ["clvision", "all"]:
            runner = CLVisionRunner(
                output_dir=args.output_dir,
                device=device,
                fail_on_mock=fail_on_mock,
            )
            cl_metrics, cl_results = runner.run_all(
                seeds=args.seeds,
                epochs_per_task=epochs_clvision,
                batch_size=batch_size,
                datasets_to_run=["split_cifar100"],
            )
            all_metrics["clvision"] = cl_metrics
            all_results.extend(cl_results)

        # Run WILDS benchmarks
        if args.suite in ["wilds", "all"]:
            runner = WILDSRunner(
                output_dir=args.output_dir,
                device=device,
                fail_on_mock=fail_on_mock,
            )
            wilds_metrics, wilds_results = runner.run_all(
                seeds=args.seeds,
                epochs=epochs_wilds,
                batch_size=batch_size,
                datasets_to_run=["iwildcam"],
            )
            all_metrics["wilds"] = wilds_metrics
            all_results.extend(wilds_results)

        # Run PEFT benchmarks
        if args.suite in ["peft", "all"]:
            runner = PEFTRunner(
                output_dir=args.output_dir,
                device=device,
                fail_on_mock=fail_on_mock,
            )
            peft_metrics, peft_results = runner.run_all(
                seeds=args.seeds,
                epochs=epochs_peft,
                batch_size=batch_size,
            )
            all_metrics["peft"] = peft_metrics
            all_results.extend(peft_results)

    except Exception as e:
        success = False
        error_message = str(e)
        print(f"\n[ERROR] Benchmark failed: {e}")
        import traceback
        traceback.print_exc()

    # Finalize manifest
    duration = time.time() - start_time
    manifest.finalize(duration, success, error_message)

    # Save artifacts
    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)

    artifacts.save_manifest(manifest)
    artifacts.save_metrics(all_metrics)
    artifacts.save_results_csv(all_results)

    # Render report
    renderer = ReportRenderer(args.output_dir)
    renderer.render(manifest.to_dict(), all_metrics, all_results)

    # Verify outputs
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    outputs_exist = artifacts.verify_outputs_exist()
    if outputs_exist:
        print("[OK] All required outputs generated successfully")
    else:
        print("[FAIL] Some outputs are missing")
        success = False

    # Summary
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    print(f"Duration: {duration/60:.1f} minutes")
    print(f"Status: {'PASS' if success else 'FAIL'}")
    print(f"\nOutputs:")
    print(f"  - {args.output_dir}/run_manifest.json")
    print(f"  - {args.output_dir}/metrics.json")
    print(f"  - {args.output_dir}/benchmark_results.csv")
    print(f"  - {args.output_dir}/benchmark_report.md")

    return success


def main():
    """Main entry point."""
    args = parse_args()

    # Ensure device is set
    if args.device == "auto":
        args.device = detect_device("auto")

    success = run_benchmark(args)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
