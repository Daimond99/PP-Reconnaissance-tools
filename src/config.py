"""Recon Tool — configuration entry point.

Visual layer (window constants, color palette, STYLESHEET, terminal
fonts) lives in `src/theme.py` and is re-exported here so existing
`from src.config import ...` imports are unchanged. This module itself
now holds only the resource-driven command/warhead data and the
authorized-scope default.
"""

from src.theme import (  # re-exported: theme split out of config 2026-08-07
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT, BG, BG_DARKER, PANEL,
    PANEL_LIGHT, PURPLE, PURPLE_DIM, PURPLE_SOFT,
    BLUE, TEXT, TEXT_DIM, BORDER,
    CONSOLE_BG, CONSOLE_TEXT, BG_APP, BG_PANEL_2,
    BG_INPUT, BORDER_SOFT, TEXT_MUTE, ORANGE,
    TERM_BG, TERM_BAR, TERM_MUTE, ACCENT_GREEN,
    ACCENT_RED, STYLESHEET, TERMINAL_FONT_FAMILY, TERMINAL_FONT_SIZE,
    TERMINAL_PROMPT,
)

# ============================================================================
# COMMANDS - คำสั่งและ Profiles
# ============================================================================

# Both loaded from src/resources/*.json (resource-driven, per the
# architecture rule in CLAUDE.md) instead of hardcoded here. load_json()
# degrades to {} on a missing/malformed file rather than crashing, so a
# corrupt resource just means an empty tool/warhead list, not a startup
# crash.
from src.utils.resource_loader import load_json as _load_json

TOOL_COMMANDS = _load_json("tool_commands.json").get("commands", {})

# Warhead profiles are per-tool (2 stealth / 2 critical / 2 quality-normal
# each), one JSON file per tool under src/resources/warheads/ — same
# per-tool-subfolder convention as nmap/flag_impacts.json. WARHEAD_BY_TOOL
# drives the WARHEAD PROFILE combo, re-populated whenever the TOOLS combo
# changes (src/ui/widgets.py TopBar). WARHEAD_COMMANDS is the flattened
# lookup `_on_warhead_change` uses to resolve a picked profile name to its
# command — safe to flatten since every profile name is already
# tool-prefixed and therefore unique across tools.
_WARHEAD_FILES = {
    "Nmap": "warheads/nmap.json",
    "Masscan": "warheads/masscan.json",
    "Ncat": "warheads/ncat.json",
    "Hydra": "warheads/hydra.json",
    "Ncrack": "warheads/ncrack.json",
    "Evil-WinRM": "warheads/evil-winrm.json",
}
WARHEAD_BY_TOOL = {tool: _load_json(path) for tool, path in _WARHEAD_FILES.items()}
WARHEAD_COMMANDS = {
    profile: cmd
    for tool_profiles in WARHEAD_BY_TOOL.values()
    for profile, cmd in tool_profiles.items()
}

OPERATION_MODES = ["Wizard Mode", "Direct Tool Mode"]

# ============================================================================
# SCOPE - authorized test range
# ============================================================================

# Sandbox/lab scope used by the Confirmation Gate's default scope check.
# Direct Tool Mode passes skip_scope=True (the user types their own lab IP),
# so this is the fallback default only.
AUTHORIZED_SCOPE = "192.168.1.0/24"

# Public API — theme names are re-exported from src/theme.py (see import above).
__all__ = [
    "WINDOW_TITLE", "WINDOW_WIDTH", "WINDOW_HEIGHT", "WINDOW_MIN_WIDTH",
    "WINDOW_MIN_HEIGHT", "BG", "BG_DARKER", "PANEL",
    "PANEL_LIGHT", "PURPLE", "PURPLE_DIM", "PURPLE_SOFT",
    "BLUE", "TEXT", "TEXT_DIM", "BORDER",
    "CONSOLE_BG", "CONSOLE_TEXT", "BG_APP", "BG_PANEL_2",
    "BG_INPUT", "BORDER_SOFT", "TEXT_MUTE", "ORANGE",
    "TERM_BG", "TERM_BAR", "TERM_MUTE", "ACCENT_GREEN",
    "ACCENT_RED", "STYLESHEET", "TERMINAL_FONT_FAMILY", "TERMINAL_FONT_SIZE",
    "TERMINAL_PROMPT", "TOOL_COMMANDS", "WARHEAD_BY_TOOL", "WARHEAD_COMMANDS",
    "OPERATION_MODES", "AUTHORIZED_SCOPE",
]
