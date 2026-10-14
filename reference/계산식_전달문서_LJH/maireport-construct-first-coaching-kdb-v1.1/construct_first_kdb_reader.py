#!/usr/bin/env python3
"""Optional read-only direct-KDB reader for the construct-first handoff."""
from __future__ import annotations

import argparse
import json
import os
from ipaddress import ip_address, ip_interface
from pathlib import Path


_BUNDLE_DATA = Path(__file__).resolve().parent / "data"
DATA = (
    _BUNDLE_DATA
    if (_BUNDLE_DATA / "runtime_dependency_map.json").is_file()
    else Path(__file__).resolve().parents[2] / "delivery/maireport-construct-first-coaching-kdb-v1.1/data"
)


def connection_config(environ=None):
    environ = os.environ if environ is None else environ
    if environ.get("KNOWLEDGE_DB_DSN"):
        return environ["KNOWLEDGE_DB_DSN"], None
    required = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER")
    missing = [key for key in required if not environ.get(key)]
    if missing:
        raise RuntimeError(
            "Direct KDB mode requires KNOWLEDGE_DB_DSN or explicit server PG settings; missing: "
            + ", ".join(missing)
        )
    return None, {
        "host": environ["PGHOST"],
        "port": int(environ["PGPORT"]),
        "dbname": environ["PGDATABASE"],
        "user": environ["PGUSER"],
        "password": environ.get("PGPASSWORD", ""),
    }


def validate_server_identity(server_address, database, environ=None):
    environ = os.environ if environ is None else environ
    expected_database = environ.get("KNOWLEDGE_DB_NAME", "health_knowledge")
    expected_address = environ.get("KNOWLEDGE_DB_EXPECTED_SERVER_ADDR")
    if expected_address is None:
        host = environ.get("PGHOST", "")
        try:
            expected_address = str(ip_address(host))
        except ValueError as exc:
            raise RuntimeError(
                "Set KNOWLEDGE_DB_EXPECTED_SERVER_ADDR when PGHOST is not a literal server IP"
            ) from exc
    try:
        actual_ip = ip_interface(server_address).ip
        expected_ip = ip_address(expected_address)
    except ValueError as exc:
        raise RuntimeError("KDB server identity must use literal IP addresses") from exc
    if actual_ip.is_loopback or expected_ip.is_loopback:
        raise RuntimeError("Localhost is not an allowed canonical KDB server")
    if actual_ip != expected_ip or database != expected_database:
        raise RuntimeError(
            f"Unexpected KDB target: {actual_ip} / {database}; "
            f"expected {expected_ip} / {expected_database}"
        )


def _load_dependency_map(data_dir: Path) -> dict:
    path = data_dir / "runtime_dependency_map.json"
    return json.loads(path.read_text(encoding="utf-8"))


class ConstructFirstKdbReader:
    """Read the declared construct-first KDB objects without writing rows."""

    def __init__(self, data_dir: Path = DATA):
        dsn, kwargs = connection_config()
        try:
            import psycopg
            self.conn = psycopg.connect(dsn) if dsn else psycopg.connect(**kwargs)
        except ImportError:
            try:
                import psycopg2
            except ImportError as exc:
                raise RuntimeError(
                    "Install psycopg[binary] or psycopg2-binary for direct KDB mode"
                ) from exc
            self.conn = psycopg2.connect(dsn) if dsn else psycopg2.connect(**kwargs)
        with self.conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT inet_server_addr()::text, current_database()")
            self.server_address, self.database = cur.fetchone()
            if self.server_address is None:
                raise RuntimeError("A local socket is not an allowed canonical KDB server")
            validate_server_identity(self.server_address, self.database)
        self.data_dir = data_dir
        self.dependency_map = _load_dependency_map(data_dir)
        self._cache = {}

    def assert_release_gate(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT mai_kdb_assert_authoring_release_gate()")

    def read(self, artifact: str):
        if artifact in self._cache:
            return self._cache[artifact]
        objects = {
            row["artifact"]: row
            for row in self.dependency_map["kdb_objects"]
            if row.get("runtime_required") or row.get("validation_only")
        }
        if artifact not in objects:
            raise ValueError(f"Artifact is not declared in runtime dependency map: {artifact}")
        sql = objects[artifact]["selection_sql"]
        with self.conn.cursor() as cur:
            cur.execute(sql)
            columns = [description[0] for description in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        self._cache[artifact] = rows
        return rows

    def verify_contract_surface(self):
        self.assert_release_gate()
        rows = {
            artifact: len(self.read(artifact))
            for artifact in (
                "construct_first_lines",
                "construct_first_triggers",
                "trigger_packets",
                "source_fields",
                "output_contracts",
            )
        }
        trigger_keys = {
            (row["line_id"], row["trigger_id"])
            for row in self.read("construct_first_triggers")
        }
        for artifact in ("trigger_packets", "source_fields", "output_contracts"):
            keys = {
                (row["line_id"], row["trigger_id"])
                for row in self.read(artifact)
            }
            if keys != trigger_keys:
                raise RuntimeError(f"{artifact} does not exactly cover trigger paths")
        return {
            "result": "pass",
            "server_address": self.server_address,
            "database": self.database,
            "rows": rows,
            "runtime_kdb_artifacts": 5,
            "golden_fixtures_runtime_required": False,
        }

    def close(self):
        self.conn.rollback()
        self.conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("command", choices=("verify", "count"))
    parser.add_argument("artifact", nargs="?")
    args = parser.parse_args()

    reader = ConstructFirstKdbReader(args.data)
    try:
        if args.command == "verify":
            print(json.dumps(reader.verify_contract_surface(), ensure_ascii=False))
        else:
            if not args.artifact:
                raise SystemExit("count requires an artifact name")
            print(json.dumps({
                "artifact": args.artifact,
                "rows": len(reader.read(args.artifact)),
            }, ensure_ascii=False))
    finally:
        reader.close()


if __name__ == "__main__":
    main()
