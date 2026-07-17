from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trial_tools import (  # noqa: E402
    ARMS,
    analyze_records,
    assignment_for,
    audit_selection_for,
    make_audit_packet,
    record_digest,
    validate_record,
    verify_assignment,
    verify_audit_selection,
)

ASSIGNMENT_KEY = "test-assignment-key-" + "A" * 48
AUDIT_KEY = "test-audit-key-" + "B" * 48


class AssignmentTests(unittest.TestCase):
    def test_each_block_is_balanced(self) -> None:
        for block in range(25):
            start = block * 8 + 1
            assignments = [
                assignment_for(ASSIGNMENT_KEY, "Example/Repo", index).arm
                for index in range(start, start + 8)
            ]
            self.assertEqual(set(assignments), set(ARMS))
            for arm in ARMS:
                self.assertEqual(assignments.count(arm), 2)

    def test_assignment_is_deterministic_repo_bound_and_verifiable(self) -> None:
        first = assignment_for(ASSIGNMENT_KEY, "example/repo", 19)
        second = assignment_for(ASSIGNMENT_KEY, "EXAMPLE/REPO", 19)
        other = assignment_for(ASSIGNMENT_KEY, "example/other", 19)
        self.assertEqual(first, second)
        self.assertNotEqual(first.assignment_digest, other.assignment_digest)
        self.assertTrue(
            verify_assignment(
                ASSIGNMENT_KEY,
                "example/repo",
                19,
                first.arm,
                first.assignment_digest,
            )
        )
        self.assertFalse(
            verify_assignment(
                ASSIGNMENT_KEY,
                "example/repo",
                19,
                first.arm,
                "0" * 64,
            )
        )


class AuditSelectionTests(unittest.TestCase):
    def test_selection_is_deterministic_and_stratified(self) -> None:
        kwargs = dict(
            repository="example/repo",
            eligible_index=1,
            head_sha="b" * 40,
        )
        alert = audit_selection_for(AUDIT_KEY, alerted=True, **kwargs)
        no_alert = audit_selection_for(AUDIT_KEY, alerted=False, **kwargs)
        self.assertEqual(alert, audit_selection_for(AUDIT_KEY, alerted=True, **kwargs))
        self.assertEqual(alert.probability, 0.25)
        self.assertEqual(no_alert.probability, 0.50)
        self.assertNotEqual(alert.selection_digest, no_alert.selection_digest)
        self.assertTrue(
            verify_audit_selection(
                AUDIT_KEY,
                kwargs["repository"],
                kwargs["eligible_index"],
                kwargs["head_sha"],
                True,
                alert.selected,
                alert.selection_digest,
            )
        )

    def test_selection_rate_tracks_preregistered_probabilities(self) -> None:
        alert_selected = 0
        no_alert_selected = 0
        total = 10_000
        for index in range(1, total + 1):
            sha = f"{index:040x}"[-40:]
            alert_selected += audit_selection_for(
                AUDIT_KEY, "example/repo", index, sha, True
            ).selected
            no_alert_selected += audit_selection_for(
                AUDIT_KEY, "example/repo", index, sha, False
            ).selected
        self.assertLess(abs(alert_selected / total - 0.25), 0.02)
        self.assertLess(abs(no_alert_selected / total - 0.50), 0.02)


class RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads((ROOT / "fixtures" / "valid-record.json").read_text())

    @staticmethod
    def redigest(record: dict) -> None:
        record["provenance"]["record_digest"] = record_digest(record)

    def test_fixture_is_valid(self) -> None:
        self.assertEqual(validate_record(copy.deepcopy(self.record)), [])

    def test_schema_is_valid_json(self) -> None:
        schema = json.loads((ROOT / "trial-record.schema.json").read_text())
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertIn("provenance", schema["required"])

    def test_timing_violation_is_rejected(self) -> None:
        record = copy.deepcopy(self.record)
        record["baseline"]["recorded_at"] = "2026-07-17T00:08:00Z"
        self.redigest(record)
        errors = validate_record(record)
        self.assertTrue(any("baseline must precede Guard exposure" in error for error in errors))

    def test_obligation_must_follow_unsatisfied_evidence(self) -> None:
        record = copy.deepcopy(self.record)
        record["guard"]["evidence_states"][0]["state"] = "present_verified"
        self.redigest(record)
        errors = validate_record(record)
        self.assertTrue(any("cannot arise from present_verified" in error for error in errors))

    def test_digest_detects_tampering(self) -> None:
        record = copy.deepcopy(self.record)
        record["reviewer_outcome"]["decision"] = "approve"
        errors = validate_record(record)
        self.assertIn("provenance.record_digest does not match record", errors)

    def test_arm_specific_exposure_is_enforced(self) -> None:
        record = copy.deepcopy(self.record)
        record["exposure"]["components_shown"] = ["obligations"]
        self.redigest(record)
        errors = validate_record(record)
        self.assertIn("exposure.components_shown does not match arm", errors)

    def test_audit_packet_does_not_leak_treatment_or_outcomes(self) -> None:
        packet = make_audit_packet(copy.deepcopy(self.record))
        encoded = json.dumps(packet, sort_keys=True)
        for forbidden in (
            "baseline_then_guard",
            "assignment",
            "obligations",
            "subjective_label",
            "The evidence distinction changed",
            "request_changes",
            "reviewer_outcome",
            "pull/123",
        ):
            self.assertNotIn(forbidden, encoded)
        self.assertIn("packet_digest", packet)
        self.assertEqual(packet["pr"]["audit_snapshot_digest"], "9" * 64)

    def test_summary_estimands(self) -> None:
        summary = analyze_records([self.record])
        self.assertEqual(summary["record_count"], 1)
        self.assertEqual(summary["actionable_new_precision"]["estimate"], 1.0)
        self.assertEqual(summary["audited_missed_risk_recall"]["estimate"], 1.0)
        self.assertEqual(
            summary["arms"]["baseline_then_guard"]["decision_correction"]["estimate"],
            1.0,
        )

    def test_recall_uses_inverse_probability_weights(self) -> None:
        no_alert = copy.deepcopy(self.record)
        no_alert["record_id"] = "example-org__example-python__86__pr-124"
        no_alert["pr"]["number"] = 124
        no_alert["pr"]["url"] = "https://github.com/example-org/example-python/pull/124"
        no_alert["pr"]["eligible_index"] = 86
        no_alert["pr"]["head_sha"] = "6" * 40
        no_alert["assignment"]["block_index"] = 10
        no_alert["assignment"]["position_in_block"] = 5
        no_alert["assignment"]["assignment_digest"] = "7" * 64
        no_alert["guard"]["alerted"] = False
        no_alert["guard"]["evidence_states"] = []
        no_alert["guard"]["obligations"] = []
        no_alert["audit_selection"]["probability"] = 0.5
        no_alert["audit_selection"]["selection_digest"] = "8" * 64
        no_alert["adjudication"]["material_risks"][0]["mapped_obligation_ids"] = []
        no_alert["adjudication"]["obligation_labels"] = []
        self.redigest(no_alert)
        self.assertEqual(validate_record(no_alert), [])

        summary = analyze_records([self.record, no_alert])
        # Alert audit weight 4 detects 1/1; no-alert weight 2 detects 0/1.
        self.assertAlmostEqual(summary["audited_missed_risk_recall"]["estimate"], 4 / 6)

    def test_technical_failure_remains_in_intention_to_treat_ledger(self) -> None:
        record = copy.deepcopy(self.record)
        record["record_id"] = "example-org__example-python__85__pr-123-failure"
        record["record_status"] = "technical_failure"
        record["guard"]["execution_status"] = "failure"
        record["guard"]["failure_reason"] = "engine timed out before producing evidence"
        record["guard"]["alerted"] = False
        record["guard"]["evidence_states"] = []
        record["guard"]["obligations"] = []
        record["audit_selection"]["probability"] = 0.5
        record["reviewer_outcome"] = None
        record["feedback"] = None
        record["adjudication"] = None
        record["exposure"] = None
        record["status"]["technical_failure"] = True
        record["status"]["missing_outcome"] = True
        self.redigest(record)
        self.assertEqual(validate_record(record), [])

    def test_missing_required_structure_is_rejected(self) -> None:
        record = copy.deepcopy(self.record)
        del record["assignment"]
        self.redigest(record)
        errors = validate_record(record)
        self.assertIn("assignment must be an object", errors)


if __name__ == "__main__":
    unittest.main()
