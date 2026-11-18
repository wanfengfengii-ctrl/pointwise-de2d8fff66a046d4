from collections.abc import Iterable

from accounts.queries import normalize_query_routes
from accounts.results import make_bounds_result, zero_bounds
from archive.lookup import ArchiveConsistencyError, get_sealed_batch
from archive.store import ArchiveStore
from routes.endpoints import RoutePair
from settlement.balance import group_flow_bounds
from settlement.evidence import AllocationEvidence


def bounds(archive: ArchiveStore, artifact_id: int, routes: Iterable[RoutePair]) -> list[int]:
    batch = get_sealed_batch(archive, artifact_id)
    selected = normalize_query_routes(batch, routes)
    evidence = batch.evidence
    if not isinstance(evidence, AllocationEvidence):
        raise ArchiveConsistencyError(f'sealed artifact {artifact_id} has no auditable evidence')
    issued, received = evidence.totals
    if issued != received:
        raise ArchiveConsistencyError(f"unbalanced sealed evidence for {artifact_id}")
    if not selected or issued == 0:
        # Empty groups, closed-only groups and all-zero batches have no flow.
        return zero_bounds()
    minimum, maximum = group_flow_bounds(evidence, selected)
    return make_bounds_result(issued, minimum, maximum)
