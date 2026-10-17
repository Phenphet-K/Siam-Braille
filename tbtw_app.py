"""
SiamBraille 1.0 - Professional Thai Braille Translation Software
โปรแกรมแปลเอกสารเป็นอักษรเบรลล์ภาษาไทยและสากล
พัฒนาด้วย Python 3 + PyQt6 รองรับ Windows 10/11 ทั้ง 32-bit และ 64-bit

ออกแบบเพื่อรองรับโปรแกรมอ่านหน้าจอ (Screen Readers) อย่างสมบูรณ์ 100%:
- NVDA (NonVisual Desktop Access)
- JAWS for Windows
- PPA Tatip (ตาทิพย์)
- Windows Narrator
ผ่าน Windows UI Automation (UIA) และ Microsoft Active Accessibility (MSAA)
พร้อมคีย์ลัด (Shortcuts), Mnemonic (Alt keys), ป้ายกำกับเสียง (Accessible Names & Descriptions),
การประกาศสถานะอัตโนมัติ (Live Status Announcements) และคีย์สลับหน้าต่าง F6
"""

import sys
import os
import ctypes
import base64
from typing import Optional, Tuple, List, Any, TYPE_CHECKING
if TYPE_CHECKING:
    from lan_companion import LANCompanionServer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPlainTextEdit, QLabel, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QDialog, QFormLayout, QSpinBox,
    QPushButton, QFontDialog, QFrame, QStyleFactory, QToolButton,
    QCheckBox, QSizePolicy, QGroupBox, QRadioButton, QComboBox, QLineEdit,
    QMenu
)
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QKeySequence, QPainter, QColor, QPen,
    QActionGroup, QFontDatabase, QPixmap, QTextDocument,
    QPageSize, QPageLayout
)
from PyQt6.QtCore import Qt, QSize, QEvent, QRectF, QMarginsF, QTimer

try:
    from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
except ImportError:
    QPrinter, QPrintDialog = None, None

try:
    import win32print
except ImportError:
    win32print = None

try:
    import pythainlp
except ImportError:
    pythainlp = None

import webbrowser
import json
import io
import urllib.request
import license_guard

try:
    import qrcode
except ImportError:
    qrcode = None

from tbtw_engine import ThaiBrailleTranslator
try:
    from embedded_icons import ICONS_B64
except ImportError:
    ICONS_B64 = {}

def get_resource_path(rel_path: str) -> str:
    """ค้นหาไฟล์ resource ในโฟลเดอร์รันไทม์ทั้งหมด ทั้งโหมดสคริปต์, โหมด exe ใน dist และ _internal แบบไม่ขึ้นกับ drive letter หรือ architecture"""
    base_dirs = []
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        base_dirs.extend([exe_dir, os.path.join(exe_dir, "_internal")])
        meipass = getattr(sys, '_MEIPASS', '')
        if meipass:
            base_dirs.append(meipass)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dirs.extend([
        script_dir,
        os.path.join(script_dir, "dist", "SiamBraille"),
        os.path.join(script_dir, "dist", "SiamBraille", "_internal")
    ])
    
    candidate_dirs = []
    for b in base_dirs:
        if b and os.path.exists(b):
            candidate_dirs.append(b)
            candidate_dirs.append(os.path.join(b, "assets"))
            candidate_dirs.append(os.path.join(b, "assets", "rules"))
            candidate_dirs.append(os.path.join(b, "assets", "fonts"))
            candidate_dirs.append(os.path.join(b, "assets", "icons"))
            candidate_dirs.append(os.path.join(b, "logo"))
            candidate_dirs.append(os.path.join(b, "Tables"))
            candidate_dirs.append(os.path.join(b, "data"))
    
    for d in candidate_dirs:
        if d and os.path.exists(d):
            p = os.path.join(d, rel_path)
            if os.path.exists(p):
                return p
    return os.path.join(script_dir, rel_path)


# NVDA Screen Reader Controller Client Bridge (Local Project Only - Architecture Aware)
_nvda_dll = None
try:
    is_64bit = sys.maxsize > 2**32
    dll_candidates = ["nvdaControllerClient64.dll", "nvdaControllerClient.dll", "nvdaControllerClient32.dll"] if is_64bit else ["nvdaControllerClient32.dll", "nvdaControllerClient.dll", "nvdaControllerClient64.dll"]
    for dll_name in dll_candidates:
        _np = get_resource_path(dll_name)
        if os.path.exists(_np):
            try:
                _nvda_dll = ctypes.cdll.LoadLibrary(_np)
                _nvda_dll.nvdaController_testIfRunning.restype = ctypes.c_long
                _nvda_dll.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
                _nvda_dll.nvdaController_speakText.restype = ctypes.c_long
                if hasattr(_nvda_dll, "nvdaController_cancelSpeech"):
                    _nvda_dll.nvdaController_cancelSpeech.restype = ctypes.c_long
                if hasattr(_nvda_dll, "nvdaController_brailleMessage"):
                    _nvda_dll.nvdaController_brailleMessage.argtypes = [ctypes.c_wchar_p]
                    _nvda_dll.nvdaController_brailleMessage.restype = ctypes.c_long
                break
            except Exception:
                _nvda_dll = None
except Exception:
    _nvda_dll = None

def is_nvda_running() -> bool:
    """ตรวจสอบว่าโปรแกรมอ่านหน้าจอ NVDA กำลังทำงานอยู่หรือไม่"""
    if _nvda_dll:
        try:
            return _nvda_dll.nvdaController_testIfRunning() == 0
        except Exception:
            return False
    return False

def speak_nvda(text: str, interrupt: bool = False, to_braille: bool = True):
    """
    ส่งเสียงอ่านและข้อความอักษรเบรลล์ไปยัง NVDA Screen Reader ทันทีเมื่อ NVDA กำลังทำงาน
    - text: ข้อความที่จะอ่านออกเสียง
    - interrupt: หากเป็น True จะตัดเสียงที่กำลังพูดอยู่ก่อนหน้าทันที (cancelSpeech)
    - to_braille: ส่งข้อความไปยัง Refreshable Braille Display ด้วย (brailleMessage)
    """
    if not text or not _nvda_dll:
        return
    try:
        if _nvda_dll.nvdaController_testIfRunning() == 0:
            if interrupt and hasattr(_nvda_dll, "nvdaController_cancelSpeech"):
                _nvda_dll.nvdaController_cancelSpeech()
            _nvda_dll.nvdaController_speakText(text)
            if to_braille and hasattr(_nvda_dll, "nvdaController_brailleMessage"):
                _nvda_dll.nvdaController_brailleMessage(text)
    except Exception:
        pass



def get_app_icon(name: str) -> QIcon:
    """โหลดไอคอนที่สกัดมาจากต้นฉบับ Delphi ผ่าน REA"""
    path = get_resource_path(name)
    if os.path.exists(path):
        return QIcon(path)
    if name in ICONS_B64:
        pix = QPixmap()
        pix.loadFromData(base64.b64decode(ICONS_B64[name]))
        return QIcon(pix)
    return QIcon()

def get_main_app_icon() -> QIcon:
    """โหลดไอคอนหลักของโปรแกรม SiamBraille"""
    for icon_name in ["SiamBraille.ico", "icon64.ico", "icon128.ico", "siam-braille-logo.jpg", "TBTW3.ico", "TBTW2.ico"]:
        p = get_resource_path(icon_name)
        if os.path.exists(p):
            return QIcon(p)
    return get_app_icon("TBTW2.ico")


class BrailleEditorWithMargin(QPlainTextEdit):
    """
    กล่องข้อความอักษรเบรลล์ (RichEdit2) พร้อมเส้นแบ่งขอบเขตหน้ากระดาษแนวตั้ง
    ตรงตามตำแหน่งในต้นฉบับ Delphi (ที่ x=102px จากขอบซ้ายกล่องข้อความ)
    รองรับการเข้าถึงของ Screen Reader เต็มรูปแบบ
    """
    def __init__(self, parent: Optional[QWidget] = None, col_limit: int = 30):
        super().__init__(parent)
        self.col_limit = col_limit
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        # Accessibility Properties
        self.setAccessibleName("ข้อมูลแปล กล่องข้อความอักษรเบรลล์ Braille Font")
        self.setAccessibleDescription(
            "กล่องข้อความแสดงผลอักษรเบรลล์ที่แปลแล้ว รองรับฟอนต์ SimBraille กำหนดขอบเขต 30 เซลล์ต่อบรรทัด "
            "กด F6 เพื่อสลับกลับไปยังกล่องข้อมูลเดิมภาษาไทยปกติ"
        )
        self.setWhatsThis("กล่องแสดงผลอักษรเบรลล์ (Braille Font) สำหรับตรวจทานและส่งออกเครื่องพิมพ์เบรลล์")
        
    def set_col_limit(self, limit: int):
        self.col_limit = limit
        viewport = self.viewport()
        if viewport:
            viewport.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        viewport = self.viewport()
        if self.col_limit > 0 and viewport:
            painter = QPainter(viewport)
            h_bar = self.horizontalScrollBar()
            scroll_x = h_bar.value() if h_bar is not None else 0
            x = int(102 * (self.col_limit / 30.0)) - scroll_x + 2
            
            if 0 <= x <= viewport.width():
                painter.setPen(QPen(QColor(114, 114, 114), 1, Qt.PenStyle.SolidLine))
                painter.drawLine(x, 0, x, viewport.height())

class ReportTranslateDialog(QDialog):
    """
    หน้าต่างรายงานผลการแปล (Report Translate - TForm6 ใน Delphi)
    ตรงตามต้นฉบับ Version 1.80/2.00 ใน Image 1 100%
    """
    def __init__(self, parent: Optional[QWidget] = None, thai_file: str = "C:\\noname.$u$",
                 braille_file: str = "c:\\noname.tbt", line_len: int = 30, page_len: int = 25,
                 total_pages: int = 1, lines_in_last: int = 2, questionable: int = 0):
        super().__init__(parent)
        self.setWindowTitle("Report Translate")
        self.setAccessibleName("หน้าต่างรายงานผลการแปล Report Translate")
        self.setFixedSize(360, 310)
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
            }
            QLabel {
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
                color: #000000;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid;
                border-color: #ffffff #808080 #808080 #ffffff;
                padding: 3px 20px;
                min-width: 65px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                border-color: #808080 #ffffff #ffffff #808080;
                background-color: #d8d8d8;
            }
            QPushButton:focus {
                outline: 1px dotted #000000;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        
        lbl_v = QLabel("SiamBraille 1.0")
        lbl_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_v)
        
        lbl_sum = QLabel("<b>TRANSLATION SUMMERY</b>")
        lbl_sum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sum)
        
        layout.addSpacing(4)
        
        form_layout = QVBoxLayout()
        form_layout.setSpacing(6)
        
        items = [
            f"<b>Thai file name :</b> {thai_file}",
            f"<b>Braille file name :</b> {braille_file}",
            f"<b>Braille page size :</b> {line_len} columns by {page_len} lines",
            f"<b>Total Braille page :</b> {total_pages}",
            f"<b>Total lines in last page :</b> {lines_in_last}",
            f"<b>Total lquestionnable situations :</b> {questionable}"
        ]
        
        for it in items:
            lbl = QLabel(it)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            form_layout.addWidget(lbl)
            
        layout.addLayout(form_layout)
        layout.addSpacing(4)
        
        lbl_comp = QLabel("<b>TRANSLATION SUMMERY COMPLETE</b>")
        lbl_comp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_comp)
        
        layout.addSpacing(6)
        
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.setAccessibleName("ตกลง OK")
        btn_ok.setAccessibleDescription("กดปุ่มตกลงหรือกด Enter เพื่อปิดหน้าต่างรายงานการแปล")
        btn_ok.clicked.connect(self.accept)
        btn_box.addWidget(btn_ok)
        btn_box.addStretch()
        layout.addLayout(btn_box)


EMBOSSER_PROFILES = [
    ("กำหนดเอง (Custom)", None, None),
    ("มาตรฐาน TBTW ดั้งเดิม (30 เซลล์ x 25 บรรทัด)", 30, 25),
    ("Index Braille - กระดาษ A4 (33 เซลล์ x 29 บรรทัด)", 33, 29),
    ("Index Braille - กระดาษต่อเนื่อง 11.5x11 นิ้ว (40 เซลล์ x 25 บรรทัด)", 40, 25),
    ("Index Braille - กระดาษต่อเนื่อง 11.5x11 นิ้ว เต็มหน้า (47 เซลล์ x 27 บรรทัด)", 47, 27),
    ("Index Braille - กระดาษ Letter (36 เซลล์ x 27 บรรทัด)", 36, 27),
    ("Index Braille - กระดาษ A3 (47 เซลล์ x 42 บรรทัด)", 47, 42),
    ("Braillo 300/450 - กระดาษต่อเนื่อง 11.5x11 นิ้ว (42 เซลล์ x 27 บรรทัด)", 42, 27),
    ("Braillo 300/450 - กระดาษ A4 (33 เซลล์ x 29 บรรทัด)", 33, 29),
    ("Enabling Technologies Romeo/Juliet (40 เซลล์ x 25 บรรทัด)", 40, 25),
    ("ViewPlus Columbia/Premier - กระดาษ A4 (33 เซลล์ x 29 บรรทัด)", 33, 29),
    ("Nippon Telesoft Gemini - กระดาษ A4 (33 เซลล์ x 29 บรรทัด)", 33, 29),
    ("Braille Display จอเบรลล์แบบรีเฟรชได้ (40 เซลล์ x 25 บรรทัด)", 40, 25),
    ("Braille Display จอเบรลล์แบบรีเฟรชได้ (80 เซลล์ x 25 บรรทัด)", 80, 25),
]


class PageSettingDialog(QDialog):
    """หน้าต่างตั้งค่าหน้ากระดาษการแปล (Braille Page Setting - Form2 ใน Delphi) พร้อมโปรไฟล์เครื่องพิมพ์เบรลล์"""
    def __init__(self, parent: Optional[QWidget] = None, line_len: int = 30, page_len: int = 25):
        super().__init__(parent)
        self.setWindowTitle("Braille Page Setting (ตั้งค่าหน้ากระดาษเบรลล์)")
        self.setAccessibleName("หน้าต่างตั้งค่าหน้ากระดาษการแปลเบรลล์ Braille Page Setting")
        self.setFixedSize(450, 230)
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid;
                border-color: #ffffff #808080 #808080 #ffffff;
                padding: 4px 14px;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                border-color: #808080 #ffffff #ffffff #808080;
                background-color: #d8d8d8;
            }
            QSpinBox, QComboBox {
                background-color: #ffffff;
                border: 2px solid;
                border-color: #808080 #ffffff #ffffff #808080;
                padding: 2px;
                font-size: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)
        
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # 1. เลือกรุ่นเครื่องพิมพ์เบรลล์ / โปรไฟล์ขนาดกระดาษ
        self.cbo_preset = QComboBox()
        self.cbo_preset.setAccessibleName("เลือกโปรไฟล์เครื่องพิมพ์เบรลล์หรือขนาดกระดาษ")
        self.cbo_preset.setAccessibleDescription("เลือกโปรไฟล์เครื่องพิมพ์เพื่อปรับขนาดเซลล์ต่อบรรทัดและบรรทัดต่อหน้าอัตโนมัติ")
        matched_idx = 0
        for idx, (p_name, p_cpl, p_lpp) in enumerate(EMBOSSER_PROFILES):
            self.cbo_preset.addItem(p_name, (p_cpl, p_lpp))
            if p_cpl == line_len and p_lpp == page_len and matched_idx == 0:
                matched_idx = idx
                
        self.cbo_preset.setCurrentIndex(matched_idx)
        self.cbo_preset.currentIndexChanged.connect(self._on_preset_changed)
        lbl_preset = QLabel("โปรไฟล์ &Embosser :")
        lbl_preset.setBuddy(self.cbo_preset)
        form_layout.addRow(lbl_preset, self.cbo_preset)
        
        self.spin_line_len = QSpinBox()
        self.spin_line_len.setRange(10, 80)
        self.spin_line_len.setValue(line_len)
        self.spin_line_len.setAccessibleName("Line Length ความกว้างหน้ากระดาษ")
        self.spin_line_len.setAccessibleDescription("จำนวนเซลล์อักษรเบรลล์ต่อ 1 บรรทัด ค่าเริ่มต้นคือ 30 เซลล์")
        
        self.spin_page_len = QSpinBox()
        self.spin_page_len.setRange(5, 50)
        self.spin_page_len.setValue(page_len)
        self.spin_page_len.setAccessibleName("Page Length ความยาวหน้ากระดาษ")
        self.spin_page_len.setAccessibleDescription("จำนวนบรรทัดต่อ 1 หน้ากระดาษเบรลล์ ค่าเริ่มต้นคือ 25 บรรทัด")
        
        lbl_line = QLabel("&Line Length (เซลล์ต่อบรรทัด) :")
        lbl_line.setBuddy(self.spin_line_len)
        
        lbl_page = QLabel("&Page Length (บรรทัดต่อหน้า) :")
        lbl_page.setBuddy(self.spin_page_len)
        
        form_layout.addRow(lbl_line, self.spin_line_len)
        form_layout.addRow(lbl_page, self.spin_page_len)
        layout.addLayout(form_layout)
        
        layout.addSpacing(6)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_ok = QPushButton("ตกลง (&O)")
        btn_ok.setDefault(True)
        btn_ok.setAccessibleName("ปุ่มตกลง")
        btn_ok.setAccessibleDescription("บันทึกการตั้งค่าหน้ากระดาษและปิดหน้าต่าง")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        
        btn_cancel = QPushButton("ยกเลิก (&C)")
        btn_cancel.setAccessibleName("ปุ่มยกเลิก")
        btn_cancel.setAccessibleDescription("ยกเลิกและปิดหน้าต่างโดยไม่บันทึกการตั้งค่า")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)

    def _on_preset_changed(self, index: int):
        data = self.cbo_preset.currentData()
        if data and data[0] is not None and data[1] is not None:
            cpl, lpp = data
            self.spin_line_len.setValue(cpl)
            self.spin_page_len.setValue(lpp)
            p_name = self.cbo_preset.currentText()
            speak_nvda(f"เลือกโปรไฟล์ {p_name} กว้าง {cpl} เซลล์ {lpp} บรรทัด", interrupt=True)

    def get_settings(self) -> Tuple[int, int]:
        return self.spin_line_len.value(), self.spin_page_len.value()


class Grade2SettingDialog(QDialog):
    """หน้าต่างเลือกระดับการแปลอักษรเบรลล์ระดับ 2 (Form12 ใน Delphi)"""
    def __init__(self, parent: Optional[QWidget] = None, ch1_3: bool = True, ch4_6: bool = True, ch7_8: bool = True):
        super().__init__(parent)
        self.setWindowTitle("อักษรระดับ 2")
        self.setAccessibleName("หน้าต่างเลือกระดับคำย่ออักษรเบรลล์ระดับ 2")
        self.setFixedSize(300, 220)
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid;
                border-color: #ffffff #808080 #808080 #ffffff;
                padding: 4px 14px;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                border-color: #808080 #ffffff #ffffff #808080;
                background-color: #d8d8d8;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)
        
        lbl_title = QLabel("เลือกหมวดคำย่ออักษรระดับ 2 :")
        layout.addWidget(lbl_title)
        
        self.chk_1_3 = QCheckBox("บท &1 - 3 (คำย่อทั่วไป)")
        self.chk_1_3.setChecked(ch1_3)
        self.chk_1_3.setAccessibleName("บท 1 ถึง 3 คำย่อทั่วไป")
        self.chk_1_3.setAccessibleDescription("เปิดใช้คำย่อพื้นฐานบท 1 ถึง 3")
        layout.addWidget(self.chk_1_3)
        
        self.chk_4_6 = QCheckBox("บท &4 - 6 (คำย่อคำสมาส/คำสนธิ)")
        self.chk_4_6.setChecked(ch4_6)
        self.chk_4_6.setAccessibleName("บท 4 ถึง 6 คำย่อคำสมาสคำสนธิ")
        self.chk_4_6.setAccessibleDescription("เปิดใช้คำย่อจากตาราง CH46.tab สำหรับคำสมาสและคำสนธิ")
        layout.addWidget(self.chk_4_6)
        
        self.chk_7_8 = QCheckBox("บท &7 - 8 (คำย่อเฉพาะทาง)")
        self.chk_7_8.setChecked(ch7_8)
        self.chk_7_8.setAccessibleName("บท 7 ถึง 8 คำย่อเฉพาะทาง")
        self.chk_7_8.setAccessibleDescription("เปิดใช้คำย่อจากตาราง CH78.tab สำหรับคำศัพท์เฉพาะทาง")
        layout.addWidget(self.chk_7_8)
        
        self.chk_all = QCheckBox("เลือกทั้งหมด (&A)")
        self.chk_all.setChecked(ch1_3 and ch4_6 and ch7_8)
        self.chk_all.setAccessibleName("เลือกทุกบททั้งหมด")
        self.chk_all.toggled.connect(self.toggle_all)
        layout.addWidget(self.chk_all)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_ok = QPushButton("ตกลง (&O)")
        btn_ok.setDefault(True)
        btn_ok.setAccessibleName("ปุ่มตกลง")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        
        btn_cancel = QPushButton("ยกเลิก (&C)")
        btn_cancel.setAccessibleName("ปุ่มยกเลิก")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)

    def toggle_all(self, checked: bool):
        self.chk_1_3.setChecked(checked)
        self.chk_4_6.setChecked(checked)
        self.chk_7_8.setChecked(checked)

    def get_settings(self) -> Tuple[bool, bool, bool]:
        return self.chk_1_3.isChecked(), self.chk_4_6.isChecked(), self.chk_7_8.isChecked()




def get_settings(self) -> Tuple[bool, bool, bool]:
        return self.chk_1_3.isChecked(), self.chk_4_6.isChecked(), self.chk_7_8.isChecked()


