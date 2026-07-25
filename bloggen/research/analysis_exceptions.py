"""Research analysis exceptions."""


class ResearchAnalysisError(RuntimeError):
    """Base class for grounded research failures."""


class ResearchInputError(ResearchAnalysisError):
    """Raised when supplied articles cannot be analyzed."""


class ResearchOutputError(ResearchAnalysisError):
    """Raised when the model returns unusable output."""
