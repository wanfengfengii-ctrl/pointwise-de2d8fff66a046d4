import json
from dataclasses import dataclass

from counters.codec import pack_counter_rows, unpack_counter_rows
from settlement.evidence import AllocationEvidence


@dataclass(frozen=True, slots=True)
class SealedBatch:
    artifact_id: int
    evidence: AllocationEvidence


def encode_sealed_batch(batch: SealedBatch) -> str:
    evidence = batch.evidence
    return json.dumps({
        "artifact_id": batch.artifact_id,
        "day": evidence.day,
        "counter_revision": evidence.counter_revision,
        "route_revision": evidence.route_revision,
        # Per-endpoint counts of both sides and the open routes are part of
        # the sealed evidence: offline reopen must reconstruct the exact batch
        # without consulting the source ledgers.
        "lines": pack_counter_rows(evidence.lines),
        "pools": pack_counter_rows(evidence.pools),
        "open_routes": [list(route) for route in evidence.open_routes],
    }, separators=(",", ":"))


def decode_sealed_batch(payload: str) -> SealedBatch:
    data = json.loads(payload)
    try:
        if "open_routes" not in data or "pools" not in data:
            # Legacy projection payloads discarded per-pool counts, so the
            # two-side evidence can no longer be reconstructed or audited.
            raise KeyError("pools" if "pools" not in data else "open_routes")
        evidence = AllocationEvidence(
            data["day"], data["counter_revision"], data["route_revision"],
            unpack_counter_rows(data["lines"]),
            unpack_counter_rows(data["pools"]),
            tuple(
                (line, pool) for line, pool in data["open_routes"]
            ),
        )
    except KeyError as error:
        raise ValueError(f'sealed payload is missing {error.args[0]!r}') from error
    return SealedBatch(data["artifact_id"], evidence)
