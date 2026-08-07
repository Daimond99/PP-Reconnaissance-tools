"""Tests for src/ui/terminal_launch.py — the pure launch-script + path
builders split out of terminal_tabs.py (2026-08-07).

These build the bash scripts that actually run inside WSL/native shells, and
the Windows→WSL path derivation. They had zero test coverage while embedded in
terminal_tabs (Qt + subprocess made them awkward to reach); split out, they're
plain functions returning strings.
"""

from __future__ import annotations

from src.ui import terminal_launch as t


class TestWizardArgStr:
    def test_empty(self):
        assert t._wizard_arg_str(None) == ""
        assert t._wizard_arg_str([]) == ""

    def test_leading_space_and_join(self):
        assert t._wizard_arg_str(["--mode", "auto"]) == " --mode auto"

    def test_shell_metachars_are_quoted(self):
        # a malicious/space-y target must be POSIX-quoted, never bare
        out = t._wizard_arg_str(["--target", "a;b c"])
        assert " --target 'a;b c'" == out


class TestWinToWslPath:
    def test_drive_letter_lowercased_and_mounted(self):
        assert t._win_to_wsl_path(r"D:\TheRecon") == "/mnt/d/TheRecon"

    def test_backslashes_become_slashes(self):
        assert t._win_to_wsl_path(r"C:\Users\me\wl.txt") == "/mnt/c/Users/me/wl.txt"


class TestPathDerivation:
    def test_wsl_dirs_hang_off_wsl_root(self):
        root = t._wsl_root_dir()
        assert t._wsl_dir() == f"{root}/chain_wizard"
        assert t._wsl_llm_dir() == f"{root}/tools/llm-tools-nmap"
        assert t._wsl_opencode_dir() == f"{root}/tools/opencode-workspace"

    def test_local_dirs_end_with_expected_tail(self):
        assert t._repo_local_dir().replace("\\", "/").endswith("/chain_wizard")
        assert t._repo_local_llm_dir().replace("\\", "/").endswith("/tools/llm-tools-nmap")


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


class TestLlmLaunch:
    def test_offers_key_setup_when_none(self):
        s = t._llm_launch("/llm")
        assert "No keys found" in s
        assert "llm keys set openai" in s
        assert s.strip().endswith("exec bash -l")


class TestOpencodeLaunch:
    def test_scopes_path_and_respawns(self):
        s = t._opencode_launch("/ws")
        assert 'if [ -z "$HOME" ]' in s          # HOME guard first
        assert "recon_agent_bin" in s            # restricted PATH dir
        assert "AGENTS.md" in s                   # scope note dropped
        # per-name deletes, never a dir/* glob (the safety-incident fix)
        assert '"$SCOPE_BIN"/*' not in s
        assert 'while :; do "$OC"; sleep 1; done' in s

    def test_only_the_six_tools_plus_readonly_utils_scoped(self):
        # the PATH-scope symlink set must not silently grow
        assert t._SCOPE_TOOLS == ["nmap", "masscan", "hydra", "ncrack", "ncat", "evil-winrm"]
