import json
from dataclasses import dataclass

from counters.codec import pack_counter_rows, unpack_counter_rows
from counters.revisions import CounterRows
from routes.endpoints import RoutePair
from settlement.balance import RouteInterval, route_intervals
from settlement.evidence import AllocationEvidence


@dataclass(frozen=True, slots=True)
class ProjectedAllocation:
    day: str
    counter_revision: str
    route_revision: str
    lines: CounterRows
    pool_names: tuple[str, ...]
    pool_total: int
    intervals: tuple[RouteInterval, ...]

    @property
    def pools(self) -> tuple[tuple[str, None], ...]:
        return tuple((name, None) for name in self.pool_names)

    @property
    def open_routes(self) -> tuple[RoutePair, ...]:
        return tuple((line, pool) for line, pool, _, _ in self.intervals)

    @property
    def totals(self) -> tuple[int, int]:
        return sum(liters for _, liters in self.lines), self.pool_total


@dataclass(frozen=True, slots=True)
class SealedBatch:
    artifact_id: int
    evidence: AllocationEvidence | ProjectedAllocation


def encode_sealed_batch(batch: SealedBatch) -> str:
    evidence = batch.evidence
    if isinstance(evidence, AllocationEvidence):
        projection = ProjectedAllocation(
            evidence.day, evidence.counter_revision, evidence.route_revision,
            evidence.lines, tuple(name for name, _ in evidence.pools),
            evidence.totals[1], route_intervals(evidence),
        )
    else:
        projection = evidence
    return json.dumps({
        "artifact_id": batch.artifact_id,
        "day": projection.day,
        "counter_revision": projection.counter_revision,
        "route_revision": projection.route_revision,
        "lines": pack_counter_rows(projection.lines),
        "pool_names": projection.pool_names,
        "pool_total": hex(projection.pool_total),
        "route_intervals": [
            (line, pool, hex(lower), hex(upper))
            for line, pool, lower, upper in projection.intervals
        ],
    }, separators=(",", ":"))


def decode_sealed_batch(payload: str) -> SealedBatch:
    data = json.loads(payload)
    day, counter_revision, route_revision = data["day"], data["counter_revision"], data["route_revision"]
    lines = unpack_counter_rows(data["lines"])
    if "route_intervals" in data:
        evidence = ProjectedAllocation(
            day, counter_revision, route_revision, lines,
            tuple(data["pool_names"]), int(data["pool_total"], 16),
            tuple((line, pool, int(low, 16), int(high, 16))
                  for line, pool, low, high in data["route_intervals"]),
        )
    else:
        evidence = AllocationEvidence(
            day, counter_revision, route_revision, lines,
            unpack_counter_rows(data["pools"]),
            tuple((line, pool) for line, pool in data["open_routes"]),
        )
    return SealedBatch(data["artifact_id"], evidence)
