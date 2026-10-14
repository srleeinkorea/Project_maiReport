#!/usr/bin/env python3
"""Standalone sample evaluator for the current construct-first bundle.

The evaluator accepts the bundle's *normalized* trigger inputs and returns a
deterministic derived context.  It is intentionally sample code: it does not
read production data, decide delivery cadence, infer disease state from a
device signal, or replace a provider adapter.  The sibling
``trigger_reference.py`` contains the previously implemented calculation
families; this module binds those calculations to the current 89 trigger IDs
and implements the current construct-first paths that do not have a legacy
calculation.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

try:
    from trigger_reference import ALL_EVALUATORS, TriggerReferenceError
except ImportError:
    # Resolve the sibling file explicitly so ``python -I`` also works from a
    # freshly extracted bundle with no repository or PYTHONPATH.
    _bundle_dir = Path(__file__).resolve().parent
    if str(_bundle_dir) not in sys.path:
        sys.path.insert(0, str(_bundle_dir))
    _spec = importlib.util.spec_from_file_location(
        "construct_first_bundle_trigger_reference",
        _bundle_dir / "trigger_reference.py",
    )
    if _spec is None or _spec.loader is None:
        raise ImportError("bundled trigger_reference.py cannot be loaded")
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    ALL_EVALUATORS = _module.ALL_EVALUATORS
    TriggerReferenceError = _module.TriggerReferenceError


def _source_present(value: Any) -> bool:
    return value is True or (isinstance(value, str) and bool(value.strip()))


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise TriggerReferenceError(f"{field} must be boolean")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TriggerReferenceError(f"{field} must be numeric")
    return float(value)


def _context(trigger_id: str, present: bool, reason: str | None = None, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"trigger_id": trigger_id}
    result.update(extra)
    result["context_present"] = present
    if reason is not None:
        result["null_reason"] = reason
    return result


def _source_gate(row: dict[str, Any]) -> str | None:
    if "source_identity_present" in row and not _bool(row["source_identity_present"], "source_identity_present"):
        return "source_identity_missing"
    if "source_identity_and_revision" in row and not _source_present(row["source_identity_and_revision"]):
        return "source_identity_missing"
    return None


def _optional_context_gates(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key in row and row[key] is False:
            return f"{key}_not_confirmed"
    return None


def _legacy(name: str, row: dict[str, Any], trigger_id: str) -> dict[str, Any]:
    try:
        evaluator = ALL_EVALUATORS[name]
    except KeyError as exc:
        raise TriggerReferenceError(f"missing legacy evaluator binding: {name}") from exc
    result = evaluator(row)
    if not isinstance(result, dict):
        raise TriggerReferenceError(f"legacy evaluator did not return an object: {name}")
    result = dict(result)
    result.setdefault("trigger_id", trigger_id)
    if "context_present" not in result and "triggered" in result:
        result["context_present"] = result["triggered"]
    if "context_present" not in result:
        raise TriggerReferenceError(f"legacy evaluator returned no boolean state: {name}")
    return result


def _legacy_with_gates(name: str, row: dict[str, Any], trigger_id: str, *gates: str) -> dict[str, Any]:
    reason = _source_gate(row)
    if reason is None:
        reason = _optional_context_gates(row, *gates)
    if reason is not None:
        return _context(trigger_id, False, reason)
    return _legacy(name, row, trigger_id)


def _sleep_onset(row: dict[str, Any], trigger_id: str, opportunity_key: str) -> dict[str, Any]:
    reason = _source_gate(row)
    if reason is None:
        for key in ("coverage_and_missingness", "local_timezone_resolved", "shift_or_clinical_filter_passed"):
            if key in row and row[key] is False:
                reason = f"{key}_not_qualified"
                break
    if reason is not None:
        return _context(trigger_id, False, reason)
    delay = _number(row.get("sleep_onset_delay_minutes"), "sleep_onset_delay_minutes")
    if delay <= 30:
        return _context(trigger_id, False, "sleep_onset_delay_not_over_30_minutes")
    return _context(
        trigger_id,
        True,
        insomnia="not_inferred",
        inability_to_sleep="not_inferred",
        **{opportunity_key: True},
    )


def _nap_common(row: dict[str, Any], trigger_id: str) -> str | None:
    reason = _source_gate(row)
    if reason is not None:
        return reason
    for key in ("coverage_and_missingness", "primary_sleep_episode_resolved", "local_daytime_window"):
        if key in row and row[key] is False:
            return f"{key}_not_qualified"
    return None


def _parse_day(value: Any) -> date:
    if not isinstance(value, str) or len(value) < 10:
        raise TriggerReferenceError("event date must be an ISO timestamp or YYYY-MM-DD")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise TriggerReferenceError(f"invalid event date: {value!r}") from exc


def _event_dates(row: dict[str, Any]) -> set[date]:
    dates: set[date] = set()
    for event in row.get("qualified_events", []) or []:
        if not isinstance(event, dict):
            raise TriggerReferenceError("qualified_events must contain objects")
        value = event.get("start_time", event.get("startDate"))
        if value is not None:
            dates.add(_parse_day(value))
    for event in row.get("intervals", []) or []:
        if not isinstance(event, dict):
            raise TriggerReferenceError("intervals must contain objects")
        value = event.get("start", event.get("start_time"))
        if value is not None:
            dates.add(_parse_day(value))
    return dates


def _weekly_spacing(row: dict[str, Any], trigger_id: str) -> dict[str, Any]:
    reason = _source_gate(row)
    if reason is not None:
        return _context(trigger_id, False, reason)
    if row.get("complete_week") is not True:
        return _context(trigger_id, False, "complete_week_required")
    week_start = _parse_day(row.get("week_start"))
    active = _event_dates(row)
    if not active:
        return _context(trigger_id, False, "no_qualified_activity_events")
    maximum = 0
    current = 0
    for offset in range(7):
        if week_start + timedelta(days=offset) in active:
            current = 0
        else:
            current += 1
            maximum = max(maximum, current)
    if maximum <= 2:
        return _context(trigger_id, False, "maximum_consecutive_no_activity_days_at_or_below_2", threshold_inactive_days=2, maximum_consecutive_no_activity_days=maximum)
    return _context(trigger_id, True, threshold_inactive_days=2, maximum_consecutive_no_activity_days=maximum)


def _weekly_low_aerobic_day(row: dict[str, Any], trigger_id: str, opportunity_key: str) -> dict[str, Any]:
    reason = _source_gate(row)
    if reason is None and row.get("complete_local_week") is not True:
        reason = "complete_local_week_required"
    if reason is not None:
        return _context(trigger_id, False, reason)
    count = _number(row.get("qualified_aerobic_activity_days_per_week"), "qualified_aerobic_activity_days_per_week")
    if count >= 3:
        return _context(trigger_id, False, "qualified_days_at_or_above_3")
    return _context(trigger_id, True, **{opportunity_key: True}, qualified_aerobic_activity_days_per_week=int(count))


def _reference_new(trigger_id: str, row: dict[str, Any]) -> dict[str, Any]:
    """Evaluate trigger paths absent from the historical family registry."""
    source_reason = _source_gate(row)

    if trigger_id == "trigger_cardiovascular_activity_load_easy_buffer_construct_first_v1":
        reason = source_reason or _optional_context_gates(row, "adult_18_plus_context", "confirmed_cardiovascular_context", "no_contraindication_external_gate")
        if reason is not None:
            return _context(trigger_id, False, "external_safety_gate_unknown" if "contraindication" in reason else reason)
        present = all(row.get(key) is True for key in ("minimum_7_prior_positive_days", "previous_two_local_days_below_prior_median", "current_day_above_150_percent_of_prior_median"))
        return _context(trigger_id, present, None if present else "activity_load_opportunity_not_qualified", safety_clearance="not_inferred", cardiovascular_state="not_inferred")

    if trigger_id == "trigger_cardiovascular_weekly_activity_spacing_construct_first_v1":
        reason = source_reason or _optional_context_gates(row, "adult_18_plus_context", "observed_week_source_present", "confirmed_cardiovascular_context", "no_contraindication_external_gate")
        if reason is not None:
            return _context(trigger_id, False, "external_safety_gate_unknown" if "contraindication" in reason else reason)
        events = row.get("qualified_aerobic_intensity_events")
        present = isinstance(events, list) and any(isinstance(x, dict) and x.get("source_qualified_aerobic_interval") is True for x in events)
        return _context(trigger_id, present, None if present else "weekly_activity_opportunity_not_qualified", safety_clearance="not_inferred", cardiovascular_state="not_inferred")

    if trigger_id == "trigger_diabetes_bedtime_advancement_open":
        reason = source_reason or _optional_context_gates(row, "adult_18_plus_context", "missingness_qualified", "personal_sleep_baseline", "confirmed_diabetes_context")
        if reason is not None:
            return _context(trigger_id, False, reason)
        if not (row.get("short_sleep_observation") is True and row.get("bedtime_advancement_opportunity") is True):
            return _context(trigger_id, False, "sleep_observation_not_qualified")
        if not (row.get("provider_sleep_interval") is True or row.get("provider_sleep_duration") is True):
            return _context(trigger_id, False, "provider_sleep_measure_missing")
        return _context(trigger_id, True, bedtime_advancement_context_present=True)

    if trigger_id == "trigger_general_active_travel_short_trip_construct_first_v1":
        reason = source_reason
        if reason is None and row.get("complete_local_day") is not True:
            reason = "complete_local_day_required"
        if reason is None and row.get("provider_boundary_preserved") is not True:
            reason = "provider_boundary_not_preserved"
        if reason is not None:
            return _context(trigger_id, False, reason)
        ratio = _number(row.get("baseline_ratio"), "baseline_ratio")
        if ratio >= 0.8:
            return _context(trigger_id, False, "baseline_gap_below_threshold")
        return _context(trigger_id, True, route="not_inferred", safety="not_inferred", fitness="not_inferred", inactivity="not_inferred", copy_action="general_active_travel_short_trip_construct_first_v1")

    if trigger_id == "trigger_general_daytime_nap_earlier_construct_first_v1":
        reason = _nap_common(row, trigger_id)
        if reason is not None:
            return _context(trigger_id, False, reason)
        start = str(row.get("nap_start_local", row.get("daytime_sleep_start", "")))
        hour = int(start.split(":", 1)[0]) if ":" in start else -1
        if hour < 16:
            return _context(trigger_id, False, "nap_start_not_in_late_day_boundary")
        return _context(trigger_id, True, sleep_need="not_inferred", sleep_quality="not_inferred", late_daytime_nap_opportunity=True)

    if trigger_id == "trigger_general_daytime_nap_keep_short_construct_first_v1":
        reason = _nap_common(row, trigger_id)
        if reason is not None:
            return _context(trigger_id, False, reason)
        duration = _number(row.get("nap_duration_minutes"), "nap_duration_minutes")
        if duration <= 15:
            return _context(trigger_id, False, "nap_duration_not_over_15_minutes")
        return _context(trigger_id, True, sleep_need="not_inferred", sleep_quality="not_inferred", short_nap_opportunity=True)

    if trigger_id in {"trigger_general_exercise_start_gradual_pace_construct_first_v2", "trigger_general_exercise_start_warmup_construct_first_v2"}:
        reason = source_reason or _optional_context_gates(row, "provider_semantics_boundary", "general_adult_18_to_64_context")
        if reason is None and row.get("coverage_and_missingness_context") != "qualified":
            reason = "coverage_and_missingness_not_qualified"
        if reason is None and row.get("source_qualified_workout_start_opportunity") is not True:
            reason = "workout_start_opportunity_not_observed"
        if reason is not None:
            return _context(trigger_id, False, reason)
        key = "gradual_pace_opportunity_present" if "gradual" in trigger_id else "warmup_opportunity_present"
        return _context(trigger_id, True, trigger_evidence_mode="provider_workout_start_only", **{key: True})

    if trigger_id == "trigger_general_movement_variety_construct_first_v2":
        reason = _optional_context_gates(row, "provider_semantics_boundary", "general_adult_18_to_64_context")
        if reason is None and row.get("coverage_and_missingness_context") != "qualified":
            reason = "movement_variety_context_unknown"
        if reason is None and row.get("qualified_workout_type_context") != "qualified":
            reason = "movement_variety_context_unknown"
        if reason is None and row.get("complete_local_four_session_window") is not True:
            reason = "movement_variety_context_unknown"
        if reason is None and not (row.get("repeated_activity_type_context") is True and row.get("same_activity_type_session_count", 0) >= 3 and row.get("last_four_qualified_session_count", 0) >= 4):
            reason = "movement_variety_not_needed"
        if reason is not None:
            return _context(trigger_id, False, reason)
        return _context(trigger_id, True, trigger_evidence_mode="qualified_activity_type_and_local_order_only", movement_variety_opportunity=True)

    if trigger_id == "trigger_general_post_exercise_water_pause_construct_first_v1":
        reason = source_reason or _optional_context_gates(row, "local_time_and_coverage", "completed_exercise_session", "provider_quality_and_sampling")
        if reason is None and row.get("qualified_post_exercise_signal_window") is not True:
            reason = "missing_post_exercise_signal_window"
        if reason is not None:
            return _context(trigger_id, False, reason)
        return _context(trigger_id, True, interpretation_boundary="context_presence_only_no_hydration_or_recovery_state", water_pause_opportunity=True)

    if trigger_id == "trigger_general_running_rest_day_construct_first_v2":
        reason = _optional_context_gates(row, "provider_semantics_boundary", "general_adult_18_to_64_context")
        if reason is None and row.get("coverage_and_missingness_context") != "qualified":
            reason = "running_rest_day_context_unknown"
        if reason is None and row.get("complete_local_seven_day_window") is not True:
            reason = "running_rest_day_context_unknown"
        if reason is None and row.get("running_event_source_qualification") != "qualified":
            reason = "running_rest_day_context_unknown"
        if reason is None and row.get("consecutive_running_local_days") is not True:
            reason = "running_rest_day_not_needed"
        if reason is not None:
            return _context(trigger_id, False, reason)
        return _context(trigger_id, True, trigger_evidence_mode="qualified_running_type_and_consecutive_local_days_only", running_rest_day_opportunity=True)

    if trigger_id == "trigger_general_short_sleep_caffeine_cutoff_construct_first_v1":
        reason = source_reason or _optional_context_gates(row, "coverage_and_missingness", "seven_prior_valid_nights", "prior_fourteen_valid_nights", "general_adult_18_to_64_context")
        if reason is not None:
            return _context(trigger_id, False, "insufficient_prior_valid_nights" if "valid_nights" in reason else reason)
        if row.get("current_sleep_below_eighty_percent_median") is not True:
            return _context(trigger_id, False, "short_sleep_opportunity_not_present")
        return _context(trigger_id, True, caffeine_use="not_inferred", sleep_quality="not_inferred", afternoon_caffeine_boundary_opportunity=True)

    onset = {
        "trigger_general_sleep_onset_relaxing_reset_construct_first_v1": "relaxing_reset_opportunity",
        "trigger_general_sleep_onset_worry_note_construct_first_v1": "worry_note_opportunity",
        "trigger_general_sleep_onset_next_day_plan_construct_first_v1": "next_day_plan_opportunity",
    }
    if trigger_id in onset:
        return _sleep_onset(row, trigger_id, onset[trigger_id])

    if trigger_id == "trigger_general_sleep_quiet_environment_construct_first_v1":
        reason = source_reason
        if reason is None:
            for key in ("complete_local_day", "local_timezone_resolved", "coverage_and_missingness"):
                if row.get(key) is False:
                    reason = "missing_source_identity_or_coverage"
                    break
        if reason is not None:
            return _context(trigger_id, False, reason)
        sample = row.get("qualified_sample_max_dbASPL")
        if sample is None:
            return _context(trigger_id, False, "qualified_noise_sample_missing")
        if _number(sample, "qualified_sample_max_dbASPL") < 80:
            return _context(trigger_id, False, "headphone_exposure_below_80_dbASPL")
        return _context(trigger_id, True, sleep_state="not_inferred", bedroom_noise="not_inferred", quiet_sleep_environment_opportunity=True)

    if trigger_id == "trigger_general_strength_spacing_rest_construct_first_v2":
        reason = _optional_context_gates(row, "provider_semantics_boundary", "general_adult_18_to_64_context")
        if reason is None and row.get("coverage_and_missingness_context") != "qualified":
            reason = "strength_spacing_context_unknown"
        if reason is None and row.get("complete_local_two_day_window") is not True:
            reason = "strength_spacing_context_unknown"
        if reason is None and row.get("strength_event_source_qualification") != "qualified":
            reason = "strength_spacing_context_unknown"
        if reason is None and row.get("consecutive_strength_training_days") is not True:
            reason = "strength_spacing_not_needed"
        if reason is not None:
            return _context(trigger_id, False, reason)
        return _context(trigger_id, True, trigger_evidence_mode="qualified_exercise_type_and_consecutive_local_days_only", strength_spacing_opportunity=True)

    if trigger_id == "trigger_general_weekly_activity_spacing_two_day_gap_construct_first_v2":
        return _weekly_spacing(row, trigger_id)

    if trigger_id in {"trigger_general_weekly_brisk_walk_anchor_construct_first_v1", "trigger_general_weekly_social_activity_anchor_construct_first_v1"}:
        key = "brisk_walk_anchor_opportunity" if "brisk_walk" in trigger_id else "social_activity_anchor_opportunity"
        return _weekly_low_aerobic_day(row, trigger_id, key)

    if trigger_id == "trigger_general_weekly_strength_anchor_construct_first_v2":
        reason = _optional_context_gates(row, "provider_semantics_boundary", "general_adult_18_to_64_context")
        if reason is None and (row.get("complete_local_seven_day_window") is not True or row.get("coverage_and_missingness_context") != "qualified" or row.get("strength_event_source_qualification") != "qualified"):
            reason = "weekly_context_unknown"
        if reason is not None:
            return _context(trigger_id, False, reason)
        count = row.get("strength_training_day_count_below_two")
        if count is not True:
            return _context(trigger_id, False, "weekly_strength_anchor_not_needed")
        return _context(trigger_id, True, trigger_evidence_mode="qualified_exercise_type_and_local_week_only", strength_day_anchor_opportunity=True)

    if trigger_id == "trigger_dyslipidemia_weekly_aerobic_anchor_construct_first_v1":
        reason = source_reason or _optional_context_gates(row, "confirmed_dyslipidemia_context")
        if reason is None and row.get("observed_provider_week_complete") is False:
            reason = "observed_provider_week_incomplete"
        if reason is None and row.get("observed_week_source_present") is False:
            reason = "missing_observed_week_source"
        if reason is None and row.get("overlap_duplicate_ambiguity_present") is True:
            reason = "overlap_duplicate_ambiguity_present"
        if reason is not None:
            return _context(trigger_id, False, reason)
        provider = row.get("provider_platform")
        moderate_days: set[date] = set()
        vigorous_days: set[date] = set()
        if provider == "apple_health_export":
            events = row.get("qualified_intensity_events")
            if not isinstance(events, list):
                return _context(trigger_id, False, "qualified_intensity_events_missing")
            for event in events:
                if not isinstance(event, dict):
                    raise TriggerReferenceError("qualified_intensity_events must contain objects")
                event_day = _parse_day(event.get("startDate", event.get("start_time")))
                if event.get("source_qualified_moderate_aerobic_session") is True:
                    moderate_days.add(event_day)
                if event.get("source_qualified_vigorous_aerobic_session") is True:
                    vigorous_days.add(event_day)
        elif provider == "health_connect":
            records = row.get("records")
            if not isinstance(records, list):
                return _context(trigger_id, False, "records_missing")
            for record in records:
                if not isinstance(record, dict):
                    raise TriggerReferenceError("records must contain objects")
                if record.get("metadata", {}).get("dataOrigin", {}).get("packageName") is None:
                    return _context(trigger_id, False, "record_source_identity_missing")
                try:
                    start = datetime.fromisoformat(str(record.get("startTime")).replace("Z", "+00:00"))
                    end = datetime.fromisoformat(str(record.get("endTime")).replace("Z", "+00:00"))
                except ValueError as exc:
                    raise TriggerReferenceError("Health Connect record time is not ISO parseable") from exc
                if (end - start).total_seconds() / 60.0 < 10:
                    continue
                event_day = _parse_day(record.get("startTime"))
                if record.get("intensity") == "MODERATE":
                    moderate_days.add(event_day)
                if record.get("intensity") == "VIGOROUS":
                    vigorous_days.add(event_day)
        else:
            return _context(trigger_id, False, "unsupported_provider_platform")
        if not moderate_days and not vigorous_days:
            return _context(trigger_id, False, "no_qualified_intensity_session_day")
        if len(moderate_days) >= 5 or len(vigorous_days) >= 3:
            return _context(trigger_id, False, "weekly_aerobic_intensity_alternative_threshold_met")
        return _context(trigger_id, True, qualified_moderate_aerobic_session_days_per_week=len(moderate_days), qualified_vigorous_aerobic_session_days_per_week=len(vigorous_days), trigger_evidence_mode="source_qualified_aerobic_intensity_frequency_context")

    raise TriggerReferenceError(f"no construct-first evaluator for current trigger: {trigger_id}")


# Current IDs that reuse a previously implemented, input-contract-compatible
# calculation.  The current trigger packet remains authoritative; this map is
# only the executable binding to the calculation family.
LEGACY_BINDINGS: dict[str, str] = {
    "trigger_general_short_sleep_nonessential_load_postpone": "trigger_general_short_sleep_nonessential_load_postpone",
    "trigger_general_weekly_sleep_opportunity_buffer_construct_first_v2": "trigger_general_sleep_duration_variability_opportunity",
    "trigger_general_sleep_variability_next_three_night_anchor_construct_first_v2": "trigger_general_sleep_duration_variability_opportunity",
    "trigger_general_hrv_short_sleep_no_number_chase": "trigger_general_hrv_short_sleep_no_number_chase",
    "trigger_general_hrv_short_sleep_no_extra_push": "trigger_general_hrv_short_sleep_no_extra_push",
    "trigger_pneumonia_recovery_short_sleep_day_margin": "trigger_pneumonia_recovery_short_sleep_day_margin",
    "trigger_pneumonia_high_active_energy_next_day_light_start": "trigger_pneumonia_high_active_energy_next_day_light_start",
    "trigger_general_activity_load_gradual_progression_construct_first_v2": "trigger_general_activity_load_gradual_progression",
    "trigger_general_weekly_low_activity_no_catchup_construct_first_v2": "trigger_general_weekly_low_activity_volume_reactivation",
    "trigger_pneumonia_weekly_light_activity_reentry_construct_first_v1": "trigger_general_weekly_low_activity_volume_reactivation",
    "trigger_general_sleep_daylight_routine_construct_first_v2": "trigger_general_sleep_timing_next_day_available_window_anchor",
    "trigger_general_sleep_deviation_post_rest_transition_construct_first_v2": "trigger_general_sleep_timing_next_day_available_window_anchor",
    "trigger_general_sleep_deviation_next_day_first_move_construct_first_v2": "trigger_general_sleep_timing_next_day_available_window_anchor",
    "trigger_general_sedentary_first_break_early_anchor_v2": "trigger_general_sedentary_like_inactivity_first_break_early_anchor",
    "trigger_general_inactivity_gap_easy_restart": "trigger_general_inactivity_gap_easy_restart",
    "trigger_general_inactivity_gap_household_chore_construct_first_v2": "trigger_general_inactivity_gap_easy_restart",
    "trigger_general_inactivity_gap_stretch_reset_construct_first_v2": "trigger_general_inactivity_gap_easy_restart",
    "trigger_general_inactivity_gap_stairs_construct_first_v2": "trigger_general_inactivity_gap_easy_restart",
    "trigger_general_inactivity_gap_walk_in_place_construct_first_v2": "trigger_general_inactivity_gap_easy_restart",
    "trigger_general_posture_change_after_quiet_gap_construct_first_v1": "trigger_general_inactivity_gap_easy_restart",
    "trigger_general_sleep_timing_anchor_one_v2": "trigger_general_sleep_timing_regular_context",
    "trigger_general_bedtime_calm_routine_v2": "trigger_general_sleep_timing_regular_context",
    "trigger_general_weekly_sleep_timing_continuation_construct_first_v2": "trigger_general_sleep_timing_regular_context",
    "trigger_dyslipidemia_weekly_sleep_timing_construct_first_v1": "trigger_general_sleep_timing_regular_context",
    "trigger_diabetes_weekly_sleep_timing_construct_first_v1": "trigger_general_sleep_timing_regular_context",
    "trigger_cardiovascular_weekly_sleep_timing_construct_first_v1": "trigger_general_sleep_timing_regular_context",
    "trigger_diabetes_household_chore_construct_first_v1": "trigger_general_inactivity_gap_transition_anchor",
    "trigger_diabetes_inactivity_gap_next_move_v2": "trigger_diabetes_sedentary_break_device",
    "trigger_cardiovascular_inactivity_gap_construct_first_v1": "trigger_cardiovascular_device_inactivity_break",
    "trigger_dyslipidemia_weekly_activity_distribution_construct_first_v1": "trigger_general_weekly_activity_distribution_next_week_anchor",
    "trigger_general_weekly_activity_distribution_one_anchor_construct_first_v2": "trigger_general_weekly_activity_distribution_next_week_anchor",
    "trigger_general_same_pace_higher_hr_keep_easy": "trigger_general_same_pace_higher_hr_keep_easy",
    "trigger_general_same_pace_higher_hr_easy_next_construct_first_v1": "trigger_general_same_pace_higher_hr_keep_easy",
    "trigger_general_activity_load_spike_easy_buffer": "trigger_general_activity_load_spike_easy_buffer",
    "trigger_general_post_exercise_hrr_easy_cooldown": "trigger_general_post_exercise_hrr_easy_cooldown",
    "trigger_htn_high_after_quiet_activity_load_lighten_next": "trigger_htn_high_after_quiet_activity_load_lighten_next",
    "trigger_general_weekly_aerobic_low_day_anchor_construct_first_v2": "trigger_general_weekly_aerobic_activity_distribution_below_3_days",
    "trigger_general_unaccustomed_activity_keep_easy_next": "trigger_general_unaccustomed_activity_keep_easy_next",
    "trigger_general_late_activity_sleep_warm_wash_construct_first_v2": "trigger_general_late_activity_sleep_winddown_anchor",
    "trigger_general_late_activity_sleep_light_cutoff_construct_first_v2": "trigger_general_late_activity_sleep_winddown_anchor",
    "trigger_general_late_activity_sleep_breathing_construct_first_v2": "trigger_general_late_activity_sleep_winddown_anchor",
    "trigger_general_late_activity_sleep_winddown_construct_first_v2": "trigger_general_late_activity_sleep_winddown_anchor",
    "trigger_general_late_activity_sleep_reading_construct_first_v2": "trigger_general_late_activity_sleep_winddown_anchor",
    "trigger_general_weekly_weekend_sleep_anchor_construct_first_v2": "trigger_general_weekend_sleep_shift_first_activity_anchor",
    "trigger_general_postmeal_quiet_window_small_walk": "trigger_general_postmeal_quiet_window_small_walk",
    "trigger_dyslipidemia_post_exercise_cooldown_construct_first_v1": "trigger_dyslipidemia_cooldown_walk_open",
    "trigger_cardiovascular_short_activity_bout_construct_first_v1": "trigger_general_any_length_mvpa_health_connect_intensity",
    "trigger_general_short_activity_bout_keep_moving_construct_first_v2": "trigger_general_any_length_mvpa_health_connect_intensity",
    "trigger_diabetes_weekly_activity_spacing_construct_first_v1": "trigger_diabetes_weekly_mvpa_volume_frequency_below_target",
    "trigger_general_walking_speed_drop_close_short": "trigger_general_walking_speed_drop_close_short",
    "trigger_general_walking_speed_drop_easy_pace_construct_first_v2": "trigger_general_walking_speed_drop_easy_pace",
    "trigger_cardiovascular_weekly_high_volume_buffer_construct_first_v1": "trigger_general_weekly_high_activity_volume_no_extra_push",
    "trigger_general_weekly_activity_minutes_anchor_construct_first_v2": "trigger_general_weekly_high_activity_volume_no_extra_push",
    "trigger_general_weekly_high_activity_volume_buffer_construct_first_v2": "trigger_general_weekly_high_activity_volume_no_extra_push",
    "trigger_general_spo2_post_exercise_easy_cooldown": "trigger_general_spo2_post_exercise_easy_cooldown",
    "trigger_general_rhr_load_sleep_no_extra_push": "trigger_general_rhr_load_sleep_no_extra_push",
    "trigger_htn_resistance_equipment_frequency_below_2_sessions": "trigger_htn_resistance_equipment_frequency_below_2_sessions",
    "trigger_dyslipidemia_activity_snack_v2": "trigger_general_activity_volume_baseline_gap_small_reentry",
    "trigger_hypertension_activity_distribution_v2": "trigger_general_activity_volume_baseline_gap_small_reentry",
    "trigger_general_activity_small_start_v2": "trigger_general_activity_volume_baseline_gap_small_reentry",
    "trigger_pneumonia_recovery_task_split_v2": "trigger_general_activity_volume_baseline_gap_small_reentry",
    "trigger_pneumonia_recovery_activity_volume_small_reentry": "trigger_pneumonia_recovery_activity_volume_small_reentry",
    "trigger_htn_weekly_exercise_duration_above_150_minutes": "trigger_htn_weekly_exercise_duration_above_150_minutes",
    "trigger_general_sleep_duration_below_range_bedtime_advancement_construct_first_v2": "trigger_general_sleep_duration_below_range",
    "trigger_htn_weekly_exercise_duration_below_90_minutes": "trigger_htn_weekly_exercise_duration_below_90_minutes",
    "trigger_htn_aerobic_exercise_frequency_below_5_sessions": "trigger_htn_aerobic_exercise_frequency_below_5_sessions",
    "trigger_general_recorded_exercise_timing_keep_flexible_construct_first_v2": "trigger_general_recorded_exercise_timing_keep_flexible",
}


def evaluate_trigger(trigger_id: str, input_fixture: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(input_fixture, dict):
        raise TriggerReferenceError("normalized trigger input must be an object")
    if trigger_id in LEGACY_BINDINGS:
        return _legacy(LEGACY_BINDINGS[trigger_id], input_fixture, trigger_id)
    return _reference_new(trigger_id, input_fixture)


def _expected_state(row: dict[str, Any]) -> bool:
    expected = row.get("expected_derived_output")
    if not isinstance(expected, dict):
        raise TriggerReferenceError("fixture expected_derived_output must be an object")
    for key in ("context_present", "triggered"):
        if key in expected:
            if not isinstance(expected[key], bool):
                raise TriggerReferenceError(f"fixture {key} must be boolean")
            return expected[key]
    raise TriggerReferenceError("fixture has no context_present or triggered")


def replay_fixtures(data_dir: Path) -> dict[str, int]:
    fixtures = json.loads((data_dir / "golden_fixtures.json").read_text(encoding="utf-8"))
    mismatches = 0
    errors = 0
    positive = 0
    negative = 0
    for fixture in fixtures:
        expected = _expected_state(fixture)
        try:
            actual = evaluate_trigger(fixture["trigger_id"], fixture["input_fixture"])
            observed = actual.get("context_present", actual.get("triggered"))
            if observed != expected:
                mismatches += 1
        except Exception:
            errors += 1
        if expected:
            positive += 1
        else:
            negative += 1
    return {
        "positive_fixtures": positive,
        "no_trigger_fixtures": negative,
        "evaluated": len(fixtures) - errors,
        "mismatches": mismatches,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the construct-first reference evaluator")
    parser.add_argument("--data", type=Path, required=True, help="bundle data directory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("replay")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("trigger_id")
    evaluate.add_argument("input_json", type=Path)
    args = parser.parse_args()
    if args.command == "replay":
        summary = replay_fixtures(args.data)
        print(json.dumps({"result": "pass" if not summary["mismatches"] and not summary["errors"] else "fail", **summary}, ensure_ascii=False))
        raise SystemExit(0 if not summary["mismatches"] and not summary["errors"] else 1)
    input_fixture = json.loads(args.input_json.read_text(encoding="utf-8"))
    print(json.dumps(evaluate_trigger(args.trigger_id, input_fixture), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
