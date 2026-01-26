"""
Canonical Metrics for Empirical Benchmarks

Implements standard continual learning, distribution shift, and PEFT metrics.
All computations are deterministic and reproducible.
"""

import numpy as np
import torch
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import time


@dataclass
class CLMetrics:
    """
    Continual Learning Metrics.

    Tracks accuracy matrices and computes standard CL metrics:
    - Average Accuracy (AA)
    - Forgetting (F)
    - Backward Transfer (BWT)
    - Forward Transfer (FWT)

    Reference:
        Lopez-Paz, D., & Ranzato, M. (2017). Gradient Episodic Memory for
        Continual Learning. NeurIPS 2017.
    """

    num_tasks: int
    accuracy_matrix: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))
    task_train_times: List[float] = field(default_factory=list)
    task_eval_times: List[float] = field(default_factory=list)

    def __post_init__(self):
        if self.accuracy_matrix.size == 0:
            # accuracy_matrix[i, j] = accuracy on task j after training on task i
            self.accuracy_matrix = np.zeros((self.num_tasks, self.num_tasks))

    def record_accuracy(self, after_task: int, on_task: int, accuracy: float):
        """Record accuracy on task after training."""
        self.accuracy_matrix[after_task, on_task] = accuracy

    def record_train_time(self, task_id: int, duration: float):
        """Record training time for a task."""
        while len(self.task_train_times) <= task_id:
            self.task_train_times.append(0.0)
        self.task_train_times[task_id] = duration

    def record_eval_time(self, duration: float):
        """Record evaluation time."""
        self.task_eval_times.append(duration)

    def average_accuracy(self) -> float:
        """
        Average Accuracy after training on all tasks.

        AA = (1/T) * sum_{j=1}^{T} a_{T,j}
        """
        return float(np.mean(self.accuracy_matrix[-1, :]))

    def forgetting(self) -> Tuple[float, List[float]]:
        """
        Compute forgetting per task and mean forgetting.

        F_j = max_{i < T} a_{i,j} - a_{T,j}
        F = (1/(T-1)) * sum_{j=1}^{T-1} F_j
        """
        per_task_forgetting = []
        for j in range(self.num_tasks - 1):
            # Best accuracy on task j before final task
            best_before = np.max(self.accuracy_matrix[:self.num_tasks-1, j])
            # Final accuracy on task j
            final_acc = self.accuracy_matrix[-1, j]
            forgetting = max(0, best_before - final_acc)
            per_task_forgetting.append(forgetting)

        mean_forgetting = float(np.mean(per_task_forgetting)) if per_task_forgetting else 0.0
        return mean_forgetting, per_task_forgetting

    def backward_transfer(self) -> float:
        """
        Backward Transfer (BWT).

        BWT = (1/(T-1)) * sum_{i=1}^{T-1} (a_{T,i} - a_{i,i})

        Negative BWT indicates forgetting.
        """
        bwt_values = []
        for i in range(self.num_tasks - 1):
            bwt = self.accuracy_matrix[-1, i] - self.accuracy_matrix[i, i]
            bwt_values.append(bwt)

        return float(np.mean(bwt_values)) if bwt_values else 0.0

    def forward_transfer(self, random_baseline: Optional[np.ndarray] = None) -> float:
        """
        Forward Transfer (FWT).

        FWT = (1/(T-1)) * sum_{i=2}^{T} (a_{i-1,i} - b_i)

        where b_i is the random baseline accuracy on task i.
        """
        if random_baseline is None:
            # Use 1/num_classes as random baseline
            random_baseline = np.ones(self.num_tasks) * 0.01

        fwt_values = []
        for i in range(1, self.num_tasks):
            # Accuracy on task i after training on task i-1 (zero-shot)
            zero_shot_acc = self.accuracy_matrix[i-1, i]
            fwt = zero_shot_acc - random_baseline[i]
            fwt_values.append(fwt)

        return float(np.mean(fwt_values)) if fwt_values else 0.0

    def intransigence(self) -> float:
        """
        Intransigence: inability to learn new tasks.

        I = (1/T) * sum_{i=1}^{T} (a*_i - a_{i,i})

        where a*_i is the reference (joint training) accuracy.
        """
        # Without reference, we use a proxy: 1.0 - final accuracy
        intrans = 1.0 - np.mean(np.diag(self.accuracy_matrix))
        return float(intrans)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        mean_forgetting, per_task_forgetting = self.forgetting()

        return {
            "average_accuracy": self.average_accuracy(),
            "mean_forgetting": mean_forgetting,
            "per_task_forgetting": per_task_forgetting,
            "backward_transfer": self.backward_transfer(),
            "forward_transfer": self.forward_transfer(),
            "intransigence": self.intransigence(),
            "accuracy_matrix": self.accuracy_matrix.tolist(),
            "total_train_time": sum(self.task_train_times),
            "mean_train_time_per_task": np.mean(self.task_train_times) if self.task_train_times else 0,
            "total_eval_time": sum(self.task_eval_times),
        }


