"""User-created warhead profiles: validation, saving to a file that is local to
this machine, merging back into the dropdown source, and the dialog that
collects them."""

from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication

from src.core import warhead_store
from src.utils import resource_loader


@pytest.fixture
def resources(tmp_path, monkeypatch):
    root = tmp_path / "resources"
    (root / "warheads").mkdir(parents=True)
    monkeypatch.setattr(resource_loader, "RESOURCES_ROOT", root)
    monkeypatch.setattr(resource_loader, "_cache", {})
    return root


@pytest.fixture
def pools():
    by_tool = {"Nmap": {"Nmap - Built in": "sudo nmap -sS 192.168.1.0/24"}}
    flat = {"Nmap - Built in": "sudo nmap -sS 192.168.1.0/24"}
    return by_tool, flat


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class TestValidation:
    def test_valid_sudo_nmap_profile_passes(self):
        errors = warhead_store.validate_profile(
            "Nmap", "Nmap - Quiet sweep", "sudo nmap -sS -T2 192.168.1.0/24", set())
        assert errors == []

    @pytest.mark.parametrize("tool, command", [
        ("Nmap", "hydra -l admin ssh://192.168.1.1"),
        ("Hydra", "nmap -sV 192.168.1.1"),
        ("Evil-WinRM", "nmap -sV 192.168.1.1"),
    ])
    def test_command_must_match_the_chosen_tool(self, tool, command):
        assert warhead_store.validate_profile(tool, "X", command, set())

    def test_matching_tool_is_accepted(self):
        assert warhead_store.validate_profile(
            "Evil-WinRM", "X", "evil-winrm -i 192.168.1.1 -u admin -p x", set()) == []

    def test_chained_command_is_rejected(self):
        errors = warhead_store.validate_profile("Nmap", "X", "nmap -sV 192.168.1.1; ls", set())
        assert errors

    def test_newline_is_rejected(self):
        errors = warhead_store.validate_profile("Nmap", "X", "nmap -sV 192.168.1.1\nls", set())
        assert errors

    def test_program_outside_the_six_tools_is_rejected(self):
        errors = warhead_store.validate_profile("Nmap", "X", "curl http://192.168.1.1", set())
        assert errors

    def test_empty_name_and_command_are_rejected(self):
        errors = warhead_store.validate_profile("Nmap", "  ", "  ", set())
        assert "Give the profile a name." in errors
        assert "Enter the command." in errors

    def test_duplicate_name_is_rejected(self):
        errors = warhead_store.validate_profile(
            "Nmap", "Taken", "nmap -sV 192.168.1.1", {"Taken"})
        assert "A profile with this name already exists." in errors

    def test_unknown_tool_is_rejected(self):
        errors = warhead_store.validate_profile("Metasploit", "X", "nmap 192.168.1.1", set())
        assert errors

    def test_overlong_command_is_rejected(self):
        command = "nmap " + "-sV " * 200 + "192.168.1.1"
        errors = warhead_store.validate_profile("Nmap", "X", command, set())
        assert any("longer" in error for error in errors)


class TestSaving:
    def test_add_writes_the_file_and_updates_both_lookups(self, resources, pools):
        by_tool, flat = pools
        errors = warhead_store.add_profile(
            by_tool, flat, "Nmap", "Nmap - Weekend", "nmap -sS 192.168.1.1")
        assert errors == []
        saved = json.loads((resources / "warheads" / "custom.json").read_text(encoding="utf-8"))
        assert saved == {"Nmap": {"Nmap - Weekend": "nmap -sS 192.168.1.1"}}
        assert by_tool["Nmap"]["Nmap - Weekend"] == "nmap -sS 192.168.1.1"
        assert flat["Nmap - Weekend"] == "nmap -sS 192.168.1.1"

    def test_second_add_keeps_the_first(self, resources, pools):
        by_tool, flat = pools
        warhead_store.add_profile(by_tool, flat, "Nmap", "One", "nmap -sV 192.168.1.1")
        warhead_store.add_profile(by_tool, flat, "Hydra", "Two", "hydra ssh://192.168.1.1")
        saved = json.loads((resources / "warheads" / "custom.json").read_text(encoding="utf-8"))
        assert saved["Nmap"] == {"One": "nmap -sV 192.168.1.1"}
        assert saved["Hydra"] == {"Two": "hydra ssh://192.168.1.1"}

    def test_invalid_add_writes_nothing(self, resources, pools):
        by_tool, flat = pools
        errors = warhead_store.add_profile(by_tool, flat, "Nmap", "Bad", "rm -rf /")
        assert errors
        assert not (resources / "warheads" / "custom.json").exists()
        assert "Bad" not in flat

    def test_duplicate_add_is_refused(self, resources, pools):
        by_tool, flat = pools
        warhead_store.add_profile(by_tool, flat, "Nmap", "Same", "nmap -sV 192.168.1.1")
        errors = warhead_store.add_profile(by_tool, flat, "Nmap", "Same", "nmap -sS 192.168.1.1")
        assert errors


