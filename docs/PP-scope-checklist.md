# PP: Wizard-Based Security Assessment Tool — Scope Checklist

> อ้างอิงจาก Pro1new.pdf หัวข้อ 1.3 ขอบเขตของโครงงาน
> ใช้เป็น checklist ตรวจสอบว่าโค้ด/ระบบที่พัฒนาจริง ครบตามขอบเขตที่ระบุไว้ในเล่มหรือไม่

---

## 1.3.1 แพลตฟอร์มที่รองรับและรูปแบบการติดตั้งระบบ (Supported Platforms)

- [ ] เป็น Desktop Application ที่มี GUI (ไม่ใช่ CLI-only)
- [ ] รันได้บน Linux (Kali Linux) เป็นแพลตฟอร์มหลัก
- [ ] รันได้บน Windows ผ่าน WSL2 หรือ Virtualization โดยเรียกใช้เครื่องมือความมั่นคงปลอดภัยได้ครบเสมือนอยู่บน Linux

## 1.3.2 คุณสมบัติทางความมั่นคงไซเบอร์ (Cybersecurity Features)

### 1) การลาดตระเวน (Probing / Reconnaissance)
- [ ] ค้นพบโฮสต์และพอร์ต (host/port discovery) ด้วยเทคนิคส่งแพ็กเก็ตตรวจสอบหลายรูปแบบ
- [ ] สแกนพอร์ตแบบ TCP (SYN Scan, Connect Scan) และ UDP
- [ ] กำหนดเป้าหมายได้หลายรูปแบบ: IP เดี่ยว, ช่วง IP (CIDR)
- [ ] สแกนแบบ Stealth Scan เพื่อลด log บนเป้าหมาย
- [ ] ปรับความเร็ว/รูปแบบการส่งแพ็กเก็ตเพื่อหลบเลี่ยง IDS/IPS
- [ ] ใช้ Fragment Packet และ IP Decoy
- [ ] ตรวจจับ/ระบุบริการที่รันบนพอร์ต (Service Detection)
- [ ] วิเคราะห์เวอร์ชันซอฟต์แวร์/บริการ (Version Detection)
- [ ] วิเคราะห์ลายนิ้วมือระบบปฏิบัติการ (OS Fingerprinting)
- [ ] เรียกใช้สคริปต์ NSE (Nmap Scripting Engine) ตรวจสอบเบื้องต้น
- [ ] ตรวจสอบช่องโหว่ที่ทราบทั่วไป (Known Vulnerabilities) ระดับ Initial Probing
- [ ] สแกนเครือข่ายขนาดใหญ่ด้วย Masscan (ทำหน้าที่ Pre-scanner)
- [ ] ควบคุมอัตราการส่งแพ็กเก็ต/จัดการทรัพยากรป้องกัน overload

### 2) การหยั่งเชิงและทดสอบเจาะ (Prodding)
- [ ] ทดสอบความแข็งแกรงรหัสผ่านแบบ Online Brute-force
- [ ] รองรับบริการยืนยันตัวตนหลายประเภท: SSH, FTP, HTTP, ฐานข้อมูล
- [ ] ทดสอบการเข้าถึงบริการ Windows Remote Management (WinRM)
- [ ] Service Banner Grabbing เพื่อวิเคราะห์ประเภท/เวอร์ชันซอฟต์แวร์ และลด False Positive
- [ ] ทดสอบการตอบสนองของบริการด้วยคำร้องขอแบบกำหนดเอง
- [ ] วิเคราะห์ผลสแกนและแนะนำเครื่องมือทดสอบเชิงลึกที่เหมาะสมขั้นต่อไป
- [ ] สร้าง workflow ทดสอบต่อเนื่องอัตโนมัติตามผลสแกนที่พบ (Scan Chain)

## 1.3.3 ส่วนต่อประสานผู้ใช้และ AI (GUI Wizard & AI Interface)

### GUI
- [ ] พัฒนาด้วย PySide6
- [ ] มี 5 หน้าหลัก: Wizard Console, Input Management, Raw Output, Results Display, LLM Mode
- [ ] มี Real-time Output Panel
- [ ] แสดงผลได้ทั้ง Raw Output และ Parsed Results

### Assistant Mode (Wizard Mode)
- [ ] นำทางผู้ใช้ด้วยชุดคำถามต่อเนื่อง (step-by-step) ครอบคลุมทุกขั้นตอนการลาดตระเวน

### Direct-tool Mode
- [ ] เรียกใช้เครื่องมือเฉพาะทางได้โดยตรง (สำหรับผู้ใช้ระดับกลาง-สูง)
- [ ] สลับระหว่าง Wizard Mode และ Direct-tool Mode ได้อย่างยืดหยุ่น

### Generative AI Integration
- [ ] แปลงคำสั่งภาษาธรรมชาติเป็นคำสั่ง Nmap ผ่าน Function Calling (llm-tools-nmap)
- [ ] รองรับหลายโมเดล (Multi-Model): Gemini, Anthropic, ChatGPT ฯลฯ และจัดการ API Token
- [ ] Dual AI Mode: แท็บ "LLM" (llm-tools-nmap) และแท็บ "OpenCode" (AI agent แบบ shell แยก เรียกใช้เครื่องมือทั้ง 6 ตัวผ่านการสนทนาต่อเนื่อง)
  - [ ] **หมายเหตุสำคัญ:** โหมด OpenCode ต้องระบุไว้ชัดเจนว่าทำงานแยกจาก Confirmation Gate หลัก (เป็น trade-off ที่ยอมรับแล้ว ไม่ใช่บั๊ก)
