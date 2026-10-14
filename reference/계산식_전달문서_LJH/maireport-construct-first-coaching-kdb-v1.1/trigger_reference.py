#!/usr/bin/env python3
"""Executable reference for selected KDB external trigger fixtures.

This module is intentionally small and standalone. It does not import service
runtime code, activate coaching, rank messages, or read production data. Its
job is to show an external developer how KDB raw-field/output/fixture contracts
turn into deterministic derived context rows.

The functions below cover representative external-developer-ready trigger
families. They are not a complete production evaluator. Unsupported trigger
fixtures fail closed so missing implementation examples remain visible.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Callable


class TriggerReferenceError(ValueError):
    """Raised when a fixture shape cannot be evaluated by this reference."""


def _num(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TriggerReferenceError(f"{field} must be numeric")
    return float(value)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise TriggerReferenceError(f"{field} must be boolean")
    return value


def _parse_provider_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TriggerReferenceError(f"{field} must be a timestamp string")
    text = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S.%f %z"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TriggerReferenceError(f"{field} is not parseable as ISO/provider time") from exc
    if parsed.tzinfo is None:
        raise TriggerReferenceError(f"{field} must include timezone in this reference")
    return parsed


def _parse_provider_time_loose(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TriggerReferenceError(f"{field} must be a timestamp string")
    text = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f %z", "%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TriggerReferenceError(f"{field} is not parseable as provider time") from exc


def _same_local_date(a: datetime, b: datetime) -> bool:
    return a.astimezone(a.tzinfo).date() == b.astimezone(a.tzinfo).date()


def _hhmm_to_minutes(value: Any, field: str) -> int:
    if not isinstance(value, str) or ":" not in value:
        raise TriggerReferenceError(f"{field} must be HH:MM")
    hour_s, minute_s = value.split(":", 1)
    hour = int(hour_s)
    minute = int(minute_s)
    if not 0 <= hour < 24 or not 0 <= minute < 60:
        raise TriggerReferenceError(f"{field} must be within a 24-hour clock")
    return hour * 60 + minute


def _local_date(value: Any, field: str):
    if not isinstance(value, str) or not value.strip():
        raise TriggerReferenceError(f"{field} must be YYYY-MM-DD")
    try:
        return datetime.fromisoformat(value.strip()).date()
    except ValueError as exc:
        raise TriggerReferenceError(f"{field} is not parseable as YYYY-MM-DD") from exc


def _local_date_set(values: Any, field: str) -> set:
    if not isinstance(values, list):
        raise TriggerReferenceError(f"{field} must be an array of YYYY-MM-DD values")
    return {_local_date(value, f"{field}[{index}]") for index, value in enumerate(values)}


def _circular_hour_distance(current_hhmm: Any, baseline_hhmm: Any) -> float:
    current = _hhmm_to_minutes(current_hhmm, "current_mean_session_start_time")
    baseline = _hhmm_to_minutes(baseline_hhmm, "prior_median_start_time")
    diff = abs(current - baseline)
    return min(diff, 1440 - diff) / 60.0


def _context(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
    return {"context_present": value, "null_reason": null_reason, **extra}


def _rounded(value: float, digits: int = 6) -> float | int:
    rounded = round(value, digits)
    return int(rounded) if float(rounded).is_integer() else rounded


def _positive_numbers(values: Any, field: str, *, scale: float = 1.0) -> list[float]:
    if not isinstance(values, list):
        raise TriggerReferenceError(f"{field} must be an array")
    out = []
    for index, value in enumerate(values):
        number = _num(value, f"{field}[{index}]") / scale
        if number > 0:
            out.append(number)
    return out


def evaluate_daily_step_reference_no_extra_push(input_fixture: dict[str, Any]) -> dict[str, Any]:
    step_value = input_fixture.get("daily_steps")
    if step_value is None:
        step_value = input_fixture.get("count")
    steps = _num(step_value, "daily_steps_or_count")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    threshold = 7000
    if steps < threshold:
        return _context(False, "steps_below_7000", observed_local_day_steps=steps, reference_step_threshold=threshold)
    return _context(
        True,
        None,
        observed_local_day_steps=int(steps) if steps.is_integer() else steps,
        reference_step_threshold=threshold,
        no_extra_push_copy_only=True,
    )


def evaluate_multi_day_activity_pattern_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    observed_day_count = int(_num(input_fixture.get("observed_day_count"), "observed_day_count"))
    if observed_day_count < 7:
        return _context(False, "insufficient_observed_days", observed_day_count=observed_day_count)
    positive_steps = _positive_numbers(input_fixture.get("daily_steps"), "daily_steps")
    if len(positive_steps) < 6:
        return _context(False, "insufficient_positive_days", positive_day_count=len(positive_steps))
    step_median = median(positive_steps)
    relative_range = (max(positive_steps) - min(positive_steps)) / step_median
    threshold = 1.0
    if relative_range <= threshold:
        return _context(
            True,
            None,
            positive_day_count=len(positive_steps),
            median_positive_day_steps=_rounded(step_median),
            relative_range=_rounded(relative_range),
            relative_range_threshold=threshold,
        )
    return _context(False, "relative_range_above_threshold", relative_range=_rounded(relative_range), relative_range_threshold=threshold)


def evaluate_activity_load_gradual_progression(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("required_fields_present"), "required_fields_present"):
        return _context(False, "missing_required_fields")
    if "prior_14d_positive_day_minutes" in input_fixture:
        prior = _positive_numbers(input_fixture.get("prior_14d_positive_day_minutes"), "prior_14d_positive_day_minutes")
        recent = _positive_numbers(input_fixture.get("recent_7d_positive_day_minutes"), "recent_7d_positive_day_minutes")
    else:
        prior = _positive_numbers(input_fixture.get("prior_14d_positive_day_duration_ms"), "prior_14d_positive_day_duration_ms", scale=60000.0)
        recent = _positive_numbers(input_fixture.get("recent_7d_positive_day_duration_ms"), "recent_7d_positive_day_duration_ms", scale=60000.0)
    if len(prior) < 7:
        return _context(False, "insufficient_prior_positive_days", prior_positive_day_count=len(prior))
    if len(recent) < 3:
        return _context(False, "insufficient_recent_positive_days", recent_positive_day_count=len(recent))
    prior_median = median(prior)
    recent_mean = sum(recent) / len(recent)
    ratio = recent_mean / prior_median
    if ratio >= 1.5:
        return _context(
            True,
            None,
            prior_positive_day_count=len(prior),
            recent_positive_day_count=len(recent),
            prior_positive_day_median_activity_load_minutes=_rounded(prior_median, 3),
            recent_positive_day_mean_activity_load_minutes=_rounded(recent_mean, 3),
            candidate_ratio=_rounded(ratio, 3),
        )
    return _context(False, "ratio_below_progression_threshold", candidate_ratio=_rounded(ratio, 3))


def evaluate_activity_load_return_to_baseline_checkin(input_fixture: dict[str, Any]) -> dict[str, Any]:
    anchor_ratio = _num(input_fixture.get("anchor_load_ratio_to_median"), "anchor_load_ratio_to_median")
    followup = _bool(input_fixture.get("followup_trajectory_candidate"), "followup_trajectory_candidate")
    answer_missing = _bool(input_fixture.get("answer_missing"), "answer_missing")
    if anchor_ratio >= 1.5 and followup and answer_missing:
        return _context(
            True,
            None,
            anchor_load_ratio_to_median=anchor_ratio,
            followup_trajectory_candidate=followup,
            answer_missing=answer_missing,
        )
    return _context(False, "return_to_baseline_context_not_met")


def evaluate_activity_load_spike_easy_buffer(input_fixture: dict[str, Any]) -> dict[str, Any]:
    current = _num(input_fixture.get("current_day_steps"), "current_day_steps")
    prior = _positive_numbers(input_fixture.get("prior_14_positive_steps"), "prior_14_positive_steps")
    recent = _positive_numbers(input_fixture.get("prior_two_days_steps"), "prior_two_days_steps")
    if len(prior) < 7:
        return _context(False, "insufficient_prior_positive_days", prior_positive_day_count=len(prior))
    prior_median = median(prior)
    prior_two_below = len(recent) >= 2 and all(value < prior_median for value in recent[-2:])
    ratio = current / prior_median
    if ratio >= 1.5 and prior_two_below:
        return _context(
            True,
            None,
            current_local_day_signal_value=_rounded(current),
            prior_14_day_positive_median=_rounded(prior_median),
            prior_positive_day_count=len(prior),
            prior_two_days_below_median=True,
            ratio_to_median=_rounded(ratio),
        )
    return _context(False, "spike_context_not_met", prior_two_days_below_median=prior_two_below, ratio_to_median=_rounded(ratio))


def _pneumonia_condition_window_gate(input_fixture: dict[str, Any], *, copy_action: str | None = None) -> dict[str, Any] | None:
    if not _bool(input_fixture.get("confirmed_pneumonia_context"), "confirmed_pneumonia_context"):
        return _context(False, "pneumonia_context_not_confirmed", copy_action=copy_action)
    if not _bool(input_fixture.get("pneumonia_coaching_window_active"), "pneumonia_coaching_window_active"):
        return _context(False, "pneumonia_coaching_window_not_active", copy_action=copy_action)
    return None


def evaluate_pneumonia_fluid_routine_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate an explicit pneumonia ordinary-fluid daily-life choice report."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_pneumonia_context"), "confirmed_pneumonia_context"):
        return result(False, "pneumonia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("fluid_routine_choice_opportunity"), "fluid_routine_choice_opportunity"):
        return result(False, "fluid_routine_choice_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_fluid_routine_choice",
        fluid_routine_context_present=True,
        fluid_routine_choice_count=1,
        local_day_window_days=1,
        fluid_volume_not_measured=True,
        hydration_status_not_inferred=True,
    )


def evaluate_pneumonia_household_support_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit pneumonia household-support opportunity report."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_pneumonia_context"), "confirmed_pneumonia_context"):
        return result(False, "pneumonia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("household_support_opportunity"), "household_support_opportunity"):
        return result(False, "household_support_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_household_support_opportunity",
        household_support_context_present=True,
        household_support_opportunity_count=1,
        local_day_window_days=1,
        need_not_inferred=True,
        recovery_status_not_inferred=True,
        activity_clearance_not_inferred=True,
    )


def evaluate_pneumonia_recovery_high_after_quiet_lower_intensity(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_recovery_lower_intensity")
    if gate is not None:
        return gate
    actual = evaluate_activity_load_spike_easy_buffer(input_fixture)
    actual.setdefault("copy_action", "pneumonia_recovery_lower_intensity")
    return actual


def evaluate_hypertension_high_after_quiet_activity_load_lighten_next(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("confirmed_elevated_bp_or_hypertension_context"), "confirmed_elevated_bp_or_hypertension_context"):
        return _context(False, "bp_htn_context_not_confirmed")
    actual = evaluate_activity_load_spike_easy_buffer(input_fixture)
    actual.setdefault("copy_action", "hypertension_high_after_quiet_activity_load_lighten_next")
    return actual


def evaluate_htn_home_sodium_choice_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate an explicit HTN home-food-choice report without dietary inference."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_hypertension_context"), "confirmed_hypertension_context"):
        return result(False, "hypertension_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("food_choice_opportunity"), "food_choice_opportunity"):
        return result(False, "food_choice_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_home_food_choice_context",
        choice_context_present=True,
        food_choice_opportunity_count=1,
        local_day_window_days=1,
        dietary_amount_not_measured=True,
    )


def evaluate_htn_stress_practice_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate an explicit HTN stress-management practice report only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_hypertension_context"), "confirmed_hypertension_context"):
        return result(False, "hypertension_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("stress_practice_opportunity"), "stress_practice_opportunity"):
        return result(False, "stress_practice_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_stress_management_context",
        practice_context_present=True,
        stress_practice_opportunity_count=1,
        local_day_window_days=1,
        stress_state_not_measured=True,
    )


def evaluate_diabetes_tobacco_support_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate an explicit diabetes tobacco/vaping support-step report only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_diabetes_context"), "confirmed_diabetes_context"):
        return result(False, "diabetes_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("support_step_opportunity"), "support_step_opportunity"):
        return result(False, "support_step_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_tobacco_support_context",
        support_context_present=True,
        support_step_opportunity_count=1,
        local_day_window_days=1,
        clinical_care_not_executed=True,
    )


def evaluate_cad_tobacco_support_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit CAD tobacco-support step opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    context_key = "cad_context_status_user_entered_or_operating_confirmed"
    if not _bool(input_fixture.get(context_key), context_key):
        return result(False, "cad_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("support_step_opportunity"), "support_step_opportunity"):
        return result(False, "support_step_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_tobacco_support_context",
        support_context_present=True,
        support_step_opportunity_count=1,
        local_day_window_days=1,
        clinical_care_not_executed=True,
    )


def evaluate_cad_cardiac_rehab_support_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit cardiovascular cardiac-rehabilitation support opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_cad_context"), "confirmed_cad_context"):
        return result(False, "cad_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("cardiac_rehab_support_opportunity"), "cardiac_rehab_support_opportunity"):
        return result(False, "cardiac_rehab_support_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_cardiac_rehabilitation_support_context",
        cardiac_rehab_support_context_present=True,
        cardiac_rehab_support_opportunity_count=1,
        local_day_window_days=1,
        cardiac_status_not_inferred=True,
        exercise_clearance_not_executed=True,
    )


def evaluate_pneumonia_followup_question_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit pneumonia follow-up question-preparation opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_pneumonia_context"), "confirmed_pneumonia_context"):
        return result(False, "pneumonia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("followup_question_opportunity"), "followup_question_opportunity"):
        return result(False, "followup_question_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_pneumonia_followup_question_context",
        followup_question_context_present=True,
        followup_question_opportunity_count=1,
        local_day_window_days=1,
        diagnosis_not_inferred=True,
        worsening_symptom_triage_not_executed=True,
    )


def evaluate_diabetes_sleep_routine_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit diabetes sleep-promoting routine opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_diabetes_context"), "confirmed_diabetes_context"):
        return result(False, "diabetes_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("sleep_routine_opportunity"), "sleep_routine_opportunity"):
        return result(False, "sleep_routine_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_diabetes_sleep_routine_context",
        sleep_routine_context_present=True,
        sleep_routine_opportunity_count=1,
        local_day_window_days=1,
        sleep_duration_not_measured=True,
        glycemic_outcome_not_inferred=True,
    )


def evaluate_cardiovascular_sleep_anchor_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit cardiovascular sleep-wake anchor choice only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_cardiovascular_context"), "confirmed_cardiovascular_context"):
        return result(False, "cardiovascular_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("sleep_anchor_opportunity"), "sleep_anchor_opportunity"):
        return result(False, "sleep_anchor_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_cardiovascular_sleep_anchor_context",
        sleep_anchor_context_present=True,
        sleep_anchor_opportunity_count=1,
        local_day_window_days=1,
        sleep_duration_not_measured=True,
        cardiovascular_status_not_inferred=True,
    )


def evaluate_cardiovascular_meal_timing_anchor_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit cardiovascular meal-timing routine opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_cardiovascular_context"), "confirmed_cardiovascular_context"):
        return result(False, "cardiovascular_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("meal_timing_anchor_opportunity"), "meal_timing_anchor_opportunity"):
        return result(False, "meal_timing_anchor_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_cardiovascular_meal_timing_anchor_context",
        meal_timing_anchor_context_present=True,
        meal_timing_anchor_opportunity_count=1,
        local_day_window_days=1,
        meal_timing_not_measured=True,
        cardiovascular_status_not_inferred=True,
    )


def evaluate_diabetes_sedentary_break_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit diabetes sedentary-break opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_diabetes_context"), "confirmed_diabetes_context"):
        return result(False, "diabetes_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("sedentary_break_opportunity"), "sedentary_break_opportunity"):
        return result(False, "sedentary_break_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_diabetes_sedentary_break_context",
        sedentary_break_context_present=True,
        sedentary_break_opportunity_count=1,
        local_day_window_days=1,
        sitting_time_not_measured=True,
        glycemic_status_not_inferred=True,
    )


def evaluate_hypertension_sleep_hygiene_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit hypertension-scoped sleep-promoting routine opportunity."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_hypertension_context"), "confirmed_hypertension_context"):
        return result(False, "hypertension_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("sleep_hygiene_opportunity"), "sleep_hygiene_opportunity"):
        return result(False, "sleep_hygiene_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_hypertension_sleep_hygiene_context",
        sleep_hygiene_context_present=True,
        sleep_hygiene_opportunity_count=1,
        local_day_window_days=1,
        sleep_quality_not_measured=True,
        blood_pressure_not_inferred=True,
    )


def evaluate_hypertension_sedentary_break_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit hypertension-scoped sedentary-break opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_hypertension_context"), "confirmed_hypertension_context"):
        return result(False, "hypertension_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("sedentary_break_opportunity"), "sedentary_break_opportunity"):
        return result(False, "sedentary_break_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_hypertension_sedentary_break_context",
        sedentary_break_context_present=True,
        sedentary_break_opportunity_count=1,
        local_day_window_days=1,
        sitting_time_not_measured=True,
        blood_pressure_not_inferred=True,
    )


def evaluate_hypertension_meal_preparation_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit hypertension-scoped meal-preparation opportunity."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_hypertension_context"), "confirmed_hypertension_context"):
        return result(False, "hypertension_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("meal_preparation_opportunity"), "meal_preparation_opportunity"):
        return result(False, "meal_preparation_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_hypertension_meal_preparation_context",
        meal_preparation_context_present=True,
        meal_preparation_opportunity_count=1,
        local_day_window_days=1,
        dietary_targets_not_measured=True,
        blood_pressure_not_inferred=True,
    )


def evaluate_pneumonia_small_meal_routine_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit pneumonia-scoped small-meal routine opportunity."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_pneumonia_context"), "confirmed_pneumonia_context"):
        return result(False, "pneumonia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("small_meal_routine_opportunity"), "small_meal_routine_opportunity"):
        return result(False, "small_meal_routine_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_pneumonia_small_meal_routine_context",
        small_meal_routine_context_present=True,
        small_meal_routine_opportunity_count=1,
        local_day_window_days=1,
        nutrition_targets_not_measured=True,
        pneumonia_status_not_inferred=True,
    )


def evaluate_cardiovascular_meal_planning_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit cardiovascular-scoped meal-planning opportunity."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_cardiovascular_context"), "confirmed_cardiovascular_context"):
        return result(False, "cardiovascular_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("meal_planning_opportunity"), "meal_planning_opportunity"):
        return result(False, "meal_planning_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_cardiovascular_meal_planning_context",
        meal_planning_context_present=True,
        meal_planning_opportunity_count=1,
        local_day_window_days=1,
        dietary_targets_not_measured=True,
        cardiovascular_status_not_inferred=True,
    )


def evaluate_diabetes_regular_meal_routine_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit diabetes-scoped regular-meal routine opportunity."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_diabetes_context"), "confirmed_diabetes_context"):
        return result(False, "diabetes_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("regular_meal_routine_opportunity"), "regular_meal_routine_opportunity"):
        return result(False, "regular_meal_routine_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_diabetes_regular_meal_routine_context",
        regular_meal_routine_context_present=True,
        regular_meal_routine_opportunity_count=1,
        local_day_window_days=1,
        meal_timings_not_measured=True,
        diabetes_status_not_inferred=True,
    )


def evaluate_dyslipidemia_fibre_food_addition_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit dyslipidemia-scoped fibre-rich food addition opportunity."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_dyslipidemia_context"), "confirmed_dyslipidemia_context"):
        return result(False, "dyslipidemia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("fibre_food_addition_opportunity"), "fibre_food_addition_opportunity"):
        return result(False, "fibre_food_addition_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_dyslipidemia_fibre_food_addition_context",
        fibre_food_addition_context_present=True,
        fibre_food_addition_opportunity_count=1,
        local_day_window_days=1,
        dietary_target_not_measured=True,
        lipid_values_not_inferred=True,
    )


def evaluate_dyslipidemia_exercise_snack_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit dyslipidemia-scoped exercise-snack opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_dyslipidemia_context"), "confirmed_dyslipidemia_context"):
        return result(False, "dyslipidemia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("exercise_snack_opportunity"), "exercise_snack_opportunity"):
        return result(False, "exercise_snack_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_dyslipidemia_exercise_snack_context",
        exercise_snack_context_present=True,
        exercise_snack_opportunity_count=1,
        local_day_window_days=1,
        movement_not_measured=True,
        lipid_not_inferred=True,
    )


def evaluate_dyslipidemia_sleep_routine_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit dyslipidemia-scoped sleep-promoting routine opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_dyslipidemia_context"), "confirmed_dyslipidemia_context"):
        return result(False, "dyslipidemia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("sleep_routine_opportunity"), "sleep_routine_opportunity"):
        return result(False, "sleep_routine_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_dyslipidemia_sleep_routine_context",
        sleep_routine_context_present=True,
        sleep_routine_opportunity_count=1,
        local_day_window_days=1,
        sleep_quality_not_measured=True,
        lipid_values_not_inferred=True,
    )


def evaluate_dyslipidemia_resistance_session_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit dyslipidemia-scoped resistance-session opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_dyslipidemia_context"), "confirmed_dyslipidemia_context"):
        return result(False, "dyslipidemia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("resistance_session_opportunity"), "resistance_session_opportunity"):
        return result(False, "resistance_session_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_dyslipidemia_resistance_session_context",
        resistance_session_context_present=True,
        resistance_session_opportunity_count=1,
        local_day_window_days=1,
        resistance_intensity_not_measured=True,
        resistance_safety_not_inferred=True,
        lipid_not_inferred=True,
    )


def _evaluate_dyslipidemia_observation_opportunity(
    input_fixture: dict[str, Any],
    *,
    opportunity_key: str,
    context_key: str,
    evidence_mode: str,
    missing_reason: str,
) -> dict[str, Any]:
    """Evaluate a bounded dyslipidemia device-observed opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_dyslipidemia_context"), "confirmed_dyslipidemia_context"):
        return result(False, "dyslipidemia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get(opportunity_key), opportunity_key):
        return result(False, missing_reason)
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode=evidence_mode,
        **{context_key: True},
        **{f"{opportunity_key}_count": 1},
        device_observation_only=True,
        intensity_not_measured=True,
        lipid_outcome_not_inferred=True,
    )


def evaluate_dyslipidemia_combined_aerobic_resistance_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_dyslipidemia_observation_opportunity(
        input_fixture,
        opportunity_key="aerobic_resistance_combination_opportunity",
        context_key="aerobic_resistance_combination_context_present",
        evidence_mode="observed_device_dataed_dyslipidemia_combined_aerobic_resistance_context",
        missing_reason="aerobic_resistance_combination_opportunity_not_reported",
    )


def evaluate_dyslipidemia_sedentary_break_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_dyslipidemia_observation_opportunity(
        input_fixture,
        opportunity_key="inactivity_gap_move_prompt_context",
        context_key="sedentary_break_movement_context_present",
        evidence_mode="observed_device_dataed_dyslipidemia_sedentary_break_context",
        missing_reason="inactivity_gap_move_prompt_context_not_reported",
    )


def evaluate_dyslipidemia_warmup_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_dyslipidemia_observation_opportunity(
        input_fixture,
        opportunity_key="workout_start_opportunity",
        context_key="warmup_movement_context_present",
        evidence_mode="observed_device_dataed_dyslipidemia_warmup_context",
        missing_reason="workout_start_opportunity_not_reported",
    )


def evaluate_dyslipidemia_flexibility_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_dyslipidemia_observation_opportunity(
        input_fixture,
        opportunity_key="workout_end_opportunity",
        context_key="flexibility_movement_context_present",
        evidence_mode="observed_device_dataed_dyslipidemia_flexibility_context",
        missing_reason="workout_end_opportunity_not_reported",
    )


def evaluate_dyslipidemia_cooldown_walk_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_dyslipidemia_observation_opportunity(
        input_fixture,
        opportunity_key="workout_end_opportunity",
        context_key="cooldown_walk_movement_context_present",
        evidence_mode="observed_device_dataed_dyslipidemia_cooldown_walk_context",
        missing_reason="workout_end_opportunity_not_reported",
    )


