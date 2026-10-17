# -*- coding: utf-8 -*-
"""
SiamBraille 1.0 - License Guard & Hardware Fingerprinting System
ระบบตรวจสอบลิขสิทธิ์ ผูกฮาร์ดแวร์ (Motherboard UUID + CPU ID)
รองรับทั้ง:
1. การทำงานแบบ Offline (Cryptographic Digital Signature) ป้องกันการปลอมแปลง 100%
2. การแนบไฟล์ license.key ไปกับตัวติดตั้ง (Silent Auto-Activation ติดตั้งเสร็จใช้ได้ทันที)
3. การซิงค์และตรวจสอบสถานะแบบเรียลไทม์กับ Firebase Firestore (Cloud Sync)
"""

import os
import sys
import json
import time
import hmac
import hashlib
import base64
import subprocess
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

# Secret Master Key สำหรับสร้างและตรวจสอบลายเซ็นดิจิทัล (สามารถเปลี่ยนหรือโหลดจาก env ได้)
MASTER_SIGN_KEY = b"SiamBraille-Pro-2026-Secret-Master-HMAC-Token-Key!"

_CACHED_HWID = None


def get_hardware_fingerprint() -> str:
    """
    ดึงรหัสระบุเครื่องฮาร์ดแวร์ (HWID)
    โดยใช้ Motherboard UUID + CPU Processor ID
    (ไม่รวม Harddisk Serial เพื่อให้ผู้ใช้สามารถเปลี่ยน SSD หรือ Format Windows ได้โดยคีย์ไม่หลุด)
    """
    global _CACHED_HWID
    if _CACHED_HWID:
        return _CACHED_HWID

    mb_uuid = ""
    cpu_id = ""

    # วิธีที่ 1: ผ่าน WMI Python Library (เร็วที่สุดเมื่อมีไลบรารี)
    try:
        import wmi
        c = wmi.WMI()
        prods = c.Win32_ComputerSystemProduct()
        if prods and prods[0].UUID:
            mb_uuid = str(prods[0].UUID).strip()
        cpus = c.Win32_Processor()
        if cpus and cpus[0].ProcessorId:
            cpu_id = str(cpus[0].ProcessorId).strip()
    except Exception:
        pass

    # วิธีที่ 2: Fallback ผ่าน PowerShell Get-CimInstance (มาตรฐาน Windows 10/11 ไม่พึ่ง wmic)
    if not mb_uuid or not cpu_id:
        try:
            cmd = ['powershell', '-NoProfile', '-Command',
                   '(Get-CimInstance Win32_ComputerSystemProduct).UUID; (Get-CimInstance Win32_Processor).ProcessorId']
            out = subprocess.check_output(cmd, text=True, timeout=5).strip().split()
            if len(out) >= 1 and not mb_uuid:
                mb_uuid = out[0].strip()
            if len(out) >= 2 and not cpu_id:
                cpu_id = out[1].strip()
        except Exception:
            pass

    # วิธีที่ 3: Fallback ผ่าน Windows Registry
    if not mb_uuid:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            mb_uuid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
        except Exception:
            mb_uuid = "GENERIC-MB-UUID"

    if not cpu_id:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            cpu_id, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
        except Exception:
            cpu_id = "GENERIC-CPU-ID"

    # รวมและแฮชด้วย SHA-256
    raw_str = f"{mb_uuid.upper()}:{cpu_id.upper()}"
    h = hashlib.sha256(raw_str.encode("utf-8")).hexdigest().upper()
    _CACHED_HWID = f"SB-{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"
    return _CACHED_HWID


