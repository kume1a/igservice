import logging
import os
import tempfile
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _assert_safe_url(url: str) -> None:
    scheme = urlparse(url).scheme
    if scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {scheme!r}")


@contextmanager
def download_to_temp(url: str, suffix: str, directory: str) -> Iterator[Path]:
    """Download `url` to a temp file under `directory`, yielding its Path.

    The temp file is always removed on exit, even on error.
    """
    _assert_safe_url(url)
    fd, raw_path = tempfile.mkstemp(suffix=suffix, dir=directory)
    os.close(fd)
    path = Path(raw_path)
    try:
        urllib.request.urlretrieve(url, path)
        yield path
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove temp file: %s", path)


@contextmanager
def maybe_download_to_temp(
    url: Optional[str],
    suffix: str,
    directory: str,
) -> Iterator[Optional[Path]]:
    """Like `download_to_temp`, but yields None when `url` is falsy."""
    if not url:
        yield None
        return
    with download_to_temp(url, suffix, directory) as path:
        yield path
