"""
สคริปต์สำหรับกระจายไฟล์สำคัญ (ตารางคำย่อ, พจนานุกรม, ฟอนต์, ไฟล์ระบบ Delphi ดั้งเดิม)
ไปยังโฟลเดอร์ dist/TBTW3 โดยตรง เพื่อให้มีโครงสร้างเหมือนโฟลเดอร์ต้นฉบับใน C:\Program Files\TBTW
"""
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIRS = [
    os.path.join(BASE_DIR, "dist", "SiamBraille"),
    os.path.join(BASE_DIR, "dist", "TBTW3")
]

FILES_TO_COPY = [
    # ตารางอักษรเบรลล์ และพจนานุกรม
    "CH46.tab", "CH78.tab", "d2branch.tri", "d2tail.tri", "SiamBraille.dic", "Tbt.dic",
    "G2Def.def", "Mcheck.def", "setkey.def", "SiamBraille.def", "tbt.def",
    # ฟอนต์เบรลล์ SimBraille และตัวติดตั้งฟอนต์
    "SIMBRL.TTF", "fontinstall.bat", "font.reg",
    # ไอคอน SiamBraille
    "SiamBraille.ico",
    # DLLs 64-bit สำหรับ LibLouis, NVDA และประมวลผล
    "liblouis64.dll", "nvdaControllerClient64.dll", "Nbreak.dll",
    # ตัวรันโปรแกรมเสริม
    "run_SiamBraille.bat"
]

DIRS_TO_COPY = ["data", "Tables", "logo", "assets"]

def distribute():
    for target_dir in DIST_DIRS:
        os.makedirs(target_dir, exist_ok=True)
        print(f"\nกำลังกระจายไฟล์ไปยัง: {target_dir}")
        
        # คัดลอกไฟล์
        copied_files = 0
        for fname in FILES_TO_COPY:
            src = os.path.join(BASE_DIR, fname)
            if os.path.exists(src):
                dst = os.path.join(target_dir, fname)
                shutil.copy2(src, dst)
                copied_files += 1
                
        # คัดลอกโฟลเดอร์
        copied_dirs = 0
        for dname in DIRS_TO_COPY:
            src = os.path.join(BASE_DIR, dname)
            if os.path.exists(src):
                dst = os.path.join(target_dir, dname)
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                copied_dirs += 1
                
        print(f"  -> สำเร็จ! คัดลอกไฟล์ {copied_files} ไฟล์ และโฟลเดอร์ {copied_dirs} โฟลเดอร์")

if __name__ == "__main__":
    distribute()
