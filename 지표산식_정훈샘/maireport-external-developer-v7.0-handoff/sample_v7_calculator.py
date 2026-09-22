#!/usr/bin/env python3
"""maiReport v7 reference calculator.

Standard-library-only sample for an external implementation.

Usage:
  python3 sample_v7_calculator.py examples/v7-normalized-input.example.json
  python3 sample_v7_calculator.py examples/v7-device-export.example.json --format device

This is an executable reference for the contract. It is deliberately small:
provider authentication, persistence, user questions, and production-grade
provenance storage remain outside this sample.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from zoneinfo import ZoneInfo


VERSION = "v7.0"
I1_WEIGHTS = {"movement": 0.20, "distribution": 0.30, "low_burden": 0.25, "sleep": 0.25}
I3_WEIGHTS = {"volume": 0.30, "distribution": 0.15, "exercise": 0.15,
              "action": 0.15, "persistence": 0.10, "sleep_routine": 0.15}


def clip(value, low, high):
    return max(low, min(high, value))


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def avg(values):
    values = [float(v) for v in values if finite(v)]
    return mean(values) if values else None


def parse_datetime(value, timezone):
    """Parse an ISO timestamp and convert it to the user's local timezone."""
    if not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(ZoneInfo(timezone))


def display_score(indicator, raw):
    if raw is None:
        return None
    if indicator == "I1":
        return clip((raw - 35.0) * 100.0 / 55.0, 0.0, 100.0)
    if indicator == "I2":
        return clip(raw, 0.0, 100.0)
    return clip((raw - 30.0) * 100.0 / 40.0, 0.0, 100.0)


def category(indicator, display):
    if display is None:
        return None
    first, second = (40.0, 70.0) if indicator == "I1" else (33.0, 66.0)
    return "low" if display < first else "middle" if display < second else "high"


def result(indicator, status, raw=None, coverage=None, provenance=None, **extra):
    shown = display_score(indicator, raw)
    payload = {
        "status": status,
        "raw_score": round(raw, 4) if raw is not None else None,
        "display_score_0_100": round(shown, 4) if shown is not None else None,
        "category": category(indicator, shown),
        "coverage": coverage or {},
        "provenance": provenance or [],
    }
    payload.update(extra)
    return payload


def score_i1(day):
    data = day.get("i1") or {}
    if data.get("mode") == "context_only":
        return result("I1", "context_only", coverage={"mode": "daily_total_only"})

    names = ("movement", "distribution", "low_burden", "sleep")
    components = {}
    movement = data.get("movement_minutes")
    partitions = data.get("active_partition_count")
    partition_count = data.get("partition_count")
    concentration = data.get("activity_concentration")
    shortfall = data.get("sleep_shortfall_minutes")

    if finite(movement):
        components["movement"] = clip(movement / 240.0, 0.0, 1.0)
    if finite(partitions) and finite(partition_count) and partition_count > 0 and finite(concentration):
        components["distribution"] = clip(partitions / partition_count, 0.0, 1.0) * clip((1.0 - concentration) / 0.75, 0.0, 1.0)
    if finite(movement) and finite(concentration):
        low_movement_burden = 1.0 - clip((movement - 240.0) / 240.0, 0.0, 1.0)
        concentration_burden = 1.0 - clip((concentration - 0.50) / 0.50, 0.0, 1.0)
        components["low_burden"] = 0.5 * low_movement_burden + 0.5 * concentration_burden
    if finite(shortfall):
        components["sleep"] = clip(1.0 - shortfall / 120.0, 0.0, 1.0)

    available = [(name, value, I1_WEIGHTS[name]) for name, value in components.items()]
    if not available:
        return result("I1", "insufficient", coverage={"available_components": 0})
    weight_sum = sum(weight for _, _, weight in available)
    raw = 35.0 + 55.0 * sum(value * weight for _, value, weight in available) / weight_sum
    if "sleep" not in components:
        raw = min(raw, 82.0)
    return result("I1", "available", raw, coverage={"available_components": list(components)},
                  provenance=["normalized_v7_input"], components=components)


