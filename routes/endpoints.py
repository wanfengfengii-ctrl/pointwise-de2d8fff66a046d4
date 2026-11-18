from collections.abc import Iterable
from dataclasses import dataclass

RoutePair = tuple[str, str]


def _canonical_side(names: Iterable[str]) -> tuple[str, ...]:
    if isinstance(names, (str, bytes)):
        raise ValueError('an endpoint roster must be a collection of names')
    endpoints: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ValueError('endpoint names must be nonempty text')
        endpoints.add(name)
    return tuple(sorted(endpoints))


@dataclass(frozen=True, slots=True)
class EndpointRoster:
    lines: tuple[str, ...]
    pools: tuple[str, ...]

    @classmethod
    def from_sides(cls, lines: Iterable[str], pools: Iterable[str]) -> 'EndpointRoster':
        return cls(_canonical_side(lines), _canonical_side(pools))

    def contains_route(self, route: RoutePair) -> bool:
        line, pool = route
        return line in self.lines and pool in self.pools

    def coverage_difference(
        self, line_counts: Iterable[str], pool_counts: Iterable[str],
    ) -> dict[str, tuple[str, ...]]:
        differences = {}
        for side, declared, reported in (
            ('lines', self.lines, line_counts), ('pools', self.pools, pool_counts),
        ):
            expected, actual = set(declared), set(reported)
            if missing := expected - actual:
                differences[f'missing_{side}'] = tuple(sorted(missing))
            if extra := actual - expected:
                differences[f'extra_{side}'] = tuple(sorted(extra))
        return differences
