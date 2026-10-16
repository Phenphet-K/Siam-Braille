# -*- coding: utf-8 -*-
"""
SiamBraille Engine - Thai Braille Translation System
ออกแบบตามคู่มือมาตรฐานการใช้อักษรเบรลล์ในประเทศไทย ฉบับปรับปรุง พ.ศ. 2564
พร้อมระบบคำย่อระดับ 2 และการจัดหน้าตามมาตรฐานสากล
"""

import os
import sys
import ctypes
from typing import Optional, List, Tuple

# ---------------------------------------------------------------------------
# 1. Unicode Braille Utility (U+2800 .. U+28FF)
# ---------------------------------------------------------------------------

def dots_to_unicode(dots_str: str) -> str:
    """
    แปลงสตริงจุด เช่น '1245' หรือ '1-2-4-5' หรือหลายเซลล์ '156-2'
    เป็น Unicode Braille characters
    """
    if not dots_str or dots_str == '0':
        return '\u2800'
    
    cells = dots_str.split('-') if '-' in dots_str and not dots_str.startswith('-') else [dots_str]
    res = []
    for cell in cells:
        mask = 0
        for ch in cell:
            if ch.isdigit():
                d = int(ch)
                if 1 <= d <= 6:
                    mask |= (1 << (d - 1))
        res.append(chr(0x2800 + mask))
    return "".join(res)

def unicode_to_dots(char: str) -> List[int]:
    """แปลงอักขระ Unicode Braille เป็นรายการจุด เช่น '⠛' -> [1, 2, 4, 5]"""
    code = ord(char)
    if code < 0x2800 or code > 0x28FF:
        return []
    mask = code - 0x2800
    return [i for i in range(1, 7) if mask & (1 << (i - 1))]

# ---------------------------------------------------------------------------
# 2. Braille ASCII / SimBraille Mapping (North American Braille ASCII)
# ---------------------------------------------------------------------------
BRAILLE_ASCII_MAP = {
    ' ': '\u2800',
    '!': '\u282E', '"': '\u2808', '#': '\u283C', '$': '\u282B', '%': '\u2829',
    '&': '\u282F', "'": '\u2804', '(': '\u2837', ')': '\u283E', '*': '\u2821',
    '+': '\u282C', ',': '\u2820', '-': '\u2824', '.': '\u2828', '/': '\u280C',
    '0': '\u2834', '1': '\u2802', '2': '\u2806', '3': '\u2812', '4': '\u2832',
    '5': '\u2822', '6': '\u2816', '7': '\u2836', '8': '\u2826', '9': '\u2814',
    ':': '\u2831', ';': '\u2830', '<': '\u2823', '=': '\u283F', '>': '\u281C',
    '?': '\u2839', '@': '\u2808',
    'A': '\u2801', 'B': '\u2803', 'C': '\u2809', 'D': '\u2819', 'E': '\u2811',
    'F': '\u280B', 'G': '\u281B', 'H': '\u2813', 'I': '\u280A', 'J': '\u281A',
    'K': '\u2805', 'L': '\u2807', 'M': '\u280D', 'N': '\u281D', 'O': '\u2815',
    'P': '\u280F', 'Q': '\u281F', 'R': '\u2817', 'S': '\u280E', 'T': '\u281E',
    'U': '\u2825', 'V': '\u2827', 'W': '\u283A', 'X': '\u282D', 'Y': '\u283D', 'Z': '\u2835',
    '[': '\u282A', '\\': '\u2833', ']': '\u283B', '^': '\u2818', '_': '\u2838',
    '{': '\u282A', '|': '\u2833', '}': '\u283B', '~': '\u283D',
    'a': '\u2801', 'b': '\u2803', 'c': '\u2809', 'd': '\u2819', 'e': '\u2811',
    'f': '\u280B', 'g': '\u281B', 'h': '\u2813', 'i': '\u280A', 'j': '\u281A',
    'k': '\u2805', 'l': '\u2807', 'm': '\u280D', 'n': '\u281D', 'o': '\u2815',
    'p': '\u280F', 'q': '\u281F', 'r': '\u2817', 's': '\u280E', 't': '\u281E',
    'u': '\u2825', 'v': '\u2827', 'w': '\u283A', 'x': '\u282D', 'y': '\u283D', 'z': '\u2835',
}

UNICODE_TO_ASCII = {v: k for k, v in BRAILLE_ASCII_MAP.items()}

