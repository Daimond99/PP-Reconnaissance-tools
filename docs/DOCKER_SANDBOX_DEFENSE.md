# การกักกันเครื่องมือ Recon 6 ตัวด้วย Docker Container — เอกสารสรุปสำหรับ Defend

เอกสารนี้สรุปที่มา การออกแบบ การ implement และผลการทดสอบของงาน "ทำระบบกักกันการรันเครื่องมือด้วย Container (Docker / Sandbox)" (ข้อ 5 เดิมใน `docs/List การเเก้ไข.md`) สำหรับนำไปใช้ประกอบการ defend โครงงานต่ออาจารย์กรรมการ

---

## 1. ที่มาและโจทย์ (Motivation & Threat Model)

### 1.1 สถาปัตยกรรมเดิม (ก่อนแก้ไข)

ระบบ TheRecon เป็น desktop GUI (PySide6) ที่ครอบเครื่องมือ command-line ด้านความมั่นคงปลอดภัย 6 ตัว ได้แก่ **Nmap, Masscan, Hydra, Ncrack, Ncat, Evil-WinRM** เดิมทีเครื่องมือทั้ง 6 ตัวถูกติดตั้งและรัน**ตรงบน WSL2 (Ubuntu)** ซึ่งเป็น host จริงของเครื่องผู้ใช้ โดยมี Execution path 2 จุดหลัก:

1. `chain_wizard/core/executor.py::run_cmd()` — รัน `subprocess.run(cmd, shell=True)` ตรงบน WSL2 host สำหรับ chain wizard อัตโนมัติ
2. Terminal PTY ที่เปิดผ่าน `wsl.exe -e bash` (Direct Tool Mode, LLM Nmap panel, OpenCode tab, Shell tab) — คำสั่งที่ผู้ใช้/AI พิมพ์ ถูกส่งเข้า bash session ของ WSL2 host โดยตรง

### 1.2 โจทย์ที่กรรมการตั้ง (Threat Scenario)

กรรมการยกโจทย์ว่า: **"สมมุติว่าไป Nmap สแกนเหยื่อสักเหยื่อหนึ่ง แล้วเหยื่อดักใช้วิธีการเซ็ตแบนเนอร์เป็น Indirect Prompt Injection — เครื่องมือกลายเป็นเหยื่อเอง แล้วมันกลับมารัน sudo ฝั่งเรา ทำ Privilege Escalation ได้ง่ายเลย"**

กล่าวคือ:
- เครื่องมือสแกน (เช่น `nmap -sV`) อ่าน service banner จาก target
- Target ที่เป็นฝ่ายตรงข้าม (หรือถูกดักไว้) ฝังข้อความ prompt injection ไว้ใน banner นั้น
- หาก banner ถูกส่งต่อเข้าไปเป็น context ให้ LLM/AI Mode (OpenCode, LLM Nmap panel) อ่าน อาจถูกหลอกให้สร้าง/แนะนำคำสั่งอันตรายที่มี `sudo` แถมมาด้วย
- หากผู้ใช้กด "yes" ผ่าน Confirmation Gate โดยไม่ทันสังเกต (หรือกรณีเลวร้ายกว่า — การหลอกล่อผ่าน UI) คำสั่งนั้นจะถูกรันเป็น **root จริงบน WSL2 host**
- เนื่องจาก WSL2 mount `/mnt/c/...` เข้าถึงทั้ง drive C: ของ Windows โดย default การได้ root บน WSL2 เท่ากับเข้าถึงไฟล์ทั้งเครื่อง Windows ได้ทันที

นี่คือ **"เราโดนหลอกให้โจมตีตัวเอง" ไม่ใช่ attacker บุกเข้ามาตรงๆ** — เป็น threat model เฉพาะเจาะจงที่ระบบ Confirmation Gate เดิม (ตรวจ whitelist, quote-aware injection guard, exact-`yes`) ยังไม่ครอบคลุม เพราะคำสั่งที่ถูกหลอกให้สร้างอาจผ่าน validation ทุกชั้นได้ (เป็น `sudo nmap ...` ที่ดูเหมือนคำสั่งปกติ)

---

## 2. แนวทางแก้ไข (Design)

