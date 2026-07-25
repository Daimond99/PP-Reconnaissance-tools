# GUI Mission Control — file/page reference map

สร้างไว้เพื่อให้แชทใหม่สั่งแก้ GUI ต่อได้ทันที โดยไม่ต้องไล่โค้ดใหม่ทั้งหมด.
อ้างอิงจาก mockup: `Mockup HTML.txt` (Mission Control — sidebar + mission bar +
terminal chrome + Zenmap-style Results Display). GUI ตอนนี้ **เบี่ยงจาก mockup
โดยเจตนา** ในหลายจุด (ดูหัวข้อท้ายไฟล์) ตามคำสั่งผู้ใช้รอบสองให้ terminal ใช้งาน
จริง ไม่ใช่ mockup.

อัปเดตล่าสุด: 2026-07-26 (รอบสอง). อยู่บน branch `restyle-mission-control-gui`
(ยังไม่ push — เช็ค `git log` ก่อนอ้างว่า commit ไหน apply แล้วบ้าง).

## แผนที่ไฟล์ → ส่วนไหนของ GUI

| ไฟล์ | รับผิดชอบ |
|---|---|
| `src/config.py` | สี/ตัวแปร palette + `STYLESHEET` ทั้งก้อน (object name selectors ทั้งหมด) |
| `src/ui/widgets.py` | Sidebar, TopBar (mission bar), ทุกหน้า (page) ใน `MainContentArea`, helper `wrap_in_terminal()` |
| `src/ui/terminal.py` | **ใหม่** — `InteractiveTerminal`: real shell (bash) ผ่าน `QProcess`, ใช้ทั้งหน้า Raw Output และ LLM Mode |
| `src/ui/main_window.py` | ประกอบหน้าต่างหลัก, title bar (ไม่มี brand/title text แล้ว), Settings popup menu, เชื่อม `Sidebar.navigate` → `MainContentArea.stack` |
| `src/ui/wizard_console.py` | ตรรกะ Wizard Console (ไม่แตะ — ครอบด้วย terminal chrome เท่านั้น) |
| `src/ui/llm_mode.py` | **เลิกใช้ในหน้า LLM Mode แล้ว** — คลาส `LLMModeTab` ยังอยู่ในไฟล์นี้แต่ไม่ import/ใช้ที่ไหนอีก (หน้า LLM Mode ตอนนี้คือ `InteractiveTerminal` เปล่า) |
| `src/ui/tool_selection.py` | **ไม่ใช้ในหน้า sidebar แล้ว** — ไฟล์ยังอยู่ (โค้ด Ncat/Evil-WinRM/Ncrack builder logic ไม่ได้ลบ) แต่ไม่มี tab ในเมนูอีกต่อไป |
| `src/core/confirmation_gate.py` | Gate ยืนยัน "yes" ก่อนรันจริง — ไม่แตะเลย |

## Sidebar (`src/ui/widgets.py` → class `Sidebar`)

- `Sidebar.NAV_ITEMS` — list ข้อความล้วน **ไม่มี emoji/icon glyph แล้ว** 6 รายการ ตามลำดับ index 0–5:
  `0=Wizard Console, 1=Input Management, 2=Command Editor, 3=Raw Output,
  4=Results Display, 5=LLM Mode`. (`Tool Selection` ถูกตัดออกทั้ง sidebar และ stack)
  **ลำดับนี้ต้องตรงกับลำดับ `stack.addWidget(...)` ใน `MainContentArea._build_pages()`**.
- `toggle_collapsed()` — ย่อ/ขยาย sidebar (220px ↔ 64px). ปุ่ม toggle (`self.toggle_btn`)
  ตอนนี้เป็น **SVG icon จริง** (3 ขีด, วาดผ่าน `svg_icon()`) แทน glyph ตัวอักษร `☰` ที่ไม่ขึ้นก่อนหน้านี้.
- Collapsed mode: label ย่อเหลือตัวอักษรแรกของชื่อหน้า (ไม่มี icon glyph ให้ย่อกลับไปแสดงแทน).
- `_select_nav(index)` — emit signal `navigate(int)`, ตั้ง property `selected` บนปุ่มที่ถูกเลือก.
- ปุ่ม Settings ล่างสุด: `self.settings_btn` — **ผูก action แล้ว** ผ่าน `main_window._on_settings_clicked()`
  (ดูหัวข้อ Settings menu ด้านล่าง).

## Mission Bar (`src/ui/widgets.py` → class `TopBar`)

