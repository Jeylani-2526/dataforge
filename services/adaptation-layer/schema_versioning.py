"""
DataForge — Schema-Versioning Enforcement
Task: M4W14T3
Owner: Abdullah

Turns schema_evolution_policy.md into running pipeline code, via two
checks kept separate because they catch different failures:

  1. VERSION POPULATION — every record's schema_version is stamped from
     CURRENT_SCHEMA_VERSIONS (the registry, synced with
     schema_evolution_policy.md Section 4 / the Migration Log), not
     trusted verbatim from upstream. A mismatch is logged as version
     drift — an upstream producer writing a value that no longer
     matches the locked schema.
  2. ROUND-TRIP CHECK — every record is serialized then deserialized
     against the locked .avsc schema (same technique as
     schemas/validate_schema.py) before being written. A record that
     fails is real data loss, counted rather than silently dropped.

Deliberately separate from staging validation — a later, independent
check at the adaptation layer rather than trusting an earlier stage.
"""

import logging
import struct
from dataclasses import dataclass, field
from io import BytesIO

from fastavro import schemaless_reader, schemaless_writer

log = logging.getLogger(__name__)

# ── Authoritative version registry ───────────────────────────────────────
# Mirrors schema_evolution_policy.md Section 4 ("Current topics and their
# schemas" table) and the Migration Log. UPDATE THIS DICT as part of
# Section 5 Step 3 ("Version bump") whenever a schema change is committed
# — this is now a required step in the post-lock change process, not
# optional. As of M4W14, all three schemas are at 1.0 with no post-lock
# version bumps yet (only the 14 July doc-only correction, which per
# Section 2 does not bump schema_version).
CURRENT_SCHEMA_VERSIONS = {
    "alice_event": "1.0",
    "sensor_event": "1.0",
    "fused_event": "1.0",
}


@dataclass
class EnforcementResult:
    """Outcome of running both checks over one batch of records."""
    stream_name: str
    total: int = 0
    version_drift: list = field(default_factory=list)   # records whose incoming schema_version != registry
    round_trip_failed: list = field(default_factory=list)  # records that failed serialize/deserialize
    valid_records: list = field(default_factory=list)   # records that passed both checks, schema_version stamped
    # Per-record round-trip timing in ms (M4W15T4). Empty unless
    # collect_timings=True was passed to enforce() — other callers unaffected.
    record_latencies_ms: list = field(default_factory=list)

    @property
    def passed(self) -> int:
        return len(self.valid_records)

    @property
    def rejected(self) -> int:
        return len(self.version_drift) + len(self.round_trip_failed)

    @property
    def data_loss_pct(self) -> float:
        return 0.0 if self.total == 0 else round(100.0 * self.rejected / self.total, 4)

    def log_summary(self):
        log.info(
            "[%s] enforcement: total=%d  passed=%d  version_drift=%d  "
            "round_trip_failed=%d  data_loss_pct=%.4f%%",
            self.stream_name, self.total, self.passed,
            len(self.version_drift), len(self.round_trip_failed), self.data_loss_pct,
        )
        for rec in self.version_drift:
            log.warning(
                "[%s] VERSION DRIFT event_id=%s incoming_schema_version=%s expected=%s",
                self.stream_name, rec.get("event_id", "?"),
                rec.get("schema_version"), CURRENT_SCHEMA_VERSIONS.get(self.stream_name),
            )
        for rec, err in self.round_trip_failed:
            log.warning(
                "[%s] ROUND-TRIP FAILURE event_id=%s error=%s",
                self.stream_name, rec.get("event_id", "?"), err,
            )


# ── Check 1: schema_version population ───────────────────────────────────

def populate_schema_version(records: list, stream_name: str) -> tuple:
    """
    Stamps every record's schema_version from the registry. Records whose
    incoming value disagreed with the registry are returned separately as
    drift events (still logged, not silently corrected and forgotten) —
    they are NOT included in the returned `stamped` list, since a version
    mismatch is exactly the class of undocumented-change risk this policy
    exists to catch, and should be reviewed rather than auto-passed.

    Returns: (stamped_records, drift_records)
    """
    current_version = CURRENT_SCHEMA_VERSIONS.get(stream_name)
    if current_version is None:
        raise ValueError(
            f"Unknown stream_name '{stream_name}' — not in CURRENT_SCHEMA_VERSIONS "
            f"registry. Add it (see schema_evolution_policy.md Section 4) before proceeding."
        )

    stamped, drift = [], []
    for rec in records:
        incoming_version = rec.get("schema_version")
        if incoming_version is not None and incoming_version != current_version:
            drift.append(rec)
            continue
        rec = dict(rec)
        rec["schema_version"] = current_version
        stamped.append(rec)

    return stamped, drift


# ── Check 2: automated round-trip check ──────────────────────────────────

