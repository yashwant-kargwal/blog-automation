"""Pipeline exceptions."""


class PipelineError(RuntimeError):
    """Expected pipeline failure that should stop downstream stages."""
