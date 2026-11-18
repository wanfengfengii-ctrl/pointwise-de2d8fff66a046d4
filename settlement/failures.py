class SourceBindingError(ValueError):
    """The specified same-day source revisions cannot be bound."""


class InfeasibleBatchError(ValueError):
    """No complete integer allocation satisfies the bound sources."""
