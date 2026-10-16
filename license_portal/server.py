# -*- coding: utf-8 -*-
"""
SiamBraille 1.0 - License Management Web Portal Server
เซิร์ฟเวอร์เว็บแอปสำหรับจัดการคีย์ ลิขสิทธิ์ และอุปกรณ์
พัฒนาด้วย FastAPI + Uvicorn
"""

import os
import sys
import json
import time
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

# นำเข้าโมดูลจัดการลิขสิทธิ์
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import license_guard
import license_admin

app = FastAPI(title="SiamBraille License Management Portal", version="1.0.0")

PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))

class CreateLicenseRequest(BaseModel):
    owner: str
    org: Optional[str] = ""
    lic_type: str = "lifetime"  # lifetime, yearly, monthly, trial
    max_devices: int = 1
    days: Optional[int] = 0
    bound_hwid: Optional[str] = ""

import secrets

class LoginRequest(BaseModel):
    email: str
    password: Optional[str] = ""

ACTIVE_SESSIONS = {}

class RevokeRequest(BaseModel):
    reason: Optional[str] = "Revoked by admin"

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(ROOT_DIR, "public")

@app.post("/api/auth/login")
def admin_login(req: LoginRequest):
    email = req.email.strip().lower()
    try:
        import firebase_admin
        from firebase_admin import auth, credentials
        cred_path = os.path.join(ROOT_DIR, "siam-braille-firebase-adminsdk-fbsvc-5131a4721e.json")
        if not firebase_admin._apps and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            
        user = auth.get_user_by_email(email)
        # ตรวจสอบสิทธิ์ Admin (k.phenphet@gmail.com)
        if email != "k.phenphet@gmail.com":
            raise HTTPException(status_code=403, detail="บัญชีนี้ไม่ได้รับสิทธิ์เข้าใช้งานระบบผู้ดูแล")
            
        token = secrets.token_hex(20)
        ACTIVE_SESSIONS[token] = {
            "email": user.email,
            "uid": user.uid,
            "login_time": time.time()
        }
        return {
            "status": "success",
            "message": "เข้าสู่ระบบสำเร็จ",
            "token": token,
            "email": user.email,
            "uid": user.uid
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"ไม่สามารถตรวจสอบบัญชีผู้ใช้ได้: {e}")

