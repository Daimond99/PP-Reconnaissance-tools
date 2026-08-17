# TheRecon — ภาพรวมโปรแกรม (ฉบับภาษาไทย)

เอกสารนี้อธิบายว่า **TheRecon คืออะไร**, **เรียกใช้เครื่องมือ CLI อย่างไร**, และ
**พัฒนา/ต่อยอดอย่างไร** — เขียนให้คนอ่านครั้งแรกเข้าใจได้โดยไม่ต้องไล่โค้ดเอง

> เอกสารกฎเชิงสถาปัตยกรรม → [`CLAUDE.md`](../CLAUDE.md)
> แผนที่ไฟล์ทีละไฟล์ (อังกฤษ) → [`docs/CURRENT_STATE.md`](CURRENT_STATE.md)
> บันทึกการเปลี่ยนแปลง → [`docs/PROGRESS.md`](PROGRESS.md)

---

## 1. โปรแกรมนี้คืออะไร

TheRecon เป็น **desktop GUI (PySide6) + ชั้นความปลอดภัย (safety layer)** ที่ครอบ
เครื่องมือ command-line ด้านความมั่นคงปลอดภัย **6 ตัว**:

**nmap · masscan · hydra · ncrack · ncat · evil-winrm**

ไม่ได้เขียนเครื่องมือใหม่ — หน้าที่คือ **ช่วยประกอบคำสั่งให้ถูก, แสดงผลกระทบ,
บังคับให้คนกด "ยืนยัน", รันในเทอร์มินัลจริง, แล้วอ่านผลลัพธ์กลับมาแสดง**

- **Windows** → เครื่องมือรันใน **WSL2 (Ubuntu)**; ตัว GUI รันบน Windows Python
- **Linux** → เครื่องมือรัน native
- ถูกจำกัดไว้ที่ **6 ตัวเท่านั้น** ตลอดทั้งระบบ (whitelist ของ validator,
  ตัวตรวจว่าเครื่องมือติดตั้งไหม, warhead profiles, และ attack map ของ wizard
  ตรงกันหมด) เพิ่มตัวที่ 7 = ต้องแก้ทุกจุด

> ⚠️ **ทดสอบเฉพาะเป้าหมายที่ได้รับอนุญาตเท่านั้น** ทุกเส้นทางที่รันคำสั่งจริง
> ต้องมีมนุษย์ยืนยันก่อนเสมอ

---

## 2. เรียกใช้เครื่องมือ CLI อย่างไร (หัวใจของคำถาม)

โปรแกรม **ไม่ได้ผูกกับ library ของแต่ละเครื่องมือ** — มันสร้างสตริงคำสั่งแล้ว
ส่งให้เชลล์จริงรัน แล้วดักอ่าน stdout กลับมา มี 2 เส้นทางหลัก:

### เส้นทาง A — Direct Tool Mode (แถบบน, มี gate)

```
เลือกเครื่องมือ + warhead / พิมพ์คำสั่งเอง
  → Validation (src/validation/common.py)      ← เช็ค whitelist + กันคำสั่งแฝง
  → ConfirmationGate.request()                 ← สร้าง preview + ผลกระทบ (ยังไม่รัน)
  → ผู้ใช้พิมพ์คำว่า "yes" เป๊ะ ๆ
  → ConfirmationGate.confirm("yes")            ← รันจริง + บันทึก audit log
  → Execution (PTY / subprocess) ในเชลล์จริง
  → Parser (src/tools/<tool>/parser.py)        ← อ่านผล
  → Results Display
```

จุดสำคัญตอน "แปลงเป็นคำสั่งจริง":
- บน **Windows** `request()` แปลง path `C:\...` เป็นรูป WSL `/mnt/c/...`
  (`convert_windows_paths_to_wsl`) เพราะคำสั่งรันใน WSL bash ที่ไม่มี drive letter
- เจอ prefix `sudo` (masscan/nmap ต้อง root สำหรับ raw socket) → เติมคำเตือน
  "รันด้วยสิทธิ์ root" ในกล่องผลกระทบ