### 2.1 หลักการ: Blast Radius Containment

แทนที่จะพยายามป้องกัน prompt injection ที่ต้นทาง (ยากและไม่สมบูรณ์แบบ 100%) แนวทางที่เลือกคือ **จำกัดความเสียหายที่เกิดขึ้นได้ (blast radius containment)** — ให้เครื่องมือทั้ง 6 ตัวรันอยู่ใน **Docker container ที่แยกออกจาก WSL2/Windows host โดยสมบูรณ์** ต่อให้ indirect prompt injection สำเร็จและหลอกให้ sudo ถูกรันจริง ความเสียหายจะจบอยู่แค่ใน container ที่ลบทิ้งสร้างใหม่ได้ ไม่ทะลุมาถึง host จริง

**สำคัญ**: ผู้ใช้ระบุชัดเจนว่าต้องการย้าย**เฉพาะ execution ของเครื่องมือ** ไม่แตะ GUI/host อื่นใด — สถาปัตยกรรม GUI (PySide6, terminal widget, confirmation gate) ยังคงอยู่บน Windows/WSL2 host เหมือนเดิมทุกประการ มีแค่ subprocess ที่รันคำสั่งจริงที่ถูกเปลี่ยนปลายทาง

### 2.2 ทางเลือก Docker Engine (native) vs Docker Desktop

เลือกติดตั้ง **Docker Engine โดยตรงในตัว WSL2 distro (Ubuntu)** แทนการใช้ Docker Desktop เหตุผล:
- สถาปัตยกรรมเดิมเปิด terminal ผ่าน `wsl.exe -e bash` อยู่แล้ว — `docker`/`docker exec` เป็นแค่คำสั่งธรรมดาที่ bash session เดิมเรียกได้ทันที ไม่ต้องข้าม Windows↔WSL boundary เพิ่ม
- ไม่ต้องพึ่ง Docker Desktop's Windows service (`dockerDesktopLinuxEngine` npipe) ซึ่งพบว่าไม่เสถียร (daemon ไม่รันตอนทดสอบจริง)
- WSL2 (Ubuntu 26.04) รองรับ systemd อยู่แล้ว → `dockerd` รันเป็น service ปกติได้เลย

ติดตั้งด้วย `sudo apt-get install -y docker.io` (เวอร์ชัน 29.1.3-0ubuntu4.1 จาก apt repo ทางการ ไม่ต้องเพิ่ม repo เอง)

---

## 3. รายละเอียดการ Implement

### 3.1 Dockerfile (`docker/Dockerfile`)

Image ตั้งอยู่บน `ubuntu:24.04` ประกอบด้วย:

| องค์ประกอบ | รายละเอียด |
|---|---|
| เครื่องมือ 6 ตัว | `nmap`, `ncat`, `masscan`, `hydra`, `ncrack` (apt), `evil-winrm` (ruby gem) |
| User | non-root `recon` (ไม่ใช่ root ตั้งแต่ระดับ image) |
| Privilege สำหรับ raw-socket | **sudo scoped เฉพาะ 2 binary** (`nmap`, `masscan`) ผ่าน `/etc/sudoers.d/recon-tools`, `NOPASSWD` (ไม่มี tty ให้ตอบ password ผ่าน `docker exec`) |
| Wordlist | ไม่ bundle มากับ image (Ubuntu ไม่มี package `wordlists` แบบ Kali) — mount จาก host แยกต่างหาก |

**ประเด็นทางเทคนิคที่พบระหว่าง implement (คุ้มค่าต่อการอธิบายในการ defend)**:

เดิมตั้งใจใช้ **`setcap cap_net_raw,cap_net_admin+eip`** บน binary nmap/masscan โดยตรง เพื่อให้ user `recon` (non-root) รัน raw-socket scan ได้โดยไม่ต้องพึ่ง sudo เลย — เป็นแนวทาง least-privilege ที่ดีกว่าในทางทฤษฎี แต่ทดสอบจริงพบว่า **ไม่ทำงาน**: แม้ตั้ง capability ถูกต้อง (`getcap` ยืนยันว่า flag ถูกต้อง) และ container's capability bounding set ถูกต้อง (`docker exec -u root` scan ผ่านได้ปกติ) แต่ `docker exec` ในฐานะ user `recon` ยังคงถูกปฏิเสธด้วย "You requested a scan type which requires root privileges." สรุปได้ว่า Ubuntu's nmap build ไม่ยอมรับ non-root process ที่มีแค่ file-capability (ทดสอบตัดตัวแปร `--security-opt no-new-privileges` ออกแล้วก็ยังไม่ผ่าน) จึงเปลี่ยนมาใช้แนวทาง **sudo scoped เฉพาะ 2 binary** แทน ซึ่งพิสูจน์แล้วว่าทำงานได้จริง — เป็นตัวอย่างที่ดีของการที่ทฤษฎี least-privilege ไม่ตรงกับพฤติกรรมจริงของ binary ที่แจกจ่ายมา ต้อง verify ด้วยการทดสอบจริงเสมอ

### 3.2 Run script (`docker/run.sh`)

จุดสำคัญ: **นี่คือจุดเดียวในระบบทั้งหมดที่เรียก `docker run`** — โค้ดแอปพลิเคชัน (`executor.py`, `terminal_launch.py`) ไม่มีจุดไหนพิมพ์ `docker run` เองโดยตรง ทำให้ **ไม่มีทางเผลอใส่ flag อันตรายได้เลย** เพราะไม่มีช่องให้พิมพ์ flag อิสระ — เป็นการป้องกัน misconfiguration ที่ระดับสถาปัตยกรรม ไม่ใช่แค่ "จำไว้ว่าอย่าใส่"

Flag ที่ตั้งไว้ใน `docker run` และเหตุผล:

| Flag | เหตุผล |
|---|---|
| `--cap-drop=ALL` | ตัด Linux capability ทั้งหมดออกก่อน แล้วค่อยเพิ่มเฉพาะที่จำเป็นจริง |
| `--cap-add=NET_RAW --cap-add=NET_ADMIN` | ให้ nmap/masscan ทำ raw-socket scan ได้ (ผ่าน sudo ภายใน) |
| `--cap-add=SETUID --cap-add=SETGID` | sudo เองก็ต้องใช้ capability นี้เพื่อสลับเป็น root แม้เป็น setuid-root binary — พบจากการทดสอบว่าไม่มีสองตัวนี้ sudo error "unable to change to root gid" |
| **ไม่มี** `--privileged` | คงกำแพง isolation ของ Linux namespace/cgroup ไว้เต็มรูปแบบ |
| **ไม่มี** mount `/var/run/docker.sock` | กัน container escape แบบ classic (ถ้า container คุม docker daemon เองได้ = สร้าง privileged container ใหม่ได้ = หลุดออกจริง) |
| **ไม่มี** mount `/mnt/c` หรือ WSL root | container มองไม่เห็นไฟล์จริงบน Windows/WSL host เลย |
| `--network therecon-net` (custom bridge) | **ไม่ใช้** `--network=host` — container ไม่เห็น Windows LAN adapter อื่น, ตัดทาง lateral movement ไปหา host service อื่น |
| `--read-only` (root filesystem) | เขียนไฟล์ระบบไม่ได้เลย ยกเว้นจุดที่เปิดไว้ชัดเจน |
| `--tmpfs /tmp`, `--tmpfs /run` | เปิดจุดเขียนที่จำเป็นจริง (temp file ของเครื่องมือ, sudo runtime) — หายไปเมื่อ container ตาย |
| `-v <results>:/results:rw` | จุดเดียวที่แลกเปลี่ยนข้อมูลกับ host — เฉพาะ output ผลสแกน |
| `-v <wordlists>:/results/wordlists:ro` | wordlist ผู้ใช้เอง mount แบบ read-only |
| `--memory=1g --cpus=2 --pids-limit=256` | จำกัด resource กัน DoS ตัวเอง (fork bomb, memory exhaustion) จากคำสั่งที่ถูกหลอกให้รัน |
| `--restart unless-stopped` | container รันค้างไว้ (long-lived), `docker exec` เรียกซ้ำได้เร็ว ไม่ต้อง spawn ใหม่ทุกครั้ง |