# ASCII to Dots lookup
ASCII_TO_DOTS = {
    ' ': '0', '!': '2346', '"': '5', '#': '3456', '$': '1246', '%': '146',
    '&': '12346', "'": '3', '(': '12356', ')': '23456', '*': '16',
    '+': '346', ',': '6', '-': '36', '.': '46', '/': '34',
    '0': '356', '1': '2', '2': '23', '3': '25', '4': '256',
    '5': '26', '6': '235', '7': '2356', '8': '236', '9': '35',
    ':': '156', ';': '56', '<': '126', '=': '123456', '>': '345',
    '?': '1456', '@': '4',
    'a': '1', 'b': '12', 'c': '14', 'd': '145', 'e': '15',
    'f': '124', 'g': '1245', 'h': '125', 'i': '24', 'j': '245',
    'k': '13', 'l': '123', 'm': '134', 'n': '1345', 'o': '135',
    'p': '1234', 'q': '12345', 'r': '1235', 's': '234', 't': '2345',
    'u': '136', 'v': '1236', 'w': '2456', 'x': '1346', 'y': '13456', 'z': '1356',
    '[': '246', '\\': '1256', ']': '12456', '^': '45', '_': '456'
}

DOTS_TO_ASCII = {v: k for k, v in ASCII_TO_DOTS.items()}

# ---------------------------------------------------------------------------
# 3. Thai Braille Standard 2564 Mapping (คู่มือมาตรฐาน พ.ศ. 2564 & th-g0.utb)
# ---------------------------------------------------------------------------

# พยัญชนะ 44 ตัว (อักษรเดียวหรือ 2 เซลล์)
THAI_CONSONANTS_DOTS = {
    'ก': '1245',
    'ข': '13',
    'ฃ': '356-13',
    'ค': '136',
    'ฅ': '36-136',
    'ฆ': '6-136',
    'ง': '12456',
    'จ': '245',
    'ฉ': '34',
    'ช': '346',
    'ซ': '2346',
    'ฌ': '6-346',
    'ญ': '6-13456',
    'ฎ': '6-145',
    'ฏ': '6-1256',
    'ฐ': '6-2345',
    'ฑ': '6-23456',
    'ฒ': '36-23456',
    'ณ': '6-1345',
    'ด': '145',
    'ต': '1256',
    'ถ': '2345',
    'ท': '23456',
    'ธ': '356-23456',
    'น': '1345',
    'บ': '1236',
    'ป': '12346',
    'ผ': '1234',
    'ฝ': '1346',
    'พ': '1456',
    'ฟ': '1246',
    'ภ': '6-1456',
    'ม': '134',
    'ย': '13456',
    'ร': '1235',
    'ฤ': '1235-2',
    'ฤๅ': '1235-2-5-16',
    'ล': '123',
    'ฦ': '123-2',
    'ฦๅ': '123-2-5-16',
    'ว': '2456',
    'ศ': '6-234',
    'ษ': '36-234',
    'ส': '234',
    'ห': '125',
    'ฬ': '6-123',
    'อ': '135',
    'ฮ': '123456',
}

# สระและเครื่องหมาย
THAI_VOWELS_DOTS = {
    'ะ': '1',
    'ั': '345',
    '็': '3',
    'า': '16',
    'ิ': '12',
    'ี': '23',
    'ุ': '14',
    'ู': '25',
    'ึ': '246',
    'ื': '26',
    'เ': '124',
    'แ': '126',
    'โ': '24',
    'ำ': '1356',
    'ไ': '156',
    'ใ': '156-2',
    'ๆ': '2',
    '์': '356',
    'ฯ': '56-23',
    'ฺ': '3',      # พินทุ
    'ํ': '5',      # นฤคหิต
    '฿': '4-12',   # บาท
    'ๅ': '5-16',   # ลากข้างยาว
    'อ': '135',    # สระออ (เมื่อทำหน้าที่เป็นสระหลังพยัญชนะต้น)
}

# วรรณยุกต์
THAI_TONES_DOTS = {
    '่': '35',    # ไม้เอก
    '้': '256',   # ไม้โท
    '๊': '2356',  # ไม้ตรี
    '๋': '236',   # ไม้จัตวา
}

# ตัวเลข
NUMBER_SIGN = '3456'       # ⠼ (อารบิก)
THAI_NUMBER_SIGN = '6-3456' # ⠠⠼ (ไทย)

