# -*- coding: utf-8 -*-
"""
SiamBraille 1.0 - Anti-Tamper 14-Day Free Trial Guard
ระบบควบคุมสิทธิ์ทดลองใช้งานฟรี 14 วัน พร้อมระบบอุดช่องโหว่และป้องกันการรีเซ็ตขั้นสูง (Multi-Layer Defense):
1. Hardware-bound Fingerprint: ผูกกับ Motherboard UUID + CPU ID อย่างถาวร
2. Redundant Hidden Stores (กระจายซ่อน 4 จุดบน Windows):
   - Store 1: HKLM Registry (Machine-level): SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\.sb_state
   - Store 2: HKCU Registry (User-level): Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\.sb_state
   - Store 3: C:\\ProgramData\\SiamBraille\\.sys_signature (ซ่อนแบบ Hidden + System Protected OS File)
   - Store 4: %APPDATA%\\SiamBraille\\trial.dat
3. Self-Healing Mechanism: หากผู้ใช้ลบโฟลเดอร์โปรแกรม ลบ AppData หรือลบจุดใดจุดหนึ่ง ระบบจะดึงวันเริ่มต้นที่เก่าที่สุดจากจุดที่เหลือมาสร้างทับใหม่ทันที
4. Anti-Clock Rollback: ตรวจจับการหมุนนาฬิกาคอมพิวเตอร์ย้อนหลัง
5. Cloud Verification: ซิงค์รหัส HWID แฮชกับ Firebase Cloud เมื่อต่อเน็ต เพื่อจำประวัติแม้จะฟอร์แมตล้างดิสก์
6. Cryptographic Signature: ข้อมูลทุกชุดเข้ารหัสและเซ็นดิจิทัลด้วย HMAC-SHA256 ป้องกันการแก้ไขตัวเลขในไฟล์หรือ Registry เอง
"""

import os
import sys
import json
import time
import hmac
import hashlib
import base64
import ctypes
import socket
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional, Tuple, Dict, Any

try:
    import winreg
except ImportError:
    winreg = None

import license_guard

TRIAL_SALT = b"SiamBraille-AntiTamper-Trial-Salt-2026-V1"
TRIAL_DURATION_DAYS = 14
TRIAL_DURATION_SECONDS = TRIAL_DURATION_DAYS * 86400

# Registry Subkeys
HKLM_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\.sb_state"
HKCU_PATH = r"Software\Microsoft\Windows\CurrentVersion\Explorer\.sb_state"
REG_VAL_NAME = "SecTrialBlob"


def get_hashed_device_id(hwid: str) -> str:
    """แปลง HWID ให้เป็นแฮชเฉพาะทางสำหรับเก็บในฐานข้อมูล Cloud แบบไม่เปิดเผยสเปกเครื่อง"""
    return hashlib.sha256(hwid.encode("utf-8") + TRIAL_SALT).hexdigest().upper()


def get_programdata_path() -> str:
    progdata = os.getenv("PROGRAMDATA", "C:\\ProgramData")
    target_dir = os.path.join(progdata, "SiamBraille")
    return os.path.join(target_dir, ".sys_signature")


def get_appdata_path() -> str:
    appdata = os.getenv("APPDATA", "")
    if not appdata:
        appdata = os.path.expanduser("~")
    target_dir = os.path.join(appdata, "SiamBraille")
    return os.path.join(target_dir, "trial.dat")


def set_hidden_system_attributes(file_path: str):
    """ตั้งค่าไฟล์ให้เป็น Hidden + System Protected Operating System File"""
    if os.path.exists(file_path) and hasattr(ctypes, "windll"):
        try:
            # 0x02 = FILE_ATTRIBUTE_HIDDEN, 0x04 = FILE_ATTRIBUTE_SYSTEM
            ctypes.windll.kernel32.SetFileAttributesW(file_path, 0x02 | 0x04)
        except Exception:
            pass


def clear_attributes_for_write(file_path: str):
    """ปลดแอตทริบิวต์ก่อนเขียนไฟล์ทับ"""
    if os.path.exists(file_path) and hasattr(ctypes, "windll"):
        try:
            # 0x80 = FILE_ATTRIBUTE_NORMAL
            ctypes.windll.kernel32.SetFileAttributesW(file_path, 0x80)
        except Exception:
            pass


def sign_trial_payload(payload: Dict[str, Any]) -> str:
    """สร้างก้อน Base64 พร้อม HMAC-SHA256 ลายเซ็นดิจิทัล"""
    json_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    sig = hmac.new(license_guard.MASTER_SIGN_KEY + TRIAL_SALT, json_bytes, hashlib.sha256).hexdigest().upper()
    pkg = {
        "data": payload,
        "sig": sig,
        "ver": "1.0"
    }
    return base64.b64encode(json.dumps(pkg).encode('utf-8')).decode('ascii')


