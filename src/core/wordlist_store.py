"""
Copy a wordlist into the folder that docker/run.sh mounts read-only at
/results/wordlists, so the tool container (Wizard and OpenCode) can read it
straight away -- no container restart needed for files in that folder.

The destination must match docker/run.sh exactly: THERECON_WORDLISTS when
set, otherwise ~/Downloads/rockyou.txt-main. Nothing else is written.
"""

from __future__ import annotations

import os
import shutil
from typing import Tuple

SHARE_DIR_ENV = "THERECON_WORDLISTS"
DEFAULT_SHARE_DIR = os.path.join("~", "Downloads", "rockyou.txt-main")
CONTAINER_PATH = "/results/wordlists"


def share_dir() -> str:
    """The host folder that is mounted at /results/wordlists."""
    return os.path.expanduser(os.environ.get(SHARE_DIR_ENV) or DEFAULT_SHARE_DIR)


def save_wordlist(src_path: str, dest_dir: str | None = None) -> Tuple[bool, str]:
    """Copy `src_path` into the shared folder. Returns (ok, message).

    Refuses to overwrite an existing file, refuses a missing destination
    folder (it is not created here: the mount only exists for a folder
    run.sh already knows about), and copies only a regular file."""
    dest_dir = dest_dir or share_dir()
    name = os.path.basename(src_path or "")
    if not name or name in (".", ".."):
        return False, "Pick a wordlist file."
    if not os.path.isfile(src_path):
        return False, f"Not a file: {src_path}"
    if not os.path.isdir(dest_dir):
        return False, (f"Shared wordlists folder does not exist: {dest_dir}. "
                       f"Create it or set {SHARE_DIR_ENV} and re-run docker/run.sh.")
    dest = os.path.join(dest_dir, name)
    if os.path.exists(dest):
        return False, f"'{name}' is already in the shared folder — not overwritten."
    try:
        shutil.copyfile(src_path, dest)
    except OSError as exc:
        return False, f"Copy failed: {exc}"
    return True, f"Saved '{name}'. In the container it is at {CONTAINER_PATH}/{name}."
