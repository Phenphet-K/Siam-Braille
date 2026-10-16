import win32com.client # type: ignore
import os

try:
    shell = win32com.client.Dispatch("WScript.Shell")
    desktop = shell.SpecialFolders("Desktop")
    # ลบ shortcut เดิมถ้ามี
    old_lnk = os.path.join(desktop, "Thai Braille Translator 3.0.lnk")
    if os.path.exists(old_lnk):
        try: os.remove(old_lnk)
        except Exception: pass
        
    # ตรวจหาโฟลเดอร์ติดตั้ง SiamBraille
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\SiamBraille"),
        r"G:\TBTW\dist\SiamBraille",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\TBTW3"),
        r"G:\TBTW\dist\TBTW3"
    ]
    app_dir = candidates[0]
    for d in candidates:
        if os.path.exists(d):
            app_dir = d
            break
            
    exe_name = "SiamBraille.exe" if os.path.exists(os.path.join(app_dir, "SiamBraille.exe")) else "TBTW3.exe"
    icon_name = "SiamBraille.ico" if os.path.exists(os.path.join(app_dir, "SiamBraille.ico")) else "TBTW3.ico"

    shortcut = shell.CreateShortCut(os.path.join(desktop, "SiamBraille 1.0.lnk"))
    shortcut.TargetPath = os.path.join(app_dir, exe_name)
    shortcut.WorkingDirectory = app_dir
    shortcut.IconLocation = f"{os.path.join(app_dir, icon_name)},0"
    shortcut.Description = "SiamBraille 1.0 Professional"
    shortcut.Save()
    print("Desktop shortcut updated to SiamBraille 1.0 successfully!")
except Exception as e:
    print("Fallback:", e)
