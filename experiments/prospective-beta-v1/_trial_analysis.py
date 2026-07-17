"""Preregistered standard-library estimands and reporting."""
from __future__ import annotations

import hashlib
import math
import random
import statistics
from collections import Counter, defaultdict
from typing import Any, Callable, Iterable, Mapping

from _trial_core import ARMS, OBLIGATION_LABELS, TRIAL_ID

def wilson_interval(successes: int, total: int, z: float = 1.6448536269514722) -> dict[str, Any]:
    if total <= 0:
        return {"estimate": None, "lower": None, "upper": None, "successes": successes, "total": total}
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return {"estimate": p, "lower": max(0.0, center - half), "upper": min(1.0, center + half), "successes": successes, "total": total}


def _weighted_parts(record: Mapping[str, Any], numerator: Callable[[Mapping[str, Any]], int], denominator: Callable[[Mapping[str, Any]], int]) -> tuple[float, float]:
    if not record["audit_selection"]["primary_selected"] or not isinstance(record.get("adjudication"), Mapping):
        return 0.0, 0.0
    weight = 1.0 / float(record["audit_selection"]["probability"])
    return weight * numerator(record), weight * denominator(record)


def _cluster_interval(records: list[Mapping[str, Any]], numerator: Callable[[Mapping[str, Any]], int], denominator: Callable[[Mapping[str, Any]], int], seed: str) -> tuple[float | None, float | None]:
    clusters: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        clusters[str(record["repository"])].append(record)
    names = sorted(clusters)
    if len(names) < 2:
        return None, None
    rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16))
    values: list[float] = []
    for _ in range(2000):
        sample = [clusters[rng.choice(names)] for _ in names]
        num = den = 0.0
        for group in sample:
            for record in group:
                n, d = _weighted_parts(record, numerator, denominator)
                num += n; den += d
        if den: values.append(num / den)
    values.sort()
    if not values: return None, None
    return values[int(0.05 * (len(values) - 1))], values[int(0.95 * (len(values) - 1))]


def _weighted_metric(records: Iterable[Mapping[str, Any]], numerator: Callable[[Mapping[str, Any]], int], denominator: Callable[[Mapping[str, Any]], int], seed: str) -> dict[str, Any]:
    rows = list(records)
    num = den = 0.0
    for record in rows:
        n, d = _weighted_parts(record, numerator, denominator)
        num += n; den += d
    estimate = num / den if den else None
    lower, upper = _cluster_interval(rows, numerator, denominator, seed)
    return {"estimate": estimate, "lower": lower, "upper": upper, "weighted_numerator": num, "weighted_denominator": den}


