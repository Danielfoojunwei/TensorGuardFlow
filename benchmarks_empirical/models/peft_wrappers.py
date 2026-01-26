"""
PEFT Wrappers for Empirical Benchmarks

Implements LoRA and Adapter-based parameter-efficient fine-tuning.
Compatible with TensorGuardFlow artifact management.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Any, Optional, List, Tuple
import math
import os
import json
from pathlib import Path


class LoRALayer(nn.Module):
    """
    Low-Rank Adaptation (LoRA) layer.

    Implements: h = Wx + (alpha/r) * BAx
    where B: d x r, A: r x k, and r << min(d, k)

    Reference:
        Hu, E. J., et al. (2021). LoRA: Low-Rank Adaptation of Large Language Models.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        rank: int = 8,
        alpha: int = 16,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.rank = rank
        self.alpha = alpha
        self.scaling = alpha / rank

        # LoRA matrices
        self.lora_A = nn.Parameter(torch.zeros(rank, in_features))
        self.lora_B = nn.Parameter(torch.zeros(out_features, rank))

        # Dropout
        self.dropout = nn.Dropout(p=dropout) if dropout > 0 else nn.Identity()

        # Initialize
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply LoRA transformation."""
        # x: (..., in_features)
        # output: (..., out_features)
        result = self.dropout(x) @ self.lora_A.T @ self.lora_B.T
        return result * self.scaling

    def get_adapter_size_bytes(self) -> int:
        """Get size of adapter parameters in bytes."""
        return (self.lora_A.numel() + self.lora_B.numel()) * 4  # float32


class LoRALinear(nn.Module):
    """Linear layer with LoRA adaptation."""

    def __init__(
        self,
        original_layer: nn.Linear,
        rank: int = 8,
        alpha: int = 16,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.original_layer = original_layer
        self.lora = LoRALayer(
            in_features=original_layer.in_features,
            out_features=original_layer.out_features,
            rank=rank,
            alpha=alpha,
            dropout=dropout,
        )

        # Freeze original layer
        for param in self.original_layer.parameters():
            param.requires_grad = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.original_layer(x) + self.lora(x)


class AdapterLayer(nn.Module):
    """
    Adapter layer for parameter-efficient fine-tuning.

    Implements bottleneck adapter: h = h + f(h @ W_down) @ W_up
    where W_down: d x r, W_up: r x d, and r << d

    Reference:
        Houlsby, N., et al. (2019). Parameter-Efficient Transfer Learning for NLP.
    """

    def __init__(
        self,
        hidden_dim: int,
        bottleneck_dim: int = 64,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.bottleneck_dim = bottleneck_dim

        self.down_project = nn.Linear(hidden_dim, bottleneck_dim)
        self.up_project = nn.Linear(bottleneck_dim, hidden_dim)
        self.activation = nn.GELU()
        self.dropout = nn.Dropout(p=dropout)

        # Initialize
        nn.init.normal_(self.down_project.weight, std=0.01)
        nn.init.zeros_(self.down_project.bias)
        nn.init.normal_(self.up_project.weight, std=0.01)
        nn.init.zeros_(self.up_project.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply adapter transformation (residual)."""
        residual = self.down_project(x)
        residual = self.activation(residual)
        residual = self.dropout(residual)
        residual = self.up_project(residual)
        return x + residual

    def get_adapter_size_bytes(self) -> int:
        """Get size of adapter parameters in bytes."""
        total_params = sum(p.numel() for p in self.parameters())
        return total_params * 4  # float32


