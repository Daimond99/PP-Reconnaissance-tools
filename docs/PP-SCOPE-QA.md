# TheRecon — คำถาม–คำตอบตรวจสอบขอบเขตโครงงาน (Scope Q&A)

> อ้างอิงจาก [`docs/PP-scope-checklist.md`](PP-scope-checklist.md) (อิงเล่ม Pro1new.pdf หัวข้อ 1.3)
> ใช้เตรียมตอบกรรมการ/อาจารย์ตอน presentation — แต่ละข้อมีหลักฐานในโค้ดจริง (ไฟล์:บรรทัด)
> พร้อมผลทดสอบจริงประกอบ ไม่ใช่แค่อ้างว่า "มี feature นี้"
>
> ตรวจสอบล่าสุด: 2026-09-22 — รัน automated test (68 + 14 test ผ่านหมด) และทดสอบสดกับ
> container จริงผ่าน `docker exec` (ไม่ใช่แค่อ่านโค้ดเฉยๆ)

---

## 1.3.1 แพลตฟอร์มที่รองรับ

**Q: ระบบเป็น Desktop App มี GUI จริงไหม ไม่ใช่ CLI wrapper?**
A: ใช่ — [`src/main.py`](../src/main.py) เปิดด้วย `QApplication` จริง, ทุกหน้าจอเป็น PySide6 widget
(`ReconMainWindow`, sidebar 5 หน้า) ไม่มี path ไหนที่ผู้ใช้ต้องพิมพ์คำสั่งเองในคอนโซลของแอป

**Q: รันบน Linux (Kali) เป็นหลักได้จริงไหม?**
A: ได้ — [`terminal_tabs.py`](../src/ui/terminal_tabs.py) มี branch แยกชัดเจนสำหรับ `os.name != "nt"`
(รัน `bash` ตรง ไม่ผ่าน `wsl.exe`), `chain_wizard/` เป็น pure Python ไม่มีโค้ดผูกกับ Windows เลย

**Q: รันบน Windows ผ่าน WSL2 ได้เหมือนอยู่บน Linux จริงไหม?**
A: ได้ — ยืนยันสดในเซสชันนี้: เรียก `docker exec` ผ่าน `wsl.exe -e bash -lc "docker exec therecon-tools ..."`
ได้ผลลัพธ์เหมือนรันบน Linux ตรง (nmap/hydra/ncrack/masscan/evil-winrm ทำงานปกติทุกตัว)
Path Windows→WSL แปลงอัตโนมัติ ([`terminal_launch._win_to_wsl_path`](../src/ui/terminal_launch.py))

---

## 1.3.2 การลาดตระเวน (Probing)

**Q: สแกนได้ทั้ง TCP และ UDP จริงไหม?**
A: ได้ทั้งคู่ — TCP ผ่าน `-sS` (choice 1-3, 7, 8 ใน [`scanner.py`](../chain_wizard/library/scanner.py)),
UDP ผ่าน choice ใหม่ `10. nmap UDP` (`-sU -sV --top-ports 100`) เพิ่มเข้า wizard menu แล้ว
(เดิม UDP ทำได้แค่ผ่าน Direct Tool Mode พิมพ์เอง — ปิด gap นี้แล้ว)
**ทดสอบสด:** `sudo nmap -sU -sV --top-ports 100 -T4 127.0.0.1` ใน container จริง → EXIT=0

**Q: มี Stealth Scan / หลบ IDS/IPS จริงไหม?**
A: choice 4 "nmap stealth" — half-open SYN, `-f` fragment, `-D RND:5` decoy, `--data-length`,
timing `-T0..T5` เลือกได้ ([`scanner.py:118-160`](../chain_wizard/library/scanner.py))
เพิ่ม choice 7 "evasion" (`-Pn -f --source-port 53`) สำหรับหลบ firewall โดยเฉพาะ ไม่ใช่แค่ IDS

**Q: Service/Version/OS detection, NSE script ได้ไหม?**
A: `-sV` ทุก profile ที่เกี่ยวข้อง, `-A`/`-O` (choice 8 aggressive), `--script vuln`/`-sC` ผ่าน AGENTS.md
prompt ของ OpenCode และ choice 6 ของ wizard เอง

