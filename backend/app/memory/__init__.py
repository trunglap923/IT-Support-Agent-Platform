"""Consent-gated memory lifecycle."""

from app.memory.extractor import extract_candidate_proposals
from app.memory.lifecycle import MemoryLifecycleService
from app.memory.schemas import CandidateProposal

__all__ = ["CandidateProposal", "MemoryLifecycleService", "extract_candidate_proposals"]
