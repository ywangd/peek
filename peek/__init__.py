"""Top-level package for peek."""

from importlib.metadata import PackageNotFoundError, version

__author__ = """Yang Wang"""
__email__ = 'ywangd@gmail.com'


try:
    __version__ = version("es-peek")
except PackageNotFoundError:
    # package is not installed
    pass
