from dataclasses import dataclass

CounterRows = tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class CounterReceipt:
    day: str
    revision: str


@dataclass(frozen=True, slots=True)
class CounterRevision:
    day: str
    revision: str
    lines: CounterRows
    pools: CounterRows

    @property
    def receipt(self) -> CounterReceipt:
        return CounterReceipt(self.day, self.revision)

    def same_counts(self, other: 'CounterRevision') -> bool:
        return self.lines == other.lines and self.pools == other.pools

    @property
    def totals(self) -> tuple[int, int]:
        return (
            sum(liters for _, liters in self.lines),
            sum(liters for _, liters in self.pools),
        )