Object attrs ที่ `main_window.py` ผูก signal ไว้ (**ห้ามเปลี่ยนชื่อ attr เหล่านี้**):
`target_input` (ตอนนี้เป็น `QComboBox` editable, ไม่ใช่ `QLineEdit`), `opmode_combo`,
`tool_combo`, `warhead_combo`, `command_input`, `execute_btn`.
**`browse_btn` ถูกลบแล้ว** — ห้ามอ้างอิงอีก.

- Row 1: Target / Operation Mode / Tool-Scanner / Warhead Profile.
  - **Target ไม่มีปุ่ม Browse อีกต่อไป** — เปลี่ยนเป็น editable `QComboBox`
    (object name `MissionCombo`) ที่มีลูกศร dropdown ในตัว, เก็บ **ประวัติ target
    ที่เคย execute ไปแล้ว** (`add_target_history()` เรียกจาก `main_window._on_execute_clicked()`
    ก่อนรันทุกครั้ง). ใช้ `TopBar.target_text()` แทนการอ่าน `.text()` ตรงๆ
    (เพราะตอนนี้เป็น combo ไม่ใช่ line edit).
  - Label object name `MissionFieldLabel` — สไตล์แบนแล้ว (ตัด letter-spacing/shadow ออก, ตัวอักษรล้วน).
- Row 2: `command_input` (object name `CmdPreview`, แก้ไขได้จริง) + `execute_btn`
  (ปุ่มเล็กลง — padding/font ลดตาม theme "compact" แบบ Claude Desktop).
- `_on_execute_clicked()` ใน `main_window.py` อ่าน `command_input.text()` ยิงเข้า
  `ConfirmationGate` **และ** เรียก `self.top_bar.add_target_history(self._get_target())`
  ก่อนรัน — ไม่แตะ logic core ตรงนี้เวลาสไตล์ mission bar ต่อ.
- `_get_target()` เปลี่ยนจาก `.target_input.text()` เป็น `.top_bar.target_text()`.

## หน้า/แท็บทั้งหมด (`MainContentArea._build_pages()`)

Stack index ผูกกับ `Sidebar.NAV_ITEMS` แบบ 1:1, ตอนนี้มี **6 หน้า** (ไม่ใช่ 7):

| Index | Attr บน `MainContentArea` | Class | หมายเหตุ |
|---|---|---|---|
| 0 | `wizard_tab` | **`InteractiveTerminal` เปล่า (รอบสี่)** (ไม่ใช่ `WizardConsoleTab` อีกต่อไป) | เหมือน Raw Output/LLM Mode ทุกประการ — plain bash, พิมพ์ nmap ฯลฯ ได้ตรงๆ. `WizardConsoleTab` (`src/ui/wizard_console.py`) ยังอยู่ในโค้ด ไม่ถูกลบ แค่ไม่ import/ใช้จาก `widgets.py` แล้ว — dead code เหมือน `llm_mode.py`/`tool_selection.py` |
| 1 | `input_tab` | `InputManagementTab` | ไม่แตะรอบนี้ |
| 2 | `cmd_editor_tab` | `CommandEditorTab` | ไม่แตะรอบนี้ |
| 3 | `raw_output_tab` | `RawOutputTab` | **เปลี่ยนใหญ่ (รอบสาม)**: ตัด status dot/idle-running indicator ออกหมด, ข้างในเป็น `InteractiveTerminal` จริง (real bash shell, พิมพ์ได้) แทน `QTextEdit` read-only เดิม. **`append_log()`/`set_running()` ถูกลบออกจาก `RawOutputTab` แล้ว** — ไม่มี mirror จาก gated execution เข้ามาปนใน terminal อีกต่อไป, เป็น bash เปล่าล้วนๆ |
| 4 | `results_tab` | `ResultsDisplayTab` | **ลบ demo data (`_DEMO_HOSTS`) ออกแล้ว** — เริ่มต้นว่างเปล่า พร้อมข้อความ placeholder "No results yet — run an nmap scan…" จนกว่าจะมี `set_hosts()` ผลจริง |
| 5 | `llm_tab` | **`InteractiveTerminal` เปล่า** (ไม่ใช่ `LLMModeTab` อีกต่อไป) | หน้า LLM Mode ตอนนี้คือ terminal จริงล้วนๆ ไม่มีคำอธิบาย/เมนูเลือก provider ใดๆ — ผู้ใช้เชื่อม AI เอง (พิมพ์ `claude`, `llm chat`, curl API ฯลฯ ในนั้น) |