### 3.3 การเชื่อมโยงกับโค้ดแอปพลิเคชัน

**`chain_wizard/core/executor.py`** — แก้จาก:
```python
subprocess.run(cmd, shell=True, ...)   # เดิม: รันตรงบน WSL2 host
```
เป็น:
```python
subprocess.run(["docker", "exec", "-i", CONTAINER, "bash", "-c", cmd], ...)  # ใหม่
```
พร้อมลบ logic การ "prime" sudo password ฝั่ง host ออกทั้งหมด (เดิมต้องขอ password ผู้ใช้ผ่าน GUI dialog เพื่อ `sudo -v` บน host) เพราะตอนนี้ sudo ถูกจัดการโดย container's NOPASSWD sudoers rule เอง — python process นี้ไม่แตะรหัสผ่านจริงอีกต่อไปเลย (แก้ปัญหาข้อ 2 เดิมใน List การเเก้ไข ไปโดยผลพลอยได้)

**`src/ui/terminal_launch.py`** — Terminal ที่ผู้ใช้เห็น (Wizard Console, Raw Output/Direct Tool Mode, LLM Nmap panel, OpenCode tab, Shell tab) เรียกเครื่องมือผ่าน wrapper ที่ resolve เข้า `docker exec` เมื่อพิมพ์ชื่อเครื่องมือ (nmap/masscan/...) แทนการหา binary บน PATH ของ WSL host ตรงๆ

**ผลลัพธ์สุดท้าย**: ถอดเครื่องมือทั้ง 6 ตัว**ออกจาก WSL host จริง** (`apt-get purge`, `gem uninstall`) — ปิด bypass path ที่อาจเกิดถ้ามีคนพิมพ์ absolute path (`/usr/bin/nmap`) ตรงๆ เพราะตอนนี้ไม่มีของจริงให้เรียกบน host อีกต่อไป ต้องผ่าน container เท่านั้น

---

## 4. การทดสอบและยืนยันผล (Verification)

ทุกข้อทดสอบจริงบนเครื่อง ไม่ใช่แค่ทฤษฎี:

| รายการทดสอบ | ผลลัพธ์ |
|---|---|
| Docker Engine ทำงานได้ (native, ไม่ใช่ Docker Desktop) | ผ่าน — `docker run hello-world` สำเร็จ |
| Build image สำเร็จ, 6 เครื่องมือครบ | ผ่าน — `nmap, ncat, masscan, hydra, ncrack, evil-winrm` ทุกตัวเจอใน container |
| User ไม่ใช่ root | ผ่าน — `whoami` → `recon`, `id` → `uid=1001(recon)` |
| Sudo scope จำกัดจริง | ผ่าน — `sudo nmap` สำเร็จ, แต่ `sudo apt-get update` / `sudo cat /etc/shadow` / `sudo bash` ถูกปฏิเสธด้วย "a password is required" |
| Raw-socket SYN scan ทำงานได้ (loopback) | ผ่าน — `sudo nmap -sS -p1-100 127.0.0.1` สแกนสำเร็จผ่าน scoped sudo |
| Raw-socket SYN scan ทำงานได้ผ่าน NAT ไป target จริงภายนอก | ผ่าน — scan `demo.testfire.net` (IBM public pentest demo site) สำเร็จ พบ port 80/443/25 พร้อม service detection ถูกต้อง — ตอบข้อกังวลเรื่อง conntrack/NAT ที่คาดว่าอาจเป็นปัญหา |
| ไฟล์ผลลัพธ์ sync กลับ host ผ่าน volume mount | ผ่าน — ไฟล์ `-oX` ที่เขียนใน container โผล่ที่ `chain_wizard/results/` บน Windows host ถูกต้อง |
| เครื่องมือถอดออกจาก WSL host จริง | ผ่าน — `command -v nmap/masscan/hydra/ncrack/ncat/evil-winrm` บน host ทุกตัวรายงาน "gone from host" |
| Container ยังใช้งานได้ปกติหลังถอดจาก host | ผ่าน — เครื่องมือครบใน container แม้ host ไม่มีสำเนาแล้ว |
| Regression test | ผ่าน — pytest 68/68 ผ่านตลอดทุกขั้นตอนของการแก้ไข |