DIGIT_DOTS = {
    '1': '1', '2': '12', '3': '14', '4': '145', '5': '15',
    '6': '124', '7': '1245', '8': '125', '9': '24', '0': '245'
}

THAI_TO_ARABIC_DIGIT = {
    '๑': '1', '๒': '2', '๓': '3', '๔': '4', '๕': '5',
    '๖': '6', '๗': '7', '๘': '8', '๙': '9', '๐': '0'
}


# ---------------------------------------------------------------------------
# 4. LibLouis 64-bit Direct Integration
# ---------------------------------------------------------------------------

def get_resource_path(name: str) -> str:
    """ค้นหาไฟล์ resource ในโฟลเดอร์รันไทม์ทั้งหมด ทั้งโหมดสคริปต์, โหมด exe ใน dist และ _internal แบบไม่ขึ้นกับ drive letter หรือ architecture"""
    candidate_dirs = []
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        candidate_dirs.append(exe_dir)
        candidate_dirs.append(os.path.join(exe_dir, "_internal"))
        candidate_dirs.append(getattr(sys, '_MEIPASS', ''))
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_dirs.append(base_dir)
    candidate_dirs.append(os.path.join(base_dir, "_internal"))
    candidate_dirs.append(os.path.join(base_dir, "dist", "SiamBraille"))
    candidate_dirs.append(os.path.join(base_dir, "dist", "SiamBraille", "_internal"))
    candidate_dirs.append(os.path.join(base_dir, "dist", "TBTW3"))
    candidate_dirs.append(os.path.join(base_dir, "dist", "TBTW3", "_internal"))
    
    for d in candidate_dirs:
        if d and os.path.exists(d):
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    return os.path.join(base_dir, name)


class LibLouisBridge:
    """เชื่อมต่อกับ LibLouis DLL ประจำโฟลเดอร์โครงการ (Standalone - รองรับทั้ง 32-bit และ 64-bit)"""
    def __init__(self, dll_path: Optional[str] = None, tables_path: Optional[str] = None):
        self.available = False
        self.louis = None
        
        is_64bit = sys.maxsize > 2**32
        dll_candidates = ["liblouis64.dll", "liblouis.dll", "liblouis32.dll"] if is_64bit else ["liblouis32.dll", "liblouis.dll", "liblouis64.dll"]
        
        target_dll = dll_path
        if not target_dll:
            for cand in dll_candidates:
                p = get_resource_path(cand)
                if os.path.exists(p):
                    target_dll = p
                    break
        if not target_dll or not os.path.exists(target_dll):
            return
            
        target_tables = tables_path or get_resource_path("Tables")
        if not os.path.exists(target_tables):
            return
            
        self.tables_path = target_tables
        
        try:
            self.louis = ctypes.cdll.LoadLibrary(target_dll)
            self.louis.lou_translateString.argtypes = [
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.POINTER(ctypes.c_int),
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.c_int
            ]
            self.louis.lou_translateString.restype = ctypes.c_int
            self.available = True
        except Exception as e:
            self.available = False

    def translate(self, text: str, grade: int = 1) -> Optional[str]:
        """
        แปลข้อความผ่าน LibLouis
        grade=1 -> th-g0.utb (Thai Braille Grade 1 ระดับ 1 ตัวเต็ม)
        grade=2 -> th-g1.utb (Thai Braille Grade 2 ระดับ 2 คำย่อ/ลดรูป)
        คืนค่าเป็น Braille ASCII string
        """
        if not self.available or not self.louis or not text:
            return None
            
        # th-g1.utb = Grade 1/2 Standard Thai Literary Braille (มาตรฐานการใช้อักษรเบรลล์ในประเทศไทย ฉบับปรับปรุง พ.ศ. 2564)
        # th-g0.utb = Grade 0 (Uncontracted - ตัวเต็มตามตัวอักษร)
        table_name = "th-g0.utb" if grade == 0 else "th-g1.utb"
        table_path = os.path.join(self.tables_path, table_name).replace("\\", "/")
        
        in_arr = (ctypes.c_uint32 * (len(text) + 1))(*[ord(c) for c in text])
        in_len = ctypes.c_int(len(text))
        max_out = max(1024, len(text) * 4)
        out_arr = (ctypes.c_uint32 * max_out)()
        out_len = ctypes.c_int(max_out)
        
        try:
            ret = self.louis.lou_translateString(
                table_path.encode('utf-8'),
                in_arr,
                ctypes.byref(in_len),
                out_arr,
                ctypes.byref(out_len),
                None,
                None,
                0
            )
            if ret:
                chars = [out_arr[i] for i in range(out_len.value)]
                return "".join(chr(c) for c in chars)
        except Exception:
            return None
        return None


