"""Evidence-layer contracts for raw and canonical records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from skill.retrieval.models import RetrievalHit

RouteRole = Literal["primary", "supplemental"]
PolicyJurisdictionStatus = Literal[
    "observed",
    "jurisdiction_inferred",
    "jurisdiction_unknown",
]
PolicyVersionStatus = Literal["observed", "version_missing"]
EvidenceLevel = Literal[
    "peer_reviewed",
    "preprint",
    "survey_or_review",
    "metadata_only",
]
CanonicalMatchConfidence = Literal["strong_id", "heuristic"]

_ROUTE_ROLES: frozenset[str] = frozenset({"primary", "supplemental"})
_ACADEMIC_LEVELS: frozenset[str] = frozenset(
    {"peer_reviewed", "preprint", "survey_or_review", "metadata_only"}
)
_ACADEMIC_CONFIDENCE: frozenset[str] = frozenset({"strong_id", "heuristic"})


@dataclass(frozen=True)
class RawEvidenceRecord:
    source_id: str
    title: str
    url: str
    snippet: str
    credibility_tier: str | None
    route_role: RouteRole
    token_estimate: int
    raw_hit: RetrievalHit
    authority: str | None = None
    jurisdiction: str | None = None
    jurisdiction_status: PolicyJurisdictionStatus | None = None
    publication_date: str | None = None
    effective_date: str | None = None
    version: str | None = None
    version_status: PolicyVersionStatus | None = None
    evidence_level: EvidenceLevel | None = None
    canonical_match_confidence: CanonicalMatchConfidence | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    first_author: str | None = None
    year: int | None = None
    target_route: str | None = None
    variant_reason_codes: tuple[str, ...] = field(default_factory=tuple)
    variant_queries: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.route_role not in _ROUTE_ROLES:
            raise ValueError("route_role must be primary or supplemental")
        if self.token_estimate < 0:
            raise ValueError("token_estimate must be non-negative")
        object.__setattr__(self, "variant_reason_codes", tuple(self.variant_reason_codes))
        object.__setattr__(self, "variant_queries", tuple(self.variant_queries))
        if len(self.variant_reason_codes) != len(self.variant_queries):
            raise ValueError(
                "variant_reason_codes and variant_queries must have the same length"
            )


@dataclass(frozen=True)
class EvidenceSlice:
    text: str
    source_record_id: str
    source_span: str | None
    score: float
    token_estimate: int

    def __post_init__(self) -> None:
        if self.token_estimate < 0:
            raise ValueError("token_estimate must be non-negative")


@dataclass(frozen=True)
class LinkedVariant:
    source_id: str
    title: str
    url: str
    variant_type: str
    canonical_match_confidence: CanonicalMatchConfidence
    doi: str | None = None
    arxiv_id: str | None = None
    first_author: str | None = None
    year: int | None = None

    def __post_init__(self) -> None:
        if self.canonical_match_confidence not in _ACADEMIC_CONFIDENCE:
            raise ValueError("canonical_match_confidence must be strong_id or heuristic")


@dataclass(frozen=True)
class CanonicalEvidence:
    evidence_id: str
    domain: str
    canonical_title: str
    canonical_url: str
    raw_records: tuple[RawEvidenceRecord, ...]
    retained_slices: tuple[EvidenceSlice, ...]
    linked_variants: tuple[LinkedVariant, ...] = ()
    authority: str | None = None
    jurisdiction: str | None = None
    jurisdiction_status: PolicyJurisdictionStatus | None = None
    publication_date: str | None = None
    effective_date: str | None = None
    version: str | None = None
    version_status: PolicyVersionStatus | None = None
    evidence_level: EvidenceLevel | None = None
    canonical_match_confidence: CanonicalMatchConfidence | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    first_author: str | None = None
    year: int | None = None
    route_role: RouteRole = "primary"
    token_estimate: int = 0

    def __post_init__(self) -> None:
        if not self.raw_records:
            raise ValueError("raw_records must not be empty")
        if self.route_role not in _ROUTE_ROLES:
            raise ValueError("route_role must be primary or supplemental")
        if len(self.retained_slices) > 4:
            raise ValueError("retained_slices must contain at most 4 entries by default")
        if self.token_estimate < 0:
            raise ValueError("token_estimate must be non-negative")
        if self.token_estimate == 0:
            object.__setattr__(
                self,
                "token_estimate",
                sum(slice_.token_estimate for slice_ in self.retained_slices),
            )
        if self.domain == "policy":
            self._validate_policy()
        if self.domain == "academic":
            self._validate_academic()

    def _validate_policy(self) -> None:
        if not self.authority:
            raise ValueError("policy canonical evidence requires authority")
        if not (self.publication_date or self.effective_date):
            raise ValueError("policy canonical evidence requires at least one date")
        if self.version_status is None:
            raise ValueError("policy canonical evidence requires version_status")
        if self.jurisdiction_status is None:
            raise ValueError("policy canonical evidence requires jurisdiction_status")
        if self.version is None and self.version_status != "version_missing":
            raise ValueError("missing policy version must use version_missing status")
        if self.version is not None and self.version_status != "observed":
            raise ValueError("observed policy version must use observed status")
        if self.jurisdiction is None and self.jurisdiction_status == "observed":
            raise ValueError("missing policy jurisdiction cannot use observed status")
        if self.jurisdiction is not None and self.jurisdiction_status == "jurisdiction_unknown":
            raise ValueError(
                "present policy jurisdiction cannot use jurisdiction_unknown status"
            )

    def _validate_academic(self) -> None:
        if self.evidence_level is not None and self.evidence_level not in _ACADEMIC_LEVELS:
            raise ValueError("academic evidence_level is not recognized")
        if self.canonical_match_confidence is not None and (
            self.canonical_match_confidence not in _ACADEMIC_CONFIDENCE
        ):
            raise ValueError("canonical_match_confidence must be strong_id or heuristic")
        if self.linked_variants and self.canonical_match_confidence is None:
            raise ValueError(
                "academic linked_variants require canonical_match_confidence"
            )


@dataclass(frozen=True)
class EvidencePack:
    raw_records: tuple[RawEvidenceRecord, ...]
    canonical_evidence: tuple[CanonicalEvidence, ...]
    clipped: bool = False
    pruned: bool = False
    total_token_estimate: int = 0

    def __post_init__(self) -> None:
        if self.total_token_estimate < 0:
            raise ValueError("total_token_estimate must be non-negative")
        if self.total_token_estimate == 0:
            object.__setattr__(
                self,
                "total_token_estimate",
                sum(item.token_estimate for item in self.canonical_evidence),
            )
