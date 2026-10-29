"""Run-log parsing and the structured log viewer: each command becomes one
entry with its tool, exit status and findings, and the viewer can filter and
search them instead of showing the raw text dump."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication

from src.core.log_parser import LineKind, classify_line, parse_log, read_log

NEW_FORMAT = """# 2026-10-29T01:02:03.123456 exit=0
$ nmap -sS -p 22,80 10.0.0.5
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http

# 2026-10-29T01:05:00.000001 exit=1
$ sudo hydra -L users.txt -P pass.txt ssh://10.0.0.5
[22][ssh] host: 10.0.0.5   login: admin   password: hunter2
Error: connection refused

# 2026-10-29T01:09:00.000001 exit=timeout
$ evil-winrm -i 10.0.0.5 -u admin -p x
(killed after 600s)
"""

LEGACY_FORMAT = """# 2026-10-20T12:16:47.061756
$ nmap --script http-vuln* -p 80 10.0.0.9
80/tcp open  http
|_http-vuln: ERROR: Script execution failed

"""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class TestParseLog:
    def test_splits_commands_into_entries(self):
        entries = parse_log(NEW_FORMAT)
        assert [e.tool for e in entries] == ["nmap", "hydra", "evil-winrm"]

    def test_reads_exit_status(self):
        statuses = [e.status for e in parse_log(NEW_FORMAT)]
        assert statuses == ["ok", "failed", "timeout"]

    def test_counts_findings_and_errors(self):
        nmap, hydra, _ = parse_log(NEW_FORMAT)
        assert nmap.findings == 2
        assert hydra.findings == 1
        assert hydra.errors == 1

    def test_sudo_prefix_is_skipped_when_naming_the_tool(self):
        assert parse_log(NEW_FORMAT)[1].tool == "hydra"

    def test_legacy_entries_without_exit_marker_are_unknown(self):
        entry = parse_log(LEGACY_FORMAT)[0]
        assert entry.status == "unknown"
        assert entry.findings == 1
        assert entry.errors == 1

    def test_trailing_blank_lines_are_dropped(self):
        entry = parse_log(LEGACY_FORMAT)[0]
        assert entry.output[-1].startswith("|_http-vuln")

    def test_empty_text_gives_no_entries(self):
        assert parse_log("") == []

    def test_timestamp_is_shown_without_fraction(self):
        assert parse_log(NEW_FORMAT)[0].started == "2026-10-29 01:02:03"

    def test_read_log_reads_from_disk(self, tmp_path):
        path = tmp_path / "chain_x.log"
        path.write_text(NEW_FORMAT, encoding="utf-8")
        assert len(read_log(path)) == 3


class TestClassifyLine:
    @pytest.mark.parametrize("line", [
        "80/tcp open  http",
        "[22][ssh] host: 10.0.0.5   login: admin   password: hunter2",
        "Discovered credentials on ssh://10.0.0.5:22 'admin' 'pw'",
    ])
    def test_findings(self, line):
        assert classify_line(line) is LineKind.FINDING

    @pytest.mark.parametrize("line", [
        "Error: connection refused",
        "Errno::EROFS in dir_s_mkdir",
    ])
    def test_errors(self, line):
        assert classify_line(line) is LineKind.ERROR

    def test_warning(self):
        assert classify_line("Warning: remote completions disabled") is LineKind.WARNING

    def test_plain(self):
        assert classify_line("Starting Nmap 7.94SVN") is LineKind.PLAIN


class TestRenderLog:
    def test_sections_are_anchored_by_their_line_number(self):
        from src.ui.log_viewer import render_log
        doc = render_log(NEW_FORMAT)
        assert [s.anchor for s in doc.sections] == ["sec1", "sec7", "sec12"]
        assert [s.status for s in doc.sections] == ["ok", "failed", "timeout"]

    def test_totals_for_the_stats_line(self):
        from src.ui.log_viewer import render_log
        totals = render_log(NEW_FORMAT).totals
        assert totals["commands"] == 3
        assert totals["findings"] == 3
        assert totals["errors"] == 1
        assert totals["failed"] == 1
        assert totals["timed_out"] == 1

    def test_line_numbers_are_shown(self):
        from src.ui.log_viewer import render_log
        assert "    2   " in render_log(NEW_FORMAT).html

    def test_findings_are_coloured_as_findings(self):
        from src.ui.log_viewer import render_log
        from src.config import ACCENT_GREEN
        assert ACCENT_GREEN in render_log(NEW_FORMAT).html

    def test_html_in_output_is_escaped(self):
        from src.ui.log_viewer import render_log
        doc = render_log("# 2026-10-29T01:00:00 exit=0\n$ echo x\n<script>alert(1)</script>\n")
        assert "<script>" not in doc.html
        assert "&lt;script&gt;" in doc.html

    def test_plain_text_without_headers_still_renders(self):
        from src.ui.log_viewer import render_log
        doc = render_log("just a note\nanother line\n")
        assert doc.sections == []
        assert "just a note" in doc.html

    def test_needle_counts_matches_and_anchors_them(self):
        from src.ui.log_viewer import ViewOptions, render_log
        doc = render_log(NEW_FORMAT, ViewOptions(needle="hunter2"))
        assert doc.matches == 1
        assert 'name="m0"' in doc.html

    def test_regex_search(self):
        from src.ui.log_viewer import ViewOptions, render_log
        doc = render_log(NEW_FORMAT, ViewOptions(needle=r"\d+/tcp", regex=True))
        assert doc.matches == 2

    def test_invalid_regex_is_reported_not_raised(self):
        from src.ui.log_viewer import ViewOptions, render_log
        doc = render_log(NEW_FORMAT, ViewOptions(needle="(", regex=True))
        assert doc.pattern_error
        assert doc.matches == 0

    def test_case_sensitive_search(self):
        from src.ui.log_viewer import ViewOptions, render_log
        assert render_log(NEW_FORMAT, ViewOptions(needle="HUNTER2")).matches == 1
        assert render_log(NEW_FORMAT, ViewOptions(needle="HUNTER2", case_sensitive=True)).matches == 0

    def test_findings_mode_hides_plain_lines_and_empty_commands(self):
        from src.ui.log_viewer import ViewOptions, render_log
        doc = render_log(NEW_FORMAT, ViewOptions(mode="findings"))
        assert [s.tool for s in doc.visible_sections] == ["nmap", "hydra"]
        assert doc.shown_lines < doc.total_lines
        assert "Error: connection refused" not in doc.html

    def test_failed_mode_keeps_failed_and_timed_out_commands(self):
        from src.ui.log_viewer import ViewOptions, render_log
        doc = render_log(NEW_FORMAT, ViewOptions(mode="failed"))
        assert [s.tool for s in doc.visible_sections] == ["hydra", "evil-winrm"]

    def test_tool_filter(self):
        from src.ui.log_viewer import ViewOptions, render_log
        doc = render_log(NEW_FORMAT, ViewOptions(tool="hydra"))
        assert [s.tool for s in doc.visible_sections] == ["hydra"]
        assert "PORT" not in doc.html

    def test_only_matching_lines_hides_the_rest(self):
        from src.ui.log_viewer import ViewOptions, render_log
        doc = render_log(NEW_FORMAT, ViewOptions(needle="ssh", only_matches=True))
        assert "PORT" not in doc.html
        assert "22/tcp open" in doc.html
        assert [s.tool for s in doc.visible_sections] == ["nmap", "hydra"]

    def test_current_match_is_marked_differently(self):
        from src.ui.log_viewer import ViewOptions, render_log
        from src.config import ORANGE
        doc = render_log(NEW_FORMAT, ViewOptions(needle="open", current_match=1))
        assert ORANGE in doc.html
        assert doc.matches == 2


class TestLogViewerDialog:
    def _dialog(self, app, path):
        from src.ui.log_viewer import LogViewerDialog
        return LogViewerDialog([path], path)

    def test_shows_the_file_and_its_path(self, app, tmp_path):
        path = tmp_path / "chain_x.log"
        path.write_text(NEW_FORMAT, encoding="utf-8")
        dlg = self._dialog(app, path)
        assert dlg._files.currentText() == "chain_x.log"
        assert str(path) in dlg._meta.text()
        assert "hunter2" in dlg._browser.toPlainText()
        dlg.close()

    def test_timeline_has_one_item_per_visible_command(self, app, tmp_path):
        path = tmp_path / "chain_x.log"
        path.write_text(NEW_FORMAT, encoding="utf-8")
        dlg = self._dialog(app, path)
        assert dlg._timeline.count() == 3
        assert "FAILED" in dlg._timeline.item(1).text()
        dlg.close()

    def test_stats_line_has_totals(self, app, tmp_path):
        path = tmp_path / "chain_x.log"
        path.write_text(NEW_FORMAT, encoding="utf-8")
        dlg = self._dialog(app, path)
        assert "3 commands" in dlg._stats.text()
        assert "1 failed" in dlg._stats.text()
        dlg.close()

    def test_filter_chip_narrows_the_timeline(self, app, tmp_path):
        path = tmp_path / "chain_x.log"
        path.write_text(NEW_FORMAT, encoding="utf-8")
        dlg = self._dialog(app, path)
        dlg._mode_buttons["failed"].click()
        assert dlg._timeline.count() == 2
        dlg._mode_buttons["all"].click()
        assert dlg._timeline.count() == 3
        dlg.close()

    def test_search_counter_and_navigation(self, app, tmp_path):
        path = tmp_path / "chain_x.log"
        path.write_text(NEW_FORMAT, encoding="utf-8")
        dlg = self._dialog(app, path)
        dlg._search.setText("open")
        dlg._render()
        assert dlg._counter.text() == "1 / 2"
        dlg.find_next()
        assert dlg._counter.text() == "2 / 2"
        dlg.find_next()
        assert dlg._counter.text() == "1 / 2"
        dlg.find_previous()
        assert dlg._counter.text() == "2 / 2"
        dlg.close()

    def test_no_matches_shows_zero(self, app, tmp_path):
        path = tmp_path / "chain_x.log"
        path.write_text(NEW_FORMAT, encoding="utf-8")
        dlg = self._dialog(app, path)
        dlg._search.setText("zzz-not-here")
        dlg._render()
        assert dlg._counter.text() == "0 / 0"
        dlg.close()

    def test_invalid_regex_is_shown_in_status(self, app, tmp_path):
        path = tmp_path / "chain_x.log"
        path.write_text(NEW_FORMAT, encoding="utf-8")
        dlg = self._dialog(app, path)
        dlg._regex.setChecked(True)
        dlg._search.setText("(")
        dlg._render()
        assert "invalid pattern" in dlg._status.text()
        dlg.close()

    def test_opening_another_file_switches_the_view(self, app, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QFileDialog
        first = tmp_path / "chain_a.log"
        second = tmp_path / "notes.txt"
        first.write_text(NEW_FORMAT, encoding="utf-8")
        second.write_text("plain text only\n", encoding="utf-8")
        from src.ui.log_viewer import LogViewerDialog
        dlg = LogViewerDialog([first], first)
        monkeypatch.setattr(QFileDialog, "getOpenFileName",
                            staticmethod(lambda *a, **k: (str(second), "")))
        dlg._open_file()
        assert dlg._files.currentText() == "notes.txt"
        assert "plain text only" in dlg._browser.toPlainText()
        assert dlg._timeline.count() == 0
        dlg.close()

    def test_missing_file_is_reported(self, app, tmp_path):
        from src.ui.log_viewer import LogViewerDialog
        dlg = LogViewerDialog([tmp_path / "gone.log"], tmp_path / "gone.log")
        assert "Could not read this file." in dlg._browser.toPlainText()
        dlg.close()

    def test_empty_directory_gives_a_message(self, app):
        from src.ui.log_viewer import LogViewerDialog
        dlg = LogViewerDialog([])
        assert "No log files yet." in dlg._browser.toPlainText()
        dlg.close()


class TestFindLogs:
    def test_finds_results_logs_and_legacy_root_logs(self, tmp_path):
        from src.ui.log_viewer import find_logs
        (tmp_path / "results" / "logs").mkdir(parents=True)
        (tmp_path / "results" / "logs" / "chain_new.log").write_text("x", encoding="utf-8")
        (tmp_path / "chain_old.log").write_text("x", encoding="utf-8")
        (tmp_path / "scan_old.log").write_text("x", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
        names = sorted(p.name for p in find_logs(tmp_path))
        assert names == ["chain_new.log", "chain_old.log", "scan_old.log"]


class TestLargeLogs:
    def test_huge_log_render_is_bounded(self):
        import time
        from src.ui.log_viewer import RENDER_LIMIT, render_log
        block = ("# 2026-10-29T01:00:00.000000 exit=0\n$ nmap -sV 10.0.0.5\n"
                 + "22/tcp open  ssh\nplain output line\n" * 40 + "\n")
        text = block * 800
        started = time.monotonic()
        doc = render_log(text)
        elapsed = time.monotonic() - started
        assert doc.truncated is True
        assert doc.total_lines > RENDER_LIMIT
        assert elapsed < 10
        assert len(doc.html) < 5_000_000

    def test_small_log_is_not_truncated(self):
        from src.ui.log_viewer import render_log
        assert render_log(NEW_FORMAT).truncated is False
