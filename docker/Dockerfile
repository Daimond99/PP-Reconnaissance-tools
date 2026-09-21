# TheRecon tool container — the 6 authorized tools (nmap, masscan, hydra,
# ncrack, ncat, evil-winrm) plus the OpenCode agent CLI (added 2026-08-29,
# see docs/List การเเก้ไข.md item 6), all isolated from the WSL2/Windows host.
#
# Least-privilege by design:
# - runs as non-root `recon` user; nmap/masscan need raw sockets, which
#   Debian/Ubuntu's nmap build only grants via a real root UID (its libcap
#   check didn't accept file-capability-only, non-root processes when
#   tested here — verified: `setcap ...+eip` on the binary alone was NOT
#   enough, `docker exec -u root` scanning worked, `docker exec` as recon
#   with the same file capability still refused). Falls back to a sudoers
#   rule scoped to exactly those two binaries, NOPASSWD (no interactive
#   tty across `docker exec`) instead of a general root shell — matches
#   what the GUI already generates (tool_commands.json's "sudo nmap ...").
# - cap-drop=ALL + cap-add=NET_RAW,NET_ADMIN at `docker run` time (see
#   docker/run.sh) still bounds what that sudo'd root can do networking-wise,
#   even though sudo itself grants full in-container root.
# - no package here ever needs anything beyond that scoped sudo rule.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# No bundled wordlist — Ubuntu's repos don't carry Kali's `wordlists`
# package (rockyou.txt etc). The run script mounts the host's own
# wordlist directory into /results/wordlists instead of baking one in.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nmap \
        ncat \
        masscan \
        hydra \
        ncrack \
        ruby ruby-dev build-essential libssl-dev \
        ca-certificates \
        curl unzip \
        sudo \
    && rm -rf /var/lib/apt/lists/*

RUN gem install evil-winrm --no-document

RUN useradd -m -s /bin/bash recon \
    && mkdir -p /results \
    && chown recon:recon /results

# OpenCode agent CLI — installed as `recon` (not root) so its own binary and
# any first-run files land under /home/recon, same ownership as everything
# else that user touches. Runs *inside* this container from here on (see
# docs/List การเเก้ไข.md item 6 / src/ui/terminal_launch.py::_opencode_launch)
# instead of on the WSL host with a soft PATH-scoping trick — this
# container's own filesystem + installed binaries + scoped sudoers rule
# below ARE its sandbox now, a real boundary instead of a restricted PATH.
USER recon
RUN curl -fsSL https://opencode.ai/install | bash
ENV PATH="/home/recon/.opencode/bin:${PATH}"
USER root

# curl/unzip were only needed to fetch the OpenCode installer above — drop
# them same as the ruby build toolchain, nothing else in this image needs
# network access or an archive tool of its own.
RUN apt-get update \
    && apt-get purge -y ruby-dev build-essential curl unzip \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Scoped sudo — exactly nmap and masscan, nothing else, no password prompt
# (docker exec has no interactive tty for sudo to prompt on). `recon`
# cannot sudo any other command, so this is not a general root shell.
RUN echo "recon ALL=(root) NOPASSWD: /usr/bin/nmap, /usr/bin/masscan" \
        > /etc/sudoers.d/recon-tools \
    && chmod 440 /etc/sudoers.d/recon-tools

USER recon
WORKDIR /results

# Kept alive for `docker exec` — the app never runs anything via
# `docker run`'s own CMD, every real invocation is a separate `docker exec`
# against this long-lived container (see docker/run.sh).
CMD ["sleep", "infinity"]