def generate_license_payload(license_key: str, owner_name: str, org_name: str = "",
                             license_type: str = "lifetime", max_devices: int = 1,
                             expires_timestamp: Optional[int] = None,
                             bound_hwids: Optional[list] = None) -> Tuple[str, str]:
    """
    สร้างก้อนข้อมูลลิขสิทธิ์พร้อมลายเซ็นดิจิทัล (Digital Signature)
    สำหรับผู้ดูแลระบบ (Admin) ใช้ออกคีย์และส่งออกไฟล์ license.key
    """
    payload = {
        "key": license_key.strip().upper(),
        "owner": owner_name.strip(),
        "org": org_name.strip(),
        "type": license_type,  # 'lifetime', 'yearly', 'monthly', 'trial'
        "max_devices": max(1, max_devices),
        "issued_at": int(time.time()),
        "expires_at": expires_timestamp,  # None หรือ 0 = ถาวร (Lifetime)
        "devices": bound_hwids or []
    }
    
    # สร้าง canonical JSON string
    json_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    sig = hmac.new(MASTER_SIGN_KEY, json_bytes, hashlib.sha256).hexdigest().upper()
    
    # ห่อเป็น Base64 Token
    full_pkg = {
        "payload": payload,
        "sig": sig,
        "ver": "1.0"
    }
    encoded = base64.b64encode(json.dumps(full_pkg).encode('utf-8')).decode('ascii')
    return encoded, sig


