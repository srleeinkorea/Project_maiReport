#!/usr/bin/env python3
"""Small raw-provider adapter used by the construct-first sample bundle.

This is an executable contract guard, not a production ingestion service.  It
demonstrates the boundary that the operating product must implement: provider
records are reconciled first, only declared fields are used, missing coverage
stays unknown, and disease/safety context is supplied separately. The sample
normalizes Health Connect ``ActivityIntensityRecord`` rows, Apple Health
``HKWorkout`` rows, and Samsung Health ``com.samsung.health.exercise`` rows.
The Apple and Samsung examples converge to one normalized session-time input
before trigger evaluation.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


class AdapterError(ValueError):
    """Raised when raw input cannot satisfy the declared provider contract."""


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise AdapterError(f"invalid JSON input: {path}") from exc


def _iso(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise AdapterError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdapterError(f"{field} is not an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise AdapterError(f"{field} must include a timezone")
    return parsed


def _source_fields(data_dir: Path, trigger_id: str, provider: str) -> list[dict[str, Any]]:
    rows = _read(data_dir / "source_fields.json")
    return [row for row in rows if row.get("trigger_id") == trigger_id and row.get("provider_platform") == provider]


def _require_contract(data_dir: Path, trigger_id: str, provider: str) -> list[dict[str, Any]]:
    fields = _source_fields(data_dir, trigger_id, provider)
    if not fields:
        raise AdapterError(f"no KDB source contract for {trigger_id}/{provider}")
    return fields


def _deduplicate_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    overlap = False
    for record in records:
        identity = record.get("id") or record.get("uid") or json.dumps(record, sort_keys=True, separators=(",", ":"))
        if identity in seen:
            overlap = True
            continue
        seen.add(str(identity))
        unique.append(record)
    return unique, overlap


def normalize_health_connect_activity_intensity(
    data_dir: Path,
    trigger_id: str,
    raw: dict[str, Any],
    external_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize a Health Connect ActivityIntensityRecord sample.

    The adapter accepts only fields represented by the current source contract
    and never invents zeroes for missing rows.  External disease/adult/safety
    inputs are copied explicitly; they are never inferred from the records.
    """
    provider = raw.get("provider_platform")
    if provider != "health_connect":
        raise AdapterError("this sample adapter accepts provider_platform=health_connect only")
    _require_contract(data_dir, trigger_id, provider)
    records = raw.get("records")
    if not isinstance(records, list):
        raise AdapterError("records must be an array")
    unique, duplicate_seen = _deduplicate_records(records)
    intervals: list[float] = []
    intensity_values: list[str] = []
    qualified_events: list[dict[str, Any]] = []
    source_packages: set[str] = set()
    for index, record in enumerate(unique):
        if not isinstance(record, dict):
            raise AdapterError(f"records[{index}] must be an object")
        if record.get("recordType") != "ActivityIntensityRecord":
            continue
        origin = record.get("metadata", {}).get("dataOrigin", {}).get("packageName")
        if not isinstance(origin, str) or not origin:
            raise AdapterError(f"records[{index}] is missing metadata.dataOrigin.packageName")
        source_packages.add(origin)
        start = _iso(record.get("startTime"), f"records[{index}].startTime")
        end = _iso(record.get("endTime"), f"records[{index}].endTime")
        minutes = (end - start).total_seconds() / 60.0
        if minutes <= 0:
            continue
        intensity = record.get("intensity")
        if intensity not in {"MODERATE", "VIGOROUS"}:
            continue
        intensity_values.append(intensity)
        intervals.append(round(minutes, 6))
        qualified_events.append({
            "start_time": start.isoformat(),
            "duration_minutes": round(minutes, 6),
            "source_confirmed_moderate_or_vigorous": True,
            "intensity": intensity,
        })

    normalized: dict[str, Any] = {
        "provider_platform": provider,
        "provider_source_status": "primary_reference_adapter",
        "source_identity_present": bool(source_packages),
        "source_packages": sorted(source_packages),
        "complete_week": raw.get("complete_week") is True,
        "complete_window": raw.get("complete_window") is True,
        "qualified_interval_minutes": intervals,
        "intensity_values": intensity_values,
        "qualified_events": qualified_events,
        "overlap_duplicate_ambiguity_present": duplicate_seen or raw.get("overlap_duplicate_ambiguity_present") is True,
    }
    if isinstance(raw.get("week_start_local_date"), str):
        normalized["week_start_local_date"] = raw["week_start_local_date"]
    if external_context:
        for key, value in external_context.items():
            if key in {"source_identity_present", "complete_week", "complete_window", "qualified_interval_minutes", "qualified_events"}:
                raise AdapterError(f"external context cannot override derived provider field: {key}")
            normalized[key] = value
    return normalized