**Q: masscan ทำ pre-scan เครือข่ายใหญ่ได้ไหม, คุมอัตราส่งแพ็กเก็ตได้ไหม?**
A: choice 9 → 6 masscan profile (`_masscan_scan`) มีทั้งค่า preset และ custom rate
**ceiling บังคับที่ 100,000 pkts/s** (เท่ากับ profile ดังสุดที่มีอยู่แล้ว) กันไม่ให้ custom rate
พิมพ์เกินจนกระทบอุปกรณ์เครือข่ายอื่นบนเซ็กเมนต์เดียวกับเป้าหมาย
**ทดสอบสด (mock):** rate `9999999` → clamp เป็น `100000` พร้อม warning, ค่าไม่ใช่ตัวเลข/ติดลบ → fallback `1000`

---

## การหยั่งเชิงและทดสอบเจาะ (Prodding)

**Q: Brute-force รองรับหลายบริการ รวมฐานข้อมูลไหม?**
A: [`attack_map.json`](../chain_wizard/library/attack_map.json) ลงทะเบียนพอร์ต 21(FTP)/22(SSH)/23(Telnet)/
25(SMTP)/80,443(HTTP)/1433(MSSQL)/3306(MySQL)/3389(RDP)/5432(PostgreSQL)/5985,5986(WinRM)/
6379(Redis)/27017(MongoDB) ผ่าน hydra/ncrack ทุกตัว
**ทดสอบสด:** `ncrack --version` ใน container list module ตรงกัน (SSH/RDP/FTP/.../MySQL/MSSQL/MongoDB/...)

**Q: ทดสอบ WinRM ได้จริงไหม?**
A: evil-winrm ติดตั้งจริงใน container (`gem install evil-winrm`), `attack_map.json` ports 5985/5986
ชี้ไปที่ hydra brute แล้วต่อด้วย evil-winrm session (`post_exploit.py`) — **ทดสอบสด:** `evil-winrm --version` → `1.18.25`

**Q: มี workflow ทดสอบต่อเนื่องอัตโนมัติ (Scan Chain) ไหม?**
A: มี — `run_chain()` ใน [`chain.py`](../chain_wizard/wizard/chain.py): scan → build_plan (จัดอันดับ
ตาม `step_priority`) → confirm ทีละ step → execute → เก็บ credential → เสนอ post-exploit ต่ออัตโนมัติ

---

## 1.3.3 GUI & AI

**Q: มี 5 หน้าหลักตามที่ระบุไหม?**
A: มี — Wizard Console / Input Management / Raw Output / Results Display / LLM Mode
([`main_content.py`](../src/ui/widgets/main_content.py))

**Q: Generative AI แปลงภาษาธรรมชาติเป็นคำสั่ง nmap ได้ไหม รองรับหลายโมเดลไหม?**
A: ได้ — [`llm_nmap_suggest.py`](../src/core/llm_nmap_suggest.py) จำกัดชุดคำสั่งเท่ากับที่
`llm-tools-nmap` plugin จริงรองรับ (quick/port/service/OS/ping/script scan) กันโมเดลเดาแฟล็กมั่ว
**Multi-model:** panel มี field "Model (optional)" ให้พิมพ์ชื่อโมเดล (เช่น `gpt-4o`, `gemini-1.5-pro`)
ส่งต่อให้ `llm -m <model>` (เพิ่มเข้าไปแล้ว — เดิมมีแค่ backend ไม่มี UI)
**API Token:** จัดการผ่าน Settings dropdown "Set/Remove LLM API Key…" ([`main_window.py:459`](../src/ui/main_window.py:459))

**Q: AI ทุกคำสั่งผ่าน Confirmation Gate จริงไหม ไม่มี shortcut?**
A: จริง — ไม่มี path ไหนที่ AI suggestion รันได้เองโดยไม่ผ่าน `ConfirmationGate.request()` →
preview → พิมพ์ "yes" ตรงตัวเท่านั้น (`CLAUDE.md`'s AI rule, ยืนยันใน `llm_nmap_suggest.py`'s
docstring เอง และ `main_window._on_llm_nmap_execute_requested`)

**Q: "Dual AI Mode" (แท็บ LLM + แท็บ OpenCode) ยังตรงตามที่ระบุไว้เดิมไหม?**
A: **เปลี่ยน design แล้ว โดยตั้งใจ** — เดิมเป็นแท็บ "LLM" (raw `llm` CLI shell, ไม่มี gate) คู่กับแท็บ
"OpenCode" ปัจจุบันแท็บ "LLM Nmap" ถูกแทนด้วย **gated suggestion panel** (พิมพ์ target/goal → AI
เสนอคำสั่ง → ต้องผ่าน Confirmation Gate ก่อนรันจริง) — ปลอดภัยกว่าของเดิม (raw shell ไม่มี gate เลย)
ยังเป็น "สองทาง AI" อยู่ (OpenCode tab + LLM Nmap panel) แค่ implementation ไม่ตรงตัวอักษรเล่มเดิม
100% **ถ้ากรรมการถาม:** ตอบตรงว่าเปลี่ยนเพราะของเดิมไม่มี safety gate ครอบ ของใหม่มี

