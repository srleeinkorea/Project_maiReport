#!/usr/bin/env python3
"""Run the construct-first coaching delivery contract.

This runner is intentionally narrower than a production evaluator.  The
operating product owns provider parsing, user identity, permissions, freshness,
prioritisation, deduplication, and delivery.  The runner accepts an already
derived trigger context and resolves it to the construct-first line copy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class ConstructFirstBundleError(ValueError):
    """Raised when the delivery bundle or derived context is incomplete."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConstructFirstBundleError(f"missing bundle file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConstructFirstBundleError(f"invalid JSON: {path}") from exc


def load_bundle(data_dir: Path) -> dict[str, Any]:
    data_dir = data_dir.resolve()
    names = (
        "manifest",
        "construct_first_lines",
        "construct_first_triggers",
        "trigger_packets",
        "source_fields",
        "output_contracts",
        "golden_fixtures",
        "runtime_dependency_map",
    )
    bundle = {name: _read_json(data_dir / f"{name}.json") for name in names}
    validate_bundle(bundle)
    return bundle


def _pair(row: dict[str, Any]) -> tuple[str, str]:
    line_id = row.get("line_id") or row.get("source_line_id") or row.get("coaching_line_id")
    trigger_id = row.get("trigger_id") or row.get("source_trigger_id")
    if not isinstance(line_id, str) or not isinstance(trigger_id, str):
        raise ConstructFirstBundleError(f"row has no line/trigger identity: {row!r}")
    return line_id, trigger_id


def _fixture_triggered(expected: dict[str, Any]) -> bool:
    for key in ("context_present", "triggered"):
        if key in expected:
            if not isinstance(expected[key], bool):
                raise ConstructFirstBundleError(f"{key} must be boolean in fixture output")
            return expected[key]
    raise ConstructFirstBundleError("fixture output must contain context_present or triggered")


def validate_bundle(bundle: dict[str, Any]) -> None:
    manifest = bundle["manifest"]
    if manifest.get("contract") != "construct_first_coaching_delivery_v1":
        raise ConstructFirstBundleError("unexpected construct-first delivery contract")

    dependency_map = bundle["runtime_dependency_map"]
    if dependency_map.get("contract") != "construct_first_runtime_dependency_map_v1":
        raise ConstructFirstBundleError("unexpected runtime dependency map contract")
    objects = dependency_map.get("kdb_objects")
    if not isinstance(objects, list) or not objects:
        raise ConstructFirstBundleError("runtime dependency map has no KDB objects")
    object_artifacts = {row.get("artifact") for row in objects}
    required_artifacts = {
        "construct_first_lines",
        "construct_first_triggers",
        "trigger_packets",
        "source_fields",
        "output_contracts",
        "golden_fixtures",
    }
    if object_artifacts != required_artifacts:
        raise ConstructFirstBundleError("runtime dependency map does not cover bundle artifacts")
    required_runtime = {
        row["artifact"] for row in objects if row.get("runtime_required") is True
    }
    if required_runtime != {
        "construct_first_lines",
        "construct_first_triggers",
        "trigger_packets",
        "source_fields",
        "output_contracts",
    }:
        raise ConstructFirstBundleError("runtime-required KDB artifact set is incomplete")
    fixture_meta = next(row for row in objects if row["artifact"] == "golden_fixtures")
    if fixture_meta.get("validation_only") is not True:
        raise ConstructFirstBundleError("golden fixtures must remain validation-only")
    if not dependency_map.get("external_inputs_not_in_kdb"):
        raise ConstructFirstBundleError("runtime dependency map must declare external inputs")

    lines = bundle["construct_first_lines"]
    line_ids = [row.get("coaching_line_id") for row in lines]
    if not line_ids or any(not isinstance(value, str) for value in line_ids):
        raise ConstructFirstBundleError("construct-first line catalog is empty or malformed")
    if len(set(line_ids)) != len(line_ids):
        raise ConstructFirstBundleError("duplicate construct-first line id")
    if any(row.get("operational_ready") is not True for row in lines):
        raise ConstructFirstBundleError("non-operational line entered construct-first delivery bundle")
    line_set = set(line_ids)

    trigger_rows = bundle["construct_first_triggers"]
    trigger_pairs = {_pair(row) for row in trigger_rows}
    if not trigger_pairs:
        raise ConstructFirstBundleError("construct-first trigger catalog is empty")
    if any(line_id not in line_set for line_id, _ in trigger_pairs):
        raise ConstructFirstBundleError("trigger references a line outside construct-first catalog")
    if any(row.get("external_developer_contract_status") != "external_developer_ready" for row in trigger_rows):
        raise ConstructFirstBundleError("trigger without an external developer contract entered delivery bundle")

    packet_pairs = {_pair(row) for row in bundle["trigger_packets"]}
    source_pairs = {_pair(row) for row in bundle["source_fields"]}
    output_pairs = {_pair(row) for row in bundle["output_contracts"]}
    if packet_pairs != trigger_pairs:
        raise ConstructFirstBundleError("trigger packets do not exactly cover construct-first triggers")
    if source_pairs != trigger_pairs:
        raise ConstructFirstBundleError("source field contracts do not exactly cover construct-first triggers")
    if output_pairs != trigger_pairs:
        raise ConstructFirstBundleError("output contracts do not exactly cover construct-first triggers")

    fixture_groups: dict[tuple[str, str], set[str]] = {}
    for row in bundle["golden_fixtures"]:
        pair = _pair(row)
        if pair not in trigger_pairs:
            raise ConstructFirstBundleError("fixture references a trigger outside construct-first catalog")
        expected = row.get("expected_derived_output")
        if not isinstance(expected, dict):
            raise ConstructFirstBundleError("fixture expected_derived_output must be an object")
        _fixture_triggered(expected)
        fixture_groups.setdefault(pair, set()).add(str(row.get("fixture_kind")))
    for pair in trigger_pairs:
        kinds = fixture_groups.get(pair, set())
        if "positive_trigger_example" not in kinds:
            raise ConstructFirstBundleError(f"trigger lacks a positive fixture: {pair}")