@dataclass
class WILDSMetrics:
    """
    Distribution Shift Metrics for WILDS benchmarks.

    Tracks:
    - In-Distribution (ID) accuracy
    - Out-of-Distribution (OOD) accuracy
    - Worst-group accuracy
    """

    id_accuracy: float = 0.0
    ood_accuracy: float = 0.0
    worst_group_accuracy: float = 0.0
    per_group_accuracy: Dict[int, float] = field(default_factory=dict)
    train_time: float = 0.0
    eval_time: float = 0.0
    id_samples: int = 0
    ood_samples: int = 0

    def record_id_accuracy(self, accuracy: float, num_samples: int):
        """Record in-distribution accuracy."""
        self.id_accuracy = accuracy
        self.id_samples = num_samples

    def record_ood_accuracy(self, accuracy: float, num_samples: int):
        """Record out-of-distribution accuracy."""
        self.ood_accuracy = accuracy
        self.ood_samples = num_samples

    def record_worst_group(self, worst_acc: float, per_group: Dict[int, float]):
        """Record worst-group accuracy."""
        self.worst_group_accuracy = worst_acc
        self.per_group_accuracy = per_group

    def id_ood_gap(self) -> float:
        """Compute ID-OOD accuracy gap."""
        return self.id_accuracy - self.ood_accuracy

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "id_accuracy": self.id_accuracy,
            "ood_accuracy": self.ood_accuracy,
            "id_ood_gap": self.id_ood_gap(),
            "worst_group_accuracy": self.worst_group_accuracy,
            "per_group_accuracy": self.per_group_accuracy,
            "train_time": self.train_time,
            "eval_time": self.eval_time,
            "id_samples": self.id_samples,
            "ood_samples": self.ood_samples,
        }


@dataclass
class PEFTMetrics:
    """
    Parameter-Efficient Fine-Tuning Metrics.

    Tracks:
    - Training throughput (steps/sec, examples/sec)
    - Memory usage (peak GPU memory)
    - Adapter size
    - Final accuracy
    """

    total_params: int = 0
    trainable_params: int = 0
    adapter_size_bytes: int = 0
    peak_memory_mb: float = 0.0
    steps_per_second: float = 0.0
    examples_per_second: float = 0.0
    train_time: float = 0.0
    final_accuracy: float = 0.0
    inference_latency_p50: float = 0.0
    inference_latency_p95: float = 0.0
    inference_latencies: List[float] = field(default_factory=list)

    def record_params(self, total: int, trainable: int, adapter_bytes: int):
        """Record parameter counts."""
        self.total_params = total
        self.trainable_params = trainable
        self.adapter_size_bytes = adapter_bytes

    def record_throughput(self, steps: int, examples: int, duration: float):
        """Record training throughput."""
        self.train_time = duration
        self.steps_per_second = steps / duration if duration > 0 else 0
        self.examples_per_second = examples / duration if duration > 0 else 0

    def record_memory(self, peak_mb: float):
        """Record peak memory usage."""
        self.peak_memory_mb = peak_mb

    def record_inference_latency(self, latency: float):
        """Record a single inference latency measurement."""
        self.inference_latencies.append(latency)

    def compute_latency_percentiles(self):
        """Compute latency percentiles."""
        if self.inference_latencies:
            self.inference_latency_p50 = float(np.percentile(self.inference_latencies, 50))
            self.inference_latency_p95 = float(np.percentile(self.inference_latencies, 95))

    def param_efficiency(self) -> float:
        """Compute parameter efficiency (trainable / total)."""
        if self.total_params == 0:
            return 0.0
        return self.trainable_params / self.total_params

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        self.compute_latency_percentiles()

        return {
            "total_params": self.total_params,
            "trainable_params": self.trainable_params,
            "adapter_size_bytes": self.adapter_size_bytes,
            "adapter_size_kb": self.adapter_size_bytes / 1024,
            "param_efficiency": self.param_efficiency(),
            "peak_memory_mb": self.peak_memory_mb,
            "steps_per_second": self.steps_per_second,
            "examples_per_second": self.examples_per_second,
            "train_time": self.train_time,
            "final_accuracy": self.final_accuracy,
            "inference_latency_p50_ms": self.inference_latency_p50 * 1000,
            "inference_latency_p95_ms": self.inference_latency_p95 * 1000,
        }


def evaluate_model(
    model: torch.nn.Module,
    dataloader: torch.utils.data.DataLoader,
    device: str = "cuda",
    record_latency: bool = False,
) -> Tuple[float, Optional[List[float]]]:
    """
    Evaluate model accuracy on a dataloader.

    Args:
        model: Model to evaluate
        dataloader: DataLoader for evaluation
        device: Device to use
        record_latency: Whether to record per-batch latencies

    Returns:
        Tuple of (accuracy, optional list of latencies)
    """
    model.eval()
    correct = 0
    total = 0
    latencies = [] if record_latency else None

    with torch.no_grad():
        for batch in dataloader:
            if len(batch) == 2:
                x, y = batch
            elif len(batch) == 3:
                x, y, _ = batch  # Some datasets have metadata
            else:
                continue

            x = x.to(device)
            y = y.to(device)

            if record_latency:
                start = time.perf_counter()

            outputs = model(x)
            preds = outputs.argmax(dim=1)

            if record_latency:
                if device == "cuda":
                    torch.cuda.synchronize()
                latencies.append(time.perf_counter() - start)

            correct += (preds == y).sum().item()
            total += y.size(0)

    accuracy = correct / total if total > 0 else 0.0
    return accuracy, latencies


def train_epoch(
    model: torch.nn.Module,
    dataloader: torch.utils.data.DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: torch.nn.Module,
    device: str = "cuda",
) -> Tuple[float, int]:
    """
    Train model for one epoch.

    Returns:
        Tuple of (average loss, number of steps)
    """
    model.train()
    total_loss = 0.0
    num_steps = 0

    for batch in dataloader:
        if len(batch) == 2:
            x, y = batch
        elif len(batch) == 3:
            x, y, _ = batch
        else:
            continue

        x = x.to(device)
        y = y.to(device)

        optimizer.zero_grad()
        outputs = model(x)
        loss = criterion(outputs, y)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        num_steps += 1

    avg_loss = total_loss / num_steps if num_steps > 0 else 0.0
    return avg_loss, num_steps
