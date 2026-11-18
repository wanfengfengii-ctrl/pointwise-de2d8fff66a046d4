from archive.publication import publish_batch
from archive.store import ArchiveStore, BeforeCommit
from counters.ledger import CounterLedger
from routes.catalog import RouteCatalog
from settlement.balance import is_feasible
from settlement.evidence import build_allocation_evidence
from settlement.failures import InfeasibleBatchError
from settlement.sources import bind_sources


def certify(
    counters: CounterLedger,
    routes: RouteCatalog,
    archive: ArchiveStore,
    day: str,
    counter_revision: str,
    route_revision: str,
    *,
    before_commit: BeforeCommit | None = None,
) -> int:
    sources = bind_sources(counters, routes, day, counter_revision, route_revision)
    evidence = build_allocation_evidence(sources)
    if not is_feasible(evidence):
        raise InfeasibleBatchError(
            f'open routes cannot carry all counts for {day}/{counter_revision}/{route_revision}'
        )
    return publish_batch(archive, evidence, before_commit)
