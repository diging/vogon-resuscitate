class GilesUploadError(Exception):
    """Exception raised when no Giles uploads are available."""
    pass

class GilesTextExtractionError(Exception):
    """Exception raised when no valid text/plain content is found."""
    pass