def verify_trial_payload(token_b64: str, expected_hwid: str) -> Optional[Dict[str, Any]]:
    """ตรวจสอบความถูกต้องของก้อน Token ป้องกันการแก้ไขตัวเลขหรือดัดแปลง"""
    if not token_b64 or not token_b64.strip():
        return None
    try:
        raw_json = base64.b64decode(token_b64.strip()).decode('utf-8')
        pkg = json.loads(raw_json)
        data = pkg.get("data", {})
        sig = pkg.get("sig", "")

        json_bytes = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')
        expected_sig = hmac.new(license_guard.MASTER_SIGN_KEY + TRIAL_SALT, json_bytes, hashlib.sha256).hexdigest().upper()

        if not hmac.compare_digest(sig, expected_sig):
            return None

        # ตรวจสอบว่าตรงกับ HWID ของเครื่องนี้หรือไม่
        if data.get("hwid") != expected_hwid:
            return None

        return data
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Redundant Storage Accessors
# ---------------------------------------------------------------------------
def read_registry_hklm() -> str:
    if not winreg:
        return ""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, HKLM_PATH, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, REG_VAL_NAME)
        winreg.CloseKey(key)
        return str(val).strip()
    except Exception:
        return ""


def write_registry_hklm(token_str: str) -> bool:
    if not winreg:
        return False
    try:
        key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, HKLM_PATH, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, REG_VAL_NAME, 0, winreg.REG_SZ, token_str)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def read_registry_hkcu() -> str:
    if not winreg:
        return ""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, HKCU_PATH, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, REG_VAL_NAME)
        winreg.CloseKey(key)
        return str(val).strip()
    except Exception:
        return ""