@app.get("/", response_class=HTMLResponse)
def get_landing_page():
    index_file = os.path.join(PUBLIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SiamBraille 1.0</h1>"

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
def get_admin_dashboard():
    admin_file = os.path.join(PUBLIC_DIR, "admin", "index.html")
    if not os.path.exists(admin_file):
        admin_file = os.path.join(PORTAL_DIR, "index.html")
    if os.path.exists(admin_file):
        with open(admin_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SiamBraille License Portal Dashboard</h1>"

@app.get("/api/download/setup")
def download_setup_installer():
    setup_file = os.path.join(ROOT_DIR, "dist", "SiamBraille_Setup_v1.0.exe")
    if not os.path.exists(setup_file):
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์ตัวติดตั้งโปรแกรม")
    return FileResponse(
        path=setup_file,
        filename="SiamBraille_Setup_v1.0.exe",
        media_type="application/vnd.microsoft.portable-executable"
    )

@app.get("/api/stats")
def get_stats():
    lics = license_admin.list_all_licenses()
    total_keys = len(lics)
    total_devices = sum(len(l.get("devices", [])) for l in lics)
    total_seats = sum(l.get("max_devices", 1) for l in lics)
    active_keys = sum(1 for l in lics if l.get("status") == "active")
    revoked_keys = sum(1 for l in lics if l.get("status") == "revoked")
    
    return {
        "total_keys": total_keys,
        "total_devices": total_devices,
        "total_seats": total_seats,
        "active_keys": active_keys,
        "revoked_keys": revoked_keys
    }

@app.get("/api/licenses")
def get_licenses():
    lics = license_admin.list_all_licenses()
    # เรียงลำดับจากล่าสุดไปเก่าสุด
    lics.sort(key=lambda x: x.get("issued_at", 0), reverse=True)
    return lics

@app.post("/api/licenses")
def create_new_license(req: CreateLicenseRequest):
    if not req.owner.strip():
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อผู้ใช้งาน/เจ้าของลิขสิทธิ์")
        
    rec = license_admin.create_license(
        owner=req.owner,
        org=req.org or "",
        lic_type=req.lic_type,
        max_devices=req.max_devices,
        days=req.days or 0,
        bound_hwid=req.bound_hwid or ""
    )
    return {
        "status": "success",
        "message": f"ออกคีย์สำเร็จสำหรับ {rec['owner']}",
        "data": rec
    }

@app.get("/api/licenses/{key}/download")
def download_license_key(key: str):
    lics = license_admin.load_local_db()
    if key not in lics:
        # ลองค้นหาจาก stream
        all_lics = license_admin.list_all_licenses()
        matched = [l for l in all_lics if l.get("key") == key]
        if not matched:
            raise HTTPException(status_code=404, detail="ไม่พบคีย์นี้ในระบบ")
        rec = matched[0]
    else:
        rec = lics[key]
        
    token = rec.get("token", "")
    if not token:
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูล Token ลิขสิทธิ์")
        
    return Response(
        content=token,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=license.key"}
    )

@app.post("/api/licenses/{key}/revoke")
def revoke_key(key: str, req: RevokeRequest):
    success = license_admin.revoke_license(key, req.reason or "Revoked via Web Portal")
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบรหัสคีย์ที่ระบุ")
    return {"status": "success", "message": f"ระงับคีย์ {key} เรียบร้อยแล้ว"}

@app.post("/api/licenses/{key}/reactivate")
def reactivate_key(key: str):
    success = license_admin.reactivate_license(key)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบรหัสคีย์ที่ระบุ")
    return {"status": "success", "message": f"เปิดใช้งานคีย์ {key} อีกครั้งเรียบร้อยแล้ว"}

@app.post("/api/licenses/{key}/reset_devices")
def reset_devices_endpoint(key: str):
    success = license_admin.reset_devices(key)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบรหัสคีย์ที่ระบุ")
    return {"status": "success", "message": f"รีเซ็ตอุปกรณ์สำหรับคีย์ {key} สำเร็จ พร้อมสำหรับการผูกเครื่องใหม่ (ย้ายเครื่อง)"}

@app.delete("/api/licenses/{key}")
@app.post("/api/licenses/{key}/delete")
def delete_license_endpoint(key: str):
    success = license_admin.delete_license(key)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบรหัสคีย์ที่ระบุ")
    return {"status": "success", "message": f"ลบคีย์ {key} ออกจากระบบเรียบร้อยแล้ว"}


@app.post("/api/verify")
def verify_client_key(payload: dict):
    """API สำหรับโปรแกรม SiamBraille บนคอมพิวเตอร์ลูกข่ายเรียกมาตรวจสอบออนไลน์"""
    key = payload.get("key", "").strip().upper()
    hwid = payload.get("hwid", "").strip()
    
    if not key:
        return {"valid": False, "message": "ไม่ได้ระบุรหัสคีย์"}
        
    all_lics = license_admin.list_all_licenses()
    matched = [l for l in all_lics if l.get("key") == key]
    if not matched:
        return {"valid": False, "message": "ไม่พบรหัสคีย์นี้ในระบบ"}
        
    rec = matched[0]
    if rec.get("status") == "revoked":
        return {"valid": False, "message": f"คีย์นี้ถูกระงับการใช้งาน: {rec.get('revoke_reason', '')}"}
        
    # ตรวจสอบวันหมดอายุ
    exp = rec.get("expires_at")
    if exp and exp > 0 and time.time() > exp:
        return {"valid": False, "message": "คีย์หมดอายุการใช้งานแล้ว"}
        
    # ตรวจสอบ HWID
    devices = rec.get("devices", [])
    if hwid:
        if hwid not in devices:
            if len(devices) >= rec.get("max_devices", 1):
                return {"valid": False, "message": f"คีย์นี้ใช้งานเต็มโควต้า {rec.get('max_devices', 1)} เครื่องแล้ว"}
            # ผูกเครื่องใหม่
            devices.append(hwid)
            rec["devices"] = devices
            # อัปเดต DB
            ldb = license_admin.load_local_db()
            if key in ldb:
                ldb[key]["devices"] = devices
                license_admin.save_local_db(ldb)
                
    return {
        "valid": True,
        "message": "ลิขสิทธิ์ถูกต้อง",
        "owner": rec.get("owner"),
        "type": rec.get("type"),
        "expires_at": rec.get("expires_at"),
        "devices_count": len(devices),
        "max_devices": rec.get("max_devices", 1)
    }

# ==========================================
# ระบบถอดรหัส Mini QR บนสลิปโอนเงิน (BOT Standard)
# ==========================================
THAI_BANKS = {
    '002': 'ธนาคารกรุงเทพ (BBL)',
    '004': 'ธนาคารกสิกรไทย (KBANK)',
    '006': 'ธนาคารกรุงไทย (KTB)',
    '011': 'ธนาคารทหารไทยธนชาต (TTB)',
    '014': 'ธนาคารไทยพาณิชย์ (SCB)',
    '025': 'ธนาคารกรุงศรีอยุธยา (BAY)',
    '030': 'ธนาคารออมสิน (GSB)',
    '034': 'ธ.ก.ส. (BAAC)',
    '065': 'ธนาคารธนชาต',
    '067': 'ธนาคารทิสโก้ (TISCO)',
    '069': 'ธนาคารเกียรตินาคินภัทร (KKP)',
    '073': 'ธนาคารแลนด์ แอนด์ เฮ้าส์ (LH Bank)',
    '140': 'TrueMoney Wallet'
}

def parse_tlv(payload: str) -> dict[str, str]:
    data: dict[str, str] = {}
    i = 0
    while i < len(payload):
        tag = payload[i:i+2]
        if not tag or len(tag) < 2:
            break
        length_str = payload[i+2:i+4]
        if not length_str.isdigit():
            break
        length = int(length_str)
        val = payload[i+4:i+4+length]
        data[tag] = val
        i += 4 + length
    return data

def parse_slip_qr(payload: str) -> dict:
    root = parse_tlv(payload)
    tag00 = root.get('00', '')
    sub = parse_tlv(tag00)
    api_version = sub.get('00')
    bank_code = sub.get('01')
    trans_ref = sub.get('02')
    bank_name = THAI_BANKS.get(bank_code, f'ธนาคารรหัส {bank_code}') if bank_code else 'ไม่ระบุธนาคาร'
    return {
        'api_version': api_version,
        'bank_code': bank_code,
        'bank_name': bank_name,
        'trans_ref': trans_ref,
        'is_valid': bool(api_version == '000001' and bank_code and trans_ref)
    }

class VerifySlipCheckoutRequest(BaseModel):
    slip_qr_payload: str
    cust_name: str
    cust_email: str
    cust_phone: str
    cust_org: Optional[str] = ""
    plan_id: str = "personal"
    devices: int = 1

@app.post("/api/checkout/verify-slip")
def verify_slip_checkout(req: VerifySlipCheckoutRequest):
    """
    ตรวจสอบความถูกต้องของสลิปโอนเงินผ่าน Mini QR (BOT Standard)
    โดยไม่ต้องพึ่งพา AI Gemini:
    1. ถอดรหัส Tag 00 / Sub-tags 00, 01, 02
    2. สกัดรหัสธนาคารต้นทาง (sendingBank) และรหัสธุรกรรม (transRef)
    3. ตรวจสอบการใช้งานซ้ำ (Anti-Fraud Duplicate Detection)
    4. ออก License Key อัตโนมัติทันที
    """
    raw_payload = req.slip_qr_payload.strip()
    if not raw_payload:
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูล Mini QR บนสลิป")

    info = parse_slip_qr(raw_payload)
    if not info["is_valid"]:
        raise HTTPException(status_code=400, detail="QR Code บนภาพไม่ใช่ Mini QR สำหรับตรวจสลิปของธนาคารไทย (มาตรฐาน ธปท.)")

    trans_ref = info["trans_ref"]
    bank_name = info["bank_name"]
    bank_code = info["bank_code"]

    # ตรวจสอบการใช้สลิปซ้ำในระบบท้องถิ่น (orders.json)
    orders_path = os.path.join(PORTAL_DIR, "orders.json")
    orders = []
    if os.path.exists(orders_path):
        try:
            with open(orders_path, "r", encoding="utf-8") as f:
                orders = json.load(f)
        except Exception:
            orders = []

    for ord_item in orders:
        if ord_item.get("trans_ref") == trans_ref:
            raise HTTPException(
                status_code=400,
                detail=f"สลิปนี้ (รหัสอ้างอิง {trans_ref}) ถูกใช้งานสั่งซื้อไปแล้วเมื่อ {ord_item.get('created_at')} ป้องกันการใช้สลิปซ้ำ!"
            )

    # ออก License Key
    max_dev = req.devices
    lic_type = "lifetime"
    owner_label = f"{req.cust_name.strip()} ({req.cust_email.strip()})"
    new_key = license_admin.create_license(
        owner=owner_label,
        org=req.cust_org or "สั่งซื้อผ่านเว็บไซต์ (ตรวจ Mini QR สลิป)",
        lic_type=lic_type,
        max_devices=max_dev
    )

    # บันทึกประวัติคำสั่งซื้อ
    order_record = {
        "order_id": f"ORD-{int(time.time())}-{trans_ref[-6:] if len(trans_ref) >= 6 else trans_ref}",
        "trans_ref": trans_ref,
        "bank_code": bank_code,
        "bank_name": bank_name,
        "customer_name": req.cust_name,
        "customer_email": req.cust_email,
        "customer_phone": req.cust_phone,
        "customer_org": req.cust_org,
        "plan_id": req.plan_id,
        "license_key": new_key,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    orders.append(order_record)
    with open(orders_path, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    return {
        "status": "success",
        "message": "ตรวจสอบสลิปผ่าน Mini QR สำเร็จ ออกสิทธิ์เรียบร้อยแล้ว",
        "key": new_key,
        "order": order_record
    }

# ==========================================
# ระบบชำระเงินออนไลน์ผ่าน Stripe (Credit/Debit/PromptPay)
# ==========================================
import stripe_service

class StripeCheckoutRequest(BaseModel):
    plan_id: str
    cust_name: str
    cust_email: str
    cust_phone: Optional[str] = ""
    cust_org: Optional[str] = ""
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

@app.post("/api/checkout/stripe/create-session")
def create_stripe_session_endpoint(req: StripeCheckoutRequest):
    """สร้างเซสชัน Stripe Checkout สำหรับการชำระเงิน"""
    try:
        res = stripe_service.create_stripe_checkout(
            plan_id=req.plan_id,
            cust_name=req.cust_name,
            cust_email=req.cust_email,
            cust_phone=req.cust_phone or "",
            cust_org=req.cust_org or "",
            success_url=req.success_url,
            cancel_url=req.cancel_url
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/checkout/stripe/verify-session")
def verify_stripe_session_endpoint(session_id: str):
    """ตรวจสอบสถานะจาก Stripe และออก License Key อัตโนมัติ"""
    if not session_id:
        raise HTTPException(status_code=400, detail="ไม่ได้ระบุ session_id")
    try:
        res = stripe_service.verify_and_fulfill_checkout(session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# ระบบจัดการแพ็กเกจราคา (Dynamic Pricing Management)
# ==========================================
PACKAGES_PATH = os.path.join(PORTAL_DIR, "packages.json")

def load_packages_db() -> list:
    if os.path.exists(PACKAGES_PATH):
        try:
            with open(PACKAGES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_packages_db(pkgs: list):
    with open(PACKAGES_PATH, "w", encoding="utf-8") as f:
        json.dump(pkgs, f, ensure_ascii=False, indent=2)

@app.get("/api/packages")
def get_packages():
    """ดึงข้อมูลรายการแพ็กเกจราคาสำหรับแสดงบนหน้าเว็บ"""
    return {"status": "success", "data": load_packages_db()}

class PackageItem(BaseModel):
    id: str
    name: str
    desc: Optional[str] = ""
    price: float
    period: Optional[str] = "ตลอดชีพ"
    type: str = "lifetime"
    max_devices: int = 1
    popular: Optional[bool] = False
    badge: Optional[str] = ""
    features: List[str] = []

@app.post("/api/packages")
def save_package(item: PackageItem):
    """สร้างหรืออัปเดตราคา/จำนวนเครื่องของแพ็กเกจ (Admin Only)"""
    pkgs = load_packages_db()
    found = False
    new_data = item.dict()
    for idx, p in enumerate(pkgs):
        if p.get("id") == item.id:
            pkgs[idx] = new_data
            found = True
            break
    if not found:
        pkgs.append(new_data)
    save_packages_db(pkgs)
    return {"status": "success", "message": "บันทึกแพ็กเกจเรียบร้อย", "data": new_data}

@app.delete("/api/packages/{package_id}")
def delete_package(package_id: str):
    """ลบแพ็กเกจ"""
    pkgs = load_packages_db()
    pkgs = [p for p in pkgs if p.get("id") != package_id]
    save_packages_db(pkgs)
    return {"status": "success", "message": "ลบแพ็กเกจเรียบร้อย"}

@app.get("/api/orders")
def get_orders():
    """ดึงประวัติการสั่งซื้อและการตรวจสลิป Mini QR ทั้งหมด"""
    orders_path = os.path.join(PORTAL_DIR, "orders.json")
    if os.path.exists(orders_path):
        try:
            with open(orders_path, "r", encoding="utf-8") as f:
                return {"status": "success", "data": json.load(f)}
        except Exception:
            pass
    return {"status": "success", "data": []}

def start_server(host="0.0.0.0", port=8080):
    print(f"\n=======================================================")
    print(f" SiamBraille 1.0 License Management Portal")
    print(f" Dashboard URL: http://localhost:{port}")
    print(f"=======================================================\n")
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    start_server()
