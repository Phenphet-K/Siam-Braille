import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from tbtw_app import get_main_app_icon, AboutBoxDialog, TBTWMainWindow

def test_logo_and_about():
    app = QApplication.instance() or QApplication(sys.argv)
    
    # 1. Test get_main_app_icon
    icon = get_main_app_icon()
    assert not icon.isNull(), "Icon should not be null!"
    print("get_main_app_icon() SUCCESS! Icon sizes loaded.")
    
    # 2. Test AboutBoxDialog
    dlg = AboutBoxDialog()
    assert dlg.windowTitle() == "About TBT for windows"
    assert "TBTW for windows" in dlg.memo.toPlainText()
    assert "Version : 3.00" in dlg.memo.toPlainText()
    assert "Wiraman Niyomphon" in dlg.memo.toPlainText()
    print("AboutBoxDialog SUCCESS! Memo text and layout verified.")
    
    # 3. Test TBTWMainWindow icon
    win = TBTWMainWindow()
    assert not win.windowIcon().isNull(), "Main window icon should not be null!"
    print("Main window icon verified successfully!")
    
    # Close immediately
    QTimer.singleShot(100, dlg.accept)
    dlg.exec()
    print("Dialog exec & close SUCCESS!")
    print("All Logo & About Box tests PASSED!")

if __name__ == "__main__":
    test_logo_and_about()
