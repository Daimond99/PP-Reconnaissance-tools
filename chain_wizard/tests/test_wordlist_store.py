"""Saving a wordlist into the shared (mounted) folder: copy only, never overwrite."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.core.wordlist_store import save_wordlist  # noqa: E402


def test_copies_file_into_shared_folder(tmp_path):
    src = tmp_path / "src" / "users.txt"
    src.parent.mkdir()
    src.write_text("admin\nroot\n")
    share = tmp_path / "share"
    share.mkdir()
    ok, msg = save_wordlist(str(src), str(share))
    assert ok, msg
    assert (share / "users.txt").read_text() == "admin\nroot\n"
    assert "/results/wordlists/users.txt" in msg


def test_refuses_to_overwrite(tmp_path):
    src = tmp_path / "pw.txt"
    src.write_text("new")
    share = tmp_path / "share"
    share.mkdir()
    (share / "pw.txt").write_text("keep")
    ok, _ = save_wordlist(str(src), str(share))
    assert not ok
    assert (share / "pw.txt").read_text() == "keep"


def test_refuses_missing_folder_and_missing_source(tmp_path):
    src = tmp_path / "pw.txt"
    src.write_text("x")
    assert not save_wordlist(str(src), str(tmp_path / "nope"))[0]
    assert not save_wordlist(str(tmp_path / "missing.txt"), str(tmp_path))[0]
