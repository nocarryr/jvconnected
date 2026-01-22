from pathlib import Path
import importlib.resources

def get_resource_filename(name: str) -> Path:
    """Get a resource filename relative to this package location using
    :func:`importlib.resources.files`

    Arguments:
        name (str): The filename or directory name

    Returns:
        The resource filename as a :class:`pathlib.Path`

    """
    p = importlib.resources.files(__name__).joinpath(name)
    assert isinstance(p, Path)
    return Path(p)