def step_volume_credit(steps):
    curve = ((0, 0.0), (3000, 0.35), (6000, 0.65), (10000, 0.95), (12000, 1.0))
    if not finite(steps) or steps < 0:
        return None
    for (left_steps, left_credit), (right_steps, right_credit) in zip(curve, curve[1:]):
        if steps <= right_steps:
            fraction = (steps - left_steps) / (right_steps - left_steps)
            return left_credit + fraction * (right_credit - left_credit)
    return 1.0


def score_i2(day):
    data = day.get("i2") or {}
    daily_steps = data.get("daily_steps")
    credits = {}
    step_credit = step_volume_credit(daily_steps)
    if step_credit is not None:
        credits["daily_step_volume"] = step_credit
    for field, name in (("post_anchor_action_credit", "postmeal_activity_timing"),
                        ("inactivity_break_credit", "inactivity_break_reactivation"),
                        ("movement_distribution_credit", "movement_distribution")):
        value = data.get(field)
        if finite(value) and 0.0 <= value <= 1.0:
            credits[name] = value
    if not credits:
        return result("I2", "unknown", coverage={"available_components": []})
    if set(credits) == {"daily_step_volume"}:
        return result("I2", "context_only", coverage={"available_components": list(credits)},
                      provenance=["daily_step_volume_context_only"], components=credits)

    # Daily volume remains an activity-context component when a richer lane is
    # present; it never creates service-action completion by itself.
    weights = {"daily_step_volume": 0.55, "postmeal_activity_timing": 0.20,
               "inactivity_break_reactivation": 0.15, "movement_distribution": 0.10}
    observed_weight = sum(weights[name] for name in credits)
    caps = {"volume_only": 85.0, "partial_base": 55.0, "partial_weight_scale": 45.0,
            "multi_context_min": 95.0, "full_context": 100.0}
    if set(credits) == set(weights):
        cap, evidence = caps["full_context"], "full_context"
    else:
        cap, evidence = caps["partial_base"] + caps["partial_weight_scale"] * observed_weight, "partial_context"
        if "daily_step_volume" in credits:
            cap = max(cap, caps["volume_only"])
        if "daily_step_volume" in credits and len(credits) >= 3:
            cap = max(cap, caps["multi_context_min"])
    quality = sum(weights[name] * value for name, value in credits.items()) / observed_weight
    raw = clip(quality * cap, 0.0, 100.0)
    return result("I2", "available", raw,
                  coverage={"available_components": list(credits), "evidence_level": evidence},
                  provenance=["normalized_v7_input"], components=credits)


def generic_signal(recent, baseline):
    recent_mean, baseline_mean = avg(recent), avg(baseline)
    if recent_mean is None or baseline_mean is None:
        return None
    return clip((recent_mean - baseline_mean) / max(abs(baseline_mean) * 0.50, 1.0), -1.0, 1.0)


def action_rate(day):
    opportunities = day.get("action_opportunities")
    completed = day.get("action_completed")
    if not finite(opportunities) or not finite(completed) or opportunities <= 0:
        return None
    return clip(completed / opportunities, 0.0, 1.0)


def action_totals(window):
    """Aggregate completed/opportunity counts; unknown is excluded."""
    opportunities = 0.0
    completed = 0.0
    valid_days = 0
    for day in window:
        data = day.get("i3", {})
        day_opportunities = data.get("action_opportunities")
        day_completed = data.get("action_completed")
        if finite(day_opportunities) and finite(day_completed) and day_opportunities >= 0 and day_completed >= 0:
            opportunities += day_opportunities
            completed += min(day_completed, day_opportunities)
            valid_days += 1
    return opportunities, completed, valid_days


def routine_stability(window):
    """Return routine regularity: lower bedtime/wake variability is better."""
    bed = [x for x in (d.get("bedtime_minute_local") for d in window) if finite(x)]
    wake = [x for x in (d.get("wake_time_minute_local") for d in window) if finite(x)]
    if len(bed) < 3 or len(wake) < 3:
        return None
    return (pstdev(bed) + pstdev(wake)) / 2.0