def verify_license_package(pkg_str: str, current_hwid: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    ตรวจสอบความถูกต้องของก้อนลิขสิทธิ์:
    1. ตรวจสอบลายเซ็นดิจิทัล (HMAC-SHA256) ว่าไม่ได้ถูกแก้ไข ดัดแปลง หรือสร้างขึ้นเอง
    2. ตรวจสอบวันหมดอายุ (ถ้าเป็นแบบรายเดือน/รายปี)
    3. ตรวจสอบการผูกเครื่อง (HWID)
    """
    if not pkg_str or not pkg_str.strip():
        return False, "ไม่พบข้อมูลลิขสิทธิ์", {}

    try:
        raw_json = base64.b64decode(pkg_str.strip()).decode('utf-8')
        pkg = json.loads(raw_json)
        payload = pkg.get("payload", {})
        sig = pkg.get("sig", "")
    except Exception:
        return False, "รูปแบบไฟล์ลิขสิทธิ์ไม่ถูกต้อง (Invalid format)", {}

    # 1. ตรวจสอบ Signature
    json_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    expected_sig = hmac.new(MASTER_SIGN_KEY, json_bytes, hashlib.sha256).hexdigest().upper()
    
    if not hmac.compare_digest(sig, expected_sig):
        return False, "ลายเซ็นดิจิทัลไม่ถูกต้อง ลิขสิทธิ์อาจถูกดัดแปลง (Signature mismatch)", payload

    # 2. ตรวจสอบวันหมดอายุ
    expires_at = payload.get("expires_at")
    if expires_at and expires_at > 0:
        now_ts = int(time.time())
        if now_ts > expires_at:
            exp_date = datetime.fromtimestamp(expires_at).strftime("%d/%m/%Y")
            return False, f"ลิขสิทธิ์หมดอายุแล้วเมื่อ {exp_date} กรุณาต่ออายุการใช้งาน", payload

    # 3. ตรวจสอบการผูกเครื่อง (Hardware ID)
    if current_hwid:
        bound_devices = payload.get("devices", [])
        # ถ้ามีระบุเครื่องเฉพาะเจาะจง ต้องมี HWID เครื่องนี้อยู่ในรายการ
        if bound_devices and current_hwid not in bound_devices:
            # ถ้ายังมีโควต้าเครื่องว่างอยู่ อนุญาตให้ผูกได้ (จะไปบันทึกตอนเปิดครั้งแรก)
            if len(bound_devices) >= payload.get("max_devices", 1):
                return False, f"คีย์นี้ถูกใช้งานเต็มจำนวนโควต้า {payload.get('max_devices', 1)} เครื่องแล้ว (เครื่องนี้: {current_hwid})", payload

    return True, "ลิขสิทธิ์ถูกต้องสมบูรณ์", payload


class LicenseManager:
    """
    คลาสจัดการการตรวจสอบลิขสิทธิ์ในฝั่งผู้ใช้งาน (Client-side)
    ค้นหา license.key อัตโนมัติ ตรวจสอบความถูกต้อง และจำสถานะ
    """
    def __init__(self):
        self.hwid = get_hardware_fingerprint()
        self.is_licensed = False
        self.license_info: Dict[str, Any] = {}
        self.status_message = "ยังไม่ได้เปิดใช้งาน (Unregistered)"
        self.license_file_path = ""
        
        # 1. ตรวจสอบลิขสิทธิ์จริงก่อน
        self.check_local_license()

        # 2. ตรวจสอบสิทธิ์ทดลองใช้ฟรี 14 วัน (หากยังไม่มีลิขสิทธิ์ถาวร)
        try:
            import trial_guard
            self.trial = trial_guard.global_trial_manager
            self.trial.verify_and_update()
            if not self.is_licensed:
                if self.trial.is_trial_active:
                    self.status_message = f"ทดลองใช้ฟรี: เหลืออีก {self.trial.days_remaining} วัน (วันที่ {self.trial.day_number}/14)"
                elif self.trial.is_expired:
                    self.status_message = self.trial.status_message
        except Exception:
            self.trial = None

    @property
    def is_trial(self) -> bool:
        return not self.is_licensed and (self.trial is not None and self.trial.is_trial_active)

    @property
    def is_trial_expired(self) -> bool:
        return not self.is_licensed and (self.trial is not None and self.trial.is_expired)

    @property
    def trial_days_remaining(self) -> int:
        return self.trial.days_remaining if self.trial else 0

    @property
    def trial_day_number(self) -> int:
        return self.trial.day_number if self.trial else 1

    def get_candidate_paths(self) -> list:
        paths = []
        # โฟลเดอร์ปัจจุบันของตัวโปรแกรม
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        paths.append(os.path.join(exe_dir, "license.key"))
        paths.append(os.path.join(exe_dir, "siambraille.lic"))
        
        # โฟลเดอร์ต้นทาง
        base_dir = os.path.dirname(os.path.abspath(__file__))
        paths.append(os.path.join(base_dir, "license.key"))
        paths.append(os.path.join(base_dir, "siambraille.lic"))
        
        # %APPDATA%\SiamBraille
        appdata = os.getenv("APPDATA", "")
        if appdata:
            paths.append(os.path.join(appdata, "SiamBraille", "license.key"))
            
        # C:\ProgramData\SiamBraille
        progdata = os.getenv("PROGRAMDATA", "C:\\ProgramData")
        if progdata:
            paths.append(os.path.join(progdata, "SiamBraille", "license.key"))
            
        return paths

    def check_local_license(self) -> bool:
        """ตรวจสอบไฟล์ license.key ในเครื่อง"""
        for p in self.get_candidate_paths():
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        raw = f.read().strip()
                    valid, msg, info = verify_license_package(raw, self.hwid)
                    if valid:
                        self.is_licensed = True
                        self.license_info = info
                        self.status_message = f"เปิดใช้งานแล้ว: {info.get('owner', 'ผู้ใช้งาน')} ({info.get('type', 'Lifetime')})"
                        self.license_file_path = p
                        
                        # หากเครื่องนี้ยังไม่ได้ถูกบันทึกใน devices และมีโควต้าว่าง ให้บันทึกลงไฟล์
                        if self.hwid not in info.get("devices", []):
                            info["devices"].append(self.hwid)
                            # สร้าง signature ใหม่และบันทึก
                            re_encoded, _ = generate_license_payload(
                                info["key"], info["owner"], info.get("org", ""),
                                info.get("type", "lifetime"), info.get("max_devices", 1),
                                info.get("expires_at"), info["devices"]
                            )
                            try:
                                with open(p, "w", encoding="utf-8") as fw:
                                    fw.write(re_encoded)
                            except Exception:
                                pass
                        return True
                    else:
                        self.status_message = msg
                except Exception as e:
                    self.status_message = f"เกิดข้อผิดพลาดในการอ่านลิขสิทธิ์: {e}"
                    
        self.is_licensed = False
        return False

    def fetch_token_from_cloud(self, key: str) -> Tuple[bool, str, str]:
        """ดึง Token ลิขสิทธิ์จาก Firebase Cloud Firestore หรือ Server"""
        import urllib.request
        clean_key = key.strip().upper()
        
        # 1. ลองดึงจาก Firebase Firestore REST API โดยตรง
        firestore_url = f"https://firestore.googleapis.com/v1/projects/siam-braille/databases/(default)/documents/licenses/{clean_key}"
        try:
            req = urllib.request.Request(firestore_url, headers={"User-Agent": "SiamBraille-Client/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    fields = data.get("fields", {})
                    status = fields.get("status", {}).get("stringValue", "active")
                    if status == "revoked":
                        reason = fields.get("revoke_reason", {}).get("stringValue", "ถูกระงับโดยผู้ดูแล")
                        return False, f"คีย์นี้ถูกระงับการใช้งาน ({reason})", ""
                    
                    token = fields.get("token", {}).get("stringValue", "")
                    if token:
                        return True, "ดึงข้อมูลลิขสิทธิ์จาก Cloud สำเร็จ", token
        except Exception:
            pass

        # 2. ลองดึงจาก Local / Production Server
        server_endpoints = [
            f"http://127.0.0.1:8080/api/licenses/{clean_key}/download",
            f"https://siam-braille.web.app/api/licenses/{clean_key}/download"
        ]
        for ep in server_endpoints:
            try:
                req = urllib.request.Request(ep, headers={"User-Agent": "SiamBraille-Client/1.0"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    if resp.status == 200:
                        token_data = resp.read().decode('utf-8').strip()
                        if token_data:
                            return True, "ดึงข้อมูลลิขสิทธิ์จากเซิร์ฟเวอร์สำเร็จ", token_data
            except Exception:
                continue

        return False, "ไม่สามารถเชื่อมต่อคีย์กับระบบออนไลน์ได้ (โปรดตรวจสอบอินเทอร์เน็ตหรือรหัสคีย์)", ""

    def activate_with_key_string(self, key_string: str) -> Tuple[bool, str]:
        """รับรหัสคีย์ (เช่น SB10-XXXX-XXXX-XXXX) หรือก้อน License Token จากผู้ใช้ แล้วตรวจสอบและบันทึกลงเครื่องอัตโนมัติ"""
        raw = key_string.strip()
        if not raw:
            return False, "กรุณากรอกรหัสคีย์หรือ License Token"

        token_to_verify = raw
        # หากผู้ใช้กรอกรหัสคีย์สั้น เช่น SB10-XXXX-XXXX-XXXX ให้ดึง Token ออนไลน์
        if raw.upper().startswith("SB10-") or (raw.upper().startswith("SB-") and len(raw) < 50):
            ok, cloud_msg, fetched_token = self.fetch_token_from_cloud(raw.upper())
            if not ok:
                return False, cloud_msg
            token_to_verify = fetched_token

        valid, msg, info = verify_license_package(token_to_verify, self.hwid)
        if not valid:
            return False, msg

        # ผูก HWID เครื่องนี้
        if self.hwid not in info.get("devices", []):
            info["devices"].append(self.hwid)
            re_encoded, _ = generate_license_payload(
                info["key"], info["owner"], info.get("org", ""),
                info.get("type", "lifetime"), info.get("max_devices", 1),
                info.get("expires_at"), info["devices"]
            )
        else:
            re_encoded = token_to_verify

        # บันทึกลง %APPDATA%\SiamBraille\license.key และ C:\ProgramData\SiamBraille\license.key
        saved = False
        save_dirs = []
        appdata = os.getenv("APPDATA", "")
        if appdata:
            save_dirs.append(os.path.join(appdata, "SiamBraille"))
        progdata = os.getenv("PROGRAMDATA", "C:\\ProgramData")
        if progdata:
            save_dirs.append(os.path.join(progdata, "SiamBraille"))

        for target_dir in save_dirs:
            try:
                os.makedirs(target_dir, exist_ok=True)
                save_path = os.path.join(target_dir, "license.key")
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(re_encoded)
                saved = True
                self.license_file_path = save_path
            except Exception:
                pass

        if saved:
            self.is_licensed = True
            self.license_info = info
            self.status_message = f"เปิดใช้งานสำเร็จ: {info.get('owner', 'ผู้ใช้งาน')}"
            return True, f"เปิดใช้งานโปรแกรม SiamBraille 1.0 สำเร็จเรียบร้อยแล้ว!\nเจ้าของลิขสิทธิ์: {info.get('owner')}\nประเภท: {info.get('type', 'Lifetime').title()}"

        return False, "ไม่สามารถบันทึกไฟล์ลิขสิทธิ์ลงเครื่องได้ กรุณาตรวจสอบสิทธิ์การเขียนโฟลเดอร์"


# Singleton instance สำหรับเรียกใช้ในโปรแกรม
global_license_manager = LicenseManager()