class TestApplyOnStartup:
    def test_missing_file_is_quiet(self, resources, pools):
        by_tool, flat = pools
        before = dict(flat)
        warhead_store.apply_custom(by_tool, flat)
        assert flat == before

    def test_saved_profiles_come_back_after_restart(self, resources, pools):
        by_tool, flat = pools
        warhead_store.add_profile(by_tool, flat, "Nmap", "Saved", "nmap -sV 192.168.1.1")
        fresh_by_tool = {"Nmap": {"Nmap - Built in": "sudo nmap -sS 192.168.1.0/24"}}
        fresh_flat = {"Nmap - Built in": "sudo nmap -sS 192.168.1.0/24"}
        warhead_store.apply_custom(fresh_by_tool, fresh_flat)
        assert fresh_flat["Saved"] == "nmap -sV 192.168.1.1"
        assert fresh_by_tool["Nmap"]["Saved"] == "nmap -sV 192.168.1.1"

    def test_bad_or_duplicate_entries_in_the_file_are_skipped(self, resources, pools):
        by_tool, flat = pools
        (resources / "warheads" / "custom.json").write_text(json.dumps({
            "Nmap": {
                "Nmap - Built in": "nmap -sV 192.168.1.9",
                "Evil": "rm -rf /",
                "Good": "nmap -sV 192.168.1.9",
                "Number": 7,
            },
            "Hydra": "not a dict",
        }), encoding="utf-8")
        warhead_store.apply_custom(by_tool, flat)
        assert flat["Nmap - Built in"] == "sudo nmap -sS 192.168.1.0/24"
        assert "Evil" not in flat
        assert flat["Good"] == "nmap -sV 192.168.1.9"
        assert "Number" not in flat


class TestDialog:
    def test_prefills_the_tool_template_and_enables_save(self, app):
        from src.ui.widgets.warhead_dialog import AddWarheadDialog
        from src.core.warhead_store import validate_profile
        dlg = AddWarheadDialog(["Nmap", "Hydra"], "Nmap", set())
        assert dlg.command.startswith("sudo nmap") or dlg.command.startswith("nmap")
        dlg._name.setText("Dialog profile")
        save = dlg._buttons.button(dlg._buttons.StandardButton.Save)
        assert save.isEnabled() == (validate_profile("Nmap", "Dialog profile", dlg.command, set()) == [])
        dlg.close()

    def test_save_stays_disabled_until_valid(self, app):
        from src.ui.widgets.warhead_dialog import AddWarheadDialog
        dlg = AddWarheadDialog(["Nmap"], "Nmap", set())
        save = dlg._buttons.button(dlg._buttons.StandardButton.Save)
        dlg._name.setText("")
        assert not save.isEnabled()
        dlg._name.setText("Ready")
        assert save.isEnabled()
        dlg._command.setText("curl http://x")
        assert not save.isEnabled()
        dlg.close()

    def test_switching_tool_refreshes_the_template_until_edited(self, app):
        from src.ui.widgets.warhead_dialog import AddWarheadDialog
        dlg = AddWarheadDialog(["Nmap", "Hydra"], "Nmap", set())
        dlg._tool.setCurrentText("Hydra")
        assert dlg.command.startswith("hydra")
        dlg._command.setText("hydra -l root ssh://192.168.1.1")
        dlg._tool.setCurrentText("Nmap")
        assert dlg.command == "hydra -l root ssh://192.168.1.1"
        dlg.close()


class TestTopBarButton:
    def test_plus_button_emits_add_request(self, app):
        from src.ui.widgets.topbar import TopBar
        bar = TopBar()
        seen = []
        bar.addProfileRequested.connect(lambda: seen.append(True))
        bar.add_profile_btn.click()
        assert seen == [True]
        bar.close()


class TestMainWindowWiring:
    def test_accepted_dialog_saves_and_selects_the_new_profile(self, app, resources, monkeypatch):
        from src.ui import main_window as mw

        class _FakeDialog:
            DialogCode = mw.AddWarheadDialog.DialogCode
            tool = "Hydra"
            name = "Wiring check profile"
            command = "hydra -l root ssh://192.168.1.1"

            def __init__(self, *args, **kwargs):
                pass

            def exec(self):
                return self.DialogCode.Accepted

        monkeypatch.setattr(mw, "AddWarheadDialog", _FakeDialog)
        window = mw.ReconMainWindow()
        window._on_add_profile()
        top = window.top_bar
        assert top.tool_combo.currentText() == "Hydra"
        assert top.warhead_combo.currentText() == "Wiring check profile"
        assert "hydra -l root" in top.command_input.text()
        assert (resources / "warheads" / "custom.json").is_file()


