"""
Continual Learning Vision Datasets

Implements Split CIFAR-100 and Split TinyImageNet following
standard continual learning benchmarks (Avalanche-like protocols).

NO MOCK DATA. All datasets are downloaded from public sources.
"""

import os
import sys
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, Subset
from torchvision import datasets, transforms
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import urllib.request
import zipfile
import tarfile
import shutil


class MockDataError(Exception):
    """Raised when mock/simulated data is detected."""
    pass


def verify_not_mock(data: Any, name: str):
    """Verify that data is not mock/simulated."""
    if data is None:
        raise MockDataError(f"Dataset {name} returned None - possible mock data")
    if isinstance(data, (list, np.ndarray, torch.Tensor)) and len(data) == 0:
        raise MockDataError(f"Dataset {name} is empty - possible mock data")


class SplitCIFAR100:
    """
    Split CIFAR-100 Benchmark.

    Splits CIFAR-100 into 20 tasks with 5 classes each.
    Uses deterministic class ordering based on seed.

    This downloads the REAL CIFAR-100 dataset from torchvision.
    """

    def __init__(
        self,
        data_dir: str = "./data/cifar100",
        num_tasks: int = 20,
        classes_per_task: int = 5,
        seed: int = 42,
        download: bool = True,
        fail_on_mock: bool = True,
    ):
        self.data_dir = Path(data_dir)
        self.num_tasks = num_tasks
        self.classes_per_task = classes_per_task
        self.seed = seed
        self.fail_on_mock = fail_on_mock

        # Validate configuration
        total_classes = num_tasks * classes_per_task
        if total_classes != 100:
            raise ValueError(
                f"num_tasks * classes_per_task must equal 100, got {total_classes}"
            )

        # Set random seed for reproducible class ordering
        np.random.seed(seed)
        self.class_order = np.random.permutation(100).tolist()

        # Standard CIFAR transforms
        self.train_transform = transforms.Compose([
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.5071, 0.4867, 0.4408],
                std=[0.2675, 0.2565, 0.2761]
            ),
        ])

        self.eval_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.5071, 0.4867, 0.4408],
                std=[0.2675, 0.2565, 0.2761]
            ),
        ])

        # Download and load CIFAR-100
        self._load_dataset(download)

    def _load_dataset(self, download: bool):
        """Load CIFAR-100 dataset."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.train_dataset = datasets.CIFAR100(
                root=str(self.data_dir),
                train=True,
                download=download,
                transform=self.train_transform,
            )
            self.test_dataset = datasets.CIFAR100(
                root=str(self.data_dir),
                train=False,
                download=download,
                transform=self.eval_transform,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to download CIFAR-100. Ensure internet connection. Error: {e}"
            )

        # Verify not mock data
        if self.fail_on_mock:
            verify_not_mock(self.train_dataset, "CIFAR-100 train")
            verify_not_mock(self.test_dataset, "CIFAR-100 test")
            if len(self.train_dataset) != 50000:
                raise MockDataError(
                    f"CIFAR-100 train should have 50000 samples, got {len(self.train_dataset)}"
                )
            if len(self.test_dataset) != 10000:
                raise MockDataError(
                    f"CIFAR-100 test should have 10000 samples, got {len(self.test_dataset)}"
                )

        # Build class-to-indices mapping
        self.train_class_indices = self._build_class_indices(self.train_dataset)
        self.test_class_indices = self._build_class_indices(self.test_dataset)

        print(f"[SplitCIFAR100] Loaded {len(self.train_dataset)} train, {len(self.test_dataset)} test samples")

    def _build_class_indices(self, dataset: Dataset) -> Dict[int, List[int]]:
        """Build mapping from class to sample indices."""
        class_indices = {i: [] for i in range(100)}
        for idx, (_, label) in enumerate(dataset):
            class_indices[label].append(idx)
        return class_indices

    def get_task_classes(self, task_id: int) -> List[int]:
        """Get class indices for a specific task."""
        if task_id < 0 or task_id >= self.num_tasks:
            raise ValueError(f"task_id must be in [0, {self.num_tasks}), got {task_id}")

        start = task_id * self.classes_per_task
        end = start + self.classes_per_task
        return self.class_order[start:end]

    def get_task_data(
        self,
        task_id: int,
        train: bool = True,
    ) -> Tuple[Dataset, List[int]]:
        """
        Get data for a specific task.

        Returns:
            Tuple of (Subset dataset, list of original class labels)
        """
        classes = self.get_task_classes(task_id)
        class_indices = self.train_class_indices if train else self.test_class_indices
        base_dataset = self.train_dataset if train else self.test_dataset

        # Collect all indices for task classes
        indices = []
        for cls in classes:
            indices.extend(class_indices[cls])

        subset = Subset(base_dataset, indices)
        return subset, classes

    def get_all_tasks_up_to(
        self,
        task_id: int,
        train: bool = True,
    ) -> Tuple[Dataset, List[int]]:
        """Get data for all tasks up to and including task_id."""
        all_indices = []
        all_classes = []

        for t in range(task_id + 1):
            classes = self.get_task_classes(t)
            class_indices = self.train_class_indices if train else self.test_class_indices
            for cls in classes:
                all_indices.extend(class_indices[cls])
            all_classes.extend(classes)

        base_dataset = self.train_dataset if train else self.test_dataset
        subset = Subset(base_dataset, all_indices)
        return subset, all_classes

    def get_dataloader(
        self,
        task_id: int,
        train: bool = True,
        batch_size: int = 64,
        num_workers: int = 4,
    ) -> DataLoader:
        """Get DataLoader for a specific task."""
        subset, _ = self.get_task_data(task_id, train)
        return DataLoader(
            subset,
            batch_size=batch_size,
            shuffle=train,
            num_workers=num_workers,
            pin_memory=True,
        )

    def get_info(self) -> Dict[str, Any]:
        """Get dataset information."""
        return {
            "name": "Split CIFAR-100",
            "num_tasks": self.num_tasks,
            "classes_per_task": self.classes_per_task,
            "total_classes": 100,
            "train_samples": len(self.train_dataset),
            "test_samples": len(self.test_dataset),
            "image_size": (3, 32, 32),
            "class_order": self.class_order,
            "seed": self.seed,
        }


class SplitTinyImageNet:
    """
    Split TinyImageNet Benchmark.

    Splits TinyImageNet (200 classes) into 20 tasks with 10 classes each
    OR 40 tasks with 5 classes each.

    Downloads the REAL TinyImageNet dataset from the official source.
    """

    TINYIMAGENET_URL = "http://cs231n.stanford.edu/tiny-imagenet-200.zip"

    def __init__(
        self,
        data_dir: str = "./data/tinyimagenet",
        num_tasks: int = 20,
        classes_per_task: int = 10,
        seed: int = 42,
        download: bool = True,
        fail_on_mock: bool = True,
    ):
        self.data_dir = Path(data_dir)
        self.num_tasks = num_tasks
        self.classes_per_task = classes_per_task
        self.seed = seed
        self.fail_on_mock = fail_on_mock

        # Validate configuration
        total_classes = num_tasks * classes_per_task
        if total_classes != 200:
            raise ValueError(
                f"num_tasks * classes_per_task must equal 200, got {total_classes}"
            )

        # Set random seed for reproducible class ordering
        np.random.seed(seed)
        self.class_order = np.random.permutation(200).tolist()

        # Standard TinyImageNet transforms
        self.train_transform = transforms.Compose([
            transforms.RandomCrop(64, padding=8),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])

        self.eval_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])

        # Download and load TinyImageNet
        self._load_dataset(download)

    def _download_tinyimagenet(self):
        """Download TinyImageNet dataset."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.data_dir / "tiny-imagenet-200.zip"
        extract_dir = self.data_dir / "tiny-imagenet-200"

        if extract_dir.exists():
            print(f"[TinyImageNet] Dataset already exists at {extract_dir}")
            return

        print(f"[TinyImageNet] Downloading from {self.TINYIMAGENET_URL}...")
        try:
            urllib.request.urlretrieve(self.TINYIMAGENET_URL, zip_path)
        except Exception as e:
            raise RuntimeError(f"Failed to download TinyImageNet: {e}")

        print(f"[TinyImageNet] Extracting to {extract_dir}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.data_dir)

        # Clean up zip file
        zip_path.unlink()
        print("[TinyImageNet] Download complete.")

    def _load_dataset(self, download: bool):
        """Load TinyImageNet dataset."""
        extract_dir = self.data_dir / "tiny-imagenet-200"

        if download and not extract_dir.exists():
            self._download_tinyimagenet()

        if not extract_dir.exists():
            raise RuntimeError(
                f"TinyImageNet not found at {extract_dir}. Set download=True."
            )

        # Load training data
        train_dir = extract_dir / "train"
        self.train_dataset = datasets.ImageFolder(
            str(train_dir),
            transform=self.train_transform,
        )

        # Load validation data (TinyImageNet has val in different structure)
        val_dir = extract_dir / "val"
        self._prepare_val_folder(val_dir)
        self.test_dataset = datasets.ImageFolder(
            str(val_dir / "images_organized"),
            transform=self.eval_transform,
        )

        # Build class mapping
        self.class_to_idx = self.train_dataset.class_to_idx
        self.idx_to_class = {v: k for k, v in self.class_to_idx.items()}

        # Verify not mock data
        if self.fail_on_mock:
            verify_not_mock(self.train_dataset, "TinyImageNet train")
            verify_not_mock(self.test_dataset, "TinyImageNet test")
            if len(self.train_dataset) < 100000:
                raise MockDataError(
                    f"TinyImageNet train should have ~100000 samples, got {len(self.train_dataset)}"
                )

        # Build class-to-indices mapping
        self.train_class_indices = self._build_class_indices(self.train_dataset)
        self.test_class_indices = self._build_class_indices(self.test_dataset)

        print(f"[SplitTinyImageNet] Loaded {len(self.train_dataset)} train, {len(self.test_dataset)} test samples")

    def _prepare_val_folder(self, val_dir: Path):
        """Reorganize validation folder into class subfolders."""
        organized_dir = val_dir / "images_organized"
        if organized_dir.exists():
            return

        # Read val annotations
        annotations_file = val_dir / "val_annotations.txt"
        if not annotations_file.exists():
            raise RuntimeError(f"Val annotations not found: {annotations_file}")

        # Parse annotations
        img_to_class = {}
        with open(annotations_file, 'r') as f:
            for line in f:
                parts = line.strip().split('\t')
                img_name = parts[0]
                class_name = parts[1]
                img_to_class[img_name] = class_name

        # Create organized folder structure
        images_dir = val_dir / "images"
        for img_name, class_name in img_to_class.items():
            class_dir = organized_dir / class_name
            class_dir.mkdir(parents=True, exist_ok=True)

            src = images_dir / img_name
            dst = class_dir / img_name
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)

    def _build_class_indices(self, dataset: Dataset) -> Dict[int, List[int]]:
        """Build mapping from class to sample indices."""
        class_indices = {i: [] for i in range(200)}
        for idx in range(len(dataset)):
            _, label = dataset[idx]
            class_indices[label].append(idx)
        return class_indices

    def get_task_classes(self, task_id: int) -> List[int]:
        """Get class indices for a specific task."""
        if task_id < 0 or task_id >= self.num_tasks:
            raise ValueError(f"task_id must be in [0, {self.num_tasks}), got {task_id}")

        start = task_id * self.classes_per_task
        end = start + self.classes_per_task
        return self.class_order[start:end]

    def get_task_data(
        self,
        task_id: int,
        train: bool = True,
    ) -> Tuple[Dataset, List[int]]:
        """Get data for a specific task."""
        classes = self.get_task_classes(task_id)
        class_indices = self.train_class_indices if train else self.test_class_indices
        base_dataset = self.train_dataset if train else self.test_dataset

        indices = []
        for cls in classes:
            indices.extend(class_indices.get(cls, []))

        subset = Subset(base_dataset, indices)
        return subset, classes

    def get_all_tasks_up_to(
        self,
        task_id: int,
        train: bool = True,
    ) -> Tuple[Dataset, List[int]]:
        """Get data for all tasks up to and including task_id."""
        all_indices = []
        all_classes = []

        for t in range(task_id + 1):
            classes = self.get_task_classes(t)
            class_indices = self.train_class_indices if train else self.test_class_indices
            for cls in classes:
                all_indices.extend(class_indices.get(cls, []))
            all_classes.extend(classes)

        base_dataset = self.train_dataset if train else self.test_dataset
        subset = Subset(base_dataset, all_indices)
        return subset, all_classes

    def get_dataloader(
        self,
        task_id: int,
        train: bool = True,
        batch_size: int = 64,
        num_workers: int = 4,
    ) -> DataLoader:
        """Get DataLoader for a specific task."""
        subset, _ = self.get_task_data(task_id, train)
        return DataLoader(
            subset,
            batch_size=batch_size,
            shuffle=train,
            num_workers=num_workers,
            pin_memory=True,
        )

    def get_info(self) -> Dict[str, Any]:
        """Get dataset information."""
        return {
            "name": "Split TinyImageNet",
            "num_tasks": self.num_tasks,
            "classes_per_task": self.classes_per_task,
            "total_classes": 200,
            "train_samples": len(self.train_dataset),
            "test_samples": len(self.test_dataset),
            "image_size": (3, 64, 64),
            "class_order": self.class_order,
            "seed": self.seed,
        }
