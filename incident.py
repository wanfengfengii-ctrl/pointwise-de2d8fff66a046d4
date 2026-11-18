import argparse
from contextlib import ExitStack, closing
from pathlib import Path
from tempfile import TemporaryDirectory

from accounts.bounds import bounds
from archive.lookup import read_receipt
from archive.store import ArchiveStore
from counters.imports import stage_counters
from counters.ledger import CounterLedger
from routes.catalog import RouteCatalog
from routes.registration import put_routes
from settlement.admission import certify
from settlement.failures import InfeasibleBatchError

DAY = "2025-04-09"
FULL = (("A", "X"), ("A", "Y"), ("B", "X"), ("B", "Y"))
INTO_X = (("A", "X"), ("B", "X"))
DIAGONAL = (("A", "X"), ("B", "Y"))


def check_rejection(ledger, catalog, archive, counter_rev, route_rev, previous_id):
    try:
        artifact_id = certify(ledger, catalog, archive, DAY, counter_rev, route_rev)
    except InfeasibleBatchError:
        if archive.read_publication(previous_id + 1) != (None, None):
            return [f"{route_rev}: rejected, but left a publication row"], previous_id + 1
        return [], previous_id
    receipt = read_receipt(archive, artifact_id)
    return [f"{route_rev}: expected rejection, published {artifact_id} with receipt {receipt!r}"], artifact_id


def check_bounds(archive, artifact_id):
    mismatches = []
    for label, group, expected in (
        ("single", (("A", "X"),), [0, 1]),
        ("into X", INTO_X, [1, 1]),
        ("diagonal", DIAGONAL, [0, 2]),
    ):
        actual = bounds(archive, artifact_id, group)
        if actual != expected:
            mismatches.append(f"{label}: expected {expected}, got {actual}")
    return mismatches


def exercise(root, case):
    issues = []
    archive_path = ":memory:" if root is None else root / "archive.sqlite"
    with closing(ArchiveStore(archive_path)) as archive:
        with ExitStack() as opened:
            counter_path = ":memory:" if root is None else root / "counters.sqlite"
            route_path = ":memory:" if root is None else root / "routes.sqlite"
            ledger = opened.enter_context(closing(CounterLedger(counter_path)))
            catalog = opened.enter_context(closing(RouteCatalog(route_path)))
            lines, pools = {"A": 1, "B": 1}, {"X": 1, "Y": 1}
            stage_counters(ledger, DAY, "balanced", lines, pools)
            put_routes(catalog, DAY, "all", lines, pools, FULL)
            good_id = certify(ledger, catalog, archive, DAY, "balanced", "all")
            if case != "audit":
                put_routes(catalog, DAY, "closed-Y", lines, pools, INTO_X)
                first, last_id = check_rejection(ledger, catalog, archive, "balanced", "closed-Y", good_id)
                issues.extend(first)
                lines["C"], pools["Z"] = 1, 1
                stage_counters(ledger, DAY, "six", lines, pools)
                opened_routes = INTO_X + (("C", "Y"), ("C", "Z"))
                put_routes(catalog, DAY, "shared-X", lines, pools, opened_routes)
                second, _ = check_rejection(ledger, catalog, archive, "six", "shared-X", last_id)
                issues.extend(second)
        if case != "admission" and root is None:
            issues.extend(check_bounds(archive, good_id))
    if case != "admission" and root is not None:
        with closing(ArchiveStore(archive_path)) as archive:
            issues.extend(check_bounds(archive, good_id))
    return issues


def main():
    parser = argparse.ArgumentParser(description="Check the daily allocation incident")
    parser.add_argument("--case", choices=("both", "admission", "audit"), default="both")
    parser.add_argument("--memory", action="store_true", help="Use in-memory stores without reopening")
    args = parser.parse_args()
    if args.memory:
        issues = exercise(None, args.case)
    else:
        with TemporaryDirectory() as directory:
            issues = exercise(Path(directory), args.case)
    if issues:
        print("DAILY_FLOW_RECONCILIATION")
        print("\n".join(issues))
        return 1
    print("Daily allocation incident checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
