from __future__ import annotations

import copy

from src.utils import resource_loader
from src.utils.resource_loader import load_json, save_json
from src.validation.common import parse_command_line

CUSTOM_RESOURCE = "warheads/custom.json"

PROGRAM_BY_TOOL = {
    "Nmap": "nmap",
    "Masscan": "masscan",
    "Ncat": "ncat",
    "Hydra": "hydra",
    "Ncrack": "ncrack",
    "Evil-WinRM": "evil-winrm",
}

MAX_NAME_LENGTH = 60
MAX_COMMAND_LENGTH = 400


def validate_profile(tool: str, name: str, command: str, taken: set[str]) -> list[str]:
    errors: list[str] = []
    program = PROGRAM_BY_TOOL.get(tool)
    if program is None:
        errors.append("Pick one of the six tools.")

    name, command = name.strip(), command.strip()
    if not name:
        errors.append("Give the profile a name.")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"The name is longer than {MAX_NAME_LENGTH} characters.")
    elif name in taken:
        errors.append("A profile with this name already exists.")

    if not command:
        errors.append("Enter the command.")
    elif len(command) > MAX_COMMAND_LENGTH:
        errors.append(f"The command is longer than {MAX_COMMAND_LENGTH} characters.")
    else:
        ok, message, argv = parse_command_line(command)
        if not ok:
            errors.append(message)
        elif program is not None:
            program_index = 1 if argv[0].lower() == "sudo" else 0
            if argv[program_index].lower() != program:
                errors.append(f"The command must start with {program}.")
    return errors


def _custom_exists() -> bool:
    return (resource_loader.RESOURCES_ROOT / CUSTOM_RESOURCE).is_file()


def _read_custom() -> dict:
    if not _custom_exists():
        return {}
    data = load_json(CUSTOM_RESOURCE)
    return copy.deepcopy(data) if isinstance(data, dict) else {}


def apply_custom(by_tool: dict, flat: dict) -> None:
    for tool, profiles in _read_custom().items():
        if not isinstance(profiles, dict):
            continue
        for name, command in profiles.items():
            if not isinstance(name, str) or not isinstance(command, str):
                continue
            if name in flat or validate_profile(tool, name, command, set()):
                continue
            by_tool.setdefault(tool, {})[name.strip()] = command.strip()
            flat[name.strip()] = command.strip()


def add_profile(by_tool: dict, flat: dict, tool: str, name: str, command: str) -> list[str]:
    errors = validate_profile(tool, name, command, set(flat))
    if errors:
        return errors
    name, command = name.strip(), command.strip()
    custom = _read_custom()
    custom.setdefault(tool, {})[name] = command
    save_json(CUSTOM_RESOURCE, custom)
    by_tool.setdefault(tool, {})[name] = command
    flat[name] = command
    return []


def custom_profiles() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for tool, profiles in _read_custom().items():
        if isinstance(profiles, dict):
            entries = {name: command for name, command in profiles.items()
                       if isinstance(name, str) and isinstance(command, str)}
            if entries:
                result[tool] = entries
    return result


def _forget(custom: dict, by_tool: dict, flat: dict, tool: str, name: str) -> None:
    profiles = custom.get(tool, {})
    profiles.pop(name, None)
    if not profiles:
        custom.pop(tool, None)
    by_tool.get(tool, {}).pop(name, None)
    flat.pop(name, None)


def delete_profile(by_tool: dict, flat: dict, tool: str, name: str) -> list[str]:
    custom = _read_custom()
    if name not in custom.get(tool, {}):
        return ["Only your own profiles can be deleted."]
    _forget(custom, by_tool, flat, tool, name)
    save_json(CUSTOM_RESOURCE, custom)
    return []


def update_profile(by_tool: dict, flat: dict, old_tool: str, old_name: str,
                   tool: str, name: str, command: str) -> list[str]:
    custom = _read_custom()
    if old_name not in custom.get(old_tool, {}):
        return ["Only your own profiles can be edited."]
    errors = validate_profile(tool, name, command, set(flat) - {old_name})
    if errors:
        return errors
    name, command = name.strip(), command.strip()
    _forget(custom, by_tool, flat, old_tool, old_name)
    custom.setdefault(tool, {})[name] = command
    save_json(CUSTOM_RESOURCE, custom)
    by_tool.setdefault(tool, {})[name] = command
    flat[name] = command
    return []
