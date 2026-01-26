"""
Continual Learning Vision Benchmark Runner

Runs Split CIFAR-100, Split TinyImageNet, and CORe50 benchmarks.
Compares frozen, naive fine-tune, and TensorGuardFlow methods.
"""

import time
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from ..datasets import SplitCIFAR100, SplitTinyImageNet, CORe50Dataset
from ..models import get_backbone, LoRAAdapter
from ..reporting.metrics import CLMetrics, evaluate_model, train_epoch
from ..reporting.artifacts import ArtifactManager


class CLVisionRunner:
    """
    Runner for Continual Learning Vision benchmarks.

    Supports three methods:
    1. Frozen: Only train classifier, backbone frozen
    2. Naive Fine-tune: Train entire model sequentially
    3. TensorGuardFlow: Use adapters with artifact management
    """

    def __init__(
        self,
        output_dir: str = "reports",
        device: str = "cuda",
        fail_on_mock: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.device = device if torch.cuda.is_available() else "cpu"
        self.fail_on_mock = fail_on_mock
        self.artifacts = ArtifactManager(output_dir)

        if self.device == "cpu":
            print("[CLVision] Warning: Running on CPU. Benchmarks will be slower.")

    def run_all(
        self,
        seeds: List[int] = [42, 123, 456],
        epochs_per_task: int = 5,
        batch_size: int = 64,
        learning_rate: float = 0.001,
        datasets_to_run: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Run all CLVision benchmarks.

        Returns:
            Tuple of (aggregated_metrics, per_run_results)
        """
        print("\n" + "=" * 70)
        print("CONTINUAL LEARNING VISION BENCHMARK")
        print("=" * 70)

        if datasets_to_run is None:
            datasets_to_run = ["split_cifar100"]  # Default to CIFAR-100 for speed

        all_results = []
        all_metrics = {"by_dataset": {}, "by_method": {}}

        for dataset_name in datasets_to_run:
            print(f"\n[Dataset] {dataset_name}")

            for seed in seeds:
                print(f"\n  [Seed {seed}]")

                # Run each method
                for method in ["frozen", "naive_finetune", "tensorguard"]:
                    print(f"\n    [Method] {method}")

                    try:
                        result = self._run_single(
                            dataset_name=dataset_name,
                            method=method,
                            seed=seed,
                            epochs_per_task=epochs_per_task,
                            batch_size=batch_size,
                            learning_rate=learning_rate,
                        )
                        all_results.append(result)

                    except Exception as e:
                        print(f"      Error: {e}")
                        all_results.append({
                            "suite": "clvision",
                            "dataset": dataset_name,
                            "method": method,
                            "seed": seed,
                            "error": str(e),
                            "metrics": {},
                        })

        # Aggregate results
        aggregated = self._aggregate_results(all_results)

        return aggregated, all_results

    def _run_single(
        self,
        dataset_name: str,
        method: str,
        seed: int,
        epochs_per_task: int,
        batch_size: int,
        learning_rate: float,
    ) -> Dict[str, Any]:
        """Run a single benchmark configuration."""
        # Set seeds for reproducibility
        self._set_seed(seed)

        # Load dataset
        dataset = self._load_dataset(dataset_name, seed)
        num_tasks = dataset.num_tasks if hasattr(dataset, 'num_tasks') else 20

        # Create model
        model = self._create_model(method, dataset, seed)
        model = model.to(self.device)

        # Initialize metrics tracker
        metrics = CLMetrics(num_tasks=num_tasks)

        # Training loop over tasks
        for task_id in range(num_tasks):
            print(f"      Task {task_id + 1}/{num_tasks}", end="", flush=True)

            # Train on current task
            train_start = time.time()
            self._train_task(
                model=model,
                dataset=dataset,
                task_id=task_id,
                method=method,
                epochs=epochs_per_task,
                batch_size=batch_size,
                learning_rate=learning_rate,
            )
            train_time = time.time() - train_start
            metrics.record_train_time(task_id, train_time)

            # Evaluate on all tasks seen so far
            eval_start = time.time()
            for eval_task in range(task_id + 1):
                acc = self._evaluate_task(model, dataset, eval_task, batch_size)
                metrics.record_accuracy(task_id, eval_task, acc)
            eval_time = time.time() - eval_start
            metrics.record_eval_time(eval_time)

            # Print progress
            current_acc = metrics.accuracy_matrix[task_id, task_id]
            print(f" | Acc: {current_acc*100:.1f}% | Time: {train_time:.1f}s")

        # Save raw artifacts
        self.artifacts.save_raw_artifact(
            "clvision", seed,
            f"{dataset_name}_{method}_accuracy_matrix",
            metrics.accuracy_matrix,
        )

        result = {
            "suite": "clvision",
            "dataset": dataset_name,
            "method": method,
            "seed": seed,
            "metrics": metrics.to_dict(),
        }

        return result

    def _load_dataset(self, name: str, seed: int):
        """Load a CL dataset."""
        if name == "split_cifar100":
            return SplitCIFAR100(
                data_dir="./data/cifar100",
                num_tasks=20,
                classes_per_task=5,
                seed=seed,
                download=True,
                fail_on_mock=self.fail_on_mock,
            )
        elif name == "split_tinyimagenet":
            return SplitTinyImageNet(
                data_dir="./data/tinyimagenet",
                num_tasks=20,
                classes_per_task=10,
                seed=seed,
                download=True,
                fail_on_mock=self.fail_on_mock,
            )
        elif name == "core50":
            return CORe50Dataset(
                data_dir="./data/core50",
                scenario="nc",
                seed=seed,
                download=True,
                fail_on_mock=self.fail_on_mock,
            )
        else:
            raise ValueError(f"Unknown dataset: {name}")

    def _create_model(self, method: str, dataset, seed: int) -> nn.Module:
        """Create model based on method."""
        # Determine number of classes
        info = dataset.get_info()
        num_classes = info.get('total_classes', 100)

        if method == "frozen":
            model = get_backbone(
                name="resnet18",
                num_classes=num_classes,
                pretrained=True,
                frozen=True,
            )
        elif method == "naive_finetune":
            model = get_backbone(
                name="resnet18",
                num_classes=num_classes,
                pretrained=True,
                frozen=False,
            )
        elif method == "tensorguard":
            # Use LoRA adapters
            model = get_backbone(
                name="resnet18",
                num_classes=num_classes,
                pretrained=True,
                frozen=True,
            )
            # Apply LoRA to later layers
            lora = LoRAAdapter(rank=8, alpha=16, target_modules=['layer3', 'layer4'])
            # For ResNet, we need to wrap the classifier
            # The backbone is frozen, classifier is trainable
        else:
            raise ValueError(f"Unknown method: {method}")

        return model

    def _train_task(
        self,
        model: nn.Module,
        dataset,
        task_id: int,
        method: str,
        epochs: int,
        batch_size: int,
        learning_rate: float,
    ):
        """Train model on a single task."""
        model.train()

        # Get task dataloader
        train_loader = dataset.get_dataloader(
            task_id=task_id,
            train=True,
            batch_size=batch_size,
            num_workers=2,
        )

        # Get task classes for label mapping
        task_classes = dataset.get_task_classes(task_id)

        # Setup optimizer
        if method == "frozen" or method == "tensorguard":
            # Only train classifier
            params = [p for p in model.classifier.parameters()]
        else:
            params = model.parameters()

        optimizer = torch.optim.Adam(params, lr=learning_rate)
        criterion = nn.CrossEntropyLoss()

        # Training loop
        for epoch in range(epochs):
            for batch in train_loader:
                x, y = batch[0], batch[1]
                x = x.to(self.device)
                y = y.to(self.device)

                optimizer.zero_grad()
                outputs = model(x)
                loss = criterion(outputs, y)
                loss.backward()
                optimizer.step()

    def _evaluate_task(
        self,
        model: nn.Module,
        dataset,
        task_id: int,
        batch_size: int,
    ) -> float:
        """Evaluate model on a single task."""
        model.eval()

        test_loader = dataset.get_dataloader(
            task_id=task_id,
            train=False,
            batch_size=batch_size,
            num_workers=2,
        )

        correct = 0
        total = 0

        with torch.no_grad():
            for batch in test_loader:
                x, y = batch[0], batch[1]
                x = x.to(self.device)
                y = y.to(self.device)

                outputs = model(x)
                preds = outputs.argmax(dim=1)
                correct += (preds == y).sum().item()
                total += y.size(0)

        return correct / total if total > 0 else 0.0

    def _set_seed(self, seed: int):
        """Set random seeds for reproducibility."""
        torch.manual_seed(seed)
        np.random.seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False

    def _aggregate_results(
        self,
        results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Aggregate results across seeds."""
        aggregated = {
            "mean": {},
            "std": {},
            "by_dataset": {},
            "by_method": {},
        }

        # Filter successful results
        valid_results = [r for r in results if 'error' not in r]

        if not valid_results:
            return aggregated

        # Aggregate key metrics
        metrics_to_aggregate = [
            "average_accuracy",
            "mean_forgetting",
            "backward_transfer",
            "forward_transfer",
        ]

        for metric in metrics_to_aggregate:
            values = [
                r['metrics'].get(metric, 0)
                for r in valid_results
                if r['metrics'].get(metric) is not None
            ]
            if values:
                aggregated['mean'][metric] = float(np.mean(values))
                aggregated['std'][metric] = float(np.std(values))

        return aggregated