# ---------------------------------------------------------------------------
# 5. Master Thai Braille Translator (TBTW Engine Version 3.00)
# ---------------------------------------------------------------------------

class ThaiBrailleTranslator:
    """
    ระบบแปลภาษาไทยเป็นอักษรเบรลล์ รองรับทั้ง TBTW Classic และ มาตรฐาน พ.ศ. 2564
    """
    def __init__(self, grade: int = 1, engine_mode: str = "auto"):
        self.grade = grade  # 1 = ระดับ 1 (เต็ม), 2 = ระดับ 2 (ย่อ)
        self.engine_mode = engine_mode  # 'auto', 'liblouis', 'classic', 'pure_python'
        
        # 1. โหลด LibLouis bridge
        self.liblouis = LibLouisBridge()
        
        # 2. โหลดตารางคำย่อ TBTW ดั้งเดิม (CH46.tab, CH78.tab)
        self.classic_ch46 = {}
        self.classic_ch78 = {}
        self.load_classic_tables()

    def load_classic_tables(self):
        """โหลดตารางคำย่อ Delphi TBTW ดั้งเดิม (CH46.tab และ CH78.tab)"""
        ch46_path = get_resource_path("CH46.tab")
        ch78_path = get_resource_path("CH78.tab")
        
        if os.path.exists(ch46_path):
            try:
                with open(ch46_path, 'rb') as f:
                    content = f.read().decode('cp874', errors='replace')
                    for line in content.splitlines():
                        if '=' in line:
                            th, brl = line.split('=', 1)
                            self.classic_ch46[th.strip()] = brl.strip()
            except Exception:
                pass
                
        if os.path.exists(ch78_path):
            try:
                with open(ch78_path, 'rb') as f:
                    content = f.read().decode('cp874', errors='replace')
                    for line in content.splitlines():
                        if '=' in line:
                            th, brl = line.split('=', 1)
                            self.classic_ch78[th.strip()] = brl.strip()
            except Exception:
                pass

    def translate(self, text: str, grade: Optional[int] = None, mode: Optional[str] = None) -> str:
        """
        แปลข้อความภาษาไทยเป็น Braille Unicode (และแปลงต่อเป็น SimBraille ได้)
        """
        if not text:
            return ""
            
        g = self.grade if grade is None else grade
        m = self.engine_mode if mode is None else mode
        
        # กรณีเลือกโหมด 'auto' หรือ 'liblouis' และมี LibLouis พร้อม
        if m in ('auto', 'liblouis') and self.liblouis.available:
            ascii_res = self.liblouis.translate(text, grade=g)
            if ascii_res is not None:
                return self.ascii_to_unicode(ascii_res)
                
        # กรณีเลือกโหมด Classic (ใช้ CH46/CH78 ร่วมกับกฎเดิม)
        if m == 'classic':
            return self.translate_classic(text, grade=g)
            
        # Fallback: Pure Python 2564 Engine
        return self.translate_2564_pure(text, grade=g)

    def translate_classic(self, text: str, grade: int = 1) -> str:
        """แปลด้วยระบบ TBTW Classic ดั้งเดิม พร้อมแทนที่คำย่อจาก CH78 และ CH46"""
        working_text = text
        ascii_tokens = []
        
        # ถ้าเป็นระดับ 2 ตรวจแทนที่กลุ่มคำตาม CH78.tab ก่อน (คำประสมยาว)
        if grade == 2 and self.classic_ch78:
            for th_word, brl in sorted(self.classic_ch78.items(), key=lambda x: len(x[0]), reverse=True):
                if th_word in working_text:
                    working_text = working_text.replace(th_word, f"«{brl}»")
                    
        # ตรวจแทนที่คำเดี่ยวตาม CH46.tab
        if grade == 2 and self.classic_ch46:
            for th_word, brl in sorted(self.classic_ch46.items(), key=lambda x: len(x[0]), reverse=True):
                if th_word in working_text:
                    working_text = working_text.replace(th_word, f"«{brl}»")

        # นำส่วนที่เหลือเข้ากระบวนการแปลระดับ 1
        res = []
        parts = working_text.split("«")
        for part in parts:
            if "»" in part:
                brl_code, rest = part.split("»", 1)
                res.append(self.ascii_to_unicode(brl_code))
                if rest:
                    res.append(self.translate_2564_pure(rest, grade=1))
            else:
                res.append(self.translate_2564_pure(part, grade=1))
                
        return "".join(res)

    def translate_2564_pure(self, text: str, grade: int = 1) -> str:
        """
        ระบบแปลภาษาไทยตามคู่มือมาตรฐาน พ.ศ. 2564 แบบ Pure Python (ไม่พึ่ง LibLouis)
        ถูกต้องตามกฎ:
        1. สระหน้า (เ, แ, โ, ใ, ไ) วางหน้าพยัญชนะ
        2. สระบน/ล่าง วางหลังพยัญชนะ
        3. กฎข้อ 1.3: สระ -า, -อ และ -ว (สระอัวลดรูป) วางหลังวรรณยุกต์ (บ้าน, พ่อ, ช่วย)
        4. สระเออ และข้อยกเว้น
        5. สระพิเศษ: อำ, ไอ, ใอ, ฤ, ฤๅ
        6. เลขไทยจุด 6 นำหน้าเครื่องหมายเลข
        """
        result = []
        i = 0
        n = len(text)
        in_arabic_num = False
        in_thai_num = False
        
        while i < n:
            ch = text[i]
            
            # ช่องว่าง / เอนเทอร์
            if ch == ' ':
                result.append('\u2800')
                in_arabic_num = False
                in_thai_num = False
                i += 1
                continue
            elif ch == '\n':
                result.append('\n')
                in_arabic_num = False
                in_thai_num = False
                i += 1
                continue
            elif ch == '\r':
                i += 1
                continue
                
            # ตัวเลขอารบิก
            if ch in DIGIT_DOTS:
                if not in_arabic_num:
                    result.append(dots_to_unicode(NUMBER_SIGN))
                    in_arabic_num = True
                result.append(dots_to_unicode(DIGIT_DOTS[ch]))
                i += 1
                continue
            else:
                in_arabic_num = False
                
            # ตัวเลขไทย
            if ch in THAI_TO_ARABIC_DIGIT:
                if not in_thai_num:
                    result.append(dots_to_unicode(THAI_NUMBER_SIGN))
                    in_thai_num = True
                arab = THAI_TO_ARABIC_DIGIT[ch]
                result.append(dots_to_unicode(DIGIT_DOTS[arab]))
                i += 1
                continue
            else:
                in_thai_num = False
                
            # สระหน้า (เ-, แ-, โ-, ใ-, ไ-)
            if ch in ('เ', 'แ', 'โ', 'ใ', 'ไ'):
                # ตรวจสอบข้อยกเว้น สระเออ ลดรูปในระดับ 1 และ 2 (Grade 1 with some short form)
                # เช่น เ-ิ + ตัวสะกด (เดิม, เดิน) -> พยัญชนะ + สระเออลดรูป (จุด 1-4-6 / %)
                if grade >= 1 and ch == 'เ' and (i + 2) < n and text[i+1] in THAI_CONSONANTS_DOTS and text[i+2] == 'ิ':
                    cons = text[i+1]
                    result.append(dots_to_unicode(THAI_CONSONANTS_DOTS[cons]))
                    result.append(dots_to_unicode('146')) # สระเออลดรูป
                    i += 3
                    continue
                # สระเออ ไม่มีตัวสะกด เช่น เธอ, เสนอ, ละเมอ
                if grade >= 1 and ch == 'เ' and (i + 2) < n and text[i+1] in THAI_CONSONANTS_DOTS and text[i+2] == 'อ':
                    cons = text[i+1]
                    result.append(dots_to_unicode(THAI_CONSONANTS_DOTS[cons]))
                    result.append(dots_to_unicode('146')) # สระเออลดรูป
                    i += 3
                    continue
                    
                # ทั่วไป: สระหน้าวางนำหน้าพยัญชนะ
                result.append(dots_to_unicode(THAI_VOWELS_DOTS[ch]))
                i += 1
                continue
                
            # พยัญชนะต้น
            if ch in THAI_CONSONANTS_DOTS:
                cons_code = THAI_CONSONANTS_DOTS[ch]
                result.append(dots_to_unicode(cons_code))
                i += 1
                
                # อ่านสระและวรรณยุกต์ที่เกาะกับพยัญชนะนี้
                above_below_vowel = None
                tone_mark = None
                post_vowel = None
                
                while i < n:
                    nxt = text[i]
                    if nxt in ('ิ', 'ี', 'ึ', 'ื', 'ุ', 'ู', 'ั', '็', '์'):
                        above_below_vowel = THAI_VOWELS_DOTS[nxt]
                        i += 1
                    elif nxt in THAI_TONES_DOTS:
                        tone_mark = THAI_TONES_DOTS[nxt]
                        i += 1
                    elif nxt in ('า', 'อ', 'ำ', 'ะ', 'ๅ'):
                        post_vowel = THAI_VOWELS_DOTS[nxt]
                        i += 1
                        break
                    elif nxt == 'ว' and above_below_vowel == THAI_VOWELS_DOTS['ั']:
                        # สระอัว ( -ัว ) เช่น วัว, ตัว
                        # ในเบรลล์: ว ถือเป็นส่วนสระอัว
                        post_vowel = THAI_CONSONANTS_DOTS['ว']
                        i += 1
                        break
                    else:
                        break
                        
                # -------------------------------------------------------------
                # จัดเรียงตามกฎคู่มือมาตรฐาน 2564 ข้อ 1.2 และ 1.3:
                # -------------------------------------------------------------
                # ก) สระบน/ล่าง ( -ิ, -ี, -ึ, -ื, -ุ, -ู, -ั, -็, -์ ) มาก่อนวรรณยุกต์
                if above_below_vowel:
                    result.append(dots_to_unicode(above_below_vowel))
                    
                # ข) วรรณยุกต์ (เอก โท ตรี จัตวา)
                # ข้อ 1.3: ถ้ามีสระ -า, -อ, หรือ -ว (สระอัวลดรูป เช่น ช่วย)
                # วรรณยุกต์จะต้องวางไว้ *ก่อน* สระหลังเหล่านี้!
                if tone_mark:
                    result.append(dots_to_unicode(tone_mark))
                    
                # ค) สระหลัง (-า, -อ, -ำ, -ะ)
                if post_vowel:
                    result.append(dots_to_unicode(post_vowel))
                    
                continue
                
            # ตัวอักษรภาษาอังกฤษ (English Braille UEB)
            if 'a' <= ch <= 'z':
                result.append(dots_to_unicode(ASCII_TO_DOTS[ch]))
                i += 1
                continue
            elif 'A' <= ch <= 'Z':
                # เครื่องหมายตัวพิมพ์ใหญ่ (Capital indicator = จุด 6)
                result.append(dots_to_unicode('6'))
                result.append(dots_to_unicode(ASCII_TO_DOTS[ch.lower()]))
                i += 1
                continue

            # สระเดี่ยวๆ หรือเครื่องหมายวรรคตอน
            if ch in THAI_VOWELS_DOTS:
                result.append(dots_to_unicode(THAI_VOWELS_DOTS[ch]))
                i += 1
                continue
            elif ch in THAI_TONES_DOTS:
                result.append(dots_to_unicode(THAI_TONES_DOTS[ch]))
                i += 1
                continue
            elif ch in BRAILLE_ASCII_MAP:
                result.append(BRAILLE_ASCII_MAP[ch])
                i += 1
                continue
            else:
                # ตัวอักขระพิเศษอื่นๆ
                i += 1
                
        return "".join(result)

    def to_ascii_braille(self, unicode_braille: str) -> str:
        """แปลง Unicode Braille เป็น SimBraille / Braille ASCII string"""
        res = []
        for ch in unicode_braille:
            if ch in ('\n', '\r', '\t'):
                res.append(ch)
            else:
                res.append(UNICODE_TO_ASCII.get(ch, ' '))
        return "".join(res)

    def ascii_to_unicode(self, ascii_str: str) -> str:
        """แปลง Braille ASCII string เป็น Unicode Braille"""
        res = []
        for ch in ascii_str:
            if ch in ('\n', '\r', '\t'):
                res.append(ch)
            else:
                res.append(BRAILLE_ASCII_MAP.get(ch, '\u2800'))
        return "".join(res)
