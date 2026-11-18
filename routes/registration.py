from collections.abc import Iterable

from routes.catalog import RouteCatalog
from routes.endpoints import RoutePair
from routes.snapshot import RouteReceipt
from routes.validation import validate_route_registration


def put_routes(
    catalog: RouteCatalog,
    day: str,
    revision: str,
    lines: Iterable[str],
    pools: Iterable[str],
    open_routes: Iterable[RoutePair],
) -> RouteReceipt:
    snapshot = validate_route_registration(day, revision, lines, pools, open_routes)
    return catalog.put(snapshot)
