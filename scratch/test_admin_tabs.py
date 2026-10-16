# -*- coding: utf-8 -*-
import sys
import time
from playwright.sync_api import sync_playwright

def test_admin_packages():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        
        # 1. เข้าหน้า Admin
        print("Navigating to http://127.0.0.1:8080/admin ...")
        page.goto("http://127.0.0.1:8080/admin", wait_until="networkidle")
        
        # 2. ทำการ Login ผ่าน mock session token ใน sessionStorage
        page.evaluate("""() => {
            sessionStorage.setItem('sb_admin_token', 'local_test_token');
            sessionStorage.setItem('sb_admin_email', 'k.phenphet@gmail.com');
            showDashboard('k.phenphet@gmail.com');
        }""")
        page.wait_for_timeout(1000)
        
        # 3. สลับไปแท็บ Packages
        print("Switching to Packages tab...")
        page.click("#btnTabPackages")
        page.wait_for_timeout(1000)
        page.screenshot(path="C:/Users/Administrator/.gemini/antigravity-ide/brain/94ff4fc3-f7cf-46da-82a1-3b103efca9d2/admin_packages_tab.png")
        print("Captured admin_packages_tab.png")
        
        # 4. สลับไปแท็บ Orders
        print("Switching to Orders tab...")
        page.click("#btnTabOrders")
        page.wait_for_timeout(1000)
        page.screenshot(path="C:/Users/Administrator/.gemini/antigravity-ide/brain/94ff4fc3-f7cf-46da-82a1-3b103efca9d2/admin_orders_tab.png")
        print("Captured admin_orders_tab.png")
        
        # 5. ทดสอบเปิด Modal เพิ่มแพ็กเกจ
        print("Testing open Package modal...")
        page.click("#btnTabPackages")
        page.wait_for_timeout(500)
        page.click("button:has-text('+ เพิ่มแพ็กเกจใหม่')")
        page.wait_for_timeout(500)
        page.screenshot(path="C:/Users/Administrator/.gemini/antigravity-ide/brain/94ff4fc3-f7cf-46da-82a1-3b103efca9d2/admin_add_package_modal.png")
        print("Captured admin_add_package_modal.png")
        
        browser.close()
        print("All tests passed successfully!")

if __name__ == "__main__":
    test_admin_packages()