def _normalize_exercise_timing_records(
    data_dir: Path,
    trigger_id: str,
    raw: dict[str, Any],
    provider: str,
    records: list[dict[str, Any]],
    start_key: str,
    identity_reader,
    type_reader,
    duration_reader=None,
) -> dict[str, Any]:
    """Normalize provider-specific exercise rows to one session-time contract."""
    _require_contract(data_dir, trigger_id, provider)
    unique, duplicate_seen = _deduplicate_records(records)
    starts: list[str] = []
    source_ids: set[str] = set()
    for index, record in enumerate(unique):
        if not isinstance(record, dict):
            raise AdapterError(f"records[{index}] must be an object")
        activity_type = type_reader(record)
        if activity_type is None:
            continue
        identity = identity_reader(record)
        if not isinstance(identity, str) or not identity.strip():
            raise AdapterError(f"records[{index}] is missing provider source identity")
        source_ids.add(identity.strip())
        parsed = _iso(record.get(start_key), f"records[{index}].{start_key}")
        if duration_reader is not None:
            duration_minutes = duration_reader(record, index)
            if duration_minutes <= 0:
                raise AdapterError(f"records[{index}] has non-positive duration")
        starts.append(f"{parsed.hour:02d}:{parsed.minute:02d}")
    return {
        "provider_platform": provider,
        "provider_source_status": "primary_reference_adapter",
        "source_identity_present": bool(source_ids),
        "session_start_times": starts,
        "source_records_count": len(starts),
        "overlap_duplicate_ambiguity_present": duplicate_seen or raw.get("overlap_duplicate_ambiguity_present") is True,
    }


def normalize_apple_exercise_timing(
    data_dir: Path,
    trigger_id: str,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Normalize Apple Health ``HKWorkout`` export rows."""
    if raw.get("provider_platform") != "apple_health_export":
        raise AdapterError("Apple sample requires provider_platform=apple_health_export")
    records = raw.get("records")
    if not isinstance(records, list):
        raise AdapterError("records must be an array")

    def identity(record: dict[str, Any]) -> Any:
        return record.get("sourceName") or record.get("sourceVersion") or record.get("device")

    def activity(record: dict[str, Any]) -> Any:
        return record.get("workoutActivityType")

    def duration(record: dict[str, Any], index: int) -> float:
        start = _iso(record.get("startDate"), f"records[{index}].startDate")
        end = _iso(record.get("endDate"), f"records[{index}].endDate")
        return (end - start).total_seconds() / 60.0

    return _normalize_exercise_timing_records(
        data_dir, trigger_id, raw, "apple_health_export", records,
        "startDate", identity, activity, duration,
    )


def normalize_samsung_exercise_timing(
    data_dir: Path,
    trigger_id: str,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Normalize Samsung Health ``com.samsung.health.exercise`` rows."""
    if raw.get("provider_platform") != "samsung_health_export":
        raise AdapterError("Samsung sample requires provider_platform=samsung_health_export")
    records = raw.get("records")
    if not isinstance(records, list):
        raise AdapterError("records must be an array")

    def identity(record: dict[str, Any]) -> Any:
        return record.get("pkg_name") or record.get("datauuid") or record.get("source_package")

    def activity(record: dict[str, Any]) -> Any:
        return record.get("exercise_type")

    def duration(record: dict[str, Any], index: int) -> float:
        value = record.get("duration")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AdapterError(f"records[{index}].duration must be numeric minutes")
        return float(value)

    return _normalize_exercise_timing_records(
        data_dir, trigger_id, raw, "samsung_health_export", records,
        "start_time", identity, activity, duration,
    )


def normalize(data_dir: Path, trigger_id: str, raw: dict[str, Any], external_context: dict[str, Any] | None = None) -> dict[str, Any]:
    if raw.get("provider_platform") == "health_connect":
        normalized = normalize_health_connect_activity_intensity(data_dir, trigger_id, raw, external_context)
    elif raw.get("provider_platform") == "apple_health_export":
        normalized = normalize_apple_exercise_timing(data_dir, trigger_id, raw)
    elif raw.get("provider_platform") == "samsung_health_export":
        normalized = normalize_samsung_exercise_timing(data_dir, trigger_id, raw)
    else:
        raise AdapterError(f"no sample raw adapter for provider_platform={raw.get('provider_platform')!r}")
    if external_context:
        for key, value in external_context.items():
            if key in {"source_identity_present", "session_start_times", "source_records_count"}:
                raise AdapterError(f"external context cannot override derived provider field: {key}")
            normalized[key] = value
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize a raw provider sample for the construct-first evaluator")
    parser.add_argument("--data", type=Path, required=True, help="bundle data directory")
    parser.add_argument("trigger_id")
    parser.add_argument("raw_json", type=Path)
    parser.add_argument("--external-context", type=Path, help="explicit disease/adult/safety context JSON")
    args = parser.parse_args()
    raw = _read(args.raw_json)
    context = _read(args.external_context) if args.external_context else None
    if context is not None and not isinstance(context, dict):
        raise SystemExit("external context must contain an object")
    print(json.dumps(normalize(args.data, args.trigger_id, raw, context), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
