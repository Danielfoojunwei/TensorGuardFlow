"""
Report Renderer for Empirical Benchmarks

Generates human-readable Markdown reports from benchmark results.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np


class ReportRenderer:
    """
    Renders benchmark results as Markdown reports.
    """

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)

    def render(
        self,
        manifest: Dict[str, Any],
        metrics: Dict[str, Any],
        results: List[Dict[str, Any]],
    ) -> str:
        """Render complete benchmark report."""
        sections = [
            self._render_header(manifest),
            self._render_summary(metrics),
            self._render_system_info(manifest),
            self._render_clvision_results(metrics, results),
            self._render_wilds_results(metrics, results),
            self._render_peft_results(metrics, results),
            self._render_reproducibility(manifest),
            self._render_footer(manifest),
        ]

        report = "\n\n".join(filter(None, sections))

        # Save report
        report_path = self.output_dir / "benchmark_report.md"
        with open(report_path, 'w') as f:
            f.write(report)

        print(f"[Report] Saved benchmark report: {report_path}")
        return report

    def _render_header(self, manifest: Dict[str, Any]) -> str:
        """Render report header."""
        suite = manifest.get('suite', 'all')
        timestamp = manifest.get('timestamp', datetime.now().isoformat())
        run_id = manifest.get('run_id', 'unknown')

        return f"""# TensorGuardFlow Empirical Benchmark Report

**Generated:** {timestamp}
**Run ID:** `{run_id}`
**Suite:** {suite}
**Status:** {"PASS" if manifest.get('success', False) else "FAIL"}

---

This report contains empirically measured benchmark results using real public datasets.
All results are reproducible by running `make bench`.

