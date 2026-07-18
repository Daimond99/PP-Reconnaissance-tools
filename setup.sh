#!/usr/bin/env bash
#
# setup.sh — Installer for TheRecon (Authorized Security Workspace)
#
# ใช้สำหรับติดตั้งเครื่องมือ recon ที่โปรแกรมนี้เรียกใช้ผ่าน subprocess
# รองรับ: Kali Linux, Debian/Ubuntu-based distros
#
# คำเตือน: เครื่องมือเหล่านี้ (nmap, masscan, hydra, ncrack, evil-winrm)
# เป็นเครื่องมือ security testing ที่ต้องใช้เฉพาะกับระบบ/เครือข่ายที่ได้รับ
# อนุญาตให้ทดสอบเท่านั้น (เช่น sandbox หรือ lab ที่กำหนดไว้ในขอบเขตของโครงงาน)
# ห้ามใช้กับระบบที่ไม่ได้รับอนุญาตโดยเด็ดขาด
#
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[+]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
log_err()   { echo -e "${RED}[-]${NC} $1"; }

# --- ตรวจสอบว่ารันด้วย root/sudo หรือไม่ (ต้องใช้สำหรับ apt install) ---
if [[ $EUID -ne 0 ]]; then
    log_warn "สคริปต์นี้ต้องใช้สิทธิ์ sudo สำหรับการติดตั้ง package"
    SUDO="sudo"
else
    SUDO=""
fi

# --- ตรวจสอบ distro ---
if [[ -f /etc/debian_version ]]; then
    PKG_MANAGER="apt"
    log_info "ตรวจพบ Debian-based distro (Kali/Debian/Ubuntu) — ใช้ apt"
else
    log_err "สคริปต์นี้รองรับเฉพาะ Debian-based distro (Kali/Debian/Ubuntu) เท่านั้น"
    exit 1
fi

# --- อัปเดต package list ---
log_info "กำลังอัปเดต package list..."
$SUDO apt update -qq

# --- ฟังก์ชันติดตั้งแบบ idempotent ---
install_apt_pkg() {
    local pkg="$1"
    if command -v "$pkg" &>/dev/null; then
        log_info "$pkg ติดตั้งอยู่แล้ว — ข้าม"
    else
        log_info "กำลังติดตั้ง $pkg ..."
        $SUDO apt install -y "$pkg"
    fi
}

# --- ติดตั้งเครื่องมือหลัก ---
# หมายเหตุ: Kali Linux มักมี nmap, hydra ติดตั้งมาให้อยู่แล้ว
install_apt_pkg nmap        # มาพร้อม ncat ในตัว
install_apt_pkg masscan
install_apt_pkg hydra
install_apt_pkg ncrack

# --- ติดตั้ง ncat แยก กรณีบาง distro ไม่รวมมากับ nmap ---
if ! command -v ncat &>/dev/null; then
    log_warn "ไม่พบ ncat แยก — ปกติจะมาพร้อม nmap แล้ว ตรวจสอบด้วยตนเองถ้าจำเป็น"
fi

# --- ติดตั้ง Ruby (จำเป็นสำหรับ evil-winrm) ---
if ! command -v ruby &>/dev/null || ! command -v gem &>/dev/null; then
    log_info "กำลังติดตั้ง Ruby และ gem..."
    $SUDO apt install -y ruby ruby-dev build-essential
else
    log_info "Ruby/gem ติดตั้งอยู่แล้ว — ข้าม"
fi

# --- ติดตั้ง evil-winrm ผ่าน gem ---
if command -v evil-winrm &>/dev/null; then
    log_info "evil-winrm ติดตั้งอยู่แล้ว — ข้าม"
else
    log_info "กำลังติดตั้ง evil-winrm ผ่าน gem..."
    $SUDO gem install evil-winrm
fi

# --- ตั้งค่า capability ให้ masscan รัน raw socket ได้โดยไม่ต้อง sudo ทั้งโปรแกรม ---
MASSCAN_PATH=$(command -v masscan || true)
if [[ -n "$MASSCAN_PATH" ]]; then
    log_info "กำลังตั้งค่า capability สำหรับ masscan (raw socket โดยไม่ต้องรันทั้งโปรแกรมด้วย root)..."
    $SUDO setcap cap_net_raw,cap_net_admin+eip "$MASSCAN_PATH" || \
        log_warn "ไม่สามารถตั้งค่า setcap ได้ — masscan อาจต้องรันด้วย sudo"
fi

NMAP_PATH=$(command -v nmap || true)
if [[ -n "$NMAP_PATH" ]]; then
    log_info "กำลังตั้งค่า capability สำหรับ nmap (SYN scan โดยไม่ต้องรันทั้งโปรแกรมด้วย root)..."
    $SUDO setcap cap_net_raw,cap_net_admin+eip "$NMAP_PATH" || \
        log_warn "ไม่สามารถตั้งค่า setcap ได้ — บาง scan type ของ nmap อาจต้องใช้ sudo"
fi

# --- สรุปผลการติดตั้ง ---
echo ""
log_info "==== สรุปสถานะเครื่องมือ ===="
for tool in nmap masscan ncat hydra ncrack evil-winrm ruby; do
    if command -v "$tool" &>/dev/null; then
        VERSION_INFO=$("$tool" --version 2>&1 | head -n1 || echo "N/A")
        echo -e "  ${GREEN}✔${NC} $tool  ($VERSION_INFO)"
    else
        echo -e "  ${RED}✘${NC} $tool  (ไม่พบ — ติดตั้งไม่สำเร็จ)"
    fi
done

echo ""
log_info "ติดตั้งเสร็จสิ้น ขั้นตอนถัดไป: ตั้งค่า Python virtualenv แล้วรัน 'pip install -r requirements.txt'"
log_warn "ใช้เครื่องมือเหล่านี้เฉพาะภายในขอบเขต sandbox/lab ที่ได้รับอนุญาตเท่านั้น"
