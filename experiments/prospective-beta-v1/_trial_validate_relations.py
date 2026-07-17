"""Timing, treatment, adjudication, and integrity validation."""
from __future__ import annotations

import hmac
from typing import Any, Mapping

from _trial_core import DECISIONS, OBLIGATION_LABELS, SHA256_RE, _expect, _parse_time, record_digest


def validate_relations(record: Mapping[str, Any], values: Mapping[str, Any], errors: list[str], *, verify_digest: bool) -> None:
    pr, enrollment, eligibility = values["pr"], values["enrollment"], values["eligibility"]
    assignment, guard, audit = values["assignment"], values["guard"], values["audit_selection"]
    status, provenance = values["status"], values["provenance"]
    baseline, exposure = values["baseline"], values["exposure"]
    outcome, feedback, adjudication = values["reviewer_outcome"], values["feedback"], values["adjudication"]
    obligation_ids = values["obligation_ids"]

    expected_p = 0.25 if guard.get("alerted") else 0.50
    _expect(audit.get("probability") == expected_p, "audit_selection.probability does not match alert stratum", errors)
    _expect(isinstance(audit.get("primary_selected"), bool), "audit_selection.primary_selected must be boolean", errors)
    _expect(isinstance(audit.get("safety_audit"), bool), "audit_selection.safety_audit must be boolean", errors)

    arm = assignment.get("arm")
    components = {
        "control_delayed": {"evidence_states", "obligations"},
        "evidence_only": {"evidence_states"},
        "obligation_first": {"evidence_states", "obligations"},
        "baseline_then_guard": {"evidence_states", "obligations"},
    }
    if exposure is not None and arm in components:
        _expect(isinstance(exposure.get("components_shown"), list) and set(exposure["components_shown"]) == components[arm], "exposure.components_shown does not match arm", errors)
        _expect(exposure.get("delayed_until_outcome") is (arm == "control_delayed"), "exposure.delayed_until_outcome does not match arm", errors)
    if arm in {"evidence_only", "baseline_then_guard"}:
        _expect(baseline is not None, f"{arm} requires a baseline", errors)
    if arm == "obligation_first":
        _expect(baseline is None, "obligation_first must not claim a pre-exposure baseline", errors)

    times = {
        "opened": _parse_time(pr.get("opened_at"), "pr.opened_at", errors),
        "activated": _parse_time(enrollment.get("activated_at"), "enrollment.activated_at", errors),
        "determined": _parse_time(eligibility.get("determined_at"), "eligibility.determined_at", errors),
        "assigned": _parse_time(assignment.get("assigned_at"), "assignment.assigned_at", errors),
        "generated": _parse_time(guard.get("generated_at"), "guard.generated_at", errors),
        "selected": _parse_time(audit.get("selected_at"), "audit_selection.selected_at", errors),
        "baseline": _parse_time(baseline.get("recorded_at"), "baseline.recorded_at", errors) if baseline else None,
        "exposed": _parse_time(exposure.get("occurred_at"), "exposure.occurred_at", errors) if exposure else None,
        "outcome": _parse_time(outcome.get("recorded_at"), "reviewer_outcome.recorded_at", errors) if outcome else None,
    }
    for before, after, message in (
        ("activated", "opened", "PR must open after repository activation"),
        ("opened", "determined", "eligibility must follow PR opening"),
        ("determined", "assigned", "assignment must follow eligibility"),
        ("assigned", "generated", "Guard generation must follow assignment"),
        ("generated", "selected", "audit selection must follow Guard generation"),
        ("generated", "exposed", "exposure must follow Guard generation"),
    ):
        if times[before] and times[after]: _expect(times[after] >= times[before], message, errors)
    if times["baseline"] and times["exposed"]: _expect(times["baseline"] < times["exposed"], "baseline must precede Guard exposure", errors)
    if arm == "control_delayed" and times["exposed"] and times["outcome"] and not status.get("safety_override"):
        _expect(times["exposed"] >= times["outcome"], "delayed control exposure must follow outcome", errors)

    if outcome: _expect(outcome.get("decision") in DECISIONS, "reviewer_outcome.decision is invalid", errors)
    if baseline: _expect(baseline.get("decision") in DECISIONS, "baseline.decision is invalid", errors)
    if feedback: _expect(feedback.get("subjective_label") in {"useful", "noisy", "missed_something", "neutral", "not_provided"}, "feedback.subjective_label is invalid", errors)
    if adjudication:
        _expect(adjudication.get("recommended_decision") in DECISIONS, "adjudication.recommended_decision is invalid", errors)
        for label in adjudication.get("obligation_labels", []):
            if isinstance(label, Mapping):
                _expect(label.get("label") in OBLIGATION_LABELS, "obligation adjudication label is invalid", errors)
                _expect(label.get("obligation_id") in obligation_ids, "adjudication references unknown obligation", errors)
        for risk in adjudication.get("material_risks", []):
            if isinstance(risk, Mapping):
                _expect(risk.get("material") is True, "adjudicated risks must be material", errors)
                for oid in risk.get("mapped_obligation_ids", []): _expect(oid in obligation_ids, "material risk maps to unknown obligation", errors)
        _expect(bool(audit.get("primary_selected") or audit.get("safety_audit")), "adjudication requires an audit", errors)

    _expect(status.get("technical_failure") is (record.get("record_status") == "technical_failure"), "technical failure status mismatch", errors)
    _expect(status.get("missing_outcome") is (outcome is None), "status.missing_outcome must match reviewer_outcome", errors)
    if record.get("record_status") == "technical_failure": _expect(values["execution"] == "failure", "technical_failure record requires failed Guard execution", errors)
    if verify_digest:
        digest = provenance.get("record_digest")
        valid = isinstance(digest, str) and bool(SHA256_RE.fullmatch(digest))
        _expect(valid, "provenance.record_digest must be SHA-256", errors)
        if valid: _expect(hmac.compare_digest(digest, record_digest(record)), "provenance.record_digest does not match record", errors)
