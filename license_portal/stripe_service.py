import os
import json
import time
from typing import Optional, Dict, Any
import stripe
import license_admin

# โหลด Stripe Secret Key จากไฟล์ stripe api key.txt หรือ Environment
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
if not STRIPE_API_KEY:
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "stripe api key.txt"),
        os.path.join(os.path.dirname(__file__), "stripe api key.txt"),
        "stripe api key.txt"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    STRIPE_API_KEY = f.read().strip()
                if STRIPE_API_KEY:
                    break
            except Exception:
                pass

if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY

PACKAGES_FILE = os.path.join(os.path.dirname(__file__), "packages.json")
ORDERS_FILE = os.path.join(os.path.dirname(__file__), "orders.json")

def get_package(plan_id: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(PACKAGES_FILE):
        return None
    try:
        with open(PACKAGES_FILE, "r", encoding="utf-8") as f:
            pkgs = json.load(f)
            for p in pkgs:
                if p.get("id") == plan_id:
                    return p
    except Exception:
        pass
    return None

def create_stripe_checkout(
    plan_id: str,
    cust_name: str,
    cust_email: str,
    cust_phone: str = "",
    cust_org: str = "",
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None
) -> Dict[str, Any]:
    """สร้าง Stripe Checkout Session สำหรับชำระเงินค่าลิขสิทธิ์ SiamBraille"""
    if not stripe.api_key:
        raise ValueError("ไม่ได้กำหนด Stripe API Key ในระบบ")
        
    pkg = get_package(plan_id)
    if not pkg:
        raise ValueError(f"ไม่พบข้อมูลแพ็กเกจ {plan_id}")

    amount_satang = int(round(float(pkg.get("price", 1290)) * 100))
    pkg_name = pkg.get("name", "SiamBraille License")
    max_devices = int(pkg.get("max_devices", 1))

    if not success_url:
        success_url = "https://siam-braille.web.app/checkout/success.html?session_id={CHECKOUT_SESSION_ID}"
    if not cancel_url:
        cancel_url = "https://siam-braille.web.app/#pricing"

    session = stripe.checkout.Session.create(
        line_items=[{
            "price_data": {
                "currency": "thb",
                "product_data": {
                    "name": f"SiamBraille 1.0 - {pkg_name}",
                    "description": pkg.get("desc", "โปรแกรมแปลเอกสารเป็นอักษรเบรลล์ภาษาไทย SiamBraille"),
                    "images": ["https://siam-braille.web.app/assets/icons/glyph_translate.png"]
                },
                "unit_amount": amount_satang,
            },
            "quantity": 1,
        }],
        mode="payment",
        invoice_creation={"enabled": True},  # ออกใบเสร็จรับเงินทางการอัตโนมัติ
        customer_email=cust_email if cust_email and "@" in cust_email else None,
        metadata={
            "plan_id": plan_id,
            "cust_name": cust_name,
            "cust_email": cust_email,
            "cust_phone": cust_phone,
            "cust_org": cust_org,
            "max_devices": str(max_devices)
        },
        success_url=success_url,
        cancel_url=cancel_url
    )

    return {
        "status": "success",
        "session_id": session.id,
        "checkout_url": session.url
    }

def verify_and_fulfill_checkout(session_id: str) -> Dict[str, Any]:
    """
    ตรวจสอบการโอนเงินจริงจาก Stripe และดึงลิงก์ใบเสร็จรับเงิน (Official Receipt/Invoice)
    พร้อมออก License Key อัตโนมัติทันที
    """
    if not stripe.api_key:
        raise ValueError("ไม่ได้กำหนด Stripe API Key ในระบบ")
        
    session = stripe.checkout.Session.retrieve(session_id, expand=["invoice", "payment_intent"])
    
    # 1. เช็คเงินโอนจริง: ตรวจสอบสถานะว่าชำระเงินจริงแล้วเท่านั้น
    if session.payment_status != "paid":
        return {
            "status": "pending",
            "paid": False,
            "message": "ระบบยังไม่พบยอดเงินโอนจริง หรืออยู่ระหว่างประมวลผล"
        }

    # 2. ดึงข้อมูลใบเสร็จรับเงิน (Stripe Receipt & Invoice)
    receipt_url = None
    invoice_pdf = None
    if session.invoice:
        try:
            if isinstance(session.invoice, str):
                inv = stripe.Invoice.retrieve(session.invoice)
            else:
                inv = session.invoice
            receipt_url = getattr(inv, "hosted_invoice_url", None)
            invoice_pdf = getattr(inv, "invoice_pdf", None)
        except Exception:
            pass

    if not receipt_url and session.payment_intent:
        try:
            if hasattr(session.payment_intent, "latest_charge") and session.payment_intent.latest_charge:
                ch = stripe.Charge.retrieve(session.payment_intent.latest_charge)
                receipt_url = ch.receipt_url
            elif hasattr(session.payment_intent, "charges") and session.payment_intent.charges.data:
                receipt_url = session.payment_intent.charges.data[0].receipt_url
        except Exception:
            pass

    # ตรวจสอบว่าเคยออกสิทธิ์สำหรับ session_id นี้หรือยัง ป้องกัน duplicate
    orders = []
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                orders = json.load(f)
        except Exception:
            orders = []

    for ord_item in orders:
        if ord_item.get("stripe_session_id") == session_id:
            return {
                "status": "success",
                "paid": True,
                "already_fulfilled": True,
                "message": "ตรวจพบยอดเงินโอนจริงเรียบร้อยแล้ว (ออกใบเสร็จและคีย์เดิม)",
                "key": ord_item.get("license_key"),
                "receipt_url": ord_item.get("receipt_url") or receipt_url,
                "invoice_pdf": ord_item.get("invoice_pdf") or invoice_pdf,
                "order": ord_item
            }

    # ออก License Key ใหม่
    metadata = session.metadata or {}
    plan_id = metadata.get("plan_id", "personal")
    cust_name = metadata.get("cust_name", "Customer")
    cust_email = metadata.get("cust_email", "") or (session.customer_details.email if session.customer_details else "")
    cust_phone = metadata.get("cust_phone", "")
    cust_org = metadata.get("cust_org", "สั่งซื้อผ่าน Stripe")
    try:
        max_devices = int(metadata.get("max_devices", 1))
    except (ValueError, TypeError):
        max_devices = 1

    owner_label = f"{cust_name.strip()} ({cust_email.strip()})" if cust_email else cust_name.strip()
    
    new_key = license_admin.create_license(
        owner=owner_label,
        org=cust_org,
        lic_type="lifetime",
        max_devices=max_devices
    )

    order_record = {
        "order_id": f"ORD-STRIPE-{int(time.time())}-{session_id[-6:]}",
        "stripe_session_id": session_id,
        "payment_method": "stripe",
        "payment_status": "paid",
        "verified_real_money": True,
        "amount_total": (session.amount_total or 0) / 100.0,
        "currency": session.currency.upper() if session.currency else "THB",
        "customer_name": cust_name,
        "customer_email": cust_email,
        "customer_phone": cust_phone,
        "customer_org": cust_org,
        "plan_id": plan_id,
        "license_key": new_key,
        "max_devices": max_devices,
        "receipt_url": receipt_url,
        "invoice_pdf": invoice_pdf,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    orders.append(order_record)
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    return {
        "status": "success",
        "paid": True,
        "already_fulfilled": False,
        "message": "ตรวจสอบยอดเงินโอนจริงผ่าน Stripe สำเร็จ และออกใบเสร็จรับเงินเรียบร้อยแล้ว",
        "key": new_key,
        "receipt_url": receipt_url,
        "invoice_pdf": invoice_pdf,
        "order": order_record
    }
