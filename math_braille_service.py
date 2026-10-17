# -*- coding: utf-8 -*-
"""
Math to Braille Service (MathCAT Engine Integration)
แปลงสูตรคณิตศาสตร์และสมการวิทยาศาสตร์ (LaTeX / MathML / ธรรมดา)
เป็นอักษรเบรลล์คณิตศาสตร์มาตรฐาน Nemeth Code และ UEB Math
พร้อมคำอ่านออกเสียง (Speech) และเลขตำแหน่งจุดเบรลล์
"""

import os
import sys
import ctypes
import re
from typing import Dict, Any, Optional

try:
    from latex2mathml.converter import convert as latex_to_mathml
except ImportError:
    latex_to_mathml = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ตารางจับคู่ Unicode Braille (0x2800) ไปยัง SimBraille Font ASCII
UNICODE_TO_SIMBRAILLE_ASCII = (
    " A1B'K2L@CIF/MSP\"E3H9O6R^DJG>NTQ,*5<-U8V.%[$+X!&;:4\\0Z7(_?W]#Y)="
)

class MathCATService:
    _instance = None
    _lib = None
    _is_initialized = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._init_dll()

    def _init_dll(self):
        if self._is_initialized and self._lib:
            return

        # ค้นหา DLL
        possible_dll_paths = [
            os.path.join(BASE_DIR, "libMathCat64.dll"),
            os.path.join(BASE_DIR, "tools", "decompile", "SMB25.5.5", "libMathCat64.dll"),
            os.path.join(BASE_DIR, "dist", "SiamBraille", "libMathCat64.dll"),
        ]

        dll_path = None
        for p in possible_dll_paths:
            if os.path.exists(p):
                dll_path = os.path.abspath(p)
                break

        if not dll_path:
            print("[MathCAT] ไม่พบไฟล์ libMathCat64.dll")
            return

        # ค้นหา Rules
        possible_rules = [
            os.path.join(BASE_DIR, "data", "Rules"),
            os.path.join(BASE_DIR, "Rules"),
            os.path.join(BASE_DIR, "tools", "decompile", "SMB25.5.5", "Rules"),
            os.path.join(BASE_DIR, "dist", "SiamBraille", "data", "Rules"),
        ]

        rules_dir = None
        for r in possible_rules:
            if os.path.exists(r) and os.path.isdir(r):
                rules_dir = os.path.abspath(r)
                break

        try:
            self._lib = ctypes.CDLL(dll_path)

            self._lib.GetMathCATVersion.restype = ctypes.c_char_p
            self._lib.SetRulesDir.argtypes = [ctypes.c_char_p]
            self._lib.SetRulesDir.restype = ctypes.c_char_p

            self._lib.SetPreference.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            self._lib.SetPreference.restype = ctypes.c_char_p

            self._lib.SetMathML.argtypes = [ctypes.c_char_p]
            self._lib.SetMathML.restype = ctypes.c_char_p

            self._lib.GetBraille.argtypes = [ctypes.c_char_p]
            self._lib.GetBraille.restype = ctypes.c_char_p

            self._lib.GetSpokenText.restype = ctypes.c_char_p
            self._lib.GetError.restype = ctypes.c_char_p

            if rules_dir:
                res = self._lib.SetRulesDir(rules_dir.encode("utf-8"))
                res_str = res.decode("utf-8") if res else ""
                if res_str.lower() != "ok":
                    err = self._lib.GetError()
                    err_msg = err.decode("utf-8") if err else res_str
                    print(f"[MathCAT] SetRulesDir ล้มเหลว: {err_msg}")
                    return

            self._is_initialized = True
            v = self._lib.GetMathCATVersion()
            ver_str = v.decode("utf-8") if v else "Unknown"
            print(f"[MathCAT] โหลด MathCAT Engine v{ver_str} สำเร็จ (Rules: {rules_dir})")
        except Exception as e:
            print(f"[MathCAT] โหลด DLL ผิดพลาด: {e}")
            self._is_initialized = False

    def is_available(self) -> bool:
        return self._is_initialized and self._lib is not None

    def to_mathml(self, text: str) -> Optional[str]:
        """แปลงข้อความคณิตศาสตร์เป็น MathML"""
        s = text.strip()
        if not s:
            return None

        # 1. หากเป็น MathML อยู่แล้ว
        if s.startswith("<math") and s.endswith("</math>"):
            return s
        if "<math" in s and "</math>" in s:
            m = re.search(r"(<math.*?</math>)", s, re.DOTALL)
            if m:
                return m.group(1)

        # 2. แปลงจาก LaTeX (ถ้ามี latex2mathml)
        if latex_to_mathml:
            try:
                clean_tex = s
                if clean_tex.startswith("$") and clean_tex.endswith("$"):
                    clean_tex = clean_tex.strip("$")
                mml = latex_to_mathml(clean_tex)
                if mml:
                    return mml
            except Exception:
                pass

        # 3. แปลงแบบ Fallback ด้วย SymPy (ถ้ามี)
        try:
            import sympy
            from sympy.printing.mathml import mathml as sympy_mathml
            from sympy.parsing.sympy_parser import parse_expr
            expr = parse_expr(s.replace("^", "**"))
            return f'<math xmlns="http://www.w3.org/1998/Math/MathML">{sympy_mathml(expr, printer="presentation")}</math>'
        except Exception:
            pass

        return None

    def convert(self, math_input: str, code: str = "Nemeth") -> Dict[str, Any]:
        """
        แปลงสมการคณิตศาสตร์เป็นอักษรเบรลล์
        code: 'Nemeth' หรือ 'UEB'
        """
        base_fail = {
            "success": False,
            "error": "",
            "braille": "",
            "simbraille_ascii": "",
            "dot_numbers": "",
            "spoken": "",
            "mathml": ""
        }

        if not self.is_available():
            base_fail["error"] = "MathCAT Engine ไม่พร้อมทำงาน (ไม่พบ libMathCat64.dll หรือ Rules)"
            return base_fail

        mml = self.to_mathml(math_input)
        if not mml:
            base_fail["error"] = "ไม่สามารถแปลงรูปแบบสมการคณิตศาสตร์เป็น MathML ได้ (กรุณาตรวจไวยากรณ์ LaTeX/สูตร)"
            return base_fail

        try:
            braille_code = b"Nemeth" if code.lower() == "nemeth" else b"UEB"
            self._lib.SetPreference(b"BrailleCode", braille_code)

            res_set = self._lib.SetMathML(mml.encode("utf-8"))
            res_str = res_set.decode("utf-8") if res_set else ""
            if not res_str:
                err = self._lib.GetError()
                err_msg = err.decode("utf-8") if err else "SetMathML failed"
                base_fail["error"] = f"MathCAT SetMathML ผิดพลาด: {err_msg}"
                base_fail["mathml"] = mml
                return base_fail

            b_bytes = self._lib.GetBraille(b"")
            sp_bytes = self._lib.GetSpokenText()

            braille_unicode = b_bytes.decode("utf-8") if b_bytes else ""
            spoken_text = sp_bytes.decode("utf-8") if sp_bytes else ""

            # แปลงเป็นเลขจุดเบรลล์
            dot_cells = []
            for ch in braille_unicode:
                val = ord(ch) - 0x2800
                if 0 <= val <= 0xFF:
                    if val == 0:
                        dot_cells.append(" ")
                    else:
                        d = "".join([str(i + 1) for i in range(8) if (val & (1 << i))])
                        dot_cells.append(d)
                elif ch == " ":
                    dot_cells.append(" ")

            dot_numbers = " ".join([c for c in dot_cells if c != " "])

            # แปลงเป็น SimBraille ASCII (สำหรับแสดงผลบนฟอนต์ SimBraille)
            simbraille_chars = []
            for ch in braille_unicode:
                offset = ord(ch) - 0x2800
                if 0 <= offset < len(UNICODE_TO_SIMBRAILLE_ASCII):
                    simbraille_chars.append(UNICODE_TO_SIMBRAILLE_ASCII[offset])
                elif ch == " ":
                    simbraille_chars.append(" ")
                else:
                    simbraille_chars.append(ch)

            simbraille_ascii = "".join(simbraille_chars)

            return {
                "success": True,
                "error": "",
                "braille": braille_unicode,
                "simbraille_ascii": simbraille_ascii,
                "dot_numbers": dot_numbers,
                "spoken": spoken_text,
                "mathml": mml
            }
        except Exception as e:
            base_fail["error"] = f"เกิดข้อผิดพลาดในการประมวลผล: {e}"
            base_fail["mathml"] = mml
            return base_fail