def write_registry_hkcu(token_str: str) -> bool:
    if not winreg:
        return False
    try:
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, HKCU_PATH, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, REG_VAL_NAME, 0, winreg.REG_SZ, token_str)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def read_file_token(path: str) -> str:
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def write_file_token(path: str, token_str: str, make_system_hidden: bool = False) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        clear_attributes_for_write(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(token_str)
        if make_system_hidden:
            set_hidden_system_attributes(path)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Cloud Online Sync & Clock Check (Firebase Firestore)
# ---------------------------------------------------------------------------
def check_cloud_trial_history(hwid_hash: str) -> Tuple[Optional[int], Optional[int]]:
    """
    ตรวจสอบประวัติใน Cloud Firestore ว่าเครื่องนี้เคยลงทะเบียนทดลองใช้มาก่อนหรือไม่
    คืนค่า (first_run_timestamp, true_network_timestamp)
    """
    import urllib.request
    firestore_url = f"https://firestore.googleapis.com/v1/projects/siam-braille/databases/(default)/documents/trials/{hwid_hash}"
    network_time = None
    first_run = None

    try:
        req = urllib.request.Request(firestore_url, headers={"User-Agent": "SiamBraille-Guard/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            # ดึง True Network Time จาก Header Date ของ Google Server
            date_header = resp.headers.get("Date")
            if date_header:
                try:
                    network_time = int(parsedate_to_datetime(date_header).timestamp())
                except Exception:
                    pass

            if resp.status == 200:
                body = json.loads(resp.read().decode('utf-8'))
                fields = body.get("fields", {})
                first_run_str = fields.get("first_run", {}).get("integerValue", "")
                if first_run_str:
                    first_run = int(first_run_str)
    except Exception:
        pass

    return first_run, network_time


def register_cloud_trial(hwid_hash: str, first_run: int, expires_at: int):
    """ลงทะเบียนข้อมูลทดลองใช้งานขึ้น Cloud Firestore แบบเบื้องหลัง"""
    import urllib.request
    firestore_url = f"https://firestore.googleapis.com/v1/projects/siam-braille/databases/(default)/documents/trials/{hwid_hash}"
    payload = {
        "fields": {
            "hwid_hash": {"stringValue": hwid_hash},
            "first_run": {"integerValue": str(first_run)},
            "expires_at": {"integerValue": str(expires_at)},
            "platform": {"stringValue": "Windows"}
        }
    }
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            firestore_url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "SiamBraille-Guard/1.0"},
            method="PATCH"
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Master Trial Manager
# ---------------------------------------------------------------------------
class TrialManager:
    """
    คลาสตรวจสอบและควบคุมสิทธิ์ทดลองใช้งาน 14 วัน
    พร้อมระบบตรวจจับการลบโฟลเดอร์ รีเซ็ตเครื่อง หรือหมุนนาฬิกาย้อนหลัง
    """
    def __init__(self):
        self.hwid = license_guard.get_hardware_fingerprint()
        self.hwid_hash = get_hashed_device_id(self.hwid)
        
        self.is_trial_active = False
        self.is_expired = False
        self.is_tampered = False
        
        self.first_run_time: int = 0
        self.expires_at: int = 0
        self.last_seen_time: int = 0
        self.days_remaining: int = 0
        self.day_number: int = 1
        self.status_message = ""
        
        self.verify_and_update()

    def verify_and_update(self):
        now = int(time.time())
        store_tokens = [
            read_registry_hklm(),
            read_registry_hkcu(),
            read_file_token(get_programdata_path()),
            read_file_token(get_appdata_path())
        ]

        valid_records = []
        for t in store_tokens:
            if t:
                rec = verify_trial_payload(t, self.hwid)
                if rec:
                    valid_records.append(rec)

        # 1. กรณีพบข้อมูลบันทึกอยู่ในเครื่องอย่างน้อย 1 จุด
        if valid_records:
            # เลือกวันที่เริ่มต้นที่เก่าที่สุดเสมอ (ป้องกันผู้ใช้ลบไฟล์ล่าสุดเพื่อแอบเริ่มนับใหม่)
            earliest_first_run = min(r.get("first_run", now) for r in valid_records)
            highest_last_seen = max(r.get("last_seen", now) for r in valid_records)

            self.first_run_time = earliest_first_run
            self.expires_at = self.first_run_time + TRIAL_DURATION_SECONDS
            self.last_seen_time = highest_last_seen

            # ตรวจสอบการหมุนนาฬิกาย้อนหลัง (Clock Rollback)
            if now < (self.last_seen_time - 3600):
                self.is_tampered = True
                self.is_expired = True
                self.status_message = "ตรวจพบการปรับเวลาเครื่องย้อนหลัง ระบบระงับสิทธิ์ทดลองใช้"
                return

        # 2. กรณีไม่พบข้อมูลในเครื่องเลย (เช่น เพิ่งลงครั้งแรก หรือผู้ใช้ล้างเครื่อง/ฟอร์แมตดิสก์มา)
        else:
            # ตรวจสอบกับ Cloud Firestore ก่อน
            cloud_first_run, true_net_time = check_cloud_trial_history(self.hwid_hash)
            if true_net_time and true_net_time > now:
                now = true_net_time

            if cloud_first_run and cloud_first_run > 0:
                # เครื่องนี้เคยทดลองใช้แล้ว ดึงวันที่เก่ามาบังคับใช้ทันที!
                self.first_run_time = cloud_first_run
                self.expires_at = self.first_run_time + TRIAL_DURATION_SECONDS
                self.last_seen_time = now
            else:
                # ใช้งานครั้งแรกจริงๆ เริ่มต้นนับ 14 วัน
                self.first_run_time = now
                self.expires_at = now + TRIAL_DURATION_SECONDS
                self.last_seen_time = now
                
                # ส่งขึ้น Cloud บันทึกไว้
                try:
                    import threading
                    threading.Thread(
                        target=register_cloud_trial,
                        args=(self.hwid_hash, self.first_run_time, self.expires_at),
                        daemon=True
                    ).start()
                except Exception:
                    pass

        # ปรับปรุงเวลาล่าสุด
        self.last_seen_time = max(now, self.last_seen_time)

        # คำนวณวันคงเหลือ
        diff_seconds = self.expires_at - now
        self.days_remaining = max(0, int(diff_seconds / 86400))
        used_seconds = now - self.first_run_time
        self.day_number = min(14, max(1, int(used_seconds / 86400) + 1))

        if now >= self.expires_at:
            self.is_trial_active = False
            self.is_expired = True
            exp_date = datetime.fromtimestamp(self.expires_at).strftime("%d/%m/%Y")
            self.status_message = f"ระยะเวลาทดลองใช้ฟรี 14 วันสิ้นสุดลงแล้วเมื่อ {exp_date} (กรุณาสั่งซื้อหรือเปิดใช้งานลิขสิทธิ์)"
        else:
            self.is_trial_active = True
            self.is_expired = False
            self.status_message = f"ทดลองใช้ฟรีวันที่ {self.day_number}/14 วัน (เหลืออีก {self.days_remaining} วัน)"

        # 3. กลไก Self-Healing: กระจายเขียนบันทึกซ่อมแซมลงทุก Store ให้ครบ 4 จุดเสมอ
        self.self_heal_all_stores()

    def self_heal_all_stores(self):
        """เขียนข้อมูลที่ถูกต้องลงทุกจุดจัดเก็บ ป้องกันการถูกลบทีละจุด"""
        payload = {
            "hwid": self.hwid,
            "hwid_hash": self.hwid_hash,
            "first_run": self.first_run_time,
            "expires_at": self.expires_at,
            "last_seen": self.last_seen_time,
            "duration": TRIAL_DURATION_DAYS
        }
        token = sign_trial_payload(payload)

        # บันทึกทั้ง 4 จุด
        write_registry_hkcu(token)
        write_registry_hklm(token)
        write_file_token(get_programdata_path(), token, make_system_hidden=True)
        write_file_token(get_appdata_path(), token, make_system_hidden=False)


# Singleton
global_trial_manager = TrialManager()
