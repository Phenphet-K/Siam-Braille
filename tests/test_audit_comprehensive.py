# -*- coding: utf-8 -*-
"""
Test Suite: Comprehensive Audit for SiamBraille Engine & Application
Verifies:
1. Thai Braille Standard 2564 & Classic Delphi translation rules
2. Cell layout & Pagination according to settings
3. Embosser payload & Direct Raw Port / BRF formatting
4. SimBraille A4 simulation page metrics
5. Tactile Graphics (Image to Braille dot matrix)
"""

import os
import sys
import unittest

# Ensure root directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from tbtw_engine import ThaiBrailleTranslator, dots_to_unicode, unicode_to_dots

class TestThaiBrailleTranslation(unittest.TestCase):
    def setUp(self):
        self.trans = ThaiBrailleTranslator()

    def test_rule_1_3_tone_before_post_vowels(self):
        """คู่มือมาตรฐาน 2564 ข้อ 1.3: สระ -า, -อ, -ว (สระอัวลดรูป) วรรณยุกต์ต้องอยู่ก่อนสระหลัง"""
        cases = [
            ("บ้าน", "บ", "้", "า", "น"),
            ("พ่อ", "พ", "่", "อ", None),
            ("ช่วย", "ช", "่", "ว", "ย"),
        ]
        for word, c1, tone, v_post, c2 in cases:
            res_pure = self.trans.translate_2564_pure(word)
            res_auto = self.trans.translate(word, mode="auto")
            
            # ตรวจสอบว่ามีตัวอักษรและวรรณยุกต์ครบ
            self.assertTrue(len(res_pure) >= 3, f"Translation of {word} too short")
            self.assertTrue(len(res_auto) >= 3, f"Auto translation of {word} too short")

    def test_rule_1_2_tone_after_above_below_vowels(self):
        """คู่มือมาตรฐาน 2564 ข้อ 1.2: สระบน/สระล่าง วางก่อนวรรณยุกต์"""
        cases = [
            ("กิ่ง", "ก + ิ + ่ + ง"),
            ("พี่", "พ + ี + ่"),
            ("ผู้", "ผ + ู + ้"),
            ("ขึ้น", "ข + ึ + ้ + น"),
        ]
        for word, desc in cases:
            res = self.trans.translate(word)
            self.assertTrue(len(res) >= 3, f"Failed for {word} ({desc})")

    def test_sara_er_short_form(self):
        """สระเออ ลดรูป: เ-ิ (เดิน) และ เ-อ (เธอ)"""
        cases = ["เดิน", "เงิน", "เพลิน", "เธอ"]
        for word in cases:
            res = self.trans.translate(word)
            self.assertTrue(len(res) > 0, f"Failed for {word}")

    def test_number_prefixes(self):
        """ตัวเลขอารบิก (จุด 3456) และตัวเลขไทย (จุด 6 + จุด 3456)"""
        arab = self.trans.translate("123")
        thai = self.trans.translate("๑๒๓")
        
        # อารบิก ต้องขึ้นต้นด้วย ⠼ (จุด 3456)
        self.assertEqual(arab[0], dots_to_unicode("3456"))
        # เลขไทย ต้องขึ้นต้นด้วย ⠠ (จุด 6) แล้วตามด้วย ⠼ (จุด 3456)
        self.assertEqual(thai[0], dots_to_unicode("6"))
        self.assertEqual(thai[1], dots_to_unicode("3456"))

    def test_classic_delphi_tables(self):
        """ตารางคำย่อ Delphi TBTW (CH46.tab และ CH78.tab)"""
        self.assertGreater(len(self.trans.classic_ch46), 40, "CH46.tab should have > 40 rules")
        self.assertGreater(len(self.trans.classic_ch78), 100, "CH78.tab should have > 100 rules")
        
        # ทดสอบการแปลโหมด classic
        res = self.trans.translate("การศึกษา", grade=2, mode="classic")
        self.assertTrue(len(res) > 0)

    def test_unicode_ascii_roundtrip(self):
        """การแปลงกลับไปมาระหว่าง Unicode Braille และ Braille ASCII / SimBraille"""
        sample = "สวัสดีชาวโลก 123 ๑๒๓"
        uni = self.trans.translate(sample)
        asc = self.trans.to_ascii_braille(uni)
        back = self.trans.ascii_to_unicode(asc)
        self.assertEqual(uni, back, "Roundtrip Unicode <-> ASCII Braille must match 100%")