def score_i3(days):
    ordered = sorted(days, key=lambda x: x["day"])
    if not ordered:
        return result("I3", "insufficient", coverage={"recent_days": 0, "baseline_days": 0})
    latest = date.fromisoformat(ordered[-1]["day"])
    recent_start = latest - timedelta(days=6)
    baseline_start = latest - timedelta(days=13)
    recent = [d for d in ordered if recent_start <= date.fromisoformat(d["day"]) <= latest]
    baseline = [d for d in ordered if baseline_start <= date.fromisoformat(d["day"]) < recent_start]
    if len(recent) < 3 or len(baseline) < 3:
        return result("I3", "insufficient", coverage={"recent_days": len(recent), "baseline_days": len(baseline)},
                      calculated_for_day=latest.isoformat())

    components = {}

    def add_generic(name, field):
        recent_values = [d.get("i3", {}).get(field) for d in recent]
        baseline_values = [d.get("i3", {}).get(field) for d in baseline]
        if sum(finite(v) for v in recent_values) >= 3 and sum(finite(v) for v in baseline_values) >= 3:
            components[name] = generic_signal(recent_values, baseline_values)

    add_generic("volume", "volume")
    add_generic("distribution", "active_minutes")

    recent_exercise = [d.get("i3", {}).get("exercise_minutes") for d in recent]
    baseline_exercise = [d.get("i3", {}).get("exercise_minutes") for d in baseline]
    if sum(finite(v) for v in recent_exercise) >= 3 and sum(finite(v) for v in baseline_exercise) >= 3:
        components["exercise"] = generic_signal(recent_exercise, baseline_exercise)

    recent_opportunities, recent_completed, recent_action_days = action_totals(recent)
    baseline_opportunities, baseline_completed, baseline_action_days = action_totals(baseline)
    if recent_action_days >= 3 and baseline_action_days >= 3 and recent_opportunities > 0 and baseline_opportunities > 0:
        recent_rate = recent_completed / recent_opportunities
        baseline_rate = baseline_completed / baseline_opportunities
        components["action"] = clip((recent_rate - baseline_rate) / 0.50, -1.0, 1.0)

    recent_persistence = [1.0 if d["i3"].get("volume") > 0 else 0.0 for d in recent if finite(d.get("i3", {}).get("volume"))]
    baseline_persistence = [1.0 if d["i3"].get("volume") > 0 else 0.0 for d in baseline if finite(d.get("i3", {}).get("volume"))]
    if len(recent_persistence) >= 3 and len(baseline_persistence) >= 3:
        components["persistence"] = generic_signal(recent_persistence, baseline_persistence)

    recent_routine = routine_stability(recent)
    baseline_routine = routine_stability(baseline)
    if recent_routine is not None and baseline_routine is not None:
        components["sleep_routine"] = clip((baseline_routine - recent_routine) / max(abs(baseline_routine) * 0.50, 15.0), -1.0, 1.0)

    if not components:
        return result("I3", "insufficient", coverage={"recent_days": len(recent), "baseline_days": len(baseline), "components": 0},
                      calculated_for_day=latest.isoformat())
    weight_sum = sum(I3_WEIGHTS[name] for name in components)
    signal = sum(I3_WEIGHTS[name] * value for name, value in components.items()) / weight_sum
    raw = 50.0 + 20.0 * clip(signal, -1.0, 1.0)
    return result("I3", "available", raw,
                  coverage={"recent_days": len(recent), "baseline_days": len(baseline), "components": list(components)},
                  provenance=["normalized_v7_input", "7_day_vs_7_day"], components=components,
                  calculated_for_day=latest.isoformat())


def calculate(normalized):
    if normalized.get("formula_version") != VERSION:
        raise ValueError("formula_version must be v7.0")
    days = sorted(normalized.get("days") or [], key=lambda x: x["day"])
    return {"formula_version": VERSION, "results": {
        "I1": score_i1(days[-1]) if days else result("I1", "insufficient"),
        "I2": score_i2(days[-1]) if days else result("I2", "insufficient"),
        "I3": score_i3(days),
    }}


def first_value(row, *names):
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return None