class LoRAAdapter:
    """
    LoRA adapter manager for applying LoRA to models.

    Integrates with TensorGuardFlow artifact management.
    """

    def __init__(
        self,
        rank: int = 8,
        alpha: int = 16,
        dropout: float = 0.1,
        target_modules: Optional[List[str]] = None,
    ):
        self.rank = rank
        self.alpha = alpha
        self.dropout = dropout
        self.target_modules = target_modules or ['layer3', 'layer4']
        self.lora_layers: Dict[str, LoRALinear] = {}

    def apply_to_model(self, model: nn.Module) -> nn.Module:
        """Apply LoRA to target modules in the model."""
        for name, module in model.named_modules():
            if any(target in name for target in self.target_modules):
                if isinstance(module, nn.Linear):
                    lora_linear = LoRALinear(
                        original_layer=module,
                        rank=self.rank,
                        alpha=self.alpha,
                        dropout=self.dropout,
                    )
                    self.lora_layers[name] = lora_linear

                    # Replace module in parent
                    self._set_module(model, name, lora_linear)

        return model

    def _set_module(self, model: nn.Module, name: str, new_module: nn.Module):
        """Set a module by name (handles nested modules)."""
        parts = name.split('.')
        parent = model
        for part in parts[:-1]:
            parent = getattr(parent, part)
        setattr(parent, parts[-1], new_module)

    def get_trainable_params(self) -> int:
        """Get number of trainable (LoRA) parameters."""
        total = 0
        for layer in self.lora_layers.values():
            total += layer.lora.lora_A.numel()
            total += layer.lora.lora_B.numel()
        return total

    def get_adapter_size_bytes(self) -> int:
        """Get total adapter size in bytes."""
        return sum(l.lora.get_adapter_size_bytes() for l in self.lora_layers.values())

    def save_adapter(self, path: str, task_id: Optional[int] = None):
        """Save LoRA adapter weights."""
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        # Save weights
        state_dict = {}
        for name, layer in self.lora_layers.items():
            state_dict[f"{name}.lora_A"] = layer.lora.lora_A.data.cpu()
            state_dict[f"{name}.lora_B"] = layer.lora.lora_B.data.cpu()

        weights_file = save_path / f"lora_adapter{'_task' + str(task_id) if task_id is not None else ''}.pt"
        torch.save(state_dict, weights_file)

        # Save metadata
        metadata = {
            "rank": self.rank,
            "alpha": self.alpha,
            "dropout": self.dropout,
            "target_modules": self.target_modules,
            "num_params": self.get_trainable_params(),
            "size_bytes": self.get_adapter_size_bytes(),
            "task_id": task_id,
        }
        meta_file = save_path / f"lora_metadata{'_task' + str(task_id) if task_id is not None else ''}.json"
        with open(meta_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        return weights_file

    def load_adapter(self, path: str, task_id: Optional[int] = None):
        """Load LoRA adapter weights."""
        load_path = Path(path)
        weights_file = load_path / f"lora_adapter{'_task' + str(task_id) if task_id is not None else ''}.pt"
        state_dict = torch.load(weights_file, map_location='cpu')

        for name, layer in self.lora_layers.items():
            if f"{name}.lora_A" in state_dict:
                layer.lora.lora_A.data = state_dict[f"{name}.lora_A"]
                layer.lora.lora_B.data = state_dict[f"{name}.lora_B"]


class AdapterWrapper:
    """
    Adapter manager for applying bottleneck adapters to models.
    """

    def __init__(
        self,
        bottleneck_dim: int = 64,
        dropout: float = 0.1,
        target_modules: Optional[List[str]] = None,
    ):
        self.bottleneck_dim = bottleneck_dim
        self.dropout = dropout
        self.target_modules = target_modules or ['layer3', 'layer4']
        self.adapters: Dict[str, AdapterLayer] = {}

    def apply_to_model(self, model: nn.Module) -> nn.Module:
        """Apply adapters after target modules."""
        for name, module in model.named_modules():
            if any(target in name for target in self.target_modules):
                if isinstance(module, nn.Sequential):
                    # Add adapter at the end of sequential
                    hidden_dim = self._infer_hidden_dim(module)
                    if hidden_dim:
                        adapter = AdapterLayer(
                            hidden_dim=hidden_dim,
                            bottleneck_dim=self.bottleneck_dim,
                            dropout=self.dropout,
                        )
                        self.adapters[name] = adapter
                        # Append to sequential
                        module.add_module('adapter', adapter)

        return model

    def _infer_hidden_dim(self, module: nn.Sequential) -> Optional[int]:
        """Infer hidden dimension from sequential module."""
        for layer in reversed(list(module.modules())):
            if isinstance(layer, nn.Conv2d):
                return layer.out_channels
            if isinstance(layer, nn.Linear):
                return layer.out_features
            if isinstance(layer, nn.BatchNorm2d):
                return layer.num_features
        return None

    def get_trainable_params(self) -> int:
        """Get number of trainable adapter parameters."""
        return sum(
            sum(p.numel() for p in adapter.parameters())
            for adapter in self.adapters.values()
        )

    def get_adapter_size_bytes(self) -> int:
        """Get total adapter size in bytes."""
        return sum(a.get_adapter_size_bytes() for a in self.adapters.values())

    def save_adapter(self, path: str, task_id: Optional[int] = None):
        """Save adapter weights."""
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        state_dict = {name: adapter.state_dict() for name, adapter in self.adapters.items()}
        weights_file = save_path / f"adapter{'_task' + str(task_id) if task_id is not None else ''}.pt"
        torch.save(state_dict, weights_file)

        metadata = {
            "bottleneck_dim": self.bottleneck_dim,
            "dropout": self.dropout,
            "target_modules": self.target_modules,
            "num_params": self.get_trainable_params(),
            "size_bytes": self.get_adapter_size_bytes(),
            "task_id": task_id,
        }
        meta_file = save_path / f"adapter_metadata{'_task' + str(task_id) if task_id is not None else ''}.json"
        with open(meta_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        return weights_file

    def load_adapter(self, path: str, task_id: Optional[int] = None):
        """Load adapter weights."""
        load_path = Path(path)
        weights_file = load_path / f"adapter{'_task' + str(task_id) if task_id is not None else ''}.pt"
        state_dict = torch.load(weights_file, map_location='cpu')

        for name, adapter in self.adapters.items():
            if name in state_dict:
                adapter.load_state_dict(state_dict[name])
