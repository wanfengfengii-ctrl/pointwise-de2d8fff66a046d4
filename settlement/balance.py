from accounts.objectives import build_group_objective
from routes.endpoints import RoutePair
from settlement.evidence import AllocationEvidence
from settlement.flow import build_network, maximum_flow, min_cost_flow


def is_feasible(evidence: AllocationEvidence) -> bool:
    """A complete integer allocation exists iff max flow covers both totals.

    Line emissions and pool receipts are node capacities of a bipartite
    network, with open routes as the only edges.  Equal grand totals alone are
    not sufficient: every line subset must be able to reach enough pool
    capacity, which the max-flow cut check enforces exactly.
    """
    issued, received = evidence.totals
    if issued != received:
        return False
    if issued == 0:
        # Zero liters are covered by the all-zero flow on any roster.
        return True
    network, source, sink, total = build_network(evidence)
    return maximum_flow(network, source, sink) == total


def group_flow_bounds(
    evidence: AllocationEvidence, selected: frozenset[RoutePair],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Reachable integer min/max liters carried jointly by the selected routes.

    Returns ``((min_sent, min_cost), (max_sent, negated_max_cost))`` where each
    solver run pushed the full batch total, mirroring the min/max cost flow
    contract consumed by ``accounts.results.make_bounds_result``.  Both extremes
    are taken over complete feasible allocations only: every endpoint keeps its
    required count instead of selected-route flow being optimized in isolation.
    """
    total = evidence.totals[0]
    if not selected or total == 0:
        # Empty groups, closed-only groups and all-zero batches carry no flow.
        return (total, 0), (total, 0)

    objective = build_group_objective(selected)
    minimum_network, min_source, min_sink, _ = build_network(
        evidence, objective.costs(maximize=False),
    )
    minimum = min_cost_flow(minimum_network, min_source, min_sink, total)

    maximum_network, max_source, max_sink, _ = build_network(
        evidence, objective.costs(maximize=True),
    )
    maximum = min_cost_flow(maximum_network, max_source, max_sink, total)
    return minimum, maximum
