"""Budget-constrained packing for scored canonical evidence."""

from __future__ import annotations

from dataclasses import replace

from skill.evidence.models import CanonicalEvidence, EvidencePack
from skill.evidence.score import score_evidence_records


def _total_tokens(records: list[CanonicalEvidence]) -> int:
    return sum(record.token_estimate for record in records)


def _with_updated_tokens(record: CanonicalEvidence) -> CanonicalEvidence:
    updated = replace(
        record,
        token_estimate=sum(slice_.token_estimate for slice_ in record.retained_slices),
    )
    if hasattr(record, "total_score"):
        object.__setattr__(updated, "total_score", getattr(record, "total_score"))
    return updated


def _slice_metadata_anchor_bonus(record: CanonicalEvidence, slice_text: str) -> float:
    normalized_text = slice_text.casefold()
    bonus = 0.0

    for anchor in (record.publication_date, record.effective_date, record.version):
        if anchor and anchor.casefold() in normalized_text:
            bonus += 0.35

    if record.year is not None and str(record.year) in slice_text:
        bonus += 0.2

    if sum(character.isdigit() for character in slice_text) >= 4:
        bonus += 0.15

    if any(separator in slice_text for separator in (":", ";", "|", "\t")):
        bonus += 0.1

    return min(bonus, 1.0)


def _select_top_k(
    records: list[CanonicalEvidence],
    *,
    top_k: int,
    supplemental_min_items: int,
) -> tuple[list[CanonicalEvidence], bool, int]:
    if top_k <= 0 or not records:
        return [], bool(records), 0

    primary_records = [record for record in records if record.route_role == "primary"]
    supplemental_records = [record for record in records if record.route_role == "supplemental"]
    reserve = 0
    if primary_records and supplemental_records and top_k > 1 and supplemental_min_items > 0:
        reserve = min(supplemental_min_items, len(supplemental_records), top_k - 1)

    selected: list[CanonicalEvidence] = []
    selected.extend(primary_records[: top_k - reserve])
    selected.extend(supplemental_records[:reserve])

    if len(selected) < top_k:
        selected_ids = {record.evidence_id for record in selected}
        for record in records:
            if record.evidence_id in selected_ids:
                continue
            selected.append(record)
            if len(selected) == top_k:
                break

    selected = sorted(
        selected,
        key=lambda record: (
            -getattr(record, "total_score", 0.0),
            record.route_role != "primary",
            record.evidence_id,
        ),
    )
    return selected, len(records) > len(selected), reserve


def _trim_lowest_scoring_slice(records: list[CanonicalEvidence]) -> bool:
    candidates: list[tuple[float, int, str, int]] = []
    for index, record in enumerate(records):
        if len(record.retained_slices) <= 1:
            continue
        lowest_slice = min(
            enumerate(record.retained_slices),
            key=lambda entry: (
                entry[1].score + _slice_metadata_anchor_bonus(record, entry[1].text),
                entry[1].token_estimate,
                entry[1].text,
            ),
        )
        candidates.append(
            (
                lowest_slice[1].score + _slice_metadata_anchor_bonus(record, lowest_slice[1].text),
                lowest_slice[1].token_estimate,
                record.evidence_id,
                index,
            )
        )

    if not candidates:
        return False

    _, _, _, record_index = min(candidates, key=lambda item: (item[0], item[1], item[2]))
    record = records[record_index]
    lowest_slice_index = min(
        range(len(record.retained_slices)),
        key=lambda idx: (
            record.retained_slices[idx].score
            + _slice_metadata_anchor_bonus(record, record.retained_slices[idx].text),
            record.retained_slices[idx].token_estimate,
            record.retained_slices[idx].text,
        ),
    )
    updated_slices = tuple(
        slice_
        for idx, slice_ in enumerate(record.retained_slices)
        if idx != lowest_slice_index
    )
    records[record_index] = score_evidence_records(
        [_with_updated_tokens(replace(record, retained_slices=updated_slices))]
    )[0]
    return True


def _drop_lowest_scoring_record(
    records: list[CanonicalEvidence],
    *,
    supplemental_reserve: int,
) -> bool:
    if not records:
        return False

    supplemental_count = sum(record.route_role == "supplemental" for record in records)
    primary_count = sum(record.route_role == "primary" for record in records)

    removable_indices = [
        index
        for index, record in enumerate(records)
        if not (
            record.route_role == "supplemental"
            and supplemental_count <= supplemental_reserve
            and primary_count > 0
        )
    ]
    if not removable_indices:
        removable_indices = list(range(len(records)))

    record_index = min(
        removable_indices,
        key=lambda index: (
            getattr(records[index], "total_score", 0.0),
            records[index].token_estimate,
            records[index].evidence_id,
        ),
    )
    records.pop(record_index)
    return True


def build_evidence_pack(
    records: list[CanonicalEvidence],
    *,
    token_budget: int,
    top_k: int,
    supplemental_min_items: int = 1,
) -> EvidencePack:
    """Build a bounded evidence pack with slice-first pruning."""

    selected_records, clipped, supplemental_reserve = _select_top_k(
        list(records),
        top_k=top_k,
        supplemental_min_items=supplemental_min_items,
    )

    working_records = [_with_updated_tokens(record) for record in selected_records]
    pruned = False

    while working_records and _total_tokens(working_records) > token_budget:
        if _trim_lowest_scoring_slice(working_records):
            clipped = True
            pruned = True
            continue
        if _drop_lowest_scoring_record(
            working_records,
            supplemental_reserve=supplemental_reserve,
        ):
            clipped = True
            pruned = True
            continue
        break

    raw_records = tuple(
        raw_record
        for record in working_records
        for raw_record in record.raw_records
    )
    return EvidencePack(
        raw_records=raw_records,
        canonical_evidence=tuple(working_records),
        clipped=clipped,
        pruned=pruned,
        total_token_estimate=_total_tokens(working_records),
    )
