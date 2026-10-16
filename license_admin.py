# -*- coding: utf-8 -*-
"""
SiamBraille 1.0 - License Admin Tool
เครื่องมือจัดการคีย์สำหรับผู้ดูแลระบบ (Admin)
- ออกคีย์ใหม่ (เดี่ยว / กลุ่ม / องค์กร / รายเดือน / รายปี / ถาวร)
- ส่งออกไฟล์ license.key สำหรับแนบไปกับตัวติดตั้ง (Inno Setup)
- ซิงค์และบันทึกฐานข้อมูล Firebase Firestore
- ตรวจสอบรายการคีย์และอุปกรณ์ที่ลงทะเบียน
"""

import os
import sys
import json
import time
import uuid
import secrets
import argparse
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import license_guard

FIREBASE_KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "siam-braille-firebase-adminsdk-fbsvc-5131a4721e.json")
LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "licenses_db.json")

def generate_random_key() -> str:
    """สร้างรหัสคีย์รูปแบบ SB10-XXXX-XXXX-XXXX"""
    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    part3 = secrets.token_hex(2).upper()
    return f"SB10-{part1}-{part2}-{part3}"

def get_firestore_client():
    if not os.path.exists(FIREBASE_KEY_PATH):
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        return None

def load_local_db() -> Dict[str, Any]:
    if os.path.exists(LOCAL_DB_PATH):
        try:
            with open(LOCAL_DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_local_db(db: Dict[str, Any]):
    with open(LOCAL_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def create_license(owner: str, org: str = "", lic_type: str = "lifetime",
                   max_devices: int = 1, days: int = 0,
                   bound_hwid: str = "", export_path: str = "") -> Dict[str, Any]:
    """
    สร้าง License ใหม่
    - lic_type: 'lifetime', 'yearly', 'monthly', 'trial'
    - max_devices: จำนวนเครื่องที่อนุญาต (1 = เดี่ยว, 5/10/20 = กลุ่ม/องค์กร)
    - days: จำนวนวันหมดอายุ (ถ้า 0 และไม่ใช่ lifetime จะคำนวณตามประเภท)
    - bound_hwid: รหัส HWID เจาะจง (ถ้าไม่ระบุ จะเปิดให้ผูกเครื่องแรกที่เปิด)
    """
    key = generate_random_key()
    
    now = int(time.time())
    expires_at = None
    
    if lic_type == "yearly":
        expires_at = now + (365 * 86400)
    elif lic_type == "monthly":
        expires_at = now + (30 * 86400)
    elif lic_type == "trial":
        expires_at = now + (14 * 86400)
    elif days > 0:
        expires_at = now + (days * 86400)
        
    bound_devices = [bound_hwid.strip()] if bound_hwid.strip() else []
    
    token, sig = license_guard.generate_license_payload(
        license_key=key,
        owner_name=owner,
        org_name=org,
        license_type=lic_type,
        max_devices=max_devices,
        expires_timestamp=expires_at,
        bound_hwids=bound_devices
    )
    
    record = {
        "key": key,
        "owner": owner,
        "org": org,
        "type": lic_type,
        "max_devices": max_devices,
        "issued_at": now,
        "expires_at": expires_at,
        "devices": bound_devices,
        "status": "active",
        "token": token,
        "sig": sig,
        "last_sync": now
    }
    
    # 1. บันทึกลง Local DB
    ldb = load_local_db()
    ldb[key] = record
    save_local_db(ldb)
    
    # 2. บันทึกลง Firebase Firestore (ถ้าต่อได้)
    fs = get_firestore_client()
    if fs:
        try:
            fs.collection("licenses").document(key).set(record)
            print(f"[Firebase] บันทึกคีย์ {key} ขึ้น Cloud สำเร็จ!")
        except Exception as e:
            print(f"[Firebase Notice] Cloud DB ยังไม่พร้อม บันทึกลง Local DB แทน: {e}")
            
    # 3. ส่งออกไฟล์ license.key
    if export_path:
        os.makedirs(os.path.dirname(os.path.abspath(export_path)), exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(token)
        print(f"[Export] ส่งออกไฟล์ลิขสิทธิ์สำเร็จ: {export_path}")
        
    return record


def list_all_licenses() -> List[Dict[str, Any]]:
    """ดึงรายการลิขสิทธิ์ทั้งหมด (ลองดึงจาก Firebase ก่อน ถ้าไม่ได้ใช้ Local DB)"""
    fs = get_firestore_client()
    if fs:
        try:
            docs = fs.collection("licenses").stream()
            res = [d.to_dict() for d in docs]
            if res:
                return res
        except Exception:
            pass
            
    ldb = load_local_db()
    return list(ldb.values())


def revoke_license(key: str, reason: str = "Suspended by admin") -> bool:
    """ระงับหรือยกเลิกคีย์"""
    ldb = load_local_db()
    if key in ldb:
        ldb[key]["status"] = "revoked"
        ldb[key]["revoke_reason"] = reason
        save_local_db(ldb)
        
    fs = get_firestore_client()
    if fs:
        try:
            fs.collection("licenses").document(key).update({
                "status": "revoked",
                "revoke_reason": reason
            })
            return True
        except Exception:
            pass
    return key in ldb


def reactivate_license(key: str) -> bool:
    """เปิดใช้งานคีย์อีกครั้งหลังจากถูกระงับ"""
    ldb = load_local_db()
    if key in ldb:
        ldb[key]["status"] = "active"
        if "revoke_reason" in ldb[key]:
            del ldb[key]["revoke_reason"]
        save_local_db(ldb)
        
    fs = get_firestore_client()
    if fs:
        try:
            fs.collection("licenses").document(key).update({
                "status": "active",
                "revoke_reason": ""
            })
            return True
        except Exception:
            pass
    return key in ldb


def reset_devices(key: str) -> bool:
    """ปลดล็อกอุปกรณ์ทั้งหมดที่ผูกไว้ เพื่อให้ลูกค้านำคีย์ไปเปิดใช้งานในคอมพิวเตอร์เครื่องใหม่ได้ (ย้ายเครื่อง)"""
    ldb = load_local_db()
    if key in ldb:
        ldb[key]["devices"] = []
        save_local_db(ldb)
        
    fs = get_firestore_client()
    if fs:
        try:
            fs.collection("licenses").document(key).update({
                "devices": []
            })
            return True
        except Exception:
            pass
    return key in ldb


def delete_license(key: str) -> bool:
    """ลบคีย์ลิขสิทธิ์ออกจากระบบอย่างถาวร ทั้ง Local DB และ Firebase Firestore"""
    deleted = False
    ldb = load_local_db()
    if key in ldb:
        del ldb[key]
        save_local_db(ldb)
        deleted = True
        
    fs = get_firestore_client()
    if fs:
        try:
            fs.collection("licenses").document(key).delete()
            deleted = True
        except Exception:
            pass
    return deleted



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SiamBraille 1.0 License Administration Tool")
    parser.add_argument("--create", action="store_true", help="สร้างคีย์ใหม่")
    parser.add_argument("--owner", type=str, default="ผู้ใช้งานทั่วไป", help="ชื่อเจ้าของคีย์")
    parser.add_argument("--org", type=str, default="", help="ชื่อหน่วยงาน/องค์กร/โรงเรียน")
    parser.add_argument("--type", type=str, choices=["lifetime", "yearly", "monthly", "trial"], default="lifetime", help="ประเภทลิขสิทธิ์")
    parser.add_argument("--devices", type=int, default=1, help="จำนวนเครื่องสูงสุดที่อนุญาต")
    parser.add_argument("--hwid", type=str, default="", help="ระบุ HWID เจาะจง (ถ้าไม่ระบุจะผูกเครื่องแรกที่เปิดใช้งาน)")
    parser.add_argument("--export", type=str, default="license.key", help="เส้นทางไฟล์ที่จะส่งออก license.key")
    parser.add_argument("--list", action="store_true", help="แสดงรายการคีย์ทั้งหมด")
    parser.add_argument("--my-hwid", action="store_true", help="แสดง Hardware ID ของเครื่องนี้")
    
    args = parser.parse_args()
    
    if args.my_hwid:
        print("\n=== ข้อมูลเครื่องปัจจุบัน ===")
        print("Hardware ID (HWID):", license_guard.get_hardware_fingerprint())
        sys.exit(0)
        
    if args.create:
        rec = create_license(
            owner=args.owner,
            org=args.org,
            lic_type=args.type,
            max_devices=args.devices,
            bound_hwid=args.hwid,
            export_path=args.export
        )
        print("\n=== สร้างคีย์สำเร็จเรียบร้อย! ===")
        print(f"License Key : {rec['key']}")
        print(f"Owner       : {rec['owner']}")
        print(f"Org         : {rec.get('org', '-')}")
        print(f"Type        : {rec['type']}")
        print(f"Max Devices : {rec['max_devices']} เครื่อง")
        if rec['expires_at']:
            print(f"Expires     : {datetime.fromtimestamp(rec['expires_at']).strftime('%d/%m/%Y %H:%M')}")
        else:
            print("Expires     : ถาวร (Lifetime / ไม่มีวันหมดอายุ)")
        print(f"File Saved  : {args.export}")
        sys.exit(0)
        
    if args.list:
        lics = list_all_licenses()
        print(f"\n=== รายการลิขสิทธิ์ทั้งหมด ({len(lics)} รายการ) ===")
        print(f"{'Key':<22} {'Owner':<20} {'Type':<10} {'Devices':<10} {'Status':<10}")
        print("-" * 75)
        for l in lics:
            dev_str = f"{len(l.get('devices', []))}/{l.get('max_devices', 1)}"
            print(f"{l.get('key', '-'):<22} {l.get('owner', '-'):<20} {l.get('type', '-'):<10} {dev_str:<10} {l.get('status', '-'):<10}")
        sys.exit(0)
        
    parser.print_help()