- รหัสผ่านถูก **mask** ใน preview และ audit log (ผ่าน `argv_override` — โชว์คำสั่ง
  ที่ปิดบัง แต่รัน argv จริง)

### เส้นทาง B — Wizard Console (โหมดไกด์, มี confirm ของตัวเอง)

ฟอร์มซ้าย (target / mode AUTO·SEMI / wordlist) → กด Start scan → ฟอร์มถูกแปลงเป็น
flag แล้วเปิดแท็บเทอร์มินัลรัน **`chain_wizard/`** เป็น subprocess:

```
scan (nmap/masscan) → วางแผนโจมตีเรียงตามผลกระทบ → confirm ทีละสเต็ป
  → brute-force (hydra) → เก็บ credential → post-exploit ในขอบเขต (ncat/nmap-NSE/evil-winrm)
```

`chain_wizard/` เป็น Python แยกต่างหาก (อยู่ราก repo ไม่ใช่ใต้ `src/`),
รันเครื่องมือทั้ง 6 ตรง ๆ ผ่าน `subprocess`, **ไม่ผ่าน** `ConfirmationGate` ของ GUI
แต่ถือ confirm ทีละสเต็ปเป็นของตัวเอง

### การรันจริงอยู่ที่เทอร์มินัลไหน

`terminal_tabs.make_terminal()` เลือก backend ตัวแรกที่ใช้ได้ (fallback 3 ชั้น):

1. **`XtermTerminal`** (`src/ui/webterm/`) — หลัก: xterm.js ใน QWebEngineView +
   PTY จริง (ConPTY/pywinpty บน Windows, `pty.fork` บน Linux)
2. **`PtyTerminal`** (`src/ui/pty_terminal.py`) — สำรอง: ConPTY + pyte
3. **`InteractiveTerminal`** (`src/ui/terminal.py`) — ท้ายสุด: QProcess pipe เปล่า

**Windows launch:** `wsl.exe -e bash …` โดย **ไม่ใส่ `-d`** → ใช้ distro default
ของผู้ใช้ (ไม่ hardcode ชื่อ distro), path ฝั่ง WSL คำนวณจากตำแหน่ง repo ตอนรันไทม์

---

## 3. Pipeline / สถาปัตยกรรม (ห้ามข้ามชั้น)

```
GUI (src/ui/)
  → Wizard panel / Direct Tool Mode
  → Validation (src/validation/common.py)
  → Confirmation Gate (src/core/confirmation_gate.py)   ← ประตู "yes" เดียว
  → Execution (terminal PTY / subprocess)
  → Parser (src/tools/<tool>/parser.py)
  → Results Display (src/ui/widgets/)
```

**กฎเหล็ก:**
- GUI **ไม่เคย** สร้างคำสั่งหรือถือ logic ความปลอดภัย
- Validation รันก่อนสร้างคำสั่งเสมอ
- Execution รันหลัง gate เสมอ
- package ใน `src/tools/` มีเฉพาะตัวที่มีคนเรียกจริง — ห้าม scaffold เปล่า ๆ
  "เผื่อรักษา layout"

โมดูลสำคัญ:

| ส่วน | ที่อยู่ | หน้าที่ |
|------|--------|--------|
| Entry point | `src/main.py` | splash → `ReconMainWindow` → preflight doctor |
| ประตูความปลอดภัย | `src/core/confirmation_gate.py` | เฉพาะ Direct Tool Mode Execute |
| Wizard ไกด์ | `chain_wizard/` | subprocess CLI, confirm เอง |
| Validation | `src/validation/common.py` | whitelist + กันคำสั่งแฝง (quote-aware) |
| Resources | `src/resources/*.json` | เมนู/warhead/impact — ไม่ hardcode |
| Audit trail | `logs/audit_log.jsonl` | append-only, rotate ตามขนาด |
| โหลด JSON | `src/utils/resource_loader.py` | ตัวเดียวที่ได้รับอนุญาต `open()` resource |

---

## 4. หน้าจอ (Sidebar 5 หน้า)