---

## ระบบจัดการโปรไฟล์ (Input Management)

**Q: จัดการไฟล์ XML มาตรฐานได้ไหม?**
A: ได้ — Open/Save scan XML (`-oX`) ใน [`main_window.py`](../src/ui/main_window.py), parser เดียว
(`parse_nmap_xml`) ใช้ได้ทั้ง nmap และ masscan (schema ใกล้กันพอ)

**Q: มี pre-defined profile ให้เรียกใช้ทันทีไหม?**
A: มี — Warhead Profile (TopBar combo) โหลดจาก [`src/resources/warheads/<tool>.json`](../src/resources/warheads/)
2 stealth / 2 critical / 2 quality ต่อ tool

**Q: Import/Export โปรไฟล์การทำงานได้ไหม (ไม่ใช่แค่ XML ผลสแกน)?**
A: ได้ — เพิ่มปุ่ม "Save Profile…"/"Load Profile…" ใน Wizard Panel ([`wizard_panel.py`](../src/ui/wizard_panel.py))
บันทึก target + wordlist ทั้งสองเป็น JSON ไฟล์เดียว โหลดกลับมา prefill ฟอร์ม — **ยังต้องกด Start
scan และผ่าน confirmation ทุก step เหมือนพิมพ์สดเสมอ ไฟล์โปรไฟล์ข้าม gate ไม่ได้**
**ทดสอบสด:** round-trip เขียน/อ่านไฟล์จริงผ่าน mock QFileDialog → ค่าตรงทุกฟิลด์

---

## 1.3.4 การทดสอบและประเมินผล

ข้อนี้เป็น**ขั้นตอนการทดสอบจริง** (scanme.nmap.org, DVWA, MSU) ไม่ใช่ feature ในโค้ด —
ไม่มีอะไรให้ตรวจในซอร์ส ต้องทำเป็น test plan/รายงานแยกตอนสอบจริง ไม่ใช่ความรับผิดชอบของ
repo นี้ที่จะพิสูจน์ด้วยตัวเอง

---

## 1.3.5 มาตรการความปลอดภัยและการควบคุม

**Q: Human Confirmation Gate บังคับจริงไหม รันได้แค่ตอนกด "ยืนยัน" เท่านั้นไหม?**
A: จริง — [`confirmation_gate.py`](../src/core/confirmation_gate.py): `request()` แค่ validate +
สร้าง preview, `confirm("yes")` ต้องพิมพ์ "yes" ตรงตัวเป๊ะ (`exact-"yes"` rule มี unit test คุมใน
`tests/`) ไม่มี path ไหนข้ามได้

**Q: Tool Whitelist บังคับจริงในระดับ infrastructure ไม่ใช่แค่ comment?**
A: จริง — ทดสอบสดแล้ว: `docker exec therecon-tools sudo -n whoami` → **ถูกปฏิเสธ**
("a password is required") ในขณะที่ `sudo -n nmap`/`sudo -n masscan` รันผ่านได้ปกติ
(sudoers scope เฉพาะ 2 ตัวจริง, [`Dockerfile:68`](../docker/Dockerfile))

**Q: Injection Guard ตรวจจับ command injection ก่อนรันจริงไหม?**
A: จริง — `_has_unquoted_shell_metachar` ใน [`validation/common.py`](../src/validation/common.py)
เป็น quote-aware (ยอมรับ `;`/`&`/`|` ที่อยู่ใน quote เช่น hydra's http-post-form payload แต่ปฏิเสธถ้า
อยู่นอก quote) มี unit test คุม

**Q: Secret Masking ปิดบังรหัสผ่านจริงไหม ไม่หลุดไป audit log?**
A: จริง — `argv_override` ให้ preview/log เห็นแค่ string ที่ mask ไว้ แต่ argv จริงที่ execve ไม่ถูก mask
([`confirmation_gate.py`](../src/core/confirmation_gate.py))