def _avro_field_types(parsed_schema: dict) -> dict:
    """Maps field name -> Avro primitive type string, resolving ["null", T] unions."""
    types = {}
    for f in parsed_schema.get("fields", []):
        t = f["type"]
        if isinstance(t, list):
            non_null = [x for x in t if x != "null"]
            t = non_null[0] if non_null else "null"
        if isinstance(t, dict):
            t = t.get("type", t)
        types[f["name"]] = t
    return types


def _float32_round(value):
    """Rounds a Python float to float32 precision, matching what fastavro
    does on write for an Avro `float` field. Used to normalize the
    *expected* value before comparison — not a workaround, but the
    correct baseline: a field declared `float` in the schema is only
    ever supposed to carry float32 precision, per the ALICE schema's own
    fused_event_schema_v1.avsc doc note on data_loss_pct."""
    return struct.unpack(">f", struct.pack(">f", value))[0]


def round_trip_check(records: list, parsed_schema: dict, collect_timings: bool = False) -> tuple:
    """
    Serializes then immediately deserializes every record against the
    given (already fastavro.parse_schema()'d) schema, using the same
    schemaless_writer/schemaless_reader pair schemas/validate_schema.py
    uses for manual validation. A record whose round-tripped value
    doesn't equal the original is a real data-loss event.

    IMPORTANT — precision-aware comparison: fields declared as Avro
    `float` (32-bit) in the schema are expected to lose precision
    relative to a Python double on round-trip; that is the schema
    working as designed, not data loss (see alice_event_schema_v1.avsc /
    fused_event_schema_v1.avsc field docs — momentum, energy, and
    data_loss_pct are all declared `float` for exactly this reason).
    The *expected* value is normalized to float32 precision for any
    field the schema declares as `float` before comparing, so only
    genuine mismatches — wrong values, dropped fields, type errors —
    are flagged, not precision the schema itself sanctions.

    collect_timings (M4W15T4, default False — existing callers unaffected):
    when True, times each record's serialize+deserialize+compare cycle
    individually with time.perf_counter() and returns those latencies in
    milliseconds as a third list. This is the per-record unit of work
    the adaptation layer actually performs, so it's used as the latency
    basis for the M4W15T4 full-volume throughput/p95 report — there's no
    live event stream yet (that's M5's Kafka/Structured Streaming work),
    so a true end-to-end event latency doesn't exist to measure this
    milestone; per-record processing time is the fair proxy available
    now, and is reported as such (not mislabeled as network/streaming
    latency).

    Returns: (passed_records, failed_records_with_errors) when
    collect_timings=False (unchanged from before this parameter existed).
    Returns: (passed_records, failed_records_with_errors, latencies_ms)
    when collect_timings=True.
    """
    import time

    field_types = _avro_field_types(parsed_schema)
    passed, failed = [], []
    latencies_ms = []

    for rec in records:
        start = time.perf_counter() if collect_timings else None
        try:
            buffer = BytesIO()
            schemaless_writer(buffer, parsed_schema, rec)
            buffer.seek(0)
            decoded = schemaless_reader(buffer, parsed_schema)

            expected = dict(rec)
            for key, value in expected.items():
                if field_types.get(key) == "float" and isinstance(value, (int, float)) and value is not None:
                    expected[key] = _float32_round(value)

            if decoded == expected:
                passed.append(rec)
            else:
                failed.append((rec, f"round-trip mismatch: decoded={decoded} != expected={expected}"))
        except Exception as exc:
            failed.append((rec, str(exc)))
        finally:
            if collect_timings:
                latencies_ms.append((time.perf_counter() - start) * 1000.0)

    if collect_timings:
        return passed, failed, latencies_ms
    return passed, failed


# ── Combined enforcement entry point ─────────────────────────────────────

def enforce(
    records: list, stream_name: str, parsed_schema: dict, collect_timings: bool = False
) -> EnforcementResult:
    """
    Runs both checks in sequence: version population/drift check first
    (cheap, catches upstream producer bugs), then round-trip check on the
    survivors (catches serialization-level data loss). This ordering
    means a version-drift record never gets a round-trip check run on
    it — it's already rejected for a different reason, so we don't spend
    the extra serialize/deserialize cycle on it.

    collect_timings (M4W15T4, default False): forwarded to
    round_trip_check(); when True, result.record_latencies_ms is
    populated. Default keeps every existing caller (the adaptation job's
    normal runs, and M4W15T3's round-trip test suite) byte-for-byte
    unaffected.
    """
    result = EnforcementResult(stream_name=stream_name, total=len(records))

    stamped, drift = populate_schema_version(records, stream_name)
    result.version_drift = drift

    if collect_timings:
        passed, failed, latencies_ms = round_trip_check(
            stamped, parsed_schema, collect_timings=True
        )
        result.record_latencies_ms = latencies_ms
    else:
        passed, failed = round_trip_check(stamped, parsed_schema)

    result.round_trip_failed = failed
    result.valid_records = passed

    result.log_summary()
    return result
