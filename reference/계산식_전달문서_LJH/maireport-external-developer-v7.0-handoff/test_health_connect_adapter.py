"""Small stdlib regression tests for the Health Connect reference adapter."""

import importlib.util
import json
import tempfile
import zipfile
from pathlib import Path


HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("sample_v7_calculator", HERE / "sample_v7_calculator.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CONVERTER_SPEC = importlib.util.spec_from_file_location(
    "samsung_health_to_health_connect_fixture",
    HERE / "samsung_health_to_health_connect_fixture.py",
)
CONVERTER = importlib.util.module_from_spec(CONVERTER_SPEC)
CONVERTER_SPEC.loader.exec_module(CONVERTER)


def load_contract(name):
    return json.loads((HERE / "contracts" / name).read_text())


def load_sample():
    return json.loads((HERE / "examples/v7-health-connect-export.example.json").read_text())


def load_samsung_sample():
    return json.loads((HERE / "examples/v7-health-connect-samsung-health.example.json").read_text())


def test_health_connect_sample_reaches_all_indicators():
    normalized = MODULE.normalize_device_export(load_sample())
    output = MODULE.calculate(normalized)
    assert len(normalized["days"]) == 14
    assert all(output["results"][name]["status"] == "available" for name in ("I1", "I2", "I3"))
    assert 0 <= output["results"]["I3"]["display_score_0_100"] <= 100


def test_health_connect_metadata_id_duplicate_is_not_doubled():
    raw = load_sample()
    first = raw["records"]["steps"][0]
    raw["records"]["steps"].append(dict(first))
    normalized = MODULE.normalize_device_export(raw)
    assert normalized["days"][0]["i3"]["volume"] == 4000


def test_cross_midnight_sleep_is_attributed_once_to_local_end_day():
    normalized = MODULE.normalize_device_export(load_sample())
    rows = {row["day"]: row for row in normalized["days"]}
    assert rows["2026-09-01"]["i1"]["sleep_shortfall_minutes"] == 0
    assert "2026-08-31" not in rows


def test_samsung_health_origin_via_health_connect_is_selectable():
    normalized = MODULE.normalize_device_export(load_samsung_sample())
    output = MODULE.calculate(normalized)
    assert len(normalized["days"]) == 14
    assert output["results"]["I3"]["status"] == "available"
    assert all("com.sec.android.app.shealth" in day["source"]["data_origin_packages"]
               for day in normalized["days"])


def test_unapproved_health_connect_origin_is_rejected():
    raw = load_samsung_sample()
    raw["records"]["steps"][0]["metadata"]["dataOrigin"]["packageName"] = "com.other.app"
    normalized = MODULE.normalize_device_export(raw)
    assert all(day["day"] != "2026-09-01" for day in normalized["days"])
    assert normalized["adapter_diagnostics"]["rejected_rows"][0]["reason"] == "data_origin_not_allowed"


def test_daily_step_context_is_used_when_a_richer_i2_lane_exists():
    result = MODULE.score_i2({"i2": {"daily_steps": 6000, "post_anchor_action_credit": 1.0,
                                     "inactivity_break_credit": None, "movement_distribution_credit": None}})
    assert result["status"] == "available"
    assert "daily_step_volume" in result["components"]


def test_multiple_health_connect_origins_require_source_policy():
    raw = load_sample()
    second = dict(raw["records"]["steps"][0])
    second["metadata"] = dict(second["metadata"])
    second["metadata"]["dataOrigin"] = {"packageName": "com.other.app"}
    raw["records"]["steps"].append(second)
    try:
        MODULE.normalize_device_export(raw)
    except ValueError as exc:
        assert str(exc) == "health_connect_source_policy_required"
    else:
        raise AssertionError("multiple data origins must require a source policy")


def test_generic_device_sleep_cross_midnight_uses_local_end_day():
    raw = {
        "provider": "apple_health",
        "user_timezone": "Asia/Seoul",
        "steps": [{"startDate": "2026-09-01T08:00:00+09:00", "endDate": "2026-09-01T08:10:00+09:00", "value": 100}],
        "sleep": [{"startDate": "2026-08-31T23:00:00+09:00", "endDate": "2026-09-01T07:00:00+09:00"}],
    }
    normalized = MODULE.normalize_device_export(raw)
    rows = {row["day"]: row for row in normalized["days"]}
    assert rows["2026-09-01"]["i1"]["sleep_shortfall_minutes"] == 0
    assert "2026-08-31" not in rows


