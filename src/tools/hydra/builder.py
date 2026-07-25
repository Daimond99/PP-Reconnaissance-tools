"""
Hydra Command Builder — turns validated brute-force inputs into an executable
command string. Builders never execute, parse, or touch the GUI
(docs/ARCHITECTURE.md, Command Builder layer).

Mirrors the classic THC `hydra-wizard.sh` flow: a single login or a login list
(-l/-L), a single password or a password list (-p/-P), optional port (-s) and
"try login as password / null / reversed" extras (-e nsr), then the service
module as the final argument.

No Windows-native hydra binary exists, so on Windows this command is executed
through WSL by the caller — that routing is an execution concern, not a
build-time one, so this module always emits a plain `hydra ...` command.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class HydraSpec:
    """Validated inputs for one hydra run."""
    target: str
    service: str                       # ssh, ftp, http-get, smtp, ...
    login: str                         # single username or a path to a userlist
    login_is_file: bool                # True -> -L, False -> -l
    password: str                      # single password or a path to a passlist
    password_is_file: bool             # True -> -P, False -> -p
    port: Optional[str] = None         # -s <port>
    extra: str = ""                    # letters for -e, e.g. "nsr"
    extra_flags: List[str] = field(default_factory=list)


def _argv(spec: HydraSpec, mask_password: bool = False) -> List[str]:
    argv: List[str] = ["hydra"]

    argv += (["-L", spec.login] if spec.login_is_file else ["-l", spec.login])

    if mask_password and not spec.password_is_file:
        argv += ["-p", "********"]
    else:
        argv += (["-P", spec.password] if spec.password_is_file else ["-p", spec.password])

    if spec.port:
        argv += ["-s", str(spec.port)]
    if spec.extra:
        argv += ["-e", spec.extra]
    argv += spec.extra_flags
    argv += [spec.target, spec.service]
    return argv


def build_hydra_argv(spec: HydraSpec) -> List[str]:
    """The real argv that gets executed (real password included)."""
    return _argv(spec, mask_password=False)


def build_hydra_command(spec: HydraSpec, mask_password: bool = True) -> str:
    """A display/audit command string. By default the single-password value is
    masked so the real secret is never shown in the preview box or audit log
    (a passlist *file path* is not secret, so it is left visible)."""
    return " ".join(shlex.quote(tok) for tok in _argv(spec, mask_password=mask_password))
