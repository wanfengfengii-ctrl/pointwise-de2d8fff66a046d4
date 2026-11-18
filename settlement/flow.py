"""Exact integer flow primitives for the bipartite line/pool allocation.

The sealed network is a transportation problem:

    source -> line nodes   capacity = reported line liters
    line   -> pool nodes   capacity = total liters, one edge per open route
    pool   -> sink         capacity = reported pool liters

All capacities and costs are ordinary Python integers, so the solver keeps
exact results even for counts beyond SQLite's signed integer range.  Runtime
depends on the (small) roster size, not on the magnitude of the counts.
"""

from collections import deque
from collections.abc import Mapping

from routes.endpoints import RoutePair
from settlement.evidence import AllocationEvidence


class _Edge:
    __slots__ = ('to', 'rev', 'capacity', 'cost')

    def __init__(self, to: int, rev: int, capacity: int, cost: int):
        self.to = to
        self.rev = rev
        self.capacity = capacity
        self.cost = cost


class FlowNetwork:
    def __init__(self) -> None:
        self._adjacency: list[list[_Edge]] = []

    def add_node(self) -> int:
        self._adjacency.append([])
        return len(self._adjacency) - 1

    def add_edge(self, u: int, v: int, capacity: int, cost: int = 0) -> None:
        forward = _Edge(v, len(self._adjacency[v]), capacity, cost)
        backward = _Edge(u, len(self._adjacency[u]), 0, -cost)
        self._adjacency[u].append(forward)
        self._adjacency[v].append(backward)

    @property
    def adjacency(self) -> list[list[_Edge]]:
        return self._adjacency


NetworkView = tuple[FlowNetwork, int, int, int]


def build_network(
    evidence: AllocationEvidence,
    route_costs: Mapping[RoutePair, int] | None = None,
) -> NetworkView:
    network = FlowNetwork()
    source = network.add_node()
    sink = network.add_node()
    line_nodes = {name: network.add_node() for name, _ in evidence.lines}
    pool_nodes = {name: network.add_node() for name, _ in evidence.pools}
    total = sum(liters for _, liters in evidence.lines)

    for name, liters in evidence.lines:
        network.add_edge(source, line_nodes[name], liters)
    for name, liters in evidence.pools:
        network.add_edge(pool_nodes[name], sink, liters)
    # An open route can never carry more than the whole batch total.
    for line, pool in evidence.open_routes:
        cost = 0 if route_costs is None else route_costs.get((line, pool), 0)
        network.add_edge(line_nodes[line], pool_nodes[pool], total, cost)
    return network, source, sink, total


def maximum_flow(network: FlowNetwork, source: int, sink: int) -> int:
    """Dinic maximum flow; augmentations are count-magnitude independent."""
    graph = network.adjacency
    pushed_total = 0
    while True:
        level = [-1] * len(graph)
        level[source] = 0
        queue = deque([source])
        while queue:
            u = queue.popleft()
            for edge in graph[u]:
                if edge.capacity > 0 and level[edge.to] < 0:
                    level[edge.to] = level[u] + 1
                    queue.append(edge.to)
        if level[sink] < 0:
            return pushed_total
        cursor = [0] * len(graph)

        def augment(node: int, pushed: int) -> int:
            if node == sink:
                return pushed
            while cursor[node] < len(graph[node]):
                edge = graph[node][cursor[node]]
                if edge.capacity > 0 and level[edge.to] == level[node] + 1:
                    sent = augment(edge.to, min(pushed, edge.capacity))
                    if sent:
                        edge.capacity -= sent
                        graph[edge.to][edge.rev].capacity += sent
                        return sent
                cursor[node] += 1
            return 0

        while True:
            bound = sum(edge.capacity for edge in graph[source])
            sent = augment(source, bound)
            if not sent:
                break
            pushed_total += sent


def min_cost_flow(
    network: FlowNetwork, source: int, sink: int, required: int,
) -> tuple[int, int]:
    """Successive shortest path flow of ``required`` units.

    Returns ``(sent_units, total_cost)``.  Shortest paths are found with SPFA
    so unit costs of -1, 0 and 1 (including active negative reverse edges)
    stay exact; each augmentation pushes a full bottleneck, so the iteration
    count is governed by the graph size rather than by liter counts.
    """
    graph = network.adjacency
    sent = 0
    cost = 0
    while sent < required:
        distances: list[int | None] = [None] * len(graph)
        previous_edge: list[_Edge | None] = [None] * len(graph)
        previous_node = [-1] * len(graph)
        in_queue = [False] * len(graph)
        distances[source] = 0
        queue = deque([source])
        in_queue[source] = True
        while queue:
            u = queue.popleft()
            in_queue[u] = False
            base = distances[u]
            for edge in graph[u]:
                if edge.capacity <= 0:
                    continue
                candidate = base + edge.cost
                current = distances[edge.to]
                if current is None or candidate < current:
                    distances[edge.to] = candidate
                    previous_edge[edge.to] = edge
                    previous_node[edge.to] = u
                    if not in_queue[edge.to]:
                        queue.append(edge.to)
                        in_queue[edge.to] = True
        if distances[sink] is None:
            break

        amount = required - sent
        node = sink
        while node != source:
            edge = previous_edge[node]
            amount = min(amount, edge.capacity)
            node = previous_node[node]
        node = sink
        while node != source:
            edge = previous_edge[node]
            edge.capacity -= amount
            graph[node][edge.rev].capacity += amount
            cost += amount * edge.cost
            node = previous_node[node]
        sent += amount
    return sent, cost