class TestEditAndDelete:
    def test_custom_profiles_lists_only_user_entries(self, resources, pools):
        by_tool, flat = pools
        warhead_store.add_profile(by_tool, flat, "Nmap", "Mine", "nmap -sV 192.168.1.1")
        assert warhead_store.custom_profiles() == {"Nmap": {"Mine": "nmap -sV 192.168.1.1"}}

    def test_update_renames_and_moves_tool(self, resources, pools):
        by_tool, flat = pools
        warhead_store.add_profile(by_tool, flat, "Nmap", "Old", "nmap -sV 192.168.1.1")
        errors = warhead_store.update_profile(by_tool, flat, "Nmap", "Old",
                                              "Hydra", "New", "hydra ssh://192.168.1.1")
        assert errors == []
        assert "Old" not in flat and "New" in flat
        assert "New" in by_tool["Hydra"] and "Old" not in by_tool["Nmap"]
        assert warhead_store.custom_profiles() == {"Hydra": {"New": "hydra ssh://192.168.1.1"}}

    def test_update_keeps_the_same_name_without_conflict(self, resources, pools):
        by_tool, flat = pools
        warhead_store.add_profile(by_tool, flat, "Nmap", "Same", "nmap -sV 192.168.1.1")
        errors = warhead_store.update_profile(by_tool, flat, "Nmap", "Same",
                                              "Nmap", "Same", "nmap -sS 192.168.1.1")
        assert errors == []
        assert flat["Same"] == "nmap -sS 192.168.1.1"

    def test_update_rejects_invalid_command_and_keeps_old(self, resources, pools):
        by_tool, flat = pools
        warhead_store.add_profile(by_tool, flat, "Nmap", "Keep", "nmap -sV 192.168.1.1")
        errors = warhead_store.update_profile(by_tool, flat, "Nmap", "Keep",
                                              "Nmap", "Keep", "nmap -sV 1; rm -rf /")
        assert errors
        assert flat["Keep"] == "nmap -sV 192.168.1.1"
        assert warhead_store.custom_profiles()["Nmap"]["Keep"] == "nmap -sV 192.168.1.1"

    def test_built_in_profiles_cannot_be_edited_or_deleted(self, resources, pools):
        by_tool, flat = pools
        assert warhead_store.update_profile(by_tool, flat, "Nmap", "Nmap - Built in",
                                            "Nmap", "X", "nmap -sV 192.168.1.1")
        assert warhead_store.delete_profile(by_tool, flat, "Nmap", "Nmap - Built in")
        assert "Nmap - Built in" in flat

    def test_delete_removes_from_file_and_lookups(self, resources, pools):
        by_tool, flat = pools
        warhead_store.add_profile(by_tool, flat, "Nmap", "Gone", "nmap -sV 192.168.1.1")
        assert warhead_store.delete_profile(by_tool, flat, "Nmap", "Gone") == []
        assert "Gone" not in flat and "Gone" not in by_tool["Nmap"]
        assert warhead_store.custom_profiles() == {}
        assert not (resources / "warheads" / "custom.json").read_text(encoding="utf-8").count("Gone")


class TestEditDialogs:
    def test_edit_mode_prefills_and_keeps_the_saved_command(self, app):
        from src.ui.widgets.warhead_dialog import AddWarheadDialog
        dlg = AddWarheadDialog(["Nmap", "Hydra"], "Nmap", set(),
                               initial=("Hydra", "Mine", "hydra ssh://192.168.1.9"))
        assert dlg.tool == "Hydra"
        assert dlg.name == "Mine"
        assert dlg.command == "hydra ssh://192.168.1.9"
        dlg._tool.setCurrentText("Nmap")
        assert dlg.command == "hydra ssh://192.168.1.9"
        dlg.close()

    def test_manage_dialog_lists_entries_and_enables_actions_on_selection(self, app):
        from src.ui.widgets.warhead_dialog import ManageWarheadDialog
        dlg = ManageWarheadDialog({"Nmap": {"One": "nmap -sV 192.168.1.1"},
                                   "Hydra": {"Two": "hydra ssh://192.168.1.1"}})
        assert dlg._list.count() == 2
        assert not dlg._edit_btn.isEnabled()
        dlg._list.setCurrentRow(1)
        assert dlg._edit_btn.isEnabled() and dlg._delete_btn.isEnabled()
        dlg._choose("delete")
        assert (dlg.action, dlg.tool, dlg.name) == ("delete", "Hydra", "Two")
        dlg.close()

    def test_manage_dialog_empty_state(self, app):
        from src.ui.widgets.warhead_dialog import ManageWarheadDialog
        dlg = ManageWarheadDialog({})
        assert dlg._list.count() == 0
        dlg.close()