- [ ] สรุปผลลัพธ์การสแกนที่ซับซ้อนให้เข้าใจง่าย (Intelligent Analysis)
- [ ] แนะนำขั้นตอนทดสอบถัดไปตามบริบทช่องโหว่ที่พบ (Next-step Recommendation)

### ระบบจัดการโปรไฟล์ (Input Management)
- [ ] บันทึก/โหลดการตั้งค่าจากไฟล์คอนฟิกภายนอก (Configurable-First)
- [ ] จัดการข้อมูลรูปแบบไฟล์มาตรฐาน เช่น XML
- [ ] จัดการ/เรียกใช้ชุดคำสั่งสำเร็จรูป (Pre-defined Profiles)
- [ ] Import และ Export โปรไฟล์การทำงานได้

## 1.3.4 การทดสอบและประเมินผล (Testing & Evaluation)

- [ ] ทดสอบกับเป้าหมายสาธารณะ: scanme.nmap.org, zero.webappsecurity.com, demo.testfire.net
  - [ ] มีการจำกัด **ห้าม** prodding เชิงลึกหรือสแกนความเร็วสูงกับเป้าหมายสาธารณะ
- [ ] ทดสอบกับ Sandbox Testbed: DVWA, Metasploitable2, Linux Server (SSH brute-force), Windows Server (WinRM)
- [ ] ทดสอบกับระบบจริง (Real Site Testbed) เฉพาะที่ได้รับอนุญาตเป็นลายลักษณ์อักษร: reg.msu.ac.th, isanmsu.com (พันธมิตร) / it.msu.ac.th, wbi.msu.ac.th (ต้องขออนุญาตก่อน)
- [ ] กรอบควบคุมการทดสอบ: จำกัดพารามิเตอร์ตามประเภทเป้าหมาย (สาธารณะ/Testbed/ระบบจริง)
- [ ] มีระบบบันทึกกิจกรรมทดสอบทั้งหมด พร้อมเวลาและเป้าหมาย
- [ ] เก็บหลักฐานการอนุญาตและขอบเขตการทดสอบ
- [ ] หากพบช่องโหว่ในระบบจริง ต้องแจ้งผู้ดูแลระบบทันทีโดยไม่เปิดเผยต่อสาธารณะ

## 1.3.5 มาตรการความปลอดภัยและการควบคุม (Safety and Control Measures)

- [ ] Human Confirmation Gate: แสดงคำสั่งที่ AI สร้างให้ผู้ใช้ตรวจสอบก่อนรันทุกครั้ง, รันได้เมื่อผู้ใช้กด "ยืนยัน" เท่านั้น
- [ ] Basic Safety Check: ตรวจจับคำสั่งที่อาจส่งผลกระทบอันตราย (เช่น Masscan สแกนใหญ่เกินขอบเขต, พารามิเตอร์ขัดแย้งกัน)
- [ ] Audit Log: บันทึกทุกคำสั่งจากโหมด AI พร้อมสถานะยืนยัน/ยกเลิกของผู้ใช้
- [ ] Safe Defaults & Hard Limits: กำหนดค่าตั้งต้น/ค่าสูงสุดที่ปลอดภัยสำหรับ rate limit ป้องกัน Accidental DoS
- [ ] Operational Impact Warning: แจ้งเตือนเมื่อพบคำสั่ง/โปรไฟล์ที่มีผลกระทบสูง (สแกนรุนแรง, brute-force ความเร็วสูง)
- [ ] Multi-level Confirmation: ยืนยันซ้ำสำหรับปฏิบัติการความเสี่ยงสูง
- [ ] Tool Whitelist: อนุญาตเฉพาะ 6 เครื่องมือ — Nmap, Masscan, Hydra, Ncrack, Ncat, Evil-WinRM
- [ ] Injection Guard: ตรวจจับ/ปฏิเสธคำสั่งที่มีรูปแบบ command injection ก่อนประมวลผล
- [ ] Secret Masking: ปิดบังรหัสผ่าน/ข้อมูลลับใน Command Preview
- [ ] Scope Check: ยืนยันเป้าหมายอยู่ในขอบเขตที่ได้รับอนุญาตก่อนดำเนินการทุกครั้ง

## 1.3.6 จริยธรรมและกฎหมาย (Ethics & Legal Compliance)

- [ ] มีการระบุ/บังคับใช้ Authorized Scope เท่านั้น (ป้องกันการนำไปใช้โจมตี/บุกรุกระบบผู้อื่นโดยพลการ)
- [ ] เอกสาร/UI สื่อสารชัดเจนว่าเครื่องมือนี้เพื่อการศึกษาและ Offensive Security ที่ได้รับอนุญาต สอดคล้องกับ พ.ร.บ. คอมพิวเตอร์

---

## หมายเหตุการใช้งาน checklist นี้กับ Claude Code

- แต่ละข้อควรตรวจสอบแบบ **มีหลักฐานในโค้ดจริง** (function/class/config ที่เกี่ยวข้อง) ไม่ใช่แค่ชื่อ feature ที่ตั้งใจไว้
- รายการที่เกี่ยวกับ "ต้องห้าม" หรือ "guardrail" (เช่น Confirmation Gate, Tool Whitelist, Injection Guard, Scope Check) ควรตรวจว่ามี **enforcement จริง** ไม่ใช่แค่ comment หรือ TODO
- ข้อ 1.3.3 (Dual AI Mode / OpenCode) ควรตรวจว่าเอกสารในโค้ด/README ระบุ trade-off เรื่อง Confirmation Gate ไว้อย่างชัดเจนตามที่เล่มกำหนด ไม่ใช่ปล่อยผ่านเงียบๆ
