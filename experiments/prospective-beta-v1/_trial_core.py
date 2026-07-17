"""Auditable standard-library kernel for Busleyden's prospective beta trial."""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

TRIAL_ID = "busleyden-prospective-beta-v1"
SCHEMA_VERSION = "1.0"
ARMS = ("control_delayed", "evidence_only", "obligation_first", "baseline_then_guard")
EVIDENCE_STATES = {"present_verified", "present_unverified", "missing", "conflicting", "not_assessed"}
OBLIGATION_EVIDENCE_STATES = {"present_unverified", "missing", "conflicting"}
DECISIONS = {"approve", "request_changes", "abstain"}
OBLIGATION_LABELS = {"actionable_new", "already_covered", "incorrect", "unclear"}
RECORD_STATUSES = {"assigned", "exposed", "awaiting_outcome", "awaiting_audit", "complete", "withdrawn", "technical_failure"}
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TrialValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Assignment:
    arm: str
    block_index: int
    position_in_block: int
    assignment_digest: str


@dataclass(frozen=True)
class AuditSelection:
    selected: bool
    probability: float
    selection_digest: str
    score: float


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _key_bytes(key: bytes | str) -> bytes:
    raw = key.encode() if isinstance(key, str) else key
    if not isinstance(raw, bytes) or len(raw) < 32:
        raise TrialValidationError("trial keys must contain at least 32 bytes")
    return raw


def key_commitment(key: bytes | str) -> str:
    return hashlib.sha256(_key_bytes(key)).hexdigest()


def _hmac(key: bytes | str, domain: str, value: Mapping[str, Any]) -> str:
    return hmac.new(_key_bytes(key), domain.encode() + b"\0" + canonical_json(value), hashlib.sha256).hexdigest()


def record_digest(record: Mapping[str, Any]) -> str:
    body = dict(record)
    provenance = dict(body.get("provenance") or {})
    provenance.pop("record_digest", None)
    body["provenance"] = provenance
    return sha256_json(body)


def assignment_for(key: bytes | str, repository: str, eligible_index: int) -> Assignment:
    if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
        raise TrialValidationError("repository must be owner/name")
    if isinstance(eligible_index, bool) or not isinstance(eligible_index, int) or eligible_index < 1:
        raise TrialValidationError("eligible_index must be a positive integer")
    repository = repository.lower()
    block = (eligible_index - 1) // 8
    position = (eligible_index - 1) % 8
    slots = [(arm, copy) for arm in ARMS for copy in range(2)]
    slots.sort(key=lambda slot: _hmac(key, "assignment-slot-v1", {
        "trial_id": TRIAL_ID, "repository": repository, "block_index": block,
        "arm": slot[0], "replicate": slot[1],
    }))
    arm = slots[position][0]
    digest = _hmac(key, "assignment-proof-v1", {
        "trial_id": TRIAL_ID, "repository": repository, "eligible_index": eligible_index,
        "block_index": block, "position_in_block": position, "arm": arm,
    })
    return Assignment(arm, block, position, digest)


def verify_assignment(key: bytes | str, repository: str, eligible_index: int, arm: str, assignment_digest: str) -> bool:
    expected = assignment_for(key, repository, eligible_index)
    return hmac.compare_digest(expected.arm, arm) and hmac.compare_digest(expected.assignment_digest, assignment_digest)


def audit_selection_for(key: bytes | str, repository: str, eligible_index: int, head_sha: str, alerted: bool) -> AuditSelection:
    if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
        raise TrialValidationError("repository must be owner/name")
    if isinstance(eligible_index, bool) or not isinstance(eligible_index, int) or eligible_index < 1:
        raise TrialValidationError("eligible_index must be a positive integer")
    if not isinstance(head_sha, str) or not SHA40_RE.fullmatch(head_sha):
        raise TrialValidationError("head_sha must be a lowercase 40-character Git SHA")
    if not isinstance(alerted, bool):
        raise TrialValidationError("alerted must be a boolean")
    probability = 0.25 if alerted else 0.50
    digest = _hmac(key, "primary-audit-selection-v1", {
        "trial_id": TRIAL_ID, "repository": repository.lower(), "eligible_index": eligible_index,
        "head_sha": head_sha, "alerted": alerted,
    })
    score = int(digest[:16], 16) / 2**64
    return AuditSelection(score < probability, probability, digest, score)


def verify_audit_selection(key: bytes | str, repository: str, eligible_index: int, head_sha: str,
                           alerted: bool, selected: bool, selection_digest: str) -> bool:
    expected = audit_selection_for(key, repository, eligible_index, head_sha, alerted)
    return expected.selected is selected and hmac.compare_digest(expected.selection_digest, selection_digest)


def _parse_time(value: Any, field: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty ISO-8601 timestamp")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} is not a valid ISO-8601 timestamp")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{field} must include a timezone")
        return None
    return parsed


def _mapping(record: Mapping[str, Any], key: str, errors: list[str], optional: bool = False) -> Mapping[str, Any] | None:
    value = record.get(key)
    if value is None and optional:
        return None
    if not isinstance(value, Mapping):
        errors.append(f"{key} must be an object" + (" or null" if optional else ""))
        return None
    return value


def _expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