def _health_connect_metadata(row):
    metadata = row.get("metadata") or {}
    origin = metadata.get("dataOrigin") or metadata.get("data_origin") or {}
    device = metadata.get("device") or {}
    package_name = origin.get("packageName") or origin.get("package_name")
    return {
        "metadata_id": metadata.get("id"),
        "client_record_id": metadata.get("clientRecordId") or metadata.get("client_record_id"),
        "data_origin_package": package_name,
        "device": {
            key: device.get(key)
            for key in ("manufacturer", "model", "type")
            if device.get(key) is not None
        },
        "recording_method": metadata.get("recordingMethod") or metadata.get("recording_method"),
    }


def normalize_device_export(raw):
    """Convert Apple/Samsung/Health Connect-like export envelopes to v7 input.

    Accepted step aliases include Apple value/startDate/endDate and Samsung
    step_count/start_time/end_time. This is an educational adapter, not a
    replacement for provider-specific production parsing.
    """
    timezone = raw.get("user_timezone", "UTC")
    provider = raw.get("provider", "unknown")
    if provider == "health_connect":
        return normalize_health_connect_export(raw)
    grouped = defaultdict(lambda: {"steps": [], "sleep": [], "exercise": []})
    seen = set()
    rejected = []

    for row in raw.get("steps", []):
        start = parse_datetime(first_value(row, "startDate", "start_time", "start"), timezone)
        end = parse_datetime(first_value(row, "endDate", "end_time", "end"), timezone)
        value = first_value(row, "value", "steps", "step_count")
        source_type = row.get("source_type")
        if provider == "samsung_health" and source_type is not None:
            try:
                normalized_source_type = int(source_type)
            except (TypeError, ValueError):
                normalized_source_type = None
            if normalized_source_type != -2:
                rejected.append({"kind": "step", "reason": "non_native_source_type", "source_type": source_type})
                continue
        if start is None or end is None or end <= start or not finite(value):
            rejected.append({"kind": "step", "reason": "invalid_or_timezone_missing"})
            continue
        if start.date() != end.date():
            rejected.append({"kind": "step", "reason": "cross_midnight"})
            continue
        key = (start.isoformat(), end.isoformat(), float(value))
        if key in seen:
            continue
        seen.add(key)
        grouped[start.date()]["steps"].append((start, end, float(value)))

    sleep_seen = set()
    for row in raw.get("sleep", []):
        start = parse_datetime(first_value(row, "startDate", "start_time", "start"), timezone)
        end = parse_datetime(first_value(row, "endDate", "end_time", "end"), timezone)
        if start is None or end is None or end <= start:
            continue
        key = (start.isoformat(), end.isoformat())
        if key in sleep_seen:
            continue
        sleep_seen.add(key)
        # Sleep is attributed once to the local end day, consistently with
        # Health Connect. Step daypart/gap intervals remain same-day only.
        grouped[end.date()]["sleep"].append((start, end))

    for row in raw.get("exercise", []):
        start = parse_datetime(first_value(row, "startDate", "start_time", "start"), timezone)
        duration = first_value(row, "duration", "duration_minutes")
        if start is not None and finite(duration) and duration >= 0:
            grouped[start.date()]["exercise"].append(float(duration))

    days = []
    for day, parts in sorted(grouped.items()):
        rows = sorted(parts["steps"], key=lambda x: x[0])
        overlap = any(rows[i][1] > rows[i + 1][0] for i in range(len(rows) - 1))
        positive = [row for row in rows if row[2] > 0]
        daily_steps = sum(row[2] for row in rows)
        movement_minutes = sum((end - start).total_seconds() / 60.0 for start, end, _ in positive)
        partitions = [0.0] * 8
        for start, end, _ in positive:
            slot = min(7, int((start.hour * 60 + start.minute) / 180))
            partitions[slot] += (end - start).total_seconds() / 60.0
        active_partition_count = sum(value > 0 for value in partitions)
        concentration = max(partitions) / movement_minutes if movement_minutes > 0 else None
        total_gap = 0.0
        first_reactivation = None
        for previous, current in zip(positive, positive[1:]):
            gap = (current[0] - previous[1]).total_seconds() / 60.0
            if gap >= 60:
                total_gap += gap
                if first_reactivation is None:
                    first_reactivation = current[2]
        gap_quality = clip(1.0 - min(total_gap, 900.0) / 900.0, 0.0, 1.0)
        reactivation_quality = clip((first_reactivation / daily_steps) / 0.25, 0.0, 1.0) if first_reactivation is not None and daily_steps > 0 else None
        inactivity_break_credit = (0.70 * reactivation_quality + 0.30 * gap_quality) if reactivation_quality is not None else None
        movement_distribution_credit = clip(active_partition_count / 8.0, 0.0, 1.0) * clip((1.0 - concentration) / 0.75, 0.0, 1.0) if concentration is not None else None
        sleep_minutes = sum((end - start).total_seconds() / 60.0 for start, end in parts["sleep"])
        sleep_shortfall = max(0.0, 480.0 - sleep_minutes) if parts["sleep"] else None
        source = {"provider": provider, "metric": "steps", "unit": "count",
                  "source_identity": raw.get("source_identity", provider),
                  "provenance_status": "sample_provider_export",
                  "observation_status": "observed" if rows else "missing"}
        days.append({
            "day": day.isoformat(), "source": source,
            "i1": {"mode": "rich" if rows and not overlap else "context_only",
                   "movement_minutes": movement_minutes if not overlap else None,
                   "active_partition_count": active_partition_count if not overlap else None,
                   "partition_count": 8 if not overlap else None,
                   "activity_concentration": concentration if not overlap else None,
                   "sleep_shortfall_minutes": sleep_shortfall},
            "i2": {"daily_steps": daily_steps,
                   "post_anchor_action_credit": None,
                   "inactivity_break_credit": inactivity_break_credit if not overlap else None,
                   "movement_distribution_credit": movement_distribution_credit if not overlap else None},
            "i3": {"volume": daily_steps, "active_minutes": movement_minutes if not overlap else None,
                   "movement_bouts": len(positive), "exercise_sessions": len(parts["exercise"]),
                   "exercise_minutes": sum(parts["exercise"]) if parts["exercise"] else 0.0,
                   "action_opportunities": None, "action_completed": None, "action_unresolved": None,
                   "bedtime_minute_local": None, "wake_time_minute_local": None},
        })
    return {"formula_version": VERSION, "user_timezone": timezone, "days": days,
            "adapter_diagnostics": {"rejected_rows": rejected}}