def fixture_gap_pairs(bundle: dict[str, Any]) -> list[tuple[str, str]]:
    trigger_pairs = {_pair(row) for row in bundle["construct_first_triggers"]}
    fixture_groups: dict[tuple[str, str], set[str]] = {}
    for row in bundle["golden_fixtures"]:
        fixture_groups.setdefault(_pair(row), set()).add(str(row.get("fixture_kind")))
    return sorted(
        pair for pair in trigger_pairs
        if "no_trigger_example" not in fixture_groups.get(pair, set())
    )


def _trigger_index(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lines = {row["coaching_line_id"]: row for row in bundle["construct_first_lines"]}
    return {
        row["trigger_id"]: {"trigger": row, "line": lines[row["line_id"]]}
        for row in bundle["construct_first_triggers"]
    }


def select_coaching_candidates(
    bundle: dict[str, Any], derived_context_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Resolve true derived trigger contexts to user-facing coaching lines.

    ``derived_context_rows`` are produced by the operating product's provider
    adapter and signal derivation layer.  This function does not infer disease,
    recovery, diagnosis, clearance, or a medical state from a device signal.
    """
    index = _trigger_index(bundle)
    candidates: list[dict[str, Any]] = []
    for context in derived_context_rows:
        if not isinstance(context, dict):
            raise ConstructFirstBundleError("each derived context row must be an object")
        trigger_id = context.get("trigger_id")
        if not isinstance(trigger_id, str) or trigger_id not in index:
            raise ConstructFirstBundleError(f"unknown construct-first trigger: {trigger_id!r}")
        state = context.get("context_present", context.get("triggered"))
        if not isinstance(state, bool):
            raise ConstructFirstBundleError(
                f"derived context must contain boolean context_present or triggered: {trigger_id}"
            )
        if not state:
            continue
        entry = index[trigger_id]
        line = entry["line"]
        candidates.append(
            {
                "line_id": line["coaching_line_id"],
                "trigger_id": trigger_id,
                "headline": line["headline"],
                "detail": line["detail"],
                "population_condition": line["population_condition"],
                "construct_ids": line["current_construct_ids"],
                "derived_context": context,
            }
        )
    return candidates


def replay_golden_fixtures(bundle: dict[str, Any]) -> dict[str, int]:
    """Verify delivery routing against every construct-first fixture oracle."""
    index = _trigger_index(bundle)
    positive = 0
    negative = 0
    for fixture in bundle["golden_fixtures"]:
        expected = fixture["expected_derived_output"]
        should_emit = _fixture_triggered(expected)
        trigger_id = fixture["trigger_id"]
        context = {"trigger_id": trigger_id, "context_present": should_emit}
        candidates = select_coaching_candidates(bundle, [context])
        if bool(candidates) != should_emit:
            raise ConstructFirstBundleError(f"fixture routing mismatch: {fixture.get('fixture_id')}")
        if should_emit:
            positive += 1
        else:
            negative += 1
        if trigger_id not in index:
            raise ConstructFirstBundleError(f"fixture trigger is not indexed: {trigger_id}")
    return {"positive_fixtures": positive, "no_trigger_fixtures": negative}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the construct-first coaching delivery contract")
    parser.add_argument("--data", type=Path, required=True, help="bundle data directory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    sub.add_parser("replay")
    select = sub.add_parser("select")
    select.add_argument("context_json", type=Path, help="JSON array of derived context rows")
    args = parser.parse_args()

    bundle = load_bundle(args.data)
    if args.command == "verify":
        print(json.dumps({"result": "pass", "lines": len(bundle["construct_first_lines"]), "triggers": len(bundle["construct_first_triggers"])}, ensure_ascii=False))
    elif args.command == "replay":
        print(json.dumps({"result": "pass", **replay_golden_fixtures(bundle)}, ensure_ascii=False))
    else:
        rows = json.loads(args.context_json.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise SystemExit("context_json must contain an array")
        print(json.dumps(select_coaching_candidates(bundle, rows), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
