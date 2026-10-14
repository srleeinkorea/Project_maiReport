# maiReport construct-first coaching delivery maireport-construct-first-coaching-kdb-v1.1

This bundle contains only the server KDB's construct-first operational-ready coaching lines.
Goal actions, user-question proxies, ranking, cadence, deduplication, permissions, and delivery
remain independent operating-product concerns and are intentionally not readiness prerequisites here.

The runner accepts a derived trigger-context row and resolves it to the approved coaching copy.
It does not infer disease, diagnosis, recovery, safety clearance, or a medical state from a device
signal. Provider parsing and signal derivation remain service-owned implementations described by
the evaluator contract, trigger packet, source-field contract, output contract, and golden fixtures.

`data/evaluator_contracts.json` is the normative compiled evaluator surface. It combines the
provider raw-field allowlist, normalized output, ordered preprocessing, trigger predicate,
external-context boundary, no-emit/null-reason rules, and KDB-versus-operating-product boundary
for every trigger path. An implementation must not substitute an unlisted provider field or invent
missing-data behavior.

The executable sample path is:

```bash
python3 provider_reference_adapter.py --data data   trigger_general_short_activity_bout_keep_moving_construct_first_v2   examples/raw_health_connect_activity_intensity.json > /tmp/normalized.json
python3 construct_first_reference_evaluator.py --data data evaluate   trigger_general_short_activity_bout_keep_moving_construct_first_v2 /tmp/normalized.json
python3 provider_reference_adapter.py --data data   trigger_general_recorded_exercise_timing_keep_flexible_construct_first_v2   examples/raw_apple_hkworkout_timing.json > /tmp/apple-normalized.json
python3 provider_reference_adapter.py --data data   trigger_general_recorded_exercise_timing_keep_flexible_construct_first_v2   examples/raw_samsung_exercise_timing.json > /tmp/samsung-normalized.json
python3 construct_first_reference_evaluator.py --data data replay
```

`provider_reference_adapter.py` contains raw-provider samples for Health Connect
`ActivityIntensityRecord`, Apple Health `HKWorkout`, and Samsung Health
`com.samsung.health.exercise`. It enforces provider-specific source identity, timestamp/duration
parsing, duplicate handling, coverage and explicit external-context separation, then maps the
Apple and Samsung exercise-time examples to the same normalized session-time input. An unsupported
raw shape fails closed rather than silently substituting a nearby field.
`construct_first_reference_evaluator.py` is the executable reference for all current trigger IDs
and operates on the adapter's normalized input contract. These scripts are sample implementation
code, not production ingestion or delivery. The small `sample_validation/` folder contains only the
optional compatibility helper imported by the bundled legacy evaluator; it is included so the
bundle has no import dependency on the maiReport repository.

## Verify

```bash
python3 construct_first_runner.py --data data verify
python3 construct_first_runner.py --data data replay
python3 construct_first_runner.py --data data select examples/derived_context.json
```

The bundle is a versioned snapshot. Additive line/trigger additions must ship in a new
backward-compatible bundle release; changes to existing IDs or trigger meaning require v2.
The operating product still owns actual activation and delivery.

## Release metadata

Release delta metadata is maintained outside this operating delivery bundle. The ZIP contains the
effective current contracts only; delta history is not required by the runtime evaluator and is
kept in the repository release metadata for the next export review.

## KDB runtime dependency map

data/runtime_dependency_map.json is the implementation handoff for deciding whether the
operating product should query KDB directly or materialize an operating database projection.
It identifies the authoritative KDB object, runtime role, stable keys, required columns, selection
SQL, join keys, and corresponding bundle file for every artifact. It also explicitly separates
provider raw records and derived context rows, which are operating-product inputs and are not stored
in KDB.

The five runtime-required KDB artifacts are the line catalog, trigger export, trigger packet,
source-field contract, and output contract. Golden fixtures are release-validation-only. The
evaluator_contracts.json file is a compiled projection of those source objects and may be used
instead of reading the distributed contracts at runtime. The map documents direct-KDB,
operating-database-projection, and delivery-bundle choices without selecting one for the operating
product.

For a direct-KDB proof of concept, install psycopg and provide explicit server identity settings:

python3 construct_first_kdb_reader.py --data data verify

This command performs a read-only release-gate check and verifies that the five runtime-required
objects have matching trigger keys. It does not read provider user data, write KDB rows, or implement
service delivery. For an operating-database projection, use the same map as the extraction contract.