> **Note:** These benchmarks use downloaded datasets (CIFAR-100, TinyImageNet, CORe50, WILDS).
> No simulations or mock data are used."""

    def _render_summary(self, metrics: Dict[str, Any]) -> str:
        """Render executive summary."""
        cl_metrics = metrics.get('clvision', {})
        wilds_metrics = metrics.get('wilds', {})
        peft_metrics = metrics.get('peft', {})

        lines = ["## Executive Summary", ""]

        if cl_metrics:
            avg_acc = cl_metrics.get('mean', {}).get('average_accuracy', 0)
            forgetting = cl_metrics.get('mean', {}).get('mean_forgetting', 0)
            bwt = cl_metrics.get('mean', {}).get('backward_transfer', 0)

            lines.append("### Continual Learning (CLVision)")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Average Accuracy | **{avg_acc*100:.2f}%** |")
            lines.append(f"| Mean Forgetting | {forgetting*100:.2f}% |")
            lines.append(f"| Backward Transfer | {bwt*100:+.2f}% |")
            lines.append("")

        if wilds_metrics:
            id_acc = wilds_metrics.get('mean', {}).get('id_accuracy', 0)
            ood_acc = wilds_metrics.get('mean', {}).get('ood_accuracy', 0)
            gap = wilds_metrics.get('mean', {}).get('id_ood_gap', 0)

            lines.append("### Distribution Shift (WILDS)")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| ID Accuracy | **{id_acc*100:.2f}%** |")
            lines.append(f"| OOD Accuracy | {ood_acc*100:.2f}% |")
            lines.append(f"| ID-OOD Gap | {gap*100:.2f}% |")
            lines.append("")

        if peft_metrics:
            throughput = peft_metrics.get('mean', {}).get('examples_per_second', 0)
            memory = peft_metrics.get('mean', {}).get('peak_memory_mb', 0)
            adapter_kb = peft_metrics.get('mean', {}).get('adapter_size_kb', 0)

            lines.append("### PEFT/LoRA Performance")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Throughput | **{throughput:.1f} examples/sec** |")
            lines.append(f"| Peak Memory | {memory:.1f} MB |")
            lines.append(f"| Adapter Size | {adapter_kb:.1f} KB |")
            lines.append("")

        return "\n".join(lines)

    def _render_system_info(self, manifest: Dict[str, Any]) -> str:
        """Render system information."""
        sys_info = manifest.get('system_info', {})

        lines = [
            "## System Information",
            "",
            "| Component | Value |",
            "|-----------|-------|",
            f"| Platform | {sys_info.get('platform', 'Unknown')} {sys_info.get('platform_version', '')} |",
            f"| Python | {sys_info.get('python_version', 'Unknown').split()[0]} |",
            f"| PyTorch | {sys_info.get('torch_version', 'N/A')} |",
            f"| CPU | {sys_info.get('cpu', 'Unknown')} |",
            f"| CPU Cores | {sys_info.get('cpu_count', 'Unknown')} |",
            f"| RAM | {sys_info.get('ram_gb', 0):.1f} GB |",
        ]

        if sys_info.get('gpu_available'):
            lines.append(f"| GPU | {sys_info.get('gpu_name', 'Unknown')} |")
            lines.append(f"| GPU Memory | {sys_info.get('gpu_memory_gb', 0):.1f} GB |")
            lines.append(f"| CUDA | {sys_info.get('cuda_version', 'Unknown')} |")

        return "\n".join(lines)

    def _render_clvision_results(
        self,
        metrics: Dict[str, Any],
        results: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Render CLVision detailed results."""
        cl_results = [r for r in results if r.get('suite') == 'clvision']
        if not cl_results:
            return None

        lines = [
            "## Continual Learning Results (CLVision)",
            "",
            "### Datasets",
            "- **Split CIFAR-100**: 20 tasks, 5 classes per task",
            "- **Split TinyImageNet**: 20 tasks, 10 classes per task",
            "- **CORe50**: 10 tasks (NC scenario), 5 classes per task",
            "",
            "### Methods Compared",
            "1. **Frozen**: Backbone frozen, only classifier trained",
            "2. **Naive Fine-tune**: Sequential fine-tuning (no CL strategy)",
            "3. **TensorGuardFlow**: Adapter-based with artifact management",
            "",
            "### Results by Dataset and Method",
            "",
        ]

        # Group by dataset
        datasets = set(r.get('dataset', 'unknown') for r in cl_results)

        for dataset in sorted(datasets):
            dataset_results = [r for r in cl_results if r.get('dataset') == dataset]

            lines.append(f"#### {dataset}")
            lines.append("")
            lines.append("| Method | Avg Acc | Forgetting | BWT | FWT |")
            lines.append("|--------|---------|------------|-----|-----|")

            for r in dataset_results:
                method = r.get('method', 'unknown')
                m = r.get('metrics', {})
                avg_acc = m.get('average_accuracy', 0)
                forgetting = m.get('mean_forgetting', 0)
                bwt = m.get('backward_transfer', 0)
                fwt = m.get('forward_transfer', 0)

                lines.append(
                    f"| {method} | {avg_acc*100:.2f}% | {forgetting*100:.2f}% | "
                    f"{bwt*100:+.2f}% | {fwt*100:+.2f}% |"
                )

            lines.append("")

        # Add accuracy matrix visualization hint
        lines.append("### Accuracy Matrices")
        lines.append("")
        lines.append("Raw accuracy matrices are saved in `reports/raw/clvision/seed_*/accuracy_matrix.npy`")

        return "\n".join(lines)

    def _render_wilds_results(
        self,
        metrics: Dict[str, Any],
        results: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Render WILDS detailed results."""
        wilds_results = [r for r in results if r.get('suite') == 'wilds']
        if not wilds_results:
            return None

        lines = [
            "## Distribution Shift Results (WILDS)",
            "",
            "### Datasets",
            "- **iWildCam**: Wildlife camera trap images (182 species)",
            "- **Camelyon17**: Medical imaging (tumor detection)",
            "",
            "### Results",
            "",
            "| Dataset | Method | ID Acc | OOD Acc | Gap | Worst-Group |",
            "|---------|--------|--------|---------|-----|-------------|",
        ]

        for r in wilds_results:
            dataset = r.get('dataset', 'unknown')
            method = r.get('method', 'unknown')
            m = r.get('metrics', {})

            id_acc = m.get('id_accuracy', 0)
            ood_acc = m.get('ood_accuracy', 0)
            gap = m.get('id_ood_gap', 0)
            worst = m.get('worst_group_accuracy', 0)

            lines.append(
                f"| {dataset} | {method} | {id_acc*100:.2f}% | {ood_acc*100:.2f}% | "
                f"{gap*100:.2f}% | {worst*100:.2f}% |"
            )

        return "\n".join(lines)

    def _render_peft_results(
        self,
        metrics: Dict[str, Any],
        results: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Render PEFT detailed results."""
        peft_results = [r for r in results if r.get('suite') == 'peft']
        if not peft_results:
            return None

        lines = [
            "## PEFT/LoRA Performance Results",
            "",
            "### Configuration",
            "- **LoRA Rank**: 8",
            "- **LoRA Alpha**: 16",
            "- **Target Modules**: layer3, layer4",
            "",
            "### Throughput and Memory",
            "",
            "| Method | Trainable Params | Throughput | Peak Memory | Adapter Size | P50 Latency |",
            "|--------|------------------|------------|-------------|--------------|-------------|",
        ]

        for r in peft_results:
            method = r.get('method', 'unknown')
            m = r.get('metrics', {})

            trainable = m.get('trainable_params', 0)
            throughput = m.get('examples_per_second', 0)
            memory = m.get('peak_memory_mb', 0)
            adapter_kb = m.get('adapter_size_kb', 0)
            latency = m.get('inference_latency_p50_ms', 0)

            trainable_str = f"{trainable/1e6:.2f}M" if trainable > 1e6 else f"{trainable/1e3:.1f}K"

            lines.append(
                f"| {method} | {trainable_str} | {throughput:.1f} ex/s | "
                f"{memory:.1f} MB | {adapter_kb:.1f} KB | {latency:.2f} ms |"
            )

        return "\n".join(lines)

    def _render_reproducibility(self, manifest: Dict[str, Any]) -> str:
        """Render reproducibility section."""
        git_commit = manifest.get('git_commit', 'N/A')
        git_branch = manifest.get('git_branch', 'N/A')
        git_dirty = manifest.get('git_dirty', False)
        seeds = manifest.get('seeds', [42, 123, 456])

        lines = [
            "## Reproducibility",
            "",
            "### Git State",
            f"- **Commit**: `{git_commit}`",
            f"- **Branch**: `{git_branch}`",
            f"- **Dirty**: {git_dirty}",
            "",
            "### Random Seeds",
            f"Seeds used: `{seeds}`",
            "",
            "### How to Reproduce",
            "```bash",
            "# Clone repository at the same commit",
            f"git checkout {git_commit}",
            "",
            "# Install dependencies",
            "pip install -e '.[bench]'",
            "",
            "# Run benchmarks",
            "make bench",
            "",
            "# Or run with specific seeds",
            f"python -m benchmarks_empirical.run --suite all --seeds {' '.join(map(str, seeds))}",
            "```",
            "",
            "### Dependencies",
            "Full pip freeze is available in `run_manifest.json`.",
        ]

        return "\n".join(lines)

    def _render_footer(self, manifest: Dict[str, Any]) -> str:
        """Render report footer."""
        duration = manifest.get('duration_seconds', 0)
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)

        return f"""---

## Benchmark Metadata

- **Total Duration**: {hours}h {minutes}m {seconds}s
- **Run ID**: `{manifest.get('run_id', 'unknown')}`
- **Generated By**: TensorGuardFlow Empirical Benchmark Framework v1.0.0

---

*This report was automatically generated. For questions, see the [documentation](../docs/BENCHMARK_CLAIMS_AUDIT.md).*"""
