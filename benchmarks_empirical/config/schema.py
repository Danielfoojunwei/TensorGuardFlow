"""
Configuration schema for empirical benchmarks.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import yaml
from pathlib import Path


class Suite(Enum):
    CLVISION = "clvision"
    WILDS = "wilds"
    PEFT = "peft"
    ALL = "all"


class Method(Enum):
    FROZEN = "frozen"
    NAIVE_FINETUNE = "naive_finetune"
    TENSORGUARD = "tensorguard"


@dataclass
class DatasetConfig:
    """Configuration for a dataset."""
    name: str
    num_tasks: int = 20
    classes_per_task: int = 5
    train_transforms: Optional[str] = "standard"
    eval_transforms: Optional[str] = "standard"
    download: bool = True
    data_dir: str = "./data"


@dataclass
class ModelConfig:
    """Configuration for model backbone."""
    backbone: str = "resnet18"
    pretrained: bool = True
    num_classes: int = 100
    hidden_dim: int = 512


@dataclass
class TrainingConfig:
    """Training configuration."""
    epochs_per_task: int = 5
    batch_size: int = 64
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    optimizer: str = "adam"
    scheduler: Optional[str] = None


@dataclass
class PEFTConfig:
    """PEFT-specific configuration."""
    adapter_type: str = "lora"
    lora_rank: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.1
    target_modules: List[str] = field(default_factory=lambda: ["query", "value"])


@dataclass
class BenchmarkConfig:
    """Main benchmark configuration."""
    suite: str
    datasets: List[DatasetConfig]
    model: ModelConfig
    training: TrainingConfig
    peft: Optional[PEFTConfig] = None
    methods: List[str] = field(default_factory=lambda: ["frozen", "naive_finetune", "tensorguard"])
    seeds: List[int] = field(default_factory=lambda: [42, 123, 456])
    device: str = "cuda"
    output_dir: str = "reports"
    fail_on_mock: bool = True

    @classmethod
    def from_yaml(cls, path: str) -> "BenchmarkConfig":
        """Load configuration from YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        # Parse datasets
        datasets = [
            DatasetConfig(**ds) for ds in data.get('datasets', [])
        ]

        # Parse model config
        model = ModelConfig(**data.get('model', {}))

        # Parse training config
        training = TrainingConfig(**data.get('training', {}))

        # Parse PEFT config if present
        peft = None
        if 'peft' in data:
            peft = PEFTConfig(**data['peft'])

        return cls(
            suite=data.get('suite', 'clvision'),
            datasets=datasets,
            model=model,
            training=training,
            peft=peft,
            methods=data.get('methods', ['frozen', 'naive_finetune', 'tensorguard']),
            seeds=data.get('seeds', [42, 123, 456]),
            device=data.get('device', 'cuda'),
            output_dir=data.get('output_dir', 'reports'),
            fail_on_mock=data.get('fail_on_mock', True),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'suite': self.suite,
            'datasets': [
                {
                    'name': ds.name,
                    'num_tasks': ds.num_tasks,
                    'classes_per_task': ds.classes_per_task,
                }
                for ds in self.datasets
            ],
            'model': {
                'backbone': self.model.backbone,
                'pretrained': self.model.pretrained,
                'num_classes': self.model.num_classes,
            },
            'training': {
                'epochs_per_task': self.training.epochs_per_task,
                'batch_size': self.training.batch_size,
                'learning_rate': self.training.learning_rate,
            },
            'methods': self.methods,
            'seeds': self.seeds,
            'device': self.device,
        }


def load_suite_config(suite: str) -> BenchmarkConfig:
    """Load configuration for a specific suite."""
    config_dir = Path(__file__).parent / "suites"
    config_path = config_dir / f"{suite}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Suite configuration not found: {config_path}")

    return BenchmarkConfig.from_yaml(str(config_path))


def get_default_config(suite: str) -> BenchmarkConfig:
    """Get default configuration for a suite."""
    if suite == "clvision":
        return BenchmarkConfig(
            suite="clvision",
            datasets=[
                DatasetConfig(name="split_cifar100", num_tasks=20, classes_per_task=5),
                DatasetConfig(name="split_tinyimagenet", num_tasks=20, classes_per_task=10),
            ],
            model=ModelConfig(backbone="resnet18", pretrained=True, num_classes=100),
            training=TrainingConfig(epochs_per_task=5, batch_size=64),
        )
    elif suite == "wilds":
        return BenchmarkConfig(
            suite="wilds",
            datasets=[
                DatasetConfig(name="iwildcam", num_tasks=1, classes_per_task=182),
            ],
            model=ModelConfig(backbone="resnet50", pretrained=True, num_classes=182),
            training=TrainingConfig(epochs_per_task=10, batch_size=32),
        )
    elif suite == "peft":
        return BenchmarkConfig(
            suite="peft",
            datasets=[
                DatasetConfig(name="cifar100", num_tasks=1, classes_per_task=100),
            ],
            model=ModelConfig(backbone="resnet18", pretrained=True, num_classes=100),
            training=TrainingConfig(epochs_per_task=10, batch_size=64),
            peft=PEFTConfig(adapter_type="lora", lora_rank=8),
        )
    else:
        raise ValueError(f"Unknown suite: {suite}")
