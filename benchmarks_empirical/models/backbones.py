"""
Model Backbones for Empirical Benchmarks

Provides small, publicly available pretrained backbones for benchmarking.
Uses torchvision models only (no external dependencies).
"""

import torch
import torch.nn as nn
from torchvision import models
from typing import Dict, Any, Optional, Tuple


AVAILABLE_BACKBONES = [
    'resnet18',
    'resnet34',
    'resnet50',
    'mobilenet_v2',
    'efficientnet_b0',
]


class ClassificationHead(nn.Module):
    """Simple classification head for continual learning."""

    def __init__(self, in_features: int, num_classes: int, hidden_dim: int = 512):
        super().__init__()
        self.head = nn.Sequential(
            nn.Linear(in_features, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(x)


class ContinualLearningModel(nn.Module):
    """
    Model wrapper for continual learning benchmarks.

    Supports:
    - Frozen backbone (frozen=True)
    - Full fine-tuning (frozen=False)
    - Expandable classification head for new tasks
    """

    def __init__(
        self,
        backbone_name: str = 'resnet18',
        num_classes: int = 100,
        pretrained: bool = True,
        frozen: bool = False,
    ):
        super().__init__()
        self.backbone_name = backbone_name
        self.num_classes = num_classes
        self.pretrained = pretrained
        self.frozen = frozen

        # Load backbone
        self.backbone, self.feature_dim = self._load_backbone(backbone_name, pretrained)

        # Freeze backbone if requested
        if frozen:
            for param in self.backbone.parameters():
                param.requires_grad = False

        # Classification head
        self.classifier = nn.Linear(self.feature_dim, num_classes)

        # Task-specific heads for continual learning
        self.task_heads: Dict[int, nn.Linear] = {}

    def _load_backbone(
        self, name: str, pretrained: bool
    ) -> Tuple[nn.Module, int]:
        """Load a pretrained backbone."""
        weights = 'DEFAULT' if pretrained else None

        if name == 'resnet18':
            model = models.resnet18(weights=weights)
            feature_dim = model.fc.in_features
            model.fc = nn.Identity()
        elif name == 'resnet34':
            model = models.resnet34(weights=weights)
            feature_dim = model.fc.in_features
            model.fc = nn.Identity()
        elif name == 'resnet50':
            model = models.resnet50(weights=weights)
            feature_dim = model.fc.in_features
            model.fc = nn.Identity()
        elif name == 'mobilenet_v2':
            model = models.mobilenet_v2(weights=weights)
            feature_dim = model.classifier[1].in_features
            model.classifier = nn.Identity()
        elif name == 'efficientnet_b0':
            model = models.efficientnet_b0(weights=weights)
            feature_dim = model.classifier[1].in_features
            model.classifier = nn.Identity()
        else:
            raise ValueError(f"Unknown backbone: {name}. Available: {AVAILABLE_BACKBONES}")

        return model, feature_dim

    def forward(self, x: torch.Tensor, task_id: Optional[int] = None) -> torch.Tensor:
        """Forward pass."""
        features = self.backbone(x)

        if task_id is not None and task_id in self.task_heads:
            return self.task_heads[task_id](features)
        return self.classifier(features)

    def get_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract features without classification."""
        return self.backbone(x)

    def add_task_head(self, task_id: int, num_classes: int):
        """Add a task-specific head."""
        self.task_heads[task_id] = nn.Linear(self.feature_dim, num_classes)
        if next(self.parameters()).is_cuda:
            self.task_heads[task_id] = self.task_heads[task_id].cuda()

    def expand_classifier(self, new_classes: int):
        """Expand the main classifier for new classes."""
        old_weight = self.classifier.weight.data
        old_bias = self.classifier.bias.data
        old_num_classes = old_weight.shape[0]

        new_num_classes = old_num_classes + new_classes
        new_classifier = nn.Linear(self.feature_dim, new_num_classes)

        # Copy old weights
        new_classifier.weight.data[:old_num_classes] = old_weight
        new_classifier.bias.data[:old_num_classes] = old_bias

        # Initialize new weights
        nn.init.kaiming_normal_(new_classifier.weight.data[old_num_classes:])
        nn.init.zeros_(new_classifier.bias.data[old_num_classes:])

        self.classifier = new_classifier
        self.num_classes = new_num_classes

        if next(self.parameters()).is_cuda:
            self.classifier = self.classifier.cuda()

    def get_trainable_params(self) -> int:
        """Get number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def get_total_params(self) -> int:
        """Get total number of parameters."""
        return sum(p.numel() for p in self.parameters())

    def freeze_backbone(self):
        """Freeze the backbone."""
        for param in self.backbone.parameters():
            param.requires_grad = False
        self.frozen = True

    def unfreeze_backbone(self):
        """Unfreeze the backbone."""
        for param in self.backbone.parameters():
            param.requires_grad = True
        self.frozen = False


def get_backbone(
    name: str = 'resnet18',
    num_classes: int = 100,
    pretrained: bool = True,
    frozen: bool = False,
) -> ContinualLearningModel:
    """
    Get a backbone model for benchmarking.

    Args:
        name: Backbone name (resnet18, resnet34, resnet50, mobilenet_v2, efficientnet_b0)
        num_classes: Number of output classes
        pretrained: Whether to use pretrained weights
        frozen: Whether to freeze the backbone

    Returns:
        ContinualLearningModel instance
    """
    return ContinualLearningModel(
        backbone_name=name,
        num_classes=num_classes,
        pretrained=pretrained,
        frozen=frozen,
    )


def count_parameters(model: nn.Module) -> Dict[str, int]:
    """Count model parameters."""
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    frozen = total - trainable

    return {
        'total': total,
        'trainable': trainable,
        'frozen': frozen,
    }
