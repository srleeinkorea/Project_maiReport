"""Convert a redacted Samsung Health export ZIP into Health Connect-shaped JSON.

This is a validation fixture producer, not a claim that Samsung's CSV export is
the same wire format as Health Connect. It preserves Samsung record IDs and
labels every generated record with Samsung Health's Health Connect data origin.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ORIGIN = "com.sec.android.app.shealth"
STAGE_MAP = {"40001": 1, "40002": 4, "40003": 5, "40004": 6}


def member_ending(zip_file: zipfile.ZipFile, suffix: str, required_header: str | None = None) -> str:
    matches = [name for name in zip_file.namelist()
               if name.endswith(suffix) or Path(name).name.startswith(suffix)]
    if required_header:
        matches = [name for name in matches
                   if any(required_header in line for line in
                          zip_file.read(name).decode("utf-8-sig", errors="replace").splitlines()[:4])]
    if not matches:
        raise FileNotFoundError(f"Samsung export member not found: {suffix}")
    if len(matches) > 1:
        raise ValueError(
            f"multiple Samsung export members match {suffix}: {', '.join(sorted(matches))}; "
            "pass an export ZIP containing one snapshot or select the snapshot before conversion"
        )
    return matches[0]


def read_csv(zip_file: zipfile.ZipFile, suffix: str, *, required_header: str | None = None) -> list[dict[str, str]]:
    member = member_ending(zip_file, suffix, required_header=required_header)
    text = zip_file.read(member).decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    # Samsung exports use a metadata line before the CSV header. Some exports
    # contain an additional blank/metadata line; tolerate it without treating
    # a data row as the header.
    header_index = next((index for index, line in enumerate(lines[:4])
                         if "start_time" in line or "startDate" in line), 1)
    return list(csv.DictReader(io.StringIO("\n".join(lines[header_index:]))))


def offset_text(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"UTC([+-])(\d{2})(\d{2})", value.strip())
    if not match:
        return None
    sign, hours, minutes = match.groups()
    return f"{sign}{hours}:{minutes}"


def timestamp(value: str | None, offset: str | None) -> datetime | None:
    if not value or not offset:
        return None
    try:
        return datetime.strptime(value[:23], "%Y-%m-%d %H:%M:%S.%f").replace(
            tzinfo=timezone(datetime.strptime(offset, "%z").utcoffset())
        )
    except (TypeError, ValueError):
        return None


def iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def local_day(value: datetime, user_timezone: str) -> str:
    return value.astimezone(ZoneInfo(user_timezone)).date().isoformat()


def metadata(record_id: str | None, device_id: str | None) -> dict:
    data = {
        "id": record_id or f"generated-{device_id or 'unknown'}",
        "clientRecordId": device_id,
        "dataOrigin": {"packageName": ORIGIN},
        "device": {"manufacturer": "Samsung", "model": "unknown"}
    }
    return data


def convert(input_zip: Path, output: Path, *, user_timezone: str, limit_days: int) -> dict:
    with zipfile.ZipFile(input_zip) as source:
        step_rows = read_csv(source, "com.samsung.shealth.tracker.pedometer_step_count.202109221041.csv") if any(
            name.endswith("com.samsung.shealth.tracker.pedometer_step_count.202109221041.csv") for name in source.namelist()
        ) else read_csv(source, "com.samsung.shealth.tracker.pedometer_step_count.")
        sleep_rows = read_csv(source, "com.samsung.shealth.sleep.202109221041.csv") if any(
            name.endswith("com.samsung.shealth.sleep.202109221041.csv") for name in source.namelist()
        ) else read_csv(source, "com.samsung.shealth.sleep.")
        stage_rows = read_csv(source, "com.samsung.health.sleep_stage.202109221041.csv") if any(
            name.endswith("com.samsung.health.sleep_stage.202109221041.csv") for name in source.namelist()
        ) else read_csv(source, "com.samsung.health.sleep_stage.")
        exercise_rows = read_csv(source, "com.samsung.shealth.exercise.202109221041.csv") if any(
            name.endswith("com.samsung.shealth.exercise.202109221041.csv") for name in source.namelist()
        ) else read_csv(source, "com.samsung.shealth.exercise.",
                        required_header="com.samsung.health.exercise.start_time")

    step_records = []
    for row in step_rows:
        start = timestamp(row.get("com.samsung.health.step_count.start_time"), offset_text(row.get("com.samsung.health.step_count.time_offset")))
        end = timestamp(row.get("com.samsung.health.step_count.end_time"), offset_text(row.get("com.samsung.health.step_count.time_offset")))
        try:
            count = float(row.get("com.samsung.health.step_count.count", ""))
        except ValueError:
            continue
        if start is None or end is None or end <= start or count < 0:
            continue
        step_records.append((start, {"startTime": iso(start), "endTime": iso(end), "count": count,
                                     "metadata": metadata(row.get("com.samsung.health.step_count.datauuid"), row.get("com.samsung.health.step_count.deviceuuid"))}))

    selected_days = sorted({local_day(start, user_timezone) for start, _ in step_records})[:limit_days]
    allowed_days = set(selected_days)
    steps = [record for start, record in step_records if local_day(start, user_timezone) in allowed_days]
    selected_sleep_ids = set()
    sleep_sessions = []
    for row in sleep_rows:
        offset = offset_text(row.get("com.samsung.health.sleep.time_offset"))
        start = timestamp(row.get("com.samsung.health.sleep.start_time"), offset)
        end = timestamp(row.get("com.samsung.health.sleep.end_time"), offset)
        if start is None or end is None or end <= start or local_day(end, user_timezone) not in allowed_days:
            continue
        record_id = row.get("com.samsung.shealth.sleep.datauuid")
        selected_sleep_ids.add(row.get("combined_id") or record_id)
        sleep_sessions.append({"startTime": iso(start), "endTime": iso(end), "stages": [],
                               "metadata": metadata(record_id, row.get("com.samsung.health.sleep.deviceuuid"))})

    for row in stage_rows:
        offset = offset_text(row.get("time_offset"))
        start = timestamp(row.get("start_time"), offset)
        end = timestamp(row.get("end_time"), offset)
        sleep_id = row.get("sleep_id")
        stage = STAGE_MAP.get((row.get("stage") or "").strip())
        if start is None or end is None or end <= start or stage is None or sleep_id not in selected_sleep_ids:
            continue
        for session in sleep_sessions:
            if session["startTime"] <= iso(start) <= session["endTime"]:
                session["stages"].append({"startTime": iso(start), "endTime": iso(end), "stage": stage})
                break

    exercise_sessions = []
    for row in exercise_rows:
        offset = offset_text(row.get("com.samsung.health.exercise.time_offset"))
        start = timestamp(row.get("com.samsung.health.exercise.start_time"), offset)
        end = timestamp(row.get("com.samsung.health.exercise.end_time"), offset)
        if start is None or end is None or end <= start or local_day(start, user_timezone) not in allowed_days:
            continue
        exercise_sessions.append({"startTime": iso(start), "endTime": iso(end),
                                  "exerciseType": row.get("com.samsung.health.exercise.exercise_type"),
                                  "metadata": metadata(row.get("com.samsung.health.exercise.datauuid"), row.get("com.samsung.health.exercise.deviceuuid"))})

    result = {
        "provider": "health_connect",
        "user_timezone": user_timezone,
        "source_identity": "samsung_health_via_health_connect",
        "allowed_data_origin_packages": [ORIGIN],
        "conversion": {"source": str(input_zip), "source_type": "Samsung Health CSV export", "selected_local_days": selected_days},
        "records": {"steps": steps, "sleep_sessions": sleep_sessions, "exercise_sessions": exercise_sessions}
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("input_zip", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--user-timezone", default="Europe/Moscow")
    parser.add_argument("--limit-days", type=int, default=14)
    args = parser.parse_args(argv)
    result = convert(args.input_zip, args.output, user_timezone=args.user_timezone, limit_days=args.limit_days)
    print(json.dumps({"days": result["conversion"]["selected_local_days"], "steps": len(result["records"]["steps"]),
                      "sleep_sessions": len(result["records"]["sleep_sessions"]), "exercise_sessions": len(result["records"]["exercise_sessions"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
