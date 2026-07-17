"""Cross-field record validation, blinded packets, and loading."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from _trial_core import TrialValidationError, sha256_json
from _trial_validate_base import validate_base
from _trial_validate_relations import validate_relations


def validate_record(record: Any, *, verify_digest: bool = True) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, Mapping):
        return ["record must be an object"]
    values = validate_base(record, errors)
    validate_relations(record, values, errors, verify_digest=verify_digest)
    return errors


def make_audit_packet(record: Mapping[str, Any]) -> dict[str, Any]:
    errors = validate_record(record)
    if errors: raise TrialValidationError("record is invalid: " + "; ".join(errors))
    pr = record["pr"]
    packet = {
        "packet_schema_version": "1.0", "trial_id": record["trial_id"],
        "record_id": record["record_id"], "repository": record["repository"],
        "pr": {name: pr[name] for name in ("base_sha", "head_sha", "changed_files", "audit_snapshot_digest", "audit_snapshot_refs")},
        "audit_scope": "Independently identify material risks and record a review recommendation. Do not open the live PR conversation before stage 1 is frozen.",
    }
    packet["packet_digest"] = sha256_json(packet)
    return packet


def load_records(path: str | Path) -> list[dict[str, Any]]:
    root = Path(path)
    files = [root] if root.is_file() else sorted(root.rglob("*.json"))
    records = []
    for file in files:
        if file.name in {"PROTOCOL_MANIFEST.json", "ACTIVATION.json", "ACTIVATION.example.json"}: continue
        value = json.loads(file.read_text())
        errors = validate_record(value)
        if errors: raise TrialValidationError(f"{file}: " + "; ".join(errors))
        records.append(value)
    return records
