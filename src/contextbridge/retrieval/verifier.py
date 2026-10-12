"""Evidence verification: is a card backed by the evidence stored for exactly that version?

Verification never proves a claim true. It reports ``supported`` only when the inspected record
is consistent with the card *and* an injected judge finds that the stored evidence backs the claim.
Word overlap, vector similarity, and model confidence are not evidence, so none is used here.
Without a judge the honest answer is ``uncertain``: provenance can be checked, support cannot.
"""

from typing import Literal, Protocol

from pydantic import ValidationError

from contextbridge.contracts import MemoryRecord
from contextbridge.schemas import InspectionResponse
from contextbridge.security import contains_secret

Judgment = Literal["supports", "contradicts", "insufficient"]
Verdict = Literal["supported", "uncertain"]


class EvidenceJudge(Protocol):
    """Decides whether ``evidence`` backs ``claim``. Both strings are untrusted data."""

    def judge(self, claim: str, evidence: str) -> Judgment: ...


class EvidenceVerifier:
    def __init__(self, judge: EvidenceJudge | None = None):
        self.judge = judge
        self.unavailable = False

    def verify(self, record: dict, inspection: dict) -> Verdict:
        self.unavailable = False
        try:
            memory = MemoryRecord.model_validate(record)
            inspected = InspectionResponse.model_validate(inspection)
        except (ValidationError, TypeError, ValueError):
            return "uncertain"
        card = memory.memory.version
        # A contested decision must not be compressed into one confident answer.
        if memory.decision_state != "clear" or inspected.memory.id != memory.memory.id:
            return "uncertain"
        stored = next((v for v in inspected.history if v.id == card.id), None)
        if stored is None:
            return "uncertain"
        # The card must describe exactly the version whose evidence is being read.
        if (
            stored.content != card.content
            or stored.status != card.status
            or (stored.number, stored.valid_from, stored.valid_to)
            != (card.number, card.valid_from, card.valid_to)
            or stored.source != card.source
        ):
            return "uncertain"
        if self.judge is None or contains_secret(stored.source.evidence):
            return "uncertain"
        try:
            outcome = self.judge.judge(stored.content, stored.source.evidence)
        except Exception:
            self.unavailable = True
            return "uncertain"
        return "supported" if outcome == "supports" else "uncertain"