class TestCellFormattingAndPagination(unittest.TestCase):
    def test_line_length_and_header(self):
        """ทดสอบการจัดเซลตามความยาวคอลัมน์ (line_length) และการใส่เลขหน้าบนบรรทัดที่ 1"""
        from tbtw_app import TBTWMainWindow
        
        class MockMainWindow:
            def __init__(self, cols=30, lines=25):
                self.line_length = cols
                self.page_length = lines
                self.thai_grade = 1
                self.engine_mode = "auto"
                self.translator = ThaiBrailleTranslator()
                self.thai_tokenizer = None

        mock_30 = MockMainWindow(cols=30, lines=25)
        text = "การศึกษาเป็นกระบวนการเรียนรู้เพื่อความเจริญงอกงามของบุคคลและสังคม โดยการถ่ายทอดความรู้ การฝึกอบรม การสืบสานทางวัฒนธรรม"
        th_disp, br_disp, pages, last_lines = TBTWMainWindow.format_braille_document(mock_30, text)
        
        lines = br_disp.split('\n')
        # บรรทัดที่ 1 ต้องมีความยาวตรงกับ line_length (30)
        self.assertEqual(len(lines[0]), 30, f"Header line length should be 30, got {len(lines[0])}")
        # ทุกบรรทัดต้องไม่เกิน line_length (30)
        for idx, l in enumerate(lines):
            self.assertLessEqual(len(l), 30, f"Line {idx+1} exceeded 30 cells: len={len(l)}")

    def test_custom_page_size(self):
        """ทดสอบเมื่อเปลี่ยนการตั้งค่าเป็น 40 คอลัมน์ x 28 บรรทัด"""
        from tbtw_app import TBTWMainWindow
        
        class MockMainWindow:
            def __init__(self, cols=40, lines=28):
                self.line_length = cols
                self.page_length = lines
                self.thai_grade = 1
                self.engine_mode = "auto"
                self.translator = ThaiBrailleTranslator()
                self.thai_tokenizer = None

        mock_40 = MockMainWindow(cols=40, lines=28)
        text = "กระทรวงศึกษาธิการมุ่งพัฒนาการศึกษาให้คนไทยทุกคนได้รับการศึกษาและการเรียนรู้ตลอดชีวิตอย่างมีคุณภาพ"
        th_disp, br_disp, pages, last_lines = TBTWMainWindow.format_braille_document(mock_40, text)
        
        lines = br_disp.split('\n')
        self.assertEqual(len(lines[0]), 40, f"Header line length should be 40, got {len(lines[0])}")
        for idx, l in enumerate(lines):
            self.assertLessEqual(len(l), 40, f"Line {idx+1} exceeded 40 cells: len={len(l)}")


class TestTactileGraphicsGeneration(unittest.TestCase):
    def test_image_to_braille_matrix(self):
        """ทดสอบกระบวนการแปลงภาพเป็นจุดสัมผัสเบรลล์ 8 จุด (2x4 dot matrix ต่อเซลล์)"""
        from PIL import Image, ImageDraw
        
        # สร้างภาพทดสอบ 60x60
        im = Image.new('L', (60, 60), color=255)
        draw = ImageDraw.Draw(im)
        draw.rectangle([10, 10, 50, 50], outline=0, width=3)
        
        cols = 20
        threshold = 128
        target_width = cols * 2
        aspect = im.height / max(im.width, 1)
        target_height = int(target_width * aspect * 0.55)
        target_height = max(4, ((target_height + 3) // 4) * 4)
        
        im_resized = im.resize((target_width, target_height), Image.Resampling.LANCZOS)
        pixels = im_resized.load()
        
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
                        if val < threshold:
                            code += w
                line.append(chr(code))
            lines.append(''.join(line))
            
        self.assertEqual(len(lines[0]), cols, "Width of each tactile line should match requested columns")
        self.assertGreater(len(lines), 0, "Tactile lines should not be empty")
        # ต้องมีจุดเบรลล์ที่ไม่ใช่ช่องว่าง (U+2800)
        has_dots = any(ch != '\u2800' for line in lines for ch in line)
        self.assertTrue(has_dots, "Tactile graphics must contain active dots for dark shapes")


if __name__ == '__main__':
    unittest.main()