def _write_synthetic_samsung_zip(path):
    files = {
        "com.samsung.shealth.tracker.pedometer_step_count.synthetic.csv": "meta\ncom.samsung.health.step_count.start_time,com.samsung.health.step_count.end_time,com.samsung.health.step_count.count,com.samsung.health.step_count.time_offset,com.samsung.health.step_count.datauuid,com.samsung.health.step_count.deviceuuid\n2026-09-01 08:00:00.000,2026-09-01 08:10:00.000,100,UTC+0900,step-1,device-1\n2026-09-01 12:00:00.000,2026-09-01 12:10:00.000,200,UTC+0900,step-2,device-1\n",
        "com.samsung.shealth.sleep.synthetic.csv": "meta\ncom.samsung.health.sleep.start_time,com.samsung.health.sleep.end_time,com.samsung.health.sleep.time_offset,com.samsung.shealth.sleep.datauuid,com.samsung.health.sleep.deviceuuid,combined_id\n2026-08-31 23:00:00.000,2026-09-01 07:00:00.000,UTC+0900,sleep-1,device-1,sleep-1\n",
        "com.samsung.health.sleep_stage.synthetic.csv": "meta\nstart_time,end_time,time_offset,stage,sleep_id\n2026-09-01 02:00:00.000,2026-09-01 03:00:00.000,UTC+0900,40003,sleep-1\n",
        "com.samsung.shealth.exercise.synthetic.csv": "meta\ncom.samsung.health.exercise.start_time,com.samsung.health.exercise.end_time,com.samsung.health.exercise.time_offset,com.samsung.health.exercise.exercise_type,com.samsung.health.exercise.datauuid,com.samsung.health.exercise.deviceuuid\n2026-09-01 18:00:00.000,2026-09-01 18:30:00.000,UTC+0900,walking,exercise-1,device-1\n",
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def test_samsung_converter_is_reproducible_without_real_public_data():
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        input_zip = directory / "synthetic-samsung.zip"
        output_json = directory / "converted.json"
        _write_synthetic_samsung_zip(input_zip)
        converted = CONVERTER.convert(input_zip, output_json, user_timezone="Asia/Seoul", limit_days=14)
        assert converted["conversion"]["selected_local_days"] == ["2026-09-01"]
        assert len(converted["records"]["steps"]) == 2
        assert len(converted["records"]["sleep_sessions"]) == 1
        assert converted["records"]["sleep_sessions"][0]["metadata"]["device"]["model"] == "unknown"
        assert converted["records"]["steps"][0]["metadata"]["clientRecordId"] == "device-1"
        normalized = MODULE.normalize_device_export(converted)
        assert normalized["days"][0]["day"] == "2026-09-01"
        assert MODULE.calculate(normalized)["results"]["I3"]["status"] == "insufficient"


def test_converter_rejects_multiple_snapshot_members_instead_of_mixing_exports():
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        input_zip = directory / "ambiguous.zip"
        with zipfile.ZipFile(input_zip, "w") as archive:
            archive.writestr("a/com.samsung.shealth.tracker.pedometer_step_count.one.csv", "meta\nstart_time\n")
            archive.writestr("b/com.samsung.shealth.tracker.pedometer_step_count.two.csv", "meta\nstart_time\n")
        try:
            CONVERTER.read_csv(zipfile.ZipFile(input_zip), "com.samsung.shealth.tracker.pedometer_step_count.")
        except ValueError as exc:
            assert "multiple Samsung export members" in str(exc)
        else:
            raise AssertionError("ambiguous Samsung snapshots must not be mixed")


def test_converter_ignores_same_prefix_recovery_heart_rate_file():
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        input_zip = directory / "exercise-prefix.zip"
        with zipfile.ZipFile(input_zip, "w") as archive:
            archive.writestr(
                "com.samsung.shealth.exercise.synthetic.csv",
                "meta\ncom.samsung.health.exercise.start_time,com.samsung.health.exercise.end_time\n",
            )
            archive.writestr(
                "com.samsung.shealth.exercise.recovery_heart_rate.synthetic.csv",
                "meta\ncom.samsung.health.exercise.recovery_heart_rate.start_time,com.samsung.health.exercise.recovery_heart_rate.end_time\n",
            )
        with zipfile.ZipFile(input_zip) as archive:
            rows = CONVERTER.read_csv(
                archive, "com.samsung.shealth.exercise.",
                required_header="com.samsung.health.exercise.start_time",
            )
        assert rows == []


def test_contracts_cover_reference_runner_shapes():
    normalized_schema = load_contract("normalized-v7-input.schema.json")
    output_schema = load_contract("indicator-v7-output.schema.json")
    assert normalized_schema["additionalProperties"] is False
    assert output_schema["additionalProperties"] is False
    assert set(normalized_schema["$defs"]["i1"]["required"]) == {
        "mode", "movement_minutes", "active_partition_count", "partition_count",
        "activity_concentration", "sleep_shortfall_minutes"
    }
    assert set(normalized_schema["$defs"]["i2"]["required"]) == {
        "daily_steps", "post_anchor_action_credit", "inactivity_break_credit",
        "movement_distribution_credit"
    }
    assert set(normalized_schema["$defs"]["i3"]["required"]) == {
        "volume", "active_minutes", "movement_bouts", "exercise_sessions",
        "exercise_minutes", "action_opportunities", "action_completed",
        "action_unresolved", "bedtime_minute_local", "wake_time_minute_local"
    }
    assert output_schema["$defs"]["result"]["required"] == [
        "status", "raw_score", "display_score_0_100", "category"
    ]
    for example in (HERE / "examples").glob("*.json"):
        raw = json.loads(example.read_text())
        normalized = raw if raw.get("formula_version") else MODULE.normalize_device_export(raw)
        output = MODULE.calculate(normalized)
        assert set(output["results"]) == {"I1", "I2", "I3"}
        for result in output["results"].values():
            assert {"status", "raw_score", "display_score_0_100", "category"} <= set(result)


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
    print("health connect adapter tests passed")
