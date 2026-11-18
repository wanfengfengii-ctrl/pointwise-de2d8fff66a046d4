from dataclasses import dataclass

from routes.endpoints import RoutePair


@dataclass(frozen=True, slots=True)
class GroupObjective:
    selected: frozenset[RoutePair]

    def costs(self, *, maximize: bool) -> dict[RoutePair, int]:
        weight = -1 if maximize else 1
        return dict.fromkeys(self.selected, weight)


def build_group_objective(routes: frozenset[RoutePair]) -> GroupObjective:
    return GroupObjective(routes)
