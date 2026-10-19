# PP-Reconnaissance-tools

## What this app does

PP-Reconnaissance-tools is a desktop app that helps you run common network scans and tests. It wraps the tools in a guided wizard, a command preview, and an approval step, so you always see what will run before it runs.

**Use it only on systems you have permission to test**, such as your own lab machines.

## Features

- **Wizard** — enter a target, run a scan, pick steps from a ranked plan, and approve each step.
- **Direct Tool Mode** — choose or type a command, see the preview, then approve it.
- **Basic scan presets** — ready-made nmap scans (quick scan, common services, web ports, and more).
- **Results** — open ports, detected services, and any login found.
- **Wordlists** — use your own password lists. Save a file into the shared folder from Settings.
- **Logs** — view or clear the wizard's run logs from Settings.
- **AI helper (optional)** — suggests one nmap command for a goal. It never runs by itself.
- **OpenCode (optional)** — an AI agent that works inside the tool container.

## How it keeps things safe

- **Tools run in Docker, not on your computer.** The container is locked down: read-only, limited permissions, and it only sees the results folder and the wordlists folder.
- **Only 6 tools are allowed:** nmap, masscan, hydra, ncrack, ncat and evil-winrm. Anything else is refused.
- **Shell tricks are blocked.** Characters like `;`, `&&`, `|` and `$( )` in targets or commands are refused.
- **You approve every command.** Each one shows the tool, the target, what it does, the flags and a rough noise level. It runs only when you click **Run** (or **Yes**).
- **Logs are kept.** Wizard runs are saved in `chain_wizard/` and you can clear them from Settings.

## Known limits

- **The target scope check is not enforced right now.** The app can run against any target you type, so checking that you are allowed to test it is your responsibility.
- **Stop does not always stop a running tool.** A brute-force tool can keep running inside the container after you press Stop.
- **OpenCode does not show the preview step.** It is protected only by the Docker container.
- **The AI helper needs setup.** It needs the `llm` command and an API key before it can suggest commands.

## How to Run / Setup

**Requirements:** Linux (Kali, Debian or Ubuntu), Python 3.10+, and internet access for the first install.

### Linux (Kali / Debian / Ubuntu)

**One command** (asks for your `sudo` password; run it in a real terminal):
```bash
curl -fsSL https://raw.githubusercontent.com/Daimond99/PP-Reconnaissance-tools/for-linux-version/install.sh | bash
```
It installs Docker, builds the tool container, clones the repo to `~/PP-Reconnaissance-tools`, and sets up a Python venv. Safe to run again.

**Step by step**
```bash
# 1. Get the code
git clone --branch for-linux-version https://github.com/Daimond99/PP-Reconnaissance-tools.git
cd PP-Reconnaissance-tools

# 2. Install Docker (the apt package, not Docker Desktop)
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"    # then open a NEW terminal

# 3. Libraries the GUI's terminal needs
sudo apt-get install -y \
    libnss3 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libxkbcommon0 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
    libxshmfence1

# 4. Build and start the tool container (needs internet on the first build)
chmod +x docker/run.sh
./docker/run.sh

# 5. Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 6. Start the app
.venv/bin/python -m src.main
```

**Check that everything is ready** (optional):
```bash
.venv/bin/python -m src.preflight
```

**The tools run inside Docker, not on your computer.** nmap, masscan, hydra, ncrack, ncat and evil-winrm live only in the `therecon-tools` container. The container is read-only, has minimal Linux capabilities, and only sees the results folder and the wordlists folder described below.

#### Wordlists

`docker/run.sh` shares **one folder** with the container, read-only, at `/results/wordlists`. Default folder:
`~/Downloads/rockyou.txt-main`

- To use another folder: `THERECON_WORDLISTS=/path/to/folder ./docker/run.sh`
- Files you copy into that folder appear in the container straight away (no restart).
- Or use **Settings → Save Wordlist to Shared Folder…** in the app to copy a file there.
- Your home folder and `Downloads` are **not** shared as a whole.

#### Troubleshooting

- **`permission denied` when using docker:** you must open a new terminal (or log out and back in) after `usermod -aG docker`.
- **The build fails at the OpenCode step (`curl https://opencode.ai/install`):** the first build needs internet access. If it still fails, the image is not rebuilt.
- **`run.sh` removes the old container before it builds.** If the build fails, the old container is also gone. Check with `docker ps -a`. Once the build works again, run `./docker/run.sh` to create the container again.
- **OpenCode shows `cannot open shared object file` / OpenTUI error:** run it with the container's temporary folder: `docker exec -it -e TMPDIR=/opt/oc-tmp therecon-tools /home/recon/.opencode/bin/opencode`. The normal `run.sh` sets this for you, so re-create the container with `./docker/run.sh` if it is an older one.

## Disclaimer

**For educational use in isolated lab environments only.** TheRecon wraps offensive-security tooling (network scanners, credential brute-forcers, remote-shell clients). Running these against systems you do not own or do not have **written** authorization to test is illegal in most jurisdictions. The default `AUTHORIZED_SCOPE = 192.168.1.0/24` reflects a home-lab assumption — reconfigure or self-host in an isolated VLAN, and the authors accept no liability for misuse.
