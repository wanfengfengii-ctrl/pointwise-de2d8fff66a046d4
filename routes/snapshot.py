import json
from dataclasses import dataclass

from routes.endpoints import EndpointRoster, RoutePair


@dataclass(frozen=True, slots=True)
class RouteReceipt:
    day: str
    revision: str


@dataclass(frozen=True, slots=True)
class RouteRevision:
    day: str
    revision: str
    roster: EndpointRoster
    open_routes: tuple[RoutePair, ...]

    @property
    def receipt(self) -> RouteReceipt:
        return RouteReceipt(self.day, self.revision)

    def same_definition(self, other: 'RouteRevision') -> bool:
        return self.roster == other.roster and self.open_routes == other.open_routes


def encode_route_revision(revision: RouteRevision) -> str:
    return json.dumps({
        'day': revision.day,
        'revision': revision.revision,
        'lines': revision.roster.lines,
        'pools': revision.roster.pools,
        'open_routes': revision.open_routes,
    }, separators=(',', ':'))


def decode_route_revision(payload: str) -> RouteRevision:
    data = json.loads(payload)
    return RouteRevision(
        data['day'], data['revision'],
        EndpointRoster(tuple(data['lines']), tuple(data['pools'])),
        tuple((line, pool) for line, pool in data['open_routes']),
    )
