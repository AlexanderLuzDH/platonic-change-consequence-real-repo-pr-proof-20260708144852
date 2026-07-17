"""Structural and Guard-output validation for trial records."""
from __future__ import annotations

from typing import Any, Mapping

from _trial_core import (
    ARMS, EVIDENCE_STATES, OBLIGATION_EVIDENCE_STATES, RECORD_STATUSES,
    REPOSITORY_RE, SCHEMA_VERSION, SHA40_RE, SHA256_RE, TRIAL_ID,
    _expect, _is_int, _mapping,
)


def _sha(value: Any, regex: Any) -> bool:
    return isinstance(value, str) and bool(regex.fullmatch(value))


def validate_base(record: Mapping[str, Any], errors: list[str]) -> dict[str, Any]:
    for ok, message in (
        (record.get("schema_version") == SCHEMA_VERSION, "schema_version must be 1.0"),
        (record.get("trial_id") == TRIAL_ID, f"trial_id must be {TRIAL_ID}"),
        (isinstance(record.get("record_id"), str) and bool(record.get("record_id")), "record_id is required"),
        (record.get("record_status") in RECORD_STATUSES, "record_status is invalid"),
        (record.get("intention_to_treat") is True, "intention_to_treat must be true"),
        (isinstance(record.get("repository"), str) and bool(REPOSITORY_RE.fullmatch(record.get("repository", ""))), "repository must be owner/name"),
    ):
        _expect(ok, message, errors)

    names = ("pr", "enrollment", "eligibility", "assignment", "guard", "audit_selection", "status", "provenance")
    values: dict[str, Any] = {name: (_mapping(record, name, errors) or {}) for name in names}
    for name in ("baseline", "exposure", "reviewer_outcome", "feedback", "adjudication"):
        values[name] = _mapping(record, name, errors, optional=True)
    pr, enrollment, eligibility = values["pr"], values["enrollment"], values["eligibility"]
    assignment, guard = values["assignment"], values["guard"]

    for ok, message in (
        (_is_int(pr.get("number")) and pr.get("number", 0) > 0, "pr.number must be positive"),
        (isinstance(pr.get("url"), str) and pr.get("url", "").startswith("https://github.com/"), "pr.url must be a GitHub URL"),
        (_sha(pr.get("base_sha"), SHA40_RE), "pr.base_sha must be lowercase SHA-1"),
        (_sha(pr.get("head_sha"), SHA40_RE), "pr.head_sha must be lowercase SHA-1"),
        (_is_int(pr.get("eligible_index")) and pr.get("eligible_index", 0) > 0, "pr.eligible_index must be positive"),
        (_is_int(pr.get("prior_guard_exposures")) and pr.get("prior_guard_exposures", -1) >= 0, "pr.prior_guard_exposures must be non-negative"),
        (isinstance(pr.get("changed_files"), list), "pr.changed_files must be an array"),
        (isinstance(pr.get("audit_snapshot_refs"), list) and bool(pr.get("audit_snapshot_refs")), "pr.audit_snapshot_refs must be a non-empty array"),
        (_sha(pr.get("audit_snapshot_digest"), SHA256_RE), "pr.audit_snapshot_digest must be SHA-256"),
        (eligibility.get("eligible") is True, "eligibility.eligible must be true"),
        (enrollment.get("dependency_pr_policy") in {"include", "exclude"}, "enrollment.dependency_pr_policy is invalid"),
        (_sha(enrollment.get("assignment_key_commitment"), SHA256_RE), "enrollment.assignment_key_commitment must be SHA-256"),
        (_sha(enrollment.get("audit_key_commitment"), SHA256_RE), "enrollment.audit_key_commitment must be SHA-256"),
        (assignment.get("arm") in ARMS, "assignment.arm is invalid"),
        (_is_int(assignment.get("block_index")) and assignment.get("block_index", -1) >= 0, "assignment.block_index must be non-negative"),
        (_is_int(assignment.get("position_in_block")) and 0 <= assignment.get("position_in_block", -1) <= 7, "assignment.position_in_block must be 0..7"),
        (_sha(assignment.get("assignment_digest"), SHA256_RE), "assignment.assignment_digest must be SHA-256"),
    ):
        _expect(ok, message, errors)

    execution = guard.get("execution_status")
    states = guard.get("evidence_states") if isinstance(guard.get("evidence_states"), list) else []
    obligations = guard.get("obligations") if isinstance(guard.get("obligations"), list) else []
    _expect(execution in {"success", "failure"}, "guard.execution_status is invalid", errors)
    _expect(isinstance(guard.get("alerted"), bool), "guard.alerted must be boolean", errors)
    _expect(isinstance(guard.get("evidence_states"), list), "guard.evidence_states must be an array", errors)
    _expect(isinstance(guard.get("obligations"), list), "guard.obligations must be an array", errors)
    if execution == "failure":
        _expect(isinstance(guard.get("failure_reason"), str) and bool(guard.get("failure_reason")), "failed Guard execution requires failure_reason", errors)
        _expect(not states and not obligations, "failed Guard execution cannot emit evidence or obligations", errors)
    if execution == "success":
        _expect(guard.get("failure_reason") is None, "successful Guard execution must have null failure_reason", errors)

    evidence: dict[str, str] = {}
    for item in states:
        if not isinstance(item, Mapping):
            errors.append("guard.evidence_states entries must be objects"); continue
        eid, state = item.get("evidence_id"), item.get("state")
        _expect(isinstance(eid, str) and bool(eid), "evidence_id is required", errors)
        _expect(state in EVIDENCE_STATES, "evidence state is invalid", errors)
        if isinstance(eid, str):
            _expect(eid not in evidence, f"duplicate evidence_id {eid}", errors)
            evidence[eid] = str(state)

    obligation_ids: set[str] = set()
    for item in obligations:
        if not isinstance(item, Mapping):
            errors.append("guard.obligations entries must be objects"); continue
        oid, eid = item.get("obligation_id"), item.get("evidence_id")
        _expect(isinstance(oid, str) and bool(oid), "obligation_id is required", errors)
        if isinstance(oid, str):
            _expect(oid not in obligation_ids, f"duplicate obligation_id {oid}", errors)
            obligation_ids.add(oid)
        _expect(eid in evidence, f"obligation {oid} references unknown evidence", errors)
        if eid in evidence and evidence[eid] not in OBLIGATION_EVIDENCE_STATES:
            errors.append(f"obligation {oid} cannot arise from {evidence[eid]}")
    _expect(bool(obligations) is bool(guard.get("alerted")), "guard.alerted must equal whether obligations were emitted", errors)
    values["obligation_ids"] = obligation_ids
    values["execution"] = execution
    return values