def normalize_health_connect_export(raw):
    """Normalize Health Connect records without summing competing origins.

    The input is a transport-neutral JSON representation of Health Connect's
    StepsRecord, SleepSessionRecord, and ExerciseSessionRecord.  The service
    must choose either an aggregate daily total or one approved data-origin
    lane before calling this sample adapter; this function rejects overlapping
    step intervals and removes exact record-id duplicates.
    """
    timezone = raw.get("user_timezone", "UTC")
    provider = raw.get("provider", "health_connect")
    records = raw.get("records") or raw.get("health_connect") or {}
    allowed_origins = set(raw.get("allowed_data_origin_packages") or [])
    origin_packages = {
        package
        for rows in (records.get("steps", []), records.get("sleep_sessions", records.get("sleep", [])),
                     records.get("exercise_sessions", records.get("exercise", [])))
        for row in rows
        for package in [_health_connect_metadata(row).get("data_origin_package")]
        if package
    }
    if len(origin_packages) > 1 and not allowed_origins:
        raise ValueError("health_connect_source_policy_required")
    grouped = defaultdict(lambda: {"steps": [], "sleep": [], "exercise": [], "sources": [], "aggregate_steps": None})
    rejected = []
    seen_ids = set()
    seen_fallback = set()

    def record_key(row, kind, start, end, value=None):
        metadata = _health_connect_metadata(row)
        record_id = metadata.get("metadata_id")
        if record_id:
            return (kind, "id", record_id)
        return (kind, "fallback", metadata.get("data_origin_package"), start.isoformat(),
                end.isoformat(), value)

    for row in records.get("steps", []):
        start = parse_datetime(first_value(row, "startTime", "start_time", "start"), timezone)
        end = parse_datetime(first_value(row, "endTime", "end_time", "end"), timezone)
        value = first_value(row, "count", "value", "steps")
        if start is None or end is None or end <= start or not finite(value):
            rejected.append({"kind": "health_connect_step", "reason": "invalid_or_timezone_missing"})
            continue
        key = record_key(row, "step", start, end, float(value))
        if key in seen_ids or key in seen_fallback:
            continue
        (seen_ids if key[1] == "id" else seen_fallback).add(key)
        metadata = _health_connect_metadata(row)
        if allowed_origins and metadata.get("data_origin_package") not in allowed_origins:
            rejected.append({"kind": "health_connect_step", "reason": "data_origin_not_allowed",
                             "data_origin_package": metadata.get("data_origin_package")})
            continue
        grouped[start.date()]["steps"].append((start, end, float(value), metadata))

    # Aggregate API output is deliberately a low-resolution lane. It can
    # produce a daily context value, but never fabricated intervals.
    if not records.get("steps"):
        for row in records.get("aggregate_steps", records.get("daily_steps", [])):
            day = row.get("day")
            value = first_value(row, "count", "value", "steps")
            if isinstance(day, str) and finite(value) and value >= 0:
                try:
                    grouped[date.fromisoformat(day[:10])]["aggregate_steps"] = float(value)
                except ValueError:
                    rejected.append({"kind": "health_connect_aggregate", "reason": "invalid_day"})
            else:
                rejected.append({"kind": "health_connect_aggregate", "reason": "invalid_day_or_count"})

    for row in records.get("sleep_sessions", records.get("sleep", [])):
        start = parse_datetime(first_value(row, "startTime", "start_time", "start"), timezone)
        end = parse_datetime(first_value(row, "endTime", "end_time", "end"), timezone)
        if start is None or end is None or end <= start:
            rejected.append({"kind": "health_connect_sleep", "reason": "invalid_or_timezone_missing"})
            continue
        if allowed_origins and _health_connect_metadata(row).get("data_origin_package") not in allowed_origins:
            rejected.append({"kind": "health_connect_sleep", "reason": "data_origin_not_allowed"})
            continue
        key = record_key(row, "sleep", start, end)
        if key in seen_ids or key in seen_fallback:
            continue
        (seen_ids if key[1] == "id" else seen_fallback).add(key)
        # A sleep session is attributed to its local end day. It is not
        # split into invented overnight observations.
        grouped[end.date()]["sleep"].append((start, end, row.get("stages", []), _health_connect_metadata(row)))

    for row in records.get("exercise_sessions", records.get("exercise", [])):
        start = parse_datetime(first_value(row, "startTime", "start_time", "start"), timezone)
        end = parse_datetime(first_value(row, "endTime", "end_time", "end"), timezone)
        if start is None or end is None or end <= start:
            rejected.append({"kind": "health_connect_exercise", "reason": "invalid_or_timezone_missing"})
            continue
        if allowed_origins and _health_connect_metadata(row).get("data_origin_package") not in allowed_origins:
            rejected.append({"kind": "health_connect_exercise", "reason": "data_origin_not_allowed"})
            continue
        key = record_key(row, "exercise", start, end)
        if key in seen_ids or key in seen_fallback:
            continue
        (seen_ids if key[1] == "id" else seen_fallback).add(key)
        grouped[start.date()]["exercise"].append(((end - start).total_seconds() / 60.0,
                                                   _health_connect_metadata(row)))

    days = []
    for day, parts in sorted(grouped.items()):
        rows = sorted(parts["steps"], key=lambda x: x[0])
        overlap = any(rows[i][1] > rows[i + 1][0] for i in range(len(rows) - 1))
        if overlap:
            rejected.append({"kind": "health_connect_step", "reason": "overlapping_intervals", "day": day.isoformat()})
        positive = [row for row in rows if row[2] > 0]
        daily_steps = sum(row[2] for row in rows) if rows else parts["aggregate_steps"]
        movement_minutes = sum((end - start).total_seconds() / 60.0 for start, end, _, _ in positive)
        partitions = [0.0] * 8
        for start, end, _, _ in positive:
            slot = min(7, int((start.hour * 60 + start.minute) / 180))
            partitions[slot] += (end - start).total_seconds() / 60.0
        active_partition_count = sum(value > 0 for value in partitions)
        concentration = max(partitions) / movement_minutes if movement_minutes > 0 else None
        total_gap = 0.0
        first_reactivation = None
        for previous, current in zip(positive, positive[1:]):
            gap = (current[0] - previous[1]).total_seconds() / 60.0
            if gap >= 60:
                total_gap += gap
                if first_reactivation is None:
                    first_reactivation = current[2]
        gap_quality = clip(1.0 - min(total_gap, 900.0) / 900.0, 0.0, 1.0)
        reactivation_quality = clip((first_reactivation / daily_steps) / 0.25, 0.0, 1.0) if first_reactivation is not None and daily_steps > 0 else None
        inactivity_break_credit = (0.70 * reactivation_quality + 0.30 * gap_quality) if reactivation_quality is not None else None
        movement_distribution_credit = clip(active_partition_count / 8.0, 0.0, 1.0) * clip((1.0 - concentration) / 0.75, 0.0, 1.0) if concentration is not None else None
        sleep_minutes = sum((end - start).total_seconds() / 60.0 for start, end, _, _ in parts["sleep"])
        sleep_shortfall = max(0.0, 480.0 - sleep_minutes) if parts["sleep"] else None
        source_packages = sorted({row[3].get("data_origin_package") for row in rows if row[3].get("data_origin_package")})
        aggregate_only = not rows and parts["aggregate_steps"] is not None
        source = {"provider": provider, "metric": "steps", "unit": "count",
                  "source_identity": raw.get("source_identity", "health_connect"),
                  "provenance_status": "health_connect_record_metadata",
                  "data_origin_packages": source_packages,
                  "record_ids": [row[3].get("metadata_id") for row in rows if row[3].get("metadata_id")],
                  "observation_status": "observed" if rows else "missing"}
        sleep_sessions = [{"start": start.isoformat(), "end": end.isoformat(), "stages": stages,
                           "provenance": provenance} for start, end, stages, provenance in parts["sleep"]]
        days.append({
            "day": day.isoformat(), "source": source,
            "sleep": {"sessions": sleep_sessions},
            "i1": {"mode": "rich" if rows and not overlap else "context_only",
                   "movement_minutes": movement_minutes if not overlap else None,
                   "active_partition_count": active_partition_count if not overlap else None,
                   "partition_count": 8 if not overlap else None,
                   "activity_concentration": concentration if not overlap else None,
                   "sleep_shortfall_minutes": sleep_shortfall},
            "i2": {"daily_steps": daily_steps,
                   "post_anchor_action_credit": None,
                   "inactivity_break_credit": inactivity_break_credit if not overlap else None,
                   "movement_distribution_credit": movement_distribution_credit if not overlap else None},
            "i3": {"volume": daily_steps, "active_minutes": movement_minutes if not overlap and not aggregate_only else None,
                   "movement_bouts": len(positive), "exercise_sessions": len(parts["exercise"]),
                   "exercise_minutes": sum(item[0] for item in parts["exercise"]) if parts["exercise"] else 0.0,
                   "action_opportunities": None, "action_completed": None, "action_unresolved": None,
                   "bedtime_minute_local": None, "wake_time_minute_local": None},
        })
    return {"formula_version": VERSION, "user_timezone": timezone, "days": days,
            "adapter_diagnostics": {"provider": "health_connect", "allowed_data_origin_packages": sorted(allowed_origins), "rejected_rows": rejected,
                                    "dedupe_key": "metadata.id_then_origin_start_end_value",
                                    "sleep_day_attribution": "local_end_day"}}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Calculate maiReport v7 I1/I2/I3 from sample input")
    parser.add_argument("input", type=Path, help="JSON input file")
    parser.add_argument("--format", choices=("normalized", "device"), default="normalized")
    parser.add_argument("--output", type=Path, help="write output JSON to this path")
    args = parser.parse_args(argv)
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    normalized = normalize_device_export(raw) if args.format == "device" else raw
    output = calculate(normalized)
    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        raise SystemExit(2)
