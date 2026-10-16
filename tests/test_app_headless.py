import sys
from PyQt6.QtWidgets import QApplication
from tbtw_app import TBTWMainWindow

def test():
    import os
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from tbtw_app import ReportTranslateDialog
    ReportTranslateDialog.exec = lambda self: 1
    app = QApplication.instance() or QApplication(sys.argv)
    win = TBTWMainWindow()
    print("Window created successfully!")
    print("Title:", win.windowTitle())
    menubar = win.menuBar()
    assert menubar is not None, "MenuBar should not be None"
    print("Menu count:", len(menubar.actions()))
    
    test_text = "สวัสดีครับ ทดสอบการแปลภาษาไทยเป็นอักษรเบรลล์ บ้าน เวลา"
    win.txt_normal.setPlainText(test_text)
    win.action_translate()
    
    braille_out = win.txt_braille.toPlainText()
    print("Input chars:", len(test_text))
    print("Braille output length:", len(braille_out))
    assert len(braille_out) > 0, "Braille output should not be empty!"
    
    # Test Grade 2
    win.set_thai_grade(2)
    win.action_translate()
    braille_g2 = win.txt_braille.toPlainText()
    print("Grade 2 output length:", len(braille_g2))
    assert len(braille_g2) > 0, "Grade 2 output should not be empty!"
    
    print("All smoke tests PASSED successfully!")

if __name__ == "__main__":
    test()
