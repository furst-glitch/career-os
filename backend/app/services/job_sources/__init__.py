from .base import BaseJobSource, JobResult
from .jobindex import JobindexSource
from .jobnet import JobnetSource
from .ofir import OfirSource

# Registry: source_name -> class
SOURCES: dict[str, type[BaseJobSource]] = {
    "jobnet": JobnetSource,
    "jobindex": JobindexSource,
    "ofir": OfirSource,
}

DEFAULT_SOURCES = ["jobnet", "jobindex", "ofir"]

__all__ = ["BaseJobSource", "JobResult", "JobnetSource", "JobindexSource", "OfirSource", "SOURCES", "DEFAULT_SOURCES"]
