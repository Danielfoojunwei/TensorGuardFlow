"""
WILDS Distribution Shift Benchmark Runner

Runs WILDS benchmarks to evaluate ID vs OOD generalization.
"""

import time
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from ..datasets import WILDSDatasetLoader
from ..models import get_backbone
from ..reporting.metrics import WILDSMetrics, evaluate_model, train_epoch
from ..reporting.artifacts import ArtifactManager


class WILDSRunner:
    """
    Runner for WILDS distribution shift benchmarks.
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
            print("[WILDS] Warning: Running on CPU. Benchmarks will be slower.")

    def run_all(
        self,
        seeds: List[int] = [42, 123, 456],
        epochs: int = 10,
        batch_size: int = 32,
        learning_rate: float = 0.0001,
        datasets_to_run: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Run all WILDS benchmarks.

        Returns:
            Tuple of (aggregated_metrics, per_run_results)
        """
        print("\n" + "=" * 70)
        print("WILDS DISTRIBUTION SHIFT BENCHMARK")
        print("=" * 70)

        if datasets_to_run is None:
            datasets_to_run = ["iwildcam"]  # Default to iWildCam

        all_results = []

        for dataset_name in datasets_to_run:
            print(f"\n[Dataset] {dataset_name}")

            for seed in seeds:
                print(f"\n  [Seed {seed}]")

                for method in ["frozen", "naive_finetune", "tensorguard"]:
                    print(f"\n    [Method] {method}")

                    try:
                        result = self._run_single(
                            dataset_name=dataset_name,
                            method=method,
                            seed=seed,
                            epochs=epochs,
                            batch_size=batch_size,
                            learning_rate=learning_rate,
                        )
                        all_results.append(result)

                    except Exception as e:
                        print(f"      Error: {e}")
                        all_results.append({
                            "suite": "wilds",
                            "dataset": dataset_name,
                            "method": method,
                            "seed": seed,
                            "error": str(e),
                            "metrics": {},
                        })

        aggregated = self._aggregate_results(all_results)
        return aggregated, all_results

    def _run_single(
        self,
        dataset_name: str,
        method: str,
        seed: int,
        epochs: int,
        batch_size: int,
        learning_rate: float,
    ) -> Dict[str, Any]:
        """Run a single WILDS benchmark configuration."""
        self._set_seed(seed)

        # Load dataset
        dataset = WILDSDatasetLoader(
            dataset_name=dataset_name,
            data_dir="./data/wilds",
            download=True,
            fail_on_mock=self.fail_on_mock,
        )

        # Create model
        num_classes = dataset.num_classes
        if method == "frozen":
            model = get_backbone("resnet18", num_classes=num_classes, pretrained=True, frozen=True)
        else:
            model = get_backbone("resnet18", num_classes=num_classes, pretrained=True, frozen=False)

        model = model.to(self.device)

        # Initialize metrics
        metrics = WILDSMetrics()

        # Get dataloaders
        train_loader = dataset.get_train_loader(batch_size=batch_size, num_workers=2)
        id_val_loader = dataset.get_id_val_loader(batch_size=batch_size, num_workers=2)
        ood_val_loader = dataset.get_ood_val_loader(batch_size=batch_size, num_workers=2)

        # Training
        print(f"      Training for {epochs} epochs...")
        train_start = time.time()

        if method == "frozen":
            params = model.classifier.parameters()
        else:
            params = model.parameters()

        optimizer = torch.optim.AdamW(params, lr=learning_rate, weight_decay=0.01)
        criterion = nn.CrossEntropyLoss()

        for epoch in range(epochs):
            model.train()
            epoch_loss = 0
            num_batches = 0

            for batch in train_loader:
                x, y = batch[0].to(self.device), batch[1].to(self.device)

                optimizer.zero_grad()
                outputs = model(x)
                loss = criterion(outputs, y)
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()
                num_batches += 1

            if (epoch + 1) % 2 == 0:
                print(f"        Epoch {epoch + 1}/{epochs} | Loss: {epoch_loss/num_batches:.4f}")

        metrics.train_time = time.time() - train_start

        # Evaluation
        print("      Evaluating...")
        eval_start = time.time()

        # ID accuracy
        id_acc, _ = evaluate_model(model, id_val_loader, self.device)
        metrics.record_id_accuracy(id_acc, len(dataset.id_val_data))

        # OOD accuracy
        ood_acc, _ = evaluate_model(model, ood_val_loader, self.device)
        metrics.record_ood_accuracy(ood_acc, len(dataset.ood_val_data))

        # Worst-group accuracy (if available)
        grouper = dataset.get_grouper()
        if grouper is not None:
            from ..datasets.wilds import compute_worst_group_accuracy
            worst_acc, per_group = compute_worst_group_accuracy(
                model, ood_val_loader, grouper, self.device
            )
            metrics.record_worst_group(worst_acc, per_group)

        metrics.eval_time = time.time() - eval_start

        print(f"      ID Acc: {id_acc*100:.2f}% | OOD Acc: {ood_acc*100:.2f}%")

        # Save artifacts
        self.artifacts.save_raw_artifact(
            "wilds", seed,
            f"{dataset_name}_{method}_metrics",
            metrics.to_dict(),
        )

        return {
            "suite": "wilds",
            "dataset": dataset_name,
            "method": method,
            "seed": seed,
            "metrics": metrics.to_dict(),
        }

    def _set_seed(self, seed: int):
        """Set random seeds."""
        torch.manual_seed(seed)
        np.random.seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False

    def _aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate results across seeds."""
        valid_results = [r for r in results if 'error' not in r]

        if not valid_results:
            return {"mean": {}, "std": {}}

        metrics_to_aggregate = ["id_accuracy", "ood_accuracy", "id_ood_gap", "worst_group_accuracy"]

        aggregated = {"mean": {}, "std": {}}
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