`tool_selection_tab` ไม่มีอีกต่อไป — ไม่มีการ import `ToolSelectionTab` ใน `widgets.py` แล้ว.
`WizardConsoleTab` เช่นกัน ตั้งแต่รอบสี่ — ไม่มีการ import ใน `widgets.py` แล้ว
(`wizard_tab` ตอนนี้คือ `InteractiveTerminal` เปล่า). `main_window._on_opmode_change()`
ก็ถูกตัด branch ที่เรียก `wizard_engine.reset()`/`write_output(DIRECT_TOOL_CONTENT)`
ออกไปด้วย เพราะหน้านี้ไม่มี API แบบนั้นให้เรียกอีกแล้ว — ตอนนี้แค่สลับไป stack
index 0 เฉยๆ ไม่ว่าจะเลือก operation mode ไหน.

### `InteractiveTerminal` (`src/ui/terminal.py`) — รายละเอียดใหม่ (รอบสี่)

- เปิด real shell ผ่าน `QProcess`, merged stdout/stderr channel.
- `_default_shell()`: **WSL (`wsl.exe`, distro default = Ubuntu) มาก่อนแล้ว**
  ตั้งแต่รอบที่ยืนยัน WSL ติดตั้งจริง — ลำดับ: `$BASH_PATH` → `wsl.exe` →
  `Git\bin\bash.exe` → `Git\usr\bin\bash.exe` → `System32\bash.exe` →
  `bash.exe` (PATH). Linux/macOS: `/bin/bash` → `/usr/bin/bash` → `bash`.
  แต่ละ candidate เป็น `(program, args)` คู่กัน เพราะ `wsl.exe` ไม่รับ flag `-i`
  แบบ bash ตัวอื่น.
- **ไม่มี input line แยกอีกแล้ว** — `self.output` (`QTextEdit`) เดียวเป็นทั้ง
  scrollback และช่องพิมพ์ในตัว, editable ตรงๆ. ตัวแปร `_input_start` (ตำแหน่ง
  cursor) กันไม่ให้แก้ output เก่าได้ (Backspace/Left/Home ที่ตำแหน่ง ≤
  `_input_start` ถูกบล็อก), Enter = ส่งบรรทัดปัจจุบันเข้า stdin จริง แล้วเลื่อน
  `_input_start` ตาม. History ด้วยลูกศรขึ้น/ลง (แทนที่บรรทัด input ปัจจุบัน).
- **ไม่มีสีข้อความพิเศษอีกแล้ว** — `PURPLE` (echo คำสั่ง), `TERM_MUTE`/`ACCENT_RED`
  (status message) ถูกตัดออกหมด, ทุกอย่างใช้สี default `CONSOLE_TEXT` ล้วน.
  `_append()` ไม่มีพารามิเตอร์ `color` อีกต่อไป.
- `append_log(text)` — method ยังอยู่บนตัว widget เอง (ใช้แทรก text แยกจาก
  stdin ของ shell ได้ถ้าจำเป็น) แต่ **ไม่มีที่ไหนเรียกใช้แล้ว** — `RawOutputTab`/
  `wizard_tab`/`llm_tab` ทั้งสามเป็น bash เปล่า ไม่มี app inject ข้อความใดๆ.
- ใช้ซ้ำ 3 ที่ตอนนี้: `RawOutputTab.terminal`, `MainContentArea.wizard_tab`,
  `MainContentArea.llm_tab` ตรงๆ (ไม่มี wrapper class คั่นที่ไหนแล้ว).
- ยังเป็น non-PTY (stdin/stdout pipe ธรรมดา ไม่ใช่ TTY จริง) เหมือนเดิม —
  โปรแกรมที่เช็ค `isatty()` ยังอาจทำงานไม่สมบูรณ์.
- Top-bar "Execute" quick-run (`main_window._on_execute_clicked` /
  `_run_gated_command`) เดิม mirror ข้อความ preview/ผลลัพธ์เข้า
  `raw_output_tab` ผ่าน `append_log()` — **ตัดออกแล้ว**. ตอนนี้ preview +
  ผลลัพธ์ execution ของปุ่ม Execute ไปโผล่ที่ `QMessageBox` แทน
  (`Confirm Execution` / `Execution Finished`), ไม่ยุ่งกับ terminal เลย.
  `ConfirmationGate`/`audit_log.py` ยังทำงานเหมือนเดิมทุกจุด (ตัดแค่ layer
  แสดงผลใน terminal, ไม่ตัด logic ความปลอดภัย).
- `wizard_tab.commandEntered` เดิมต่อสาย → `main_window._log_command` →
  `raw_output_tab.append_log()` (เคยเป็น gap #2 ใน `CURRENT_STATE.md` — เสี่ยง
  double execution). **ตัดสายนี้ทิ้งแล้ว** — `_log_command` ไม่มีอยู่แล้ว.
  `commandEntered` signal ในตัว `wizard_console.py` เองยังอยู่ (ไม่แตะ logic
  ภายใน) แค่ไม่มีใคร connect ฟังจากฝั่ง `main_window.py` อีกต่อไป.
