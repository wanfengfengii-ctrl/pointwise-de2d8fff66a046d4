from collections.abc import Iterable

from accounts.queries import normalize_query_routes
from accounts.results import zero_bounds
from archive.lookup import ArchiveConsistencyError, get_sealed_batch
from archive.store import ArchiveStore
from routes.endpoints import RoutePair
from settlement.balance import route_intervals
from settlement.evidence import AllocationEvidence


def bounds(archive: ArchiveStore, artifact_id: int, routes: Iterable[RoutePair]) -> list[int]:
    batch = get_sealed_batch(archive, artifact_id)
    selected = normalize_query_routes(batch, routes)
    evidence = batch.evidence
    issued, received = evidence.totals
    if issued != received:
        raise ArchiveConsistencyError(f"unbalanced sealed evidence for {artifact_id}")
    if not selected or issued == 0:
        return zero_bounds()

    intervals = route_intervals(evidence) if isinstance(evidence, AllocationEvidence) else evidence.intervals
    lower, upper = 0, 0
    for line, pool, edge_lower, edge_upper in intervals:
        if (line, pool) in selected:
            lower += edge_lower
            upper += edge_upper
    return [lower, min(upper, issued)]
