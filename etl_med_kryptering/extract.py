"""Extract module.

Three methods for fetching the flora data into Input_dir. Each derives
the filename from the URL (never hardcoded) and adds a header row.
"""

import os
import re
import subprocess
from urllib.parse import urlparse

import requests
import wget
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import COLUMN_NAMES

CHUNK_SIZE = 8192  # download one block at a time -> flat memory use


def _filename_from_url(url: str) -> str:
    """Filename from the URL path, sanitised.

    Keeping only the basename and stripping odd characters blocks path
    traversal and shell metacharacters in the filename.
    """
    raw_name = os.path.basename(urlparse(url).path)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name)
    if not safe_name:
        raise ValueError(f"Could not derive a filename from URL: {url}")
    return safe_name


def _build_retrying_session() -> requests.Session:
    """Session that retries dropped connections, stalled reads and 5xx.

    Backoff spaces the attempts (0s, 2s, 4s). This is curl's --retry,
    but in-process.
    """
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _ensure_header_row(csv_path: str) -> None:
    """Prepend column names; the source file ships without a header.

    The check makes this idempotent if the source ever adds one.
    """
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        first_line = f.readline()
        rest = f.read()

    if first_line.strip().lower().startswith(COLUMN_NAMES[0]):
        return

    header = ",".join(COLUMN_NAMES) + "\n"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write(header)
        f.write(first_line)
        f.write(rest)


def extract_with_requests(url: str, dest_dir: str) -> str:
    """Download with `requests`.

    Security:   no shell involved, so no injection surface at all.
                Non-HTTPS is rejected; requests verifies certificates.
    Robustness: streamed in blocks (flat memory), connect+read timeouts
                so a stalled socket aborts instead of hanging, retry
                with backoff, and partial downloads are deleted.
    """
    if not url.lower().startswith("https://"):
        raise ValueError("Refusing to download over a non-HTTPS URL")

    os.makedirs(dest_dir, exist_ok=True)
    filename = _filename_from_url(url)
    dest_path = os.path.join(dest_dir, filename)

    session = _build_retrying_session()
    try:
        with session.get(url, stream=True, timeout=(5, 15)) as response:
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                for block in response.iter_content(chunk_size=CHUNK_SIZE):
                    if block:
                        f.write(block)
    except (requests.exceptions.RequestException, OSError):
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise
    finally:
        session.close()

    _ensure_header_row(dest_path)
    return dest_path


def extract_with_wget(url: str, dest_dir: str) -> str:
    """Download with the `wget` module (pure Python, not the binary).

    Security:   no shell involved, so no injection surface. Non-HTTPS
                is rejected.
    Robustness: reads in 8 KiB blocks internally, and we delete partial
                files ourselves. Weak spot: the module offers no timeout,
                so a stalled connection hangs indefinitely.
    """
    if not url.lower().startswith("https://"):
        raise ValueError("Refusing to download over a non-HTTPS URL")

    os.makedirs(dest_dir, exist_ok=True)
    filename = _filename_from_url(url)
    dest_path = os.path.join(dest_dir, filename)

    if os.path.exists(dest_path):
        os.remove(dest_path)  # wget.download errors if the target exists

    try:
        wget.download(url, out=dest_path)
    except Exception:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise

    _ensure_header_row(dest_path)
    return dest_path


def extract_with_curl(url: str, dest_dir: str) -> str:
    """Download by running the external `curl` via subprocess.

    Security:   the command is an argument LIST with shell=False, so the
                URL is one argv entry and never reaches a shell - that is
                what defeats injection (`; rm -rf .` stays literal text).
                --proto =https and --tlsv1.2 pin the transport.
    Robustness: curl streams to disk and --retry re-attempts a dropped
                transfer. A non-zero exit raises, and we delete the
                partial file.
    """
    if not url.lower().startswith("https://"):
        raise ValueError("Refusing to download over a non-HTTPS URL")

    os.makedirs(dest_dir, exist_ok=True)
    filename = _filename_from_url(url)
    dest_path = os.path.join(dest_dir, filename)

    command = [
        "curl",
        "--proto", "=https",
        "--tlsv1.2",
        "--fail",              # non-2xx status -> non-zero exit code
        "--retry", "3",
        "--connect-timeout", "5",
        "--output", dest_path,
        url,
    ]

    try:
        subprocess.run(command, shell=False, check=True, timeout=60)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise

    _ensure_header_row(dest_path)
    return dest_path