- ข้อจำกัดที่รู้อยู่: เป็น line-buffered ผ่าน stdin/stdout ปกติ ไม่ใช่ PTY เต็มรูปแบบ
  — โปรแกรมที่ต้องการ real TTY (interactive curses UI เช่นบาง REPL ที่เช็ค isatty)
  อาจทำงานไม่สมบูรณ์. ถ้าต้องการ PTY เต็มรูปแบบต้องเพิ่ม `pywinpty` (Windows) / `pty` module (Linux) แยกต่างหาก — ยังไม่ทำ.

### Results Display (`ResultsDisplayTab`) — รายละเอียด

- ซ้าย: `self.host_list` (`QListWidget`, object name `ZmHostList`) — ตอนนี้แสดง
  **แค่ hostname ล้วน ไม่มี icon emoji** ต่อแถว (ตัด `host["icon"]` ออกจาก label).
- ขวา: `self.detail_tree` (`QTreeWidget`, object name `ZmDetailTree`) — 5
  top-level node เดิม (Host Status / Addresses / Hostnames / Operating System /
  Ports used) — โครงสร้างไม่เปลี่ยน, แค่ไม่มีข้อมูลตั้งต้นแล้ว.
- **`_DEMO_HOSTS` ถูกลบทิ้งทั้งหมด**. `set_hosts([])` เป็นค่าเริ่มต้น —
  แสดง `QTreeWidgetItem` disabled บอกว่ายังไม่มีผลสแกน.
- ยังไม่มี adapter จาก `src/tools/nmap/parser.py` (มีแค่ `parse_open_ports`,
  คืนพอร์ตแบบ flat ไม่ใช่ per-host) → ต้องเขียน adapter ใหม่ถ้าต้องการต่อผลสแกนจริง
  เข้ากับ `set_hosts(list[dict])` (โครงสร้าง dict ที่ต้องการยังอยู่ใน docstring ของ method).

## Title Bar (`src/ui/main_window.py`)

- **ตัดออก**: "TR" brand mark (`#TitleMark`) และข้อความ "TheRecon / Authorized
  Security Workspace" (`#TitleBarLabel`) — เหลือแค่แถบลาก (drag area) เปล่า +
  ปุ่มควบคุมหน้าต่าง 3 ปุ่ม.
- ปุ่มควบคุมหน้าต่าง (`#WinControlBtn` / `#WinControlCloseBtn`) restyle เป็น
  flat/transparent (ไม่มี border/gradient แบบเดิม), icon สีขาว `#f8f8f2` ชัดเจน,
  close hover = แดง `#e81123` (มาตรฐาน Windows). ปุ่ม close ผูกกับ `self.close`
  จริง (`btn_close.clicked.connect(self.close)`).

## Settings menu (`main_window._on_settings_clicked`)

- คลิก `Sidebar.settings_btn` แล้วเปิด `QMenu` แบบ Zenmap-style ที่ตำแหน่งปุ่ม:
  New Window / Open Scan / Open Scan in This Window / Save Scan / Save All
  Scans to Directory / (separator) / Close Window / Quit.
- `Close Window` และ `Quit` ผูกกับ `self.close` จริง. รายการอื่นยังผูกกับ
  placeholder handler เดิม (`_on_new_scan`, `_on_import_yaml`, `_on_export_mission`
  — ยังเป็น `pass` เกือบทั้งหมด, TODO ถ้าต้องการ logic จริง).

## Stylesheet object-name reference (`src/config.py` → `STYLESHEET`)

ยังอยู่: `#Sidebar` / `#SidebarToggle` / `#SidebarNavItem` (+`[selected="true"]`) /
`#SidebarSettingsItem` / `#MissionBar` / `#MissionFieldLabel` /
`#MissionInput` / `#MissionCombo` / `#CmdPreview` / `#TermWindow` /
`#ZmHostList` / `#ZmDetailTree` / `#ZmKeyLabel` / `#ZmValueLabel` /
`#ZmAccuracyBar` / `#ZmAccuracyLabel`.

**ถูกลบ/เลิกใช้**: `#TermBar`, `#TermIcon`, `#TermTitle` (terminal header หายไป
พร้อม chrome), `#LogStatus`/`#LogStatusDot` (+`[running="true"]`) (ตัด idle/running
indicator ทิ้งจาก Raw Output แล้ว), `#TitleMark`, `#TitleBarLabel`, `#BrowseButton`
(ไม่มีปุ่ม Browse อีกแล้ว).

