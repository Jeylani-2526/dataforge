# Late & out-of-order injection for sensor_producer (M6W23T3).
# Off by default: every knob defaults to 0, so an unconfigured run behaves
# exactly as it did before this module existed.

import logging
import os
import random

log = logging.getLogger(__name__)

# The shared definition of "late". Same env var and default as fusion_engine.py,
# read here so T3 and T9 agree on the line instead of inferring it.
# Shift < this  -> tolerated disorder, the join still sees the record.
# Shift >= this -> watermark-boundary case, Spark is expected to drop it.
WATERMARK_DELAY_SECONDS = int(os.environ.get("WATERMARK_DELAY_SECONDS", "5"))
WATERMARK_DELAY_MS = WATERMARK_DELAY_SECONDS * 1000


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        raise ValueError(f"{name} must be a number, got {os.environ.get(name)!r}")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {os.environ.get(name)!r}")


class Injector:
    """Shifts a share of records back in event time, and releases a share out of
    order. Both are driven purely by env vars and both default to off."""

    def __init__(self):
        self.late_fraction = _env_float("SENSOR_LATE_FRACTION", 0.0)
        self.late_min_ms = _env_int("SENSOR_LATE_MIN_MS", 0)
        self.late_max_ms = _env_int("SENSOR_LATE_MAX_MS", 0)
        self.disorder_fraction = _env_float("SENSOR_DISORDER_FRACTION", 0.0)
        self.disorder_buffer = _env_int("SENSOR_DISORDER_BUFFER", 0)
        # An unusable seed must never stop the producer: it only matters when
        # injection is on, and Compose can hand this variable junk if a .env line
        # puts a comment after an empty value.
        seed_raw = os.environ.get("SENSOR_INJECTION_SEED", "").strip()
        self.bad_seed = None
        try:
            self.seed = int(seed_raw) if seed_raw else None
        except ValueError:
            self.seed = None
            self.bad_seed = seed_raw

        self._validate()

        # Private RNG. Using the global `random` would change the generated
        # sensor values as soon as injection is enabled, which would make an
        # injected run incomparable with an ordinary one.
        self._rng = random.Random(self.seed)

        self._buffer: list = []
        # Newest event time emitted per topic — a local model of the per-topic
        # watermark in prepare_sensor(). Lateness is measured against this, not
        # against wall clock (M6W23T4 finding).
        self._high_ts: dict = {}
        self.stats = {
            "total": 0,
            "shifted": 0,
            "reordered": 0,
            "on_time": 0,
            "late_tolerated": 0,
            "late_beyond_watermark": 0,
        }

    def _validate(self):
        for name, value in (
            ("SENSOR_LATE_FRACTION", self.late_fraction),
            ("SENSOR_DISORDER_FRACTION", self.disorder_fraction),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")

        if self.late_min_ms < 0 or self.late_max_ms < 0:
            raise ValueError("SENSOR_LATE_MIN_MS / SENSOR_LATE_MAX_MS must be >= 0")

        if self.late_min_ms > self.late_max_ms:
            raise ValueError(
                f"SENSOR_LATE_MIN_MS ({self.late_min_ms}) must not exceed "
                f"SENSOR_LATE_MAX_MS ({self.late_max_ms})"
            )

        # Silent no-ops are the trap worth failing on: a fraction set without a
        # magnitude looks configured but injects nothing.
        if self.late_fraction > 0 and self.late_max_ms == 0:
            raise ValueError(
                "SENSOR_LATE_FRACTION is set but SENSOR_LATE_MAX_MS is 0 — "
                "no lateness would be injected. Set SENSOR_LATE_MAX_MS."
            )

        if self.disorder_fraction > 0 and self.disorder_buffer < 2:
            raise ValueError(
                "SENSOR_DISORDER_FRACTION is set but SENSOR_DISORDER_BUFFER is "
                f"{self.disorder_buffer} — a buffer of at least 2 is needed to "
                "reorder anything."
            )

        # M6W23T4: a config that shifts every record by a near-uniform amount
        # moves the whole stream, watermark included, and drops nothing. Drops
        # need either on-time records to hold the watermark up (fraction < 1.0)
        # or a shift spread wider than the watermark delay.
        spread = self.late_max_ms - self.late_min_ms
        if (
            self.late_fraction >= 1.0
            and self.late_max_ms > 0
            and spread < WATERMARK_DELAY_MS
        ):
            log.warning(
                "SENSOR_LATE_FRACTION=1.0 with a %d ms spread shifts the whole "
                "stream uniformly — the watermark shifts with it and NO records "
                "will be dropped. Use a fraction below 1.0 to hold the watermark "
                "current, or widen the shift range beyond %d ms.",
                spread,
                WATERMARK_DELAY_MS,
            )

    @property
    def enabled(self) -> bool:
        return self.late_fraction > 0 or self.disorder_fraction > 0

    def describe(self) -> str:
        if self.bad_seed is not None:
            log.warning(
                "SENSOR_INJECTION_SEED=%r is not an integer — ignoring it and "
                "running unseeded. Check for a trailing comment on an empty "
                "value in .env.",
                self.bad_seed[:60],
            )
        if not self.enabled:
            return "Injection mode OFF — records published unmodified."
        return (
            f"Injection mode ON — late_fraction={self.late_fraction} "
            f"delay={self.late_min_ms}-{self.late_max_ms}ms "
            f"(watermark line {WATERMARK_DELAY_MS}ms) | "
            f"disorder_fraction={self.disorder_fraction} "
            f"buffer={self.disorder_buffer} | seed={self.seed}"
        )

    def apply(self, record: dict) -> list:
        """Returns a list of (record, kafka_timestamp_ms) ready to publish.

        kafka_timestamp_ms is None when the record was not shifted, so the
        producer omits the argument and Kafka assigns the current time exactly
        as it does today. May return zero items (record buffered) or several
        (buffer released)."""
        self.stats["total"] += 1

        if not self.enabled:
            return [(record, None)]

        kafka_ts = None

        if self._rng.random() < self.late_fraction:
            shift = self._rng.randint(self.late_min_ms, self.late_max_ms)
            if shift > 0:
                record["timestamp_ms"] -= shift
                kafka_ts = record["timestamp_ms"]
                self.stats["shifted"] += 1

        if self.disorder_fraction > 0 and self._rng.random() < self.disorder_fraction:
            self._buffer.append((record, kafka_ts))
            if len(self._buffer) >= self.disorder_buffer:
                return self._release()
            return []

        self._classify(record)
        return [(record, kafka_ts)]

    def _classify(self, record: dict):
        """Scores a record against a local model of its topic's watermark.

        Spark drops a record when it falls WATERMARK_DELAY_MS or more behind the
        newest event time already seen on that topic. Measuring the shift alone
        is wrong: a uniform shift moves the high-water mark with it and nothing
        is late (M6W23T4 Phase C). Classification happens at emission, so a
        record held in the reorder buffer is scored against the watermark at the
        moment it is actually released."""
        stype = record["sensor_type"]
        ts = record["timestamp_ms"]
        high = self._high_ts.get(stype)

        if high is None or ts > high:
            self._high_ts[stype] = ts
            self.stats["on_time"] += 1
        elif high - ts >= WATERMARK_DELAY_MS:
            self.stats["late_beyond_watermark"] += 1
        else:
            self.stats["late_tolerated"] += 1

    def _release(self) -> list:
        self._rng.shuffle(self._buffer)
        released, self._buffer = self._buffer, []
        self.stats["reordered"] += len(released)
        for rec, _ in released:
            self._classify(rec)
        return released

    def flush(self) -> list:
        """Drains the reorder buffer at shutdown so held records are not lost."""
        return self._release() if self._buffer else []

    def log_stats(self):
        if not self.enabled:
            return
        s = self.stats
        log.info(
            "Injection stats — total=%d shifted=%d reordered=%d | vs topic "
            "watermark: on_time=%d late_tolerated=%d late_beyond_watermark=%d "
            "(scored against the CONFIGURED %dms line; M6W23T4 measured the "
            "EFFECTIVE watermark at 12-13s, so real drops are far fewer)",
            s["total"],
            s["shifted"],
            s["reordered"],
            s["on_time"],
            s["late_tolerated"],
            s["late_beyond_watermark"],
            WATERMARK_DELAY_MS,
        )
