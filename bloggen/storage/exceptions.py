"""Project storage exceptions."""


class StorageError(RuntimeError):
    """Base artifact storage error."""


class ProjectExistsError(StorageError):
    """Raised when a project path would overwrite an existing project."""


class ArtifactExistsError(StorageError):
    """Raised when an artifact target already exists."""