def analyze_records(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = list(records)
    by_arm = {arm: [r for r in records if r["assignment"]["arm"] == arm] for arm in ARMS}
    repositories: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    labels = Counter()
    primary = no_alert_primary = missing = 0
    times = {arm: [] for arm in ARMS}
    corrected_repos: set[str] = set()
    for record in records:
        repositories[str(record["repository"])].append(record)
        arm = record["assignment"]["arm"]
        outcome = record.get("reviewer_outcome")
        if isinstance(outcome, Mapping): times[arm].append(float(outcome["review_time_minutes"]))
        else: missing += 1
        if record["audit_selection"]["primary_selected"]:
            primary += 1
            if not record["guard"]["alerted"]: no_alert_primary += 1
            adjudication = record.get("adjudication")
            if isinstance(adjudication, Mapping):
                labels.update(x["label"] for x in adjudication["obligation_labels"])
                baseline = record.get("baseline")
                if isinstance(baseline, Mapping) and isinstance(outcome, Mapping):
                    ref = adjudication["recommended_decision"]
                    if baseline["decision"] != ref and outcome["decision"] == ref:
                        corrected_repos.add(str(record["repository"]))
    total_labels = sum(labels[x] for x in OBLIGATION_LABELS)
    recall = _weighted_metric(records,
        lambda r: sum(bool(x["mapped_obligation_ids"]) for x in r["adjudication"]["material_risks"]),
        lambda r: len(r["adjudication"]["material_risks"]), "recall")
    arm_results: dict[str, Any] = {}
    for arm, rows in by_arm.items():
        reference = lambda r: r["adjudication"]["recommended_decision"]
        has_outcome = lambda r: int(isinstance(r.get("reviewer_outcome"), Mapping))
        accuracy = _weighted_metric(rows, lambda r: int(isinstance(r.get("reviewer_outcome"), Mapping) and r["reviewer_outcome"]["decision"] == reference(r)), has_outcome, f"accuracy-{arm}")
        has_pair = lambda r: int(isinstance(r.get("baseline"), Mapping) and isinstance(r.get("reviewer_outcome"), Mapping))
        correction = _weighted_metric(rows, lambda r: int(has_pair(r) and r["baseline"]["decision"] != reference(r) and r["reviewer_outcome"]["decision"] == reference(r)), has_pair, f"correction-{arm}")
        regression = _weighted_metric(rows, lambda r: int(has_pair(r) and r["baseline"]["decision"] == reference(r) and r["reviewer_outcome"]["decision"] != reference(r)), has_pair, f"regression-{arm}")
        arm_results[arm] = {"assigned": len(rows), "outcomes_observed": sum(has_outcome(r) for r in rows), "decision_accuracy": accuracy, "decision_correction": correction, "decision_regression": regression, "median_review_time_minutes": statistics.median(times[arm]) if times[arm] else None}
    def diff(a: Any, b: Any) -> float | None:
        return None if a is None or b is None else float(a) - float(b)
    return {
        "trial_id": TRIAL_ID,
        "record_count": len(records),
        "repository_count": len(repositories),
        "allocation": {arm: len(by_arm[arm]) for arm in ARMS},
        "missing_outcomes": {"count": missing, "rate": missing / len(records) if records else None},
        "primary_audits": primary,
        "no_alert_primary_audits": no_alert_primary,
        "actionable_new_precision": wilson_interval(labels["actionable_new"], total_labels),
        "correct_obligation_precision": wilson_interval(labels["actionable_new"] + labels["already_covered"], total_labels),
        "obligation_label_counts": {x: labels[x] for x in sorted(OBLIGATION_LABELS)},
        "audited_missed_risk_recall": recall,
        "arms": arm_results,
        "confirmatory_point_differences": {
            "baseline_then_guard_minus_control_delayed_accuracy": diff(arm_results["baseline_then_guard"]["decision_accuracy"]["estimate"], arm_results["control_delayed"]["decision_accuracy"]["estimate"]),
            "baseline_then_guard_minus_obligation_first_accuracy": diff(arm_results["baseline_then_guard"]["decision_accuracy"]["estimate"], arm_results["obligation_first"]["decision_accuracy"]["estimate"]),
            "evidence_only_minus_control_delayed_accuracy": diff(arm_results["evidence_only"]["decision_accuracy"]["estimate"], arm_results["control_delayed"]["decision_accuracy"]["estimate"]),
        },
        "independent_repositories_with_observed_correction": len(corrected_repos),
        "per_repository": {name: {"records": len(rows), "allocation": dict(Counter(r["assignment"]["arm"] for r in rows))} for name, rows in sorted(repositories.items())},
        "claim_boundary": "Pilot estimates apply only to enrolled repositories, the preregistered eligible-PR population, the frozen Guard engine and policy, and observed missingness.",
    }


def format_analysis_markdown(analysis: Mapping[str, Any]) -> str:
    def pct(value: Any) -> str:
        return "n/a" if value is None else f"{100 * float(value):.1f}%"
    lines = ["# Busleyden prospective beta analysis", "", f"- Records: {analysis['record_count']}", f"- Repositories: {analysis['repository_count']}", f"- Primary audits: {analysis['primary_audits']}", f"- No-alert primary audits: {analysis['no_alert_primary_audits']}", "", "## Primary estimands", "", "| Estimand | Estimate | 90% interval |", "|---|---:|---:|"]
    for label, key in (("Actionable-new precision", "actionable_new_precision"), ("Correct-obligation precision", "correct_obligation_precision"), ("Audited missed-risk recall (weighted)", "audited_missed_risk_recall")):
        metric = analysis[key]
        interval = "n/a" if metric["lower"] is None else f"{pct(metric['lower'])}–{pct(metric['upper'])}"
        lines.append(f"| {label} | {pct(metric['estimate'])} | {interval} |")
    lines += ["", "## Randomized arms", "", "| Arm | Assigned | Outcomes | Weighted accuracy | Corrections | Regressions | Median minutes |", "|---|---:|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        row = analysis["arms"][arm]
        median = "n/a" if row["median_review_time_minutes"] is None else f"{row['median_review_time_minutes']:.1f}"
        lines.append(f"| {arm} | {row['assigned']} | {row['outcomes_observed']} | {pct(row['decision_accuracy']['estimate'])} | {pct(row['decision_correction']['estimate'])} | {pct(row['decision_regression']['estimate'])} | {median} |")
    lines += ["", "## Interpretation limits", "", "- Audit-based decision and recall estimates use inverse-probability weights.", "- Missing outcomes remain missing; they are not scored as successes or failures.", "- Pooled estimates are pilot summaries; repository-level heterogeneity remains visible.", "- Blinded adjudication is an operational reference, not infallible ground truth.", "", "> " + str(analysis["claim_boundary"]), ""]
    return "\n".join(lines)
