#!/usr/bin/env python3
"""Synthetic Health Connect replay for the dyslipidemia intensity-frequency path.

This is KDB construction evidence only. It checks whether official-shape
ActivityIntensityRecord-like rows can be transformed into the existing
dyslipidemia weekly alternative output shape. It does not create Android runtime
ingestion, product data access, coaching delivery, score, diagnosis, exercise
prescription, frequency, or deduplication authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


OUTPUT = Path(__file__).with_name(
    "health_connect_dyslipidemia_activity_intensity_replay_20260924.json"
)

MODERATE_VALUES = {
    "MODERATE",
    "MODERATE_INTENSITY",
    "ACTIVITY_INTENSITY_TYPE_MODERATE",
    "ActivityIntensityRecord.ACTIVITY_INTENSITY_TYPE_MODERATE",
    1,
}
VIGOROUS_VALUES = {
    "VIGOROUS",
    "VIGOROUS_INTENSITY",
    "ACTIVITY_INTENSITY_TYPE_VIGOROUS",
    "ActivityIntensityRecord.ACTIVITY_INTENSITY_TYPE_VIGOROUS",
    2,
}
MINIMUM_QUALIFIED_INTERVAL_MINUTES = 10.0


def _metadata(package_name: str = "com.sec.android.app.shealth") -> dict[str, Any]:
    return {
        "dataOrigin": {"packageName": package_name},
        "recordingMethod": "RECORDING_METHOD_AUTOMATICALLY_RECORDED",
        "device": {"manufacturer": "Samsung", "model": "Galaxy Watch"},
    }


def _record(start: str, end: str, intensity: Any, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "recordType": "ActivityIntensityRecord",
        "startTime": start,
        "endTime": end,
        "intensity": intensity,
    }
    if metadata is not None:
        record["metadata"] = metadata
    return record


SYNTHETIC_CASES: list[dict[str, Any]] = [
    {
        "case_id": "positive_below_alternative",
        "fixture_kind": "positive_trigger_example",
        "input_fixture": {
            "provider_platform": "health_connect",
            "confirmed_dyslipidemia_context": True,
            "observed_provider_week_complete": True,
            "overlap_duplicate_ambiguity_present": False,
            "week_start_local_date": "2026-09-14",
            "records": [
                _record("2026-09-14T07:00:00+09:00", "2026-09-14T07:20:00+09:00", "MODERATE", metadata=_metadata()),
                _record("2026-09-16T07:00:00+09:00", "2026-09-16T07:18:00+09:00", "MODERATE", metadata=_metadata()),
                _record("2026-09-18T07:00:00+09:00", "2026-09-18T07:15:00+09:00", "MODERATE", metadata=_metadata()),
                _record("2026-09-20T09:00:00+09:00", "2026-09-20T09:12:00+09:00", "VIGOROUS", metadata=_metadata()),
            ],
        },
        "expected_derived_output": {
            "context_present": True,
            "provider_platform": "health_connect",
            "qualified_moderate_aerobic_session_days_per_week": 3,
            "qualified_vigorous_aerobic_session_days_per_week": 1,
            "moderate_threshold_distinct_days": 5,
            "vigorous_threshold_distinct_days": 3,
            "trigger_evidence_mode": "health_connect_activity_intensity_frequency_context",
            "copy_action": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
            "null_reason": None,
        },
    },
    {
        "case_id": "short_interval_below_minimum_no_trigger",
        "fixture_kind": "no_trigger_example",
        "input_fixture": {
            "provider_platform": "health_connect",
            "confirmed_dyslipidemia_context": True,
            "observed_provider_week_complete": True,
            "overlap_duplicate_ambiguity_present": False,
            "week_start_local_date": "2026-09-14",
            "records": [
                _record("2026-09-14T07:00:00+09:00", "2026-09-14T07:05:00+09:00", "MODERATE", metadata=_metadata()),
            ],
        },
        "expected_derived_output": {
            "context_present": False,
            "provider_platform": "health_connect",
            "qualified_moderate_aerobic_session_days_per_week": 0,
            "qualified_vigorous_aerobic_session_days_per_week": 0,
            "moderate_threshold_distinct_days": 5,
            "vigorous_threshold_distinct_days": 3,
            "trigger_evidence_mode": "health_connect_activity_intensity_frequency_context",
            "copy_action": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
            "null_reason": "no_qualified_intensity_session_day",
        },
    },
    {
        "case_id": "moderate_threshold_met_no_trigger",
        "fixture_kind": "no_trigger_example",
        "input_fixture": {
            "provider_platform": "health_connect",
            "confirmed_dyslipidemia_context": True,
            "observed_provider_week_complete": True,
            "overlap_duplicate_ambiguity_present": False,
            "week_start_local_date": "2026-09-14",
            "records": [
                _record(f"2026-09-{day:02d}T07:00:00+09:00", f"2026-09-{day:02d}T07:12:00+09:00", "MODERATE", metadata=_metadata())
                for day in (14, 15, 16, 17, 18)
            ],
        },
        "expected_derived_output": {
            "context_present": False,
            "provider_platform": "health_connect",
            "qualified_moderate_aerobic_session_days_per_week": 5,
            "qualified_vigorous_aerobic_session_days_per_week": 0,
            "moderate_threshold_distinct_days": 5,
            "vigorous_threshold_distinct_days": 3,
            "copy_action": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
            "null_reason": "weekly_aerobic_intensity_alternative_threshold_met",
        },
    },
    {
        "case_id": "vigorous_threshold_met_no_trigger",
        "fixture_kind": "no_trigger_example",
        "input_fixture": {
            "provider_platform": "health_connect",
            "confirmed_dyslipidemia_context": True,
            "observed_provider_week_complete": True,
            "overlap_duplicate_ambiguity_present": False,
            "week_start_local_date": "2026-09-14",
            "records": [
                _record(f"2026-09-{day:02d}T09:00:00+09:00", f"2026-09-{day:02d}T09:10:00+09:00", "VIGOROUS", metadata=_metadata())
                for day in (14, 16, 18)
            ],
        },
        "expected_derived_output": {
            "context_present": False,
            "provider_platform": "health_connect",
            "qualified_moderate_aerobic_session_days_per_week": 0,
            "qualified_vigorous_aerobic_session_days_per_week": 3,
            "moderate_threshold_distinct_days": 5,
            "vigorous_threshold_distinct_days": 3,
            "copy_action": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
            "null_reason": "weekly_aerobic_intensity_alternative_threshold_met",
        },
    },
    {
        "case_id": "missing_dyslipidemia_context_no_trigger",
        "fixture_kind": "no_trigger_example",
        "input_fixture": {
            "provider_platform": "health_connect",
            "confirmed_dyslipidemia_context": False,
            "observed_provider_week_complete": True,
            "overlap_duplicate_ambiguity_present": False,
            "week_start_local_date": "2026-09-14",
            "records": [
                _record("2026-09-14T07:00:00+09:00", "2026-09-14T07:20:00+09:00", "MODERATE", metadata=_metadata()),
            ],
        },
        "expected_derived_output": {
            "context_present": False,
            "copy_action": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
            "null_reason": "dyslipidemia_context_not_confirmed",
        },
    },
    {
        "case_id": "missing_source_identity_no_trigger",
        "fixture_kind": "no_trigger_example",
        "input_fixture": {
            "provider_platform": "health_connect",
            "confirmed_dyslipidemia_context": True,
            "observed_provider_week_complete": True,
            "overlap_duplicate_ambiguity_present": False,
            "week_start_local_date": "2026-09-14",
            "records": [
                _record("2026-09-14T07:00:00+09:00", "2026-09-14T07:20:00+09:00", "MODERATE"),
            ],
        },
        "expected_derived_output": {
            "context_present": False,
            "copy_action": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
            "null_reason": "missing_source_identity",
        },
    },
    {
        "case_id": "unsupported_provider_no_trigger",
        "fixture_kind": "no_trigger_example",
        "input_fixture": {
            "provider_platform": "samsung_health_export",
            "confirmed_dyslipidemia_context": True,
            "observed_provider_week_complete": True,
            "overlap_duplicate_ambiguity_present": False,
            "week_start_local_date": "2026-09-14",
            "records": [
                _record("2026-09-14T07:00:00+09:00", "2026-09-14T07:20:00+09:00", "MODERATE", metadata=_metadata()),
            ],
        },
        "expected_derived_output": {
            "context_present": False,
            "copy_action": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
            "null_reason": "unsupported_provider_platform",
        },
    },
    {
        "case_id": "incomplete_week_no_trigger",
        "fixture_kind": "no_trigger_example",
        "input_fixture": {
            "provider_platform": "health_connect",
            "confirmed_dyslipidemia_context": True,
            "observed_provider_week_complete": False,
            "overlap_duplicate_ambiguity_present": False,
            "week_start_local_date": "2026-09-14",
            "records": [
                _record("2026-09-14T07:00:00+09:00", "2026-09-14T07:20:00+09:00", "MODERATE", metadata=_metadata()),
            ],
        },
        "expected_derived_output": {
            "context_present": False,
            "copy_action": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
            "null_reason": "missing_observed_week_source",
        },
    },
    {
        "case_id": "duplicate_overlap_ambiguity_no_trigger",
        "fixture_kind": "no_trigger_example",
        "input_fixture": {
            "provider_platform": "health_connect",
            "confirmed_dyslipidemia_context": True,
            "observed_provider_week_complete": True,
            "overlap_duplicate_ambiguity_present": True,
            "week_start_local_date": "2026-09-14",
            "records": [
                _record("2026-09-14T07:00:00+09:00", "2026-09-14T07:20:00+09:00", "MODERATE", metadata=_metadata()),
                _record("2026-09-14T07:10:00+09:00", "2026-09-14T07:30:00+09:00", "MODERATE", metadata=_metadata()),
            ],
        },
        "expected_derived_output": {
            "context_present": False,
            "copy_action": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
            "null_reason": "unresolved_overlap_or_duplicate_coverage",
        },
    },
]


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _source_identity_present(record: dict[str, Any]) -> bool:
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        return False
    origin = metadata.get("dataOrigin")
    return isinstance(origin, dict) and isinstance(origin.get("packageName"), str) and bool(origin["packageName"].strip())


def _record_type_is_activity_intensity(record: dict[str, Any]) -> bool:
    value = record.get("recordType") or record.get("typeName")
    return value in (
        "ActivityIntensityRecord",
        "androidx.health.connect.client.records.ActivityIntensityRecord",
    )


def _intensity_kind(value: Any) -> str | None:
    if isinstance(value, str):
        normalized: Any = value.strip()
    else:
        normalized = value
    if normalized in MODERATE_VALUES:
        return "moderate"
    if normalized in VIGOROUS_VALUES:
        return "vigorous"
    return None


def evaluate_dyslipidemia_activity_intensity_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate the synthetic DYS Health Connect output contract candidate."""
    base = {
        "context_present": False,
        "provider_platform": fixture.get("provider_platform"),
        "moderate_threshold_distinct_days": 5,
        "vigorous_threshold_distinct_days": 3,
        "copy_action": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
    }
    if fixture.get("provider_platform") != "health_connect":
        return {**base, "null_reason": "unsupported_provider_platform"}
    if fixture.get("confirmed_dyslipidemia_context") is not True:
        return {**base, "null_reason": "dyslipidemia_context_not_confirmed"}
    if fixture.get("observed_provider_week_complete") is not True:
        return {**base, "null_reason": "missing_observed_week_source"}
    if fixture.get("overlap_duplicate_ambiguity_present") is True:
        return {**base, "null_reason": "unresolved_overlap_or_duplicate_coverage"}

    records = fixture.get("records")
    if not isinstance(records, list):
        return {**base, "null_reason": "missing_activity_intensity_record"}

    moderate_days: set[str] = set()
    vigorous_days: set[str] = set()
    saw_activity_intensity = False
    saw_qualified_intensity = False
    for record in records:
        if not isinstance(record, dict) or not _record_type_is_activity_intensity(record):
            continue
        saw_activity_intensity = True
        if not _source_identity_present(record):
            return {**base, "null_reason": "missing_source_identity"}
        start = _parse_time(record.get("startTime"))
        end = _parse_time(record.get("endTime"))
        if start is None or end is None or end <= start:
            return {**base, "null_reason": "missing_timestamp"}
        kind = _intensity_kind(record.get("intensity"))
        if kind is None:
            continue
        interval_minutes = (end - start).total_seconds() / 60
        if interval_minutes < MINIMUM_QUALIFIED_INTERVAL_MINUTES:
            continue
        saw_qualified_intensity = True
        local_day = start.astimezone(start.tzinfo).date().isoformat()
        if kind == "moderate":
            moderate_days.add(local_day)
        elif kind == "vigorous":
            vigorous_days.add(local_day)

    if not saw_activity_intensity:
        return {**base, "null_reason": "missing_activity_intensity_record"}

    moderate_count = len(moderate_days)
    vigorous_count = len(vigorous_days)
    out = {
        **base,
        "qualified_moderate_aerobic_session_days_per_week": moderate_count,
        "qualified_vigorous_aerobic_session_days_per_week": vigorous_count,
        "trigger_evidence_mode": "health_connect_activity_intensity_frequency_context",
    }
    if not saw_qualified_intensity:
        return {**out, "null_reason": "no_qualified_intensity_session_day"}
    if moderate_count >= 5 or vigorous_count >= 3:
        return {**out, "null_reason": "weekly_aerobic_intensity_alternative_threshold_met"}
    return {**out, "context_present": True, "null_reason": None}


