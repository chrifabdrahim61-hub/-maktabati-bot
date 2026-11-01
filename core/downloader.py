"""PDF downloader — streams to a temp file with a hard 50 MB cap (Telegram's
send limit), validates the %PDF- magic bytes, and hands back the path.

The caller is responsible for deleting the file right after sending it
(keeping the machine/database clean, as requested).
"""
import logging
import re
from pathlib import Path

import httpx

from config import TEMP_DIR

logger = logging.getLogger(__name__)

MAX_BYTES = 50 * 1024 * 1024  # Telegram bot send limit: 50 MB

_HEADERS = {"User-Agent": "Maktabati/0.5 (Telegram bot; open-access book finder)"}

_TIMEOUT = httpx.Timeout(connect=15, read=120, write=30, pool=30)


class DownloadError(Exception):
    """Generic download failure (network / HTTP status)."""


class TooLargeError(DownloadError):
    """File exceeds the Telegram 50 MB limit."""


class NotPdfError(DownloadError):
    """Downloaded bytes are not a PDF."""


def _check_size_headers(resp: httpx.Response, max_bytes: int) -> None:
    """Abort early when the server already tells us the file is too big."""
    for header in ("Content-Length", "x-archive-orig-content-length"):
        raw = resp.headers.get(header)
        if raw and raw.isdigit() and int(raw) > max_bytes:
            raise TooLargeError(f"{header}={raw} > cap {max_bytes}")


def validate_pdf_bytes(path: Path) -> None:
    """A real PDF must contain the %PDF- magic in its first 1024 bytes."""
    with path.open("rb") as fh:
        head = fh.read(1024)
    if b"%PDF-" not in head:
        raise NotPdfError("no %PDF- magic in first 1024 bytes")


async def download_pdf(url: str, dest_dir: Path = TEMP_DIR, max_bytes: int = MAX_BYTES) -> Path:
    """Stream `url` into dest_dir and return the finished, validated file path.

    Raises TooLargeError / NotPdfError / DownloadError. Partial files are
    always deleted before raising.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest_dir / f".dl_{abs(hash(url)) % 10**10}.part"

    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
        ) as client:
            # cheap pre-check: many servers (incl. archive.org) give the size upfront
            try:
                head = await client.head(url)
                if head.status_code in (401, 403):
                    raise DownloadError(f"protected file (HTTP {head.status_code})")
                _check_size_headers(head, max_bytes)
            except DownloadError:
                raise
            except httpx.HTTPError:
                pass  # HEAD unsupported/flaky → the real GET below decides

            received = 0
            async with client.stream("GET", url) as resp:
                if resp.status_code in (401, 403):
                    raise DownloadError(f"protected file (HTTP {resp.status_code})")
                resp.raise_for_status()
                _check_size_headers(resp, max_bytes)
                with tmp.open("wb") as fh:
                    async for chunk in resp.aiter_bytes(64 * 1024):
                        received += len(chunk)
                        if received > max_bytes:
                            raise TooLargeError(f"streamed {received} bytes > cap")
                        fh.write(chunk)

        if received < 512:
            raise DownloadError(f"suspiciously small file ({received} bytes)")
        validate_pdf_bytes(tmp)
        logger.info("Downloaded %s (%.1f MB)", url[:90], received / 1_048_576)
        return tmp

    except TooLargeError:
        tmp.unlink(missing_ok=True)
        raise
    except (httpx.HTTPError, OSError) as exc:
        tmp.unlink(missing_ok=True)
        raise DownloadError(f"{exc.__class__.__name__}: {exc}") from exc


_SAFE = re.compile(r"[^\w\s\-()\[\]؟،.]+", re.UNICODE)


def safe_filename(title: str, ext: str = ".pdf") -> str:
    """Turn a book title into a clean, Telegram-safe filename (keeps Arabic)."""
    cleaned = _SAFE.sub("", title)              # drop path-hostile chars
    cleaned = re.sub(r"\.{2,}", ".", cleaned)   # collapse dot runs (../../ → .)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")[:80].strip() or "book"
    return f"{cleaned}{ext}"
