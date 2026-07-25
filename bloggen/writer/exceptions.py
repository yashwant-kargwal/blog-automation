"""Blog writer exceptions."""


class WriterError(RuntimeError):
    """Base blog writer error."""


class WriterInputError(WriterError):
    """Raised when research or SEO input is invalid."""


class WriterOutputError(WriterError):
    """Raised when generated Markdown fails quality validation."""
