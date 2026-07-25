"""
Ncrack Command Builder — placeholder.
Builders never execute commands (docs/Resource System.md).

Ncrack command construction currently lives inline in the UI wizard layer
(src/ui/tool_selection.py, stability-warning + target/protocol/userlist/
passlist flow). This module exists to preserve architectural consistency;
extracting the real logic here is a future refactor, not a Windows Demo
limitation.
"""

from __future__ import annotations


class NcrackBuilder:
    """
    Placeholder builder.

    Command construction currently lives in src/ui/tool_selection.py.
    TODO: extract build_ncrack_command(...) into this module.
    """
    pass
