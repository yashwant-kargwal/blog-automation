"""SEO engine exceptions."""


class SEOError(RuntimeError):
    """Base SEO engine error."""


class SEOInputError(SEOError):
    """Raised when research input is missing or unusable."""


class SEOOutputError(SEOError):
    """Raised when the provider returns invalid SEO JSON."""