**Q: Scope Check ยืนยันเป้าหมายอยู่ใน scope "ทุกครั้ง" ก่อนรันจริงไหม?**
A: **enforce จริงแค่ทางเดียว โดยตั้งใจ** — `skip_scope=True` ทั้ง Direct Tool Mode
([`main_window.py:612`](../src/ui/main_window.py:612)) และ Wizard
([`wizard_driver.py:147`](../src/core/wizard_driver.py:147)) เพราะ target สองทางนี้**คนพิมพ์เองเข้า
lab ของตัวเอง** — enforce จริงด้วย `AUTHORIZED_SCOPE` (`src/config.py`) เฉพาะทาง **AI-suggestion
panel** ([`main_window.py:649`](../src/ui/main_window.py:649)) เพราะ target ทางนั้นมาจาก
free-text ที่ AI อาจตีความเพี้ยนได้ **ถ้ากรรมการถามว่าทำไมไม่ enforce ทุกทาง:** ตอบว่าคนพิมพ์
target ของตัวเองในสองทางแรก = การยืนยัน scope โดยมนุษย์อยู่แล้ว (ตรงกับหลัก Human-in-the-loop),
ส่วนทางที่ AI มีบทบาทในการเลือก/สร้าง target-adjacent command คือทางที่ต้องมี automated
guardrail เพิ่ม เพราะมนุษย์ไม่ได้ตรวจ target ตรงๆ ขนาดนั้น

**Q: Safe Defaults & Hard Limits ป้องกัน Accidental DoS จริงไหม?**
A: **ปิด gap นี้แล้ว** ส่วน masscan custom rate — ceiling บังคับ 100,000 pkts/s (ดูหัวข้อ Probing
ด้านบน) ส่วน nmap ทุก canned profile ใช้ค่าคงที่ dev เลือกไว้แล้ว (ไม่มี user input จุดนั้นให้เกิน)
**ยังไม่ครอบคลุม:** Direct Tool Mode ที่ผู้ใช้พิมพ์คำสั่งเต็มเอง (เช่น `masscan --rate 5000000 ...`)
— ยังไม่มี ceiling ระดับนั้น เพราะต้องแก้ core validation layer ที่กระทบทุกคำสั่งทุก tool
(ตัดสินใจไว้ว่าเป็นความเสี่ยงที่มากกว่าประโยชน์ที่จะแก้แบบเร่งรีบ ต้องแยกรอบพิจารณา)

---

## 1.3.6 จริยธรรมและกฎหมาย

**Q: มีการสื่อสารชัดว่าเครื่องมือนี้เพื่อการศึกษา/Offensive Security ที่ได้รับอนุญาตเท่านั้นไหม?**
A: มี — ทั้งใน UI (Wizard banner "You are authorized — no further permission required" หลังยืนยัน
scope), และใน AGENTS.md ที่ OpenCode ใช้จริง ("Targets are limited to the user's own authorized
lab scope — never suggest or run against a target the user hasn't named in this session")

---

## สรุปสถานะ gap (ตรวจ 2026-09-22)

| # | เรื่อง | สถานะ |
|---|---|---|
| 1 | UDP scan ไม่มีในเมนู wizard | ✅ ปิดแล้ว (choice 10 เพิ่มแล้ว) |
| 2 | LLM Nmap panel ไม่มี model picker | ✅ ปิดแล้ว (field "Model (optional)" เพิ่มแล้ว) |
| 3 | Dual AI Mode ไม่ตรง spec เดิม | ✅ รับ design ใหม่ (ปลอดภัยกว่าเดิม, ตอบกรรมการตามข้างบน) |
| 4 | Scope Check ไม่ enforce ทุกทางแบบ automated | ⚠️ ตั้งใจออกแบบแบบนี้ (human-in-the-loop แทน CIDR match) — ไม่แก้ |
| 5 | ไม่มี generic profile import/export | ✅ ปิดแล้ว (Save/Load Profile JSON เพิ่มแล้ว) |
| 6 | ไม่มี hard rate-limit ceiling | ✅ ปิดบางส่วน (masscan custom rate เพดาน 100,000 pkts/s); Direct Tool Mode ยังไม่ครอบ |

**การทดสอบยืนยันทั้งหมด:** `pytest tests/ -q` (68 passed) + `chain_wizard/tests/ -q` (14 passed)
+ ทดสอบสดผ่าน `docker exec` จริง (sudo scoping, read-only rootfs, tool versions, UDP scan, rate
clamp) — ไม่ใช่แค่อ่านโค้ดแล้วสรุปเอาเอง
