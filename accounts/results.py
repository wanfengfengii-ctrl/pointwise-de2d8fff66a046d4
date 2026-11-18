FlowResult = tuple[int, int]


def make_bounds_result(total: int, minimum: FlowResult, maximum: FlowResult) -> list[int]:
    sent_for_min, low = minimum
    sent_for_max, negated_high = maximum
    if sent_for_min != total or sent_for_max != total:
        raise RuntimeError('sealed allocation could not deliver its full recorded total')
    high = -negated_high
    if not 0 <= low <= high <= total:
        raise RuntimeError('solver returned inconsistent group bounds')
    return [low, high]


def zero_bounds() -> list[int]:
    return [0, 0]