def _expected_subset(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def build_report() -> dict[str, Any]:
    evaluations = []
    all_expected = True
    for case in SYNTHETIC_CASES:
        actual = evaluate_dyslipidemia_activity_intensity_fixture(case["input_fixture"])
        expected = case["expected_derived_output"]
        passed = _expected_subset(actual, expected)
        all_expected = all_expected and passed
        evaluations.append({
            "case_id": case["case_id"],
            "fixture_kind": case["fixture_kind"],
            "input_fixture": case["input_fixture"],
            "expected_derived_output": expected,
            "actual_derived_output": actual,
            "passed": passed,
        })
    return {
        "artifact_kind": "synthetic_health_connect_dyslipidemia_activity_intensity_replay",
        "trigger_id": "trigger_dyslipidemia_aerobic_intensity_frequency_below_alternative_health_connect_candidate",
        "line_id": "dyslipidemia_aerobic_intensity_frequency_small_anchor",
        "provider_platform": "health_connect",
        "source_signal": "Health Connect ActivityIntensityRecord",
        "candidate_output_context_key": "dyslipidemia_aerobic_intensity_frequency_below_alternative_context",
        "candidate_day_rule": "A local day qualifies when at least one Health Connect ActivityIntensityRecord interval on that day has explicit moderate or vigorous intensity, source identity, and continuous interval duration >=10 minutes. Same-day short intervals are not accumulated in this KDB candidate rule. This is a candidate KDB rule, not operating runtime policy.",
        "cases_evaluated": len(evaluations),
        "cases_passed": sum(1 for item in evaluations if item["passed"]),
        "all_expected_outputs_matched": all_expected,
        "evaluations": evaluations,
        "covered_branches": [
            "positive_below_alternative",
            "short_interval_below_minimum_no_trigger",
            "moderate_threshold_met_no_trigger",
            "vigorous_threshold_met_no_trigger",
            "missing_dyslipidemia_context_no_trigger",
            "missing_source_identity_no_trigger",
            "unsupported_provider_no_trigger",
            "incomplete_week_no_trigger",
            "duplicate_overlap_ambiguity_no_trigger",
        ],
        "boundary": "Synthetic KDB fixture/replay only. It proves the DYS output shape and fail-closed branches for Health Connect ActivityIntensityRecord-like inputs under a candidate day rule. It does not establish production data availability, product ingestion, clinical diagnosis, lipid improvement, ASCVD risk prediction, exercise prescription, clearance, compliance score, runtime authority, service action, delivery timing, frequency, or deduplication policy.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
