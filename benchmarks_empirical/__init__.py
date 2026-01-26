"""
Empirical Benchmark Framework for TensorGuardFlow

This package provides reproducible, empirical benchmarks using real public datasets.
NO simulations, NO mock data, NO hardcoded metrics.

Suites:
- clvision: Continual Learning (Split CIFAR-100, Split TinyImageNet, CORe50)
- wilds: Distribution Shift (WILDS datasets)
- peft: Parameter-Efficient Fine-Tuning (LoRA/adapter benchmarks)

Usage:
    python -m benchmarks_empirical.run --suite all --seeds 3 --output_dir reports
"""

__version__ = "1.0.0"
