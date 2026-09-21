"""Tests for src/ui/terminal_launch.py — the pure launch-script + path
builders split out of terminal_tabs.py (2026-08-07).

These build the bash scripts that actually run inside WSL/native shells, and
the Windows→WSL path derivation. They had zero test coverage while embedded in
terminal_tabs (Qt + subprocess made them awkward to reach); split out, they're
plain functions returning strings.
"""

from __future__ import annotations

from src.ui import terminal_launch as t


class TestWinToWslPath:
    def test_drive_letter_lowercased_and_mounted(self):
        assert t._win_to_wsl_path(r"D:\TheRecon") == "/mnt/d/TheRecon"

    def test_backslashes_become_slashes(self):
        assert t._win_to_wsl_path(r"C:\Users\me\wl.txt") == "/mnt/c/Users/me/wl.txt"


class TestPathDerivation:
    def test_wsl_dirs_hang_off_wsl_root(self):
        root = t._wsl_root_dir()
        assert t._wsl_dir() == f"{root}/chain_wizard"

    def test_local_dirs_end_with_expected_tail(self):
        assert t._repo_local_dir().replace("\\", "/").endswith("/chain_wizard")


class TestShellLaunch:
    def test_confines_and_blocks_opencode(self):
        s = t._shell_launch("/scope")
        assert "TR_SCOPE_DIR" in s          # confinement installed
        assert "TR_BLOCK_OPENCODE" in s     # opencode-block installed
        assert "opencode" in s
        assert s.strip().endswith("exec bash -l")

    def test_home_guard_present(self):
        # never touch the filesystem / glob if $HOME is empty
        assert 'if [ -z "$HOME" ]' in t._shell_launch("/scope")


class TestOpencodeLaunch:
    def test_execs_into_tool_container_and_respawns(self):
        s = t._opencode_launch()
        assert "therecon-tools" in s              # the shared tool container
        assert "docker exec -i therecon-tools bash -s" in s   # non-tty setup pass
        assert "AGENTS.md" in s                   # scope note dropped
        assert "opencode.json" in s               # permission gate config
        assert "/results/opencode-workspace" in s  # under the rw bind mount
        assert "/results/opencode-home" in s
        assert "docker exec -it -e HOME=" in s    # interactive pass, real tty
        assert s.strip().endswith(
            "therecon-tools opencode; sleep 1; done")

    def test_checks_container_is_running_first(self):
        s = t._opencode_launch()
        assert "docker inspect -f '{{.State.Running}}' therecon-tools" in s
        assert "./docker/run.sh" in s              # the fix, if it isn't


class TestShellWrapperScope:
    def test_only_the_six_tools_scoped(self):
        # the Shell tab's PATH-scope wrapper set must not silently grow
        assert t._SCOPE_TOOLS == ["nmap", "masscan", "hydra", "ncrack", "ncat", "evil-winrm"]
