"""Dataset loaders for empirical benchmarks."""

from .clvision import SplitCIFAR100, SplitTinyImageNet
from .core50 import CORe50Dataset
from .wilds import WILDSDatasetLoader

__all__ = [
    "SplitCIFAR100",
    "SplitTinyImageNet",
    "CORe50Dataset",
    "WILDSDatasetLoader",
]
