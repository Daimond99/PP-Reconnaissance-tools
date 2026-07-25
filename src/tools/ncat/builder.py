"""
Ncat Command Builder — placeholder.
Builders never execute commands (docs/Resource System.md).

Ncat command construction currently lives inline in the UI wizard layer
(src/ui/tool_selection.py, connect/listen mode). This module exists to
preserve architectural consistency; extracting the real logic here is a
future refactor, not a Windows Demo limitation.
"""

from __future__ import annotations


class NcatBuilder:
    """
    Placeholder builder.

    Command construction currently lives in src/ui/tool_selection.py.
    TODO: extract build_ncat_command(...) into this module.
    """
    pass