---

## 5. สิ่งที่ป้องกันได้ (Threats Mitigated) — ตอบโจทย์กรรมการโดยตรง

ตามโจทย์ **"เราโดนหลอกให้โจมตีตัวเอง"** container ออกแบบมาป้องกันผลลัพธ์ทุกรูปแบบของการถูกหลอก ไม่ใช่แค่กรณี sudo อย่างเดียว:

1. **Privilege Escalation** (กรณีหลักตามโจทย์) — sudo ที่ถูก inject หลอกให้รัน จบแค่ใน container, ไม่ทะลุถึง root จริงบน WSL2/Windows
2. **Filesystem tampering/theft** — หากช่องโหว่ใน parser ของเครื่องมือเอง (เช่น NSE script bug) ถูกโจมตี โค้ดที่รันได้เห็นแค่ filesystem ข้างใน container เท่านั้น ไม่เห็นไฟล์จริงบน host หรือ credential/loot เก่า
3. **Reverse shell / C2 callback** — evil-winrm/ncat session ที่ถูกแปลงเป็น reverse shell มองเห็นแค่ custom bridge network ไม่เห็น Windows LAN จริง
4. **Lateral movement ไป host services** — container ไม่อยู่บน host network namespace ปิดทางแตะ SMB/RDP หรือ service อื่นบนเครื่อง
5. **Persistence/implant** — container เป็น ephemeral, `docker rm -f` + สร้างใหม่จาก image สะอาด ลบร่องรอยได้ทันที ไม่ต้องไล่เช็ดเครื่อง host ทีละไฟล์
6. **Resource exhaustion (self-DoS)** — cgroup limit (`--memory`, `--cpus`, `--pids-limit`) กันไม่ให้คำสั่งที่ถูกหลอกให้รันจนเครื่อง host ค้าง

---

## 6. ข้อจำกัด (สิ่งที่ต้องยอมรับตรงๆ ต่อกรรมการ)

- **Container escape ผ่าน kernel exploit** — Docker container แชร์ kernel เดียวกับ WSL2 host (ไม่ใช่ VM แยกจริงแบบ Hyper-V) หาก 0-day ระดับ kernel หลุดออกมาได้เสมอ container ลดพื้นที่โจมตีแต่ไม่ได้รับประกัน 100%
- **ไม่ทดแทน Confirmation Gate เดิม** — เป็น defense-in-depth ชั้นเพิ่ม ไม่ใช่ตัวแทน มนุษย์ยังต้องเป็นด่านตัดสินใจ "yes" เหมือนเดิมทุกประการ
- **ไม่ป้องกันการโจมตี GUI/host โดยตรง** — หาก attacker เจาะเข้ามาทาง Windows เครื่องนี้ผ่านช่องทางอื่นที่ไม่ผ่าน scan tool เลย container ไม่เกี่ยวข้อง เป็นคนละ threat model
- **ยังต้องป้องกัน misconfig** — แม้ล็อก flag ไว้ที่ `docker/run.sh` จุดเดียวแล้ว ยังต้องมี code review ทุกครั้งที่แก้ไฟล์นี้ เพราะถ้าเผลอใส่ `--privileged` หรือ mount `docker.sock`/`/mnt/c` กำแพงทั้งหมดพังทันที

---

## 7. สรุป

งานนี้ตอบโจทย์กรรมการโดยตรง: เปลี่ยนจากการรันเครื่องมือ recon 6 ตัวบน WSL2 host ตรงๆ (ซึ่งเปิดช่องให้ indirect prompt injection ผ่าน scan banner นำไปสู่ privilege escalation จริงบนเครื่อง user) มาเป็นรันภายใน Docker container ที่ล็อกด้วยหลัก least-privilege (non-root, capability ขั้นต่ำ, sudo scope แคบ, filesystem/network แยกจาก host) — ทดสอบยืนยันแล้วว่าใช้งานได้จริงกับทั้ง target ภายในและภายนอกเครือข่าย พร้อมยอมรับข้อจำกัดที่ยังเหลืออยู่อย่างตรงไปตรงมา