class BraillePrintingDialog(QDialog):
    """
    หน้าต่างส่งพิมพ์อักษรเบรลล์ไปยังเครื่องพิมพ์เบรลล์ (Form4 ใน Delphi ดั้งเดิม: Printing Braill)
    รองรับทั้ง:
    1. เครื่องพิมพ์เบรลล์ USB / Network / SMB Share ที่ติดตั้งในระบบ Windows
    2. การส่งออกไฟล์ .BRF / .TBT
    3. กำหนดจำนวนสำเนา (Copies)
    4. โหมดพิมพ์หน้าเดียว (Single side) หรือ สองหน้า (Double side / Interpoint)
    5. ช่วงหน้า: ทั้งหมด (All) หรือระบุหน้า (From..To)
    """
    def __init__(self, parent: Optional[QWidget] = None, current_file: str = "", total_pages: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Printing Braille (ส่งพิมพ์อักษรเบรลล์)")
        self.setAccessibleName("หน้าต่างส่งพิมพ์อักษรเบรลล์ Form4")
        self.setWindowIcon(get_main_app_icon())
        self.setFixedSize(500, 460)
        self.total_pages = max(1, total_pages)
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid;
                border-color: #808080 #ffffff #ffffff #808080;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid;
                border-color: #ffffff #808080 #808080 #ffffff;
                padding: 4px 14px;
                min-width: 75px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                border-color: #808080 #ffffff #ffffff #808080;
                background-color: #d8d8d8;
            }
            QSpinBox, QComboBox, QLineEdit {
                background-color: #ffffff;
                border: 1px solid #808080;
                padding: 2px 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        
        # 1. ข้อมูลไฟล์
        file_box = QGroupBox("เอกสารที่จะพิมพ์ (File to Print)")
        file_layout = QHBoxLayout(file_box)
        self.txt_file = QLineEdit(current_file or "เอกสารปัจจุบัน (Current Document)")
        self.txt_file.setReadOnly(True)
        self.txt_file.setAccessibleName("ชื่อไฟล์เอกสารที่จะพิมพ์")
        file_layout.addWidget(self.txt_file)
        
        self.lbl_pages_info = QLabel(f"เอกสารนี้มีทั้งหมด: {self.total_pages} หน้า")
        self.lbl_pages_info.setStyleSheet("color: #000080; font-weight: bold;")
        self.lbl_pages_info.setAccessibleName(f"เอกสารนี้มี {self.total_pages} หน้า")
        file_layout.addWidget(self.lbl_pages_info)
        layout.addWidget(file_box)
        
        # 2. เครื่องพิมพ์ปลายทาง (Printer / Port)
        port_box = QGroupBox("เครื่องพิมพ์ / พอร์ต (Printer / Output)")
        port_layout = QVBoxLayout(port_box)
        
        self.cbo_printers = QComboBox()
        self.cbo_printers.setAccessibleName("เลือกเครื่องพิมพ์เบรลล์หรือพอร์ต")
        
        # ตรวจหาเครื่องพิมพ์ในระบบ Windows ผ่าน win32print
        found_printers = []
        if win32print is not None:
            try:
                flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
                p_list = win32print.EnumPrinters(flags)
                for p in p_list:
                    pname = p[2]
                    found_printers.append(pname)
            except Exception:
                pass
                
        for p in found_printers:
            self.cbo_printers.addItem(f"เครื่องพิมพ์: {p}", p)
            
        self.cbo_printers.addItem("บันทึกเป็นไฟล์ .BRF (Braille Formatted File)", "FILE_BRF")
        self.cbo_printers.addItem("พอร์ตขนานดั้งเดิม: Printer LPT1", "LPT1")
        self.cbo_printers.addItem("พอร์ตขนานดั้งเดิม: Printer LPT2", "LPT2")
        self.cbo_printers.addItem("พอร์ตสื่อสารซีเรียล / USB Virtual: COM1", "COM1")
        self.cbo_printers.addItem("พอร์ตสื่อสารซีเรียล / USB Virtual: COM2", "COM2")
        self.cbo_printers.addItem("พอร์ตสื่อสารซีเรียล / USB Virtual: COM3", "COM3")
        self.cbo_printers.addItem("พอร์ตสื่อสารซีเรียล / USB Virtual: COM4", "COM4")
        port_layout.addWidget(self.cbo_printers)
        
        # ตัวเลือกโปรไฟล์เครื่องพิมพ์เป้าหมาย (Embosser Model Profile)
        emb_row = QHBoxLayout()
        lbl_emb = QLabel("รุ่นเครื่องพิมพ์ (&Model) :")
        self.cbo_embosser = QComboBox()
        self.cbo_embosser.setAccessibleName("เลือกรุ่นเครื่องพิมพ์เบรลล์เป้าหมาย")
        for name, cpl, lpp in EMBOSSER_PROFILES:
            self.cbo_embosser.addItem(name, (cpl, lpp))
        lbl_emb.setBuddy(self.cbo_embosser)
        emb_row.addWidget(lbl_emb)
        emb_row.addWidget(self.cbo_embosser)
        port_layout.addLayout(emb_row)
        layout.addWidget(port_box)
        
        # 3. โหมดพิมพ์ (Single side vs Double side)
        mode_box = QGroupBox("รูปแบบการพิมพ์ (Printing Mode)")
        mode_layout = QHBoxLayout(mode_box)
        self.rb_single = QRadioButton("พิมพ์หน้าเดียว (Single Side)")
        self.rb_single.setChecked(True)
        self.rb_single.setAccessibleName("พิมพ์หน้าเดียว")
        self.rb_double = QRadioButton("พิมพ์สองหน้า (Double Side / Interpoint)")
        self.rb_double.setAccessibleName("พิมพ์สองหน้า")
        mode_layout.addWidget(self.rb_single)
        mode_layout.addWidget(self.rb_double)
        layout.addWidget(mode_box)
        
        # 4. ช่วงหน้า (Page Range) & จำนวนสำเนา (Copies)
        range_box = QGroupBox("ช่วงหน้าและจำนวนสำเนา (Page Range & Copies)")
        range_layout = QVBoxLayout(range_box)
        
        r_row1 = QHBoxLayout()
        self.rb_all = QRadioButton("ทุกหน้า (All Pages)")
        self.rb_all.setChecked(True)
        self.rb_all.setAccessibleName("พิมพ์ทุกหน้า")
        self.rb_range = QRadioButton("กำหนดช่วงหน้า (Pages) :")
        self.rb_range.setAccessibleName("กำหนดช่วงหน้า")
        
        self.spin_from = QSpinBox()
        self.spin_from.setRange(1, self.total_pages)
        self.spin_from.setValue(1)
        self.spin_from.setAccessibleName("หน้าเริ่มต้น")
        
        lbl_to = QLabel("ถึง")
        self.spin_to = QSpinBox()
        self.spin_to.setRange(1, self.total_pages)
        self.spin_to.setValue(self.total_pages)
        self.spin_to.setAccessibleName("หน้าสิ้นสุด")
        
        r_row1.addWidget(self.rb_all)
        r_row1.addWidget(self.rb_range)
        r_row1.addWidget(self.spin_from)
        r_row1.addWidget(lbl_to)
        r_row1.addWidget(self.spin_to)
        range_layout.addLayout(r_row1)
        
        r_row2 = QHBoxLayout()
        lbl_copies = QLabel("จำนวนสำเนา (How many copies) :")
        self.spin_copies = QSpinBox()
        self.spin_copies.setRange(1, 99)
        self.spin_copies.setValue(1)
        self.spin_copies.setAccessibleName("จำนวนชุดสำเนาที่จะพิมพ์")
        r_row2.addWidget(lbl_copies)
        r_row2.addWidget(self.spin_copies)
        r_row2.addStretch()
        range_layout.addLayout(r_row2)
        
        layout.addWidget(range_box)
        
        # ปุ่มคำสั่ง
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_print = QPushButton("ส่งพิมพ์ (&P)")
        btn_print.setDefault(True)
        btn_print.setAccessibleName("ปุ่มส่งพิมพ์เบรลล์")
        btn_print.clicked.connect(self.accept)
        btn_layout.addWidget(btn_print)
        
        btn_cancel = QPushButton("ยกเลิก (&C)")
        btn_cancel.setAccessibleName("ปุ่มยกเลิก")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
    def get_print_options(self):
        target = self.cbo_printers.currentData()
        copies = self.spin_copies.value()
        is_double = self.rb_double.isChecked()
        is_all = self.rb_all.isChecked()
        p_from = self.spin_from.value()
        p_to = self.spin_to.value()
        return {
            "target": target,
            "target_name": self.cbo_printers.currentText(),
            "embosser_profile": self.cbo_embosser.currentText(),
            "embosser_cpl_lpp": self.cbo_embosser.currentData(),
            "copies": copies,
            "is_double": is_double,
            "is_all": is_all,
            "page_from": p_from,
            "page_to": p_to
        }


class TactileGraphicsDialog(QDialog):
    """
    หน้าต่างแปลงภาพเป็นจุดสัมผัสเบรลล์ (Image to Braille Tactile Graphics Converter)
    สำหรับสร้างสื่อการเรียนรู้นูนสัมผัส แผนภาพ และงานกราฟิกสัมผัสสำหรับคนตาบอด
    แปลงภาพลายเส้น แผนภาพ หรือรูปถ่าย เป็นเมทริกซ์จุดเบรลล์ Unicode 8-dot (U+2800)
    และส่งออกหรือคัดลอกลงในกล่องแปลผลได้ทันที
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("สร้างสื่อภาพนูนสัมผัส (Tactile Graphics & Image to Braille)")
        self.setAccessibleName("หน้าต่างสร้างสื่อภาพนูนสัมผัสจากภาพ Image to Braille")
        self.setWindowIcon(get_main_app_icon())
        self.resize(680, 520)
        self.image_path = ""
        self.generated_braille = ""
        
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #808080;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid;
                border-color: #ffffff #808080 #808080 #ffffff;
                padding: 4px 14px;
                min-width: 75px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                border-color: #808080 #ffffff #ffffff #808080;
                background-color: #d8d8d8;
            }
            QPlainTextEdit {
                background-color: #ffffff;
                border: 2px solid;
                border-color: #808080 #ffffff #ffffff #808080;
                font-family: 'SimBraille', 'Consolas', monospace;
                font-size: 14px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        
        # ส่วนเลือกไฟล์ภาพ
        grp_file = QGroupBox("ไฟล์ภาพต้นฉบับ (Image Source)")
        file_layout = QHBoxLayout(grp_file)
        self.txt_file = QLineEdit()
        self.txt_file.setReadOnly(True)
        self.txt_file.setPlaceholderText("ยังไม่ได้เลือกไฟล์ภาพ (รองรับ PNG, JPG, BMP, GIF, WEBP)...")
        self.txt_file.setAccessibleName("ที่อยู่ไฟล์ภาพต้นฉบับ")
        file_layout.addWidget(self.txt_file)
        
        btn_browse = QPushButton("เลือกภาพ (&B)...")
        btn_browse.setAccessibleName("ปุ่มเลือกไฟล์ภาพ")
        btn_browse.clicked.connect(self.browse_image)
        file_layout.addWidget(btn_browse)
        layout.addWidget(grp_file)
        
        # ส่วนตั้งค่าการแปลงภาพ
        grp_opt = QGroupBox("การตั้งค่าภาพนูนสัมผัส (Tactile Settings)")
        opt_layout = QHBoxLayout(grp_opt)
        
        opt_layout.addWidget(QLabel("วิธีแปลง:"))
        self.cbo_algo = QComboBox()
        self.cbo_algo.addItem("ขีดแบ่งความเข้ม (Threshold)", "threshold")
        self.cbo_algo.addItem("กระจายจุดเฉดสี (Dithering)", "dither")
        self.cbo_algo.setAccessibleName("เลือกวิธีการแปลงภาพเป็นจุดสัมผัส")
        opt_layout.addWidget(self.cbo_algo)

        opt_layout.addWidget(QLabel("ความกว้าง (คอลัมน์):"))
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(10, 80)
        self.spin_cols.setValue(30)
        self.spin_cols.setAccessibleName("ความกว้างจำนวนคอลัมน์อักษรเบรลล์")
        opt_layout.addWidget(self.spin_cols)
        
        opt_layout.addWidget(QLabel("ระดับความเข้ม (Threshold):"))
        self.spin_thresh = QSpinBox()
        self.spin_thresh.setRange(10, 250)
        self.spin_thresh.setValue(128)
        self.spin_thresh.setAccessibleName("ค่าขีดแบ่งความเข้มขาวดำ Threshold")
        opt_layout.addWidget(self.spin_thresh)
        
        self.chk_invert = QCheckBox("กลับสี (&Invert)")
        self.chk_invert.setAccessibleName("ตัวเลือกกลับค่าสีขาวดำ")
        opt_layout.addWidget(self.chk_invert)
        
        btn_process = QPushButton("แปลง (&Convert)")
        btn_process.setDefault(True)
        btn_process.setStyleSheet("font-weight: bold; color: #000080;")
        btn_process.setAccessibleName("ปุ่มเริ่มการแปลงภาพเป็นจุดเบรลล์")
        btn_process.clicked.connect(self.convert_image)
        opt_layout.addWidget(btn_process)
        layout.addWidget(grp_opt)
        
        # ส่วนแสดงผลจุดเบรลล์ตัวอย่าง
        layout.addWidget(QLabel("ตัวอย่างผลลัพธ์จุดภาพนูนสัมผัส (Tactile Braille Preview):"))
        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setReadOnly(False)
        self.txt_preview.setAccessibleName("กล่องแสดงผลลัพธ์จุดภาพนูนสัมผัส สามารถคัดลอกหรือแก้ไขได้")
        layout.addWidget(self.txt_preview)
        
        # ปุ่มควบคุมด้านล่าง
        bottom_layout = QHBoxLayout()
        
        btn_export = QPushButton("ส่งออกไฟล์เบรลล์ (.BRF)...")
        btn_export.setAccessibleName("ส่งออกผลลัพธ์ภาพนูนเป็นไฟล์ BRF สำหรับเครื่องพิมพ์เบรลล์")
        btn_export.clicked.connect(self.export_brf)
        bottom_layout.addWidget(btn_export)
        
        bottom_layout.addStretch()
        
        btn_insert = QPushButton("นำเข้าสู่เอกสาร (&Insert)")
        btn_insert.setAccessibleName("ปุ่มนำภาพจุดเบรลล์นี้ไปแทรกลงในหน้าต่างอักษรเบรลล์")
        btn_insert.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_insert)
        
        btn_close = QPushButton("ปิด (&C)")
        btn_close.setAccessibleName("ปุ่มปิดหน้าต่าง")
        btn_close.clicked.connect(self.reject)
        bottom_layout.addWidget(btn_close)
        layout.addLayout(bottom_layout)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "เลือกไฟล์ภาพสำหรับสร้างสื่อเบรลล์",
            "",
            "รูปภาพ (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;ทุกไฟล์ (*.*)"
        )
        if file_path:
            self.image_path = file_path
            self.txt_file.setText(file_path)
            self.convert_image()

    def convert_image(self):
        if not self.image_path or not os.path.exists(self.image_path):
            QMessageBox.warning(self, "แจ้งเตือน", "กรุณาเลือกไฟล์ภาพก่อนทำการแปลง")
            return
            
        try:
            from PIL import Image, ImageOps
            
            im = Image.open(self.image_path).convert('L')
            if self.chk_invert.isChecked():
                im = ImageOps.invert(im)
                
            cols = self.spin_cols.value()
            threshold = self.spin_thresh.value()
            algo = self.cbo_algo.currentData()
            
            target_width = cols * 2
            aspect = im.height / max(im.width, 1)
            target_height = int(target_width * aspect * 0.55)
            target_height = max(4, ((target_height + 3) // 4) * 4)
            
            im = im.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            if algo == "dither":
                im = im.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
                
            pixels = im.load()
            if pixels is None:
                return
            
            # ตารางน้ำหนักเมทริกซ์ 2x4 ต่ออักษรเบรลล์ 1 เซลล์ตามมาตรฐาน Unicode Braille Patterns
            weights = [
                (0, 0, 0x01), (0, 1, 0x02), (0, 2, 0x04),
                (1, 0, 0x08), (1, 1, 0x10), (1, 2, 0x20),
                (0, 3, 0x40), (1, 3, 0x80)
            ]
            
            lines = []
            for y in range(0, target_height, 4):
                line = []
                for x in range(0, target_width, 2):
                    code = 0x2800
                    for dx, dy, w in weights:
                        px = x + dx
                        py = y + dy
                        if px < target_width and py < target_height:
                            val = pixels[px, py]
                            pixel_val = val[0] if isinstance(val, (tuple, list)) else val
                            if algo == "dither":
                                is_dot = (pixel_val == 0)
                            else:
                                is_dot = (pixel_val < threshold)
                            if is_dot:
                                code += w
                    line.append(chr(code))
                lines.append(''.join(line))
                
            self.generated_braille = '\n'.join(lines)
            self.txt_preview.setPlainText(self.generated_braille)
            algo_txt = "Dithering" if algo == "dither" else "Threshold"
            speak_nvda(f"แปลงภาพเป็นสื่อจุดเบรลล์สำเร็จ โหมด {algo_txt} ความกว้าง {cols} เซลล์ {len(lines)} บรรทัด")
        except Exception as e:
            QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถประมวลผลภาพได้: {e}")

    def export_brf(self):
        txt = self.txt_preview.toPlainText()
        if not txt.strip():
            QMessageBox.warning(self, "แจ้งเตือน", "ไม่มีข้อมูลจุดเบรลล์ให้ส่งออก กรุณาแปลงภาพก่อน")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "ส่งออกไฟล์ภาพนูนเบรลล์ (.BRF)",
            "tactile_graphic.brf",
            "Braille Formatted (*.brf);;All Files (*.*)"
        )
        if file_path:
            try:
                from tbtw_engine import ThaiBrailleTranslator
                trans = ThaiBrailleTranslator()
                ascii_payload = trans.to_ascii_braille(txt)
                with open(file_path, 'w', encoding='ascii', errors='replace') as f:
                    f.write(ascii_payload)
                QMessageBox.information(self, "ส่งออกสำเร็จ", f"ส่งออกไฟล์ภาพนูนเบรลล์ (.BRF) สำเร็จ:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถส่งออกไฟล์ได้: {e}")

    def get_braille_text(self) -> str:
        return self.txt_preview.toPlainText()


# ===========================================================================
# ระบบแปลงข้อความเป็นเลขตำแหน่งจุดเบรลล์ 1-6 (Braille Dot Numbers Converter)
# ===========================================================================

ASCII_BRAILLE_TO_DOTS = {
    ' ': ' ',
    'a': '1', 'b': '12', 'c': '14', 'd': '145', 'e': '15',
    'f': '124', 'g': '1245', 'h': '125', 'i': '24', 'j': '245',
    'k': '13', 'l': '123', 'm': '134', 'n': '1345', 'o': '135',
    'p': '1234', 'q': '12345', 'r': '1235', 's': '234', 't': '2345',
    'u': '136', 'v': '1236', 'w': '2456', 'x': '1346', 'y': '13456', 'z': '1356',
    '1': '1', '2': '12', '3': '14', '4': '145', '5': '15',
    '6': '124', '7': '1245', '8': '125', '9': '24', '0': '245',
    ',': '2', ';': '23', ':': '25', '.': '256', '!': '235',
    '(': '2356', ')': '2356', '?': '236', '"': '356', '*': '35', '\'': '3',
    '-': '36', '/': '34', '@': '4', '%': '146', '^': '45',
    '+': '235', '=': '2356', '<': '126', '>': '345', '[': '246',
    ']': '12456', '\\': '1256', '#': '3456'
}

DIGIT_TO_BRAILLE_DOTS = {
    '1': '1', '2': '12', '3': '14', '4': '145', '5': '15',
    '6': '124', '7': '1245', '8': '125', '9': '24', '0': '245',
    '๑': '1', '๒': '12', '๓': '14', '๔': '145', '๕': '15',
    '๖': '124', '๗': '1245', '๘': '125', '๙': '24', '๐': '245',
}

def unicode_braille_to_dots(ch: str) -> str:
    code = ord(ch)
    if 0x2800 <= code <= 0x28FF:
        val = code - 0x2800
        if val == 0:
            return " "
        dots = [str(i + 1) for i in range(8) if (val & (1 << i))]
        return "".join(dots)
    return ""

def text_to_braille_dot_numbers(
    text: str,
    translator=None,
    cell_sep: str = " ",
    word_sep: str = "  ",
    sep: Optional[str] = None,
    include_number_sign: bool = False
) -> str:
    """
    แปลงข้อความ (ไทย, อังกฤษ, ตัวเลข หรืออักษรเบรลล์) เป็นเลขระบุตำแหน่งจุดเบรลล์ 1-6
    เช่น:
      'ก' -> '1245'
      'a' -> '1'
      'b' -> '12'
      'ab' -> '1 12'
      '1' -> '1'  (หรือ '3456 1' หากเลือก include_number_sign=True)
      '12' -> '1 12'
      'ก ab 1' -> '1245  1 12  1'
    """
    if sep is not None:
        cell_sep = sep
    if not text:
        return ""
    output_lines = []
    for line in text.split('\n'):
        if not line:
            output_lines.append("")
            continue
        words = line.split(' ')
        converted_words = []
        for word in words:
            if not word:
                continue
            cells = []
            in_number_run = False
            for ch in word:
                code = ord(ch)
                # 1. รหัสเบรลล์ Unicode (U+2800 ถึง U+28FF)
                if 0x2800 <= code <= 0x28FF:
                    in_number_run = False
                    d = unicode_braille_to_dots(ch)
                    if d:
                        cells.append(d)
                    continue

                # 2. ตัวเลขอารบิก (0-9) หรือเลขไทย (๐-๙)
                if ch in DIGIT_TO_BRAILLE_DOTS:
                    if include_number_sign and not in_number_run:
                        cells.append('3456')  # เครื่องหมายนำเลข (#)
                        in_number_run = True
                    cells.append(DIGIT_TO_BRAILLE_DOTS[ch])
                    continue
                else:
                    in_number_run = False

                # 3. อักษรภาษาไทย
                if '\u0e00' <= ch <= '\u0e7f':
                    if translator:
                        try:
                            bu = translator.translate(ch)
                            for bch in bu:
                                d = unicode_braille_to_dots(bch)
                                if d:
                                    cells.append(d)
                        except Exception:
                            cells.append(ch)
                    else:
                        cells.append(ch)
                    continue

                # 4. อักษรภาษาอังกฤษ และสัญลักษณ์อื่นๆ
                ch_low = ch.lower()
                if ch_low in ASCII_BRAILLE_TO_DOTS:
                    cells.append(ASCII_BRAILLE_TO_DOTS[ch_low])
                else:
                    cells.append(ch)
            converted_words.append(cell_sep.join(cells))
        output_lines.append(word_sep.join(converted_words))
    return '\n'.join(output_lines)


class BrailleDotConverterDialog(QDialog):
    """
    หน้าต่างแปลงเป็นเลขตำแหน่งจุดเบรลล์ (Braille Dot Numbers Converter: จุด 1 ถึง 6)
    แปลงข้อความภาษาไทย, ภาษาอังกฤษ หรืออักษรเบรลล์ เป็นชุดเลขตำแหน่งจุด
    เช่น ก -> 1245, a -> 1, b -> 12, ab -> 1 12
    """
    def __init__(self, parent=None, initial_text="", translator=None):
        super().__init__(parent)
        self.setWindowTitle("เครื่องมือแปลงเป็นเลขตำแหน่งจุดเบรลล์ (Braille Dot Numbers)")
        self.setAccessibleName("หน้าต่างเครื่องมือแปลงเป็นเลขจุดเบรลล์ 1 ถึง 6")
        self.setWindowIcon(get_main_app_icon())
        self.resize(620, 440)
        self.translator = translator
        self.converted_text = ""

        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #808080;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid;
                border-color: #ffffff #808080 #808080 #ffffff;
                padding: 4px 14px;
                min-width: 80px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                border-color: #808080 #ffffff #ffffff #808080;
                background-color: #d8d8d8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Top Group: Input Text
        grp_in = QGroupBox("ข้อความต้นฉบับ (ภาษาไทย / อังกฤษ / อักษรเบรลล์)")
        lay_in = QVBoxLayout(grp_in)
        self.txt_input = QPlainTextEdit()
        self.txt_input.setFont(QFont("Tahoma", 11))
        self.txt_input.setPlaceholderText("พิมพ์ข้อความที่ต้องการตรวจเลขจุด เช่น ก หรือ ab...")
        self.txt_input.setAccessibleName("กล่องพิมพ์ข้อความต้นฉบับสำหรับแปลงเป็นเลขจุด")
        lay_in.addWidget(self.txt_input)
        layout.addWidget(grp_in)

        # Option: Number sign
        self.chk_number_sign = QCheckBox("ใส่เครื่องหมายนำเลขเบรลล์ (# = จุด 3456) นำหน้าตัวเลข")
        self.chk_number_sign.setFont(QFont("Tahoma", 10))
        self.chk_number_sign.setChecked(False)
        self.chk_number_sign.setAccessibleName("เลือกเพื่อให้ใส่เครื่องหมายนำเลขเบรลล์ จุด 3456 นำหน้าตัวเลข")
        self.chk_number_sign.toggled.connect(self.on_input_changed)
        layout.addWidget(self.chk_number_sign)

        # Bottom Group: Converted Dot Numbers
        grp_out = QGroupBox("เลขตำแหน่งจุดเบรลล์ 1-6 (เช่น ก = 1245, a = 1, b = 12, 1 = 1)")
        lay_out = QVBoxLayout(grp_out)
        self.txt_output = QPlainTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setFont(QFont("Consolas", 12))
        self.txt_output.setStyleSheet("background-color: #ffffff; color: #000080; font-weight: bold;")
        self.txt_output.setAccessibleName("กล่องแสดงผลลัพธ์เลขตำแหน่งจุดเบรลล์")
        lay_out.addWidget(self.txt_output)
        layout.addWidget(grp_out)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_copy = QPushButton("📋 คัดลอกเลขจุด")
        self.btn_copy.clicked.connect(self.copy_result)
        self.btn_insert = QPushButton("📥 แทรกในเอกสาร")
        self.btn_insert.clicked.connect(self.accept)
        self.btn_close = QPushButton("❌ ปิด")
        self.btn_close.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_copy)
        btn_layout.addWidget(self.btn_insert)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.txt_input.textChanged.connect(self.on_input_changed)
        if initial_text:
            self.txt_input.setPlainText(initial_text)

    def on_input_changed(self):
        text = self.txt_input.toPlainText()
        inc_sign = self.chk_number_sign.isChecked() if hasattr(self, 'chk_number_sign') else False
        res = text_to_braille_dot_numbers(text, self.translator, sep=" ", include_number_sign=inc_sign)
        self.txt_output.setPlainText(res)
        self.converted_text = res

    def copy_result(self):
        txt = self.txt_output.toPlainText()
        if txt:
            QApplication.clipboard().setText(txt)
            speak_nvda("คัดลอกเลขตำแหน่งจุดเบรลล์เรียบร้อยแล้ว")

    def get_result(self):
        return self.converted_text


class MathToBrailleDialog(QDialog):
    """
    หน้าต่างแปลงสูตรคณิตศาสตร์และวิทยาศาสตร์เป็นอักษรเบรลล์ (Math to Braille)
    ขับเคลื่อนด้วย MathCAT Engine (Nemeth Code / UEB Math)
    พร้อมการแสดงผลอักษรเบรลล์, เลขตำแหน่งจุด และคำอ่านออกเสียงสูตร (Speech)
    """
    def __init__(self, parent=None, initial_text=""):
        super().__init__(parent)
        self.setWindowTitle("เครื่องมือแปลงสูตรคณิตศาสตร์เป็นอักษรเบรลล์ (Math to Braille - Nemeth / UEB)")
        self.setAccessibleName("หน้าต่างเครื่องมือแปลงสูตรคณิตศาสตร์เป็นอักษรเบรลล์")
        self.setWindowIcon(get_main_app_icon())
        self.resize(720, 580)
        self.parent_window = parent

        self.converted_braille = ""
        self.converted_simbraille = ""
        self.converted_dots = ""
        self.converted_spoken = ""
        self.chosen_insert = ""

        # Load MathCAT Service
        from math_braille_service import MathCATService
        self.math_service = MathCATService.get_instance()

        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #808080;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid;
                border-color: #ffffff #808080 #808080 #ffffff;
                padding: 4px 10px;
                min-width: 60px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                border-color: #808080 #ffffff #ffffff #808080;
                background-color: #d8d8d8;
            }
            QLineEdit, QPlainTextEdit {
                background-color: #ffffff;
                border: 1px solid #7f9db9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # 1. Top Section: Math Formula Input
        grp_in = QGroupBox("สูตรคณิตศาสตร์ / สมการ (LaTeX, ASCIIMath หรือ MathML)")
        lay_in = QVBoxLayout(grp_in)

        # Quick Insert Toolbar
        tb_layout = QHBoxLayout()
        tb_layout.setSpacing(4)
        quick_symbols = [
            ("½ เศษส่วน", r"\frac{a}{b}"),
            ("√ รูท", r"\sqrt{x}"),
            ("x² ยกกำลัง", r"^2"),
            ("xᵢ ตัวห้อย", r"_1"),
            ("±", r"\pm"),
            ("×", r"\times"),
            ("÷", r"\div"),
            ("≠", r"\ne"),
            ("≤", r"\le"),
            ("≥", r"\ge"),
            ("π", r"\pi"),
            ("α", r"\alpha"),
            ("β", r"\beta"),
            ("θ", r"\theta"),
            ("∞", r"\infty"),
        ]
        for label, val in quick_symbols:
            btn = QPushButton(label)
            btn.setMaximumHeight(24)
            btn.setStyleSheet("padding: 2px 6px; font-size: 10px; min-width: 28px;")
            btn.clicked.connect(lambda checked=False, v=val: self.insert_symbol(v))
            tb_layout.addWidget(btn)
        tb_layout.addStretch()
        lay_in.addLayout(tb_layout)

        self.txt_math_input = QPlainTextEdit()
        self.txt_math_input.setFont(QFont("Consolas", 12))
        self.txt_math_input.setMaximumHeight(80)
        self.txt_math_input.setPlaceholderText(r"พิมพ์สูตรคณิตศาสตร์ เช่น \frac{1}{2}, \sqrt{16}=4, x^2+y^2=r^2 หรือ 1/2...")
        self.txt_math_input.setAccessibleName("กล่องพิมพ์สูตรคณิตศาสตร์หรือสมการ")
        lay_in.addWidget(self.txt_math_input)

        # Code selection row
        sel_layout = QHBoxLayout()
        sel_lbl = QLabel("มาตรฐานรหัสเบรลล์คณิตศาสตร์:")
        sel_lbl.setFont(QFont("Tahoma", 10, QFont.Weight.Bold))
        sel_layout.addWidget(sel_lbl)

        self.rb_nemeth = QRadioButton("Nemeth Code (มาตรฐานที่ใช้ในไทยและสากล)")
        self.rb_nemeth.setChecked(True)
        self.rb_nemeth.toggled.connect(self.on_input_changed)
        sel_layout.addWidget(self.rb_nemeth)

        self.rb_ueb = QRadioButton("UEB Math (Unified English Braille)")
        self.rb_ueb.toggled.connect(self.on_input_changed)
        sel_layout.addWidget(self.rb_ueb)
        sel_layout.addStretch()
        lay_in.addLayout(sel_layout)

        layout.addWidget(grp_in)

        # 2. Output Group: Braille & Spoken Math
        grp_out = QGroupBox("ผลลัพธ์การแปลงอักษรเบรลล์คณิตศาสตร์")
        lay_out = QVBoxLayout(grp_out)

        # Braille Output Row
        lbl_br = QLabel("อักษรเบรลล์ (SimBraille Font & Unicode):")
        lay_out.addWidget(lbl_br)

        self.txt_braille_out = QPlainTextEdit()
        self.txt_braille_out.setReadOnly(True)
        self.txt_braille_out.setMaximumHeight(80)
        use_simbrl = getattr(self.parent_window, 'simbrl_font_loaded', False)
        if use_simbrl:
            self.txt_braille_out.setFont(QFont("SimBraille", 18))
        else:
            self.txt_braille_out.setFont(QFont("Consolas", 14))
        self.txt_braille_out.setStyleSheet("background-color: #ffffff; color: #000080; font-weight: bold;")
        self.txt_braille_out.setAccessibleName("กล่องแสดงผลลัพธ์อักษรเบรลล์คณิตศาสตร์")
        lay_out.addWidget(self.txt_braille_out)

        # Spoken reading row
        spk_layout = QHBoxLayout()
        lbl_spk = QLabel("คำอ่านออกเสียง (Speech):")
        lbl_spk.setFont(QFont("Tahoma", 10))
        spk_layout.addWidget(lbl_spk)

        self.txt_spoken_out = QLineEdit()
        self.txt_spoken_out.setReadOnly(True)
        self.txt_spoken_out.setFont(QFont("Tahoma", 10))
        self.txt_spoken_out.setStyleSheet("background-color: #ffffff; color: #005500; font-weight: bold;")
        self.txt_spoken_out.setAccessibleName("คำอ่านออกเสียงสูตรคณิตศาสตร์")
        spk_layout.addWidget(self.txt_spoken_out)

        self.btn_speak = QPushButton("🔊 ฟังเสียงอ่าน")
        self.btn_speak.setToolTip("อ่านออกเสียงสูตรคณิตศาสตร์ด้วย NVDA")
        self.btn_speak.clicked.connect(self.speak_formula)
        spk_layout.addWidget(self.btn_speak)
        lay_out.addLayout(spk_layout)

        # Dot numbers row
        dot_layout = QHBoxLayout()
        lbl_dot = QLabel("เลขตำแหน่งจุด (Dots 1-6):")
        lbl_dot.setFont(QFont("Tahoma", 10))
        dot_layout.addWidget(lbl_dot)

        self.txt_dots_out = QLineEdit()
        self.txt_dots_out.setReadOnly(True)
        self.txt_dots_out.setFont(QFont("Consolas", 11))
        self.txt_dots_out.setStyleSheet("background-color: #ffffff; color: #800000; font-weight: bold;")
        self.txt_dots_out.setAccessibleName("เลขตำแหน่งจุดเบรลล์ 6 จุดของสูตร")
        dot_layout.addWidget(self.txt_dots_out)
        lay_out.addLayout(dot_layout)

        layout.addWidget(grp_out)

        # 3. Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_copy_braille = QPushButton("📋 คัดลอกอักษรเบรลล์")
        self.btn_copy_braille.clicked.connect(self.copy_braille)
        btn_layout.addWidget(self.btn_copy_braille)

        self.btn_copy_dots = QPushButton("📋 คัดลอกเลขจุด")
        self.btn_copy_dots.clicked.connect(self.copy_dots)
        btn_layout.addWidget(self.btn_copy_dots)

        self.btn_insert = QPushButton("📥 แทรกอักษรเบรลล์ในเอกสาร")
        self.btn_insert.setStyleSheet("font-weight: bold; color: #000080;")
        self.btn_insert.clicked.connect(self.insert_into_editor)
        btn_layout.addWidget(self.btn_insert)

        btn_layout.addStretch()

        self.btn_close = QPushButton("❌ ปิด")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        self.txt_math_input.textChanged.connect(self.on_input_changed)
        if initial_text:
            self.txt_math_input.setPlainText(initial_text)

    def insert_symbol(self, symbol: str):
        cursor = self.txt_math_input.textCursor()
        cursor.insertText(symbol)
        self.txt_math_input.setTextCursor(cursor)
        self.txt_math_input.setFocus()

    def on_input_changed(self):
        text = self.txt_math_input.toPlainText().strip()
        if not text:
            self.txt_braille_out.clear()
            self.txt_spoken_out.clear()
            self.txt_dots_out.clear()
            self.converted_braille = ""
            self.converted_simbraille = ""
            self.converted_dots = ""
            self.converted_spoken = ""
            return

        code = "Nemeth" if self.rb_nemeth.isChecked() else "UEB"
        res = self.math_service.convert(text, code=code)

        if res["success"]:
            self.converted_braille = res["braille"]
            self.converted_simbraille = res["simbraille_ascii"]
            self.converted_dots = res["dot_numbers"]
            self.converted_spoken = res["spoken"]

            use_simbrl = getattr(self.parent_window, 'simbrl_font_loaded', False)
            if use_simbrl and res["simbraille_ascii"]:
                self.txt_braille_out.setPlainText(res["simbraille_ascii"])
            else:
                self.txt_braille_out.setPlainText(res["braille"])

            self.txt_spoken_out.setText(res["spoken"])
            self.txt_dots_out.setText(res["dot_numbers"])
        else:
            self.txt_braille_out.setPlainText(f"(ข้อผิดพลาด: {res.get('error', '')})")
            self.txt_spoken_out.clear()
            self.txt_dots_out.clear()

    def speak_formula(self):
        if self.converted_spoken:
            speak_nvda(f"สูตรคณิตศาสตร์: {self.converted_spoken}", interrupt=True)
        else:
            speak_nvda("ยังไม่มีผลลัพธ์เสียงอ่านสูตรคณิตศาสตร์")

    def copy_braille(self):
        txt = self.converted_braille or self.txt_braille_out.toPlainText()
        if txt:
            QApplication.clipboard().setText(txt)
            speak_nvda("คัดลอกอักษรเบรลล์คณิตศาสตร์เรียบร้อยแล้ว")

    def copy_dots(self):
        txt = self.converted_dots
        if txt:
            QApplication.clipboard().setText(txt)
            speak_nvda("คัดลอกเลขตำแหน่งจุดเบรลล์คณิตศาสตร์เรียบร้อยแล้ว")

    def insert_into_editor(self):
        use_simbrl = getattr(self.parent_window, 'simbrl_font_loaded', False)
        if use_simbrl and self.converted_simbraille:
            self.chosen_insert = self.converted_simbraille
        else:
            self.chosen_insert = self.converted_braille or self.txt_braille_out.toPlainText()
        self.accept()

    def get_result(self) -> str:
        return self.chosen_insert


def crc16_ibm(data: str) -> str:
    crc = 0xFFFF
    for ch in data:
        x = ((crc >> 8) ^ ord(ch)) & 0xFF
        x ^= x >> 4
        crc = ((crc << 8) ^ (x << 12) ^ (x << 5) ^ x) & 0xFFFF
    return f"{crc:04X}"


def generate_promptpay_payload(target_id: str, amount: float = 0.0) -> str:
    clean = "".join(c for c in target_id if c.isdigit())
    if len(clean) == 10 and clean.startswith("0"):
        phone = "0066" + clean[1:]
        subtag = f"01{len(phone):02d}{phone}"
    elif len(clean) == 13:
        subtag = f"02{len(clean):02d}{clean}"
    else:
        phone = "0066" + clean
        subtag = f"01{len(phone):02d}{phone}"
    aid = "A000000677010111"
    tag29_v = f"00{len(aid):02d}{aid}{subtag}"
    tag29 = f"29{len(tag29_v):02d}{tag29_v}"
    payload = "000201" + ("010212" if amount > 0 else "010211") + tag29 + "5303764"
    if amount > 0:
        amt_str = f"{amount:.2f}"
        payload += f"54{len(amt_str):02d}{amt_str}"
    payload += "5802TH6304"
    return payload + crc16_ibm(payload)


class TrialExpiredDialog(QDialog):
    """หน้าต่างแจ้งเตือนเมื่อระยะเวลาทดลองใช้ฟรี 14 วันสิ้นสุดลง"""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("ระยะเวลาทดลองใช้ฟรีสิ้นสุดแล้ว - SiamBraille 1.0")
        self.setAccessibleName("หน้าต่างแจ้งเตือนระยะเวลาทดลองใช้ฟรี 14 วันสิ้นสุดลงแล้ว")
        self.setAccessibleDescription("ท่านได้ใช้งานครบกำหนดทดลองใช้ฟรี 14 วันแล้ว กรุณาสั่งซื้อหรือเปิดใช้งานลิขสิทธิ์")
        self.setWindowIcon(get_main_app_icon())
        self.setFixedSize(540, 360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Tahoma', 'Segoe UI', sans-serif;
            }
            QPushButton {
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                min-height: 38px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        lbl_title = QLabel("⏳ ระยะเวลาทดลองใช้ฟรี 14 วันสิ้นสุดลงแล้ว")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #dc2626;")
        layout.addWidget(lbl_title)

        hwid = license_guard.global_license_manager.hwid
        lbl_msg = QLabel(
            "ขอขอบคุณที่ทดลองใช้งาน <b>SiamBraille 1.0</b><br>"
            f"คอมพิวเตอร์เครื่องนี้ (รหัส HWID: <code>{hwid}</code>) ได้ใช้งานครบกำหนดสิทธิ์ทดลองใช้ฟรี 14 วันแล้ว<br><br>"
            "เพื่อใช้งานฟังก์ชันการแปลเอกสาร บันทึก และพิมพ์อักษรเบรลล์ต่ออย่างต่อเนื่อง "
            "กรุณาเลือกดำเนินการด้านล่างนี้ครับ:"
        )
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet("color: #334155; font-size: 12px; line-height: 1.4;")
        layout.addWidget(lbl_msg)

        btn_box = QVBoxLayout()
        btn_box.setSpacing(10)

        self.btn_buy = QPushButton("💳 1. สั่งซื้อลิขสิทธิ์ผ่านไทยพร้อมเพย์ (PromptPay QR)... (&B)")
        self.btn_buy.setShortcut(QKeySequence("Alt+B"))
        self.btn_buy.setStyleSheet("background-color: #0284c7; color: #ffffff; border: none; font-size: 13px;")
        self.btn_buy.clicked.connect(self.open_buy_dialog)
        btn_box.addWidget(self.btn_buy)

        self.btn_activate = QPushButton("🔑 2. มีรหัสคีย์แล้ว? เปิดใช้งานลิขสิทธิ์ทันที (&A)")
        self.btn_activate.setShortcut(QKeySequence("Alt+A"))
        self.btn_activate.setStyleSheet("background-color: #16a34a; color: #ffffff; border: none; font-size: 13px;")
        self.btn_activate.clicked.connect(self.open_activate_dialog)
        btn_box.addWidget(self.btn_activate)

        layout.addLayout(btn_box)
        layout.addStretch()

        bot_box = QHBoxLayout()
        bot_box.addStretch()
        btn_close = QPushButton("ปิด (&X)")
        btn_close.setShortcut(QKeySequence("Alt+X"))
        btn_close.setStyleSheet("background-color: #e2e8f0; color: #0f172a; border: 1px solid #cbd5e1;")
        btn_close.clicked.connect(self.accept)
        bot_box.addWidget(btn_close)
        layout.addLayout(bot_box)

    def open_buy_dialog(self):
        self.accept()
        dlg = LicensePurchaseDialog(self.parentWidget())
        dlg.exec()

    def open_activate_dialog(self):
        self.accept()
        dlg = LicenseActivationDialog(self.parentWidget())
        dlg.exec()

    def showEvent(self, event):
        super().showEvent(event)
        self.btn_buy.setFocus()
        speak_nvda("ระยะเวลาทดลองใช้ฟรี 14 วันของเครื่องนี้สิ้นสุดแล้ว กรุณาสั่งซื้อหรือเปิดใช้งานลิขสิทธิ์ กด Alt+B เพื่อสั่งซื้อ หรือ Alt+A เพื่อเปิดใช้งานด้วยรหัสคีย์")


class LicenseActivationDialog(QDialog):
    """หน้าต่างเปิดใช้งานรหัสลิขสิทธิ์ SiamBraille โดยไม่ต้องคัดลอกไฟล์"""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("เปิดใช้งานลิขสิทธิ์ - SiamBraille 1.0")
        self.setAccessibleName("หน้าต่างเปิดใช้งานรหัสลิขสิทธิ์โปรแกรม SiamBraille")
        self.setWindowIcon(get_main_app_icon())
        self.setFixedSize(480, 290)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Tahoma', 'Segoe UI', sans-serif;
                font-size: 11px;
            }
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #0369a1;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 10.5px;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton#btnCancel {
                background-color: #e2e8f0;
                color: #334155;
                border: 1px solid #cbd5e1;
            }
            QPushButton#btnCancel:hover {
                background-color: #cbd5e1;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #94a3b8;
                border-radius: 4px;
                padding: 4px 8px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                font-weight: bold;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 1.5px solid #0284c7;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        lbl_title = QLabel("<b>🔑 เปิดใช้งานรหัสลิขสิทธิ์ SiamBraille 1.0</b>")
        lbl_title.setStyleSheet("font-size: 13.5px; color: #0369a1;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            "กรุณากรอกรหัสคีย์ (License Key เช่น SB10-XXXX-XXXX-XXXX) หรือ Token ลิขสิทธิ์ที่ได้รับ<br>"
            "ระบบจะเปิดใช้งานและผูกกับเครื่องนี้โดยอัตโนมัติ โดยไม่ต้องดาวน์โหลดหรือคัดลอกไฟล์ใดๆ"
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #475569; font-size: 10.5px; line-height: 1.3;")
        layout.addWidget(lbl_desc)

        # HWID Box
        hwid_layout = QHBoxLayout()
        hwid = license_guard.global_license_manager.hwid
        lbl_hwid = QLabel(f"<b>รหัสเครื่องนี้ (HWID):</b> <span style='font-family: Consolas; color: #0284c7; font-size: 11px;'>{hwid}</span>")
        hwid_layout.addWidget(lbl_hwid)
        btn_copy_hwid = QPushButton("📋 คัดลอก")
        btn_copy_hwid.setObjectName("btnCancel")
        btn_copy_hwid.setFixedWidth(60)
        btn_copy_hwid.setStyleSheet("font-size: 10px; padding: 2px 6px; min-height: 22px;")
        btn_copy_hwid.clicked.connect(lambda: self.copy_to_clipboard(hwid, "คัดลอกรหัส HWID แล้ว"))
        hwid_layout.addWidget(btn_copy_hwid)
        layout.addLayout(hwid_layout)

        # Key Input
        layout.addWidget(QLabel("<b>ป้อนรหัส License Key:</b>"))
        self.txt_key = QLineEdit()
        self.txt_key.setPlaceholderText("SB10-XXXX-XXXX-XXXX")
        self.txt_key.setAccessibleName("ช่องกรอกรหัสลิขสิทธิ์ License Key")
        layout.addWidget(self.txt_key)

        # Status Label
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 10.5px; font-weight: bold;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_buy = QPushButton("💳 สั่งซื้อ License (PromptPay)")
        self.btn_buy.setObjectName("btnCancel")
        self.btn_buy.clicked.connect(self.open_buy_dialog)
        btn_layout.addWidget(self.btn_buy)

        btn_layout.addStretch()

        btn_cancel = QPushButton("ยกเลิก")
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        self.btn_activate = QPushButton("🚀 เปิดใช้งานทันที")
        self.btn_activate.setDefault(True)
        self.btn_activate.clicked.connect(self.do_activate)
        btn_layout.addWidget(self.btn_activate)

        layout.addLayout(btn_layout)

    def copy_to_clipboard(self, text: str, msg: str):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text)
        speak_nvda(msg)
        self.lbl_status.setStyleSheet("color: #0284c7;")
        self.lbl_status.setText(msg)

    def open_buy_dialog(self):
        self.reject()
        dlg = LicensePurchaseDialog(self.parentWidget())
        dlg.exec()

    def do_activate(self):
        key = self.txt_key.text().strip()
        if not key:
            QMessageBox.warning(self, "แจ้งเตือน", "กรุณากรอกรหัส License Key ก่อนคลิกเปิดใช้งาน")
            return

        self.btn_activate.setEnabled(False)
        self.lbl_status.setStyleSheet("color: #0284c7;")
        self.lbl_status.setText("⏳ กำลังตรวจสอบและเปิดใช้งานออนไลน์...")
        QApplication.processEvents()

        ok, msg = license_guard.global_license_manager.activate_with_key_string(key)
        self.btn_activate.setEnabled(True)

        if ok:
            speak_nvda("เปิดใช้งานลิขสิทธิ์ SiamBraille 1.0 สำเร็จเรียบร้อยแล้ว")
            QMessageBox.information(self, "เปิดใช้งานสำเร็จ", msg)
            parent = self.parentWidget()
            if parent is not None and hasattr(parent, "update_license_ui"):
                getattr(parent, "update_license_ui")()
            self.accept()
        else:
            speak_nvda(f"ข้อผิดพลาด: {msg}")
            self.lbl_status.setStyleSheet("color: #dc2626;")
            self.lbl_status.setText(f"❌ {msg}")
            QMessageBox.warning(self, "ไม่สามารถเปิดใช้งานได้", msg)


class LicensePurchaseDialog(QDialog):
    """หน้าต่างสั่งซื้อลิขสิทธิ์ SiamBraille 1.0 ผ่าน PromptPay QR จากในโปรแกรม"""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("สั่งซื้อลิขสิทธิ์ SiamBraille 1.0 (PromptPay)")
        self.setAccessibleName("หน้าต่างสั่งซื้อลิขสิทธิ์ SiamBraille ผ่านระบบพร้อมเพย์")
        self.setWindowIcon(get_main_app_icon())
        self.setFixedSize(500, 465)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Tahoma', 'Segoe UI', sans-serif;
                font-size: 10.5px;
            }
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #0369a1;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 10.5px;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton#btnSecondary {
                background-color: #e2e8f0;
                color: #334155;
                border: 1px solid #cbd5e1;
            }
            QPushButton#btnSecondary:hover {
                background-color: #cbd5e1;
            }
            QGroupBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                font-weight: bold;
                font-size: 10.5px;
                color: #1e293b;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QRadioButton {
                font-size: 10.5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        lbl_title = QLabel("<b>💳 สั่งซื้อลิขสิทธิ์ SiamBraille 1.0 ผ่านไทยพร้อมเพย์</b>")
        lbl_title.setStyleSheet("font-size: 13.5px; color: #0369a1;")
        layout.addWidget(lbl_title)

        # Plan Selection
        grp_plan = QGroupBox("1. เลือกแพ็กเกจที่ต้องการสั่งซื้อ")
        plan_layout = QVBoxLayout(grp_plan)
        self.rb_personal = QRadioButton("บุคคลทั่วไป (Personal Lifetime) — 1,290 บาท (1 เครื่อง ตลอดชีพ)")
        self.rb_personal.setChecked(True)
        self.rb_personal.toggled.connect(self.on_plan_changed)
        plan_layout.addWidget(self.rb_personal)

        self.rb_edu = QRadioButton("สถานศึกษา / องค์กร (Lab) — 4,900 บาท (5 เครื่อง ตลอดชีพ)")
        self.rb_edu.toggled.connect(self.on_plan_changed)
        plan_layout.addWidget(self.rb_edu)
        layout.addWidget(grp_plan)

        # QR and Payment Details
        grp_pay = QGroupBox("2. สแกนชำระเงินผ่านแอปธนาคารทุกแห่ง")
        pay_layout = QHBoxLayout(grp_pay)

        # Left: QR Code Box
        self.lbl_qr = QLabel()
        self.lbl_qr.setFixedSize(125, 125)
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;")
        pay_layout.addWidget(self.lbl_qr)

        # Right: Payment Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        self.lbl_price_display = QLabel("<b>ยอดชำระ:</b> <span style='font-size: 14.5px; color: #0284c7;'>1,290.00 บาท</span>")
        info_layout.addWidget(self.lbl_price_display)

        lbl_acc = QLabel("<b>ชื่อบัญชี:</b> สยามเบรลล์ ซอฟต์แวร์ (SiamBraille)")
        lbl_acc.setStyleSheet("font-size: 10px;")
        info_layout.addWidget(lbl_acc)

        pp_box = QHBoxLayout()
        self.pp_target = "0819999999"
        lbl_pp = QLabel(f"<b>พร้อมเพย์:</b> <span style='font-family: Consolas; font-size: 11px;'>{self.pp_target}</span>")
        pp_box.addWidget(lbl_pp)
        btn_copy_pp = QPushButton("📋 คัดลอก")
        btn_copy_pp.setObjectName("btnSecondary")
        btn_copy_pp.setFixedWidth(60)
        btn_copy_pp.clicked.connect(lambda: self.copy_to_clipboard(self.pp_target, "คัดลอกหมายเลขพร้อมเพย์แล้ว"))
        pp_box.addWidget(btn_copy_pp)
        info_layout.addLayout(pp_box)

        lbl_notice = QLabel(
            "⚡ เมื่อโอนเงินแล้ว ท่านสามารถเปิดหน้าเว็บเพื่อส่งสลิปตรวจ Mini QR หรือติดต่อผู้ดูแลเพื่อรับ License Key ทันที"
        )
        lbl_notice.setWordWrap(True)
        lbl_notice.setStyleSheet("color: #64748b; font-size: 9.5px; line-height: 1.2;")
        info_layout.addWidget(lbl_notice)

        pay_layout.addLayout(info_layout)
        layout.addWidget(grp_pay)

        # Bottom Actions
        layout.addStretch()

        btn_web = QPushButton("🌐 เปิดหน้าสั่งซื้อและแจ้งสลิปบนเว็บไซต์ (siam-braille.web.app)")
        btn_web.clicked.connect(lambda: webbrowser.open("https://siam-braille.web.app/#pricing"))
        layout.addWidget(btn_web)

        btn_bar = QHBoxLayout()
        btn_act_now = QPushButton("🔑 มีรหัสคีย์แล้ว? เปิดใช้งานทันที")
        btn_act_now.clicked.connect(self.open_activate_dialog)
        btn_bar.addWidget(btn_act_now)

        btn_bar.addStretch()

        btn_close = QPushButton("ปิด")
        btn_close.setObjectName("btnSecondary")
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_close)
        layout.addLayout(btn_bar)

        self.update_qr()

    def on_plan_changed(self):
        self.update_qr()

    def update_qr(self):
        amount = 1290.0 if self.rb_personal.isChecked() else 4900.0
        self.lbl_price_display.setText(f"<b>ยอดชำระ:</b> <span style='font-size: 14.5px; color: #0284c7;'>{amount:,.2f} บาท</span>")
        if qrcode:
            try:
                pp_payload = generate_promptpay_payload(self.pp_target, amount)
                img = qrcode.make(pp_payload)
                buf = io.BytesIO()
                img.save(buf)
                pix = QPixmap()
                pix.loadFromData(buf.getvalue())
                self.lbl_qr.setPixmap(pix.scaled(118, 118, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            except Exception:
                self.lbl_qr.setText("PromptPay QR")
        else:
            self.lbl_qr.setText("PromptPay QR")

    def copy_to_clipboard(self, text: str, msg: str):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text)
        speak_nvda(msg)

    def open_activate_dialog(self):
        self.reject()
        dlg = LicenseActivationDialog(self.parentWidget())
        dlg.exec()


class CheckUpdateDialog(QDialog):
    """หน้าต่างตรวจสอบการอัปเดตและแพตช์แก้ไขข้อผิดพลาด"""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("ตรวจสอบการอัปเดต - SiamBraille 1.0")
        self.setAccessibleName("หน้าต่างตรวจสอบการอัปเดตซอฟต์แวร์ SiamBraille")
        self.setWindowIcon(get_main_app_icon())
        self.setFixedSize(490, 380)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Tahoma', 'Segoe UI', sans-serif;
                font-size: 10.5px;
            }
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #0369a1;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 10.5px;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton#btnSecondary {
                background-color: #e2e8f0;
                color: #334155;
                border: 1px solid #cbd5e1;
            }
            QPushButton#btnSecondary:hover {
                background-color: #cbd5e1;
            }
            QPlainTextEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px;
                font-family: 'Tahoma', 'Segoe UI';
                font-size: 10px;
                color: #1e293b;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        lbl_title = QLabel("<b>🔄 ระบบตรวจสอบการอัปเดต SiamBraille</b>")
        lbl_title.setStyleSheet("font-size: 13.5px; color: #0369a1;")
        layout.addWidget(lbl_title)

        self.lbl_ver_status = QLabel("กำลังเชื่อมต่อเซิร์ฟเวอร์เพื่อตรวจสอบเวอร์ชันล่าสุด...")
        self.lbl_ver_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #0f172a;")
        layout.addWidget(self.lbl_ver_status)

        layout.addWidget(QLabel("<b>รายการปรับปรุงและแพตช์แก้ไขข้อผิดพลาด (Changelog):</b>"))
        self.txt_changelog = QPlainTextEdit()
        self.txt_changelog.setReadOnly(True)
        layout.addWidget(self.txt_changelog)

        btn_layout = QHBoxLayout()
        self.btn_download = QPushButton("🚀 ดาวน์โหลดตัวติดตั้งล่าสุด (Setup)")
        self.btn_download.clicked.connect(self.do_download)
        btn_layout.addWidget(self.btn_download)

        btn_layout.addStretch()

        btn_close = QPushButton("ปิด")
        btn_close.setObjectName("btnSecondary")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.download_url = "https://siam-braille.web.app/api/download/setup"
        self.check_version()

    def check_version(self):
        curr_ver = "1.0.0"
        url = "https://siam-braille.web.app/version.json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SiamBraille-Client/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    remote_ver = data.get("version", "1.0.0")
                    rel_date = data.get("release_date", "2026-10-16")
                    logs = data.get("changelog", [])
                    self.download_url = data.get("download_url", self.download_url)

                    log_text = f"เวอร์ชันในเครื่อง: {curr_ver}\nเวอร์ชันบนเซิร์ฟเวอร์: {remote_ver} ({rel_date})\n"
                    log_text += "=" * 50 + "\n\n"
                    for idx, item in enumerate(logs, 1):
                        log_text += f"{idx}. {item}\n"

                    self.txt_changelog.setPlainText(log_text)
                    self.lbl_ver_status.setText(f"✅ คุณกำลังใช้งาน SiamBraille เวอร์ชันล่าสุด ({curr_ver})")
                    self.lbl_ver_status.setStyleSheet("font-size: 12px; font-weight: bold; color: #15803d;")
                    speak_nvda(f"ตรวจสอบการอัปเดตแล้ว ท่านกำลังใช้งานเวอร์ชันล่าสุด {curr_ver}")
                    return
        except Exception:
            pass

        # Fallback offline
        self.lbl_ver_status.setText(f"✅ SiamBraille เวอร์ชัน {curr_ver} (พร้อมใช้งาน)")
        self.txt_changelog.setPlainText(
            f"เวอร์ชันปัจจุบัน: {curr_ver}\n"
            "1. ปรับปรุงการตัดคำภาษาไทย 30 เซลล์ให้คงรูปคำโดยไม่ตัดกลางพยางค์หรือสระ\n"
            "2. เพิ่มระบบเลขหน้าอักษรเบรลล์ (#a, #b...) มุมขวาบนบรรทัดที่ 1 ของทุกหน้า\n"
            "3. ย้ายตำแหน่งติดตั้งมาตรฐานไปยัง C:\\Program Files\\SiamBraille\n"
            "4. เพิ่มระบบตรวจสอบและแสดงสถานะลิขสิทธิ์ / รหัสคีย์ในเมนูเกี่ยวกับ\n"
            "5. รองรับการสั่งซื้อและเปิดใช้งาน License ผ่านตัวโปรแกรมโดยตรง"
        )

    def do_download(self):
        webbrowser.open(self.download_url)


class AboutBoxDialog(QDialog):
    """
    หน้าต่าง About SiamBraille 1.0
    แสดงข้อมูลลิขสิทธิ์ สถานะคีย์ และคุณสมบัติของซอฟต์แวร์
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("About SiamBraille 1.0 Professional Edition")
        self.setAccessibleName("หน้าต่างเกี่ยวกับโปรแกรม SiamBraille 1.0 และสถานะลิขสิทธิ์")
        self.setWindowIcon(get_main_app_icon())
        self.setFixedSize(530, 465)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Tahoma', 'Segoe UI', sans-serif;
                font-size: 11px;
            }
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #0369a1;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 10.5px;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton#btnSecondary {
                background-color: #e2e8f0;
                color: #334155;
                border: 1px solid #cbd5e1;
            }
            QPushButton#btnSecondary:hover {
                background-color: #cbd5e1;
            }
            QGroupBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                font-weight: bold;
                font-size: 11px;
                color: #1e293b;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header: Logo + App Info
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        logo_frame = QFrame()
        logo_frame.setStyleSheet("background-color: #0b192c; border: 1.5px solid #0284c7; border-radius: 6px;")
        logo_frame.setFixedSize(68, 68)

        lbl_img = QLabel(logo_frame)
        lbl_img.setGeometry(2, 2, 64, 64)
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_img.setAccessibleName("โลโก้สัญลักษณ์ SiamBraille 1.0")

        logo_file = None
        for cand in [
            os.path.join("logo", "siam-braille-logo.jpg"),
            "siam-braille-logo.jpg",
            "SiamBraille.ico",
            os.path.join("assets", "icons", "SiamBraille.ico")
        ]:
            p = get_resource_path(cand)
            if os.path.exists(p):
                logo_file = p
                break

        if logo_file:
            pix = QPixmap(logo_file).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_img.setPixmap(pix)
        else:
            lbl_img.setText("SiamBraille")

        top_layout.addWidget(logo_frame)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)

        lbl_title = QLabel("<b>SiamBraille 1.0</b>")
        lbl_title.setStyleSheet("font-size: 14.5px; color: #000080; font-family: 'Tahoma';")
        header_layout.addWidget(lbl_title)

        lbl_ver = QLabel("<b>Professional Edition (Version 1.0.0 — Build 2026)</b>")
        lbl_ver.setStyleSheet("font-size: 11px; color: #0f172a;")
        header_layout.addWidget(lbl_ver)

        lbl_desc = QLabel(
            "ระบบแปลและจัดพิมพ์เอกสารอักษรเบรลล์ภาษาไทยและสากลระดับมืออาชีพ<br>"
            "ตามคู่มือมาตรฐานการใช้อักษรเบรลล์ในประเทศไทย ฉบับปรับปรุง พ.ศ. 2564<br>"
            "รองรับการล็อก 30 เซลล์ x 25 บรรทัด และจัดเลขหน้าอัตโนมัติ"
        )
        lbl_desc.setStyleSheet("color: #475569; font-size: 10px; line-height: 1.25;")
        header_layout.addWidget(lbl_desc)

        top_layout.addLayout(header_layout)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # License Info GroupBox
        mgr = license_guard.global_license_manager
        mgr.check_local_license()
        info = mgr.license_info or {}
        is_lic = mgr.is_licensed

        grp_lic = QGroupBox("สถานะลิขสิทธิ์และการลงทะเบียน (License Status)")
        lic_form = QFormLayout(grp_lic)
        lic_form.setSpacing(4)
        lic_form.setContentsMargins(10, 8, 10, 8)

        # Status
        if is_lic:
            lic_type = info.get("type", "lifetime").title()
            status_text = f"<span style='color: #16a34a; font-weight: bold;'>🟢 เปิดใช้งานแล้ว (Active — {lic_type})</span>"
        else:
            status_text = "<span style='color: #eab308; font-weight: bold;'>🟡 รุ่นทดลองใช้งานฟรี (14 วัน)</span>"
        lbl_stat_val = QLabel(status_text)
        lic_form.addRow("<b>สถานะโปรแกรม:</b>", lbl_stat_val)

        # Key
        key_str = info.get("key", "ยังไม่มีรหัสคีย์ (กรุณาลงทะเบียน)")
        key_box = QHBoxLayout()
        lbl_key_val = QLabel(f"<span style='font-family: Consolas; font-weight: bold; color: #0284c7; font-size: 11px;'>{key_str}</span>")
        key_box.addWidget(lbl_key_val)
        if is_lic and info.get("key"):
            btn_copy_key = QPushButton("📋 คัดลอก")
            btn_copy_key.setObjectName("btnSecondary")
            btn_copy_key.setFixedWidth(58)
            btn_copy_key.setStyleSheet("font-size: 10px; padding: 2px 6px; min-height: 20px;")
            btn_copy_key.clicked.connect(lambda: self.copy_text(key_str, "คัดลอกรหัสลิขสิทธิ์แล้ว"))
            key_box.addWidget(btn_copy_key)
        key_box.addStretch()
        lic_form.addRow("<b>รหัสคีย์ (License Key):</b>", key_box)

        # Owner
        owner_str = info.get("owner", "ผู้ใช้งานทั่วไป (Unregistered)")
        org_str = f" ({info.get('org')})" if info.get("org") else ""
        lbl_owner_val = QLabel(f"<span style='font-size: 10.5px;'>{owner_str}{org_str}</span>")
        lic_form.addRow("<b>ผู้ถือลิขสิทธิ์:</b>", lbl_owner_val)

        # HWID
        hwid_str = mgr.hwid
        hwid_box = QHBoxLayout()
        lbl_hwid_val = QLabel(f"<span style='font-family: Consolas; color: #475569; font-size: 10.5px;'>{hwid_str}</span>")
        hwid_box.addWidget(lbl_hwid_val)
        btn_copy_hwid = QPushButton("📋 คัดลอก")
        btn_copy_hwid.setObjectName("btnSecondary")
        btn_copy_hwid.setFixedWidth(58)
        btn_copy_hwid.setStyleSheet("font-size: 10px; padding: 2px 6px; min-height: 20px;")
        btn_copy_hwid.clicked.connect(lambda: self.copy_text(hwid_str, "คัดลอกรหัส HWID แล้ว"))
        hwid_box.addWidget(btn_copy_hwid)
        hwid_box.addStretch()
        lic_form.addRow("<b>รหัสเครื่องนี้ (HWID):</b>", hwid_box)

        # Expiry
        exp_ts = info.get("expires_at")
        if exp_ts and exp_ts > 0:
            import datetime
            exp_str = datetime.datetime.fromtimestamp(exp_ts).strftime("%d/%m/%Y")
        else:
            exp_str = "ตลอดชีพ (ไม่มีวันหมดอายุ)" if is_lic else "14 วันนับจากติดตั้ง"
        lbl_exp_val = QLabel(f"<span style='font-size: 10.5px;'>{exp_str}</span>")
        lic_form.addRow("<b>ระยะเวลาลิขสิทธิ์:</b>", lbl_exp_val)

        layout.addWidget(grp_lic)

        # Specifications Memo
        self.memo = QPlainTextEdit()
        self.memo.setReadOnly(True)
        self.memo.setFixedHeight(88)
        self.memo.setAccessibleName("คุณสมบัติและมาตรฐานระบบ SiamBraille")
        self.memo.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0b192c;
                color: #e2e8f0;
                font-family: 'Tahoma', 'Consolas';
                font-size: 10px;
                border: 1px solid #1e293b;
                border-radius: 4px;
                padding: 4px;
                line-height: 1.25;
            }
        """)
        memo_content = (
            "มาตรฐานและคุณสมบัติระบบ SiamBraille 1.0 (Core Specifications):\n"
            " • มาตรฐานอักษรเบรลล์ไทย พ.ศ. 2564 ฉบับสมบูรณ์ (คำควบกล้ำ อักษรนำ คำย่อ สระพิเศษ)\n"
            " • จัดหน้ากระดาษเบรลล์ 30 เซลล์ x 25 บรรทัด ล็อกระยะพิมพ์ขอบกระดาษ 100%\n"
            " • ระบบเลขหน้าอักษรเบรลล์ (#a, #b...) มุมบนขวาบรรทัดที่ 1 ทุกหน้าอัตโนมัติ\n"
            " • รองรับ Universal Accessibility เข้ากันได้กับ NVDA และ JAWS สมบูรณ์ 100%\n"
            " • สั่งพิมพ์ตรงสู่ Embosser (Index, Everest, Juliet, Romeo) และจำลองจุด SimBraille A4\n"
            " • ระบบลิขสิทธิ์ดิจิทัลผูกฮาร์ดแวร์ ทำงานแบบ Offline และ Cloud Sync ผ่าน Firebase"
        )
        self.memo.setPlainText(memo_content)
        layout.addWidget(self.memo)

        # Bottom Action Bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(6)

        btn_buy = QPushButton("💳 สั่งซื้อ License...")
        btn_buy.clicked.connect(self.open_buy)
        btn_bar.addWidget(btn_buy)

        btn_act = QPushButton("🔑 เปิดใช้งานรหัสคีย์...")
        btn_act.clicked.connect(self.open_activate)
        btn_bar.addWidget(btn_act)

        btn_update = QPushButton("🔄 ตรวจสอบการอัปเดต...")
        btn_update.setObjectName("btnSecondary")
        btn_update.clicked.connect(self.open_update)
        btn_bar.addWidget(btn_update)

        btn_bar.addStretch()

        btn_close = QPushButton("ปิด")
        btn_close.setObjectName("btnSecondary")
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_close)

        layout.addLayout(btn_bar)

    def copy_text(self, text: str, msg: str):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text)
        speak_nvda(msg)

    def open_buy(self):
        self.reject()
        dlg = LicensePurchaseDialog(self.parentWidget())
        dlg.exec()

    def open_activate(self):
        self.reject()
        dlg = LicenseActivationDialog(self.parentWidget())
        dlg.exec()

    def open_update(self):
        dlg = CheckUpdateDialog(self)
        dlg.exec()


class TBTWMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 1. Translation Engine
        self.engine_mode = "auto"
        self.translator = ThaiBrailleTranslator(grade=1, engine_mode="auto")
        self.thai_grade = 1       # 1 = Grade 1, 2 = Grade 2
        self.english_grade = 1
        self.current_filename = "c:\\noname.txt"
        self.line_length = 30
        self.page_length = 25
        self.total_page = 0
        
        # เซิร์ฟเวอร์พิมพ์ระยะไกลผ่านมือถือในวง LAN
        self.lan_server: Optional['LANCompanionServer'] = None

        # สร้าง Custom Tokenizer เพื่อรักษากลุ่มคำย่อระดับ 2 (CH78.tab, CH46.tab) ไม่ให้ถูกตัดแยกคำกลางคัน
        self.thai_tokenizer: Optional[Any] = None
        if pythainlp is not None:
            try:
                from pythainlp.tokenize import Tokenizer
                from pythainlp.util import dict_trie
                from pythainlp.corpus import thai_words
                custom_words = set(thai_words())
                if hasattr(self.translator, 'classic_ch78'):
                    custom_words.update(self.translator.classic_ch78.keys())
                if hasattr(self.translator, 'classic_ch46'):
                    custom_words.update(self.translator.classic_ch46.keys())
                self.thai_tokenizer = Tokenizer(custom_dict=dict_trie(custom_words), engine='newmm')
            except Exception:
                self.thai_tokenizer = None
        
        # โหลดค่าตั้งค่าหน้ากระดาษเดิมจาก SiamBraille.def
        try:
            def_path = get_resource_path("SiamBraille.def")
            if os.path.exists(def_path):
                import struct
                with open(def_path, 'rb') as f_def:
                    b_def = f_def.read()
                    if len(b_def) >= 8:
                        c_line, c_page = struct.unpack('<II', b_def[:8])
                        if 10 <= c_line <= 80:
                            self.line_length = c_line
                        if 5 <= c_page <= 50:
                            self.page_length = c_page
        except Exception:
            pass
        
        # Grade 2 selections
        self.g2_ch1_3 = True
        self.g2_ch4_6 = True
        self.g2_ch7_8 = True
        
        # Default Settings State
        self.page_number_location = "Top Right"
        self.printer_port = "Printer LPT1"
        self.printing_mode = "Double Side"
        self.page_advance = "No"
        
        # Load SimBraille Font if available
        self.simbrl_font_loaded = False
        simbrl_path = get_resource_path("SIMBRL.TTF")
        if os.path.exists(simbrl_path):
            fid = QFontDatabase.addApplicationFont(simbrl_path)
            if fid != -1:
                self.simbrl_font_loaded = True
                
        # Current UI Language: 'th' (Thai) or 'en' (English)
        self.current_lang = "th"
        
        # 2. Window Setup & Accessibility
        self.update_title()
        self.resize(1200, 750)
        self.setMinimumSize(640, 400)
        self.showMaximized()
        self.setAccessibleName("SiamBraille 1.0 โปรแกรมแปลเอกสารเป็นอักษรเบรลล์")
        self.setAccessibleDescription(
            "หน้าต่างหลักของโปรแกรม มีกล่องข้อความภาษาไทยปกติทางซ้าย และกล่องอักษรเบรลล์ทางขวา "
            "กด F6 เพื่อสลับระหว่างสองกล่องข้อความ กด Ctrl+T เพื่อแปลเป็นอักษรเบรลล์"
        )
        
        app_icon = get_main_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
            
        # Menu references
        self.menu_file = None
        self.menu_print = None
        self.menu_edit = None
        self.menu_default = None
        self.menu_page_num = None
        self.menu_printer_port = None
        self.menu_print_mode = None
        self.menu_page_adv = None
        self.menu_set_font = None
        self.menu_set_kb = None
        self.menu_th_level = None
        self.menu_en_level = None
        self.menu_tools = None
        self.menu_help = None

        self.setup_ui()
        self.setup_menubar()
        self.setup_toolbar()
        self.setup_statusbar()
        self.retranslate_ui()

        # ตรวจสอบสิทธิ์ทดลองใช้เมื่อเปิดโปรแกรม หากหมดอายุให้เด้งหน้าแจ้งเตือนและชำระเงิน
        mgr = license_guard.global_license_manager
        if not mgr.is_licensed and getattr(mgr, "is_trial_expired", False):
            QTimer.singleShot(600, self.show_trial_expired_dialog)
        elif not mgr.is_licensed and getattr(mgr, "is_trial", False):
            rem = getattr(mgr, "trial_days_remaining", 14)
            day_num = getattr(mgr, "trial_day_number", 1)
            QTimer.singleShot(700, lambda: speak_nvda(f"ยินดีต้อนรับสู่ SiamBraille 1.0 สิทธิ์ทดลองใช้ฟรีวันที่ {day_num} จาก 14 วัน เหลืออีก {rem} วัน"))
        
    def update_title(self):
        mgr = license_guard.global_license_manager
        is_th = getattr(self, "current_lang", "th") == "th"
        if mgr.is_licensed:
            lic_tag = ""
        elif getattr(mgr, "is_trial", False) and not getattr(mgr, "is_trial_expired", False):
            rem = getattr(mgr, "trial_days_remaining", 14)
            day_num = getattr(mgr, "trial_day_number", 1)
            lic_tag = f" [ทดลองใช้วันที่ {day_num}/14 (เหลือ {rem} วัน)]" if is_th else f" [Trial Day {day_num}/14 ({rem} days left)]"
        else:
            lic_tag = " [หมดอายุทดลองใช้]" if is_th else " [Trial Expired]"
        self.setWindowTitle(f"SiamBraille 1.0{lic_tag} - ({self.current_filename})")

    def setup_ui(self):
        central_widget = QWidget(self)
        central_widget.setStyleSheet("background-color: #f0f0f0;")
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 2, 4, 2)
        main_layout.setSpacing(2)
        
        # Splitter between Left Editor and Right Editor
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setAccessibleName("แถบแบ่งหน้าต่างแก้ไขซ้ายขวา")
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #f0f0f0;
                width: 4px;
            }
        """)
        
        editor_style = """
            QPlainTextEdit {
                background-color: #ffffff;
                color: #000000;
                border: 2px solid;
                border-color: #808080 #ffffff #ffffff #808080;
                border-radius: 0px;
                padding: 2px;
                selection-background-color: #000080;
                selection-color: #ffffff;
            }
            QPlainTextEdit:focus {
                border: 2px solid;
                border-color: #808080 #ffffff #ffffff #808080;
            }
        """
        
        # --- Left Panel: Normal Font (RichEdit1 in Delphi) ---
        self.txt_normal = QPlainTextEdit()
        self.txt_normal.setFont(QFont("AngsanaUPC", 16) if "AngsanaUPC" in QFontDatabase.families() else QFont("Tahoma", 11))
        self.txt_normal.setStyleSheet(editor_style)
        self.txt_normal.setAccessibleName("ข้อมูลเดิม กล่องข้อความปกติ Normal Font")
        self.txt_normal.setAccessibleDescription(
            "กล่องข้อความสำหรับพิมพ์หรือวางข้อความภาษาไทยและอังกฤษต้นฉบับ "
            "กด F6 เพื่อสลับไปยังกล่องอักษรเบรลล์ กด Ctrl+T เพื่อสั่งแปล"
        )
        self.txt_normal.setWhatsThis("กล่องข้อความภาษาไทยปกติ (Normal Font) สำหรับพิมพ์หรือเปิดไฟล์ต้นฉบับ")
        self.txt_normal.textChanged.connect(self.on_text_changed)
        self.txt_normal.installEventFilter(self)
        
        # Keep txt_braille_thai instantiated in background so any legacy references work seamlessly
        self.txt_braille_thai = QPlainTextEdit()
        self.txt_braille_thai.hide()

        # --- Right Panel: Braille Font dots (RichEdit2 in Delphi) ---
        self.txt_braille = QPlainTextEdit()
        if self.simbrl_font_loaded:
            self.txt_braille.setFont(QFont("SimBraille", 18))
        else:
            self.txt_braille.setFont(QFont("Courier New", 13))
            
        self.txt_braille.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.txt_braille.setStyleSheet(editor_style)
        self.txt_braille.setAccessibleName("ข้อมูลแปล กล่องข้อความอักษรเบรลล์ Braille Font")
        self.txt_braille.setAccessibleDescription(
            "กล่องข้อความแสดงผลอักษรเบรลล์ที่แปลแล้ว รองรับฟอนต์ SimBraille กำหนดขอบเขต 30 เซลล์ต่อบรรทัด "
            "กด F6 เพื่อสลับกลับไปยังกล่องข้อมูลเดิมภาษาไทยปกติ"
        )
        self.txt_braille.setWhatsThis("กล่องแสดงผลอักษรเบรลล์ (Braille Font) สำหรับตรวจทานและส่งออกเครื่องพิมพ์เบรลล์")
        self.txt_braille.installEventFilter(self)
        
        # Set expanding size policies to allow editors to stretch smoothly with the window
        self.txt_normal.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.txt_braille.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 2 Main Panels: Left (Thai Original) and Right (Braille Dots)
        self.splitter.addWidget(self.txt_normal)
        self.splitter.addWidget(self.txt_braille)
        self.splitter.setSizes([512, 512])
        
        # ตั้งค่า Tab Order ให้เป็นธรรมชาติ
        QWidget.setTabOrder(self.txt_normal, self.txt_braille)
        
        # main_layout stretch factor 1: ให้พื้นที่ขยายตัวทั้งหมดแก่ splitter (Align = alClient)
        main_layout.addWidget(self.splitter, 1)
        
        # Label ข้อความสถานะสำหรับเก็บข้อความและ Screen Reader (ซ่อนไม่ให้กินพื้นที่แนวตั้ง ให้ชิด status bar เหมือน Delphi)
        self.lbl_status_msg = QLabel("โปรแกรมแปลเอกสารเป็นอักษรเบรลล์ (SiamBraille 1.0 Professional)", self)
        self.lbl_status_msg.hide()

    def set_status_message(self, msg: str):
        """อัปเดตข้อความสถานะ รองรับทั้งแถบสถานะด้านล่างและ Screen Reader (NVDA/JAWS/ตาทิพย์)"""
        self.lbl_status_msg.setText(msg)
        self.lbl_status_msg.setAccessibleName(f"สถานะ: {msg}")
        sb = self.statusBar()
        if sb is not None:
            sb.showMessage(msg, 3500)
        speak_nvda(msg)

    def eventFilter(self, watched, event):
        """ตรวจจับ focus เปลี่ยนระหว่างกล่องข้อความซ้าย/ขวา เพื่ออัปเดตแถบสถานะและแจ้ง Screen Reader ชัดเจน"""
        if event.type() == QEvent.Type.FocusIn:
            is_th = getattr(self, 'current_lang', 'th') == 'th'
            if watched == self.txt_normal:
                if hasattr(self, 'lbl_report') and self.lbl_report is not None:
                    self.lbl_report.setText("ข้อมูลเดิม" if is_th else "Original Text")
                self.set_status_message("เข้าสู่กล่องข้อความข้อมูลเดิม (ภาษาไทยปกติ)" if is_th else "Focus in Original Text box")
            elif watched == self.txt_braille:
                if hasattr(self, 'lbl_report') and self.lbl_report is not None:
                    self.lbl_report.setText("ข้อมูลไฟล์ที่แปลแล้ว" if is_th else "Translated File")
                self.set_status_message("เข้าสู่กล่องข้อความอักษรเบรลล์" if is_th else "Focus in Braille Output box")
        return super().eventFilter(watched, event)

    def setup_menubar(self):
        menubar = self.menuBar()
        if not menubar:
            return
            
        menubar.setAccessibleName("แถบเมนูหลัก Main Menu")
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #f0f0f0;
                color: #000000;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
            }
            QMenuBar::item:selected {
                background-color: #000080;
                color: #ffffff;
            }
            QMenu {
                background-color: #ffffff;
                color: #000000;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
                border: 1px solid #808080;
            }
            QMenu::item:selected {
                background-color: #000080;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #a0a0a0;
                margin: 2px 0px;
            }
        """)
        
        # ---------------------------------------------------------
        # 1. File Menu (Alt+F)
        # ---------------------------------------------------------
        self.menu_file = menubar.addMenu("&File")
        if self.menu_file:
            self.menu_file.setStatusTip("เมนูไฟล์ (Alt+F)")
            
            self.act_new = QAction("&New\tCtrl+N", self)
            self.act_new.setIcon(get_app_icon("ui_icon_new.png"))
            self.act_new.setShortcut(QKeySequence("Ctrl+N"))
            self.act_new.setStatusTip("เปิดไฟล์ใหม่ (Ctrl+N)")
            self.act_new.setWhatsThis("ล้างข้อมูลปัจจุบันและเปิดเอกสารใหม่ คีย์ลัด Ctrl+N")
            self.act_new.triggered.connect(self.file_new)
            self.menu_file.addAction(self.act_new)
            
            self.act_open = QAction("&Open...\tCtrl+O", self)
            self.act_open.setIcon(get_app_icon("ui_icon_open.png"))
            self.act_open.setShortcut(QKeySequence("Ctrl+O"))
            self.act_open.setStatusTip("เปิดไฟล์เก่า (Ctrl+O)")
            self.act_open.setWhatsThis("เลือกและเปิดไฟล์ข้อความที่มีอยู่แล้ว คีย์ลัด Ctrl+O")
            self.act_open.triggered.connect(self.file_open)
            self.menu_file.addAction(self.act_open)
            
            self.act_translate = QAction("&Translate\tCtrl+T", self)
            self.act_translate.setIcon(get_app_icon("glyph_translate.png"))
            self.act_translate.setShortcut(QKeySequence("Ctrl+T"))
            self.act_translate.setStatusTip("แปลเป็นเบรลล์ (Ctrl+T)")
            self.act_translate.setWhatsThis("แปลข้อความภาษาไทยในกล่องซ้ายเป็นอักษรเบรลล์ในกล่องขวา คีย์ลัด Ctrl+T")
            self.act_translate.triggered.connect(self.action_translate)
            self.menu_file.addAction(self.act_translate)
            
            # Print Submenu
            self.menu_print = self.menu_file.addMenu("&Print")
            if not self.menu_print:
                self.menu_print = QMenu("&Print", self.menu_file)
                self.menu_file.addMenu(self.menu_print)
            if self.menu_print:
                self.menu_print.setStatusTip("ส่งไปเครื่องพิมพ์ปกติ")
                
                self.act_print_reg = QAction("&Regular text", self)
                self.act_print_reg.setStatusTip("พิมพ์อักษรปกติ")
                self.act_print_reg.triggered.connect(self.print_regular)
                self.menu_print.addAction(self.act_print_reg)
                
                self.act_print_dots = QAction("&Braille dots", self)
                self.act_print_dots.setStatusTip("พิมพ์เป็นจุดเบรลล์")
                self.act_print_dots.triggered.connect(self.print_dots)
                self.menu_print.addAction(self.act_print_dots)
            
            self.act_braille_print = QAction("&Braille...\tCtrl+B", self)
            self.act_braille_print.setShortcut(QKeySequence("Ctrl+B"))
            self.act_braille_print.setStatusTip("ส่งไปเครื่องพิมพ์เบรลล์ (Ctrl+B)")
            self.act_braille_print.setWhatsThis("บันทึกไฟล์เป็นนามสกุล .BRF สำหรับนำไปปั๊มลงเครื่องพิมพ์เบรลล์ คีย์ลัด Ctrl+B")
            self.act_braille_print.triggered.connect(self.action_print_braille)
            self.menu_file.addAction(self.act_braille_print)
            
            self.menu_file.addSeparator()
            
            self.act_print_setup = QAction("Print &Setup...\tCtrl+P", self)
            self.act_print_setup.setShortcut(QKeySequence("Ctrl+P"))
            self.act_print_setup.setStatusTip("ตั้งค่าหน้ากระดาษและเครื่องพิมพ์ (Ctrl+P)")
            self.act_print_setup.setWhatsThis("กำหนดจำนวนเซลล์ต่อบรรทัดและจำนวนบรรทัดต่อหน้า คีย์ลัด Ctrl+P")
            self.act_print_setup.triggered.connect(self.open_page_setting)
            self.menu_file.addAction(self.act_print_setup)
            
            self.act_save = QAction("&Save\tCtrl+S", self)
            self.act_save.setIcon(get_app_icon("ui_icon_save.png"))
            self.act_save.setShortcut(QKeySequence("Ctrl+S"))
            self.act_save.setStatusTip("บันทึก (Ctrl+S)")
            self.act_save.setWhatsThis("บันทึกเอกสารปัจจุบัน คีย์ลัด Ctrl+S")
            self.act_save.triggered.connect(self.file_save)
            self.menu_file.addAction(self.act_save)
            
            self.act_save_as = QAction("Save &As...", self)
            self.act_save_as.setStatusTip("บันทึกเป็นไฟล์ใหม่")
            self.act_save_as.setWhatsThis("บันทึกเอกสารเป็นไฟล์ใหม่ด้วยชื่อหรือตำแหน่งอื่น")
            self.act_save_as.triggered.connect(self.file_save_as)
            self.menu_file.addAction(self.act_save_as)
            
            self.act_save_all = QAction("Save Al&l\tCtrl+A", self)
            self.act_save_all.setStatusTip("บันทึกไฟล์ทั้งหมด (Ctrl+A)")
            self.act_save_all.triggered.connect(self.file_save)
            self.menu_file.addAction(self.act_save_all)
            
            self.menu_file.addSeparator()
            
            self.act_exit = QAction("E&xit\tAlt+F4", self)
            self.act_exit.setStatusTip("ออกจากโปรแกรม")
            self.act_exit.triggered.connect(self.close)
            self.menu_file.addAction(self.act_exit)

        # ---------------------------------------------------------
        # 2. Edit Menu (Alt+E)
        # ---------------------------------------------------------
        self.menu_edit = menubar.addMenu("&Edit")
        if self.menu_edit:
            self.menu_edit.setStatusTip("เมนูแก้ไข (Alt+E)")
            
            self.act_cut = QAction("Cu&t\tCtrl+X", self)
            self.act_cut.setIcon(get_app_icon("ui_icon_cut.png"))
            self.act_cut.setShortcut(QKeySequence("Ctrl+X"))
            self.act_cut.setStatusTip("ตัดข้อความ (Ctrl+X)")
            self.act_cut.setWhatsThis("ตัดข้อความที่เลือกไปยังคลิปบอร์ด คีย์ลัด Ctrl+X")
            self.act_cut.triggered.connect(self.txt_normal.cut)
            self.menu_edit.addAction(self.act_cut)
            
            self.act_copy = QAction("&Copy\tCtrl+C", self)
            self.act_copy.setIcon(get_app_icon("ui_icon_copy.png"))
            self.act_copy.setShortcut(QKeySequence("Ctrl+C"))
            self.act_copy.setStatusTip("คัดลอกข้อความ (Ctrl+C)")
            self.act_copy.setWhatsThis("คัดลอกข้อความที่เลือกไปยังคลิปบอร์ด คีย์ลัด Ctrl+C")
            self.act_copy.triggered.connect(self.txt_normal.copy)
            self.menu_edit.addAction(self.act_copy)
            
            self.act_paste = QAction("&Paste\tCtrl+V", self)
            self.act_paste.setIcon(get_app_icon("ui_icon_paste.png"))
            self.act_paste.setShortcut(QKeySequence("Ctrl+V"))
            self.act_paste.setStatusTip("วางข้อความ (Ctrl+V)")
            self.act_paste.setWhatsThis("วางข้อความจากคลิปบอร์ดลงในตำแหน่งเคอร์เซอร์ คีย์ลัด Ctrl+V")
            self.act_paste.triggered.connect(self.txt_normal.paste)
            self.menu_edit.addAction(self.act_paste)
            
            self.menu_edit.addSeparator()
            
            self.act_find = QAction("&Find...\tCtrl+F", self)
            self.act_find.setIcon(get_app_icon("ui_icon_find.png"))
            self.act_find.setShortcut(QKeySequence("Ctrl+F"))
            self.act_find.setStatusTip("ค้นหาข้อความ (Ctrl+F)")
            self.act_find.triggered.connect(self.action_find)
            self.menu_edit.addAction(self.act_find)
            
            self.act_replace = QAction("&Replace...\tCtrl+R", self)
            self.act_replace.setIcon(get_app_icon("ui_icon_replace.png"))
            self.act_replace.setShortcut(QKeySequence("Ctrl+R"))
            self.act_replace.setStatusTip("แทนที่ข้อความ (Ctrl+R)")
            self.act_replace.triggered.connect(self.action_replace)
            self.menu_edit.addAction(self.act_replace)
            
            self.menu_edit.addSeparator()
            
            self.act_font = QAction("&Font...", self)
            self.act_font.setStatusTip("ตั้งแบบอักษรปกติ")
            self.act_font.triggered.connect(self.choose_font)
            self.menu_edit.addAction(self.act_font)
            
            self.act_wrap = QAction("&Word Wrap", self)
            self.act_wrap.setCheckable(True)
            self.act_wrap.setChecked(False)
            self.act_wrap.setStatusTip("ตัดคำขึ้นบรรทัดใหม่อัตโนมัติ")
            self.act_wrap.toggled.connect(self.toggle_wordwrap)
            self.menu_edit.addAction(self.act_wrap)
            
            self.act_fullscreen = QAction("Full &Screen\tF11", self)
            self.act_fullscreen.setShortcut(QKeySequence("F11"))
            self.act_fullscreen.setStatusTip("แสดงผลเต็มจอ (F11)")
            self.act_fullscreen.triggered.connect(self.toggle_fullscreen)
            self.menu_edit.addAction(self.act_fullscreen)
            
            self.act_switch_win = QAction("Switch &Window\tF6", self)
            self.act_switch_win.setShortcut(QKeySequence("F6"))
            self.act_switch_win.setStatusTip("สลับหน้าต่างข้อความ (F6)")
            self.act_switch_win.setWhatsThis("กด F6 เพื่อสลับระหว่างกล่องข้อความภาษาไทยปกติ และกล่องอักษรเบรลล์")
            self.act_switch_win.triggered.connect(self.switch_window_focus)
            self.menu_edit.addAction(self.act_switch_win)

        # ---------------------------------------------------------
        # 3. Default Menu (Alt+D)
        # ---------------------------------------------------------
        self.menu_default = menubar.addMenu("&Default")
        if self.menu_default:
            self.menu_default.setStatusTip("เมนูค่าเริ่มต้น (Alt+D)")
            
            self.act_braille_page = QAction("&Braille Page...", self)
            self.act_braille_page.setStatusTip("ตั้งค่าหน้ากระดาษเบรลล์")
            self.act_braille_page.triggered.connect(self.open_page_setting)
            self.menu_default.addAction(self.act_braille_page)
            
            # Page Number Location Submenu
            self.menu_page_num = self.menu_default.addMenu("&Page Number Location")
            if not self.menu_page_num:
                self.menu_page_num = QMenu("&Page Number Location", self.menu_default)
                self.menu_default.addMenu(self.menu_page_num)
            if self.menu_page_num:
                self.group_page_num = QActionGroup(self)
                self.group_page_num.setExclusive(True)
                
                self.act_pn_tl = QAction("Top &Left", self)
                self.act_pn_tl.setCheckable(True)
                self.act_pn_tr = QAction("Top &Right selected", self)
                self.act_pn_tr.setCheckable(True)
                self.act_pn_tr.setChecked(True)
                self.act_pn_bl = QAction("Bottom L&eft", self)
                self.act_pn_bl.setCheckable(True)
                self.act_pn_br = QAction("Bottom R&ight", self)
                self.act_pn_br.setCheckable(True)
                
                for act, name in [(self.act_pn_tl, "Top Left"), (self.act_pn_tr, "Top Right"), (self.act_pn_bl, "Bottom Left"), (self.act_pn_br, "Bottom Right")]:
                    self.group_page_num.addAction(act)
                    self.menu_page_num.addAction(act)
                    act.triggered.connect(lambda ch, a=act, n=name: self.update_check_label(self.group_page_num, a, n))
                
            # Printer Port Submenu
            self.menu_printer_port = self.menu_default.addMenu("Printer &Port")
            if not self.menu_printer_port:
                self.menu_printer_port = QMenu("Printer &Port", self.menu_default)
                self.menu_default.addMenu(self.menu_printer_port)
            if self.menu_printer_port:
                self.group_port = QActionGroup(self)
                self.group_port.setExclusive(True)
                
                self.act_port_c1 = QAction("Serial Com&1", self)
                self.act_port_c1.setCheckable(True)
                self.act_port_c2 = QAction("Serial Com&2", self)
                self.act_port_c2.setCheckable(True)
                self.act_port_l1 = QAction("Printer LP&T1 selected", self)
                self.act_port_l1.setCheckable(True)
                self.act_port_l1.setChecked(True)
                self.act_port_l2 = QAction("Printer LPT&2", self)
                self.act_port_l2.setCheckable(True)
                
                for act, name in [(self.act_port_c1, "Serial Com1"), (self.act_port_c2, "Serial Com2"), (self.act_port_l1, "Printer LPT1"), (self.act_port_l2, "Printer LPT2")]:
                    self.group_port.addAction(act)
                    self.menu_printer_port.addAction(act)
                    act.triggered.connect(lambda ch, a=act, n=name: self.update_check_label(self.group_port, a, n))
                
            # Printing Mode Submenu
            self.menu_print_mode = self.menu_default.addMenu("Printing &Mode")
            if not self.menu_print_mode:
                self.menu_print_mode = QMenu("Printing &Mode", self.menu_default)
                self.menu_default.addMenu(self.menu_print_mode)
            if self.menu_print_mode:
                self.group_pmode = QActionGroup(self)
                self.group_pmode.setExclusive(True)
                
                self.act_pm_s = QAction("&Single Side", self)
                self.act_pm_s.setCheckable(True)
                self.act_pm_d = QAction("&Double Side selected", self)
                self.act_pm_d.setCheckable(True)
                self.act_pm_d.setChecked(True)
                
                for act, name in [(self.act_pm_s, "Single Side"), (self.act_pm_d, "Double Side")]:
                    self.group_pmode.addAction(act)
                    self.menu_print_mode.addAction(act)
                    act.triggered.connect(lambda ch, a=act, n=name: self.update_check_label(self.group_pmode, a, n))
                
            # Page Advance Submenu
            self.menu_page_adv = self.menu_default.addMenu("Page &Advance")
            if not self.menu_page_adv:
                self.menu_page_adv = QMenu("Page &Advance", self.menu_default)
                self.menu_default.addMenu(self.menu_page_adv)
            if self.menu_page_adv:
                self.group_padv = QActionGroup(self)
                self.group_padv.setExclusive(True)
                
                self.act_pa_y = QAction("&Yes", self)
                self.act_pa_y.setCheckable(True)
                self.act_pa_n = QAction("&No selected", self)
                self.act_pa_n.setCheckable(True)
                self.act_pa_n.setChecked(True)
                
                for act, name in [(self.act_pa_y, "Yes"), (self.act_pa_n, "No")]:
                    self.group_padv.addAction(act)
                    self.menu_page_adv.addAction(act)
                    act.triggered.connect(lambda ch, a=act, n=name: self.update_check_label(self.group_padv, a, n))
                
            # Set Font Submenu
            self.menu_set_font = self.menu_default.addMenu("Set &Font")
            if not self.menu_set_font:
                self.menu_set_font = QMenu("Set &Font", self.menu_default)
                self.menu_default.addMenu(self.menu_set_font)
            if self.menu_set_font:
                self.group_font = QActionGroup(self)
                self.group_font.setExclusive(True)
                
                self.act_font_term = QAction("&Terminal font for the blind", self)
                self.act_font_term.setCheckable(True)
                self.act_font_sans = QAction("&Microsoft Sans Serif font for the sighted selected", self)
                self.act_font_sans.setCheckable(True)
                self.act_font_sans.setChecked(True)
                
                for act, name in [(self.act_font_term, "Terminal font for the blind"), (self.act_font_sans, "Microsoft Sans Serif font for the sighted")]:
                    self.group_font.addAction(act)
                    self.menu_set_font.addAction(act)
                    act.triggered.connect(lambda ch, a=act, n=name: self.update_check_label(self.group_font, a, n))
                
            # Set Keyboard Submenu
            self.menu_set_kb = self.menu_default.addMenu("Set &Keyboard")
            if not self.menu_set_kb:
                self.menu_set_kb = QMenu("Set &Keyboard", self.menu_default)
                self.menu_default.addMenu(self.menu_set_kb)
            if self.menu_set_kb:
                self.group_kb = QActionGroup(self)
                self.group_kb.setExclusive(True)
                
                self.act_kb_th = QAction("&Thai Keyboard selected", self)
                self.act_kb_th.setCheckable(True)
                self.act_kb_th.setChecked(True)
                self.act_kb_en = QAction("&English Keyboard", self)
                self.act_kb_en.setCheckable(True)
                
                for act, name in [(self.act_kb_th, "Thai Keyboard"), (self.act_kb_en, "English Keyboard")]:
                    self.group_kb.addAction(act)
                    self.menu_set_kb.addAction(act)
                    act.triggered.connect(lambda ch, a=act, n=name: self.update_check_label(self.group_kb, a, n))
                
            # Thai Braille Level Submenu
            self.menu_th_level = self.menu_default.addMenu("&Thai Braille Level")
            if not self.menu_th_level:
                self.menu_th_level = QMenu("&Thai Braille Level", self.menu_default)
                self.menu_default.addMenu(self.menu_th_level)
            if self.menu_th_level:
                self.group_th_lvl = QActionGroup(self)
                self.group_th_lvl.setExclusive(True)
                
                self.act_th_g1 = QAction("&Grade 1 with some short form selected", self)
                self.act_th_g1.setCheckable(True)
                self.act_th_g1.setChecked(True)
                self.act_th_g2 = QAction("Grade &2 with contractions", self)
                self.act_th_g2.setCheckable(True)
                
                self.group_th_lvl.addAction(self.act_th_g1)
                self.group_th_lvl.addAction(self.act_th_g2)
                self.menu_th_level.addAction(self.act_th_g1)
                self.menu_th_level.addAction(self.act_th_g2)
                
                self.act_th_g1.triggered.connect(lambda: self.set_thai_grade(1))
                self.act_th_g2.triggered.connect(lambda: self.open_grade2_dialog())
                
            # English Braille Level Submenu
            self.menu_en_level = self.menu_default.addMenu("&English Braille Level")
            if not self.menu_en_level:
                self.menu_en_level = QMenu("&English Braille Level", self.menu_default)
                self.menu_default.addMenu(self.menu_en_level)
            if self.menu_en_level:
                self.group_en_lvl = QActionGroup(self)
                self.group_en_lvl.setExclusive(True)
                
                self.act_en_g1 = QAction("Grade &1 with no contractions selected", self)
                self.act_en_g1.setCheckable(True)
                self.act_en_g1.setChecked(True)
                self.act_en_g2 = QAction("Grade &2 with contractions", self)
                self.act_en_g2.setCheckable(True)
                
                self.group_en_lvl.addAction(self.act_en_g1)
                self.group_en_lvl.addAction(self.act_en_g2)
                self.menu_en_level.addAction(self.act_en_g1)
                self.menu_en_level.addAction(self.act_en_g2)
                
                self.act_en_g1.triggered.connect(lambda: self.set_en_grade(1))
                self.act_en_g2.triggered.connect(lambda: self.set_en_grade(2))

        # ---------------------------------------------------------
        # 4. Tools Menu (Alt+T)
        # ---------------------------------------------------------
        self.menu_tools = menubar.addMenu("&Tools")
        if self.menu_tools:
            self.act_remote_input = QAction("&Remote Mobile Input (LAN)...\tCtrl+Shift+W", self)
            self.act_remote_input.setShortcut(QKeySequence("Ctrl+Shift+W"))
            self.act_remote_input.setWhatsThis("พิมพ์ข้อความผ่านมือถือในวง LAN เดียวกัน รองรับการพิมพ์ด้วยเสียงและแป้นสัมผัส 6 จุด คีย์ลัด Ctrl+Shift+W")
            self.act_remote_input.setStatusTip("พิมพ์ผ่านมือถือในวง LAN เดียวกัน (Ctrl+Shift+W)")
            self.act_remote_input.triggered.connect(self.open_remote_input_dialog)
            self.menu_tools.addAction(self.act_remote_input)

            self.act_tactile = QAction("&Tactile Graphics from Image...\tCtrl+G", self)
            self.act_tactile.setShortcut(QKeySequence("Ctrl+G"))
            self.act_tactile.setWhatsThis("แปลงภาพเป็นสื่อจุดนูนสัมผัส Image to Braille Tactile Graphics")
            self.act_tactile.setStatusTip("แปลงภาพเป็นสื่อจุดสัมผัสเบรลล์ (Ctrl+G)")
            self.act_tactile.triggered.connect(self.open_tactile_graphics_dialog)
            self.menu_tools.addAction(self.act_tactile)

            self.act_dot_converter = QAction("แปลงเป็นเลขจุดเบรลล์ (ก→1245, a→1, b→12)...\tCtrl+Shift+D", self)
            self.act_dot_converter.setShortcut(QKeySequence("Ctrl+Shift+D"))
            self.act_dot_converter.setWhatsThis("แปลงข้อความภาษาไทย/อังกฤษเป็นเลขตำแหน่งจุดเบรลล์ 1 ถึง 6 เช่น ก=1245, a=1, b=12 คีย์ลัด Ctrl+Shift+D")
            self.act_dot_converter.setStatusTip("แปลงข้อความเป็นชุดเลขจุดเบรลล์ 1-6 (Ctrl+Shift+D)")
            self.act_dot_converter.triggered.connect(self.open_dot_converter_dialog)
            self.menu_tools.addAction(self.act_dot_converter)

            self.act_math_to_braille = QAction("แปลงสูตรคณิตศาสตร์เป็นเบรลล์ (Math to Braille)...\tCtrl+Shift+M", self)
            self.act_math_to_braille.setShortcut(QKeySequence("Ctrl+Shift+M"))
            self.act_math_to_braille.setWhatsThis("แปลงสูตรคณิตศาสตร์และสมการวิทยาศาสตร์ (LaTeX / MathML) เป็นอักษรเบรลล์ Nemeth Code หรือ UEB Math คีย์ลัด Ctrl+Shift+M")
            self.act_math_to_braille.setStatusTip("แปลงสูตรคณิตศาสตร์เป็นอักษรเบรลล์ Nemeth/UEB (Ctrl+Shift+M)")
            self.act_math_to_braille.triggered.connect(self.open_math_to_braille_dialog)
            self.menu_tools.addAction(self.act_math_to_braille)

        # ---------------------------------------------------------
        # 5. Help Menu (Alt+H)
        # ---------------------------------------------------------
        self.menu_help = menubar.addMenu("&Help")
        if self.menu_help:
            self.act_help_doc = QAction("&Help\tF1", self)
            self.act_help_doc.setIcon(get_app_icon("ui_icon_help.png"))
            self.act_help_doc.setShortcut(QKeySequence("F1"))
            self.act_help_doc.setStatusTip("วิธีการใช้โปรแกรม (F1)")
            self.act_help_doc.setWhatsThis("เปิดคำแนะนำการใช้งานโปรแกรมและคีย์ลัด คีย์ลัด F1")
            self.act_help_doc.triggered.connect(self.show_help)
            self.menu_help.addAction(self.act_help_doc)
            
            self.act_switch_lang = QAction("&Language Switcher\tCtrl+L", self)
            self.act_switch_lang.setShortcut(QKeySequence("Ctrl+L"))
            self.act_switch_lang.setStatusTip("สลับภาษา (Ctrl+L)")
            self.act_switch_lang.triggered.connect(self.switch_language)
            self.menu_help.addAction(self.act_switch_lang)
            
            self.menu_help.addSeparator()
            
            self.act_buy_lic = QAction("สั่งซื้อลิขสิทธิ์...", self)
            self.act_buy_lic.setStatusTip("สั่งซื้อลิขสิทธิ์ SiamBraille 1.0")
            self.act_buy_lic.triggered.connect(self.show_buy_license)
            self.menu_help.addAction(self.act_buy_lic)

            self.act_activate_lic = QAction("เปิดใช้งานรหัสลิขสิทธิ์...", self)
            self.act_activate_lic.setStatusTip("กรอกรหัส License Key เพื่อเปิดใช้งานโปรแกรม")
            self.act_activate_lic.triggered.connect(self.show_activate_license)
            self.menu_help.addAction(self.act_activate_lic)

            self.act_check_update = QAction("ตรวจสอบการอัปเดต...", self)
            self.act_check_update.setStatusTip("ตรวจสอบเวอร์ชันล่าสุดและแพตช์แก้ไข")
            self.act_check_update.triggered.connect(self.show_check_update)
            self.menu_help.addAction(self.act_check_update)

            self.menu_help.addSeparator()
            
            self.act_about = QAction("เกี่ยวกับโปรแกรม...", self)
            self.act_about.setStatusTip("เกี่ยวกับโปรแกรม SiamBraille และสถานะลิขสิทธิ์")
            self.act_about.triggered.connect(self.show_about)
            self.menu_help.addAction(self.act_about)
            
            self.act_contact = QAction("ข้อมูลติดต่อและบริการ...", self)
            self.act_contact.setStatusTip("ข้อมูลติดต่อทีมพัฒนา SiamBraille")
            self.act_contact.triggered.connect(self.show_contact)
            self.menu_help.addAction(self.act_contact)

    def update_check_label(self, group: QActionGroup, selected_action: QAction, base_name: str):
        is_th = getattr(self, "current_lang", "th") == "th"
        suffix = " (เลือก)" if is_th else " selected"
        for act in group.actions():
            clean = act.text().replace(" selected", "").replace(" (เลือก)", "")
            if act == selected_action:
                act.setText(f"{clean}{suffix}")
            else:
                act.setText(clean)

    def set_thai_grade(self, g: int):
        self.thai_grade = g
        self.translator.grade = g
        is_th = getattr(self, "current_lang", "th") == "th"
        sel = " (เลือก)" if is_th else " selected"
        g1_base = "ระดับ 1 พร้อมคำย่อพื้นฐาน" if is_th else "&Grade 1 with some short form"
        g2_base = "ระดับ 2 มีคำย่อ" if is_th else "Grade &2 with contractions"
        if g == 1:
            self.act_th_g1.setText(f"{g1_base}{sel}")
            self.act_th_g2.setText(g2_base)
            msg = "เลือกระดับการแปลอักษรเบรลล์ภาษาไทย ระดับ 1 แล้ว" if is_th else "Thai Braille Grade 1 selected"
        else:
            self.act_th_g1.setText(g1_base)
            self.act_th_g2.setText(f"{g2_base}{sel}")
            msg = "เลือกระดับการแปลอักษรเบรลล์ภาษาไทย ระดับ 2 (มีคำย่อ) แล้ว" if is_th else "Thai Braille Grade 2 selected"
        self.set_status_message(msg)
        if self.txt_normal.toPlainText().strip():
            self.action_translate()

    def open_grade2_dialog(self):
        dlg = Grade2SettingDialog(self, self.g2_ch1_3, self.g2_ch4_6, self.g2_ch7_8)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.g2_ch1_3, self.g2_ch4_6, self.g2_ch7_8 = dlg.get_settings()
            self.set_thai_grade(2)

    def set_en_grade(self, g: int):
        self.english_grade = g
        is_th = getattr(self, "current_lang", "th") == "th"
        sel = " (เลือก)" if is_th else " selected"
        g1_base = "ระดับ 1 ไม่มีคำย่อ" if is_th else "Grade &1 with no contractions"
        g2_base = "ระดับ 2 มีคำย่อ" if is_th else "Grade &2 with contractions"
        if g == 1:
            self.act_en_g1.setText(f"{g1_base}{sel}")
            self.act_en_g2.setText(g2_base)
            msg = "เลือกระดับการแปลภาษาเบรลล์อังกฤษ ระดับ 1 แล้ว" if is_th else "English Braille Grade 1 selected"
        else:
            self.act_en_g1.setText(g1_base)
            self.act_en_g2.setText(f"{g2_base}{sel}")
            msg = "เลือกระดับการแปลภาษาเบรลล์อังกฤษ ระดับ 2 แล้ว" if is_th else "English Braille Grade 2 selected"
        self.set_status_message(msg)

    def switch_language(self):
        """สลับภาษาระหว่างภาษาไทย (th) และภาษาอังกฤษ (en) ทันที"""
        self.current_lang = "en" if getattr(self, "current_lang", "th") == "th" else "th"
        self.retranslate_ui()
        msg = "สลับเมนูเป็นภาษาไทยเรียบร้อยแล้ว" if self.current_lang == "th" else "Interface language switched to English"
        self.set_status_message(msg)

    def retranslate_ui(self):
        """แปลคำสั่งในเมนู แถบเครื่องมือ และแถบสถานะให้เป็นภาษาที่เลือก 100% ไม่ปนภาษา"""
        is_th = getattr(self, "current_lang", "th") == "th"

        # 1. Menubar Titles & Actions
        if hasattr(self, "menu_file") and self.menu_file:
            self.menu_file.setTitle("แฟ้ม (&F)" if is_th else "&File")
            self.menu_file.setStatusTip("เมนูแฟ้มข้อมูล (Alt+F)" if is_th else "File Menu (Alt+F)")
            if hasattr(self, "act_new") and self.act_new:
                self.act_new.setText("เปิดเอกสารใหม่ (&N)\tCtrl+N" if is_th else "&New\tCtrl+N")
                self.act_new.setStatusTip("เปิดเอกสารใหม่ (Ctrl+N)" if is_th else "Create new document (Ctrl+N)")
            if hasattr(self, "act_open") and self.act_open:
                self.act_open.setText("เปิดเอกสารเดิม (&O)...\tCtrl+O" if is_th else "&Open...\tCtrl+O")
                self.act_open.setStatusTip("เปิดเอกสารเดิม (Ctrl+O)" if is_th else "Open existing document (Ctrl+O)")
            if hasattr(self, "act_translate") and self.act_translate:
                self.act_translate.setText("แปลเอกสาร (&T)\tCtrl+T" if is_th else "&Translate\tCtrl+T")
                self.act_translate.setStatusTip("แปลเป็นอักษรเบรลล์ (Ctrl+T)" if is_th else "Translate to Braille (Ctrl+T)")
            if hasattr(self, "menu_print") and self.menu_print:
                self.menu_print.setTitle("พิมพ์ (&P)" if is_th else "&Print")
                if hasattr(self, "act_print_reg") and self.act_print_reg:
                    self.act_print_reg.setText("พิมพ์อักษรปกติ (&R)" if is_th else "&Regular text")
                if hasattr(self, "act_print_dots") and self.act_print_dots:
                    self.act_print_dots.setText("พิมพ์จุดเบรลล์ (&B)" if is_th else "&Braille dots")
            if hasattr(self, "act_braille_print") and self.act_braille_print:
                self.act_braille_print.setText("ส่งไปเครื่องพิมพ์เบรลล์ (&B)...\tCtrl+B" if is_th else "&Braille...\tCtrl+B")
                self.act_braille_print.setStatusTip("ส่งไปเครื่องพิมพ์เบรลล์ (Ctrl+B)" if is_th else "Export Braille (.BRF) (Ctrl+B)")
            if hasattr(self, "act_print_setup") and self.act_print_setup:
                self.act_print_setup.setText("ตั้งค่าหน้ากระดาษ (&S)...\tCtrl+P" if is_th else "Print &Setup...\tCtrl+P")
                self.act_print_setup.setStatusTip("ตั้งค่าหน้ากระดาษและเครื่องพิมพ์ (Ctrl+P)" if is_th else "Print Page Setup (Ctrl+P)")
            if hasattr(self, "act_save") and self.act_save:
                self.act_save.setText("บันทึก (&S)\tCtrl+S" if is_th else "&Save\tCtrl+S")
                self.act_save.setStatusTip("บันทึกเอกสาร (Ctrl+S)" if is_th else "Save document (Ctrl+S)")
            if hasattr(self, "act_save_as") and self.act_save_as:
                self.act_save_as.setText("บันทึกเป็น (&A)..." if is_th else "Save &As...")
                self.act_save_as.setStatusTip("บันทึกเป็นไฟล์ใหม่" if is_th else "Save as new file")
            if hasattr(self, "act_save_all") and self.act_save_all:
                self.act_save_all.setText("บันทึกทั้งหมด (&L)\tCtrl+A" if is_th else "Save Al&l\tCtrl+A")
            if hasattr(self, "act_exit") and self.act_exit:
                self.act_exit.setText("ออกจากโปรแกรม (&X)\tAlt+F4" if is_th else "E&xit\tAlt+F4")

        # 2. Edit Menu
        if hasattr(self, "menu_edit") and self.menu_edit:
            self.menu_edit.setTitle("แก้ไข (&E)" if is_th else "&Edit")
            self.menu_edit.setStatusTip("เมนูแก้ไข (Alt+E)" if is_th else "Edit Menu (Alt+E)")
            if hasattr(self, "act_cut") and self.act_cut:
                self.act_cut.setText("ตัด (&T)\tCtrl+X" if is_th else "Cu&t\tCtrl+X")
                self.act_cut.setStatusTip("ตัดข้อความ (Ctrl+X)" if is_th else "Cut text (Ctrl+X)")
            if hasattr(self, "act_copy") and self.act_copy:
                self.act_copy.setText("คัดลอก (&C)\tCtrl+C" if is_th else "&Copy\tCtrl+C")
                self.act_copy.setStatusTip("คัดลอกข้อความ (Ctrl+C)" if is_th else "Copy text (Ctrl+C)")
            if hasattr(self, "act_paste") and self.act_paste:
                self.act_paste.setText("วาง (&P)\tCtrl+V" if is_th else "&Paste\tCtrl+V")
                self.act_paste.setStatusTip("วางข้อความ (Ctrl+V)" if is_th else "Paste text (Ctrl+V)")
            if hasattr(self, "act_find") and self.act_find:
                self.act_find.setText("ค้นหา (&F)...\tCtrl+F" if is_th else "&Find...\tCtrl+F")
                self.act_find.setStatusTip("ค้นหาข้อความ (Ctrl+F)" if is_th else "Find text (Ctrl+F)")
            if hasattr(self, "act_replace") and self.act_replace:
                self.act_replace.setText("แทนที่ (&R)...\tCtrl+R" if is_th else "&Replace...\tCtrl+R")
                self.act_replace.setStatusTip("แทนที่ข้อความ (Ctrl+R)" if is_th else "Replace text (Ctrl+R)")
            if hasattr(self, "act_font") and self.act_font:
                self.act_font.setText("แบบอักษร (&F)..." if is_th else "&Font...")
            if hasattr(self, "act_wrap") and self.act_wrap:
                self.act_wrap.setText("ตัดคำขึ้นบรรทัดใหม่อัตโนมัติ (&W)" if is_th else "&Word Wrap")
            if hasattr(self, "act_fullscreen") and self.act_fullscreen:
                self.act_fullscreen.setText("แสดงผลเต็มจอ (&S)\tF11" if is_th else "Full &Screen\tF11")
            if hasattr(self, "act_switch_win") and self.act_switch_win:
                self.act_switch_win.setText("สลับหน้าต่างข้อความ (&W)\tF6" if is_th else "Switch &Window\tF6")

        # 3. Default Menu
        if hasattr(self, "menu_default") and self.menu_default:
            self.menu_default.setTitle("ค่าเริ่มต้น (&D)" if is_th else "&Default")
            self.menu_default.setStatusTip("เมนูค่าเริ่มต้น (Alt+D)" if is_th else "Default Settings Menu (Alt+D)")
            if hasattr(self, "act_braille_page") and self.act_braille_page:
                self.act_braille_page.setText("ตั้งค่าหน้ากระดาษเบรลล์ (&B)..." if is_th else "&Braille Page...")
            
            sel = " (เลือก)" if is_th else " selected"
            
            if hasattr(self, "menu_page_num") and self.menu_page_num:
                self.menu_page_num.setTitle("ตำแหน่งหมายเลขหน้า (&P)" if is_th else "&Page Number Location")
            if hasattr(self, "act_pn_tl") and self.act_pn_tl:
                self.act_pn_tl.setText("บนซ้าย" if is_th else "Top &Left")
            if hasattr(self, "act_pn_tr") and self.act_pn_tr:
                self.act_pn_tr.setText(("บนขวา" + (sel if self.act_pn_tr.isChecked() else "")) if is_th else ("Top &Right" + (sel if self.act_pn_tr.isChecked() else "")))
            if hasattr(self, "act_pn_bl") and self.act_pn_bl:
                self.act_pn_bl.setText("ล่างซ้าย" if is_th else "Bottom L&eft")
            if hasattr(self, "act_pn_br") and self.act_pn_br:
                self.act_pn_br.setText("ล่างขวา" if is_th else "Bottom R&ight")
            
            if hasattr(self, "menu_printer_port") and self.menu_printer_port:
                self.menu_printer_port.setTitle("พอร์ตเครื่องพิมพ์ (&P)" if is_th else "Printer &Port")
            if hasattr(self, "act_port_c1") and self.act_port_c1:
                self.act_port_c1.setText("Serial Com1" if is_th else "Serial Com&1")
            if hasattr(self, "act_port_c2") and self.act_port_c2:
                self.act_port_c2.setText("Serial Com2" if is_th else "Serial Com&2")
            if hasattr(self, "act_port_l1") and self.act_port_l1:
                self.act_port_l1.setText(("Printer LPT1" + (sel if self.act_port_l1.isChecked() else "")) if is_th else ("Printer LP&T1" + (sel if self.act_port_l1.isChecked() else "")))
            if hasattr(self, "act_port_l2") and self.act_port_l2:
                self.act_port_l2.setText("Printer LPT2" if is_th else "Printer LPT&2")

            if hasattr(self, "menu_print_mode") and self.menu_print_mode:
                self.menu_print_mode.setTitle("โหมดการพิมพ์ (&M)" if is_th else "Printing &Mode")
            if hasattr(self, "act_pm_s") and self.act_pm_s:
                self.act_pm_s.setText("หน้าเดียว" if is_th else "&Single Side")
            if hasattr(self, "act_pm_d") and self.act_pm_d:
                self.act_pm_d.setText(("สองหน้า" + (sel if self.act_pm_d.isChecked() else "")) if is_th else ("&Double Side" + (sel if self.act_pm_d.isChecked() else "")))

            if hasattr(self, "menu_page_adv") and self.menu_page_adv:
                self.menu_page_adv.setTitle("เลื่อนหน้ากระดาษ (&A)" if is_th else "Page &Advance")
            if hasattr(self, "act_pa_y") and self.act_pa_y:
                self.act_pa_y.setText("ใช่" if is_th else "&Yes")
            if hasattr(self, "act_pa_n") and self.act_pa_n:
                self.act_pa_n.setText(("ไม่" + (sel if self.act_pa_n.isChecked() else "")) if is_th else ("&No" + (sel if self.act_pa_n.isChecked() else "")))

            if hasattr(self, "menu_set_font") and self.menu_set_font:
                self.menu_set_font.setTitle("แบบอักษรเริ่มต้น (&F)" if is_th else "Set &Font")
            if hasattr(self, "act_font_term") and self.act_font_term:
                self.act_font_term.setText("Terminal สำหรับผู้พิการทางสายตา" if is_th else "&Terminal font for the blind")
            if hasattr(self, "act_font_sans") and self.act_font_sans:
                self.act_font_sans.setText(("Microsoft Sans Serif สำหรับสายตาปกติ" + (sel if self.act_font_sans.isChecked() else "")) if is_th else ("&Microsoft Sans Serif font for the sighted" + (sel if self.act_font_sans.isChecked() else "")))

            if hasattr(self, "menu_set_kb") and self.menu_set_kb:
                self.menu_set_kb.setTitle("แป้นพิมพ์ดีด (&K)" if is_th else "Set &Keyboard")
            if hasattr(self, "act_kb_th") and self.act_kb_th:
                self.act_kb_th.setText(("แป้นพิมพ์ไทย" + (sel if self.act_kb_th.isChecked() else "")) if is_th else ("&Thai Keyboard" + (sel if self.act_kb_th.isChecked() else "")))
            if hasattr(self, "act_kb_en") and self.act_kb_en:
                self.act_kb_en.setText("แป้นพิมพ์อังกฤษ" if is_th else "&English Keyboard")

            if hasattr(self, "menu_th_level") and self.menu_th_level:
                self.menu_th_level.setTitle("ระดับอักษรเบรลล์ไทย (&T)" if is_th else "&Thai Braille Level")
            if hasattr(self, "act_th_g1") and self.act_th_g1:
                self.act_th_g1.setText(("ระดับ 1 พร้อมคำย่อพื้นฐาน" + (sel if self.thai_grade == 1 else "")) if is_th else ("&Grade 1 with some short form" + (sel if self.thai_grade == 1 else "")))
            if hasattr(self, "act_th_g2") and self.act_th_g2:
                self.act_th_g2.setText(("ระดับ 2 มีคำย่อ" + (sel if self.thai_grade == 2 else "")) if is_th else ("Grade &2 with contractions" + (sel if self.thai_grade == 2 else "")))

            if hasattr(self, "menu_en_level") and self.menu_en_level:
                self.menu_en_level.setTitle("ระดับอักษรเบรลล์อังกฤษ (&E)" if is_th else "&English Braille Level")
            if hasattr(self, "act_en_g1") and self.act_en_g1:
                self.act_en_g1.setText(("ระดับ 1 ไม่มีคำย่อ" + (sel if self.english_grade == 1 else "")) if is_th else ("Grade &1 with no contractions" + (sel if self.english_grade == 1 else "")))
            if hasattr(self, "act_en_g2") and self.act_en_g2:
                self.act_en_g2.setText(("ระดับ 2 มีคำย่อ" + (sel if self.english_grade == 2 else "")) if is_th else ("Grade &2 with contractions" + (sel if self.english_grade == 2 else "")))

        # 4. Tools Menu
        if hasattr(self, "menu_tools") and self.menu_tools:
            self.menu_tools.setTitle("เครื่องมือ (&T)" if is_th else "&Tools")
            self.menu_tools.setStatusTip("เมนูเครื่องมือสร้างสื่อ (Alt+T)" if is_th else "Tools Menu (Alt+T)")
            if hasattr(self, "act_remote_input") and self.act_remote_input:
                self.act_remote_input.setText("พิมพ์ผ่านมือถือในวง LAN (&W)...\tCtrl+Shift+W" if is_th else "&Remote Mobile Input (LAN)...\tCtrl+Shift+W")
                self.act_remote_input.setStatusTip("พิมพ์ผ่านมือถือในวง LAN เดียวกัน (Ctrl+Shift+W)" if is_th else "Remote input via mobile in same LAN (Ctrl+Shift+W)")
            if hasattr(self, "act_tactile") and self.act_tactile:
                self.act_tactile.setText("สร้างภาพนูนสัมผัสจากรูปภาพ (&G)...\tCtrl+G" if is_th else "&Tactile Graphics from Image...\tCtrl+G")
                self.act_tactile.setStatusTip("แปลงภาพเป็นสื่อจุดสัมผัสเบรลล์ (Ctrl+G)" if is_th else "Convert image to tactile Braille graphics (Ctrl+G)")
            if hasattr(self, "act_dot_converter") and self.act_dot_converter:
                self.act_dot_converter.setText("แปลงเป็นเลขจุดเบรลล์ (ก→1245, a→1, b→12) (&D)...\tCtrl+Shift+D" if is_th else "&Braille Dot Numbers Converter (a->1, b->12)...\tCtrl+Shift+D")
                self.act_dot_converter.setStatusTip("แปลงเป็นเลขตำแหน่งจุดเบรลล์ 1-6 (Ctrl+Shift+D)" if is_th else "Convert to Braille dot numbers 1-6 (Ctrl+Shift+D)")
            if hasattr(self, "act_math_to_braille") and self.act_math_to_braille:
                self.act_math_to_braille.setText("แปลงสูตรคณิตศาสตร์เป็นเบรลล์ (Math to Braille) (&M)...\tCtrl+Shift+M" if is_th else "&Math to Braille Converter (Nemeth/UEB)...\tCtrl+Shift+M")
                self.act_math_to_braille.setStatusTip("แปลงสูตรคณิตศาสตร์เป็นอักษรเบรลล์ Nemeth/UEB (Ctrl+Shift+M)" if is_th else "Convert Math expressions to Braille Nemeth/UEB (Ctrl+Shift+M)")

        # 5. Help Menu
        if hasattr(self, "menu_help") and self.menu_help:
            self.menu_help.setTitle("ช่วยเหลือ (&H)" if is_th else "&Help")
            self.menu_help.setStatusTip("เมนูช่วยเหลือ (Alt+H)" if is_th else "Help Menu (Alt+H)")
            if hasattr(self, "act_help_doc") and self.act_help_doc:
                self.act_help_doc.setText("คู่มือการใช้งาน (&H)\tF1" if is_th else "&Help\tF1")
                self.act_help_doc.setStatusTip("คู่มือและวิธีใช้โปรแกรม (F1)" if is_th else "User manual and shortcuts (F1)")
            if hasattr(self, "act_switch_lang") and self.act_switch_lang:
                self.act_switch_lang.setText("Switch to English (&L)\tCtrl+L" if is_th else "สลับเป็นภาษาไทย (Switch to Thai) (&L)\tCtrl+L")
                self.act_switch_lang.setStatusTip("สลับภาษาเมนู (Ctrl+L)" if is_th else "Switch menu language (Ctrl+L)")
            if hasattr(self, "act_buy_lic") and self.act_buy_lic:
                self.act_buy_lic.setText("สั่งซื้อลิขสิทธิ์ (&B)..." if is_th else "&Buy License...")
                self.act_buy_lic.setStatusTip("สั่งซื้อลิขสิทธิ์ SiamBraille 1.0" if is_th else "Purchase SiamBraille 1.0 license")
            if hasattr(self, "act_activate_lic") and self.act_activate_lic:
                self.act_activate_lic.setText("เปิดใช้งานรหัสลิขสิทธิ์ (&A)..." if is_th else "&Activate License Key...")
                self.act_activate_lic.setStatusTip("กรอกรหัส License Key เพื่อเปิดใช้งาน" if is_th else "Enter License Key to activate")
            if hasattr(self, "act_check_update") and self.act_check_update:
                self.act_check_update.setText("ตรวจสอบการอัปเดต (&U)..." if is_th else "&Check for Updates...")
                self.act_check_update.setStatusTip("ตรวจสอบเวอร์ชันล่าสุด" if is_th else "Check for the latest updates")
            if hasattr(self, "act_about") and self.act_about:
                self.act_about.setText("เกี่ยวกับโปรแกรม SiamBraille (&A)..." if is_th else "&About SiamBraille...")
                self.act_about.setStatusTip("เกี่ยวกับโปรแกรม SiamBraille และสถานะลิขสิทธิ์" if is_th else "About SiamBraille and license information")
            if hasattr(self, "act_contact") and self.act_contact:
                self.act_contact.setText("ข้อมูลติดต่อและบริการ (&C)..." if is_th else "&Contact & Support...")
                self.act_contact.setStatusTip("ข้อมูลติดต่อทีมพัฒนา" if is_th else "Contact support and development team")

        # 6. Toolbar button
        if hasattr(self, "btn_tb_translate") and self.btn_tb_translate:
            self.btn_tb_translate.setText(" แปล" if is_th else " Translate")
            self.btn_tb_translate.setToolTip("กดปุ่มเพื่อแปลเอกสาร (Ctrl+T)" if is_th else "Click to translate to Braille (Ctrl+T)")

        # 7. Status bar panels
        if hasattr(self, "lbl_col_limit") and self.lbl_col_limit:
            self.lbl_col_limit.setText(f"คอลัมน์ต่อบรรทัด : {self.line_length}" if is_th else f"Columns per line: {self.line_length}")
        if hasattr(self, "lbl_line_limit") and self.lbl_line_limit:
            self.lbl_line_limit.setText(f"บรรทัดต่อหน้า : {self.page_length}" if is_th else f"Lines per page: {self.page_length}")
        if hasattr(self, "lbl_report") and self.lbl_report:
            txt = self.lbl_report.text().strip()
            if "แปลแล้ว" in txt or "Translated" in txt:
                self.lbl_report.setText("     ข้อมูลไฟล์ที่แปลแล้ว  " if is_th else "     Translated File  ")
            elif "ข้อมูลเดิม" in txt or "Original" in txt:
                self.lbl_report.setText("ข้อมูลเดิม" if is_th else "Original Text")
            elif "ยังไม่แปลง" in txt or "Unconverted" in txt:
                self.lbl_report.setText("ข้อมูลใหม่ยังไม่แปลง" if is_th else "Unconverted Text")
        if hasattr(self, "lbl_total_page") and self.lbl_total_page:
            txt = self.lbl_total_page.text()
            if ":" in txt:
                val = txt.split(":")[-1].strip()
                prefix = "จำนวนหน้า : " if is_th else "Total pages : "
                self.lbl_total_page.setText(f"{prefix}{val}" if val else prefix)

        self.update_title()

    def setup_toolbar(self):
        toolbar = QToolBar("ToolBar1", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setAccessibleName("แถบเครื่องมือด่วน Quick Toolbar")
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f0f0f0;
                border-top: 1px solid #ffffff;
                border-bottom: 1px solid #c0c0c0;
                padding: 2px 2px;
                spacing: 2px;
            }
            QToolButton {
                background-color: #f0f0f0;
                border: 2px solid;
                border-color: #ffffff #808080 #808080 #ffffff;
                padding: 2px;
                margin: 0px 1px;
            }
            QToolButton:hover {
                background-color: #e8e8e8;
            }
            QToolButton:pressed {
                border-color: #808080 #ffffff #ffffff #808080;
                background-color: #d8d8d8;
            }
            QToolBar::separator {
                width: 6px;
                background-color: transparent;
            }
        """)
        self.addToolBar(toolbar)
        
        # 1. New, Open, Save (ไอคอนต้นฉบับ Delphi จาก ImageList)
        act_new = QAction(get_app_icon("ui_icon_new.png"), "New", self)
        act_new.setToolTip("New (Ctrl+N)")
        act_new.setStatusTip("ปุ่มเปิดไฟล์ใหม่ New (Ctrl+N)")
        act_new.setStatusTip("เปิดไฟล์ใหม่ (Ctrl+N)")
        act_new.triggered.connect(self.file_new)
        toolbar.addAction(act_new)
        
        act_open = QAction(get_app_icon("ui_icon_open.png"), "Open", self)
        act_open.setToolTip("Open (Ctrl+O)")
        act_open.setStatusTip("ปุ่มเปิดไฟล์เดิม Open (Ctrl+O)")
        act_open.setStatusTip("เปิดไฟล์เก่า (Ctrl+O)")
        act_open.triggered.connect(self.file_open)
        toolbar.addAction(act_open)
        
        act_save = QAction(get_app_icon("ui_icon_save.png"), "Save", self)
        act_save.setToolTip("Save (Ctrl+S)")
        act_save.setStatusTip("ปุ่มบันทึกไฟล์ Save (Ctrl+S)")
        act_save.setStatusTip("บันทึก (Ctrl+S)")
        act_save.triggered.connect(self.file_save)
        toolbar.addAction(act_save)
        
        toolbar.addSeparator()
        
        # 2. Cut, Copy, Paste (ไอคอนต้นฉบับ Delphi จาก ImageList)
        act_cut = QAction(get_app_icon("ui_icon_cut.png"), "Cut", self)
        act_cut.setToolTip("Cut (Ctrl+X)")
        act_cut.setStatusTip("ปุ่มตัดข้อความ Cut (Ctrl+X)")
        act_cut.setStatusTip("ตัดข้อความ (Ctrl+X)")
        act_cut.triggered.connect(self.txt_normal.cut)
        toolbar.addAction(act_cut)
        
        act_copy = QAction(get_app_icon("ui_icon_copy.png"), "Copy", self)
        act_copy.setToolTip("Copy (Ctrl+C)")
        act_copy.setStatusTip("ปุ่มคัดลอกข้อความ Copy (Ctrl+C)")
        act_copy.setStatusTip("คัดลอกข้อความ (Ctrl+C)")
        act_copy.triggered.connect(self.txt_normal.copy)
        toolbar.addAction(act_copy)
        
        act_paste = QAction(get_app_icon("ui_icon_paste.png"), "Paste", self)
        act_paste.setToolTip("Paste (Ctrl+V)")
        act_paste.setStatusTip("ปุ่มวางข้อความ Paste (Ctrl+V)")
        act_paste.setStatusTip("วางข้อความ (Ctrl+V)")
        act_paste.triggered.connect(self.txt_normal.paste)
        toolbar.addAction(act_paste)
        
        # 3. Big "แปล" Button (SpeedButton3 ใน Delphi)
        self.btn_tb_translate = QToolButton(self)
        self.btn_tb_translate.setIcon(get_app_icon("glyph_translate.png"))
        self.btn_tb_translate.setText(" แปล")
        self.btn_tb_translate.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_tb_translate.setToolTip("กดปุ่มเพื่อแปลเอกสาร (Ctrl+T)")
        self.btn_tb_translate.setAccessibleName("ปุ่มแปลเอกสารเป็นอักษรเบรลล์ Translate (Ctrl+T)")
        self.btn_tb_translate.setAccessibleDescription("กดปุ่มนี้หรือกด Ctrl+T เพื่อแปลข้อความในกล่องข้อมูลเดิมเป็นอักษรเบรลล์")
        self.btn_tb_translate.setStatusTip("แปลเป็นเบรลล์ (Ctrl+T)")
        self.btn_tb_translate.setStyleSheet("""
            QToolButton {
                font-family: 'Tahoma', 'MS Sans Serif';
                font-weight: bold;
                font-size: 11px;
                color: #000000;
                background-color: #f0f0f0;
                border: 2px solid;
                border-color: #ffffff #808080 #808080 #ffffff;
                padding: 1px 6px;
                margin: 0px 2px;
            }
            QToolButton:hover {
                background-color: #e8e8e8;
            }
            QToolButton:pressed {
                border-color: #808080 #ffffff #ffffff #808080;
                background-color: #d8d8d8;
            }
        """)
        self.btn_tb_translate.clicked.connect(self.action_translate)
        toolbar.addWidget(self.btn_tb_translate)
        
        toolbar.addSeparator()
        
        # 4. Sunken Banner Label (Panel1 ใน Delphi: BevelInner=bvLowered)
        banner_frame = QFrame()
        banner_frame.setAccessibleName("ป้ายชื่อโปรแกรม SiamBraille 1.0")
        banner_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 2px solid;
                border-color: #808080 #ffffff #ffffff #808080;
                padding: 2px 14px;
                margin: 0px 2px;
            }
        """)
        banner_layout = QHBoxLayout(banner_frame)
        banner_layout.setContentsMargins(4, 1, 4, 1)
        
        lbl_version = QLabel("SiamBraille 1.0")
        lbl_version.setAccessibleName("SiamBraille 1.0")
        lbl_version.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #000000;
                font-family: 'Tahoma', 'MS Sans Serif', 'Arial';
                font-size: 11px;
            }
        """)
        banner_layout.addWidget(lbl_version)
        toolbar.addWidget(banner_frame)

    def setup_statusbar(self):
        statusbar = self.statusBar()
        if not statusbar:
            return
            
        statusbar.setSizeGripEnabled(True)
        statusbar.setAccessibleName("แถบสถานะโปรแกรม Status Bar")
        statusbar.setStyleSheet("""
            QStatusBar {
                background-color: #f0f0f0;
                color: #000000;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
                min-height: 24px;
                border-top: 1px solid #c0c0c0;
            }
            QStatusBar::item {
                border: none;
            }
        """)
        
        # Exact 4 Status Panels matching original:
        # [ข้อมูลไฟล์ที่แปลแล้ว] | [Total page : ] | [Colume per lines: 30] | [Lines per page: 25]
        panel_style = """
            QLabel {
                border: 1px solid;
                border-color: #808080 #ffffff #ffffff #808080;
                background-color: #f0f0f0;
                color: #000000;
                font-family: 'Tahoma', 'MS Sans Serif';
                font-size: 11px;
                padding: 2px 4px;
            }
        """
        
        # 4 Panels: [ข้อมูลเดิม/แปลแล้ว] | [จำนวนหน้า] | [คอลัมน์ต่อบรรทัด] | [บรรทัดต่อหน้า]
        is_th = getattr(self, "current_lang", "th") == "th"
        self.lbl_report = QLabel("     ข้อมูลไฟล์ที่แปลแล้ว  " if is_th else "     Translated File  ")
        self.lbl_report.setFixedWidth(160)
        self.lbl_report.setStyleSheet(panel_style)
        self.lbl_report.setAccessibleName("สถานะ: ข้อมูลไฟล์ที่แปลแล้ว" if is_th else "Status: Translated File")
        
        self.lbl_total_page = QLabel("จำนวนหน้า : " if is_th else "Total pages : ")
        self.lbl_total_page.setFixedWidth(180)
        self.lbl_total_page.setStyleSheet(panel_style)
        self.lbl_total_page.setAccessibleName("จำนวนหน้าเบรลล์ทั้งหมด" if is_th else "Total Braille Pages")
        
        self.lbl_col_limit = QLabel(f"คอลัมน์ต่อบรรทัด : {self.line_length}" if is_th else f"Columns per line: {self.line_length}")
        self.lbl_col_limit.setFixedWidth(180)
        self.lbl_col_limit.setStyleSheet(panel_style)
        self.lbl_col_limit.setAccessibleName(f"ความกว้างคอลัมน์ต่อบรรทัด: {self.line_length}" if is_th else f"Columns per line: {self.line_length}")
        
        self.lbl_line_limit = QLabel(f"บรรทัดต่อหน้า : {self.page_length}" if is_th else f"Lines per page: {self.page_length}")
        self.lbl_line_limit.setStyleSheet(panel_style)
        self.lbl_line_limit.setAccessibleName(f"ความยาวบรรทัดต่อหน้า: {self.page_length}" if is_th else f"Lines per page: {self.page_length}")
        
        # เพิ่มพาเนลเรียงจากซ้ายไปขวา สะอาด เรียบร้อย ไม่แสดงสถานะลิขสิทธิ์โจ่งแจ้งบนหน้าจอหลัก
        statusbar.addWidget(self.lbl_report)
        statusbar.addWidget(self.lbl_total_page)
        statusbar.addWidget(self.lbl_col_limit)
        statusbar.addWidget(self.lbl_line_limit, 1)

    def on_text_changed(self):
        text = self.txt_normal.toPlainText()
        is_th = getattr(self, "current_lang", "th") == "th"
        if text.strip():
            lines = text.count('\n') + 1
            body_cap = max(1, self.page_length - 1)
            pages = max(1, (lines + body_cap - 1) // body_cap)
            self.lbl_total_page.setText(f"จำนวนหน้า : {pages}" if is_th else f"Total pages : {pages}")
            self.lbl_total_page.setAccessibleName(f"จำนวนหน้า: {pages} หน้า" if is_th else f"Total pages: {pages}")
            self.lbl_report.setText("ข้อมูลใหม่ยังไม่แปลง" if is_th else "Unconverted Text")
        else:
            self.lbl_total_page.setText("จำนวนหน้า : " if is_th else "Total pages : ")
            self.lbl_total_page.setAccessibleName("จำนวนหน้า: ยังไม่มีข้อมูล" if is_th else "No page data")

    def format_braille_document(self, raw_text: str):
        """
        จัดหน้าเอกสารอักษรเบรลล์และแถบเทียบเคียงภาษาไทยตามแบบฉบับ Delphi TBTW ดั้งเดิม:
        1. บรรทัดที่ 1 ของแต่ละหน้า (Line 1) เว้นว่าง 1 บรรทัดเสมอ เพื่อเว้นไว้ใส่เลขหน้า (Header / Page Number)
        2. บรรทัดที่ 2 เป็นต้นไป (สูงสุด self.page_length - 1 บรรทัดต่อหน้า) เป็นเนื้อหา
        3. ตัดบรรทัดไม่เกิน self.line_length (ค่าเริ่มต้น 30 คอลัมน์)
        4. txt_braille_thai (คอลัมน์อ้างอิงภาษาไทย) และ txt_braille (อักษรเบรลล์) ตรงกันบรรทัดต่อบรรทัด
        5. คืนค่า (thai_display, braille_unicode_display, total_pages, lines_in_last)
        """
        if not raw_text.strip():
            return "", "", 0, 0
            
        def num_to_braille(num: int) -> str:
            m = {'1':'a','2':'b','3':'c','4':'d','5':'e','6':'f','7':'g','8':'h','9':'i','0':'j'}
            return '#' + ''.join(m.get(d, d) for d in str(num))

        has_pythainlp = pythainlp is not None

        input_lines = raw_text.split('\n')
        content_pairs = []  # list of (th_line, br_unicode_line)
        indent_size = 2

        for in_line in input_lines:
            if not in_line:
                content_pairs.append(("", ""))
                continue
                
            # แยกคำภาษาไทยเพื่อให้ตัดบรรทัดตรงขอบคำพอดีเหมือน Delphi TBTW
            tokens = []
            tokenizer = getattr(self, 'thai_tokenizer', None)
            if tokenizer is not None and hasattr(tokenizer, 'word_tokenize'):
                try:
                    tokens = tokenizer.word_tokenize(in_line)
                except Exception:
                    tokens = []
            elif pythainlp is not None:
                try:
                    tokens = pythainlp.word_tokenize(in_line, engine='newmm')
                except Exception:
                    tokens = []
            if not tokens:
                # ตัวแยกคำสำรอง: แบ่งคำ/กลุ่มพยางค์ภาษาไทย ไม่ตัดคำขาดกลางคัน
                import re
                tokens = [m for m in re.findall(r'([a-zA-Z0-9_#]+|\s+|[\u0e00-\u0e7f]{1,6}|[^\s\w])', in_line) if m]
                if not tokens:
                    tokens = in_line.split(' ')

            translated_tokens = []
            for tok in tokens:
                if tok == ' ':
                    translated_tokens.append((' ', ' ', ' '))
                else:
                    b_u = self.translator.translate(tok, grade=self.thai_grade, mode=self.engine_mode)
                    b_s = self.translator.to_ascii_braille(b_u)
                    translated_tokens.append((tok, b_u, b_s))

            curr_th = ""
            curr_bu = ""
            curr_bs = ""
            is_first_line = True

            for tok_th, tok_bu, tok_bs in translated_tokens:
                # ถ้าขึ้นบรรทัดใหม่ และคำเริ่มต้นเป็นช่องว่าง ให้ข้ามช่องว่างไป
                if not is_first_line and not curr_bs and not tok_bs.strip():
                    continue

                max_allowed = self.line_length if is_first_line else (self.line_length - indent_size)

                # ถ้าคำเดียวยาวเกิน max_allowed (เช่น URL ขนาดยาว หรือข้อความยาวติดกัน)
                if len(tok_bs) > max_allowed:
                    if curr_bs.strip(' \t\r\n\u2800'):
                        prefix = "" if is_first_line else (" " * indent_size)
                        content_pairs.append((prefix + curr_th.strip(' \t\r\n\u2800'), prefix + curr_bu.strip(' \t\r\n\u2800')))
                        curr_th, curr_bu, curr_bs = "", "", ""
                        is_first_line = False

                    sub_bs = tok_bs
                    sub_bu = tok_bu
                    sub_th = tok_th
                    while len(sub_bs) > (self.line_length - indent_size):
                        chunk_size = self.line_length if is_first_line else (self.line_length - indent_size)
                        c_bs = sub_bs[:chunk_size]
                        c_bu = sub_bu[:chunk_size]
                        th_ratio = len(sub_th) / max(len(sub_bs), 1)
                        c_th_len = max(1, int(chunk_size * th_ratio))
                        # ไม่ตัดสระบน สระล่าง หรือวรรณยุกต์ภาษาไทยให้หลุดออกจากพยัญชนะ
                        while c_th_len < len(sub_th) and ('\u0e30' <= sub_th[c_th_len] <= '\u0e4e'):
                            c_th_len += 1
                        c_th = sub_th[:c_th_len]

                        prefix = "" if is_first_line else (" " * indent_size)
                        content_pairs.append((prefix + c_th.strip(' \t\r\n\u2800'), prefix + c_bu.strip(' \t\r\n\u2800')))

                        sub_bs = sub_bs[chunk_size:]
                        sub_bu = sub_bu[chunk_size:]
                        sub_th = sub_th[c_th_len:]
                        is_first_line = False

                    curr_th = sub_th.lstrip(' \t\r\n\u2800')
                    curr_bu = sub_bu.lstrip(' \t\r\n\u2800')
                    curr_bs = sub_bs.lstrip(' \t\r\n\u2800')
                    continue

                next_len = len(curr_bs) + len(tok_bs)

                if not curr_bs:
                    curr_th = tok_th.lstrip(' \t\r\n\u2800')
                    curr_bu = tok_bu.lstrip(' \t\r\n\u2800')
                    curr_bs = tok_bs.lstrip(' \t\r\n\u2800')
                elif next_len <= max_allowed:
                    curr_th += tok_th
                    curr_bu += tok_bu
                    curr_bs += tok_bs
                else:
                    prefix = "" if is_first_line else (" " * indent_size)
                    clean_th = curr_th.strip(' \t\r\n\u2800')
                    clean_bu = curr_bu.strip(' \t\r\n\u2800')
                    content_pairs.append((prefix + clean_th, prefix + clean_bu))
                    curr_th = tok_th.lstrip(' \t\r\n\u2800')
                    curr_bu = tok_bu.lstrip(' \t\r\n\u2800')
                    curr_bs = tok_bs.lstrip(' \t\r\n\u2800')
                    is_first_line = False

            if curr_bs.strip(' \t\r\n\u2800'):
                prefix = "" if is_first_line else (" " * indent_size)
                clean_th = curr_th.strip(' \t\r\n\u2800')
                clean_bu = curr_bu.strip(' \t\r\n\u2800')
                content_pairs.append((prefix + clean_th, prefix + clean_bu))

        # จัดหน้า (Pagination) ตามแบบฉบับ Delphi TBTW
        # บรรทัดที่ 1 ของทุกหน้า: ใส่เลขหน้าเบรลล์ (#a, #b, ... #aj, #aa...) ชิดขวาที่คอลัมน์ 30
        # บรรทัดที่ 2..page_length: เนื้อหา (สูงสุด body_cap = page_length - 1 บรรทัด)
        body_cap = max(1, self.page_length - 1)
        total_content = len(content_pairs)
        total_pages = max(1, (total_content + body_cap - 1) // body_cap)

        thai_final_lines = []
        braille_final_lines = []

        for p in range(total_pages):
            p_no = p + 1
            br_page_str = num_to_braille(p_no)
            br_page_uni = self.translator.ascii_to_unicode(br_page_str)

            # บรรทัดแรก: เลขหน้าเบรลล์ชิดขวาที่คอลัมน์ line_length (30)
            braille_header_line = f"{br_page_uni:>{self.line_length}}"
            # ภาษาไทยอ้างอิงแสดง [หน้า X] ชัดเจนที่ต้นบรรทัด เพื่อให้ผู้ใช้มองเห็นเลขหน้าทันที
            thai_header_line = f"[หน้า {p_no}]"

            thai_final_lines.append(thai_header_line)
            braille_final_lines.append(braille_header_line)

            # บรรทัดเนื้อหาในหน้านี้ (สูงสุด 24 บรรทัด)
            start_idx = p * body_cap
            end_idx = min(total_content, (p + 1) * body_cap)
            for i in range(start_idx, end_idx):
                th_c, br_c = content_pairs[i]
                thai_final_lines.append(th_c)
                braille_final_lines.append(br_c)

        thai_display = "\n".join(thai_final_lines)
        braille_unicode_display = "\n".join(braille_final_lines)

        rem_content = total_content % body_cap
        if rem_content == 0 and total_content > 0:
            rem_content = body_cap
        lines_in_last = 1 + rem_content

        return thai_display, braille_unicode_display, total_pages, lines_in_last

    def action_translate(self):
        mgr = license_guard.global_license_manager
        if not mgr.is_licensed and getattr(mgr, "is_trial_expired", False):
            self.show_trial_expired_dialog()
            return

        raw_text = self.txt_normal.toPlainText()
        is_th = getattr(self, "current_lang", "th") == "th"
        if not raw_text.strip():
            self.lbl_report.setText("ข้อมูลเดิม" if is_th else "Original Text")
            self.set_status_message("ไม่มีข้อความให้แปล กรุณาพิมพ์หรือเปิดไฟล์ก่อน" if is_th else "No text to translate. Please enter or open a file first.")
            return
            
        self.lbl_report.setText("กำลังแปล..." if is_th else "Translating...")
        self.set_status_message("กำลังแปลเป็นอักษรเบรลล์ กรุณารอสักครู่..." if is_th else "Translating to Braille, please wait...")
        QApplication.processEvents()
        
        # จัดหน้าและแปลเป็นอักษรเบรลล์ (เว้นบรรทัดที่ 1 ไว้ใส่เลขหน้าตามแบบฉบับ Delphi TBTW)
        thai_display, braille_unicode, total_pages, lines_in_last = self.format_braille_document(raw_text)
        
        if self.simbrl_font_loaded:
            braille_display = self.translator.to_ascii_braille(braille_unicode)
        else:
            braille_display = braille_unicode
            
        # อัปเดตกล่องแสดงผลฝั่งขวา (Thai Line Preview + Braille Dots)
        self.txt_braille_thai.setPlainText(thai_display)
        self.txt_braille.setPlainText(braille_display)
        self.lbl_report.setText("     ข้อมูลไฟล์ที่แปลแล้ว  " if is_th else "     Translated File  ")
        
        self.total_page = total_pages
        self.lbl_total_page.setText(f"จำนวนหน้า : {total_pages}" if is_th else f"Total pages : {total_pages}")
        self.lbl_total_page.setAccessibleName(f"จำนวนหน้าเบรลล์: {total_pages} หน้า" if is_th else f"Total Braille Pages: {total_pages}")
        self.set_status_message(f"แปลเอกสารเรียบร้อยแล้ว จำนวน {total_pages} หน้า รวมหน้าสุดท้าย {lines_in_last} บรรทัด" if is_th else f"Translation complete: {total_pages} pages ({lines_in_last} lines on last page)")
        
        # สร้างชื่อไฟล์จำลองตามต้นฉบับ Delphi
        base_name = os.path.splitext(self.current_filename)[0]
        thai_temp = f"{base_name}.$u$" if not os.path.basename(self.current_filename).startswith("noname") else "C:\\noname.$u$"
        braille_target = f"{base_name}.tbt" if not os.path.basename(self.current_filename).startswith("noname") else "c:\\noname.tbt"
        
        # แสดงหน้าต่าง Report Translate modal dialog (Form6 ใน Delphi) ตรงตาม Image 1
        dlg = ReportTranslateDialog(
            parent=self,
            thai_file=thai_temp,
            braille_file=braille_target,
            line_len=self.line_length,
            page_len=self.page_length,
            total_pages=total_pages,
            lines_in_last=lines_in_last,
            questionable=0
        )
        dlg.exec()

    def file_new(self):
        is_th = getattr(self, "current_lang", "th") == "th"
        self.txt_normal.clear()
        self.txt_braille_thai.clear()
        self.txt_braille.clear()
        self.current_filename = "c:\\noname.txt"
        self.update_title()
        self.lbl_report.setText("     ข้อมูลไฟล์ที่แปลแล้ว  " if is_th else "     Translated File  ")
        self.lbl_total_page.setText("จำนวนหน้า : " if is_th else "Total pages : ")
        self.set_status_message("เปิดเอกสารใหม่เรียบร้อยแล้ว (c:\\noname.txt)" if is_th else "New document opened (c:\\noname.txt)")
        self.txt_normal.setFocus()

    def read_text_file(self, filepath: str) -> str:
        """อ่านไฟล์ข้อความโดยตรวจสอบการเข้ารหัส UTF-8, CP874, TIS-620, UTF-16 อัตโนมัติ"""
        with open(filepath, 'rb') as f:
            raw = f.read()
        for enc in ['utf-8-sig', 'utf-8', 'cp874', 'tis-620', 'utf-16', 'latin-1']:
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode('utf-8', errors='replace')

    def read_docx_file(self, filepath: str) -> str:
        """อ่านเอกสาร Microsoft Word .docx ดึงข้อความทุกย่อหน้าและตาราง"""
        try:
            import docx
            doc = docx.Document(filepath)
            paragraphs = [p.text for p in doc.paragraphs if p.text]
            for table in doc.tables:
                for row in table.rows:
                    row_txt = '  '.join([c.text.strip() for c in row.cells if c.text.strip()])
                    if row_txt:
                        paragraphs.append(row_txt)
            return '\n'.join(paragraphs)
        except Exception:
            import zipfile, xml.etree.ElementTree as ET
            with zipfile.ZipFile(filepath) as z:
                xml_content = z.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                paragraphs = []
                for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                    p_txt = ''.join([t.text for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text])
                    if p_txt:
                        paragraphs.append(p_txt)
                return '\n'.join(paragraphs)

    def read_doc_file(self, filepath: str) -> str:
        """อ่านเอกสาร Word รุ่นเก่า .doc (Word 97-2003)"""
        with open(filepath, 'rb') as f:
            data = f.read()
        u16 = data.decode('utf-16le', errors='ignore')
        cleaned = ''.join(c for c in u16 if c.isprintable() or c in '\n\r\t')
        if len(cleaned.strip()) > 30:
            return cleaned.strip()
        cp = data.decode('cp874', errors='ignore')
        cleaned = ''.join(c for c in cp if c.isprintable() or c in '\n\r\t')
        return cleaned.strip()

    def save_docx_file(self, filepath: str, text: str):
        """บันทึกข้อความเป็นเอกสาร Word .docx"""
        import docx
        doc = docx.Document()
        for line in text.splitlines():
            doc.add_paragraph(line)
        doc.save(filepath)

    def is_braille_ascii(self, text: str) -> bool:
        """ตรวจสอบว่าข้อความเป็นรหัส Braille ASCII หรือไม่"""
        sample = text[:300]
        if any('\u0e01' <= c <= '\u0e5b' for c in sample):
            return False
        if any(c in '⠁⠃⠉⠙⠑⠋⠛⠓⠊⠚' for c in sample):
            return True
        braille_markers = sum(1 for c in sample if c in ',#><%?:;!=')
        return braille_markers > 3

    def file_open(self):
        filter_str = (
            "เอกสารที่รองรับทั้งหมด (*.txt *.docx *.doc *.tbt *.brf);;"
            "Word Documents (*.docx *.doc);;"
            "Text Files (*.txt);;"
            "TBT Files (*.tbt);;"
            "Braille Formatted (*.brf);;"
            "All Files (*.*)"
        )
        filename, _ = QFileDialog.getOpenFileName(self, "เปิดไฟล์เอกสาร", "", filter_str)
        if not filename:
            return
            
        try:
            ext = os.path.splitext(filename)[1].lower()
            
            # กรณี 1: เอกสาร Word (.docx)
            if ext == '.docx':
                content = self.read_docx_file(filename)
                self.txt_normal.setPlainText(content)
                self.current_filename = filename
                self.update_title()
                self.action_translate()
                self.set_status_message(f"เปิดและแปลเอกสาร Word (.docx): {os.path.basename(filename)}")
                self.txt_normal.setFocus()
                
            # กรณี 2: เอกสาร Word รุ่นเก่า (.doc)
            elif ext == '.doc':
                content = self.read_doc_file(filename)
                self.txt_normal.setPlainText(content)
                self.current_filename = filename
                self.update_title()
                self.action_translate()
                self.set_status_message(f"เปิดและแปลเอกสาร Word (.doc): {os.path.basename(filename)}")
                self.txt_normal.setFocus()
                
            # กรณี 3: ไฟล์เครื่องพิมพ์เบรลล์ (.brf)
            elif ext == '.brf':
                content = self.read_text_file(filename)
                self.txt_braille.setPlainText(content)
                self.current_filename = filename
                self.update_title()
                if hasattr(self, 'lbl_report') and self.lbl_report is not None:
                    self.lbl_report.setText("เปิดไฟล์เบรลล์ BRF")
                self.set_status_message(f"เปิดไฟล์เครื่องพิมพ์เบรลล์: {os.path.basename(filename)}")
                self.txt_braille.setFocus()
                
            # กรณี 4: ไฟล์ .tbt หรือ .txt ทั่วไป
            else:
                content = self.read_text_file(filename)
                if ext == '.tbt' and self.is_braille_ascii(content):
                    self.txt_braille.setPlainText(content)
                    self.current_filename = filename
                    self.update_title()
                    if hasattr(self, 'lbl_report') and self.lbl_report is not None:
                        self.lbl_report.setText("เปิดไฟล์เบรลล์ TBT")
                    self.set_status_message(f"เปิดไฟล์ผลลัพธ์เบรลล์ TBT: {os.path.basename(filename)}")
                    self.txt_braille.setFocus()
                else:
                    self.txt_normal.setPlainText(content)
                    self.current_filename = filename
                    self.update_title()
                    self.action_translate()
                    self.set_status_message(f"เปิดและแปลไฟล์ข้อความ: {os.path.basename(filename)}")
                    self.txt_normal.setFocus()
                    
        except Exception as e:
            QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถเปิดไฟล์ได้: {e}")

    def file_save(self):
        if self.current_filename == "c:\\noname.txt" or not os.path.exists(self.current_filename):
            self.file_save_as()
        else:
            try:
                ext = os.path.splitext(self.current_filename)[1].lower()
                if ext == '.docx':
                    self.save_docx_file(self.current_filename, self.txt_normal.toPlainText())
                elif ext == '.brf':
                    braille_text = self.txt_braille.toPlainText()
                    ascii_brl = self.translator.to_ascii_braille(braille_text) if not self.simbrl_font_loaded else braille_text
                    with open(self.current_filename, 'w', encoding='ascii', errors='replace') as f:
                        f.write(ascii_brl)
                else:
                    with open(self.current_filename, 'w', encoding='utf-8') as f:
                        f.write(self.txt_normal.toPlainText())
                msg = f"บันทึกไฟล์เรียบร้อย: {os.path.basename(self.current_filename)}"
                if hasattr(self, 'lbl_report') and self.lbl_report is not None:
                    self.lbl_report.setText(f"  {msg}  ")
                self.set_status_message(msg)
            except Exception as e:
                QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถบันทึกไฟล์ได้: {e}")

    def file_save_as(self):
        filter_str = (
            "Text Files (*.txt);;"
            "Word Documents (*.docx);;"
            "TBT Files (*.tbt);;"
            "Braille Formatted (*.brf);;"
            "All Files (*.*)"
        )
        filename, selected_filter = QFileDialog.getSaveFileName(
            self, "บันทึกเป็น", "noname.txt", filter_str
        )
        if filename:
            if '.' not in os.path.basename(filename):
                if 'docx' in selected_filter:
                    filename += '.docx'
                elif 'brf' in selected_filter:
                    filename += '.brf'
                elif 'tbt' in selected_filter:
                    filename += '.tbt'
                else:
                    filename += '.txt'
            self.current_filename = filename
            self.update_title()
            self.file_save()

    def file_export_brf(self):
        braille_text = self.txt_braille.toPlainText()
        if not braille_text.strip():
            QMessageBox.warning(self, "คำเตือน", "ยังไม่มีผลลัพธ์อักษรเบรลล์ กรุณากดปุ่ม แปล (Ctrl+T) ก่อน")
            return
            
        if not self.simbrl_font_loaded:
            ascii_braille = self.translator.to_ascii_braille(braille_text)
        else:
            ascii_braille = braille_text
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "ส่งออกไฟล์เครื่องพิมพ์เบรลล์ (.BRF)", "document.brf", "Braille Formatted (*.brf);;All Files (*.*)"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='ascii', errors='replace') as f:
                    f.write(ascii_braille)
                msg = f"ส่งออกไฟล์สำหรับเครื่องพิมพ์เบรลล์ (.BRF) สำเร็จ: {os.path.basename(filename)}"
                QMessageBox.information(self, "ส่งออกสำเร็จ", f"ส่งออกไฟล์สำหรับเครื่องพิมพ์เบรลล์ (.BRF) สำเร็จ:\n{filename}")
                if hasattr(self, 'lbl_report') and self.lbl_report is not None:
                    self.lbl_report.setText("  ส่งออกไฟล์สำเร็จ  ")
                self.set_status_message(msg)
            except Exception as e:
                QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถส่งออกไฟล์ได้: {e}")

    def print_regular(self):
        """พิมพ์ข้อความภาษาไทยปกติ (Regular text) ออกทางเครื่องพิมพ์มาตรฐาน Windows / PDF"""
        text = self.txt_normal.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "แจ้งเตือน", "ไม่มีข้อความปกติให้พิมพ์ กรุณาพิมพ์หรือเปิดไฟล์ก่อน")
            return
            
        if QPrinter is None or QPrintDialog is None:
            QMessageBox.critical(self, "ข้อผิดพลาด", "ระบบไม่รองรับโมดูล QtPrintSupport")
            return
            
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("พิมพ์เอกสารข้อความปกติ (Regular text)")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                doc = QTextDocument()
                doc.setPlainText(text)
                doc.print(printer)
                self.set_status_message("พิมพ์เอกสารข้อความปกติสำเร็จ")
                speak_nvda("พิมพ์เอกสารข้อความปกติสำเร็จ")
            except Exception as e:
                QMessageBox.critical(self, "ข้อผิดพลาด", f"เกิดข้อผิดพลาดในการพิมพ์: {e}")

    def print_dots(self):
        """
        พิมพ์จุดเบรลล์จำลอง (SimBraille / SMB Dots) เป็นกระดาษ A4 ออกทางเครื่องพิมพ์มาตรฐาน Windows / PDF
        ใช้ฟอนต์ SimBraille (SIMBRL.TTF) วาดจุดเบรลล์สีดำลงบนหน้ากระดาษ A4
        เพื่อให้ครูผู้สอนหรือคนสายตาปกติสามารถมองเห็นและตรวจทานด้วยสายตาก่อนนำไปตอกจริง
        """
        braille_text = self.txt_braille.toPlainText()
        if not braille_text.strip():
            QMessageBox.warning(self, "แจ้งเตือน", "ไม่มีข้อความอักษรเบรลล์ให้พิมพ์ กรุณาแปลเอกสารก่อน (Ctrl+T)")
            return
            
        if QPrinter is None or QPrintDialog is None:
            QMessageBox.critical(self, "ข้อผิดพลาด", "ระบบไม่รองรับโมดูล QtPrintSupport")
            return
            
        # แปลงเป็น Braille ASCII (รหัสสำหรับฟอนต์ SimBraille)
        ascii_braille = self.translator.to_ascii_braille(braille_text) if not self.simbrl_font_loaded else braille_text
        
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        
        # กำหนดขนาดหน้ากระดาษเป็น A4 แนวตั้ง (Portrait) พร้อมระยะขอบ 15 มม.
        try:
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
            printer.setPageMargins(QMarginsF(15.0, 15.0, 15.0, 15.0), QPageLayout.Unit.Millimeter)
        except Exception:
            pass
            
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("พิมพ์จุดเบรลล์จำลอง A4 (SimBraille / SMB)")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                painter = QPainter(printer)
                paint_rect = printer.pageLayout().paintRectPixels(printer.resolution())
                avail_w = paint_rect.width()
                avail_h = paint_rect.height()
                
                # ค้นหาขนาดพอยต์ที่เหมาะสมที่สุดสำหรับกระดาษ A4 (30-40 คอลัมน์ x 25-28 บรรทัด)
                target_cols = max(self.line_length, 30)
                target_lines = max(self.page_length, 25)
                
                best_pt = 14
                for pt in range(14, 30):
                    f_test = QFont("SimBraille", pt)
                    painter.setFont(f_test)
                    fm_test = painter.fontMetrics()
                    test_w = fm_test.horizontalAdvance('W' * target_cols)
                    test_h = int(fm_test.lineSpacing() * 1.25 * target_lines)
                    if test_w <= avail_w and test_h <= avail_h:
                        best_pt = pt
                    else:
                        break
                        
                font = QFont("SimBraille", best_pt)
                painter.setFont(font)
                font_metrics = painter.fontMetrics()
                line_height = int(font_metrics.lineSpacing() * 1.25)
                
                margin_x = paint_rect.left()
                margin_y = paint_rect.top()
                
                lines = ascii_braille.split('\n')
                curr_y = margin_y + font_metrics.ascent()
                lines_in_page = 0
                max_lines = self.page_length  # ค่าเริ่มต้นตามที่ตั้งไว้ในหน้ากระดาษ (25 บรรทัด)
                
                for line in lines:
                    # ตรวจสอบการขึ้นหน้าใหม่ด้วย Form Feed (\x0c) หรือครบจำนวนบรรทัด
                    if '\x0c' in line or lines_in_page >= max_lines:
                        printer.newPage()
                        curr_y = margin_y + font_metrics.ascent()
                        lines_in_page = 0
                        line = line.replace('\x0c', '')
                        
                    painter.drawText(margin_x, curr_y, line)
                    curr_y += line_height
                    lines_in_page += 1
                    
                painter.end()
                self.set_status_message(f"พิมพ์จุดเบรลล์จำลอง A4 (SimBraille) ขนาด {best_pt}pt สำเร็จ")
                speak_nvda("พิมพ์จุดเบรลล์จำลอง A4 สำเร็จ")
            except Exception as e:
                QMessageBox.critical(self, "ข้อผิดพลาด", f"เกิดข้อผิดพลาดในการพิมพ์จุดเบรลล์: {e}")

    def action_print_braille(self):
        """
        ส่งพิมพ์ไปยังเครื่องพิมพ์อักษรเบรลล์ (Braille Embosser) - ถอดแบบจากเมนู Braille (Ctrl+B) และ Form4 ใน Delphi
        รองรับ:
        1. เครื่องพิมพ์เบรลล์ที่ติดตั้งใน Windows (USB / Network SMB Share) แบบ RAW bytes
        2. พอร์ต LPT ดั้งเดิม
        3. การส่งออกเป็นไฟล์ .BRF
        """
        braille_text = self.txt_braille.toPlainText()
        if not braille_text.strip():
            QMessageBox.warning(self, "แจ้งเตือน", "ไม่มีข้อมูลอักษรเบรลล์ที่จะส่งพิมพ์ กรุณาแปลเอกสารก่อน (Ctrl+T)")
            return
            
        ascii_braille = self.translator.to_ascii_braille(braille_text) if not self.simbrl_font_loaded else braille_text
        
        # คำนวณจำนวนหน้า
        body_cap = max(1, self.page_length - 1)
        total_p = max(1, self.total_page if self.total_page > 0 else (len(ascii_braille.split('\n')) + body_cap - 1) // body_cap)
        
        dlg = BraillePrintingDialog(self, os.path.basename(self.current_filename), total_p)
        speak_nvda("หน้าต่างส่งพิมพ์อักษรเบรลล์")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            opts = dlg.get_print_options()
            target = opts["target"]
            copies = opts["copies"]
            is_all = opts["is_all"]
            p_from = opts["page_from"]
            p_to = opts["page_to"]
            
            # กรองเนื้อหาตามช่วงหน้า
            all_lines = ascii_braille.split('\n')
            if not is_all:
                start_line = (p_from - 1) * self.page_length
                end_line = p_to * self.page_length
                filtered_lines = all_lines[start_line:end_line]
                payload_text = '\n'.join(filtered_lines)
            else:
                payload_text = ascii_braille
                
            # เพิ่ม Form Feed ต่อท้ายตาม Page Advance ถ้าเปิดใช้งาน
            if self.page_advance == "Yes" and not payload_text.endswith('\x0c'):
                payload_text += '\x0c'
                
            # กรณี 1: บันทึกเป็นไฟล์ .BRF
            if target == "FILE_BRF":
                filename, _ = QFileDialog.getSaveFileName(
                    self, "บันทึกไฟล์เครื่องพิมพ์เบรลล์ (.BRF)", "document.brf", "Braille Formatted (*.brf);;All Files (*.*)"
                )
                if filename:
                    try:
                        with open(filename, 'w', encoding='ascii', errors='replace') as f:
                            for _ in range(copies):
                                f.write(payload_text)
                        msg = f"บันทึกไฟล์เบรลล์ {os.path.basename(filename)} เรียบร้อย"
                        self.set_status_message(msg)
                        QMessageBox.information(self, "สำเร็จ", msg)
                    except Exception as e:
                        QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถบันทึกไฟล์ได้: {e}")
                return
                
            # กรณี 2: ส่งออกพอร์ตขนาน LPT
            if target in ("LPT1", "LPT2"):
                try:
                    for _ in range(copies):
                        with open(f"\\\\.\\{target}", "wb") as f_lpt:
                            f_lpt.write(payload_text.encode("ascii", errors="replace"))
                    msg = f"ส่งข้อมูลเบรลล์ไปยังพอร์ต {target} สำเร็จ"
                    self.set_status_message(msg)
                    speak_nvda(msg)
                    QMessageBox.information(self, "สำเร็จ", msg)
                except Exception as e:
                    QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถเปิดพอร์ต {target} ได้: {e}\n(หากไม่มีพอร์ต LPT จริง กรุณาเลือกเครื่องพิมพ์ในระบบ)")
                return

            # กรณี 2.1: ส่งออกพอร์ตสื่อสารซีเรียล / USB Virtual COM
            if target.startswith("COM"):
                try:
                    for _ in range(copies):
                        with open(f"\\\\.\\{target}", "wb", buffering=0) as f_com:
                            f_com.write(payload_text.encode("ascii", errors="replace"))
                    msg = f"ส่งข้อมูลเบรลล์ไปยังพอร์ต {target} สำเร็จ"
                    self.set_status_message(msg)
                    speak_nvda(msg)
                    QMessageBox.information(self, "สำเร็จ", msg)
                except Exception as e:
                    QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถเปิดพอร์ต {target} ได้: {e}\n(หากไม่มีเครื่องต่อที่พอร์ต COM จริง กรุณาเลือกเครื่องพิมพ์ในระบบ)")
                return
                
            # กรณี 3: ส่งไปยังเครื่องพิมพ์ Windows (USB, SMB Network Share หรือ Generic / Text Only Driver)
            if win32print is not None:
                try:
                    p_handle = win32print.OpenPrinter(target)
                    job_info = ("TBTW Braille Document", None, "RAW")
                    for _ in range(copies):
                        win32print.StartDocPrinter(p_handle, 1, job_info)
                        win32print.StartPagePrinter(p_handle)
                        win32print.WritePrinter(p_handle, payload_text.encode("ascii", errors="replace"))
                        win32print.EndPagePrinter(p_handle)
                        win32print.EndDocPrinter(p_handle)
                    win32print.ClosePrinter(p_handle)
                    msg = f"ส่งงานพิมพ์เบรลล์ไปยัง {opts['target_name']} สำเร็จ ({copies} ชุด)"
                    self.set_status_message(msg)
                    speak_nvda(msg)
                    QMessageBox.information(self, "พิมพ์สำเร็จ", msg)
                except Exception as e:
                    QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถส่งงานพิมพ์ไปยังเครื่องพิมพ์ได้: {e}")
            else:
                QMessageBox.critical(self, "ข้อผิดพลาด", "ระบบไม่พบโมดูล win32print สำหรับการพิมพ์ RAW")

    def action_find(self):
        QMessageBox.information(self, "ค้นหา", "ฟังก์ชันค้นหาข้อความ (Ctrl+F)")

    def action_replace(self):
        QMessageBox.information(self, "แทนที่", "ฟังก์ชันค้นหาและแทนที่ข้อความ (Ctrl+R)")

    def choose_font(self):
        font, ok = QFontDialog.getFont(self.txt_normal.font(), self, "เลือก Font อักษรปกติ")
        if ok:
            self.txt_normal.setFont(font)
            self.lbl_status_msg.setText(f"เปลี่ยนฟอนต์เป็น {font.family()} สำเร็จ")

    def toggle_wordwrap(self, checked: bool):
        mode = QPlainTextEdit.LineWrapMode.WidgetWidth if checked else QPlainTextEdit.LineWrapMode.NoWrap
        self.txt_normal.setLineWrapMode(mode)
        self.txt_braille.setLineWrapMode(mode)
        msg = "เปิดการตัดคำขึ้นบรรทัดใหม่อัตโนมัติ" if checked else "ปิดการตัดคำขึ้นบรรทัดใหม่อัตโนมัติ"
        self.lbl_status_msg.setText(msg)

    def toggle_fullscreen(self):
        sb = self.statusBar()
        if self.isFullScreen():
            self.showNormal()
            if sb is not None:
                sb.showMessage("กลับสู่ขนาดหน้าต่างปกติ", 2000)
        else:
            self.showFullScreen()
            if sb is not None:
                sb.showMessage("แสดงผลแบบเต็มหน้าจอ (กด F11 อีกครั้งเพื่อออก)", 3000)

    def switch_window_focus(self):
        """กด F6 เพื่อสลับระหว่างกล่องข้อมูลเดิมและกล่องข้อมูลแปล พร้อมเสียงประกาศแก่ Screen Reader"""
        if self.txt_normal.hasFocus():
            self.txt_braille.setFocus()
            self.lbl_status_msg.setText("สลับไปยังกล่องข้อมูลแปล (Braille Font)")
        else:
            self.txt_normal.setFocus()
            self.lbl_status_msg.setText("สลับไปยังกล่องข้อมูลเดิม (Normal Font)")

    def open_page_setting(self):
        speak_nvda("เปิดหน้าต่างตั้งค่าหน้ากระดาษเบรลล์ Print Setup", interrupt=True)
        dlg = PageSettingDialog(self, self.line_length, self.page_length)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.line_length, self.page_length = dlg.get_settings()
            getattr(self.txt_braille, 'set_col_limit', lambda x: None)(self.line_length)
            self.lbl_col_limit.setText(f"Colume per lines: {self.line_length}")
            self.lbl_line_limit.setText(f"Lines per page: {self.page_length}")
            self.lbl_col_limit.setAccessibleName(f"ความกว้างคอลัมน์ต่อบรรทัด: {self.line_length}")
            self.lbl_line_limit.setAccessibleName(f"ความยาวบรรทัดต่อหน้า: {self.page_length}")
            self.on_text_changed()
            msg = f"ตั้งค่าหน้ากระดาษสำเร็จ: บรรทัดละ {self.line_length} เซลล์, หน้าละ {self.page_length} บรรทัด"
            self.lbl_status_msg.setText(msg)
            speak_nvda(msg, interrupt=True)
            
            # บันทึกลง SiamBraille.def
            try:
                def_path = get_resource_path("SiamBraille.def")
                if os.path.exists(def_path):
                    import struct
                    with open(def_path, 'r+b') as f_def:
                        b_def = bytearray(f_def.read())
                        if len(b_def) >= 8:
                            struct.pack_into('<II', b_def, 0, self.line_length, self.page_length)
                            f_def.seek(0)
                            f_def.write(b_def)
            except Exception:
                pass

    def open_tactile_graphics_dialog(self):
        """เปิดหน้าต่างสร้างสื่อภาพนูนสัมผัส แปลงภาพเป็นอักษรเบรลล์ (Ctrl+G)"""
        dlg = TactileGraphicsDialog(self)
        speak_nvda("เปิดหน้าต่างสร้างสื่อภาพนูนสัมผัสจากภาพ Tactile Graphics")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            braille_art = dlg.get_braille_text()
            if braille_art:
                curr = self.txt_braille.toPlainText()
                if curr and not curr.endswith('\n'):
                    curr += '\n\n'
                self.txt_braille.setPlainText(curr + braille_art)
                self.set_status_message("แทรกภาพจุดเบรลล์นูนสัมผัสลงในเอกสารสำเร็จ")
                speak_nvda("แทรกภาพจุดเบรลล์นูนสัมผัสลงในเอกสารสำเร็จ")

    def open_dot_converter_dialog(self):
        """เปิดเครื่องมือแปลงเป็นเลขตำแหน่งจุดเบรลล์ 1-6 (Ctrl+Shift+D)"""
        initial_text = ""
        focused_widget = QApplication.focusWidget()
        target_edit = self.txt_normal
        if focused_widget == self.txt_braille:
            target_edit = self.txt_braille
            cursor = self.txt_braille.textCursor()
            if cursor.hasSelection():
                initial_text = cursor.selectedText()
        else:
            cursor = self.txt_normal.textCursor()
            if cursor.hasSelection():
                initial_text = cursor.selectedText()

        dlg = BrailleDotConverterDialog(self, initial_text=initial_text, translator=self.translator)
        speak_nvda("เปิดเครื่องมือแปลงเป็นเลขจุดเบรลล์ 1 ถึง 6")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            if result:
                target_edit.insertPlainText(result)
                self.set_status_message("แทรกผลลัพธ์เลขจุดเบรลล์ลงในเอกสารแล้ว")
                speak_nvda("แทรกผลลัพธ์เลขจุดเบรลล์ลงในเอกสารแล้ว")

    def open_math_to_braille_dialog(self):
        """เปิดหน้าต่างแปลงสูตรคณิตศาสตร์เป็นอักษรเบรลล์ Math to Braille (Ctrl+Shift+M)"""
        initial_text = ""
        focused_widget = QApplication.focusWidget()
        target_edit = self.txt_normal
        if focused_widget == self.txt_braille:
            target_edit = self.txt_braille
            cursor = self.txt_braille.textCursor()
            if cursor.hasSelection():
                initial_text = cursor.selectedText()
        else:
            cursor = self.txt_normal.textCursor()
            if cursor.hasSelection():
                initial_text = cursor.selectedText()

        dlg = MathToBrailleDialog(self, initial_text=initial_text)
        speak_nvda("เปิดเครื่องมือแปลงสูตรคณิตศาสตร์เป็นอักษรเบรลล์ Math to Braille")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            if result:
                target_edit.insertPlainText(result)
                self.set_status_message("แทรกอักษรเบรลล์คณิตศาสตร์ลงในเอกสารสำเร็จ")
                speak_nvda("แทรกอักษรเบรลล์คณิตศาสตร์ลงในเอกสารสำเร็จ")

    def open_remote_input_dialog(self):
        """เปิดหน้าต่างระบบพิมพ์ผ่านมือถือในวง LAN (Ctrl+Shift+W)"""
        try:
            from lan_companion import LANCompanionServer, RemoteInputDialog
            server = self.lan_server
            if server is None:
                new_server = LANCompanionServer(port=8080)
                new_server.signals.text_received.connect(self.on_remote_text_received)
                started = new_server.start()
                if not started:
                    QMessageBox.warning(self, "เซิร์ฟเวอร์", "ไม่สามารถเริ่มเซิร์ฟเวอร์ในวง LAN ได้ พอร์ตอาจถูกใช้งานอยู่")
                    return
                self.lan_server = new_server
                server = new_server
            
            if server is not None:
                dlg = RemoteInputDialog(self, server)
                dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "ข้อผิดพลาด", f"ไม่สามารถเปิดระบบพิมพ์ผ่านอุปกรณ์อื่นได้: {e}")

    def on_remote_text_received(self, text: str, mode: str = "append"):
        """รับข้อความที่ส่งมาจากมือถือในวง LAN และแทรกลงในกล่องข้อความทันที"""
        if not text:
            return
        if mode == "append":
            cur = self.txt_normal.toPlainText()
            if cur and not cur.endswith('\n') and not cur.endswith(' '):
                self.txt_normal.appendPlainText(text)
            else:
                self.txt_normal.insertPlainText(text)
        elif mode == "replace":
            self.txt_normal.setPlainText(text)
        else:
            self.txt_normal.insertPlainText(text)

        preview = text.replace('\n', ' ')
        if len(preview) > 35:
            preview = preview[:35] + "..."
        self.set_status_message(f"ได้รับข้อความจากมือถือ: {preview}")
        speak_nvda(f"ได้รับข้อความจากมือถือแล้ว: {text}")

    def closeEvent(self, event):
        """ปิดการทำงานของ Background Server อย่างปลอดภัยเมื่อปิดหน้าต่าง"""
        server = getattr(self, 'lan_server', None)
        if server is not None and hasattr(server, 'stop'):
            try:
                server.stop()
            except Exception:
                pass
        super().closeEvent(event)

    def show_trial_expired_dialog(self):
        """แสดงหน้าต่างแจ้งเตือนเมื่อหมดอายุทดลองใช้ 14 วัน"""
        dlg = TrialExpiredDialog(self)
        dlg.exec()

    def show_buy_license(self):
        dlg = LicensePurchaseDialog(self)
        dlg.exec()

    def show_activate_license(self):
        dlg = LicenseActivationDialog(self)
        dlg.exec()

    def show_check_update(self):
        dlg = CheckUpdateDialog(self)
        dlg.exec()

    def update_license_ui(self):
        mgr = license_guard.global_license_manager
        mgr.check_local_license()
        self.update_title()

    def show_about(self):
        dlg = AboutBoxDialog(self)
        dlg.exec()

    def show_contact(self):
        QMessageBox.information(
            self,
            "ข้อมูลติดต่อและสนับสนุน",
            "SiamBraille 1.0 — Thai Braille Translation Software\n\n"
            "ระบบแปลและพิมพ์อักษรเบรลล์ภาษาไทยตามมาตรฐาน พ.ศ. 2564\n"
            "เว็บไซต์: siam-braille.web.app\n"
            "ฝ่ายดูแลระบบและสนับสนุนเทคนิค"
        )

    def show_help(self):
        QMessageBox.information(
            self,
            "วิธีการใช้โปรแกรมและคีย์ลัด",
            "คู่มือการใช้งานและคีย์ลัดสำหรับผู้ใช้ทั่วไปและผู้ใช้โปรแกรมอ่านจอภาพ (Screen Reader):\n\n"
            "1. พิมพ์หรือเปิดไฟล์ภาษาไทยที่กล่องข้อความฝั่งซ้าย (Normal Font)\n"
            "2. กด 'F6' เพื่อสลับระหว่างกล่องข้อความภาษาไทยปกติ และกล่องอักษรเบรลล์\n"
            "3. กด 'Ctrl+T' หรือคลิกปุ่ม 'แปล' เพื่อแปลเอกสารเป็นอักษรเบรลล์\n"
            "4. กด 'Ctrl+N' เพื่อเปิดไฟล์ใหม่, 'Ctrl+O' เพื่อเปิดไฟล์เก่า, 'Ctrl+S' เพื่อบันทึก\n"
            "5. กด 'Ctrl+B' เพื่อส่งออกไฟล์ .BRF สำหรับเครื่องพิมพ์เบรลล์\n"
            "6. กด 'Ctrl+P' เพื่อตั้งค่าหน้ากระดาษเบรลล์ (ความกว้าง/ความยาว)\n"
            "7. กด 'Alt+F' เข้าเมนู File, 'Alt+E' เข้าเมนู Edit, 'Alt+D' เข้าเมนู Default, 'Alt+H' เข้าเมนู Help\n"
            "8. แถบสถานะด้านล่างจะรายงานจำนวนหน้าและผลการแปลทันทีผ่านโปรแกรมอ่านจอภาพ"
        )


def main():
    # กำหนด AppUserModelID เพื่อให้ Windows 10/11 Taskbar แสดงไอคอนเฉพาะของ SiamBraille แทน Generic Python/Host Icon
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PhenphetK.SiamBraille.Professional.1.0")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app_icon = get_main_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    style = QStyleFactory.create("windowsvista") or QStyleFactory.create("windows") or QStyleFactory.create("Fusion")
    if style:
        app.setStyle(style)
        
    window = TBTWMainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.showMaximized()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
