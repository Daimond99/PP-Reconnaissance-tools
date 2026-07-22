# TheRecon

**Network Reconnaissance Console** — A desktop GUI for orchestrating security reconnaissance workflows with guided wizards and direct tool access.

Built with **Python** and **PyQt5**, TheRecon provides a unified console for network scanning, credential testing, and Windows post-exploitation tooling. It supports both **Wizard Mode** (step-by-step attack chain guidance) and **Direct Tool Mode** (manual command execution).

> ⚠️ **Legal Notice:** This tool is intended for **authorized security testing and educational purposes only**. Always obtain explicit permission before scanning or testing any system you do not own. Unauthorized use may violate applicable laws.

---

## Features

| Feature | Description |
|---------|-------------|
| **Wizard Mode** | Interactive, step-by-step attack chain builder inspired by Hydra wizard workflows |
| **Direct Tool Mode** | One-click access to pre-configured commands for each supported tool |
| **Warhead Profiles** | Pre-built scan profiles: Stealth Recon, Full Aggressive, Web Focus, Vulnerability Scan |
| **Tool Manager** | Automatic detection of installed tools with version info and install guides |
| **Cross-Platform** | Runs on Windows and Linux with platform-specific install instructions |
| **Modern UI** | Frameless dark-theme console with sidebar navigation and integrated terminal |

---

## Supported Tools

| Category | Tools |
|----------|-------|
| Network Scanner | [Nmap](https://nmap.org/), [Masscan](https://github.com/robertdavidgraham/masscan) |
| Connection | [Ncat](https://nmap.org/ncat/) |
| Password Attack | [Hydra](https://github.com/vanhauser-thc/thc-hydra), [Ncrack](https://nmap.org/ncrack/) |
| Windows Attack | [Evil-WinRM](https://github.com/Hackplayers/evil-winrm) |

The application detects which tools are installed on your system at startup and provides installation guidance for missing dependencies.

---

## Requirements

- **Python** 3.8 or later
- **Pyside6**
- External security tools (Nmap, Masscan, etc.) — installed separately on your system

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Daimond99/TheRecon.git
cd TheRecon
```

### 2. Create a virtual environment (recommended)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install external tools

Install the security tools you need for your workflow. TheRecon will detect them automatically. Example on Debian/Ubuntu:

```bash
sudo apt install nmap masscan hydra ncrack
sudo gem install evil-winrm
```

---

## Usage

Launch the application from the project root:

```bash
python -m src.main
```

### Operation Modes

**Wizard Mode** — Follow guided prompts to configure a full attack chain:
1. Define target (IP, CIDR, or hostname)
2. Select scan type (Web, SSH, Windows, Database, Full Network, Custom)
3. Choose and configure tools
4. Set credentials and output options
5. Preview and execute the generated command

**Direct Tool Mode** — Select a tool from the sidebar and run pre-configured commands directly in the console.

**Warhead Profiles** — Apply one of four built-in scan profiles from the top bar for quick reconnaissance.

---

## Project Structure

```
TheRecon/
├── src/
│   ├── main.py              # Application entry point
│   ├── config.py            # UI theme, constants, and command profiles
│   ├── ui/
│   │   ├── main_window.py   # Main window and layout
│   │   └── widgets.py       # Reusable UI components (Sidebar, TopBar, Console)
│   └── core/
│       ├── wizard_engine.py # Interactive wizard state machine
│       └── tool_manager.py  # Tool detection and install guidance
├── requirements.txt
└── README.md
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   ReconMainWindow                     │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ Sidebar  │  │   TopBar     │  │ MainContentArea│ │
│  │ (Tools)  │  │ (Profiles)   │  │ (Console)      │ │
│  └──────────┘  └──────────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────┘
         │                │                  │
         ▼                ▼                  ▼
   ToolManager      config.py         WizardEngine
   (detection)    (commands/profiles)  (attack chain)
```

---

## Development

```bash
# Run from project root
python -m src.main
```

Key modules:
- `src/core/wizard_engine.py` — Wizard step logic, attack type routing, and command generation
- `src/core/tool_manager.py` — Background tool detection with threading
- `src/config.py` — Stylesheet, color palette, and command templates

---

## Contributing

Contributions are welcome. Please open an issue to discuss significant changes before submitting a pull request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## License



---

## Author

**Daimond99** — [GitHub](https://github.com/Daimond99)

---

## Disclaimer

The authors and contributors of TheRecon are not responsible for any misuse or damage caused by this program. Use responsibly and only on systems you are authorized to test.