ของเดิมที่ยังใช้อยู่: `#ContentCard`, `#TitleBar`, `#WinControlBtn`,
`#WinControlCloseBtn`, `#ExecuteButton`, `#ActionButton`, `#CommandPreviewBox`,
`#EditCommandArea`, `#VLine`/`#HLine`, `#StatusBar`/`#StatusLabel`/`#StatusDot`
(status bar ล่างสุดของหน้าต่างหลัก ยังซ่อนอยู่ `status_bar.hide()` เหมือนเดิม —
คนละอันกับ `#LogStatus` ที่ถูกลบ).

## จุดที่เบี่ยงจาก mockup โดยเจตนา (รู้ตัวแล้ว ไม่ใช่บั๊ก)

1. **Command preview ใน mission bar แก้ไขได้** (mockup ต้นฉบับอ่านอย่างเดียว) — คงไว้เพราะ `ConfirmationGate` ต้องอ่าน command จริงจากช่องนี้.
2. **Sidebar มี 6 หน้า ไม่ใช่ 7** — ตัด Tool Selection ออกตามคำสั่งผู้ใช้ (ไม่ใช่ 7 แบบรอบแรก, ไม่ใช่ 6 แบบ mockup เดิมด้วยเหตุผลเดียวกันบังเอิญตรงกัน).
3. **Terminal chrome ไม่มี header bar เลย** (mockup มี icon+title แบบ `>_  root@recon: ~/wizard`) — ผู้ใช้สั่งตัดออกให้เหลือ terminal เปล่า.
4. **Wizard Console, Raw Output, และ LLM Mode ทั้งหมดเป็น real bash shell (WSL)** ไม่ใช่ scripted/simulated terminal แบบ mockup HTML (mockup เป็น JS class จำลอง type effect ล้วน, ไม่รัน process จริง) — Wizard Console เข้าร่วมกลุ่มนี้ตั้งแต่รอบสี่ตามคำสั่งผู้ใช้ (ต้องการรัน nmap ตรงๆ ได้), ทำให้ตอนนี้ 3 ใน 6 หน้าเป็น bash เปล่าเหมือนกันหมด ไม่ผ่าน `ConfirmationGate` เลย.
5. **Results Display เริ่มต้นว่างเปล่า** ไม่มี demo data แบบ mockup (mockup มี 5 host ตัวอย่างฝังตายตัว).
6. **Target ไม่มีปุ่ม Browse** — เปลี่ยนเป็น dropdown ประวัติ target แทน (mockup มีปุ่ม "Browse…" เฉยๆ ไม่ผูก action).
7. **Settings ผูก popup menu จริง** (mockup ไม่มี dropdown ให้ settings เลย เป็นแค่รายการ sidebar เฉยๆ).

## ตรรกะที่ห้ามแตะเวลาสั่งแก้ GUI ต่อ

`src/core/confirmation_gate.py`, `src/wizard/engine.py`, `src/validation/`,
`src/tools/*/builder.py|validator.py|parser.py|analyzer.py`,
`src/report/audit_log.py`. ทั้งหมดนี้คือ "logic ที่ทำงานได้แล้ว" ตามที่ผู้ใช้ย้ำ
— งาน GUI ต่อไปแก้เฉพาะ layer การแสดงผล (`src/ui/widgets.py`, `src/ui/terminal.py`,
`src/ui/main_window.py`, `src/config.py`) เท่านั้น. **หมายเหตุรอบสี่:**
`src/ui/wizard_console.py` เองไม่ถูกเรียกใช้จาก UI แล้ว (ดูด้านล่าง) แต่ตัว
`ConfirmationGate`/`wizard/engine.py` ที่มัน (เคย) เรียกใช้ยังคง "ห้ามแตะ" อยู่
เผื่อถูกผูกกลับมาใช้ในอนาคต.

`src/ui/llm_mode.py` (`LLMModeTab`), `src/ui/tool_selection.py`
(`ToolSelectionTab`), และตั้งแต่รอบสี่ `src/ui/wizard_console.py`
(`WizardConsoleTab`) — ทั้งสามไฟล์ยังอยู่ในโค้ดแต่ **ไม่ถูกเรียกใช้จาก UI แล้ว**
— ถือเป็น dead code รอผู้ใช้ตัดสินใจว่าจะลบทิ้งจริงหรือจะเอากลับมาใช้ทางอื่น
(เช่นผูกกับปุ่มใน terminal, หรือหน้าใหม่). อย่าลบไฟล์เองโดยไม่ถาม.