- **หน้า 0 — Wizard Console** — ฟอร์มซ้าย + แท็บเทอร์มินัลขวา (เส้นทาง B ข้างบน)
- **หน้า 1 — Input Management** — คิวสแกนสไตล์ Zenmap (Status / Command)
- **หน้า 2 — Raw Output** — เทอร์มินัลแบบ **อ่านอย่างเดียว** (คีย์ผู้ใช้ถูกทิ้งก่อนถึง PTY) = พื้นผิว audit
- **หน้า 3 — Results Display** — nmap/masscan → ตาราง host/port; hydra/ncrack → ตาราง credential
- **หน้า 4 — LLM Mode** — เทอร์มินัล AI 2 ตัว (`llm` CLI + OpenCode), **ไม่มี gate โดยตั้งใจ**

---

## 5. พัฒนา/ต่อยอดอย่างไร

### รันและทดสอบ

```bash
python -m src.main            # รันแอป (จากราก repo)
pip install -r requirements.txt
python -m src.preflight       # doctor ตรวจ dependency (WSL + 6 tools + Python)
python -m pytest tests/ -q    # เทสต์ validators + confirmation gate (ไม่ต้องมีเป้าหมายจริง)
```

เทสต์ครอบเส้นทางความปลอดภัยล้วน: whitelist 6 ตัว, ตัวกันคำสั่งแฝงแบบ quote-aware,
กฎ `yes` เป๊ะ, การแปลง path Windows→WSL, การบังคับ scope, กัน replay ใช้ครั้งเดียว,
mask ความลับ

### กฎที่ต้องรู้ก่อนแก้เชิงโครงสร้าง

1. **อ่าน [`docs/CURRENT_STATE.md`](CURRENT_STATE.md) ก่อน** — snapshot ว่าอะไรทำจริง
   อะไรยัง placeholder ถูกกว่าไล่เดาจากโค้ด
2. **Resource-driven** — เมนู, help, คำเตือน, ข้อความ dialog, prompt template
   ต้องอยู่ใน `src/resources/*.json` ไม่ใช่ string ฝังใน Python
3. **Windows Demo เป็น execution profile ไม่ใช่ข้อจำกัดสถาปัตยกรรม** — ถ้าเครื่องมือ
   ยังรันบน platform นี้ไม่ได้ ไม่เป็นไร แต่ **ห้าม** scaffold
   `builder.py`/`validator.py`/`parser.py`/`analyzer.py` เปล่า ๆ ที่ไม่มีใครเรียก
4. เพิ่มโมดูลใน `src/tools/<tool>/` **ต่อเมื่อ** มีของจริงจะเรียกมันเท่านั้น

### จะเพิ่ม parser ให้เครื่องมือหนึ่ง (ตัวอย่างงานทั่วไป)

- สร้าง `src/tools/<tool>/parser.py` เฉพาะเมื่อ Results Display ต้องใช้ผลจริง
  (เช่น hydra/ncrack เพิ่มตอน Direct Tool Mode ต้องป้อนหน้า "Credentials Found")
- ต่อ auto-capture flag ที่ `main_window._scan_xml_capture_paths()` /
  `_cred_capture_paths()` (เติม `-oX` / `-o` / `-oN` ให้คำสั่งเปล่าก่อน confirm)
- masscan ใช้ `-oX` schema เป็น subset ของ nmap → parser เดียวครอบทั้งคู่

### กฎ AI/LLM

AI อธิบายเครื่องมือ/แนะนำ profile/สรุปผลได้ แต่ **ห้าม** รันสแกนเอง, ข้าม confirm,
ข้าม validation, หรือปลอมผลลัพธ์ ทุกคำสั่งที่ AI แนะนำต้องผ่าน validation +
`ConfirmationGate` ตัวเดียวกับคำสั่งที่พิมพ์เอง — ไม่มีทางลัด

---

## 6. เมื่อเอกสารขัดกับโค้ด

เชื่อ **source tree** ก่อนเสมอ README/โน้ตเก่าที่ขัดกับสถาปัตยกรรมข้างบนถือว่าล้าสมัย