def evaluate_dyslipidemia_post_exercise_stand_break_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a bounded post-exercise standing-break opportunity.

    The evaluator combines two observed opportunities. It does not infer
    disease course, lipid values, exercise intensity, recovery, or safety.
    """
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_dyslipidemia_context"), "confirmed_dyslipidemia_context"):
        return result(False, "dyslipidemia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("workout_end_observed"), "workout_end_observed"):
        return result(False, "workout_end_not_observed")
    if not _bool(input_fixture.get("later_inactivity_gap_move_prompt_context"), "later_inactivity_gap_move_prompt_context"):
        return result(False, "later_inactivity_gap_not_observed")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    if not _bool(input_fixture.get("same_local_day"), "same_local_day"):
        return result(False, "not_later_same_local_day_opportunity")

    return result(
        True,
        None,
        trigger_evidence_mode="observed_workout_end_plus_later_inactivity_gap_opportunity",
        post_exercise_stand_break_context_present=True,
        workout_end_observed=True,
        later_inactivity_gap_move_prompt_context=True,
        same_local_day=True,
        device_observation_only=True,
        exercise_intensity_not_measured=True,
        recovery_not_inferred=True,
        lipid_outcome_not_inferred=True,
        safety_not_inferred=True,
    )


def evaluate_diabetes_meal_preparation_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit diabetes meal-preparation opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_diabetes_context"), "confirmed_diabetes_context"):
        return result(False, "diabetes_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("meal_preparation_opportunity"), "meal_preparation_opportunity"):
        return result(False, "meal_preparation_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_diabetes_meal_preparation_context",
        meal_preparation_context_present=True,
        meal_preparation_opportunity_count=1,
        local_day_window_days=1,
        glycemic_outcome_not_inferred=True,
        nutrition_prescription_not_provided=True,
    )


def evaluate_dyslipidemia_heart_healthy_food_choice_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit dyslipidemia heart-healthy food-choice opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_dyslipidemia_context"), "confirmed_dyslipidemia_context"):
        return result(False, "dyslipidemia_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("heart_healthy_food_choice_opportunity"), "heart_healthy_food_choice_opportunity"):
        return result(False, "heart_healthy_food_choice_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_dyslipidemia_heart_healthy_food_choice_context",
        heart_healthy_food_choice_context_present=True,
        heart_healthy_food_choice_opportunity_count=1,
        local_day_window_days=1,
        lipid_outcome_not_inferred=True,
        diet_prescription_not_executed=True,
    )


def evaluate_hypertension_home_bp_checkin_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit hypertension home-BP check-in preparation opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_hypertension_context"), "confirmed_hypertension_context"):
        return result(False, "hypertension_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("home_bp_checkin_opportunity"), "home_bp_checkin_opportunity"):
        return result(False, "home_bp_checkin_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_hypertension_home_bp_checkin_context",
        home_bp_checkin_context_present=True,
        home_bp_checkin_opportunity_count=1,
        local_day_window_days=1,
        blood_pressure_not_measured=True,
        blood_pressure_interpretation_not_executed=True,
    )


def evaluate_hypertension_followup_question_open(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one explicit hypertension follow-up-question preparation opportunity only."""
    def result(value: bool, null_reason: str | None = None, **extra: Any) -> dict[str, Any]:
        actual = _context(value, null_reason, **extra)
        actual["triggered"] = value
        return actual

    if not _bool(input_fixture.get("confirmed_hypertension_context"), "confirmed_hypertension_context"):
        return result(False, "hypertension_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return result(False, "adult_context_not_confirmed")
    if not _bool(input_fixture.get("followup_question_opportunity"), "followup_question_opportunity"):
        return result(False, "followup_question_opportunity_not_reported")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return result(False, "missing_source_identity")
    return result(
        True,
        None,
        trigger_evidence_mode="explicit_user_reported_hypertension_followup_question_context",
        followup_question_context_present=True,
        followup_question_opportunity_count=1,
        local_day_window_days=1,
        blood_pressure_not_measured=True,
        blood_pressure_interpretation_not_executed=True,
    )


def evaluate_pneumonia_recovery_inactivity_gap_small_restart(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_after_long_rest_first_step")
    if gate is not None:
        return gate
    actual = evaluate_inactivity_gap_move_prompt(input_fixture)
    actual.setdefault("copy_action", "pneumonia_after_long_rest_first_step")
    return actual


def evaluate_pneumonia_recovery_short_sleep_day_margin(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_short_sleep_day_margin")
    if gate is not None:
        return gate
    actual = evaluate_short_sleep_cognitive_load_light_planning(input_fixture)
    actual.setdefault("copy_action", "pneumonia_short_sleep_day_margin")
    return actual


def evaluate_pneumonia_recovery_sleep_quiet_gap_light_break(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_sleep_quiet_gap_light_break")
    if gate is not None:
        return gate
    actual = evaluate_sleep_context_quiet_gap_first_break_anchor(input_fixture)
    actual.setdefault("copy_action", "pneumonia_sleep_quiet_gap_light_break")
    return actual


def evaluate_pneumonia_activity_volume_small_reentry(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_recovery_activity_volume_small_reentry")
    if gate is not None:
        return gate
    actual = evaluate_activity_volume_baseline_gap_small_reentry(input_fixture)
    actual.setdefault("copy_action", "pneumonia_recovery_activity_volume_small_reentry")
    return actual


def evaluate_pneumonia_sleep_below_range_rest_window(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_sleep_below_range_rest_window")
    if gate is not None:
        return gate
    actual = evaluate_sleep_duration_below_range(input_fixture)
    actual.setdefault("copy_action", "pneumonia_sleep_below_range_rest_window")
    return actual


def evaluate_pneumonia_irregular_sleep_keep_one_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_irregular_sleep_keep_one_anchor")
    if gate is not None:
        return gate
    actual = evaluate_irregular_sleep_week_daytime_anchor(input_fixture)
    actual.setdefault("copy_action", "pneumonia_irregular_sleep_keep_one_anchor")
    return actual


def evaluate_pneumonia_high_active_energy_next_day_light_start(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_high_active_energy_next_day_light_start")
    if gate is not None:
        return gate
    actual = evaluate_high_active_energy_no_extra_push(input_fixture)
    actual.setdefault("copy_action", "pneumonia_high_active_energy_next_day_light_start")
    return actual


def evaluate_pneumonia_weekly_high_activity_volume_no_extra_push(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_weekly_high_activity_volume_no_extra_push")
    if gate is not None:
        return gate
    actual = evaluate_general_weekly_high_activity_volume_no_extra_push(input_fixture)
    actual.setdefault("copy_action", "pneumonia_weekly_high_activity_volume_no_extra_push")
    return actual


def evaluate_pneumonia_late_activity_sleep_winddown_buffer(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_late_activity_sleep_winddown_buffer")
    if gate is not None:
        return gate
    actual = evaluate_late_activity_sleep_winddown_anchor(input_fixture)
    actual.setdefault("copy_action", "pneumonia_late_activity_sleep_winddown_buffer")
    return actual


def evaluate_pneumonia_late_sleep_morning_first_move_small(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_late_sleep_morning_first_move_small")
    if gate is not None:
        return gate
    actual = evaluate_late_sleep_morning_first_activity_anchor(input_fixture)
    actual.setdefault("copy_action", "pneumonia_late_sleep_morning_first_move_small")
    return actual


def evaluate_pneumonia_walking_speed_drop_easy_pace(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_walking_speed_drop_easy_pace")
    if gate is not None:
        return gate
    actual = evaluate_walking_pace_drop_activity_pacing(input_fixture)
    actual.setdefault("copy_action", "pneumonia_walking_speed_drop_easy_pace")
    return actual


def evaluate_pneumonia_walking_speed_drop_close_short(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_walking_speed_drop_close_short")
    if gate is not None:
        return gate
    actual = evaluate_walking_pace_drop_activity_pacing(input_fixture)
    actual.setdefault("copy_action", "pneumonia_walking_speed_drop_close_short")
    return actual


def evaluate_pneumonia_light_walking_shorten_before_speed_up_apple(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_light_walking_shorten_before_speed_up")
    if gate is not None:
        return gate
    actual = evaluate_light_walking_apple_speed_context(input_fixture)
    actual.setdefault("copy_action", "pneumonia_light_walking_shorten_before_speed_up")
    return actual


def evaluate_pneumonia_light_walking_shorten_before_speed_up_samsung(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_light_walking_shorten_before_speed_up")
    if gate is not None:
        return gate
    actual = evaluate_light_walking_activity_context(input_fixture)
    actual.setdefault("copy_action", "pneumonia_light_walking_shorten_before_speed_up")
    return actual


def evaluate_pneumonia_recorded_exercise_familiar_stop_point(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_recorded_exercise_familiar_stop_point")
    if gate is not None:
        return gate
    actual = evaluate_recorded_exercise_duration_pattern(input_fixture)
    actual.setdefault("copy_action", "pneumonia_recorded_exercise_familiar_stop_point")
    return actual


def evaluate_pneumonia_recorded_exercise_spacing_no_stack(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_recorded_exercise_spacing_no_stack")
    if gate is not None:
        return gate
    actual = evaluate_recorded_exercise_session_spacing(input_fixture)
    actual.setdefault("copy_action", "pneumonia_recorded_exercise_spacing_no_stack")
    return actual


def evaluate_pneumonia_unaccustomed_activity_keep_easy_next(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_unaccustomed_activity_keep_easy_next")
    if gate is not None:
        return gate
    actual = evaluate_unaccustomed_activity_body_feel_checkin(input_fixture)
    actual.setdefault("copy_action", "pneumonia_unaccustomed_activity_keep_easy_next")
    return actual


def evaluate_pneumonia_activity_distribution_no_catchup_burst(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_activity_distribution_no_catchup_burst")
    if gate is not None:
        return gate
    actual = evaluate_activity_distribution_next_anchor(input_fixture)
    actual.setdefault("copy_action", "pneumonia_activity_distribution_no_catchup_burst")
    return actual


def evaluate_pneumonia_weekly_activity_distribution_no_makeup_week(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_weekly_activity_distribution_no_makeup_week")
    if gate is not None:
        return gate
    actual = evaluate_weekly_activity_distribution_next_week_anchor(input_fixture)
    actual.setdefault("copy_action", "pneumonia_weekly_activity_distribution_no_makeup_week")
    return actual


def evaluate_pneumonia_post_exercise_hrr_easy_cooldown(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_post_exercise_easy_cooldown")
    if gate is not None:
        return gate
    actual = evaluate_post_exercise_hrr_context(input_fixture)
    actual.setdefault("copy_action", "pneumonia_post_exercise_easy_cooldown")
    return actual


def evaluate_pneumonia_post_exercise_spo2_easy_cooldown(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_post_exercise_easy_cooldown")
    if gate is not None:
        return gate
    actual = evaluate_spo2_post_exercise_breathing_context(input_fixture)
    actual.setdefault("copy_action", "pneumonia_post_exercise_easy_cooldown")
    return actual


def evaluate_pneumonia_post_exercise_hrr_no_number_chase(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_post_exercise_no_number_chase")
    if gate is not None:
        return gate
    actual = evaluate_post_exercise_hrr_context(input_fixture)
    actual.setdefault("copy_action", "pneumonia_post_exercise_no_number_chase")
    return actual


def evaluate_pneumonia_post_exercise_spo2_no_number_chase(input_fixture: dict[str, Any]) -> dict[str, Any]:
    gate = _pneumonia_condition_window_gate(input_fixture, copy_action="pneumonia_post_exercise_no_number_chase")
    if gate is not None:
        return gate
    actual = evaluate_spo2_post_exercise_breathing_context(input_fixture)
    actual.setdefault("copy_action", "pneumonia_post_exercise_no_number_chase")
    return actual


def evaluate_activity_pattern_variability_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    spread = _num(input_fixture.get("relative_spread"), "relative_spread")
    previous = _num(input_fixture.get("previous_window_relative_spread"), "previous_window_relative_spread")
    days_since = int(_num(input_fixture.get("days_since_previous_candidate"), "days_since_previous_candidate"))
    threshold = 1.5
    quiet_days = 7
    crossing = previous < threshold <= spread
    if crossing and days_since >= quiet_days:
        return _context(
            True,
            None,
            relative_spread=_rounded(spread),
            relative_spread_threshold=threshold,
            crossing_newly_from_below=True,
            quiet_window_days=quiet_days,
        )
    return _context(False, "variability_context_not_met", crossing_newly_from_below=crossing, quiet_window_days=quiet_days)


def evaluate_activity_distribution_next_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("required_fields_present"), "required_fields_present"):
        return _context(False, "missing_required_fields")
    intervals = []
    if "intervals" in input_fixture:
        raw_intervals = input_fixture.get("intervals")
        if not isinstance(raw_intervals, list):
            raise TriggerReferenceError("intervals must be an array")
        for index, row in enumerate(raw_intervals):
            if not isinstance(row, dict):
                raise TriggerReferenceError(f"intervals[{index}] must be an object")
            start = _parse_provider_time_loose(row.get("start"), f"intervals[{index}].start")
            end = _parse_provider_time_loose(row.get("end"), f"intervals[{index}].end")
            if end <= start:
                return _context(False, "invalid_interval")
            intervals.append((start, end))
    else:
        raw_rows = input_fixture.get("rows")
        if not isinstance(raw_rows, list):
            raise TriggerReferenceError("rows must be an array")
        for index, row in enumerate(raw_rows):
            if not isinstance(row, dict):
                raise TriggerReferenceError(f"rows[{index}] must be an object")
            start = _parse_provider_time_loose(row.get("start_time"), f"rows[{index}].start_time")
            duration_ms = _num(row.get("duration"), f"rows[{index}].duration")
            if duration_ms <= 0:
                continue
            intervals.append((start, start))
    windows = sorted({start.hour // 3 for start, _end in intervals})
    if 1 <= len(windows) <= 2:
        return _context(
            True,
            None,
            active_3h_window_count=len(windows),
            active_3h_window_indexes=windows,
            source_interval_count=len(intervals),
        )
    return _context(False, "active_window_count_outside_anchor_range", active_3h_window_count=len(windows), source_interval_count=len(intervals))


def evaluate_after_high_activity_low_movement_body_feel_checkin(input_fixture: dict[str, Any]) -> dict[str, Any]:
    prior_ratio = _num(input_fixture.get("prior_load_ratio_to_median"), "prior_load_ratio_to_median")
    next_ratio = _num(input_fixture.get("next_day_movement_ratio_to_median"), "next_day_movement_ratio_to_median")
    answer_missing = _bool(input_fixture.get("answer_missing"), "answer_missing")
    if prior_ratio >= 1.5 and next_ratio <= 0.8 and answer_missing:
        return _context(
            True,
            None,
            prior_load_ratio_to_median=prior_ratio,
            next_day_movement_ratio_to_median=next_ratio,
            answer_missing=answer_missing,
        )
    return _context(False, "after_high_activity_low_movement_context_not_met")


def evaluate_brief_brisk_bout_next_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    start_value = input_fixture.get("startDate", input_fixture.get("start_time"))
    end_value = input_fixture.get("endDate", input_fixture.get("end_time"))
    start = _parse_provider_time_loose(start_value, "start")
    end = _parse_provider_time_loose(end_value, "end")
    if end <= start:
        return _context(False, "invalid_interval")
    steps_value = input_fixture.get("value")
    if steps_value is None:
        steps_value = input_fixture.get("count")
    steps = _num(steps_value, "interval_step_count")
    minutes = (end - start).total_seconds() / 60.0
    cadence = steps / minutes
    if minutes >= 5 and cadence >= 100:
        return _context(
            True,
            None,
            interval_duration_minutes=_rounded(minutes),
            interval_step_count=_rounded(steps),
            cadence_steps_per_minute=_rounded(cadence),
        )
    return _context(False, "brief_brisk_bout_threshold_not_met", interval_duration_minutes=_rounded(minutes), cadence_steps_per_minute=_rounded(cadence))


def evaluate_current_step_light_activity_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if "observed_local_day_step_records" in input_fixture:
        steps = sum(_positive_numbers(input_fixture.get("observed_local_day_step_records"), "observed_local_day_step_records"))
    else:
        steps = _num(input_fixture.get("count"), "count")
    last_prompt_hours = _num(input_fixture.get("last_same_line_prompt_hours_ago"), "last_same_line_prompt_hours_ago")
    threshold = 3000
    if steps <= threshold and last_prompt_hours >= 24:
        return _context(
            True,
            None,
            observed_local_day_steps=_rounded(steps),
            primary_low_step_threshold=threshold,
            strict_low_step_label=steps < 1000,
        )
    return _context(False, "current_step_context_not_met", observed_local_day_steps=_rounded(steps), primary_low_step_threshold=threshold)


def evaluate_daily_step_pattern_consistency(input_fixture: dict[str, Any]) -> dict[str, Any]:
    raw_steps = input_fixture.get("complete_daily_steps")
    if not isinstance(raw_steps, list):
        raise TriggerReferenceError("complete_daily_steps must be an array")
    complete_count = len(raw_steps)
    if complete_count < 7:
        return _context(False, "insufficient_complete_days", complete_day_count=complete_count)
    positives = _positive_numbers(raw_steps, "complete_daily_steps")
    if len(positives) < 6:
        return _context(False, "insufficient_positive_days", positive_day_count=len(positives))
    step_median = median(positives)
    relative_spread = (max(positives) - min(positives)) / step_median
    threshold = 1.0
    if relative_spread <= threshold:
        return _context(
            True,
            None,
            complete_day_count=complete_count,
            positive_day_count=len(positives),
            median_positive_day_steps=_rounded(step_median),
            relative_spread=_rounded(relative_spread),
            relative_spread_threshold=threshold,
        )
    return _context(False, "relative_spread_above_threshold", relative_spread=_rounded(relative_spread), relative_spread_threshold=threshold)


def evaluate_late_activity_sleep_winddown_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if "workout_end" in input_fixture:
        activity_end = _parse_provider_time_loose(input_fixture.get("workout_end"), "workout_end")
    else:
        start = _parse_provider_time_loose(input_fixture.get("exercise_start"), "exercise_start")
        duration_ms = _num(input_fixture.get("duration_ms"), "duration_ms")
        activity_end = start + timedelta(milliseconds=duration_ms)
    sleep_onset = _parse_provider_time_loose(input_fixture.get("habitual_sleep_onset"), "habitual_sleep_onset")
    minutes = (sleep_onset - activity_end).total_seconds() / 60.0
    sleep_minutes = _num(input_fixture.get("same_night_sleep_duration_minutes"), "same_night_sleep_duration_minutes")
    if 0 <= minutes <= 120:
        return _context(
            True,
            None,
            minutes_from_activity_end_to_sleep_onset=_rounded(minutes),
            same_night_sleep_duration_minutes=_rounded(sleep_minutes),
        )
    return _context(False, "activity_not_within_winddown_window", minutes_from_activity_end_to_sleep_onset=_rounded(minutes))


def evaluate_light_walking_activity_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("complete_day"), "complete_day"):
        return _context(False, "incomplete_day")
    duration = _num(input_fixture.get("duration_minutes"), "duration_minutes")
    speed = _num(input_fixture.get("mean_speed_m_per_s"), "mean_speed_m_per_s")
    if input_fixture.get("exercise_type") == "walking" and duration >= 10 and 0.45 <= speed <= 1.07:
        return _context(
            True,
            None,
            candidate_duration_minutes=_rounded(duration),
            candidate_interval_count=1,
            speed_band_m_per_s="[0.45,1.07]",
        )
    return _context(False, "light_walking_context_not_met")


def evaluate_light_walking_apple_speed_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("complete_day"), "complete_day"):
        return _context(False, "incomplete_day")
    value = _num(input_fixture.get("value"), "value")
    if input_fixture.get("unit") == "km/hr" and 1.62 <= value <= 3.85:
        return _context(True, None, candidate_interval_count=1, speed_band_km_per_hr="[1.62,3.85]")
    return _context(False, "walking_speed_outside_light_band")


def evaluate_daily_mvpa_30min_gap_estimated(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("complete_day"), "complete_day"):
        return _context(False, "incomplete_or_unknown_day_coverage")
    events = input_fixture.get("events")
    if not isinstance(events, list):
        raise TriggerReferenceError("events must be an array")
    total = 0.0
    candidate_count = 0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise TriggerReferenceError(f"events[{index}] must be an object")
        if not _bool(event.get("source_identity_present"), f"events[{index}].source_identity_present"):
            return _context(False, "missing_source_identity")
        if event.get("exercise_type") != "1001":
            continue
        speed = _num(event.get("mean_speed_m_per_s"), f"events[{index}].mean_speed_m_per_s")
        duration = _num(event.get("duration_minutes"), f"events[{index}].duration_minutes")
        if duration <= 0:
            return _context(False, "missing_or_nonpositive_duration")
        if 1.25 <= speed <= 1.52:
            total += duration
            candidate_count += 1
    threshold = 30
    if candidate_count == 0:
        return _context(
            False,
            "no_in_band_estimated_interval",
            estimated_moderate_walking_minutes=0,
            daily_threshold_minutes=threshold,
            candidate_interval_count=0,
            speed_band_m_per_s="[1.25,1.52]",
            provider_source_status="primary_replay_source",
        )
    if 0 < total < threshold:
        return _context(
            True,
            None,
            estimated_moderate_walking_minutes=_rounded(total),
            daily_threshold_minutes=threshold,
            candidate_interval_count=candidate_count,
            speed_band_m_per_s="[1.25,1.52]",
            provider_source_status="primary_replay_source",
        )
    return _context(
        False,
        "estimated_minutes_at_or_above_30",
        estimated_moderate_walking_minutes=_rounded(total),
        daily_threshold_minutes=threshold,
        candidate_interval_count=candidate_count,
        speed_band_m_per_s="[1.25,1.52]",
        provider_source_status="primary_replay_source",
    )


def evaluate_daily_mvpa_30min_gap_direct(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if input_fixture.get("source_qualification_contract_present") is False:
        return _context(
            False,
            "samsung_source_qualification_pending",
            qualified_mvpa_minutes=None,
            provider_source_status="source_qualification_pending",
        )
    if not _bool(input_fixture.get("complete_day", input_fixture.get("complete_window")), "complete_day"):
        return _context(False, "incomplete_or_unknown_day_coverage")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    intervals = _positive_numbers(input_fixture.get("qualified_interval_minutes"), "qualified_interval_minutes")
    threshold = 30
    total = sum(intervals)
    provider_status = str(input_fixture.get("provider_source_status") or "primary_replay_source")
    if total == 0:
        return _context(
            False,
            "no_qualified_mvpa_interval",
            qualified_mvpa_minutes=0,
            daily_threshold_minutes=threshold,
            provider_source_status=provider_status,
        )
    if total < threshold:
        return _context(
            True,
            None,
            qualified_mvpa_minutes=_rounded(total),
            daily_threshold_minutes=threshold,
            provider_source_status=provider_status,
        )
    return _context(
        False,
        "qualified_minutes_at_or_above_30",
        qualified_mvpa_minutes=_rounded(total),
        daily_threshold_minutes=threshold,
        provider_source_status=provider_status,
    )


def evaluate_any_length_mvpa_accumulation(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if input_fixture.get("source_qualification_contract_present") is False:
        return _context(
            False,
            "samsung_source_qualification_pending",
            weekly_qualified_mvpa_minutes=None,
            provider_source_status="source_qualification_pending",
        )
    if not _bool(input_fixture.get("complete_week", input_fixture.get("complete_window", True)), "complete_week"):
        return _context(False, "incomplete_or_unknown_week_coverage")
    if not _bool(input_fixture.get("source_identity_present", True), "source_identity_present"):
        return _context(False, "missing_source_identity")
    intervals = _positive_numbers(input_fixture.get("qualified_interval_minutes"), "qualified_interval_minutes")
    target = 150
    total = sum(intervals)
    provider_status = str(input_fixture.get("provider_source_status") or "primary_replay_source")
    short_bout_present = any(minutes < 10 for minutes in intervals)
    if total == 0:
        return _context(
            False,
            "no_qualified_mvpa_interval",
            weekly_qualified_mvpa_minutes=0,
            weekly_target_minutes=target,
            short_qualified_bout_present=False,
            provider_source_status=provider_status,
        )
    if total < target and short_bout_present:
        return _context(
            True,
            None,
            weekly_qualified_mvpa_minutes=_rounded(total),
            weekly_target_minutes=target,
            short_qualified_bout_present=True,
            provider_source_status=provider_status,
        )
    if total >= target:
        return _context(
            False,
            "weekly_total_at_or_above_150",
            weekly_qualified_mvpa_minutes=_rounded(total),
            weekly_target_minutes=target,
            short_qualified_bout_present=short_bout_present,
            provider_source_status=provider_status,
        )
    return _context(
        False,
        "no_short_qualified_bout",
        weekly_qualified_mvpa_minutes=_rounded(total),
        weekly_target_minutes=target,
        short_qualified_bout_present=False,
        provider_source_status=provider_status,
    )


def evaluate_low_step_streak_no_catchup_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    baseline = _num(input_fixture.get("personal_step_baseline"), "personal_step_baseline")
    recent_steps = input_fixture.get("recent_daily_steps")
    if not isinstance(recent_steps, list):
        raise TriggerReferenceError("recent_daily_steps must be an array")
    below_count = sum(1 for index, value in enumerate(recent_steps) if _num(value, f"recent_daily_steps[{index}]") < baseline)
    today = _num(input_fixture.get("today_steps_so_far"), "today_steps_so_far")
    if below_count >= 3 and today < baseline:
        return _context(
            True,
            None,
            personal_step_baseline=_rounded(baseline),
            recent_below_baseline_day_count=below_count,
            today_steps_so_far=_rounded(today),
            no_catchup_anchor_window_present=True,
        )
    return _context(False, "low_step_streak_context_not_met", recent_below_baseline_day_count=below_count)


def evaluate_short_sleep_low_activity_midday_floor_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("midday_floor_window_present"), "midday_floor_window_present"):
        return _context(False, "midday_floor_window_absent")
    sleep = _num(input_fixture.get("prior_night_sleep_duration_minutes"), "prior_night_sleep_duration_minutes")
    baseline = _num(input_fixture.get("personal_sleep_baseline_minutes"), "personal_sleep_baseline_minutes")
    early_steps = _num(input_fixture.get("early_day_steps"), "early_day_steps")
    ratio = sleep / baseline
    if ratio < 0.8 and early_steps < 1000:
        return _context(
            True,
            None,
            prior_night_sleep_duration_minutes=_rounded(sleep),
            relative_sleep_duration_ratio=_rounded(ratio),
            early_day_activity_value=_rounded(early_steps),
            first_active_time=input_fixture.get("first_active_time"),
            midday_floor_window_present=True,
        )
    return _context(False, "short_sleep_low_activity_context_not_met", relative_sleep_duration_ratio=_rounded(ratio))


def evaluate_sleep_timing_next_day_available_window_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    prior = _positive_numbers(input_fixture.get("prior_14_sleep_duration_minutes"), "prior_14_sleep_duration_minutes")
    if len(prior) < 7:
        return _context(False, "insufficient_prior_valid_nights", prior_valid_night_count=len(prior))
    prior_median = median(prior)
    prior_night = _num(input_fixture.get("prior_night_duration_minutes"), "prior_night_duration_minutes")
    shift = _num(input_fixture.get("sleep_onset_shift_minutes"), "sleep_onset_shift_minutes")
    window_count_value = input_fixture.get("next_day_positive_step_window_count")
    if window_count_value is None:
        window_count_value = input_fixture.get("next_day_positive_pedometer_window_count")
    window_count = int(_num(window_count_value, "next_day_positive_activity_window_count"))
    ratio = prior_night / prior_median
    if window_count >= 1 and (ratio < 0.8 or abs(shift) >= 60):
        return _context(
            True,
            None,
            prior_14_night_median_sleep_duration_minutes=_rounded(prior_median),
            prior_night_sleep_duration_minutes=_rounded(prior_night),
            relative_sleep_duration_ratio=_rounded(ratio),
            sleep_onset_shift_minutes=_rounded(shift),
            next_day_activity_window_present=True,
        )
    return _context(False, "sleep_timing_activity_window_context_not_met", relative_sleep_duration_ratio=_rounded(ratio))


def _sleep_duration_hours(input_fixture: dict[str, Any]) -> float:
    if "sleep_duration_hours" in input_fixture:
        return _num(input_fixture.get("sleep_duration_hours"), "sleep_duration_hours")
    return _num(input_fixture.get("sleep_duration_minutes"), "sleep_duration_minutes") / 60.0


def _circular_mad_minutes(values: list[float]) -> float:
    center = median(values)
    distances = [min(abs(value - center), 1440.0 - abs(value - center)) for value in values]
    return median(distances)


def _nearest_rank_percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise TriggerReferenceError("percentile values must not be empty")
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def evaluate_sleep_duration_below_range(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    hours = _sleep_duration_hours(input_fixture)
    lower = 7.0
    if hours < lower:
        return _context(True, None, sleep_duration_hours=_rounded(hours), lower_bound_hours=lower)
    return _context(False, "sleep_duration_not_below_range", sleep_duration_hours=_rounded(hours), lower_bound_hours=lower)


def evaluate_sleep_duration_within_range(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    hours = _sleep_duration_hours(input_fixture)
    lower = 7.0
    upper = 9.0
    if lower <= hours <= upper:
        return _context(True, None, sleep_duration_hours=_rounded(hours), lower_bound_hours=lower, upper_bound_hours=upper)
    return _context(False, "sleep_duration_outside_range", sleep_duration_hours=_rounded(hours), lower_bound_hours=lower, upper_bound_hours=upper)


def _positive_sleep_hours(input_fixture: dict[str, Any]) -> list[float]:
    if "resolved_sleep_duration_hours" in input_fixture:
        return _positive_numbers(input_fixture.get("resolved_sleep_duration_hours"), "resolved_sleep_duration_hours")
    return [
        value / 60.0
        for value in _positive_numbers(input_fixture.get("resolved_sleep_duration_minutes"), "resolved_sleep_duration_minutes")
    ]


def _midpoints(input_fixture: dict[str, Any]) -> list[float]:
    values = input_fixture.get("sleep_midpoint_minutes")
    if not isinstance(values, list):
        raise TriggerReferenceError("sleep_midpoint_minutes must be an array")
    out = []
    for index, value in enumerate(values):
        minutes = _num(value, f"sleep_midpoint_minutes[{index}]")
        if not 0 <= minutes < 1440:
            raise TriggerReferenceError(f"sleep_midpoint_minutes[{index}] must be within a day")
        out.append(minutes)
    return out


def evaluate_sleep_duration_regular_range_within_fact40(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    hours = _positive_sleep_hours(input_fixture)
    midpoints = _midpoints(input_fixture)
    if len(hours) < 7 or len(midpoints) < 7:
        return _context(False, "insufficient_resolved_sleep_nights", resolved_night_count=min(len(hours), len(midpoints)))
    mean_hours = sum(hours[-7:]) / 7.0
    mad = _circular_mad_minutes(midpoints[-7:])
    lower = 7.0
    upper = 9.0
    threshold = 180.0
    if lower <= mean_hours <= upper and mad <= threshold:
        return _context(
            True,
            None,
            resolved_night_count=7,
            mean_sleep_duration_hours=_rounded(mean_hours),
            midpoint_mad_minutes=_rounded(mad),
            lower_bound_hours=lower,
            upper_bound_hours=upper,
            midpoint_mad_threshold_minutes=threshold,
        )
    return _context(
        False,
        "regular_sleep_duration_context_not_met",
        mean_sleep_duration_hours=_rounded(mean_hours),
        midpoint_mad_minutes=_rounded(mad),
    )


def evaluate_sleep_timing_regular_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    midpoints = _midpoints(input_fixture)
    if len(midpoints) < 7:
        return _context(False, "insufficient_resolved_sleep_nights", resolved_night_count=len(midpoints))
    threshold = 180.0
    mad = _circular_mad_minutes(midpoints[-7:])
    if mad <= threshold:
        return _context(True, None, resolved_night_count=7, midpoint_mad_minutes=_rounded(mad), midpoint_mad_threshold_minutes=threshold)
    return _context(False, "sleep_timing_not_regular", midpoint_mad_minutes=_rounded(mad), midpoint_mad_threshold_minutes=threshold)


def evaluate_sleep_duration_variability_opportunity(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    durations = _positive_numbers(input_fixture.get("resolved_sleep_duration_minutes"), "resolved_sleep_duration_minutes")
    if len(durations) < 7:
        return _context(False, "insufficient_resolved_sleep_nights", resolved_night_count=len(durations))
    previous = _num(input_fixture.get("previous_window_variability_ratio"), "previous_window_variability_ratio")
    days_since = int(_num(input_fixture.get("days_since_previous_candidate"), "days_since_previous_candidate"))
    window = durations[-7:]
    p10 = _nearest_rank_percentile(window, 0.10)
    p90 = _nearest_rank_percentile(window, 0.90)
    baseline = median(window)
    ratio = (p90 - p10) / baseline if baseline > 0 else 0.0
    threshold = 0.25
    quiet_days = 7
    crossing = previous <= threshold < ratio
    if crossing and days_since >= quiet_days:
        return _context(
            True,
            None,
            resolved_night_count=7,
            variability_ratio=_rounded(ratio),
            variability_ratio_threshold=threshold,
            quiet_window_days=quiet_days,
        )
    return _context(
        False,
        "sleep_duration_variability_context_not_met",
        variability_ratio=_rounded(ratio),
        variability_ratio_threshold=threshold,
        crossing_newly_from_below=crossing,
        quiet_window_days=quiet_days,
    )


def evaluate_inactivity_gap_move_prompt(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("device_presence_confident"), "device_presence_confident"):
        return _context(False, "missing_device_presence_confidence")
    quiet_gap = _num(input_fixture.get("quiet_gap_minutes"), "quiet_gap_minutes")
    threshold = 120.0
    if quiet_gap >= threshold:
        return _context(
            True,
            None,
            quiet_gap_minutes=_rounded(quiet_gap),
            quiet_gap_threshold_minutes=threshold,
            quiet_gap_window=input_fixture.get("quiet_gap_window", "10:00-18:00"),
        )
    return _context(False, "quiet_gap_below_threshold", quiet_gap_minutes=_rounded(quiet_gap), quiet_gap_threshold_minutes=threshold)


def evaluate_diabetes_sedentary_break_device(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Apply confirmed diabetes/adult context to an existing device opportunity."""
    def fail(reason: str) -> dict[str, Any]:
        result = _context(False, reason)
        result["triggered"] = False
        return result

    if not _bool(input_fixture.get("confirmed_diabetes_context"), "confirmed_diabetes_context"):
        return fail("diabetes_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return fail("adult_context_not_confirmed")
    if not _bool(input_fixture.get("inactivity_gap_move_prompt_context"), "inactivity_gap_move_prompt_context"):
        return fail("provider_inactivity_gap_not_qualified")
    if not _bool(input_fixture.get("provider_source_identity"), "provider_source_identity"):
        return fail("missing_source_identity")
    if input_fixture.get("coverage_and_missingness") != "qualified":
        return fail("coverage_or_missingness_not_qualified")
    if not _bool(input_fixture.get("posture_uncertainty_boundary"), "posture_uncertainty_boundary"):
        return fail("posture_uncertainty_boundary_missing")
    result = _context(
        True,
        None,
        trigger_evidence_mode="provider_qualified_inactivity_gap_plus_external_diabetes_context",
        sedentary_break_context_present=True,
    )
    result["triggered"] = True
    return result


def evaluate_cardiovascular_device_inactivity_break(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Apply external CVD/adult/safety context to an existing device opportunity."""
    def fail(reason: str) -> dict[str, Any]:
        result = _context(False, reason)
        result["triggered"] = False
        return result

    if not _bool(input_fixture.get("confirmed_cardiovascular_context"), "confirmed_cardiovascular_context"):
        return fail("cardiovascular_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return fail("adult_context_not_confirmed")
    if not _bool(input_fixture.get("no_contraindication_external_gate"), "no_contraindication_external_gate"):
        return fail("external_safety_gate_unknown")
    if not _bool(input_fixture.get("inactivity_gap_move_prompt_context"), "inactivity_gap_move_prompt_context"):
        return fail("provider_inactivity_gap_not_qualified")
    if not _bool(input_fixture.get("provider_source_identity"), "provider_source_identity"):
        return fail("missing_source_identity")
    if input_fixture.get("coverage_and_missingness") != "qualified":
        return fail("coverage_or_missingness_not_qualified")
    if not _bool(input_fixture.get("posture_uncertainty_boundary"), "posture_uncertainty_boundary"):
        return fail("posture_uncertainty_boundary_missing")
    result = _context(
        True,
        None,
        trigger_evidence_mode="provider_qualified_inactivity_gap_plus_external_cvd_and_safety_context",
        low_intensity_movement_opportunity_present=True,
        cardiovascular_status_not_inferred=True,
        safety_clearance_not_inferred=True,
    )
    result["triggered"] = True
    return result


def evaluate_hypertension_device_sedentary_break(input_fixture: dict[str, Any]) -> dict[str, Any]:
    """Apply external hypertension/adult/safety context to a device opportunity."""
    def fail(reason: str) -> dict[str, Any]:
        result = _context(False, reason)
        result["triggered"] = False
        return result

    if not _bool(input_fixture.get("confirmed_elevated_bp_or_hypertension_context"), "confirmed_elevated_bp_or_hypertension_context"):
        return fail("hypertension_context_not_confirmed")
    if not _bool(input_fixture.get("adult_18_plus_context"), "adult_18_plus_context"):
        return fail("adult_context_not_confirmed")
    if not _bool(input_fixture.get("red_flag_or_clinician_boundary"), "red_flag_or_clinician_boundary"):
        return fail("external_safety_gate_unknown")
    if not _bool(input_fixture.get("inactivity_gap_move_prompt_context"), "inactivity_gap_move_prompt_context"):
        return fail("provider_inactivity_gap_not_qualified")
    if not _bool(input_fixture.get("provider_source_identity"), "provider_source_identity"):
        return fail("missing_source_identity")
    if input_fixture.get("coverage_and_missingness") != "qualified":
        return fail("coverage_or_missingness_not_qualified")
    if not _bool(input_fixture.get("posture_uncertainty_boundary"), "posture_uncertainty_boundary"):
        return fail("posture_uncertainty_boundary_missing")
    result = _context(
        True,
        None,
        trigger_evidence_mode="provider_qualified_inactivity_gap_plus_external_hypertension_and_safety_context",
        low_intensity_movement_opportunity_present=True,
        blood_pressure_status_not_inferred=True,
        safety_clearance_not_inferred=True,
    )
    result["triggered"] = True
    return result


def evaluate_daily_sedentary_like_inactivity_above_8h_fact41(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("complete_day_coverage_present"), "complete_day_coverage_present"):
        return _context(False, "missing_complete_day_coverage")
    hours = _num(
        input_fixture.get("estimated_sedentary_like_inactivity_hours_per_day"),
        "estimated_sedentary_like_inactivity_hours_per_day",
    )
    threshold = 8.0
    if hours > threshold:
        return _context(
            True,
            None,
            estimated_sedentary_like_inactivity_hours_per_day=_rounded(hours),
            fact41_upper_bound_hours_per_day=threshold,
            waking_observation_window=input_fixture.get("waking_observation_window", "06:00-23:00"),
            complete_day_first_positive_event_max=input_fixture.get("complete_day_first_positive_event_max", "10:00"),
            complete_day_last_positive_event_min=input_fixture.get("complete_day_last_positive_event_min", "20:00"),
        )
    return _context(
        False,
        "sedentary_like_inactivity_not_above_fact41_upper_bound",
        estimated_sedentary_like_inactivity_hours_per_day=_rounded(hours),
        fact41_upper_bound_hours_per_day=threshold,
    )


def evaluate_weekly_activity_distribution_next_week_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("complete_week_coverage_present"), "complete_week_coverage_present"):
        return _context(False, "insufficient_weekly_coverage")
    if not _bool(input_fixture.get("personal_baseline_context_present"), "personal_baseline_context_present"):
        return _context(False, "missing_personal_baseline_context")
    if not _bool(input_fixture.get("next_week_first_anchor_window_present"), "next_week_first_anchor_window_present"):
        return _context(False, "next_week_anchor_window_absent")
    if not _bool(input_fixture.get("next_week_prompt_eligible"), "next_week_prompt_eligible"):
        return _context(False, "next_week_prompt_not_eligible")
    values = input_fixture.get("positive_activity_days_in_7day_window")
    if not isinstance(values, list):
        raise TriggerReferenceError("positive_activity_days_in_7day_window must be an array")
    positive_days = set()
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise TriggerReferenceError(f"positive_activity_days_in_7day_window[{index}] must be YYYY-MM-DD")
        try:
            positive_days.add(datetime.fromisoformat(value).date())
        except ValueError as exc:
            raise TriggerReferenceError(
                f"positive_activity_days_in_7day_window[{index}] is not parseable as a date"
            ) from exc
    candidate_days = 2
    if len(positive_days) == candidate_days:
        return _context(
            True,
            None,
            positive_activity_day_count=len(positive_days),
            window_length_days=7,
            candidate_positive_activity_day_count=candidate_days,
            next_week_first_anchor_window_present=True,
            next_week_prompt_eligible=True,
        )
    return _context(
        False,
        "positive_day_count_not_two",
        positive_activity_day_count=len(positive_days),
        candidate_positive_activity_day_count=candidate_days,
    )


def evaluate_walking_pace_drop_activity_pacing(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    current = _positive_numbers(
        input_fixture.get("current_day_walking_speed_values_m_per_s"),
        "current_day_walking_speed_values_m_per_s",
    )
    minimum_current_records = 5
    if len(current) < minimum_current_records:
        return _context(False, "insufficient_current_day_records", current_day_positive_record_count=len(current))
    prior = _positive_numbers(
        input_fixture.get("prior_14day_eligible_day_daily_p90_m_per_s"),
        "prior_14day_eligible_day_daily_p90_m_per_s",
    )
    minimum_prior_days = 7
    if len(prior) < minimum_prior_days:
        return _context(False, "insufficient_prior_eligible_days", prior_eligible_day_count=len(prior))
    current_p90 = _nearest_rank_percentile(current, 0.90)
    prior_median = median(prior)
    threshold_ratio = 0.8
    if current_p90 <= threshold_ratio * prior_median:
        return _context(
            True,
            None,
            current_day_walking_speed_p90_m_per_s=_rounded(current_p90),
            prior_14day_eligible_day_daily_p90_median_m_per_s=_rounded(prior_median),
            threshold_ratio_to_prior_median=threshold_ratio,
            current_day_positive_record_count=len(current),
            prior_eligible_day_count=len(prior),
        )
    return _context(
        False,
        "current_p90_above_threshold",
        current_day_walking_speed_p90_m_per_s=_rounded(current_p90),
        prior_14day_eligible_day_daily_p90_median_m_per_s=_rounded(prior_median),
        threshold_ratio_to_prior_median=threshold_ratio,
    )


def evaluate_break_like_movement_reactivation(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    quiet_gap = _num(input_fixture.get("quiet_gap_minutes"), "quiet_gap_minutes")
    first_steps = _num(input_fixture.get("first_light_step_count"), "first_light_step_count")
    quiet_threshold = 120.0
    min_steps = 1.0
    max_steps = 300.0
    if quiet_gap >= quiet_threshold and min_steps <= first_steps <= max_steps:
        return _context(
            True,
            None,
            quiet_gap_minutes=_rounded(quiet_gap),
            quiet_gap_threshold_minutes=quiet_threshold,
            first_light_step_count=_rounded(first_steps),
            light_step_min_steps=min_steps,
            light_step_max_steps=max_steps,
        )
    return _context(False, "break_like_reactivation_context_not_met", quiet_gap_minutes=_rounded(quiet_gap), first_light_step_count=_rounded(first_steps))


def evaluate_quiet_gap_light_step_followthrough_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    base = evaluate_break_like_movement_reactivation(input_fixture)
    if not base["context_present"]:
        return base
    delay = _num(input_fixture.get("followthrough_delay_minutes"), "followthrough_delay_minutes")
    event_present = _bool(input_fixture.get("followthrough_event_present"), "followthrough_event_present")
    min_delay = 60.0
    max_delay = 240.0
    if event_present and min_delay <= delay <= max_delay:
        return _context(
            True,
            None,
            quiet_gap_minutes=base["quiet_gap_minutes"],
            quiet_gap_threshold_minutes=base["quiet_gap_threshold_minutes"],
            first_light_step_count=base["first_light_step_count"],
            light_step_min_steps=base["light_step_min_steps"],
            light_step_max_steps=base["light_step_max_steps"],
            followthrough_delay_minutes=_rounded(delay),
            followthrough_min_delay_minutes=min_delay,
            followthrough_max_delay_minutes=max_delay,
            followthrough_event_present=True,
        )
    return _context(False, "followthrough_window_not_met", followthrough_delay_minutes=_rounded(delay), followthrough_event_present=event_present)


def evaluate_irregular_sleep_week_daytime_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    midpoints = _midpoints(input_fixture)
    if len(midpoints) < 7:
        return _context(False, "insufficient_resolved_sleep_nights", resolved_night_count=len(midpoints))
    active_days = int(_num(input_fixture.get("active_days_in_window"), "active_days_in_window"))
    anchor_present = _bool(input_fixture.get("daytime_anchor_window_present"), "daytime_anchor_window_present")
    threshold = 180.0
    mad = _circular_mad_minutes(midpoints[-7:])
    if mad > threshold and active_days >= 3 and anchor_present:
        return _context(
            True,
            None,
            resolved_night_count=7,
            midpoint_mad_minutes=_rounded(mad),
            midpoint_mad_threshold_minutes=threshold,
            active_days_in_window=active_days,
            daytime_anchor_window_present=True,
        )
    return _context(
        False,
        "irregular_sleep_week_daytime_anchor_context_not_met",
        midpoint_mad_minutes=_rounded(mad),
        active_days_in_window=active_days,
        daytime_anchor_window_present=anchor_present,
    )


def evaluate_sleep_context_quiet_gap_first_break_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("recent_sleep_context_present"), "recent_sleep_context_present"):
        return _context(False, "missing_recent_sleep_context")
    if not _bool(input_fixture.get("device_presence_confident"), "device_presence_confident"):
        return _context(False, "missing_device_presence_confidence")
    quiet_gap = _num(input_fixture.get("quiet_gap_minutes"), "quiet_gap_minutes")
    threshold = 120.0
    if quiet_gap >= threshold:
        return _context(
            True,
            None,
            quiet_gap_minutes=_rounded(quiet_gap),
            quiet_gap_threshold_minutes=threshold,
            quiet_gap_window=input_fixture.get("quiet_gap_window", "10:00-18:00"),
        )
    return _context(False, "quiet_gap_below_threshold", quiet_gap_minutes=_rounded(quiet_gap), quiet_gap_threshold_minutes=threshold)


def evaluate_sleep_drift_midday_reset_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    prior = input_fixture.get("prior_sleep_midpoint_minutes")
    if not isinstance(prior, list):
        raise TriggerReferenceError("prior_sleep_midpoint_minutes must be an array")
    prior_midpoints = []
    for index, value in enumerate(prior):
        minutes = _num(value, f"prior_sleep_midpoint_minutes[{index}]")
        if not 0 <= minutes < 1440:
            raise TriggerReferenceError(f"prior_sleep_midpoint_minutes[{index}] must be within a day")
        prior_midpoints.append(minutes)
    if len(prior_midpoints) < 6:
        return _context(False, "insufficient_prior_valid_nights", prior_valid_night_count=len(prior_midpoints))
    current = _num(input_fixture.get("current_sleep_midpoint_minutes"), "current_sleep_midpoint_minutes")
    first_delay = _num(input_fixture.get("first_activity_delay_minutes"), "first_activity_delay_minutes")
    window = _bool(input_fixture.get("midday_anchor_window_present"), "midday_anchor_window_present")
    drift_threshold = 90.0
    delay_threshold = 60.0
    drift = min(abs(current - median(prior_midpoints)), 1440.0 - abs(current - median(prior_midpoints)))
    if drift >= drift_threshold and first_delay >= delay_threshold and window:
        return _context(
            True,
            None,
            prior_valid_night_count=len(prior_midpoints),
            sleep_midpoint_drift_minutes=_rounded(drift),
            sleep_midpoint_drift_threshold_minutes=drift_threshold,
            first_activity_delay_minutes=_rounded(first_delay),
            first_activity_delay_threshold_minutes=delay_threshold,
            midday_anchor_window_present=True,
        )
    return _context(False, "sleep_drift_midday_reset_context_not_met", sleep_midpoint_drift_minutes=_rounded(drift), first_activity_delay_minutes=_rounded(first_delay))


def evaluate_late_sleep_morning_first_activity_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")

    def minute_array(field: str) -> list[float]:
        values = input_fixture.get(field)
        if not isinstance(values, list):
            raise TriggerReferenceError(f"{field} must be an array")
        out = []
        for index, value in enumerate(values):
            minutes = _num(value, f"{field}[{index}]")
            if not 0 <= minutes < 1440:
                raise TriggerReferenceError(f"{field}[{index}] must be within a day")
            out.append(minutes)
        return out

    prior_onsets = minute_array("prior_sleep_onset_minutes")
    prior_wakes = minute_array("prior_wake_minutes")
    prior_count = min(len(prior_onsets), len(prior_wakes))
    if prior_count < 6:
        return _context(False, "insufficient_prior_valid_nights", prior_valid_night_count=prior_count)
    current_onset = _num(input_fixture.get("current_sleep_onset_minutes"), "current_sleep_onset_minutes")
    current_wake = _num(input_fixture.get("current_wake_minutes"), "current_wake_minutes")
    first_delay = _num(input_fixture.get("first_activity_delay_minutes"), "first_activity_delay_minutes")
    late_threshold = 60.0
    delay_threshold = 60.0
    onset_late = (current_onset - median(prior_onsets)) % 1440.0
    wake_late = (current_wake - median(prior_wakes)) % 1440.0
    late_sleep_or_wake = onset_late >= late_threshold or wake_late >= late_threshold
    if late_sleep_or_wake and first_delay >= delay_threshold:
        return _context(
            True,
            None,
            prior_valid_night_count=prior_count,
            onset_late_minutes=_rounded(onset_late),
            wake_late_minutes=_rounded(wake_late),
            late_onset_or_wake_threshold_minutes=late_threshold,
            first_activity_delay_minutes=_rounded(first_delay),
            first_activity_delay_threshold_minutes=delay_threshold,
        )
    return _context(False, "late_sleep_morning_first_activity_context_not_met", onset_late_minutes=_rounded(onset_late), wake_late_minutes=_rounded(wake_late), first_activity_delay_minutes=_rounded(first_delay))


def evaluate_weekend_sleep_shift_first_activity_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")

    def minute_array(field: str) -> list[float]:
        values = input_fixture.get(field)
        if not isinstance(values, list):
            raise TriggerReferenceError(f"{field} must be an array")
        return [_num(value, f"{field}[{index}]") for index, value in enumerate(values)]

    weekday = minute_array("weekday_sleep_midpoint_minutes")
    weekend = minute_array("weekend_sleep_midpoint_minutes")
    if not weekday or not weekend:
        return _context(False, "missing_weekday_or_weekend_sleep_timing")
    observed = _bool(input_fixture.get("weekend_first_activity_observed"), "weekend_first_activity_observed")
    shift = (median(weekend) - median(weekday)) % 1440.0
    threshold = 90.0
    maximum = 720.0
    if threshold <= shift <= maximum and observed:
        return _context(
            True,
            None,
            weekday_weekend_sleep_midpoint_shift_minutes=_rounded(shift),
            weekday_weekend_shift_threshold_minutes=threshold,
            maximum_late_shift_minutes=maximum,
            weekend_first_activity_observed=True,
        )
    return _context(False, "weekend_sleep_shift_first_activity_context_not_met", weekday_weekend_sleep_midpoint_shift_minutes=_rounded(shift), weekend_first_activity_observed=observed)


def evaluate_activity_sleep_timing_reflection(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")

    def local_dates(field: str) -> set[Any]:
        values = input_fixture.get(field)
        if not isinstance(values, list):
            raise TriggerReferenceError(f"{field} must be an array")
        dates = set()
        for index, value in enumerate(values):
            if not isinstance(value, str):
                raise TriggerReferenceError(f"{field}[{index}] must be YYYY-MM-DD")
            try:
                dates.add(datetime.fromisoformat(value).date())
            except ValueError as exc:
                raise TriggerReferenceError(f"{field}[{index}] is not parseable as a date") from exc
        return dates

    activity_dates = local_dates("activity_timing_local_dates")
    sleep_dates = local_dates("sleep_night_anchor_local_dates")
    paired_count = len(activity_dates & sleep_dates)
    minimum = 3
    if paired_count >= minimum:
        return _context(
            True,
            None,
            paired_local_day_count=paired_count,
            minimum_paired_local_day_count=minimum,
        )
    return _context(
        False,
        "insufficient_paired_local_days",
        paired_local_day_count=paired_count,
        minimum_paired_local_day_count=minimum,
    )


def evaluate_unaccustomed_activity_body_feel_checkin(input_fixture: dict[str, Any]) -> dict[str, Any]:
    novel = _bool(input_fixture.get("novel_activity_load_pattern"), "novel_activity_load_pattern")
    answer_missing = _bool(input_fixture.get("answer_missing"), "answer_missing")
    lookback = int(_num(input_fixture.get("novelty_lookback_days"), "novelty_lookback_days"))
    if novel and answer_missing and lookback >= 28:
        return _context(
            True,
            None,
            novel_activity_load_pattern=True,
            novelty_lookback_days=lookback,
            answer_missing=True,
        )
    return _context(False, "unaccustomed_activity_context_not_met")


def evaluate_weekly_aerobic_activity_distribution_below_3_days(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    events = input_fixture.get("qualified_events")
    if not isinstance(events, list):
        raise TriggerReferenceError("qualified_events must be an array")
    qualified_days = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise TriggerReferenceError(f"qualified_events[{index}] must be an object")
        if not event.get("source_confirmed_moderate_or_vigorous"):
            continue
        time_value = event.get("startDate", event.get("start_time"))
        qualified_days.add(_parse_provider_time_loose(time_value, f"qualified_events[{index}].start").date())
    threshold = 3
    if 0 < len(qualified_days) < threshold:
        return _context(True, None, qualified_aerobic_activity_days_per_week=len(qualified_days), threshold_distinct_days=threshold)
    return _context(False, "weekly_aerobic_distribution_threshold_not_met", qualified_aerobic_activity_days_per_week=len(qualified_days), threshold_distinct_days=threshold)


def evaluate_hypertension_aerobic_frequency_below_5_sessions(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("confirmed_elevated_bp_or_hypertension_context"), "confirmed_elevated_bp_or_hypertension_context"):
        return _context(False, "bp_htn_context_not_confirmed")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    provider = input_fixture.get("provider_platform")
    if provider not in {"apple_health_export", "samsung_health_export"}:
        return _context(False, "unsupported_provider_platform")
    if not _bool(input_fixture.get("observed_week_source_present"), "observed_week_source_present"):
        return _context(False, "missing_observed_week_source")
    events = input_fixture.get("qualified_events")
    if not isinstance(events, list):
        raise TriggerReferenceError("qualified_events must be an array")
    qualified_days = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise TriggerReferenceError(f"qualified_events[{index}] must be an object")
        if not event.get("source_qualified_aerobic_exercise"):
            continue
        time_value = event.get("startDate", event.get("start_time"))
        qualified_days.add(_parse_provider_time_loose(time_value, f"qualified_events[{index}].start").date())
    threshold = 5
    count = len(qualified_days)
    if count < threshold:
        return _context(
            True,
            None,
            provider_platform=provider,
            qualified_aerobic_exercise_days_per_week=count,
            threshold_distinct_days=threshold,
            trigger_evidence_mode="source_qualified_aerobic_exercise_frequency_context",
        )
    return _context(
        False,
        "weekly_aerobic_frequency_threshold_not_met",
        provider_platform=provider,
        qualified_aerobic_exercise_days_per_week=count,
        threshold_distinct_days=threshold,
    )


def _count_source_qualified_resistance_equipment_sessions(
    input_fixture: dict[str, Any],
    *,
    context_key: str = "confirmed_elevated_bp_or_hypertension_context",
    context_reason: str = "bp_htn_context_not_confirmed",
) -> tuple[str, int] | dict[str, Any]:
    if not _bool(input_fixture.get(context_key), context_key):
        return _context(False, context_reason)
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    provider = input_fixture.get("provider_platform")
    if provider != "apple_health_export":
        return _context(False, "unsupported_provider_platform")
    if not _bool(input_fixture.get("observed_week_source_present"), "observed_week_source_present"):
        return _context(False, "missing_observed_week_source")
    events = input_fixture.get("qualified_events")
    if not isinstance(events, list):
        raise TriggerReferenceError("qualified_events must be an array")
    session_count = 0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise TriggerReferenceError(f"qualified_events[{index}] must be an object")
        if not event.get("source_qualified_resistance_equipment_exercise"):
            continue
        time_value = event.get("startDate", event.get("start_time"))
        _parse_provider_time_loose(time_value, f"qualified_events[{index}].start")
        session_count += 1
    return provider, session_count


def evaluate_hypertension_resistance_equipment_frequency_below_2_sessions(input_fixture: dict[str, Any]) -> dict[str, Any]:
    calculated = _count_source_qualified_resistance_equipment_sessions(input_fixture)
    if isinstance(calculated, dict):
        return calculated
    provider, count = calculated
    minimum = 2
    maximum = 3
    if count < minimum:
        return _context(
            True,
            None,
            provider_platform=provider,
            qualified_resistance_equipment_sessions_per_week=count,
            minimum_range_sessions=minimum,
            maximum_range_sessions=maximum,
            trigger_evidence_mode="source_qualified_resistance_equipment_session_frequency_context",
        )
    return _context(
        False,
        "weekly_resistance_equipment_frequency_not_below_range",
        provider_platform=provider,
        qualified_resistance_equipment_sessions_per_week=count,
        minimum_range_sessions=minimum,
        maximum_range_sessions=maximum,
    )


def evaluate_diabetes_resistance_equipment_frequency_below_2_sessions(input_fixture: dict[str, Any]) -> dict[str, Any]:
    context_key = (
        "confirmed_diabetes_context"
        if "confirmed_diabetes_context" in input_fixture
        else "confirmed_elevated_bp_or_diabetes_context"
    )
    calculated = _count_source_qualified_resistance_equipment_sessions(
        input_fixture,
        context_key=context_key,
        context_reason="diabetes_context_not_confirmed",
    )
    if isinstance(calculated, dict):
        return calculated
    provider, count = calculated
    minimum = 2
    maximum = 3
    if count < minimum:
        return _context(
            True,
            None,
            provider_platform=provider,
            qualified_resistance_equipment_sessions_per_week=count,
            minimum_range_sessions=minimum,
            maximum_range_sessions=maximum,
            trigger_evidence_mode="source_qualified_resistance_equipment_session_frequency_context",
        )
    return _context(
        False,
        "weekly_resistance_equipment_frequency_not_below_range",
        provider_platform=provider,
        qualified_resistance_equipment_sessions_per_week=count,
        minimum_range_sessions=minimum,
        maximum_range_sessions=maximum,
    )


def evaluate_hypertension_resistance_equipment_frequency_above_3_sessions(input_fixture: dict[str, Any]) -> dict[str, Any]:
    calculated = _count_source_qualified_resistance_equipment_sessions(input_fixture)
    if isinstance(calculated, dict):
        return calculated
    provider, count = calculated
    minimum = 2
    maximum = 3
    if count > maximum:
        return _context(
            True,
            None,
            provider_platform=provider,
            qualified_resistance_equipment_sessions_per_week=count,
            minimum_range_sessions=minimum,
            maximum_range_sessions=maximum,
            trigger_evidence_mode="source_qualified_resistance_equipment_session_frequency_context",
        )
    return _context(
        False,
        "weekly_resistance_equipment_frequency_not_above_range",
        provider_platform=provider,
        qualified_resistance_equipment_sessions_per_week=count,
        minimum_range_sessions=minimum,
        maximum_range_sessions=maximum,
    )


def evaluate_dyslipidemia_aerobic_intensity_frequency_below_alternative(
    input_fixture: dict[str, Any],
) -> dict[str, Any]:
    if not _bool(input_fixture.get("confirmed_dyslipidemia_context"), "confirmed_dyslipidemia_context"):
        return _context(False, "dyslipidemia_context_not_confirmed")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    provider = input_fixture.get("provider_platform")
    if provider == "health_connect":
        # Health Connect has a different official record shape and its own
        # source-qualified replay contract. Keep it provider-specific rather
        # than forcing ActivityIntensityRecord rows through the Apple fields.
        from sample_validation.health_connect_dyslipidemia_activity_intensity_replay import (
            evaluate_dyslipidemia_activity_intensity_fixture,
        )

        return evaluate_dyslipidemia_activity_intensity_fixture(input_fixture)
    if provider != "apple_health_export":
        return _context(False, "unsupported_provider_platform")
    if not _bool(input_fixture.get("observed_week_source_present"), "observed_week_source_present"):
        return _context(False, "missing_observed_week_source")
    events = input_fixture.get("qualified_intensity_events")
    if not isinstance(events, list):
        raise TriggerReferenceError("qualified_intensity_events must be an array")
    moderate_days = set()
    vigorous_days = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise TriggerReferenceError(f"qualified_intensity_events[{index}] must be an object")
        time_value = event.get("startDate", event.get("start_time"))
        day = _parse_provider_time_loose(
            time_value, f"qualified_intensity_events[{index}].start"
        ).date()
        if event.get("source_qualified_moderate_aerobic_session"):
            moderate_days.add(day)
        if event.get("source_qualified_vigorous_aerobic_session"):
            vigorous_days.add(day)
    moderate_threshold = 5
    vigorous_threshold = 3
    moderate_count = len(moderate_days)
    vigorous_count = len(vigorous_days)
    if moderate_count < moderate_threshold and vigorous_count < vigorous_threshold:
        return _context(
            True,
            None,
            provider_platform=provider,
            qualified_moderate_aerobic_session_days_per_week=moderate_count,
            qualified_vigorous_aerobic_session_days_per_week=vigorous_count,
            moderate_threshold_distinct_days=moderate_threshold,
            vigorous_threshold_distinct_days=vigorous_threshold,
            trigger_evidence_mode="source_qualified_aerobic_intensity_frequency_context",
        )
    return _context(
        False,
        "weekly_aerobic_intensity_alternative_threshold_met",
        provider_platform=provider,
        qualified_moderate_aerobic_session_days_per_week=moderate_count,
        qualified_vigorous_aerobic_session_days_per_week=vigorous_count,
        moderate_threshold_distinct_days=moderate_threshold,
        vigorous_threshold_distinct_days=vigorous_threshold,
    )


def evaluate_diabetes_weekly_mvpa_volume_frequency_below_target(
    input_fixture: dict[str, Any],
) -> dict[str, Any]:
    if not _bool(input_fixture.get("confirmed_diabetes_context"), "confirmed_diabetes_context"):
        return _context(False, "diabetes_context_not_confirmed")
    if not _bool(
        input_fixture.get("diabetes_type_complication_and_contraindication_boundary"),
        "diabetes_type_complication_and_contraindication_boundary",
    ):
        return _context(False, "diabetes_boundary_not_supplied")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    provider = input_fixture.get("provider_platform")
    if provider != "apple_health_export":
        return _context(False, "unsupported_provider_platform")
    if not _bool(input_fixture.get("observed_week_source_present"), "observed_week_source_present"):
        return _context(False, "missing_observed_week_source")
    events = input_fixture.get("qualified_mvpa_events")
    if not isinstance(events, list):
        raise TriggerReferenceError("qualified_mvpa_events must be an array")
    total_minutes = 0.0
    mvpa_days = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise TriggerReferenceError(f"qualified_mvpa_events[{index}] must be an object")
        time_value = event.get("startDate", event.get("start_time"))
        day = _parse_provider_time_loose(
            time_value, f"qualified_mvpa_events[{index}].start"
        ).date()
        minutes = _num(event.get("duration_minutes"), f"qualified_mvpa_events[{index}].duration_minutes")
        if minutes <= 0:
            continue
        if event.get("source_qualified_mvpa_interval"):
            total_minutes += minutes
            mvpa_days.add(day)
    minute_threshold = 150.0
    day_threshold = 3
    day_count = len(mvpa_days)
    if total_minutes < minute_threshold or day_count < day_threshold:
        return _context(
            True,
            None,
            provider_platform=provider,
            weekly_qualified_mvpa_minutes=_rounded(total_minutes, 3),
            qualified_mvpa_days_per_week=day_count,
            weekly_target_minutes=minute_threshold,
            weekly_target_days=day_threshold,
            trigger_evidence_mode="source_qualified_weekly_mvpa_volume_frequency_context",
        )
    return _context(
        False,
        "weekly_mvpa_volume_and_frequency_targets_met",
        provider_platform=provider,
        weekly_qualified_mvpa_minutes=_rounded(total_minutes, 3),
        qualified_mvpa_days_per_week=day_count,
        weekly_target_minutes=minute_threshold,
        weekly_target_days=day_threshold,
    )


def evaluate_general_weekly_high_activity_volume_no_extra_push(
    input_fixture: dict[str, Any],
) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    provider = input_fixture.get("provider_platform")
    if provider != "apple_health_export":
        return _context(False, "unsupported_provider_platform")
    if not _bool(input_fixture.get("observed_week_source_present"), "observed_week_source_present"):
        return _context(False, "missing_observed_week_source")
    if input_fixture.get("condition_or_disability_scope_confirmed_when_used_as_dr") is False:
        return _context(False, "condition_or_disability_scope_not_confirmed")
    events = input_fixture.get("qualified_aerobic_intensity_events")
    if not isinstance(events, list):
        raise TriggerReferenceError("qualified_aerobic_intensity_events must be an array")
    moderate_minutes = 0.0
    vigorous_minutes = 0.0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise TriggerReferenceError(f"qualified_aerobic_intensity_events[{index}] must be an object")
        minutes = _num(event.get("duration_minutes"), f"qualified_aerobic_intensity_events[{index}].duration_minutes")
        if minutes <= 0:
            continue
        met_value = _num(event.get("met_value"), f"qualified_aerobic_intensity_events[{index}].met_value")
        if event.get("source_qualified_aerobic_interval") and met_value >= 3.0:
            moderate_minutes += minutes
            if met_value >= 6.0:
                vigorous_minutes += minutes
    moderate_threshold = 300.0
    vigorous_threshold = 150.0
    payload = {
        "provider_platform": provider,
        "weekly_qualified_moderate_minutes": _rounded(moderate_minutes, 3),
        "weekly_qualified_vigorous_minutes": _rounded(vigorous_minutes, 3),
        "moderate_upper_threshold_minutes": moderate_threshold,
        "vigorous_upper_threshold_minutes": vigorous_threshold,
    }
    if moderate_minutes > moderate_threshold or vigorous_minutes > vigorous_threshold:
        return _context(
            True,
            None,
            **payload,
            trigger_evidence_mode="source_qualified_weekly_high_activity_volume_context",
        )
    return _context(False, "weekly_activity_volume_not_above_upper_boundary", **payload)


def evaluate_diabetes_postmeal_low_movement_small_walk(
    input_fixture: dict[str, Any],
) -> dict[str, Any]:
    if not _bool(input_fixture.get("confirmed_diabetes_context"), "confirmed_diabetes_context"):
        return _context(False, "diabetes_context_not_confirmed")
    if not _bool(input_fixture.get("hypoglycemia_or_contraindication_boundary"), "hypoglycemia_or_contraindication_boundary"):
        return _context(False, "hypoglycemia_or_contraindication_boundary_not_supplied")
    if not _bool(input_fixture.get("meal_anchor_supplied_by_operation"), "meal_anchor_supplied_by_operation"):
        return _context(False, "meal_anchor_not_supplied")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    provider = input_fixture.get("provider_platform")
    if provider not in {"apple_health_export", "samsung_health_export", "health_connect"}:
        return _context(False, "unsupported_provider_platform")
    followup_minutes = _num(input_fixture.get("postmeal_followup_window_minutes"), "postmeal_followup_window_minutes")
    movement_minutes = _num(input_fixture.get("postmeal_positive_step_movement_minutes"), "postmeal_positive_step_movement_minutes")
    completion_threshold = _num(input_fixture.get("completion_movement_minutes_threshold"), "completion_movement_minutes_threshold")
    if followup_minutes != 45:
        return _context(False, "unsupported_postmeal_followup_window")
    if completion_threshold != 10:
        return _context(False, "unsupported_completion_threshold")
    if movement_minutes < 0 or movement_minutes > followup_minutes:
        raise TriggerReferenceError("postmeal_positive_step_movement_minutes outside followup window")
    payload = {
        "provider_platform": provider,
        "postmeal_followup_window_minutes": _rounded(followup_minutes),
        "postmeal_positive_step_movement_minutes": _rounded(movement_minutes, 3),
        "completion_movement_minutes_threshold": _rounded(completion_threshold),
        "trigger_evidence_mode": "operation_meal_anchor_plus_source_qualified_step_window_context",
    }
    if movement_minutes < completion_threshold:
        return _context(True, None, **payload)
    return _context(False, "postmeal_movement_threshold_met", **payload)


def evaluate_general_postmeal_quiet_window_small_walk(
    input_fixture: dict[str, Any],
) -> dict[str, Any]:
    if not _bool(input_fixture.get("meal_anchor_supplied_by_operation"), "meal_anchor_supplied_by_operation"):
        return _context(False, "meal_anchor_not_supplied")
    if not _bool(input_fixture.get("meal_recall_collected_after_meal"), "meal_recall_collected_after_meal"):
        return _context(False, "meal_recall_not_available_after_meal")
    if not _bool(input_fixture.get("postmeal_followup_window_elapsed"), "postmeal_followup_window_elapsed"):
        return _context(False, "postmeal_followup_window_not_elapsed")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    provider = input_fixture.get("provider_platform")
    if provider not in {"apple_health_export", "samsung_health_export", "health_connect"}:
        return _context(False, "unsupported_provider_platform")
    followup_minutes = _num(input_fixture.get("postmeal_followup_window_minutes"), "postmeal_followup_window_minutes")
    movement_minutes = _num(input_fixture.get("postmeal_positive_step_movement_minutes"), "postmeal_positive_step_movement_minutes")
    completion_threshold = _num(input_fixture.get("completion_movement_minutes_threshold"), "completion_movement_minutes_threshold")
    if followup_minutes != 45:
        return _context(False, "unsupported_postmeal_followup_window")
    if completion_threshold != 10:
        return _context(False, "unsupported_completion_threshold")
    if movement_minutes < 0 or movement_minutes > followup_minutes:
        raise TriggerReferenceError("postmeal_positive_step_movement_minutes outside followup window")
    payload = {
        "provider_platform": provider,
        "postmeal_followup_window_minutes": _rounded(followup_minutes),
        "postmeal_positive_step_movement_minutes": _rounded(movement_minutes, 3),
        "completion_movement_minutes_threshold": _rounded(completion_threshold),
        "trigger_evidence_mode": "recalled_meal_anchor_plus_source_qualified_step_window_context",
        "delivery_timing_hint": "next_meal_or_general_postmeal_habit_prompt",
    }
    if movement_minutes < completion_threshold:
        return _context(True, None, **payload)
    return _context(False, "postmeal_movement_threshold_met", **payload)


def _sum_source_qualified_exercise_minutes(input_fixture: dict[str, Any]) -> tuple[str, float] | dict[str, Any]:
    if not _bool(input_fixture.get("confirmed_elevated_bp_or_hypertension_context"), "confirmed_elevated_bp_or_hypertension_context"):
        return _context(False, "bp_htn_context_not_confirmed")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    provider = input_fixture.get("provider_platform")
    if provider not in {"apple_health_export", "samsung_health_export"}:
        return _context(False, "unsupported_provider_platform")
    if not _bool(input_fixture.get("observed_week_source_present"), "observed_week_source_present"):
        return _context(False, "missing_observed_week_source")
    events = input_fixture.get("session_events")
    if not isinstance(events, list):
        raise TriggerReferenceError("session_events must be an array")
    minutes = 0.0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise TriggerReferenceError(f"session_events[{index}] must be an object")
        if not event.get("source_qualified_exercise_session"):
            continue
        minutes += _num(event.get("duration_minutes"), f"session_events[{index}].duration_minutes")
    return provider, minutes


def evaluate_hypertension_weekly_exercise_duration_below_90_minutes(input_fixture: dict[str, Any]) -> dict[str, Any]:
    calculated = _sum_source_qualified_exercise_minutes(input_fixture)
    if isinstance(calculated, dict):
        return calculated
    provider, minutes = calculated
    threshold = 90.0
    maximum = 150.0
    if minutes < threshold:
        return _context(
            True,
            None,
            provider_platform=provider,
            weekly_exercise_duration_minutes=_rounded(minutes, 3),
            minimum_range_minutes=threshold,
            maximum_range_minutes=maximum,
            trigger_evidence_mode="source_qualified_weekly_exercise_duration_context",
        )
    return _context(
        False,
        "weekly_exercise_duration_not_below_range",
        provider_platform=provider,
        weekly_exercise_duration_minutes=_rounded(minutes, 3),
        minimum_range_minutes=threshold,
        maximum_range_minutes=maximum,
    )


def evaluate_hypertension_weekly_exercise_duration_above_150_minutes(input_fixture: dict[str, Any]) -> dict[str, Any]:
    calculated = _sum_source_qualified_exercise_minutes(input_fixture)
    if isinstance(calculated, dict):
        return calculated
    provider, minutes = calculated
    threshold = 150.0
    minimum = 90.0
    if minutes > threshold:
        return _context(
            True,
            None,
            provider_platform=provider,
            weekly_exercise_duration_minutes=_rounded(minutes, 3),
            minimum_range_minutes=minimum,
            maximum_range_minutes=threshold,
            trigger_evidence_mode="source_qualified_weekly_exercise_duration_context",
        )
    return _context(
        False,
        "weekly_exercise_duration_not_above_range",
        provider_platform=provider,
        weekly_exercise_duration_minutes=_rounded(minutes, 3),
        minimum_range_minutes=minimum,
        maximum_range_minutes=threshold,
    )


def evaluate_energy_low_gap_apple(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    valid_prior_days = int(_num(input_fixture.get("valid_prior_days"), "valid_prior_days"))
    if valid_prior_days < 7:
        return _context(False, "insufficient_prior_valid_days")
    current = _num(input_fixture.get("current_day_active_energy"), "current_day_active_energy")
    previous = _num(input_fixture.get("previous_day_active_energy"), "previous_day_active_energy")
    baseline = _num(input_fixture.get("prior_positive_median"), "prior_positive_median")
    threshold_ratio = 0.5
    if current < threshold_ratio * baseline and previous < threshold_ratio * baseline:
        return _context(True, None, threshold_ratio=threshold_ratio)
    return _context(False, "not_two_consecutive_below_half_days", threshold_ratio=threshold_ratio)


def evaluate_energy_low_gap_samsung(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    valid_prior_days = int(_num(input_fixture.get("valid_prior_days"), "valid_prior_days"))
    if valid_prior_days < 7:
        return _context(False, "insufficient_prior_valid_days")
    current = _num(input_fixture.get("current_recorded_calorie"), "current_recorded_calorie")
    baseline = _num(input_fixture.get("prior_positive_median"), "prior_positive_median")
    threshold_ratio = 0.5
    if current < threshold_ratio * baseline:
        return _context(True, None, threshold_ratio=threshold_ratio)
    return _context(False, "not_below_half_prior_median", threshold_ratio=threshold_ratio)


def evaluate_apple_record_gap_movement(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    raw_records = input_fixture.get("records")
    if not isinstance(raw_records, list):
        raise TriggerReferenceError("records must be an array")
    records = []
    for index, raw in enumerate(raw_records):
        if not isinstance(raw, dict):
            raise TriggerReferenceError(f"records[{index}] must be an object")
        value = _num(raw.get("value"), f"records[{index}].value")
        if value <= 0:
            continue
        start = _parse_provider_time(raw.get("startDate"), f"records[{index}].startDate")
        end = _parse_provider_time(raw.get("endDate"), f"records[{index}].endDate")
        if end <= start:
            return _context(False, "missing_timestamped_step_record")
        records.append({"start": start, "end": end, "value": value})
    records.sort(key=lambda row: row["start"])
    if len(records) < 2:
        return _context(False, "fewer_than_two_observed_records", record_count=len(records))
    gaps = []
    for left, right in zip(records, records[1:]):
        if right["start"] < left["end"]:
            return _context(False, "unresolved_duplicate_or_overlap")
        if not _same_local_date(left["start"], right["start"]):
            continue
        gaps.append((right["start"] - left["end"]).total_seconds() / 60.0)
    observed_gap = max(gaps) if gaps else 0.0
    minimum_gap_minutes = 180
    if observed_gap >= minimum_gap_minutes:
        return _context(
            True,
            None,
            observed_gap_minutes=int(observed_gap) if observed_gap.is_integer() else observed_gap,
            minimum_gap_minutes=minimum_gap_minutes,
            record_count=len(records),
        )
    return _context(False, "gap_below_three_hours", observed_gap_minutes=observed_gap, minimum_gap_minutes=minimum_gap_minutes)


def _short_sleep_high_activity(
    input_fixture: dict[str, Any],
    *,
    activity_current_key: str,
    activity_baseline_key: str,
    activity_not_above_reason: str,
) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    valid_prior_days = int(_num(input_fixture.get("valid_prior_paired_days"), "valid_prior_paired_days"))
    if valid_prior_days < 7:
        return _context(False, "insufficient_prior_paired_days")
    sleep = _num(input_fixture.get("current_sleep_minutes"), "current_sleep_minutes")
    sleep_baseline = _num(input_fixture.get("sleep_median_minutes"), "sleep_median_minutes")
    activity = _num(input_fixture.get(activity_current_key), activity_current_key)
    activity_baseline = _num(input_fixture.get(activity_baseline_key), activity_baseline_key)
    short_sleep_ratio_threshold = 0.8
    high_activity_ratio_threshold = 1.25
    if sleep >= short_sleep_ratio_threshold * sleep_baseline:
        return _context(False, "sleep_not_below_threshold", short_sleep_ratio_threshold=short_sleep_ratio_threshold)
    if activity < high_activity_ratio_threshold * activity_baseline:
        return _context(False, activity_not_above_reason, high_activity_ratio_threshold=high_activity_ratio_threshold)
    return _context(
        True,
        None,
        short_sleep_ratio_threshold=short_sleep_ratio_threshold,
        high_activity_ratio_threshold=high_activity_ratio_threshold,
    )


def evaluate_short_sleep_steps(input_fixture: dict[str, Any]) -> dict[str, Any]:
    return _short_sleep_high_activity(
        input_fixture,
        activity_current_key="current_steps",
        activity_baseline_key="step_median",
        activity_not_above_reason="activity_not_above_threshold",
    )


def evaluate_short_sleep_exercise_time(input_fixture: dict[str, Any]) -> dict[str, Any]:
    return _short_sleep_high_activity(
        input_fixture,
        activity_current_key="current_exercise_time_minutes",
        activity_baseline_key="exercise_time_median_minutes",
        activity_not_above_reason="exercise_time_not_above_threshold",
    )


def evaluate_short_sleep_exercise_duration(input_fixture: dict[str, Any]) -> dict[str, Any]:
    return _short_sleep_high_activity(
        input_fixture,
        activity_current_key="current_exercise_duration_minutes",
        activity_baseline_key="exercise_duration_median_minutes",
        activity_not_above_reason="exercise_duration_not_above_threshold",
    )


def evaluate_samsung_exercise_timing_shift(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    valid_prior_days = int(_num(input_fixture.get("valid_prior_session_days"), "valid_prior_session_days"))
    if valid_prior_days < 7:
        return _context(False, "insufficient_prior_session_days")
    distance = _circular_hour_distance(
        input_fixture.get("current_mean_session_start_time"),
        input_fixture.get("prior_median_start_time"),
    )
    threshold_hours = 6
    if distance > threshold_hours:
        return _context(True, None, circular_shift_hours=int(distance) if distance.is_integer() else distance, threshold_hours=threshold_hours)
    return _context(False, "shift_at_or_below_six_hours", circular_shift_hours=distance, threshold_hours=threshold_hours)


def evaluate_recorded_exercise_duration_pattern(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    durations = _positive_numbers(input_fixture.get("daily_durations_minutes"), "daily_durations_minutes")
    provider = input_fixture.get("provider_platform")
    minimum_days = 3 if provider == "apple_health_export" else 2
    if len(durations) < minimum_days:
        return _context(False, "insufficient_session_days", observed_session_day_count=len(durations))
    duration_median = median(durations)
    if duration_median <= 0:
        return _context(False, "zero_or_missing_duration_median")
    relative_spread = (max(durations) - min(durations)) / duration_median
    threshold = 1.0
    if relative_spread <= threshold:
        return _context(
            True,
            None,
            observed_session_day_count=len(durations),
            median_daily_representative_duration_minutes=_rounded(duration_median),
            duration_relative_spread=_rounded(relative_spread),
            relative_spread_threshold=threshold,
        )
    return _context(False, "relative_spread_above_threshold", duration_relative_spread=_rounded(relative_spread), relative_spread_threshold=threshold)


def evaluate_recorded_exercise_session_spacing(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    raw_dates = input_fixture.get("session_local_dates")
    if not isinstance(raw_dates, list):
        raise TriggerReferenceError("session_local_dates must be an array")
    dates = []
    for index, value in enumerate(raw_dates):
        if not isinstance(value, str):
            raise TriggerReferenceError(f"session_local_dates[{index}] must be YYYY-MM-DD")
        try:
            dates.append(datetime.fromisoformat(value).date())
        except ValueError as exc:
            raise TriggerReferenceError(f"session_local_dates[{index}] is not parseable as a date") from exc
    dates = sorted(set(dates))
    if len(dates) < 2:
        return _context(False, "insufficient_session_days", observed_session_day_count=len(dates))
    maximum_gap_days = max((right - left).days for left, right in zip(dates, dates[1:]))
    threshold_days = 3
    if maximum_gap_days <= threshold_days:
        return _context(
            True,
            None,
            observed_session_day_count=len(dates),
            maximum_session_day_gap_days=maximum_gap_days,
            maximum_gap_threshold_days=threshold_days,
        )
    return _context(False, "maximum_gap_above_threshold", maximum_session_day_gap_days=maximum_gap_days, maximum_gap_threshold_days=threshold_days)


def evaluate_diabetes_aerobic_session_gap_over_2_days(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("confirmed_diabetes_context"), "confirmed_diabetes_context"):
        return _context(False, "diabetes_context_not_confirmed")
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    provider = input_fixture.get("provider_platform")
    if provider not in {"apple_health_export", "samsung_health_export"}:
        return _context(False, "unsupported_provider_platform")
    observation_start = _local_date(input_fixture.get("observation_start_day"), "observation_start_day")
    through_day = _local_date(input_fixture.get("through_day"), "through_day")
    if through_day < observation_start:
        raise TriggerReferenceError("through_day must not precede observation_start_day")
    qualifying_days = _local_date_set(
        input_fixture.get("source_qualified_aerobic_activity_days", []),
        "source_qualified_aerobic_activity_days",
    )
    reset_days = _local_date_set(
        input_fixture.get("other_recorded_activity_reset_days", []),
        "other_recorded_activity_reset_days",
    )
    last_signal_day = observation_start.toordinal() - 1
    last_reset_mode = "observation_start"
    emitted = False
    day_ordinal = observation_start.toordinal()
    while day_ordinal <= through_day.toordinal():
        day = datetime.fromordinal(day_ordinal).date()
        if day in qualifying_days or day in reset_days:
            last_signal_day = day_ordinal
            last_reset_mode = (
                "source_qualified_activity_day"
                if day in qualifying_days
                else "recorded_activity_context"
            )
            emitted = False
        elif day_ordinal - last_signal_day >= 3 and not emitted:
            return _context(
                True,
                None,
                provider_platform=provider,
                candidate_day=day.isoformat(),
                gap_threshold_days=2,
                day_3_emit_once=True,
                trigger_evidence_mode="estimated_no_recorded_exercise",
                last_reset_day=None
                if last_reset_mode == "observation_start"
                else datetime.fromordinal(last_signal_day).date().isoformat(),
                last_reset_mode=last_reset_mode,
                no_signal_interpretation="estimated_no_recorded_exercise_not_confirmed_no_exercise",
            )
        day_ordinal += 1
    return _context(
        False,
        "no_gap_candidate_in_observation_window",
        provider_platform=provider,
        gap_threshold_days=2,
    )


def evaluate_recorded_exercise_timing_pattern(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    raw_times = input_fixture.get("session_start_times")
    if not isinstance(raw_times, list):
        raise TriggerReferenceError("session_start_times must be an array")
    minutes = sorted({_hhmm_to_minutes(value, f"session_start_times[{index}]") for index, value in enumerate(raw_times)})
    if len(minutes) < 3:
        return _context(False, "insufficient_session_days", observed_session_day_count=len(minutes))
    gaps = [right - left for left, right in zip(minutes, minutes[1:])]
    gaps.append((minutes[0] + 1440) - minutes[-1])
    circular_spread_hours = (1440 - max(gaps)) / 60.0
    threshold_hours = 6
    if circular_spread_hours <= threshold_hours:
        return _context(
            True,
            None,
            observed_session_day_count=len(minutes),
            circular_start_time_spread_hours=_rounded(circular_spread_hours),
            circular_spread_threshold_hours=threshold_hours,
        )
    return _context(False, "circular_spread_above_threshold", circular_start_time_spread_hours=_rounded(circular_spread_hours), circular_spread_threshold_hours=threshold_hours)


def evaluate_running_speed_personal_pacing(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    prior_days = int(_num(input_fixture.get("prior_observed_running_days"), "prior_observed_running_days"))
    if prior_days < 14:
        return _context(False, "insufficient_prior_observed_running_days", baseline_observed_day_count=prior_days)
    current = _num(input_fixture.get("current_daily_median_running_speed_km_per_hr"), "current_daily_median_running_speed_km_per_hr")
    baseline = _num(input_fixture.get("prior_14_observed_day_median_running_speed_km_per_hr"), "prior_14_observed_day_median_running_speed_km_per_hr")
    if current < baseline:
        return _context(
            True,
            None,
            current_daily_median_running_speed_km_per_hr=_rounded(current),
            prior_14_observed_day_median_running_speed_km_per_hr=_rounded(baseline),
            baseline_observed_day_count=14,
        )
    return _context(False, "current_not_below_prior_median", baseline_observed_day_count=prior_days)


def evaluate_running_power_activity_distribution(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    prior_days = int(_num(input_fixture.get("prior_observed_running_days"), "prior_observed_running_days"))
    if prior_days < 14:
        return _context(False, "insufficient_prior_observed_running_days", baseline_observed_day_count=prior_days)
    current = _num(input_fixture.get("current_daily_median_running_power_watt"), "current_daily_median_running_power_watt")
    baseline = _num(input_fixture.get("prior_14_observed_day_median_running_power_watt"), "prior_14_observed_day_median_running_power_watt")
    threshold = 1.2
    ratio = current / baseline
    if ratio >= threshold:
        return _context(
            True,
            None,
            current_daily_median_running_power_watt=_rounded(current),
            prior_14_observed_day_median_running_power_watt=_rounded(baseline),
            ratio_to_prior_median=_rounded(ratio),
            ratio_threshold_to_prior_median=threshold,
            baseline_observed_day_count=14,
        )
    return _context(False, "current_below_1_2x_prior_median", ratio_to_prior_median=_rounded(ratio), ratio_threshold_to_prior_median=threshold)


def evaluate_weekly_low_activity_volume_reactivation(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    current = _num(input_fixture.get("current_seven_day_activity_minutes"), "current_seven_day_activity_minutes")
    prior_totals = _positive_numbers(
        input_fixture.get("prior_three_positive_week_totals_minutes"),
        "prior_three_positive_week_totals_minutes",
    )
    if len(prior_totals) < 3:
        return _context(False, "insufficient_prior_positive_week_windows", prior_positive_week_count=len(prior_totals))
    prior = prior_totals[-3:]
    baseline = median(prior)
    if baseline <= 0:
        return _context(False, "prior_median_zero_or_missing")
    if not _bool(input_fixture.get("new_below_baseline_crossing"), "new_below_baseline_crossing"):
        return _context(False, "not_new_below_baseline_crossing")
    if not _bool(input_fixture.get("quiet_window_elapsed"), "quiet_window_elapsed"):
        return _context(False, "quiet_window_not_elapsed")
    threshold = 0.5
    ratio = current / baseline
    if ratio < threshold:
        return _context(
            True,
            None,
            current_seven_day_activity_minutes=_rounded(current),
            prior_three_positive_week_median_minutes=_rounded(baseline),
            prior_positive_week_count=3,
            ratio_to_prior_median=_rounded(ratio),
            threshold_ratio_to_prior_median=threshold,
            new_below_baseline_crossing=True,
            quiet_window_elapsed=True,
        )
    return _context(
        False,
        "current_not_below_half_prior_median",
        ratio_to_prior_median=_rounded(ratio),
        threshold_ratio_to_prior_median=threshold,
    )


def evaluate_activity_volume_baseline_gap_small_reentry(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("quiet_window_elapsed"), "quiet_window_elapsed"):
        return _context(False, "quiet_window_not_elapsed")
    derivation_contract_id = input_fixture.get("derivation_contract_id")
    if not isinstance(derivation_contract_id, str) or not derivation_contract_id:
        raise TriggerReferenceError("derivation_contract_id must be a non-empty string")
    source_path_kind = input_fixture.get("source_path_kind")
    if source_path_kind not in {"baseline_drop", "two_day_below_half_gap", "no_positive_gap"}:
        raise TriggerReferenceError("source_path_kind must be baseline_drop, two_day_below_half_gap, or no_positive_gap")
    prior = _positive_numbers(input_fixture.get("prior_14_positive_values"), "prior_14_positive_values")
    minimum_prior = 7
    if len(prior) < minimum_prior:
        return _context(False, "insufficient_prior_positive_days", prior_positive_day_count=len(prior))
    baseline = median(prior)
    if baseline <= 0:
        return _context(False, "prior_median_zero_or_missing")
    threshold = 0.5
    if source_path_kind == "no_positive_gap":
        gap_days = int(_num(input_fixture.get("consecutive_gap_days"), "consecutive_gap_days"))
        required_gap_days = int(_num(input_fixture.get("required_gap_days"), "required_gap_days"))
        if gap_days >= required_gap_days:
            return _context(
                True,
                None,
                derivation_contract_id=derivation_contract_id,
                source_path_kind=source_path_kind,
                consecutive_gap_days=gap_days,
                required_gap_days=required_gap_days,
                baseline_window_days=14,
                minimum_prior_positive_days=minimum_prior,
                threshold_ratio_to_prior_median=threshold,
            )
        return _context(False, "gap_condition_not_met", consecutive_gap_days=gap_days, required_gap_days=required_gap_days)
    current = _num(input_fixture.get("current_daily_value"), "current_daily_value")
    ratio = current / baseline
    if source_path_kind == "two_day_below_half_gap":
        previous = _num(input_fixture.get("previous_daily_value"), "previous_daily_value")
        previous_ratio = previous / baseline
        if ratio < threshold and previous_ratio < threshold:
            return _context(
                True,
                None,
                derivation_contract_id=derivation_contract_id,
                source_path_kind=source_path_kind,
                current_daily_value=_rounded(current),
                previous_daily_value=_rounded(previous),
                prior_positive_day_median=_rounded(baseline),
                ratio_to_prior_median=_rounded(ratio),
                previous_ratio_to_prior_median=_rounded(previous_ratio),
                baseline_window_days=14,
                minimum_prior_positive_days=minimum_prior,
                threshold_ratio_to_prior_median=threshold,
            )
        return _context(False, "gap_condition_not_met", ratio_to_prior_median=_rounded(ratio), previous_ratio_to_prior_median=_rounded(previous_ratio))
    if ratio < threshold:
        return _context(
            True,
            None,
            derivation_contract_id=derivation_contract_id,
            source_path_kind=source_path_kind,
            current_daily_value=_rounded(current),
            prior_positive_day_median=_rounded(baseline),
            ratio_to_prior_median=_rounded(ratio),
            baseline_window_days=14,
            minimum_prior_positive_days=minimum_prior,
            threshold_ratio_to_prior_median=threshold,
        )
    return _context(False, "current_not_below_half_prior_median", ratio_to_prior_median=_rounded(ratio))


def evaluate_short_sleep_cognitive_load_light_planning(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    valid_prior_nights = int(_num(input_fixture.get("valid_prior_nights"), "valid_prior_nights"))
    if valid_prior_nights < 7:
        return _context(False, "insufficient_prior_valid_nights")
    current = _num(input_fixture.get("current_sleep_minutes"), "current_sleep_minutes")
    baseline = _num(input_fixture.get("prior_valid_night_median_minutes"), "prior_valid_night_median_minutes")
    threshold = 0.8
    if current < threshold * baseline:
        return _context(True, None, short_sleep_ratio_threshold=threshold)
    return _context(False, "sleep_not_below_threshold", short_sleep_ratio_threshold=threshold)


def evaluate_long_wake_low_activity_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("sleep_wake_record_present"), "sleep_wake_record_present"):
        return _context(False, "missing_sleep_wake_record")
    if not _bool(input_fixture.get("activity_or_presence_record_present"), "activity_or_presence_record_present"):
        return _context(False, "missing_activity_or_presence_record")
    if not _bool(input_fixture.get("no_recent_equivalent_answer"), "no_recent_equivalent_answer"):
        return _context(False, "recent_equivalent_answer_present")
    if not _bool(input_fixture.get("red_flag_or_clinician_boundary_clear"), "red_flag_or_clinician_boundary_clear"):
        return _context(False, "red_flag_or_clinician_boundary_not_clear")
    wake_hours = _num(input_fixture.get("wake_hours_at_prompt"), "wake_hours_at_prompt")
    current_activity = _num(input_fixture.get("current_activity_until_prompt"), "current_activity_until_prompt")
    prior_activity = _positive_numbers(input_fixture.get("prior_activity_until_prompt_values"), "prior_activity_until_prompt_values")
    prior_sleep = _positive_numbers(input_fixture.get("prior_sleep_duration_minutes"), "prior_sleep_duration_minutes")
    minimum_activity_days = 7
    minimum_sleep_nights = 6
    if len(prior_activity) < minimum_activity_days:
        return _context(False, "insufficient_prior_activity_days", prior_activity_day_count=len(prior_activity))
    if len(prior_sleep) < minimum_sleep_nights:
        return _context(False, "insufficient_prior_sleep_nights", prior_sleep_night_count=len(prior_sleep))
    activity_median = median(prior_activity)
    low_activity_threshold = 0.5
    ratio = current_activity / activity_median if activity_median > 0 else 0.0
    long_wake_threshold = 10.0
    if wake_hours >= long_wake_threshold and ratio <= low_activity_threshold:
        return _context(
            True,
            None,
            wake_hours_at_prompt=_rounded(wake_hours),
            long_wake_min_hours_at_prompt=long_wake_threshold,
            current_activity_until_prompt=_rounded(current_activity),
            prior_activity_until_prompt_median=_rounded(activity_median),
            low_activity_ratio_to_prior_median=_rounded(ratio),
            low_activity_threshold_ratio=low_activity_threshold,
            prior_activity_day_count=len(prior_activity),
            prior_sleep_night_count=len(prior_sleep),
            no_recent_equivalent_answer=True,
        )
    return _context(
        False,
        "long_wake_low_activity_context_not_met",
        wake_hours_at_prompt=_rounded(wake_hours),
        low_activity_ratio_to_prior_median=_rounded(ratio),
        low_activity_threshold_ratio=low_activity_threshold,
    )


def evaluate_recorded_activity_pattern_consistency_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    provider = input_fixture.get("provider_platform")
    if provider not in {"apple_health_export", "samsung_health_export", "health_connect"}:
        return _context(False, "unsupported_provider_platform")
    source_path = input_fixture.get("source_path_key")
    if not isinstance(source_path, str) or not source_path:
        return _context(False, "missing_source_path_key")
    window_length = int(_num(input_fixture.get("window_length_days"), "window_length_days"))
    if window_length < 7:
        return _context(False, "insufficient_window_coverage", window_length_days=window_length)
    values = _positive_numbers(input_fixture.get("positive_window_values"), "positive_window_values")
    minimum = int(_num(input_fixture.get("minimum_positive_count"), "minimum_positive_count"))
    if len(values) < minimum:
        return _context(False, "insufficient_positive_values", positive_day_or_session_count=len(values))
    threshold = _num(input_fixture.get("relative_spread_threshold"), "relative_spread_threshold")
    baseline = median(values)
    if baseline <= 0:
        return _context(False, "zero_or_missing_median")
    relative_spread = (max(values) - min(values)) / baseline
    if relative_spread <= threshold:
        return _context(
            True,
            None,
            provider_platform=provider,
            source_path_key=source_path,
            positive_day_or_session_count=len(values),
            window_length_days=window_length,
            relative_spread=_rounded(relative_spread),
            relative_spread_threshold=_rounded(threshold),
            minimum_positive_count=minimum,
        )
    return _context(
        False,
        "relative_spread_above_threshold",
        provider_platform=provider,
        source_path_key=source_path,
        positive_day_or_session_count=len(values),
        relative_spread=_rounded(relative_spread),
        relative_spread_threshold=_rounded(threshold),
    )


def evaluate_recorded_activity_recurrence_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("complete_current_window"), "complete_current_window"):
        return _context(False, "incomplete_current_window")
    if not _bool(input_fixture.get("complete_prior_window"), "complete_prior_window"):
        return _context(False, "incomplete_prior_window")
    source_path = input_fixture.get("source_path_key")
    if source_path not in {"apple_stand_hour", "samsung_longest_active_bout", "health_connect_exercise_session"}:
        return _context(False, "unsupported_source_path_key", source_path_key=source_path)
    current = int(_num(input_fixture.get("current_positive_day_count"), "current_positive_day_count"))
    prior = int(_num(input_fixture.get("prior_positive_day_count"), "prior_positive_day_count"))
    quiet = _bool(input_fixture.get("quiet_window_satisfied"), "quiet_window_satisfied")
    payload = {
        "current_window_days": 7,
        "current_positive_day_count": current,
        "prior_window_days": 7,
        "prior_positive_day_count": prior,
        "quiet_window_days": 3,
        "source_path_key": source_path,
        "provider_source_status": "primary_replay_source",
    }
    if not quiet:
        return _context(False, "quiet_window_not_satisfied", **payload)
    if current < 3:
        return _context(False, "current_positive_days_below_3", **payload)
    if prior >= 3:
        return _context(False, "prior_positive_days_at_or_above_3", **payload)
    return _context(True, None, **payload)


def evaluate_high_load_low_movement_first_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    prior_load = _num(input_fixture.get("prior_day_activity_load"), "prior_day_activity_load")
    current_movement = _num(input_fixture.get("current_day_movement_value"), "current_day_movement_value")
    load_values = _positive_numbers(input_fixture.get("prior_14_positive_load_values"), "prior_14_positive_load_values")
    movement_values = _positive_numbers(
        input_fixture.get("prior_14_positive_movement_values"),
        "prior_14_positive_movement_values",
    )
    minimum = 7
    if len(load_values) < minimum:
        return _context(False, "insufficient_prior_positive_load_days", prior_positive_load_day_count=len(load_values))
    if len(movement_values) < minimum:
        return _context(
            False,
            "insufficient_prior_positive_movement_days",
            prior_positive_movement_day_count=len(movement_values),
        )
    if current_movement <= 0:
        return _context(False, "current_movement_not_positive", current_day_movement_value=_rounded(current_movement))
    load_median = median(load_values)
    movement_median = median(movement_values)
    high_threshold = 1.5
    low_threshold = 0.5
    load_ratio = prior_load / load_median if load_median > 0 else 0
    movement_ratio = current_movement / movement_median if movement_median > 0 else 0
    payload = {
        "prior_day_activity_load": _rounded(prior_load),
        "prior_load_positive_day_count": len(load_values),
        "prior_load_positive_day_median": _rounded(load_median),
        "high_load_ratio_threshold": high_threshold,
        "load_ratio_to_median": _rounded(load_ratio),
        "current_day_movement_value": _rounded(current_movement),
        "prior_movement_positive_day_count": len(movement_values),
        "prior_movement_positive_day_median": _rounded(movement_median),
        "low_movement_ratio_threshold": low_threshold,
        "movement_ratio_to_median": _rounded(movement_ratio),
        "first_anchor_copy_only": True,
    }
    if load_ratio >= high_threshold and movement_ratio <= low_threshold:
        return _context(True, None, **payload)
    return _context(False, "high_load_low_movement_context_not_met", **payload)


def evaluate_multi_day_gap_today_reentry_anchor(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    baseline = _positive_numbers(input_fixture.get("prior_positive_activity_values"), "prior_positive_activity_values")
    minimum = 7
    if len(baseline) < minimum:
        return _context(False, "insufficient_prior_positive_activity_days", prior_positive_day_count=len(baseline))
    previous = input_fixture.get("previous_two_day_activity_values")
    if not isinstance(previous, list) or len(previous) != 2:
        raise TriggerReferenceError("previous_two_day_activity_values must contain exactly two source-observed values")
    previous_values = [_num(value, f"previous_two_day_activity_values[{index}]") for index, value in enumerate(previous)]
    current = _num(input_fixture.get("current_day_activity_value"), "current_day_activity_value")
    baseline_median = median(baseline)
    gap_threshold = 0.2
    reentry_threshold = 0.5
    gap_met = all(value <= gap_threshold * baseline_median for value in previous_values)
    current_ratio = current / baseline_median if baseline_median > 0 else 0
    payload = {
        "prior_positive_day_count": len(baseline),
        "prior_positive_day_median": _rounded(baseline_median),
        "gap_low_ratio_threshold": gap_threshold,
        "previous_two_day_activity_values": [_rounded(value) for value in previous_values],
        "previous_two_days_low": gap_met,
        "current_day_activity_value": _rounded(current),
        "reentry_low_ratio_threshold": reentry_threshold,
        "current_ratio_to_median": _rounded(current_ratio),
        "nonjudgmental_message_boundary": True,
    }
    if gap_met and 0 < current <= reentry_threshold * baseline_median:
        return _context(True, None, **payload)
    if current <= 0:
        return _context(False, "current_day_not_positive_reentry", **payload)
    return _context(False, "multi_day_gap_reentry_context_not_met", **payload)


def evaluate_active_energy_activity_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("energy_feeling_checkin_context_available"), "energy_feeling_checkin_context_available"):
        return _context(False, "missing_energy_feeling_checkin_context")
    current = _num(input_fixture.get("current_day_active_energy"), "current_day_active_energy")
    prior = _positive_numbers(input_fixture.get("prior_14_positive_active_energy_values"), "prior_14_positive_active_energy_values")
    minimum = 7
    if len(prior) < minimum:
        return _context(False, "insufficient_prior_positive_energy_days", prior_positive_energy_day_count=len(prior))
    if current <= 0:
        return _context(False, "current_active_energy_not_positive", current_day_active_energy=_rounded(current))
    baseline = median(prior)
    threshold = 1.5
    ratio = current / baseline if baseline > 0 else 0
    payload = {
        "current_day_active_energy": _rounded(current),
        "prior_positive_energy_day_count": len(prior),
        "prior_positive_energy_median": _rounded(baseline),
        "high_energy_ratio_threshold": threshold,
        "energy_ratio_to_median": _rounded(ratio),
        "energy_feeling_checkin_context_available": True,
    }
    if ratio >= threshold:
        return _context(True, None, **payload)
    return _context(False, "active_energy_ratio_below_threshold", **payload)


def evaluate_high_active_energy_no_extra_push(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    current = _num(input_fixture.get("current_day_active_energy"), "current_day_active_energy")
    prior = _positive_numbers(input_fixture.get("prior_14_positive_active_energy_values"), "prior_14_positive_active_energy_values")
    minimum = 7
    if len(prior) < minimum:
        return _context(False, "insufficient_prior_positive_energy_days", prior_positive_energy_day_count=len(prior))
    if current <= 0:
        return _context(False, "current_active_energy_not_positive", current_day_active_energy=_rounded(current))
    baseline = median(prior)
    threshold = 1.5
    ratio = current / baseline if baseline > 0 else 0
    payload = {
        "current_day_active_energy": _rounded(current),
        "prior_positive_energy_day_count": len(prior),
        "prior_positive_energy_median": _rounded(baseline),
        "high_energy_ratio_threshold": threshold,
        "energy_ratio_to_median": _rounded(ratio),
        "interpretation_boundary": "provider_specific_active_energy_context_only_no_calorie_equivalence_or_recovery_state",
    }
    if ratio >= threshold:
        return _context(True, None, **payload)
    return _context(False, "active_energy_ratio_below_threshold", **payload)


def evaluate_mixed_intensity_equivalence(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("complete_comparison_window"), "complete_comparison_window"):
        return _context(False, "incomplete_comparison_window")
    if not _bool(input_fixture.get("nonoverlapping_interval_identity"), "nonoverlapping_interval_identity"):
        return _context(False, "unresolved_overlap_or_duplicate")
    moderate = _num(input_fixture.get("moderate_minutes"), "moderate_minutes")
    vigorous = _num(input_fixture.get("vigorous_minutes"), "vigorous_minutes")
    if moderate < 0 or vigorous < 0:
        raise TriggerReferenceError("moderate_minutes and vigorous_minutes must be non-negative")
    equivalent = moderate + 2.0 * vigorous
    provider_status = input_fixture.get("provider_source_status", "primary_replay_source")
    if not isinstance(provider_status, str) or not provider_status:
        raise TriggerReferenceError("provider_source_status must be a non-empty string")
    payload = {
        "moderate_minutes": _rounded(moderate),
        "vigorous_minutes": _rounded(vigorous),
        "moderate_equivalent_activity_minutes": _rounded(equivalent),
        "conversion_rule": "moderate + 2 * vigorous",
        "provider_source_status": provider_status,
    }
    if equivalent > 0:
        return _context(True, None, **payload)
    return _context(False, "no_source_qualified_moderate_or_vigorous_minutes", **payload)


def evaluate_post_exercise_hrr_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("completed_exercise_session"), "completed_exercise_session"):
        return _context(False, "missing_completed_exercise_session")
    if not _bool(input_fixture.get("qualified_post_exercise_recovery_window"), "qualified_post_exercise_recovery_window"):
        return _context(False, "missing_qualified_post_exercise_recovery_window")
    if not _bool(input_fixture.get("provider_quality_and_sampling"), "provider_quality_and_sampling"):
        return _context(False, "missing_provider_quality_or_sampling")
    if not _bool(input_fixture.get("breathing_feel_checkin_context_available"), "breathing_feel_checkin_context_available"):
        return _context(False, "missing_breathing_feel_checkin_context")
    provider_status = input_fixture.get("provider_source_status", "primary_replay_source")
    if not isinstance(provider_status, str) or not provider_status:
        raise TriggerReferenceError("provider_source_status must be a non-empty string")
    payload = {
        "post_exercise_hrr_window_context_present": True,
        "provider_source_status": provider_status,
        "interpretation_boundary": "context_presence_only_no_hrr_threshold_or_recovery_state",
    }
    return _context(True, None, **payload)


def evaluate_hrv_short_sleep_body_feel_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not _bool(input_fixture.get("source_identity_present"), "source_identity_present"):
        return _context(False, "missing_source_identity")
    if not _bool(input_fixture.get("valid_hrv_signal_and_timing"), "valid_hrv_signal_and_timing"):
        return _context(False, "missing_valid_hrv_signal_and_timing")
    if not _bool(input_fixture.get("sleep_wear_coverage_confidence"), "sleep_wear_coverage_confidence"):
        return _context(False, "missing_sleep_wear_coverage_confidence")
    if not _bool(input_fixture.get("no_recent_equivalent_feeling_answer"), "no_recent_equivalent_feeling_answer"):
        return _context(False, "recent_equivalent_feeling_answer_present")
    sleep_hours = _num(input_fixture.get("sleep_hours"), "sleep_hours")
    current_hrv = _num(input_fixture.get("current_hrv"), "current_hrv")
    prior = _positive_numbers(input_fixture.get("prior_14_hrv_values"), "prior_14_hrv_values")
    minimum = 7
    if sleep_hours >= 6.0:
        return _context(False, "sleep_duration_not_short", sleep_hours=_rounded(sleep_hours), short_sleep_threshold_hours=6.0)
    if len(prior) < minimum:
        return _context(False, "insufficient_prior_hrv_days", prior_hrv_day_count=len(prior))
    if current_hrv <= 0:
        return _context(False, "current_hrv_not_positive", current_hrv=_rounded(current_hrv))
    baseline = median(prior)
    threshold = 0.8
    ratio = current_hrv / baseline if baseline > 0 else 0
    payload = {
        "sleep_hours": _rounded(sleep_hours),
        "short_sleep_threshold_hours": 6.0,
        "current_hrv": _rounded(current_hrv),
        "prior_hrv_day_count": len(prior),
        "prior_hrv_median": _rounded(baseline),
        "low_hrv_ratio_threshold": threshold,
        "hrv_ratio_to_median": _rounded(ratio),
        "no_recent_equivalent_feeling_answer": True,
        "interpretation_boundary": "context_presence_only_no_hrv_recovery_or_readiness_state",
    }
    if ratio <= threshold:
        return _context(True, None, hrv_short_sleep_body_feel_context_present=True, **payload)
    return _context(False, "hrv_ratio_above_low_threshold", **payload)


def evaluate_resting_hr_load_sleep_body_feel_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    required_booleans = [
        "source_identity_present",
        "valid_resting_hr_signal_and_timing",
        "device_presence_or_wear_confidence",
        "missing_wear_filter_passed",
        "acute_symptom_or_clinical_concern_filter_passed",
        "no_recent_equivalent_feeling_answer",
    ]
    for field in required_booleans:
        if not _bool(input_fixture.get(field), field):
            return _context(False, f"missing_or_false_{field}")

    sleep_hours = _num(input_fixture.get("sleep_hours"), "sleep_hours")
    current_rhr = _num(input_fixture.get("current_resting_hr"), "current_resting_hr")
    prior_rhr = _positive_numbers(input_fixture.get("prior_14_resting_hr_values"), "prior_14_resting_hr_values")
    prior_day_energy = _num(input_fixture.get("prior_day_active_energy"), "prior_day_active_energy")
    prior_energy = _positive_numbers(input_fixture.get("prior_14_active_energy_values"), "prior_14_active_energy_values")
    if sleep_hours >= 6.0:
        return _context(False, "sleep_duration_not_short", sleep_hours=_rounded(sleep_hours))
    if len(prior_rhr) < 7:
        return _context(False, "insufficient_prior_resting_hr_days", prior_resting_hr_day_count=len(prior_rhr))
    if len(prior_energy) < 7:
        return _context(False, "insufficient_prior_active_energy_days", prior_active_energy_day_count=len(prior_energy))
    if current_rhr <= 0 or prior_day_energy <= 0:
        return _context(False, "current_resting_hr_or_prior_day_energy_not_positive")
    prior_rhr_median = median(prior_rhr)
    prior_energy_median = median(prior_energy)
    rhr_ratio = current_rhr / prior_rhr_median
    energy_ratio = prior_day_energy / prior_energy_median
    payload = {
        "sleep_hours": _rounded(sleep_hours),
        "short_sleep_threshold_hours": 6.0,
        "current_resting_hr": _rounded(current_rhr),
        "prior_resting_hr_day_count": len(prior_rhr),
        "prior_resting_hr_median": _rounded(prior_rhr_median),
        "resting_hr_ratio_to_median": _rounded(rhr_ratio),
        "resting_hr_high_ratio_threshold": 1.08,
        "prior_day_active_energy": _rounded(prior_day_energy),
        "prior_active_energy_day_count": len(prior_energy),
        "prior_active_energy_median": _rounded(prior_energy_median),
        "active_energy_ratio_to_median": _rounded(energy_ratio),
        "active_energy_high_ratio_threshold": 1.5,
        "no_recent_equivalent_feeling_answer": True,
        "interpretation_boundary": "context_presence_only_no_rhr_recovery_or_readiness_state",
    }
    if rhr_ratio >= 1.08 and energy_ratio >= 1.5:
        return _context(True, None, resting_hr_load_sleep_body_feel_context_present=True, **payload)
    if rhr_ratio < 1.08:
        return _context(False, "resting_hr_ratio_below_threshold", resting_hr_load_sleep_body_feel_context_present=False, **payload)
    return _context(False, "prior_day_active_energy_ratio_below_threshold", resting_hr_load_sleep_body_feel_context_present=False, **payload)


def evaluate_resting_respiratory_rate_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    required_booleans = [
        "source_identity_present",
        "rest_or_sleep_measurement_context",
        "measurement_quality_and_coverage",
        "symptom_or_red_flag_filter_passed",
        "condition_checkin_context_available",
    ]
    for field in required_booleans:
        if not _bool(input_fixture.get(field), field):
            return _context(False, f"missing_or_false_{field}")
    current = _num(input_fixture.get("current_respiratory_rate"), "current_respiratory_rate")
    prior = _positive_numbers(input_fixture.get("prior_14_respiratory_rate_values"), "prior_14_respiratory_rate_values")
    if len(prior) < 7:
        return _context(False, "insufficient_prior_respiratory_rate_days", prior_respiratory_rate_day_count=len(prior))
    prior_median = median(prior)
    ratio = current / prior_median
    payload = {
        "resting_respiratory_rate_context_present": ratio >= 1.08,
        "current_respiratory_rate": _rounded(current),
        "prior_respiratory_rate_day_count": len(prior),
        "prior_respiratory_rate_median": _rounded(prior_median),
        "respiratory_rate_ratio_to_median": _rounded(ratio),
        "respiratory_rate_high_ratio_threshold": 1.08,
        "interpretation_boundary": "context_presence_only_no_respiratory_disease_or_recovery_state",
    }
    if ratio >= 1.08:
        return _context(True, None, **payload)
    return _context(False, "respiratory_rate_ratio_below_threshold", **payload)


def evaluate_spo2_post_exercise_breathing_context(input_fixture: dict[str, Any]) -> dict[str, Any]:
    required_booleans = [
        "source_identity_present",
        "known_exercise_session",
        "symptom_or_red_flag_filter_passed",
        "breathing_feel_checkin_context_available",
    ]
    for field in required_booleans:
        if not _bool(input_fixture.get(field), field):
            return _context(False, f"missing_or_false_{field}")
    minutes = _num(input_fixture.get("minutes_after_exercise_end"), "minutes_after_exercise_end")
    coverage = _num(input_fixture.get("coverage_rate"), "coverage_rate")
    spo2 = _num(input_fixture.get("spo2"), "spo2")
    low = _num(input_fixture.get("spo2_min"), "spo2_min")
    high = _num(input_fixture.get("spo2_max"), "spo2_max")
    if not (0 <= minutes <= 180):
        return _context(False, "outside_post_exercise_window", minutes_after_exercise_end=_rounded(minutes))
    if coverage < 80:
        return _context(False, "coverage_below_threshold", coverage_rate=_rounded(coverage), coverage_rate_threshold=80)
    if not (0 < low <= spo2 <= high <= 100):
        return _context(False, "invalid_spo2_min_point_max_order")
    return _context(
        True,
        None,
        spo2_post_exercise_breathing_context_present=True,
        minutes_after_exercise_end=_rounded(minutes),
        post_exercise_window_minutes=180,
        coverage_rate=_rounded(coverage),
        coverage_rate_threshold=80,
        interpretation_boundary="context_presence_only_no_spo2_threshold_or_oxygenation_state",
    )


def evaluate_same_pace_higher_hr_body_feel_checkin(input_fixture: dict[str, Any]) -> dict[str, Any]:
    required_booleans = [
        "source_identity_present",
        "heart_rate_signal_quality_and_coverage",
        "wear_or_phone_presence_confidence",
        "overlap_and_duplicate_resolution",
        "acute_illness_injury_or_red_flag_filter_passed",
        "no_recent_equivalent_body_feel_answer",
    ]
    for field in required_booleans:
        if not _bool(input_fixture.get(field), field):
            return _context(False, f"missing_or_false_{field}")
    current_speed = _num(input_fixture.get("current_speed"), "current_speed")
    current_hr = _num(input_fixture.get("current_heart_rate"), "current_heart_rate")
    prior_speeds = _positive_numbers(input_fixture.get("prior_comparable_speed_values"), "prior_comparable_speed_values")
    prior_hr = _positive_numbers(input_fixture.get("prior_comparable_heart_rate_values"), "prior_comparable_heart_rate_values")
    prior_count = min(len(prior_speeds), len(prior_hr))
    if prior_count < 7:
        return _context(False, "insufficient_prior_comparable_bouts", prior_comparable_bout_count=prior_count)
    speed_median = median(prior_speeds)
    hr_median = median(prior_hr)
    speed_delta_ratio = abs(current_speed - speed_median) / speed_median
    hr_ratio = current_hr / hr_median
    payload = {
        "same_pace_higher_hr_body_feel_context_present": speed_delta_ratio <= 0.05 and hr_ratio >= 1.10,
        "current_speed": _rounded(current_speed),
        "prior_comparable_speed_median": _rounded(speed_median),
        "speed_similarity_max_delta_ratio": 0.05,
        "speed_delta_ratio": _rounded(speed_delta_ratio),
        "current_heart_rate": _rounded(current_hr),
        "prior_comparable_heart_rate_median": _rounded(hr_median),
        "heart_rate_high_ratio_threshold": 1.10,
        "heart_rate_ratio_to_median": _rounded(hr_ratio),
        "prior_comparable_bout_count": prior_count,
        "interpretation_boundary": "context_presence_only_no_cause_fitness_or_recovery_state",
    }
    if speed_delta_ratio > 0.05:
        return _context(False, "pace_not_similar", **payload)
    if hr_ratio < 1.10:
        return _context(False, "heart_rate_ratio_below_threshold", **payload)
    return _context(True, None, **payload)


ALL_EVALUATORS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "trigger_general_multi_day_activity_pattern_context": evaluate_multi_day_activity_pattern_context,
    "trigger_general_daily_step_pattern_keep_margin": evaluate_multi_day_activity_pattern_context,
    "trigger_general_daily_step_pattern_flexible_window": evaluate_multi_day_activity_pattern_context,
    "trigger_general_activity_load_gradual_progression": evaluate_activity_load_gradual_progression,
    "trigger_general_activity_load_spike_no_extra_push": evaluate_activity_load_gradual_progression,
    "trigger_general_activity_load_spike_insert_easy_day": evaluate_activity_load_gradual_progression,
    "trigger_general_recent_activity_load_spike_context": evaluate_activity_load_gradual_progression,
    "trigger_general_recent_activity_load_spike_no_record_push": evaluate_activity_load_gradual_progression,
    "trigger_general_recent_activity_load_spike_no_new_normal": evaluate_activity_load_gradual_progression,
    "trigger_general_activity_load_return_to_baseline_checkin": evaluate_activity_load_return_to_baseline_checkin,
    "trigger_general_activity_load_return_keep_light": evaluate_activity_load_return_to_baseline_checkin,
    "trigger_general_activity_load_return_no_baseline_chase": evaluate_activity_load_return_to_baseline_checkin,
    "trigger_general_activity_load_spike_easy_buffer": evaluate_activity_load_spike_easy_buffer,
    "trigger_general_activity_load_high_after_quiet_no_stack_tomorrow": evaluate_activity_load_spike_easy_buffer,
    "trigger_general_activity_load_high_after_quiet_same_day_closeout": evaluate_activity_load_spike_easy_buffer,
    "trigger_pneumonia_recovery_high_after_quiet_lower_intensity": evaluate_pneumonia_recovery_high_after_quiet_lower_intensity,
    "trigger_pneumonia_fluid_routine_open": evaluate_pneumonia_fluid_routine_open,
    "trigger_pneumonia_household_support_open": evaluate_pneumonia_household_support_open,
    "trigger_htn_high_after_quiet_activity_load_lighten_next": evaluate_hypertension_high_after_quiet_activity_load_lighten_next,
    "trigger_htn_home_sodium_choice_open": evaluate_htn_home_sodium_choice_open,
    "trigger_htn_stress_practice_open": evaluate_htn_stress_practice_open,
    "trigger_diabetes_tobacco_support_open": evaluate_diabetes_tobacco_support_open,
    "trigger_cad_tobacco_support_open": evaluate_cad_tobacco_support_open,
    "trigger_cad_cardiac_rehab_support_open": evaluate_cad_cardiac_rehab_support_open,
    "trigger_pneumonia_followup_question_open": evaluate_pneumonia_followup_question_open,
    "trigger_diabetes_sleep_routine_open": evaluate_diabetes_sleep_routine_open,
    "trigger_cardiovascular_sleep_anchor_open": evaluate_cardiovascular_sleep_anchor_open,
    "trigger_cardio_meal_timing_anchor_open": evaluate_cardiovascular_meal_timing_anchor_open,
    "trigger_diabetes_sedentary_break_open": evaluate_diabetes_sedentary_break_open,
    "trigger_diabetes_sedentary_break_device": evaluate_diabetes_sedentary_break_device,
    "trigger_cardiovascular_device_inactivity_break": evaluate_cardiovascular_device_inactivity_break,
    "trigger_hypertension_sedentary_break_device": evaluate_hypertension_device_sedentary_break,
    "trigger_hypertension_sleep_hygiene_open": evaluate_hypertension_sleep_hygiene_open,
    "trigger_hypertension_sedentary_break_open": evaluate_hypertension_sedentary_break_open,
    "trigger_hypertension_meal_preparation_open": evaluate_hypertension_meal_preparation_open,
    "trigger_pneumonia_small_meal_routine_open": evaluate_pneumonia_small_meal_routine_open,
    "trigger_cardiovascular_meal_planning_open": evaluate_cardiovascular_meal_planning_open,
    "trigger_diabetes_regular_meal_routine_open": evaluate_diabetes_regular_meal_routine_open,
    "trigger_dyslipidemia_fibre_food_addition_open": evaluate_dyslipidemia_fibre_food_addition_open,
    "trigger_dyslipidemia_exercise_snack_open": evaluate_dyslipidemia_exercise_snack_open,
    "trigger_dyslipidemia_sleep_routine_open": evaluate_dyslipidemia_sleep_routine_open,
    "trigger_dyslipidemia_resistance_session_open": evaluate_dyslipidemia_resistance_session_open,
    "trigger_dyslipidemia_combined_aerobic_resistance_open": evaluate_dyslipidemia_combined_aerobic_resistance_open,
    "trigger_dyslipidemia_sedentary_break_open": evaluate_dyslipidemia_sedentary_break_open,
    "trigger_dyslipidemia_warmup_open": evaluate_dyslipidemia_warmup_open,
    "trigger_dyslipidemia_flexibility_open": evaluate_dyslipidemia_flexibility_open,
    "trigger_dyslipidemia_cooldown_walk_open": evaluate_dyslipidemia_cooldown_walk_open,
    "trigger_dyslipidemia_post_exercise_stand_break_open": evaluate_dyslipidemia_post_exercise_stand_break_open,
    "trigger_diabetes_meal_preparation_open": evaluate_diabetes_meal_preparation_open,
    "trigger_dyslipidemia_heart_healthy_food_choice_open": evaluate_dyslipidemia_heart_healthy_food_choice_open,
    "trigger_hypertension_home_bp_checkin_open": evaluate_hypertension_home_bp_checkin_open,
    "trigger_hypertension_followup_question_open": evaluate_hypertension_followup_question_open,
    "trigger_pneumonia_recovery_inactivity_gap_small_restart": evaluate_pneumonia_recovery_inactivity_gap_small_restart,
    "trigger_pneumonia_recovery_short_sleep_day_margin": evaluate_pneumonia_recovery_short_sleep_day_margin,
    "trigger_pneumonia_recovery_sleep_quiet_gap_light_break": evaluate_pneumonia_recovery_sleep_quiet_gap_light_break,
    "trigger_general_activity_pattern_variability_context": evaluate_activity_pattern_variability_context,
    "trigger_general_activity_variability_no_big_makeup_day": evaluate_activity_pattern_variability_context,
    "trigger_general_activity_variability_no_every_day_equal_chase": evaluate_activity_pattern_variability_context,
    "trigger_general_activity_sleep_timing_reflection": evaluate_activity_sleep_timing_reflection,
    "trigger_general_activity_sleep_timing_no_fixed_rule": evaluate_activity_sleep_timing_reflection,
    "trigger_general_activity_sleep_timing_one_anchor_not_perfect": evaluate_activity_sleep_timing_reflection,
    "trigger_general_activity_distribution_next_anchor": evaluate_activity_distribution_next_anchor,
    "trigger_general_activity_distribution_no_catchup_burst": evaluate_activity_distribution_next_anchor,
    "trigger_general_activity_distribution_one_window_not_every_window": evaluate_activity_distribution_next_anchor,
    "trigger_general_after_high_activity_low_movement_body_feel_checkin": evaluate_after_high_activity_low_movement_body_feel_checkin,
    "trigger_general_after_high_activity_low_movement_no_refill": evaluate_after_high_activity_low_movement_body_feel_checkin,
    "trigger_general_after_high_activity_low_movement_no_new_baseline": evaluate_after_high_activity_low_movement_body_feel_checkin,
    "trigger_general_brief_brisk_bout_next_anchor": evaluate_brief_brisk_bout_next_anchor,
    "trigger_general_brief_brisk_bout_keep_small": evaluate_brief_brisk_bout_next_anchor,
    "trigger_general_current_step_light_activity_context": evaluate_current_step_light_activity_context,
    "trigger_general_low_step_no_catchup_burst": evaluate_current_step_light_activity_context,
    "trigger_general_low_step_next_transition_anchor": evaluate_current_step_light_activity_context,
    "trigger_general_daily_step_pattern_consistency": evaluate_daily_step_pattern_consistency,
    "trigger_general_daily_step_pattern_no_target_chase": evaluate_daily_step_pattern_consistency,
    "trigger_general_daily_step_pattern_keep_margin_consistency_context": evaluate_daily_step_pattern_consistency,
    "trigger_general_daily_step_reference_no_extra_push": evaluate_daily_step_reference_no_extra_push,
    "trigger_general_daily_step_reference_keep_tomorrow_margin": evaluate_daily_step_reference_no_extra_push,
    "trigger_general_daily_step_reference_close_step_chase": evaluate_daily_step_reference_no_extra_push,
    "trigger_general_daily_sedentary_like_inactivity_above_8h_fact41": evaluate_daily_sedentary_like_inactivity_above_8h_fact41,
    "trigger_general_sedentary_like_inactivity_no_catchup_burst": evaluate_daily_sedentary_like_inactivity_above_8h_fact41,
    "trigger_general_sedentary_like_inactivity_first_break_early_anchor": evaluate_daily_sedentary_like_inactivity_above_8h_fact41,
    "trigger_general_weekly_activity_distribution_next_week_anchor": evaluate_weekly_activity_distribution_next_week_anchor,
    "trigger_general_weekly_activity_distribution_no_makeup_week": evaluate_weekly_activity_distribution_next_week_anchor,
    "trigger_general_weekly_activity_distribution_one_anchor_not_every_day": evaluate_weekly_activity_distribution_next_week_anchor,
    "trigger_general_walking_pace_drop_activity_pacing": evaluate_walking_pace_drop_activity_pacing,
    "trigger_general_walking_speed_drop_close_short": evaluate_walking_pace_drop_activity_pacing,
    "trigger_general_break_like_movement_reactivation": evaluate_break_like_movement_reactivation,
    "trigger_general_break_like_movement_keep_small": evaluate_break_like_movement_reactivation,
    "trigger_general_break_like_movement_next_gap_pre_anchor": evaluate_break_like_movement_reactivation,
    "trigger_general_inactivity_gap_move_prompt": evaluate_inactivity_gap_move_prompt,
    "trigger_general_inactivity_gap_easy_restart": evaluate_inactivity_gap_move_prompt,
    "trigger_general_inactivity_gap_transition_anchor": evaluate_inactivity_gap_move_prompt,
    "trigger_general_irregular_sleep_week_daytime_anchor": evaluate_irregular_sleep_week_daytime_anchor,
    "trigger_general_irregular_sleep_week_keep_anchor_small": evaluate_irregular_sleep_week_daytime_anchor,
    "trigger_general_irregular_sleep_week_no_fixed_rule": evaluate_irregular_sleep_week_daytime_anchor,
    "trigger_general_late_activity_sleep_winddown_anchor": evaluate_late_activity_sleep_winddown_anchor,
    "trigger_general_late_activity_next_time_finish_earlier": evaluate_late_activity_sleep_winddown_anchor,
    "trigger_general_late_activity_no_extra_evening_activity": evaluate_late_activity_sleep_winddown_anchor,
    "trigger_general_late_sleep_morning_first_activity_anchor": evaluate_late_sleep_morning_first_activity_anchor,
    "trigger_general_late_sleep_morning_keep_first_move_small": evaluate_late_sleep_morning_first_activity_anchor,
    "trigger_general_late_sleep_morning_no_evening_catchup": evaluate_late_sleep_morning_first_activity_anchor,
    "trigger_general_light_walking_activity_context": evaluate_light_walking_activity_context,
    "trigger_general_light_walking_apple_speed_context": evaluate_light_walking_apple_speed_context,
    "trigger_general_light_walking_keep_easy_pace_samsung": evaluate_light_walking_activity_context,
    "trigger_general_light_walking_keep_easy_pace_apple": evaluate_light_walking_apple_speed_context,
    "trigger_general_light_walking_shorten_before_speed_up_samsung": evaluate_light_walking_activity_context,
    "trigger_general_light_walking_shorten_before_speed_up_apple": evaluate_light_walking_apple_speed_context,
    "trigger_general_daily_mvpa_30min_gap_health_connect_intensity": evaluate_daily_mvpa_30min_gap_direct,
    "trigger_general_any_length_mvpa_health_connect_intensity": evaluate_any_length_mvpa_accumulation,
    "trigger_general_daily_mvpa_30min_gap_direct": evaluate_daily_mvpa_30min_gap_direct,
    "trigger_general_daily_mvpa_30min_gap_estimated": evaluate_daily_mvpa_30min_gap_estimated,
    "trigger_general_any_length_mvpa_accumulation": evaluate_any_length_mvpa_accumulation,
    "trigger_general_mvpa_gap_no_catchup_burst_daily_direct": evaluate_daily_mvpa_30min_gap_direct,
    "trigger_general_mvpa_gap_no_catchup_burst_daily_estimated": evaluate_daily_mvpa_30min_gap_estimated,
    "trigger_general_mvpa_gap_no_catchup_burst_daily_health_connect": evaluate_daily_mvpa_30min_gap_direct,
    "trigger_general_mvpa_gap_next_familiar_walking_anchor_daily_direct": evaluate_daily_mvpa_30min_gap_direct,
    "trigger_general_mvpa_gap_next_familiar_walking_anchor_daily_estimated": evaluate_daily_mvpa_30min_gap_estimated,
    "trigger_general_mvpa_gap_next_familiar_walking_anchor_daily_health_connect": evaluate_daily_mvpa_30min_gap_direct,
    "trigger_general_mvpa_gap_no_catchup_burst_weekly_any_length": evaluate_any_length_mvpa_accumulation,
    "trigger_general_mvpa_gap_no_catchup_burst_weekly_health_connect": evaluate_any_length_mvpa_accumulation,
    "trigger_general_mvpa_gap_next_familiar_walking_anchor_weekly_any_length": evaluate_any_length_mvpa_accumulation,
    "trigger_general_mvpa_gap_next_familiar_walking_anchor_weekly_health_connect": evaluate_any_length_mvpa_accumulation,
    "trigger_general_low_step_streak_no_catchup_anchor": evaluate_low_step_streak_no_catchup_anchor,
    "trigger_general_low_step_streak_plan_next_first_anchor": evaluate_low_step_streak_no_catchup_anchor,
    "trigger_general_low_step_streak_close_today_without_step_chase": evaluate_low_step_streak_no_catchup_anchor,
    "trigger_general_brief_brisk_bout_daily_route_anchor": evaluate_brief_brisk_bout_next_anchor,
    "trigger_general_quiet_gap_light_step_followthrough_anchor": evaluate_quiet_gap_light_step_followthrough_anchor,
    "trigger_general_quiet_gap_followthrough_keep_small": evaluate_quiet_gap_light_step_followthrough_anchor,
    "trigger_general_quiet_gap_followthrough_close_loop": evaluate_quiet_gap_light_step_followthrough_anchor,
    "trigger_general_short_sleep_low_activity_midday_floor_anchor": evaluate_short_sleep_low_activity_midday_floor_anchor,
    "trigger_general_short_sleep_low_activity_no_afternoon_catchup": evaluate_short_sleep_low_activity_midday_floor_anchor,
    "trigger_general_short_sleep_low_activity_no_step_chase": evaluate_short_sleep_low_activity_midday_floor_anchor,
    "trigger_general_sleep_context_quiet_gap_first_break_anchor": evaluate_sleep_context_quiet_gap_first_break_anchor,
    "trigger_general_sleep_context_quiet_gap_keep_first_break_small": evaluate_sleep_context_quiet_gap_first_break_anchor,
    "trigger_general_sleep_context_quiet_gap_one_break_enough": evaluate_sleep_context_quiet_gap_first_break_anchor,
    "trigger_general_sleep_duration_below_range": evaluate_sleep_duration_below_range,
    "trigger_general_sleep_duration_below_range_one_evening_cutoff": evaluate_sleep_duration_below_range,
    "trigger_general_sleep_duration_regular_range_within_fact40": evaluate_sleep_duration_regular_range_within_fact40,
    "trigger_general_sleep_duration_regular_no_perfection_chase": evaluate_sleep_duration_regular_range_within_fact40,
    "trigger_general_sleep_duration_regular_no_new_experiment": evaluate_sleep_duration_regular_range_within_fact40,
    "trigger_general_sleep_duration_variability_opportunity": evaluate_sleep_duration_variability_opportunity,
    "trigger_general_sleep_variability_next_three_night_anchor": evaluate_sleep_duration_variability_opportunity,
    "trigger_general_sleep_variability_no_big_catchup_night": evaluate_sleep_duration_variability_opportunity,
    "trigger_general_sleep_duration_within_range": evaluate_sleep_duration_within_range,
    "trigger_pneumonia_sleep_below_range_rest_window": evaluate_pneumonia_sleep_below_range_rest_window,
    "trigger_pneumonia_irregular_sleep_keep_one_anchor": evaluate_pneumonia_irregular_sleep_keep_one_anchor,
    "trigger_pneumonia_high_active_energy_next_day_light_start": evaluate_pneumonia_high_active_energy_next_day_light_start,
    "trigger_pneumonia_weekly_high_activity_volume_no_extra_push": evaluate_pneumonia_weekly_high_activity_volume_no_extra_push,
    "trigger_pneumonia_late_activity_sleep_winddown_buffer": evaluate_pneumonia_late_activity_sleep_winddown_buffer,
    "trigger_pneumonia_late_sleep_morning_first_move_small": evaluate_pneumonia_late_sleep_morning_first_move_small,
    "trigger_pneumonia_walking_speed_drop_easy_pace": evaluate_pneumonia_walking_speed_drop_easy_pace,
    "trigger_pneumonia_walking_speed_drop_close_short": evaluate_pneumonia_walking_speed_drop_close_short,
    "trigger_pneumonia_light_walking_shorten_before_speed_up_apple": evaluate_pneumonia_light_walking_shorten_before_speed_up_apple,
    "trigger_pneumonia_light_walking_shorten_before_speed_up_samsung": evaluate_pneumonia_light_walking_shorten_before_speed_up_samsung,
    "trigger_pneumonia_recorded_exercise_familiar_stop_point": evaluate_pneumonia_recorded_exercise_familiar_stop_point,
    "trigger_pneumonia_recorded_exercise_spacing_no_stack": evaluate_pneumonia_recorded_exercise_spacing_no_stack,
    "trigger_pneumonia_unaccustomed_activity_keep_easy_next": evaluate_pneumonia_unaccustomed_activity_keep_easy_next,
    "trigger_pneumonia_activity_distribution_no_catchup_burst": evaluate_pneumonia_activity_distribution_no_catchup_burst,
    "trigger_pneumonia_weekly_activity_distribution_no_makeup_week": evaluate_pneumonia_weekly_activity_distribution_no_makeup_week,
    "trigger_general_sleep_drift_midday_reset_anchor": evaluate_sleep_drift_midday_reset_anchor,
    "trigger_general_sleep_drift_no_full_day_reset": evaluate_sleep_drift_midday_reset_anchor,
    "trigger_general_sleep_drift_no_evening_catchup": evaluate_sleep_drift_midday_reset_anchor,
    "trigger_general_sleep_timing_regular_context": evaluate_sleep_timing_regular_context,
    "trigger_general_sleep_timing_one_anchor_not_perfect": evaluate_sleep_timing_regular_context,
    "trigger_general_sleep_timing_regular_leave_wide_window": evaluate_sleep_timing_regular_context,
    "trigger_general_sleep_timing_next_day_available_window_anchor": evaluate_sleep_timing_next_day_available_window_anchor,
    "trigger_general_sleep_deviation_next_day_no_full_reset": evaluate_sleep_timing_next_day_available_window_anchor,
    "trigger_general_sleep_deviation_next_day_one_window_enough": evaluate_sleep_timing_next_day_available_window_anchor,
    "trigger_general_unaccustomed_activity_body_feel_checkin": evaluate_unaccustomed_activity_body_feel_checkin,
    "trigger_general_unaccustomed_activity_keep_easy_next": evaluate_unaccustomed_activity_body_feel_checkin,
    "trigger_general_unaccustomed_activity_no_new_normal": evaluate_unaccustomed_activity_body_feel_checkin,
    "trigger_general_weekend_sleep_shift_first_activity_anchor": evaluate_weekend_sleep_shift_first_activity_anchor,
    "trigger_general_weekend_sleep_shift_no_hard_reset": evaluate_weekend_sleep_shift_first_activity_anchor,
    "trigger_general_weekend_sleep_shift_no_fixed_rule": evaluate_weekend_sleep_shift_first_activity_anchor,
    "trigger_general_weekly_aerobic_activity_distribution_below_3_days": evaluate_weekly_aerobic_activity_distribution_below_3_days,
    "trigger_general_weekly_aerobic_low_day_next_anchor": evaluate_weekly_aerobic_activity_distribution_below_3_days,
    "trigger_general_weekly_aerobic_low_day_no_makeup_long_session": evaluate_weekly_aerobic_activity_distribution_below_3_days,
    "trigger_htn_aerobic_exercise_frequency_below_5_sessions": evaluate_hypertension_aerobic_frequency_below_5_sessions,
    "trigger_htn_resistance_equipment_frequency_below_2_sessions": evaluate_hypertension_resistance_equipment_frequency_below_2_sessions,
    "trigger_htn_resistance_equipment_frequency_above_3_sessions": evaluate_hypertension_resistance_equipment_frequency_above_3_sessions,
    "trigger_diabetes_resistance_equipment_frequency_below_2_sessions": evaluate_diabetes_resistance_equipment_frequency_below_2_sessions,
    "trigger_dyslipidemia_aerobic_intensity_frequency_below_alternative": evaluate_dyslipidemia_aerobic_intensity_frequency_below_alternative,
    "trigger_diabetes_weekly_mvpa_volume_frequency_below_target": evaluate_diabetes_weekly_mvpa_volume_frequency_below_target,
    "trigger_general_weekly_high_activity_volume_no_extra_push": evaluate_general_weekly_high_activity_volume_no_extra_push,
    "trigger_diabetes_postmeal_low_movement_small_walk": evaluate_diabetes_postmeal_low_movement_small_walk,
    "trigger_general_postmeal_quiet_window_small_walk": evaluate_general_postmeal_quiet_window_small_walk,
    "trigger_htn_weekly_exercise_duration_below_90_minutes": evaluate_hypertension_weekly_exercise_duration_below_90_minutes,
    "trigger_htn_weekly_exercise_duration_above_150_minutes": evaluate_hypertension_weekly_exercise_duration_above_150_minutes,
    "trigger_general_energy_low_gap_small_move_reentry_apple": evaluate_energy_low_gap_apple,
    "trigger_general_energy_low_gap_small_move_reentry_samsung": evaluate_energy_low_gap_samsung,
    "trigger_general_apple_activity_energy_gap_no_catchup_burst": evaluate_energy_low_gap_apple,
    "trigger_general_apple_activity_energy_gap_next_known_anchor": evaluate_energy_low_gap_apple,
    "trigger_general_samsung_exercise_energy_drop_keep_session_tiny": evaluate_energy_low_gap_samsung,
    "trigger_general_samsung_exercise_energy_drop_no_catchup_burst": evaluate_energy_low_gap_samsung,
    "trigger_general_apple_record_gap_movement": evaluate_apple_record_gap_movement,
    "trigger_general_apple_record_gap_no_catchup_burst": evaluate_apple_record_gap_movement,
    "trigger_general_apple_record_gap_next_transition_enough": evaluate_apple_record_gap_movement,
    "trigger_general_apple_short_sleep_high_activity": evaluate_short_sleep_steps,
    "trigger_general_apple_short_sleep_high_exercise_time": evaluate_short_sleep_exercise_time,
    "trigger_general_samsung_short_sleep_high_activity": evaluate_short_sleep_steps,
    "trigger_general_samsung_short_sleep_high_exercise_duration": evaluate_short_sleep_exercise_duration,
    "trigger_general_short_sleep_high_activity_no_extra_push_apple_steps": evaluate_short_sleep_steps,
    "trigger_general_short_sleep_high_activity_no_extra_push_apple_exercise_time": evaluate_short_sleep_exercise_time,
    "trigger_general_short_sleep_high_activity_no_extra_push_samsung_steps": evaluate_short_sleep_steps,
    "trigger_general_short_sleep_high_activity_no_extra_push_samsung_exercise_duration": evaluate_short_sleep_exercise_duration,
    "trigger_general_short_sleep_high_activity_next_day_light_start_apple_steps": evaluate_short_sleep_steps,
    "trigger_general_short_sleep_high_activity_next_day_light_start_apple_exercise_time": evaluate_short_sleep_exercise_time,
    "trigger_general_short_sleep_high_activity_next_day_light_start_samsung_steps": evaluate_short_sleep_steps,
    "trigger_general_short_sleep_high_activity_next_day_light_start_samsung_exercise_duration": evaluate_short_sleep_exercise_duration,
    "trigger_general_samsung_exercise_timing_shift": evaluate_samsung_exercise_timing_shift,
    "trigger_general_samsung_exercise_timing_shift_next_window_flexible": evaluate_samsung_exercise_timing_shift,
    "trigger_general_samsung_exercise_timing_shift_keep_flexible": evaluate_samsung_exercise_timing_shift,
    "trigger_general_recorded_exercise_duration_pattern_consistency": evaluate_recorded_exercise_duration_pattern,
    "trigger_general_recorded_exercise_duration_keep_easy": evaluate_recorded_exercise_duration_pattern,
    "trigger_general_recorded_exercise_duration_familiar_stop_point": evaluate_recorded_exercise_duration_pattern,
    "trigger_general_recorded_exercise_session_spacing_consistency": evaluate_recorded_exercise_session_spacing,
    "trigger_general_recorded_exercise_spacing_no_stack": evaluate_recorded_exercise_session_spacing,
    "trigger_general_recorded_exercise_spacing_keep_open_day": evaluate_recorded_exercise_session_spacing,
    "trigger_diabetes_aerobic_session_gap_over_2_days_estimated": evaluate_diabetes_aerobic_session_gap_over_2_days,
    "trigger_general_recorded_exercise_timing_pattern_consistency": evaluate_recorded_exercise_timing_pattern,
    "trigger_general_recorded_exercise_timing_keep_flexible": evaluate_recorded_exercise_timing_pattern,
    "trigger_general_recorded_exercise_timing_nearby_window_fallback": evaluate_recorded_exercise_timing_pattern,
    "trigger_general_running_speed_personal_pacing": evaluate_running_speed_personal_pacing,
    "trigger_general_running_speed_no_pace_record_chase": evaluate_running_speed_personal_pacing,
    "trigger_general_running_power_activity_distribution": evaluate_running_power_activity_distribution,
    "trigger_general_running_speed_keep_next_run_easy": evaluate_running_speed_personal_pacing,
    "trigger_general_running_power_keep_next_run_easy": evaluate_running_power_activity_distribution,
    "trigger_general_running_power_no_record_chase": evaluate_running_power_activity_distribution,
    "trigger_general_weekly_low_activity_volume_reactivation": evaluate_weekly_low_activity_volume_reactivation,
    "trigger_general_weekly_low_activity_no_catchup_burst": evaluate_weekly_low_activity_volume_reactivation,
    "trigger_general_weekly_low_activity_next_week_known_slot": evaluate_weekly_low_activity_volume_reactivation,
    "trigger_general_activity_volume_baseline_gap_small_reentry": evaluate_activity_volume_baseline_gap_small_reentry,
    "trigger_general_activity_volume_baseline_gap_no_catchup_burst": evaluate_activity_volume_baseline_gap_small_reentry,
    "trigger_general_activity_volume_baseline_gap_next_known_anchor": evaluate_activity_volume_baseline_gap_small_reentry,
    "trigger_pneumonia_recovery_activity_volume_small_reentry": evaluate_pneumonia_activity_volume_small_reentry,
    "trigger_general_short_sleep_cognitive_load_light_planning": evaluate_short_sleep_cognitive_load_light_planning,
    "trigger_general_short_sleep_nonessential_load_postpone": evaluate_short_sleep_cognitive_load_light_planning,
    "trigger_general_short_sleep_no_new_load_today": evaluate_short_sleep_cognitive_load_light_planning,
    "trigger_general_long_wake_low_activity_micro_start": evaluate_long_wake_low_activity_context,
    "trigger_general_long_wake_low_activity_no_evening_catchup": evaluate_long_wake_low_activity_context,
    "trigger_general_long_wake_low_activity_one_break_enough": evaluate_long_wake_low_activity_context,
    "trigger_general_long_wake_low_activity_energy_checkin": evaluate_long_wake_low_activity_context,
    "trigger_general_recorded_activity_pattern_consistency_anchor": evaluate_recorded_activity_pattern_consistency_anchor,
    "trigger_general_recorded_activity_pattern_no_extra_push": evaluate_recorded_activity_pattern_consistency_anchor,
    "trigger_general_recorded_activity_pattern_fallback_anchor": evaluate_recorded_activity_pattern_consistency_anchor,
    "trigger_general_recorded_activity_recurrence_anchor": evaluate_recorded_activity_recurrence_anchor,
    "trigger_general_recorded_activity_recurrence_keep_session_small": evaluate_recorded_activity_recurrence_anchor,
    "trigger_general_recorded_activity_recurrence_no_streak_chase": evaluate_recorded_activity_recurrence_anchor,
    "trigger_general_high_load_low_movement_first_anchor": evaluate_high_load_low_movement_first_anchor,
    "trigger_general_high_load_low_movement_no_makeup_day": evaluate_high_load_low_movement_first_anchor,
    "trigger_general_high_load_low_movement_no_new_baseline": evaluate_high_load_low_movement_first_anchor,
    "trigger_general_multi_day_gap_today_reentry_anchor": evaluate_multi_day_gap_today_reentry_anchor,
    "trigger_general_multi_day_gap_reentry_keep_first_step_small": evaluate_multi_day_gap_today_reentry_anchor,
    "trigger_general_multi_day_gap_reentry_close_today_small": evaluate_multi_day_gap_today_reentry_anchor,
    "trigger_general_active_energy_activity_context": evaluate_active_energy_activity_context,
    "trigger_general_high_active_energy_no_extra_push": evaluate_high_active_energy_no_extra_push,
    "trigger_general_high_active_energy_next_day_light_start": evaluate_high_active_energy_no_extra_push,
    "trigger_general_mixed_intensity_equivalence": evaluate_mixed_intensity_equivalence,
    "trigger_general_mixed_intensity_equivalence_next_choice": evaluate_mixed_intensity_equivalence,
    "trigger_general_mixed_intensity_equivalence_no_double_bucket_chase": evaluate_mixed_intensity_equivalence,
    "trigger_general_post_exercise_hrr_context": evaluate_post_exercise_hrr_context,
    "trigger_general_post_exercise_hrr_easy_cooldown": evaluate_post_exercise_hrr_context,
    "trigger_general_post_exercise_hrr_no_number_chase": evaluate_post_exercise_hrr_context,
    "trigger_pneumonia_post_exercise_hrr_easy_cooldown": evaluate_pneumonia_post_exercise_hrr_easy_cooldown,
    "trigger_pneumonia_post_exercise_hrr_no_number_chase": evaluate_pneumonia_post_exercise_hrr_no_number_chase,
    "trigger_general_hrv_short_sleep_body_feel_context": evaluate_hrv_short_sleep_body_feel_context,
    "trigger_general_hrv_short_sleep_no_extra_push": evaluate_hrv_short_sleep_body_feel_context,
    "trigger_general_hrv_short_sleep_no_number_chase": evaluate_hrv_short_sleep_body_feel_context,
    "trigger_general_resting_hr_load_sleep_body_feel_context": evaluate_resting_hr_load_sleep_body_feel_context,
    "trigger_general_rhr_load_sleep_no_extra_push": evaluate_resting_hr_load_sleep_body_feel_context,
    "trigger_general_rhr_load_sleep_no_number_chase": evaluate_resting_hr_load_sleep_body_feel_context,
    "trigger_general_resting_respiratory_rate_context": evaluate_resting_respiratory_rate_context,
    "trigger_general_resting_respiratory_rate_no_number_chase": evaluate_resting_respiratory_rate_context,
    "trigger_general_resting_respiratory_rate_no_extra_fix_push": evaluate_resting_respiratory_rate_context,
    "trigger_general_spo2_post_exercise_breathing_context": evaluate_spo2_post_exercise_breathing_context,
    "trigger_general_spo2_post_exercise_easy_cooldown": evaluate_spo2_post_exercise_breathing_context,
    "trigger_general_spo2_post_exercise_no_number_chase": evaluate_spo2_post_exercise_breathing_context,
    "trigger_pneumonia_post_exercise_spo2_easy_cooldown": evaluate_pneumonia_post_exercise_spo2_easy_cooldown,
    "trigger_pneumonia_post_exercise_spo2_no_number_chase": evaluate_pneumonia_post_exercise_spo2_no_number_chase,
    "trigger_general_same_pace_higher_hr_body_feel_checkin": evaluate_same_pace_higher_hr_body_feel_checkin,
    "trigger_general_same_pace_higher_hr_keep_easy": evaluate_same_pace_higher_hr_body_feel_checkin,
    "trigger_general_same_pace_higher_hr_no_number_chase": evaluate_same_pace_higher_hr_body_feel_checkin,
    "trigger_general_walking_speed_drop_easy_pace": evaluate_walking_pace_drop_activity_pacing,
}

# Compatibility alias for older callers. Canonical delivery must call
# select_canonical_evaluators() with the current catalog IDs instead of
# treating every historical evaluator as active.
EVALUATORS = ALL_EVALUATORS


def select_canonical_evaluators(
    trigger_ids: set[str] | list[str] | tuple[str, ...],
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    requested = set(trigger_ids)
    missing = requested - ALL_EVALUATORS.keys()
    if missing:
        raise TriggerReferenceError(f"missing canonical evaluators: {sorted(missing)}")
    return {trigger_id: ALL_EVALUATORS[trigger_id] for trigger_id in sorted(requested)}


EVALUATOR_BINDING_RATIONALE: dict[str, str] = {
    "trigger_general_activity_load_gradual_progression": "Primary activity-load progression rule: recent seven-day positive-day mean versus prior fourteen-day positive-day median.",
    "trigger_general_activity_load_spike_no_extra_push": "Same computed activity-load spike context as gradual progression; copy action changes to no-extra-push.",
    "trigger_general_activity_load_spike_insert_easy_day": "Same computed activity-load spike context as gradual progression; copy action changes to insert-easy-day.",
    "trigger_general_recent_activity_load_spike_context": "Legacy trigger id for the same activity-load progression calculation.",
    "trigger_general_recent_activity_load_spike_no_record_push": "Same recent activity-load spike calculation; copy action changes to no-record-push.",
    "trigger_general_recent_activity_load_spike_no_new_normal": "Same recent activity-load spike calculation; copy action changes to no-new-normal.",
    "trigger_general_activity_load_return_to_baseline_checkin": "Primary activity-load return-to-baseline trajectory/body-feel context calculation.",
    "trigger_general_activity_load_return_keep_light": "Same activity-load return-to-baseline trajectory context; copy action changes to keep-light.",
    "trigger_general_activity_load_return_no_baseline_chase": "Same activity-load return-to-baseline trajectory context; copy action changes to no-baseline-chase.",
    "trigger_general_activity_load_spike_easy_buffer": "Primary high-after-quiet activity-load spike calculation: current day versus prior positive-day median after two below-median days.",
    "trigger_general_activity_load_high_after_quiet_no_stack_tomorrow": "Same high-after-quiet activity-load spike context as easy-buffer; copy action changes to no-stack-tomorrow.",
    "trigger_general_activity_load_high_after_quiet_same_day_closeout": "Same high-after-quiet activity-load spike context as easy-buffer; copy action changes to same-day-closeout.",
    "trigger_htn_high_after_quiet_activity_load_lighten_next": "Hypertension/elevated-BP DR high-after-quiet activity-load calculation: confirmed BP/HTN context plus the source-qualified high-after-quiet activity-load rule; copy action changes to next-activity-lighten.",
    "trigger_general_resting_respiratory_rate_context": "Primary resting respiratory-rate context calculation: current daily median versus prior fourteen-day personal median with quality and red-flag gates.",
    "trigger_general_resting_respiratory_rate_no_number_chase": "Same resting respiratory-rate context calculation; copy action changes to no-number-chase while preserving zero-candidate replay status.",
    "trigger_general_resting_respiratory_rate_no_extra_fix_push": "Same resting respiratory-rate context calculation; copy action changes to no-extra-fix-push while preserving zero-candidate replay status.",
    "trigger_general_activity_pattern_variability_context": "Primary multi-day activity-pattern variability calculation: personal relative-spread threshold crossing after the quiet window.",
    "trigger_general_activity_variability_no_big_makeup_day": "Same multi-day activity-pattern variability threshold crossing as the small-anchor line; copy action changes to no-big-makeup-day.",
    "trigger_general_activity_variability_no_every_day_equal_chase": "Same multi-day activity-pattern variability threshold crossing as the small-anchor line; copy action changes to no-every-day-equal-chase.",
    "trigger_general_late_activity_sleep_winddown_anchor": "Primary late-activity winddown calculation: activity end time within the window before habitual sleep onset.",
    "trigger_general_late_activity_next_time_finish_earlier": "Same late-activity sleep-winddown window calculation as the winddown anchor; copy action changes to next-time-finish-earlier.",
    "trigger_general_late_activity_no_extra_evening_activity": "Same late-activity sleep-winddown window calculation as the winddown anchor; copy action changes to no-extra-evening-activity.",
    "trigger_general_any_length_mvpa_health_connect_intensity": "Health Connect source-qualified weekly any-length MVPA accumulation uses the same weekly qualified-minute calculation.",
    "trigger_general_any_length_mvpa_accumulation": "Apple/source-qualified weekly any-length MVPA accumulation uses the same weekly qualified-minute calculation.",
    "trigger_general_mvpa_gap_no_catchup_burst_weekly_any_length": "No-catch-up-burst copy shares the weekly any-length MVPA threshold calculation.",
    "trigger_general_mvpa_gap_no_catchup_burst_weekly_health_connect": "Health Connect no-catch-up-burst copy shares the weekly any-length MVPA threshold calculation.",
    "trigger_general_mvpa_gap_next_familiar_walking_anchor_weekly_any_length": "Familiar-anchor copy shares the weekly any-length MVPA threshold calculation.",
    "trigger_general_mvpa_gap_next_familiar_walking_anchor_weekly_health_connect": "Health Connect familiar-anchor copy shares the weekly any-length MVPA threshold calculation.",
    "trigger_general_daily_mvpa_30min_gap_health_connect_intensity": "Health Connect direct daily MVPA path uses the same complete-day qualified-minute threshold calculation.",
    "trigger_general_daily_mvpa_30min_gap_direct": "Direct daily MVPA path uses the same complete-day qualified-minute threshold calculation.",
    "trigger_general_mvpa_gap_no_catchup_burst_daily_direct": "No-catch-up-burst copy shares the direct daily MVPA threshold calculation.",
    "trigger_general_mvpa_gap_no_catchup_burst_daily_health_connect": "Health Connect no-catch-up-burst copy shares the direct daily MVPA threshold calculation.",
    "trigger_general_daily_mvpa_30min_gap_estimated": "Samsung walking-speed estimated MVPA path uses the estimated in-band walking-minute calculation.",
    "trigger_general_mvpa_gap_no_catchup_burst_daily_estimated": "No-catch-up-burst copy shares the estimated daily MVPA threshold calculation.",
    "trigger_general_mvpa_gap_next_familiar_walking_anchor_daily_direct": "Familiar-anchor copy shares the direct daily MVPA threshold calculation.",
    "trigger_general_mvpa_gap_next_familiar_walking_anchor_daily_estimated": "Familiar-anchor copy shares the estimated daily MVPA threshold calculation.",
    "trigger_general_mvpa_gap_next_familiar_walking_anchor_daily_health_connect": "Health Connect familiar-anchor copy shares the direct daily MVPA threshold calculation.",
    "trigger_general_activity_distribution_next_anchor": "Primary source-qualified within-day three-hour activity-window distribution calculation.",
    "trigger_general_activity_distribution_no_catchup_burst": "Same within-day activity-window distribution context; copy action changes to no-catchup-burst.",
    "trigger_general_activity_distribution_one_window_not_every_window": "Same within-day activity-window distribution context; copy action changes to one-window-not-every-window.",
    "trigger_general_after_high_activity_low_movement_body_feel_checkin": "Primary adjacent-day prior-high-load plus next-day low-movement body-feel context calculation.",
    "trigger_general_after_high_activity_low_movement_no_refill": "Same adjacent-day prior-high-load plus next-day low-movement context; copy action changes to no-refill.",
    "trigger_general_after_high_activity_low_movement_no_new_baseline": "Same adjacent-day prior-high-load plus next-day low-movement context; existing no-new-baseline action line is reused.",
    "trigger_general_high_load_low_movement_first_anchor": "Primary prior-day load >=150 percent baseline plus current-day low positive movement context calculation.",
    "trigger_general_high_load_low_movement_no_makeup_day": "Same high-load/low-movement context; copy action changes to no-makeup-day.",
    "trigger_general_high_load_low_movement_no_new_baseline": "Same high-load/low-movement context; copy action changes to no-new-baseline.",
    "trigger_general_multi_day_activity_pattern_context": "Primary source-qualified seven observed-day daily step activity-pattern calculation.",
    "trigger_general_daily_step_pattern_keep_margin": "Same seven observed-day daily step activity-pattern context; copy action changes to keep-margin.",
    "trigger_general_daily_step_pattern_flexible_window": "Same seven observed-day daily step activity-pattern context; copy action changes to flexible-window.",
    "trigger_general_daily_step_pattern_consistency": "Primary source-qualified seven complete-day daily step-pattern consistency calculation.",
    "trigger_general_daily_step_pattern_no_target_chase": "Same seven complete-day daily step-pattern consistency context; copy action changes to no-target-chase and reuses the line-specific step-pattern replay bridge.",
    "trigger_general_daily_step_pattern_keep_margin_consistency_context": "Same seven complete-day daily step-pattern consistency context; existing keep-margin action line is reused.",
    "trigger_general_hrv_short_sleep_body_feel_context": "Primary short-sleep plus low-HRV context calculation.",
    "trigger_general_hrv_short_sleep_no_extra_push": "Same short-sleep plus low-HRV context; copy action changes to no-extra-push.",
    "trigger_general_hrv_short_sleep_no_number_chase": "Same short-sleep plus low-HRV context; copy action changes to no-number-chase.",
    "trigger_general_inactivity_gap_move_prompt": "Primary source-qualified inactivity-gap move-prompt calculation.",
    "trigger_general_inactivity_gap_easy_restart": "Same inactivity-gap move-prompt context; copy action changes to easy-restart.",
    "trigger_general_inactivity_gap_transition_anchor": "Same inactivity-gap move-prompt context; copy action changes to transition-anchor.",
    "trigger_general_irregular_sleep_week_daytime_anchor": "Primary source-qualified irregular sleep-week plus daytime anchor-opportunity calculation.",
    "trigger_general_irregular_sleep_week_keep_anchor_small": "Same irregular sleep-week daytime-anchor context; copy action changes to keep-anchor-small.",
    "trigger_general_irregular_sleep_week_no_fixed_rule": "Same irregular sleep-week daytime-anchor context; existing activity/sleep no-fixed-rule action line is reused.",
    "trigger_general_late_sleep_morning_first_activity_anchor": "Primary source-qualified late sleep/wake plus delayed first-activity calculation.",
    "trigger_general_late_sleep_morning_keep_first_move_small": "Same late-sleep morning first-activity context; copy action changes to keep-first-move-small.",
    "trigger_general_late_sleep_morning_no_evening_catchup": "Same late-sleep morning first-activity context; copy action changes to no-evening-catchup.",
    "trigger_general_daily_sedentary_like_inactivity_above_8h_fact41": "Primary source-qualified fact41 sedentary-like inactivity above-8h calculation.",
    "trigger_general_sedentary_like_inactivity_no_catchup_burst": "Same fact41 sedentary-like inactivity context; copy action changes to no-catchup-burst.",
    "trigger_general_sedentary_like_inactivity_first_break_early_anchor": "Same fact41 sedentary-like inactivity context; copy action changes to early-first-break anchor.",
    "trigger_general_break_like_movement_reactivation": "Primary source-qualified quiet-gap then first-light-movement calculation.",
    "trigger_general_break_like_movement_keep_small": "Same break-like movement context; copy action changes to keep-small.",
    "trigger_general_break_like_movement_next_gap_pre_anchor": "Same break-like movement context; copy action changes to next-gap pre-anchor.",
    "trigger_general_quiet_gap_light_step_followthrough_anchor": "Primary source-qualified quiet-gap plus first-light-event plus 60-240 minute follow-through calculation.",
    "trigger_general_quiet_gap_followthrough_keep_small": "Same quiet-gap follow-through context; copy action changes to keep-small.",
    "trigger_general_quiet_gap_followthrough_close_loop": "Same quiet-gap follow-through context; copy action changes to close-loop.",
    "trigger_general_brief_brisk_bout_next_anchor": "Primary source-qualified short ambulatory bout calculation.",
    "trigger_general_brief_brisk_bout_keep_small": "Same short ambulatory bout context; copy action changes to keep-small.",
    "trigger_general_brief_brisk_bout_daily_route_anchor": "Same short ambulatory bout context; copy action changes to daily-route anchor.",
    "trigger_general_sleep_duration_below_range": "Primary source-qualified daily sleep-duration below-range calculation.",
    "trigger_general_sleep_duration_below_range_one_evening_cutoff": "Same below-range sleep-duration observation context; copy action changes to one-evening-cutoff.",
    "trigger_general_sleep_duration_regular_range_within_fact40": "Primary rolling seven observed-night mean 7-9 hour plus midpoint-regularity calculation.",
    "trigger_general_sleep_duration_regular_no_perfection_chase": "Same regular sleep-duration context; copy action changes to no-perfection-chase.",
    "trigger_general_sleep_duration_regular_no_new_experiment": "Same regular sleep-duration context; copy action changes to no-new-experiment.",
    "trigger_general_sleep_drift_midday_reset_anchor": "Primary sleep midpoint drift plus delayed first-activity plus midday anchor-window calculation.",
    "trigger_general_sleep_drift_no_full_day_reset": "Same sleep-drift midday-reset context; copy action changes to no-full-day-reset.",
    "trigger_general_sleep_drift_no_evening_catchup": "Same sleep-drift midday-reset context; copy action changes to no-evening-catchup.",
    "trigger_general_weekend_sleep_shift_first_activity_anchor": "Primary source-qualified weekday/weekend sleep-midpoint shift plus first-activity calculation.",
    "trigger_general_weekend_sleep_shift_no_hard_reset": "Same weekend sleep-shift first-activity context; copy action changes to no-hard-reset.",
    "trigger_general_weekend_sleep_shift_no_fixed_rule": "Same weekend sleep-shift first-activity context; existing activity/sleep no-fixed-rule action line is reused.",
    "trigger_general_current_step_light_activity_context": "Primary source-qualified current/local-day low-step calculation.",
    "trigger_general_low_step_no_catchup_burst": "Same current/local-day low-step context; copy action changes to no-catchup-burst.",
    "trigger_general_low_step_next_transition_anchor": "Same current/local-day low-step context; copy action changes to next-transition-anchor.",
    "trigger_general_light_walking_activity_context": "Primary Samsung estimated light-walking interval context.",
    "trigger_general_light_walking_keep_easy_pace_samsung": "Same Samsung estimated light-walking interval context; copy action changes to keep-easy-pace.",
    "trigger_general_light_walking_shorten_before_speed_up_samsung": "Same Samsung estimated light-walking interval context; copy action changes to shorten-before-speed-up.",
    "trigger_general_light_walking_apple_speed_context": "Primary Apple WalkingSpeed light-walking interval context.",
    "trigger_general_light_walking_keep_easy_pace_apple": "Same Apple WalkingSpeed light-walking interval context; copy action changes to keep-easy-pace.",
    "trigger_general_light_walking_shorten_before_speed_up_apple": "Same Apple WalkingSpeed light-walking interval context; copy action changes to shorten-before-speed-up.",
    "trigger_general_long_wake_low_activity_micro_start": "Primary long-wake low-activity context calculation.",
    "trigger_general_long_wake_low_activity_no_evening_catchup": "Same long-wake low-activity context calculation; copy action changes to no-evening-catchup.",
    "trigger_general_long_wake_low_activity_one_break_enough": "Same long-wake low-activity context calculation; existing one-break-enough action line is reused.",
    "trigger_general_long_wake_low_activity_energy_checkin": "Same long-wake low-activity context calculation with a different copy surface.",
    "trigger_general_high_active_energy_no_extra_push": "Primary provider-specific high active-energy no-extra-push calculation.",
    "trigger_general_high_active_energy_next_day_light_start": "Same high active-energy context; copy action changes to next-day-light-start.",
    "trigger_general_mixed_intensity_equivalence": "Primary moderate-equivalent activity-minute calculation.",
    "trigger_general_mixed_intensity_equivalence_next_choice": "Same moderate-equivalent calculation; copy action changes to next-choice framing.",
    "trigger_general_mixed_intensity_equivalence_no_double_bucket_chase": "Same moderate-equivalent calculation; copy action changes to no-double-bucket-chase.",
    "trigger_general_post_exercise_hrr_context": "Primary post-exercise HRR/recovery-window context presence calculation.",
    "trigger_general_post_exercise_hrr_easy_cooldown": "Same post-exercise recovery-window context; copy action changes to easy cooldown.",
    "trigger_general_post_exercise_hrr_no_number_chase": "Same post-exercise recovery-window context; copy action changes to no-number-chase.",
    "trigger_pneumonia_post_exercise_hrr_easy_cooldown": "Pneumonia DR wrapper around the post-exercise HRR/recovery-window context: confirmed pneumonia context plus active pneumonia coaching window and source-qualified post-exercise HRR window support leaving an easy cooldown before the next activity without inferring HRR meaning, recovery, fatigue, severity, oxygenation, or activity clearance.",
    "trigger_pneumonia_post_exercise_hrr_no_number_chase": "Pneumonia DR wrapper around the post-exercise HRR/recovery-window context: confirmed pneumonia context plus active pneumonia coaching window and source-qualified post-exercise HRR window support not chasing the number and closing with a familiar finish routine without inferring HRR meaning, recovery, fatigue, severity, oxygenation, or activity clearance.",
    "trigger_general_resting_hr_load_sleep_body_feel_context": "Primary short-sleep plus high-RHR plus prior-day load context calculation.",
    "trigger_general_rhr_load_sleep_no_extra_push": "Same short-sleep/RHR/load context; copy action changes to no-extra-push.",
    "trigger_general_rhr_load_sleep_no_number_chase": "Same short-sleep/RHR/load context; copy action changes to no-number-chase.",
    "trigger_general_resting_respiratory_rate_no_number_chase": "Same resting respiratory-rate context; copy action changes to no-number-chase while preserving zero-candidate replay status.",
    "trigger_general_resting_respiratory_rate_no_extra_fix_push": "Same resting respiratory-rate context; copy action changes to no-extra-fix-push while preserving zero-candidate replay status.",
    "trigger_general_running_power_activity_distribution": "Primary comparable running-power baseline calculation.",
    "trigger_general_running_power_keep_next_run_easy": "Same running-power baseline context; copy action changes to keep-next-run-easy.",
    "trigger_general_running_power_no_record_chase": "Same running-power baseline context; copy action changes to no-record-chase.",
    "trigger_general_running_speed_personal_pacing": "Primary comparable running-speed baseline calculation.",
    "trigger_general_running_speed_no_pace_record_chase": "Same running-speed baseline context; copy action changes to no-pace-record-chase.",
    "trigger_general_running_speed_keep_next_run_easy": "Same running-speed baseline context; copy action changes to keep-next-run-easy.",
    "trigger_general_activity_volume_baseline_gap_small_reentry": "Primary activity-volume baseline-gap family calculation over preserved source-specific provider paths.",
    "trigger_general_activity_volume_baseline_gap_no_catchup_burst": "Same activity-volume baseline-gap family context; copy action changes to no-catchup-burst.",
    "trigger_general_activity_volume_baseline_gap_next_known_anchor": "Same activity-volume baseline-gap family context; copy action changes to next-known-anchor.",
    "trigger_pneumonia_recovery_activity_volume_small_reentry": "Pneumonia DR wrapper around the activity-volume baseline-gap family: operating-supplied confirmed pneumonia context plus an active pneumonia coaching window and source-specific baseline-drop or recorded-gap context supports a small activity re-entry action without inferring pneumonia, recovery status, safety clearance, or clinical deterioration from device data.",
    "trigger_pneumonia_sleep_below_range_rest_window": "Pneumonia DR wrapper around the sleep-duration-below-range calculation: operating-supplied confirmed pneumonia context plus an active pneumonia coaching window and source-qualified sleep-duration observation support a rest-window planning action without inferring immune status, recovery status, or activity clearance from device data.",
    "trigger_pneumonia_irregular_sleep_keep_one_anchor": "Pneumonia DR wrapper around the irregular-sleep-week daytime-anchor calculation: operating-supplied confirmed pneumonia context plus an active pneumonia coaching window and source-qualified irregular sleep timing with an available daytime anchor supports keeping one easy anchor without prescribing sleep, diagnosing recovery, or inferring pneumonia severity.",
    "trigger_pneumonia_high_active_energy_next_day_light_start": "Pneumonia DR wrapper around the provider-specific high active-energy calculation: confirmed pneumonia context plus active pneumonia coaching window and a high active-energy day support a next-day light-start action without treating active energy as recovery, fatigue, severity, or activity-clearance evidence.",
    "trigger_pneumonia_weekly_high_activity_volume_no_extra_push": "Pneumonia DR wrapper around the source-qualified weekly high activity-volume calculation: confirmed pneumonia context plus active pneumonia coaching window and Apple Workout/PhysicalEffort upper-volume context support no-extra-push copy without inferring overtraining, recovery, severity, or exercise safety.",
    "trigger_pneumonia_late_activity_sleep_winddown_buffer": "Pneumonia DR wrapper around the late-activity sleep-winddown calculation: confirmed pneumonia context plus active pneumonia coaching window and a source-qualified late activity end near habitual sleep onset support leaving an evening winddown buffer without inferring sleep disorder, recovery, fatigue, severity, or activity clearance.",
    "trigger_pneumonia_late_sleep_morning_first_move_small": "Pneumonia DR wrapper around the late-sleep morning first-activity calculation: confirmed pneumonia context plus active pneumonia coaching window and source-qualified late sleep/wake plus delayed first activity support keeping the first morning movement small without inferring recovery, fatigue, severity, or activity clearance.",
    "trigger_pneumonia_walking_speed_drop_easy_pace": "Pneumonia DR wrapper around the Apple WalkingSpeed personal drop calculation: confirmed pneumonia context plus active pneumonia coaching window and a source-qualified walking-speed drop support an easy-pace copy without inferring pneumonia worsening, hypoxemia, gait disorder, fatigue, recovery, severity, or activity clearance.",
    "trigger_pneumonia_walking_speed_drop_close_short": "Pneumonia DR wrapper around the Apple WalkingSpeed personal drop calculation: confirmed pneumonia context plus active pneumonia coaching window and a source-qualified walking-speed drop support closing the walk short without inferring pneumonia worsening, hypoxemia, gait disorder, fatigue, recovery, severity, or activity clearance.",
    "trigger_pneumonia_light_walking_shorten_before_speed_up_apple": "Pneumonia DR wrapper around the Apple light-walking speed-band calculation: confirmed pneumonia context plus active pneumonia coaching window and source-qualified estimated light walking support shortening the walk instead of speeding up without inferring pneumonia status, fatigue, recovery, or activity clearance.",
    "trigger_pneumonia_light_walking_shorten_before_speed_up_samsung": "Pneumonia DR wrapper around the Samsung walking-event light-walking calculation: confirmed pneumonia context plus active pneumonia coaching window and source-qualified estimated light walking support shortening the walk instead of speeding up without inferring pneumonia status, fatigue, recovery, or activity clearance.",
    "trigger_pneumonia_recorded_exercise_familiar_stop_point": "Pneumonia DR wrapper around the provider-recorded exercise-duration familiar stop-point calculation: confirmed pneumonia context plus active pneumonia coaching window and a source-qualified familiar exercise-duration pattern support ending near the familiar duration without inferring target compliance, fatigue, recovery, or activity clearance.",
    "trigger_pneumonia_recorded_exercise_spacing_no_stack": "Pneumonia DR wrapper around the provider-recorded exercise-session spacing calculation: confirmed pneumonia context plus active pneumonia coaching window and source-qualified exercise sessions already spaced within a three-day gap support not stacking extra sessions without inferring target compliance, fatigue, recovery, or activity clearance.",
    "trigger_pneumonia_unaccustomed_activity_keep_easy_next": "Pneumonia DR wrapper around the unaccustomed activity-pattern calculation: confirmed pneumonia context plus active pneumonia coaching window and source-qualified unusual activity pattern support keeping the next movement easy without measuring symptoms, fatigue, recovery, injury, or activity clearance.",
    "trigger_pneumonia_activity_distribution_no_catchup_burst": "Pneumonia DR wrapper around the within-day activity-distribution calculation: confirmed pneumonia context plus active pneumonia coaching window and activity concentrated in one or two local three-hour windows support avoiding a catch-up burst without inferring sedentary time, fatigue, recovery, or activity clearance.",
    "trigger_pneumonia_weekly_activity_distribution_no_makeup_week": "Pneumonia DR wrapper around the weekly activity-distribution calculation: confirmed pneumonia context plus active pneumonia coaching window and weekly activity concentrated in one or two days support avoiding a large make-up week without inferring activity sufficiency, fatigue, recovery, or activity clearance.",
    "trigger_general_recorded_exercise_duration_pattern_consistency": "Primary provider-recorded exercise-duration pattern calculation over Apple/Samsung seven-day relative-spread windows.",
    "trigger_general_recorded_exercise_duration_keep_easy": "Same provider-recorded exercise-duration pattern context; copy action changes to keep-easy duration.",
    "trigger_general_recorded_exercise_duration_familiar_stop_point": "Same provider-recorded exercise-duration pattern context; copy action changes to familiar-stop-point.",
    "trigger_general_recorded_exercise_session_spacing_consistency": "Primary provider-recorded exercise-session day spacing calculation.",
    "trigger_general_recorded_exercise_spacing_no_stack": "Same recorded exercise-session spacing context; copy action changes to no-stack.",
    "trigger_general_recorded_exercise_spacing_keep_open_day": "Same recorded exercise-session spacing context; copy action changes to keep-open-day.",
    "trigger_diabetes_aerobic_session_gap_over_2_days_estimated": "Diabetes-scoped aerobic-session gap calculation: confirmed diabetes context plus Apple/Samsung source-qualified/reset activity days; no signal after observation start is estimated no recorded exercise and emits once on day 3.",
    "trigger_htn_resistance_equipment_frequency_below_2_sessions": "Hypertension/elevated-BP DR equipment-resistance frequency calculation: confirmed BP/HTN context plus Apple source-qualified traditional strength-training sessions in an observed local week below two sessions.",
    "trigger_htn_resistance_equipment_frequency_above_3_sessions": "Hypertension/elevated-BP DR equipment-resistance frequency calculation: confirmed BP/HTN context plus Apple source-qualified traditional strength-training sessions in an observed local week above three sessions.",
    "trigger_diabetes_resistance_equipment_frequency_below_2_sessions": "Diabetes DR equipment-resistance frequency calculation: confirmed diabetes context plus Apple source-qualified traditional strength-training sessions in an observed local week below two sessions; this does not infer diabetes control or exercise clearance.",
    "trigger_general_recorded_exercise_timing_pattern_consistency": "Primary provider-recorded exercise start-time pattern calculation over Apple/Samsung seven-day circular local-clock spread windows.",
    "trigger_general_recorded_exercise_timing_keep_flexible": "Same provider-recorded exercise start-time pattern context; copy action changes to keep-flexible timing.",
    "trigger_general_recorded_exercise_timing_nearby_window_fallback": "Same provider-recorded exercise start-time pattern context; copy action changes to nearby-window fallback.",
    "trigger_general_samsung_exercise_timing_shift": "Primary Samsung provider-recorded exercise timing-shift calculation: current session start time versus prior fourteen-day circular timing baseline.",
    "trigger_general_samsung_exercise_timing_shift_next_window_flexible": "Same Samsung exercise timing-shift context; copy action changes to next-window-flexible.",
    "trigger_general_samsung_exercise_timing_shift_keep_flexible": "Same Samsung exercise timing-shift context; existing recorded-exercise timing keep-flexible action line is reused.",
    "trigger_general_recorded_activity_pattern_consistency_anchor": "Primary source-qualified recorded activity-pattern consistency calculation.",
    "trigger_general_recorded_activity_pattern_no_extra_push": "Same recorded activity-pattern consistency context; copy action changes to no-extra-push.",
    "trigger_general_recorded_activity_pattern_fallback_anchor": "Same recorded activity-pattern consistency context; copy action changes to fallback-anchor.",
    "trigger_general_short_sleep_cognitive_load_light_planning": "Primary short-sleep cognitive-load light-planning calculation.",
    "trigger_general_short_sleep_nonessential_load_postpone": "Same short-sleep planning context; copy action changes to postpone nonessential load.",
    "trigger_general_short_sleep_no_new_load_today": "Same short-sleep planning context; copy action changes to no-new-load-today.",
    "trigger_general_samsung_short_sleep_high_exercise_duration": "Primary Samsung short-sleep plus high exercise-duration context.",
    "trigger_general_short_sleep_high_activity_no_extra_push_samsung_exercise_duration": "Same Samsung short-sleep plus high exercise-duration context; copy action changes to no-extra-push.",
    "trigger_general_apple_short_sleep_high_exercise_time": "Primary Apple short-sleep plus high exercise-time context.",
    "trigger_general_short_sleep_high_activity_no_extra_push_apple_exercise_time": "Same Apple short-sleep plus high exercise-time context; copy action changes to no-extra-push.",
    "trigger_general_apple_short_sleep_high_activity": "Primary Apple short-sleep plus high step/activity context.",
    "trigger_general_samsung_short_sleep_high_activity": "Primary Samsung short-sleep plus high step/activity context using the same paired-day calculation.",
    "trigger_general_short_sleep_high_activity_no_extra_push_apple_steps": "Same Apple short-sleep plus high step/activity context; copy action changes to no-extra-push.",
    "trigger_general_short_sleep_high_activity_no_extra_push_samsung_steps": "Same Samsung short-sleep plus high step/activity context; copy action changes to no-extra-push.",
    "trigger_general_short_sleep_high_activity_next_day_light_start_apple_steps": "Same Apple short-sleep plus high step/activity context; copy action changes to next-day-light-start.",
    "trigger_general_short_sleep_high_activity_next_day_light_start_apple_exercise_time": "Same Apple short-sleep plus high exercise-time context; copy action changes to next-day-light-start.",
    "trigger_general_short_sleep_high_activity_next_day_light_start_samsung_steps": "Same Samsung short-sleep plus high step/activity context; copy action changes to next-day-light-start.",
    "trigger_general_short_sleep_high_activity_next_day_light_start_samsung_exercise_duration": "Same Samsung short-sleep plus high exercise-duration context; copy action changes to next-day-light-start.",
    "trigger_general_sleep_duration_variability_opportunity": "Primary personal sleep-duration variability crossing calculation.",
    "trigger_general_sleep_variability_next_three_night_anchor": "Same sleep-variability crossing context; copy action changes to three-night anchor.",
    "trigger_general_sleep_variability_no_big_catchup_night": "Same sleep-variability crossing context; copy action changes to no-big-catch-up-night.",
    "trigger_general_sleep_context_quiet_gap_first_break_anchor": "Primary recent sleep-context plus daytime quiet-gap first-break calculation.",
    "trigger_general_sleep_context_quiet_gap_keep_first_break_small": "Same recent sleep-context plus daytime quiet-gap context; copy action changes to keep-first-break-small.",
    "trigger_general_sleep_context_quiet_gap_one_break_enough": "Same recent sleep-context plus daytime quiet-gap context; copy action changes to one-break-enough.",
    "trigger_general_sleep_timing_regular_context": "Primary source-qualified seven observed-night sleep-timing regularity context calculation.",
    "trigger_general_sleep_timing_one_anchor_not_perfect": "Same sleep-timing regularity context; copy action changes to one-anchor-not-perfect.",
    "trigger_general_sleep_timing_regular_leave_wide_window": "Same sleep-timing regularity context; copy action changes to leave-wide-window.",
    "trigger_general_unaccustomed_activity_body_feel_checkin": "Primary unaccustomed activity-pattern body-feel context calculation.",
    "trigger_general_unaccustomed_activity_keep_easy_next": "Same unaccustomed activity-pattern context; copy action changes to keep-easy-next movement.",
    "trigger_general_unaccustomed_activity_no_new_normal": "Same unaccustomed activity-pattern context; copy action changes to no-new-normal baseline handling.",
    "trigger_general_spo2_post_exercise_breathing_context": "Primary Samsung post-exercise SpO2 breathing-context presence calculation.",
    "trigger_general_spo2_post_exercise_easy_cooldown": "Same post-exercise SpO2 context; copy action changes to easy cooldown.",
    "trigger_general_spo2_post_exercise_no_number_chase": "Same post-exercise SpO2 context; copy action changes to no-number-chase.",
    "trigger_pneumonia_post_exercise_spo2_easy_cooldown": "Pneumonia DR wrapper around the Samsung post-exercise SpO2 context: confirmed pneumonia context plus active pneumonia coaching window and source-qualified post-exercise SpO2 support context support leaving an easy cooldown before the next activity without inferring oxygenation status, hypoxemia, respiratory disease, recovery, fatigue, severity, or activity clearance.",
    "trigger_pneumonia_post_exercise_spo2_no_number_chase": "Pneumonia DR wrapper around the Samsung post-exercise SpO2 context: confirmed pneumonia context plus active pneumonia coaching window and source-qualified post-exercise SpO2 support context support not repeatedly checking the number and closing with one breathing-feel check without inferring oxygenation status, hypoxemia, respiratory disease, recovery, fatigue, severity, or activity clearance.",
    "trigger_general_same_pace_higher_hr_body_feel_checkin": "Primary paired speed/heart-rate comparable-baseline context calculation.",
    "trigger_general_same_pace_higher_hr_keep_easy": "Same paired speed/heart-rate comparable-baseline context; copy action changes to keep-easy pacing.",
    "trigger_general_same_pace_higher_hr_no_number_chase": "Same paired speed/heart-rate comparable-baseline context; copy action changes to no-number-chase.",
    "trigger_general_walking_pace_drop_activity_pacing": "Primary walking-speed drop activity-pacing calculation.",
    "trigger_general_walking_speed_drop_close_short": "Same walking-speed drop context; copy action changes to close-short/no distance chase.",
    "trigger_general_walking_speed_drop_easy_pace": "Same walking-speed drop context; copy action changes to easy pace.",
    "trigger_general_weekly_aerobic_activity_distribution_below_3_days": "Primary weekly source-qualified aerobic-day count calculation.",
    "trigger_general_weekly_aerobic_low_day_next_anchor": "Same weekly aerobic-day count calculation; copy action changes to next anchor.",
    "trigger_general_weekly_aerobic_low_day_no_makeup_long_session": "Same weekly aerobic-day count calculation; copy action changes to no long make-up session.",
    "trigger_general_weekly_low_activity_volume_reactivation": "Primary weekly low activity-volume reactivation calculation.",
    "trigger_general_weekly_low_activity_no_catchup_burst": "Same weekly low activity-volume context; copy action changes to no catch-up burst.",
    "trigger_general_weekly_low_activity_next_week_known_slot": "Same weekly low activity-volume context; copy action changes to next-week-known-slot.",
    "trigger_general_weekly_activity_distribution_next_week_anchor": "Primary source-qualified weekly activity distribution next-week anchor calculation.",
    "trigger_general_weekly_activity_distribution_no_makeup_week": "Same weekly activity distribution next-week anchor context; copy action changes to no-makeup-week.",
    "trigger_general_weekly_activity_distribution_one_anchor_not_every_day": "Same weekly activity distribution next-week anchor context; copy action changes to one-anchor-not-every-day.",
    "trigger_general_sleep_timing_next_day_available_window_anchor": "Primary sleep-deviation plus next-day activity-window calculation.",
    "trigger_general_sleep_deviation_next_day_no_full_reset": "Same sleep-deviation plus next-day activity-window context; copy action changes to no-full-reset.",
    "trigger_general_sleep_deviation_next_day_one_window_enough": "Same sleep-deviation plus next-day activity-window context; copy action changes to one-window-enough.",
    "trigger_general_recorded_activity_recurrence_anchor": "Primary provider-recorded activity recurrence calculation after a prior quiet window.",
    "trigger_general_recorded_activity_recurrence_keep_session_small": "Same recorded activity recurrence context; copy action changes to keep-session-small.",
    "trigger_general_recorded_activity_recurrence_no_streak_chase": "Same recorded activity recurrence context; copy action changes to no-streak-chase.",
    "trigger_general_multi_day_gap_today_reentry_anchor": "Primary multi-day activity gap plus current low-positive reentry calculation.",
    "trigger_general_multi_day_gap_reentry_keep_first_step_small": "Same multi-day gap today reentry context; copy action changes to keep-first-step-small.",
    "trigger_general_multi_day_gap_reentry_close_today_small": "Same multi-day gap today reentry context; copy action changes to close-today-small.",
    "trigger_general_short_sleep_low_activity_midday_floor_anchor": "Primary short-sleep plus low early-day activity plus midday-floor calculation.",
    "trigger_general_short_sleep_low_activity_no_afternoon_catchup": "Same short-sleep low-activity midday-floor context; copy action changes to no-afternoon-catchup.",
    "trigger_general_short_sleep_low_activity_no_step_chase": "Same short-sleep low-activity midday-floor context; copy action changes to no-step/activity-number-chase.",
    "trigger_general_activity_sleep_timing_reflection": "Primary paired activity/sleep timing reflection calculation over at least three comparable local days.",
    "trigger_general_activity_sleep_timing_no_fixed_rule": "Same paired activity/sleep timing context; copy action changes to no-fixed-rule.",
    "trigger_general_activity_sleep_timing_one_anchor_not_perfect": "Same paired activity/sleep timing context; copy action changes to one-anchor-not-perfect.",
    "trigger_general_daily_step_reference_no_extra_push": "Primary source-qualified daily step reference-status calculation.",
    "trigger_general_daily_step_reference_keep_tomorrow_margin": "Same daily step reference-status context; copy action changes to keep-tomorrow-margin.",
    "trigger_general_daily_step_reference_close_step_chase": "Same daily step reference-status context; copy action changes to close-step-chase.",
    "trigger_general_low_step_streak_no_catchup_anchor": "Primary source-qualified low-step streak no-catchup anchor calculation.",
    "trigger_general_low_step_streak_plan_next_first_anchor": "Same low-step streak no-catchup context; copy action changes to plan-next-first-anchor.",
    "trigger_general_low_step_streak_close_today_without_step_chase": "Same low-step streak no-catchup context; copy action changes to close-today-without-step-chase.",
    "trigger_general_energy_low_gap_small_move_reentry_apple": "Primary Apple provider-estimated active-energy low-gap calculation.",
    "trigger_general_energy_low_gap_small_move_reentry_samsung": "Primary Samsung recorded exercise-calorie baseline-drop calculation.",
    "trigger_general_apple_activity_energy_gap_no_catchup_burst": "Same Apple provider-estimated active-energy low-gap context; existing activity-volume no-catchup-burst action line is reused with zero-candidate replay status preserved.",
    "trigger_general_apple_activity_energy_gap_next_known_anchor": "Same Apple provider-estimated active-energy low-gap context; existing activity-volume next-known-anchor action line is reused with zero-candidate replay status preserved.",
    "trigger_general_samsung_exercise_energy_drop_keep_session_tiny": "Same Samsung exercise-calorie baseline-drop context; copy action changes to keep-session-tiny.",
    "trigger_general_samsung_exercise_energy_drop_no_catchup_burst": "Same Samsung exercise-calorie baseline-drop context; existing activity-volume no-catchup-burst action line is reused.",
    "trigger_general_apple_record_gap_movement": "Primary Apple StepCount record-gap movement-opportunity calculation.",
    "trigger_general_apple_record_gap_no_catchup_burst": "Same Apple StepCount record-gap context; copy action changes to no-catchup-burst while preserving zero-candidate external replay status.",
    "trigger_general_apple_record_gap_next_transition_enough": "Same Apple StepCount record-gap context; copy action changes to next-transition-enough while preserving zero-candidate external replay status.",
    "trigger_htn_aerobic_exercise_frequency_below_5_sessions": "Primary hypertension/elevated-BP DR frequency context calculation: source-qualified provider aerobic exercise days in an observed local week below five distinct days.",
    "trigger_dyslipidemia_aerobic_intensity_frequency_below_alternative": "Primary dyslipidemia DR intensity-frequency context calculation: Apple Workout plus same-source PhysicalEffort MET qualifies moderate and vigorous aerobic session days, then triggers only when neither the moderate five-day nor vigorous three-day alternative is met.",
    "trigger_diabetes_weekly_mvpa_volume_frequency_below_target": "Primary diabetes DR weekly MVPA volume/frequency context calculation: Apple Workout plus same-source PhysicalEffort MET qualifies weekly MVPA minutes and distinct MVPA days, then triggers when minutes are below 150 or days are below three under an externally supplied diabetes boundary.",
    "trigger_general_weekly_high_activity_volume_no_extra_push": "General/mixed-scope weekly high activity-volume calculation: Apple Workout plus same-source PhysicalEffort MET qualifies weekly moderate and vigorous aerobic minutes, then triggers when moderate minutes are above 300 or vigorous minutes are above 150 without treating the threshold as risk, overtraining, clearance, or a stop prescription.",
    "trigger_diabetes_postmeal_low_movement_small_walk": "Primary diabetes DR postmeal movement context calculation: operation-supplied meal anchor plus source-qualified provider step intervals; triggers when the 45-minute postmeal window contains fewer than 10 positive-step movement minutes under externally supplied diabetes and safety boundary context.",
    "trigger_general_postmeal_quiet_window_small_walk": "Primary general wellness postmeal movement context calculation: operation/user recalled meal anchor plus source-qualified provider step intervals; triggers only after the 45-minute follow-up window has elapsed and movement is below 10 positive-step minutes, then supports next-meal or general postmeal habit copy rather than real-time delivery.",
    "trigger_htn_weekly_exercise_duration_below_90_minutes": "Primary hypertension/elevated-BP DR duration context calculation: source-qualified provider exercise minutes in an observed local week below the 90-minute lower bound.",
    "trigger_htn_weekly_exercise_duration_above_150_minutes": "Primary hypertension/elevated-BP DR duration context calculation: source-qualified provider exercise minutes in an observed local week above the 150-minute upper bound.",
    "trigger_htn_home_sodium_choice_open": "Primary hypertension DR self-report context calculation: one explicit adult home food-choice opportunity within a one-local-day boundary, without inferring sodium intake, diet quality, or BP outcome.",
    "trigger_htn_stress_practice_open": "Primary hypertension DR self-report context calculation: one explicit adult stress-management practice opportunity within a one-local-day boundary, without inferring stress state, mental-health status, or BP outcome.",
    "trigger_diabetes_tobacco_support_open": "Primary diabetes DR self-report context calculation: one explicit adult tobacco/vaping cessation-support opportunity within a one-local-day boundary, without inferring use, dependence, withdrawal, treatment, referral, or glycemic outcome.",
    "trigger_cad_tobacco_support_open": "Primary CAD DR self-report context calculation: one explicit adult tobacco/vaping cessation-support opportunity within a one-local-day boundary, without inferring use, dependence, withdrawal, treatment, referral, or cardiovascular outcome.",
    "trigger_cad_cardiac_rehab_support_open": "Primary cardiovascular DR self-report context calculation: one explicit adult cardiac-rehabilitation support opportunity within a one-local-day boundary, without inferring cardiac status, exercise clearance, medication change, or clinical outcome.",
    "trigger_pneumonia_followup_question_open": "Primary pneumonia DR self-report context calculation: one explicit adult follow-up-question preparation opportunity within a one-local-day boundary, without inferring diagnosis, severity, worsening symptoms, treatment response, or clinical action.",
    "trigger_diabetes_sleep_routine_open": "Primary diabetes DR self-report context calculation: one explicit adult sleep-promoting routine opportunity within a one-local-day boundary, without inferring sleep duration, sleep disorder, glucose response, or clinical outcome.",
    "trigger_cardiovascular_sleep_anchor_open": "Primary cardiovascular DR self-report context calculation: one explicit adult sleep-wake anchor choice within a one-local-day boundary, without inferring sleep duration, sleep disorder, circadian phase, cardiovascular status, or clinical outcome.",
    "trigger_cardio_meal_timing_anchor_open": "Primary cardiovascular DR self-report context calculation: one explicit adult meal-timing routine opportunity within a one-local-day boundary, without inferring meal timing, meal schedule adherence, cardiovascular status, glycemic outcome, or clinical outcome.",
    "trigger_diabetes_sedentary_break_open": "Primary diabetes DR self-report context calculation: one explicit adult sedentary-break opportunity within a one-local-day boundary, without measuring sitting time, inferring glycemic status, or creating a clinical exercise prescription.",
    "trigger_hypertension_sleep_hygiene_open": "Primary hypertension DR self-report context calculation: one explicit adult sleep-promoting routine opportunity within a one-local-day boundary, without measuring sleep quality/duration, BP, or inferring treatment/outcomes.",
    "trigger_dyslipidemia_exercise_snack_open": "Primary dyslipidemia DR self-report context calculation: one explicit adult exercise-snack opportunity within one local day, without measuring steps, sitting time, intensity, lipid outcomes, treatment, or provider use.",
    "trigger_dyslipidemia_sleep_routine_open": "Primary dyslipidemia DR self-report context calculation: one explicit adult sleep-promoting routine opportunity within one local day, without measuring sleep, inferring lipid values, or creating treatment/provider authority.",
    "trigger_dyslipidemia_resistance_session_open": "Primary dyslipidemia DR self-report context calculation: one explicit adult resistance-session opportunity within one local day, without inferring device resistance, intensity, safety, lipid outcomes, treatment, or provider use.",
    "trigger_pneumonia_fluid_routine_open": "Primary pneumonia DR self-report context calculation: one explicit adult ordinary-fluid daily-life choice within a one-local-day boundary, without inferring fluid volume, hydration status, fluid restriction, treatment, provider use, or clinical outcome.",
    "trigger_pneumonia_household_support_open": "Primary pneumonia DR self-report context calculation: one explicit adult household-support opportunity within a one-local-day boundary, without inferring need, recovery status, activity clearance, treatment, provider use, or clinical outcome.",
    "trigger_diabetes_meal_preparation_open": "Primary diabetes DR self-report context calculation: one explicit adult meal-preparation opportunity within a one-local-day boundary, without inferring nutrition prescription, glucose response, medication, or clinical outcome.",
    "trigger_dyslipidemia_heart_healthy_food_choice_open": "Primary dyslipidemia DR self-report context calculation: one explicit adult heart-healthy food-choice opportunity within a one-local-day boundary, without inferring diet prescription, lipid value/target, medication, or clinical outcome.",
    "trigger_hypertension_home_bp_checkin_open": "Primary hypertension DR self-report context calculation: one explicit adult home-BP check-in preparation opportunity within a one-local-day boundary, without measuring BP, interpreting numbers, diagnosing, or changing treatment.",
    "trigger_hypertension_followup_question_open": "Primary hypertension DR self-report context calculation: one explicit adult follow-up-question preparation opportunity within a one-local-day boundary, without measuring BP, interpreting numbers, diagnosing, or changing treatment.",
}


def evaluate_fixture(trigger_id: str, input_fixture: dict[str, Any]) -> dict[str, Any]:
    evaluator = ALL_EVALUATORS.get(trigger_id)
    if evaluator is None:
        raise TriggerReferenceError(f"unsupported trigger_id: {trigger_id}")
    actual = evaluator(input_fixture)
    actual.setdefault("trigger_id", trigger_id)
    if trigger_id == "trigger_general_walking_speed_drop_close_short":
        actual.setdefault("copy_action", "walking_speed_drop_close_short")
    if trigger_id == "trigger_general_weekly_aerobic_low_day_no_makeup_long_session":
        actual.setdefault("copy_action", "weekly_aerobic_low_day_no_makeup_long_session")
    if trigger_id.startswith("trigger_general_mvpa_gap_no_catchup_burst_"):
        actual.setdefault("copy_action", "mvpa_gap_no_catchup_burst")
    if trigger_id.startswith("trigger_general_mvpa_gap_next_familiar_walking_anchor_"):
        actual.setdefault("copy_action", "mvpa_gap_next_familiar_walking_anchor")
    if trigger_id == "trigger_general_recorded_exercise_spacing_no_stack":
        actual.setdefault("copy_action", "recorded_exercise_spacing_no_stack")
    if trigger_id == "trigger_general_recorded_exercise_spacing_keep_open_day":
        actual.setdefault("copy_action", "recorded_exercise_spacing_keep_open_day")
    if trigger_id == "trigger_diabetes_aerobic_session_gap_over_2_days_estimated":
        actual.setdefault("copy_action", "diabetes_aerobic_session_small_restart")
    if trigger_id == "trigger_htn_aerobic_exercise_frequency_below_5_sessions":
        actual.setdefault("copy_action", "hypertension_aerobic_frequency_small_weekly_anchor")
    if trigger_id == "trigger_htn_resistance_equipment_frequency_below_2_sessions":
        actual.setdefault("copy_action", "hypertension_resistance_equipment_frequency_low_small_anchor")
    if trigger_id == "trigger_htn_resistance_equipment_frequency_above_3_sessions":
        actual.setdefault("copy_action", "hypertension_resistance_equipment_frequency_high_recovery_anchor")
    if trigger_id == "trigger_diabetes_resistance_equipment_frequency_below_2_sessions":
        actual.setdefault("copy_action", "diabetes_resistance_equipment_frequency_low_small_anchor")
    if trigger_id == "trigger_dyslipidemia_aerobic_intensity_frequency_below_alternative":
        actual.setdefault("copy_action", "dyslipidemia_aerobic_intensity_frequency_small_anchor")
    if trigger_id == "trigger_diabetes_weekly_mvpa_volume_frequency_below_target":
        actual.setdefault("copy_action", "diabetes_weekly_mvpa_volume_frequency_small_anchor")
    if trigger_id == "trigger_general_weekly_high_activity_volume_no_extra_push":
        actual.setdefault("copy_action", "general_weekly_high_activity_volume_no_extra_push")
    if trigger_id == "trigger_diabetes_postmeal_low_movement_small_walk":
        actual.setdefault("copy_action", "diabetes_postmeal_low_movement_small_walk")
    if trigger_id == "trigger_general_postmeal_quiet_window_small_walk":
        actual.setdefault("copy_action", "general_postmeal_quiet_window_small_walk")
    if trigger_id == "trigger_htn_weekly_exercise_duration_below_90_minutes":
        actual.setdefault("copy_action", "hypertension_exercise_duration_low_small_anchor")
    if trigger_id == "trigger_htn_weekly_exercise_duration_above_150_minutes":
        actual.setdefault("copy_action", "hypertension_exercise_duration_high_lighten_next")
    if trigger_id == "trigger_htn_high_after_quiet_activity_load_lighten_next":
        actual.setdefault("copy_action", "hypertension_high_after_quiet_activity_load_lighten_next")
    if trigger_id == "trigger_htn_home_sodium_choice_open":
        actual.setdefault("copy_action", "hypertension_home_sodium_one_small_swap")
    if trigger_id == "trigger_htn_stress_practice_open":
        actual.setdefault("copy_action", "hypertension_stress_management_one_practice")
    if trigger_id == "trigger_diabetes_tobacco_support_open":
        actual.setdefault("copy_action", "diabetes_tobacco_cessation_one_support_step")
    if trigger_id == "trigger_cad_tobacco_support_open":
        actual.setdefault("copy_action", "cad_tobacco_cessation_one_support_step")
    if trigger_id == "trigger_cad_cardiac_rehab_support_open":
        actual.setdefault("copy_action", "cad_cardiac_rehab_support_one_step")
    if trigger_id == "trigger_pneumonia_followup_question_open":
        actual.setdefault("copy_action", "pneumonia_followup_question_one_step")
    if trigger_id == "trigger_diabetes_sleep_routine_open":
        actual.setdefault("copy_action", "diabetes_sleep_routine_one_step")
    if trigger_id == "trigger_cardiovascular_sleep_anchor_open":
        actual.setdefault("copy_action", "cardiovascular_sleep_anchor_one_step")
    if trigger_id == "trigger_cardio_meal_timing_anchor_open":
        actual.setdefault("copy_action", "cardio_meal_timing_anchor_one_step")
    if trigger_id == "trigger_diabetes_sedentary_break_open":
        actual.setdefault("copy_action", "diabetes_sedentary_break_one_step")
    if trigger_id == "trigger_hypertension_sleep_hygiene_open":
        actual.setdefault("copy_action", "hypertension_sleep_hygiene_routine_one_step")
    if trigger_id == "trigger_hypertension_sedentary_break_open":
        actual.setdefault("copy_action", "hypertension_sedentary_break_one_step")
    if trigger_id == "trigger_hypertension_meal_preparation_open":
        actual.setdefault("copy_action", "hypertension_meal_preparation_one_step")
    if trigger_id == "trigger_pneumonia_small_meal_routine_open":
        actual.setdefault("copy_action", "pneumonia_small_meal_routine_one_step")
    if trigger_id == "trigger_cardiovascular_meal_planning_open":
        actual.setdefault("copy_action", "cardiovascular_meal_planning_one_step")
    if trigger_id == "trigger_diabetes_regular_meal_routine_open":
        actual.setdefault("copy_action", "diabetes_regular_meal_routine_one_step")
    if trigger_id == "trigger_dyslipidemia_fibre_food_addition_open":
        actual.setdefault("copy_action", "dyslipidemia_fibre_food_addition_one_step")
    if trigger_id == "trigger_dyslipidemia_exercise_snack_open":
        actual.setdefault("copy_action", "dyslipidemia_exercise_snack_one_step")
    if trigger_id == "trigger_dyslipidemia_sleep_routine_open":
        actual.setdefault("copy_action", "dyslipidemia_sleep_routine_one_step")
    if trigger_id == "trigger_dyslipidemia_resistance_session_open":
        actual.setdefault("copy_action", "dyslipidemia_resistance_session_one_step")
    if trigger_id == "trigger_diabetes_meal_preparation_open":
        actual.setdefault("copy_action", "diabetes_meal_preparation_one_step")
    if trigger_id == "trigger_dyslipidemia_heart_healthy_food_choice_open":
        actual.setdefault("copy_action", "dyslipidemia_heart_healthy_food_choice_one_step")
    if trigger_id == "trigger_hypertension_home_bp_checkin_open":
        actual.setdefault("copy_action", "hypertension_home_bp_prepare_one_step")
    if trigger_id == "trigger_hypertension_followup_question_open":
        actual.setdefault("copy_action", "hypertension_followup_question_one_step")
    if trigger_id == "trigger_general_recorded_activity_pattern_no_extra_push":
        actual.setdefault("copy_action", "recorded_activity_pattern_no_extra_push")
    if trigger_id == "trigger_general_recorded_activity_pattern_fallback_anchor":
        actual.setdefault("copy_action", "recorded_activity_pattern_fallback_anchor")
    if trigger_id == "trigger_general_running_speed_no_pace_record_chase":
        actual.setdefault("copy_action", "running_speed_no_pace_record_chase")
    if trigger_id == "trigger_general_inactivity_gap_easy_restart":
        actual.setdefault("copy_action", "inactivity_gap_easy_restart")
    if trigger_id == "trigger_general_inactivity_gap_transition_anchor":
        actual.setdefault("copy_action", "inactivity_gap_transition_anchor")
    if trigger_id == "trigger_general_sedentary_like_inactivity_no_catchup_burst":
        actual.setdefault("copy_action", "sedentary_like_inactivity_no_catchup_burst")
    if trigger_id == "trigger_general_sedentary_like_inactivity_first_break_early_anchor":
        actual.setdefault("copy_action", "sedentary_like_inactivity_first_break_early_anchor")
    if trigger_id == "trigger_general_brief_brisk_bout_keep_small":
        actual.setdefault("copy_action", "brief_brisk_bout_keep_small")
    if trigger_id == "trigger_general_brief_brisk_bout_daily_route_anchor":
        actual.setdefault("copy_action", "brief_brisk_bout_daily_route_anchor")
    if trigger_id == "trigger_general_low_step_no_catchup_burst":
        actual.setdefault("copy_action", "low_step_no_catchup_burst")
    if trigger_id == "trigger_general_low_step_next_transition_anchor":
        actual.setdefault("copy_action", "low_step_next_transition_anchor")
    if trigger_id.startswith("trigger_general_short_sleep_high_activity_next_day_light_start_"):
        actual.setdefault("copy_action", "short_sleep_high_activity_next_day_light_start")
    if trigger_id == "trigger_general_activity_volume_baseline_gap_no_catchup_burst":
        actual.setdefault("copy_action", "activity_volume_baseline_gap_no_catchup_burst")
    if trigger_id == "trigger_general_apple_activity_energy_gap_no_catchup_burst":
        actual.setdefault("copy_action", "activity_volume_baseline_gap_no_catchup_burst")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_no_candidate_observed")
    if trigger_id == "trigger_general_apple_activity_energy_gap_next_known_anchor":
        actual.setdefault("copy_action", "activity_volume_baseline_gap_next_known_anchor")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_no_candidate_observed")
    if trigger_id == "trigger_general_apple_record_gap_no_catchup_burst":
        actual.setdefault("copy_action", "apple_record_gap_no_catchup_burst")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_no_candidate_observed")
    if trigger_id == "trigger_general_apple_record_gap_next_transition_enough":
        actual.setdefault("copy_action", "apple_record_gap_next_transition_enough")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_no_candidate_observed")
    if trigger_id == "trigger_general_activity_volume_baseline_gap_next_known_anchor":
        actual.setdefault("copy_action", "activity_volume_baseline_gap_next_known_anchor")
    if trigger_id == "trigger_pneumonia_recovery_activity_volume_small_reentry":
        actual.setdefault("copy_action", "pneumonia_recovery_activity_volume_small_reentry")
    if trigger_id == "trigger_general_break_like_movement_keep_small":
        actual.setdefault("copy_action", "break_like_movement_keep_small")
    if trigger_id == "trigger_general_break_like_movement_next_gap_pre_anchor":
        actual.setdefault("copy_action", "break_like_movement_next_gap_pre_anchor")
    if trigger_id == "trigger_general_quiet_gap_followthrough_keep_small":
        actual.setdefault("copy_action", "quiet_gap_followthrough_keep_small")
    if trigger_id == "trigger_general_quiet_gap_followthrough_close_loop":
        actual.setdefault("copy_action", "quiet_gap_followthrough_close_loop")
    if trigger_id == "trigger_general_daily_step_pattern_keep_margin":
        actual.setdefault("copy_action", "daily_step_pattern_keep_margin")
    if trigger_id == "trigger_general_daily_step_pattern_flexible_window":
        actual.setdefault("copy_action", "daily_step_pattern_flexible_window")
    if trigger_id == "trigger_general_daily_step_pattern_no_target_chase":
        actual.setdefault("copy_action", "daily_step_pattern_no_target_chase")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_candidate_verified")
    if trigger_id == "trigger_general_daily_step_pattern_keep_margin_consistency_context":
        actual.setdefault("copy_action", "daily_step_pattern_keep_margin")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_candidate_verified")
    if trigger_id == "trigger_general_recorded_exercise_duration_keep_easy":
        actual.setdefault("copy_action", "recorded_exercise_duration_keep_easy")
    if trigger_id == "trigger_general_recorded_exercise_duration_familiar_stop_point":
        actual.setdefault("copy_action", "recorded_exercise_duration_familiar_stop_point")
    if trigger_id == "trigger_general_recorded_exercise_timing_keep_flexible":
        actual.setdefault("copy_action", "recorded_exercise_timing_keep_flexible")
    if trigger_id == "trigger_general_recorded_exercise_timing_nearby_window_fallback":
        actual.setdefault("copy_action", "recorded_exercise_timing_nearby_window_fallback")
    if trigger_id == "trigger_general_samsung_exercise_timing_shift_next_window_flexible":
        actual.setdefault("copy_action", "samsung_exercise_timing_shift_next_window_flexible")
    if trigger_id == "trigger_general_samsung_exercise_timing_shift_keep_flexible":
        actual.setdefault("copy_action", "recorded_exercise_timing_keep_flexible")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_candidate_verified")
    if trigger_id == "trigger_general_sleep_timing_one_anchor_not_perfect":
        actual.setdefault("copy_action", "sleep_timing_one_anchor_not_perfect")
    if trigger_id == "trigger_general_sleep_timing_regular_leave_wide_window":
        actual.setdefault("copy_action", "sleep_timing_regular_leave_wide_window")
    if trigger_id == "trigger_general_activity_distribution_no_catchup_burst":
        actual.setdefault("copy_action", "activity_distribution_no_catchup_burst")
    if trigger_id == "trigger_general_activity_distribution_one_window_not_every_window":
        actual.setdefault("copy_action", "activity_distribution_one_window_not_every_window")
    if trigger_id == "trigger_general_same_pace_higher_hr_keep_easy":
        actual.setdefault("copy_action", "same_pace_higher_hr_keep_easy")
    if trigger_id == "trigger_general_same_pace_higher_hr_no_number_chase":
        actual.setdefault("copy_action", "same_pace_higher_hr_no_number_chase")
    if trigger_id == "trigger_general_hrv_short_sleep_no_number_chase":
        actual.setdefault("copy_action", "hrv_short_sleep_no_number_chase")
    if trigger_id == "trigger_general_rhr_load_sleep_no_number_chase":
        actual.setdefault("copy_action", "rhr_load_sleep_no_number_chase")
    if trigger_id == "trigger_general_resting_respiratory_rate_no_number_chase":
        actual.setdefault("copy_action", "resting_respiratory_rate_no_number_chase")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_no_candidate_observed")
    if trigger_id == "trigger_general_resting_respiratory_rate_no_extra_fix_push":
        actual.setdefault("copy_action", "resting_respiratory_rate_no_extra_fix_push")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_no_candidate_observed")
    if trigger_id == "trigger_general_running_power_no_record_chase":
        actual.setdefault("copy_action", "running_power_no_record_chase")
    if trigger_id == "trigger_general_unaccustomed_activity_keep_easy_next":
        actual.setdefault("copy_action", "unaccustomed_activity_keep_easy_next")
    if trigger_id == "trigger_general_unaccustomed_activity_no_new_normal":
        actual.setdefault("copy_action", "unaccustomed_activity_no_new_normal")
    if trigger_id == "trigger_general_activity_load_return_keep_light":
        actual.setdefault("copy_action", "activity_load_return_keep_light")
    if trigger_id == "trigger_general_activity_load_return_no_baseline_chase":
        actual.setdefault("copy_action", "activity_load_return_no_baseline_chase")
    if trigger_id == "trigger_general_after_high_activity_low_movement_no_refill":
        actual.setdefault("copy_action", "after_high_activity_low_movement_no_refill")
    if trigger_id == "trigger_general_after_high_activity_low_movement_no_new_baseline":
        actual.setdefault("copy_action", "high_load_low_movement_no_new_baseline")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_candidate_verified")
    if trigger_id == "trigger_general_sleep_context_quiet_gap_keep_first_break_small":
        actual.setdefault("copy_action", "sleep_context_quiet_gap_keep_first_break_small")
    if trigger_id == "trigger_general_sleep_context_quiet_gap_one_break_enough":
        actual.setdefault("copy_action", "sleep_context_quiet_gap_one_break_enough")
    if trigger_id == "trigger_general_high_load_low_movement_no_makeup_day":
        actual.setdefault("copy_action", "high_load_low_movement_no_makeup_day")
    if trigger_id == "trigger_general_high_load_low_movement_no_new_baseline":
        actual.setdefault("copy_action", "high_load_low_movement_no_new_baseline")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_candidate_verified")
    if trigger_id == "trigger_general_spo2_post_exercise_no_number_chase":
        actual.setdefault("copy_action", "spo2_post_exercise_no_number_chase")
    if trigger_id == "trigger_general_sleep_duration_below_range_one_evening_cutoff":
        actual.setdefault("copy_action", "sleep_duration_below_range_one_evening_cutoff")
    if trigger_id == "trigger_general_sleep_duration_regular_no_perfection_chase":
        actual.setdefault("copy_action", "sleep_duration_regular_no_perfection_chase")
    if trigger_id == "trigger_general_sleep_duration_regular_no_new_experiment":
        actual.setdefault("copy_action", "sleep_duration_regular_no_new_experiment")
    if trigger_id == "trigger_general_sleep_variability_no_big_catchup_night":
        actual.setdefault("copy_action", "sleep_variability_no_big_catchup_night")
    if trigger_id == "trigger_general_sleep_drift_no_full_day_reset":
        actual.setdefault("copy_action", "sleep_drift_no_full_day_reset")
    if trigger_id == "trigger_general_sleep_drift_no_evening_catchup":
        actual.setdefault("copy_action", "sleep_drift_no_evening_catchup")
    if trigger_id == "trigger_general_irregular_sleep_week_keep_anchor_small":
        actual.setdefault("copy_action", "irregular_sleep_week_keep_anchor_small")
    if trigger_id == "trigger_general_irregular_sleep_week_no_fixed_rule":
        actual.setdefault("copy_action", "activity_sleep_timing_no_fixed_rule")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_candidate_verified")
    if trigger_id == "trigger_general_late_sleep_morning_keep_first_move_small":
        actual.setdefault("copy_action", "late_sleep_morning_keep_first_move_small")
    if trigger_id == "trigger_general_late_sleep_morning_no_evening_catchup":
        actual.setdefault("copy_action", "late_sleep_morning_no_evening_catchup")
    if trigger_id == "trigger_general_mixed_intensity_equivalence_no_double_bucket_chase":
        actual.setdefault("copy_action", "mixed_intensity_no_double_bucket_chase")
    if trigger_id == "trigger_general_weekly_activity_distribution_no_makeup_week":
        actual.setdefault("copy_action", "weekly_activity_distribution_no_makeup_week")
    if trigger_id == "trigger_general_weekly_activity_distribution_one_anchor_not_every_day":
        actual.setdefault("copy_action", "weekly_activity_distribution_one_anchor_not_every_day")
    if trigger_id == "trigger_general_weekly_low_activity_next_week_known_slot":
        actual.setdefault("copy_action", "weekly_low_activity_next_week_known_slot")
    if trigger_id == "trigger_general_weekend_sleep_shift_no_hard_reset":
        actual.setdefault("copy_action", "weekend_sleep_shift_no_hard_reset")
    if trigger_id == "trigger_general_weekend_sleep_shift_no_fixed_rule":
        actual.setdefault("copy_action", "activity_sleep_timing_no_fixed_rule")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_candidate_verified")
    if trigger_id == "trigger_general_long_wake_low_activity_no_evening_catchup":
        actual.setdefault("copy_action", "long_wake_low_activity_no_evening_catchup")
    if trigger_id == "trigger_general_long_wake_low_activity_one_break_enough":
        actual.setdefault("copy_action", "sleep_context_quiet_gap_one_break_enough")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_candidate_verified")
    if trigger_id == "trigger_general_activity_load_high_after_quiet_no_stack_tomorrow":
        actual.setdefault("copy_action", "activity_load_high_after_quiet_no_stack_tomorrow")
    if trigger_id == "trigger_general_activity_load_high_after_quiet_same_day_closeout":
        actual.setdefault("copy_action", "activity_load_high_after_quiet_same_day_closeout")
    if trigger_id == "trigger_pneumonia_recovery_high_after_quiet_lower_intensity":
        actual.setdefault("copy_action", "pneumonia_recovery_lower_intensity")
    if trigger_id == "trigger_general_activity_load_spike_insert_easy_day":
        actual.setdefault("copy_action", "activity_load_spike_insert_easy_day")
    if trigger_id == "trigger_general_late_activity_next_time_finish_earlier":
        actual.setdefault("copy_action", "late_activity_next_time_finish_earlier")
    if trigger_id == "trigger_general_late_activity_no_extra_evening_activity":
        actual.setdefault("copy_action", "late_activity_no_extra_evening_activity")
    if trigger_id == "trigger_general_activity_variability_no_big_makeup_day":
        actual.setdefault("copy_action", "activity_variability_no_big_makeup_day")
    if trigger_id == "trigger_general_activity_variability_no_every_day_equal_chase":
        actual.setdefault("copy_action", "activity_variability_no_every_day_equal_chase")
    if trigger_id == "trigger_general_recent_activity_load_spike_no_record_push":
        actual.setdefault("copy_action", "recent_activity_load_spike_no_record_push")
    if trigger_id == "trigger_general_recent_activity_load_spike_no_new_normal":
        actual.setdefault("copy_action", "recent_activity_load_spike_no_new_normal")
    if trigger_id == "trigger_general_sleep_deviation_next_day_no_full_reset":
        actual.setdefault("copy_action", "sleep_deviation_next_day_no_full_reset")
    if trigger_id == "trigger_general_sleep_deviation_next_day_one_window_enough":
        actual.setdefault("copy_action", "sleep_deviation_next_day_one_window_enough")
    if trigger_id == "trigger_general_recorded_activity_recurrence_keep_session_small":
        actual.setdefault("copy_action", "recorded_activity_recurrence_keep_session_small")
    if trigger_id == "trigger_general_recorded_activity_recurrence_no_streak_chase":
        actual.setdefault("copy_action", "recorded_activity_recurrence_no_streak_chase")
    if trigger_id == "trigger_general_multi_day_gap_reentry_keep_first_step_small":
        actual.setdefault("copy_action", "multi_day_gap_reentry_keep_first_step_small")
    if trigger_id == "trigger_general_multi_day_gap_reentry_close_today_small":
        actual.setdefault("copy_action", "multi_day_gap_reentry_close_today_small")
    if trigger_id == "trigger_general_short_sleep_low_activity_no_afternoon_catchup":
        actual.setdefault("copy_action", "short_sleep_low_activity_no_afternoon_catchup")
    if trigger_id == "trigger_general_short_sleep_low_activity_no_step_chase":
        actual.setdefault("copy_action", "short_sleep_low_activity_no_step_chase")
    if trigger_id == "trigger_general_short_sleep_no_new_load_today":
        actual.setdefault("copy_action", "short_sleep_no_new_load_today")
    if trigger_id == "trigger_general_activity_sleep_timing_no_fixed_rule":
        actual.setdefault("copy_action", "activity_sleep_timing_no_fixed_rule")
    if trigger_id == "trigger_general_activity_sleep_timing_one_anchor_not_perfect":
        actual.setdefault("copy_action", "activity_sleep_timing_one_anchor_not_perfect")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_candidate_verified")
    if trigger_id == "trigger_general_daily_step_reference_keep_tomorrow_margin":
        actual.setdefault("copy_action", "daily_steps_reference_keep_tomorrow_margin")
    if trigger_id == "trigger_general_daily_step_reference_close_step_chase":
        actual.setdefault("copy_action", "daily_steps_reference_close_step_chase")
    if trigger_id == "trigger_general_low_step_streak_plan_next_first_anchor":
        actual.setdefault("copy_action", "low_step_streak_plan_next_first_anchor")
    if trigger_id == "trigger_general_low_step_streak_close_today_without_step_chase":
        actual.setdefault("copy_action", "low_step_streak_close_today_without_step_chase")
    if trigger_id == "trigger_general_high_active_energy_next_day_light_start":
        actual.setdefault("copy_action", "high_active_energy_next_day_light_start")
    if trigger_id == "trigger_general_post_exercise_hrr_no_number_chase":
        actual.setdefault("copy_action", "post_exercise_no_hrr_number_chase")
    if trigger_id == "trigger_general_samsung_exercise_energy_drop_keep_session_tiny":
        actual.setdefault("copy_action", "samsung_exercise_energy_drop_keep_session_tiny")
    if trigger_id == "trigger_general_samsung_exercise_energy_drop_no_catchup_burst":
        actual.setdefault("copy_action", "activity_volume_baseline_gap_no_catchup_burst")
        actual.setdefault("actual_replay_candidate_status", "sample_replay_candidate_verified")
    if trigger_id in (
        "trigger_general_light_walking_shorten_before_speed_up_samsung",
        "trigger_general_light_walking_shorten_before_speed_up_apple",
    ):
        actual.setdefault("copy_action", "light_walking_shorten_before_speed_up")
    return actual


def assert_expected_subset(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            raise AssertionError(f"{key}: expected {expected_value!r}, got {actual.get(key)!r}; actual={actual!r}")


def run_fixture_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for row in rows:
        trigger_id = str(row["trigger_id"])
        actual = evaluate_fixture(trigger_id, row["input_fixture"])
        expected = row.get("expected_derived_output", {})
        if not isinstance(expected, dict):
            raise TriggerReferenceError("expected_derived_output must be an object")
        assert_expected_subset(actual, expected)
        results.append({"trigger_id": trigger_id, "fixture_id": row.get("fixture_id"), "actual": actual})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run selected KDB external trigger fixture rows.")
    parser.add_argument("fixture_json", type=Path, help="JSON array of fixture rows with trigger_id/input_fixture/expected_derived_output")
    args = parser.parse_args()
    rows = json.loads(args.fixture_json.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("fixture_json must contain a JSON array")
    print(json.dumps(run_fixture_rows(rows), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
