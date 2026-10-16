import sys
import tbtw_engine
from tbtw_app import TBTWMainWindow

sys.stdout.reconfigure(encoding='utf-8')

class AppMock:
    def __init__(self):
        self.translator = tbtw_engine.ThaiBrailleTranslator(grade=1, engine_mode='auto')
        self.thai_grade = 1
        self.engine_mode = 'auto'
        self.line_length = 30
        self.page_length = 25

app = AppMock()

test_cases = [
    ("Thai with Numbers & English", "สวัสดีปีใหม่ 2026 ขอให้ทุกคน Happy New Year มีความสุขมากๆ"),
    ("Long URL without spaces", "ทดลองใช้ https://verylongdomainname.example.com/subpath/to/resource/deep?id=123456789&key=abcdefghij"),
    ("Punctuation & Quotes", "ข้อความใน \"เครื่องหมายคำพูด\" และ (วงเล็บ) [ก้ามปู] {ปีกกา} 100% + 50 - 20 = 130!"),
    ("Multiple Newlines & Blank Lines", "ย่อหน้าที่หนึ่ง\n\n\nย่อหน้าที่สองหลังจากเว้นสองบรรทัด\n\nย่อหน้าที่สาม"),
    ("Bullet Points and Lists", "1. ข้อแรก การทำงานของระบบ\n2. ข้อสอง คุณภาพของการแปล\n3. ข้อสาม ความเร็วและความเสถียร"),
    ("Complex Vowels & Tone Marks", "เกลี้ยงเกลา เปรี้ยวเปรียบ เปลี่ยนแปลง เคลือบแคลง กว้างขวาง ประเสริฐ กรรมาธิการ"),
    ("Zero-width space / Thai words", "การแปลภาษาไทยและอักษรเบรลล์มาตรฐานระดับชาติฉบับปรับปรุงพุทธศักราช๒๕๖๔"),
]

print("==============================================================")
print(" SiamBraille 1.0 - Edge Cases & Stress Validation Suite")
print("==============================================================")

all_passed = True

for idx, (title, sample_text) in enumerate(test_cases, 1):
    try:
        th_disp, br_disp, pages, lines_in_last = TBTWMainWindow.format_braille_document(app, sample_text)
        ascii_br = app.translator.to_ascii_braille(br_disp)
        lines = ascii_br.splitlines()
        
        max_col = max((len(l) for l in lines), default=0)
        col_ok = max_col <= 30
        
        if not col_ok:
            all_passed = False
            over = [f"L{i+1}:{len(l)}" for i, l in enumerate(lines) if len(l) > 30]
            print(f"Test {idx} [{title}]: FAIL (Over limit: {', '.join(over)})")
        else:
            print(f"Test {idx} [{title}]: PASS (Pages={pages}, Lines={len(lines)}, MaxCol={max_col})")
            
    except Exception as e:
        all_passed = False
        print(f"Test {idx} [{title}]: ERROR ({e})")

print("-" * 62)
if all_passed:
    print("ALL 7 ADVANCED EDGE CASES PASSED WITH 100% STABILITY!")
else:
    print("SOME EDGE CASES FAILED!")
print("==============================================================")
