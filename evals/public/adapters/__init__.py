"""Dataset-specific adapters for public retrieval benchmarks."""

from evals.public.adapters.beir import BEIR_DATASETS, load_beir_dataset

__all__ = ["BEIR_DATASETS", "load_beir_dataset"]
