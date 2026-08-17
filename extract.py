"""Extract module.

Three independent methods for fetching the flora data file from the
international data source and saving it, unmodified, into Input_dir.
Each method derives the destination filename from the URL itself
(never hardcoded), so the pipeline keeps working if the data source
changes filenames.
"""

import os
import re
import subprocess
from urllib.parse import urlparse

import requests
import wget

CHUNK_SIZE = 8192  # bytes per block; keeps memory flat and lets us resume/react to interruptions


def _filename_from_url(url: str) -> str:
    """Derive a safe local filename from the URL's path component.

    Only the basename is kept (no directories from the URL are honoured),
    and anything that isn't alphanumeric/dot/dash/underscore is stripped.
    This is what prevents a malicious or malformed URL from writing
    outside Input_dir (path traversal) or injecting shell metacharacters
    into a filename that later gets used in a command.
    """
    raw_name = os.path.basename(urlparse(url).path)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name)
    if not safe_name:
        raise ValueError(f"Could not derive a filename from URL: {url}")
    return safe_name


def extract_with_requests(url: str, dest_dir: str) -> str:
    """Download using the `requests` library, streamed in small blocks.

    Security:
      - HTTPS is enforced by rejecting non-https URLs outright, and
        requests verifies the TLS certificate by default (verify=True),
        so the data transport is protected against MITM tampering.
      - No shell/subprocess is involved here at all, so there is no
        command-line injection surface for this method.
    Robustness:
      - stream=True + iter_content(CHUNK_SIZE) pulls the body in small
        blocks instead of buffering the whole response in memory, and
        a read timeout means a stalled/unstable connection raises
        instead of hanging forever. A partial/interrupted download is
        removed rather than left as a corrupt file.
    """
    if not url.lower().startswith("https://"):
        raise ValueError("Refusing to download over a non-HTTPS URL")

    os.makedirs(dest_dir, exist_ok=True)
    filename = _filename_from_url(url)
    dest_path = os.path.join(dest_dir, filename)

    try:
        with requests.get(url, stream=True, timeout=(5, 15)) as response:
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                for block in response.iter_content(chunk_size=CHUNK_SIZE):
                    if block:
                        f.write(block)
    except (requests.exceptions.RequestException, OSError):
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise

    return dest_path


def extract_with_wget(url: str, dest_dir: str) -> str:
    """Download using the `wget` Python module, streamed in small blocks.

    Security:
      - Same HTTPS enforcement as the requests method. The `wget` module
        is a pure-Python HTTP client (not a wrapper around the external
        wget binary), so it never touches a shell and has no command-line
        injection surface either.
    Robustness:
      - Internally the wget module reads the response in fixed-size
        blocks (default 8 KiB) and writes them incrementally to disk,
        so it doesn't buffer the entire file in memory. If the download
        is interrupted, the partially written file is removed here so a
        failed run never leaves a corrupt file behind for the next stage.
    """
    if not url.lower().startswith("https://"):
        raise ValueError("Refusing to download over a non-HTTPS URL")

    os.makedirs(dest_dir, exist_ok=True)
    filename = _filename_from_url(url)
    dest_path = os.path.join(dest_dir, filename)

    if os.path.exists(dest_path):
        os.remove(dest_path)  # wget.download errors if the target already exists

    try:
        wget.download(url, out=dest_path)
    except Exception:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise

    return dest_path


def extract_with_curl(url: str, dest_dir: str) -> str:
    """Download by invoking the external `curl` program via subprocess.

    Security:
      - subprocess.run() is called with an argument LIST and shell=False
        (the default), so the URL is passed to curl as a single argv
        entry rather than being interpolated into a shell command
        string. That's what defeats command-line injection: even if the
        URL contained characters like `; rm -rf .` or `$(...)`, they
        would never be interpreted by a shell because no shell is
        invoked.
      - "--proto =https" and "--tlsv1.2" pin the transfer to HTTPS with
        a modern TLS version, and curl verifies certificates by default
        (no -k/--insecure flag is used), so data-in-transit is protected.
    Robustness:
      - curl streams the response to disk in blocks internally (it does
        not buffer the whole file in memory) and "--retry" makes it
        re-attempt the transfer if the connection drops mid-download.
        A non-zero exit code (e.g. connection reset) raises
        CalledProcessError, and the partial output file is deleted so a
        failed run doesn't leave corrupt data behind.
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
        "--fail",              # non-2xx HTTP status -> non-zero exit code
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

    return dest_path
