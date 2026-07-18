## ⚠️ ขอบเขตการใช้งาน (Scope of Use)

โปรเจคนี้เป็นเครื่องมือ security recon ที่ได้รับอนุญาตให้ใช้เพื่อการศึกษา
ภายใต้การดูแลของอาจารย์ผู้สอน **การทดสอบทุกครั้งต้องทำภายใน sandbox/lab
environment ที่กำหนดไว้เท่านั้น ห้ามใช้กับระบบหรือเครือข่ายใด ๆ
ที่อยู่นอกขอบเขตที่ได้รับอนุญาตโดยเด็ดขาด**

---

## Prerequisites

- Kali Linux หรือ Debian/Ubuntu-based distro
- Python 3.10+
- สิทธิ์ sudo (สำหรับติดตั้ง package และตั้งค่า network capability)
- เครื่องมือที่โปรแกรมเรียกใช้ผ่าน subprocess:
  - `nmap` (รวม `ncat`)
  - `masscan`
  - `hydra`
  - `ncrack`
  - `evil-winrm` (Ruby gem)

> หมายเหตุ: บน Kali Linux เครื่องมือส่วนใหญ่ (nmap, hydra) มักติดตั้งมาให้อยู่แล้ว
> สคริปต์ `setup.sh` จะตรวจสอบและข้ามการติดตั้งซ้ำโดยอัตโนมัติ

---

## Installation

1. **Clone repository**
   ```bash
   git clone <repo-url>
   cd therecon
   ```

2. **ติดตั้งเครื่องมือ recon ระดับระบบ**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   สคริปต์นี้จะ:
   - ติดตั้ง nmap, masscan, hydra, ncrack ผ่าน `apt`
   - ติดตั้ง Ruby และ evil-winrm ผ่าน `gem`
   - ตั้งค่า `setcap` ให้ nmap/masscan ทำ raw socket scan ได้โดยไม่ต้องรัน
     โปรแกรมทั้งหมดด้วย root (ปลอดภัยกว่าการ sudo ทั้งแอป)
   - แสดงสรุปสถานะการติดตั้งของแต่ละเครื่องมือ

3. **สร้าง virtual environment และติดตั้ง Python dependencies**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **รันโปรแกรม**
   ```bash
   python main.py
   ```

---

## หมายเหตุเรื่องสิทธิ์การรัน (Privileges)

- โปรแกรมนี้**ไม่จำเป็นต้องรันทั้งแอปด้วย `sudo`** เนื่องจาก `setup.sh`
  ได้ตั้งค่า `setcap cap_net_raw,cap_net_admin+eip` ให้กับ `nmap` และ `masscan`
  ไว้แล้ว ทำให้ทำ raw socket scan (เช่น SYN scan) ได้โดยไม่ต้องยก
  สิทธิ์ทั้งโปรเซส
- หากใช้ scan mode บางประเภทที่ยังต้องการสิทธิ์เพิ่มเติม โปรแกรมจะแจ้งเตือน
  ผ่าน output console — ให้พิจารณารันเฉพาะคำสั่งนั้นด้วย `sudo` แทนการรัน
  ทั้งโปรแกรมด้วยสิทธิ์ root
