from routes.endpoints import RoutePair
from settlement.evidence import AllocationEvidence

RouteInterval = tuple[str, str, int, int]


def _route_capacity(evidence: AllocationEvidence) -> dict[RoutePair, int]:
    lines, pools = dict(evidence.lines), dict(evidence.pools)
    return {pair: min(lines[pair[0]], pools[pair[1]]) for pair in evidence.open_routes}


def is_feasible(evidence: AllocationEvidence) -> bool:
    issued, received = evidence.totals
    if issued != received:
        return False
    outbound = dict.fromkeys(dict(evidence.lines), 0)
    for (line, _), capacity in _route_capacity(evidence).items():
        outbound[line] += capacity
    return all(outbound[line] >= liters for line, liters in evidence.lines)


def route_intervals(evidence: AllocationEvidence) -> tuple[RouteInterval, ...]:
    lines, pools = dict(evidence.lines), dict(evidence.pools)
    outbound = dict.fromkeys(lines, 0)
    inbound = dict.fromkeys(pools, 0)
    capacities = _route_capacity(evidence)
    for (line, pool), capacity in capacities.items():
        outbound[line] += capacity
        inbound[pool] += capacity

    result = []
    for (line, pool), capacity in capacities.items():
        needed_from_line = lines[line] - (outbound[line] - capacity)
        needed_for_pool = pools[pool] - (inbound[pool] - capacity)
        result.append((line, pool, max(0, needed_from_line, needed_for_pool), capacity))
    return tuple(result)
