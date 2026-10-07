"""Snapshot anomaly gate.

A sudden mass "disappearance" is far more likely to be a source redesign,
parser regression, blocked/partial response or pagination failure than a real
wave of resignations. Snapshots failing the gate are QUARANTINED: they remain
on disk for forensics but cannot create absence events.
"""

from dataclasses import dataclass, field

from venue_access.domain.enums import SnapshotStatus
from venue_access.domain.models import ParsedSnapshot, SnapshotMeta

# Baseline policy (ADR 005): quarantine on >15% disappearance, and always on
# structural red flags below.
MAX_DROP_RATIO = 0.15
MAX_GROWTH_RATIO = 0.50  # sudden +50% is also suspicious (dupes, parse bugs)
MIN_ABS_RECORDS = 10


@dataclass
class GateResult:
    passed: bool
    status: SnapshotStatus
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


def evaluate_snapshot(
    parsed: ParsedSnapshot,
    violations: list[str],
    previous: SnapshotMeta | dict | None,
) -> GateResult:
    reasons: list[str] = []
    metrics: dict[str, float] = {}

    record_count = len(parsed.records)
    seg_count = sum(len(r.segments) for r in parsed.records)
    code_count = sum(1 for r in parsed.records for s in r.segments if s.member_code)
    metrics.update(
        record_count=record_count,
        segment_count=seg_count,
        member_code_count=code_count,
        parse_error_count=len(parsed.parse_errors),
        parse_error_ratio=(len(parsed.parse_errors) / record_count) if record_count else 1.0,
    )

    # Hard failures.
    if record_count == 0:
        reasons.append("SOURCE_EMPTY: zero records parsed")
        return GateResult(False, SnapshotStatus.QUARANTINED, reasons, metrics)
    if record_count < MIN_ABS_RECORDS:
        reasons.append(f"SOURCE_PARTIAL: {record_count} < {MIN_ABS_RECORDS} records")
        return GateResult(False, SnapshotStatus.QUARANTINED, reasons, metrics)
    if metrics["parse_error_ratio"] > 0.25:
        reasons.append(f"PARSE_ERROR: ratio {metrics['parse_error_ratio']:.0%}")
    for v in violations:
        reasons.append(v)

    if previous is not None:
        prev_records = previous.get("record_count") or 0
        prev_segments = previous.get("segment_count") or 0
        prev_sig = previous.get("source_schema_signature") or ""
        if prev_records:
            drop = (prev_records - record_count) / prev_records
            metrics["record_count_delta_ratio"] = -drop
            if drop > MAX_DROP_RATIO:
                reasons.append(
                    f"QUARANTINE: record drop {drop:.0%} > {MAX_DROP_RATIO:.0%} "
                    f"({prev_records} -> {record_count})"
                )
            elif drop < -MAX_GROWTH_RATIO:
                reasons.append(
                    f"QUARANTINE: record growth {-drop:.0%} > {MAX_GROWTH_RATIO:.0%} "
                    f"({prev_records} -> {record_count})"
                )
        if prev_segments:
            seg_drop = (prev_segments - seg_count) / prev_segments
            metrics["segment_count_delta_ratio"] = -seg_drop
            if seg_drop > MAX_DROP_RATIO:
                reasons.append(
                    f"QUARANTINE: segment drop {seg_drop:.0%} > {MAX_DROP_RATIO:.0%} "
                    f"({prev_segments} -> {seg_count})"
                )
        if prev_sig and parsed.schema_signature and prev_sig != parsed.schema_signature:
            metrics["schema_signature_changed"] = 1.0
            reasons.append(
                f"SCHEMA_SIGNATURE_CHANGED: {prev_sig} -> {parsed.schema_signature}"
            )

    hard = [r for r in reasons if r.split(":")[0] in
            {"SOURCE_EMPTY", "SOURCE_PARTIAL", "QUARANTINE", "VALIDATION_ERROR"}]
    if hard:
        return GateResult(False, SnapshotStatus.QUARANTINED, reasons, metrics)
    status = SnapshotStatus.VALIDATED if not reasons else SnapshotStatus.VALIDATED
    return GateResult(True, status, reasons, metrics)
