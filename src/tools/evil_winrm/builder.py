"""
Evil-WinRM Command Builder — placeholder.
Builders never execute commands (docs/Resource System.md).

Note: package directory is "evil_winrm" (underscore) because Python package
names cannot contain a hyphen; the tool name displayed to users remains
"evil-winrm" everywhere else (src/config.py, src/ui/tool_selection.py).

Evil-WinRM command construction currently lives inline in the UI wizard
layer (src/ui/tool_selection.py, target/username/password flow, using
ConfirmationGate(argv_override=...) to keep the real password out of the
preview/audit log). This module exists to preserve architectural
consistency; extracting the real logic here is a future refactor, not a
Windows Demo limitation.
"""

from __future__ import annotations


class EvilWinRMBuilder:
    """
    Placeholder builder.

    Command construction currently lives in src/ui/tool_selection.py.
    TODO: extract build_evil_winrm_command(...) into this module.
    """
    pass
