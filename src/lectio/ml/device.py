import gc
from typing import Literal

import torch

from lectio.core.config import Device

ResolvedDevice = Literal["cuda", "mps", "cpu"]


def resolve_device(requested: Device) -> ResolvedDevice:
    if requested != "auto":
        return requested

    if torch.cuda.is_available():
        return "cuda"

    if torch.backends.mps.is_available():
        return "mps"

    return "cpu"


def free_accelerator_memory() -> None:
    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    elif torch.backends.mps.is_available():
        torch.mps.empty_cache()
