from pathlib import Path
from pkg_resources import resource_filename

def get_resource_filename(name: str) -> Path:
    """Get a resource filename relative to this package location using
    `pkg_resources`_

    Arguments:
        name (str): The filename or directory name

    Returns:
        The resource filename as a :class:`pathlib.Path`

    .. _pkg_resources: https://setuptools.readthedocs.io/en/latest/pkg_resources.html#resourcemanager-api
    """
    return Path(resource_filename(__name__, name))
