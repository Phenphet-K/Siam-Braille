# -*- coding: utf-8 -*-
import os
import ctypes
import sys

sys.stdout.reconfigure(encoding='utf-8')

_base = os.path.dirname(os.path.abspath(__file__))
louis = ctypes.cdll.LoadLibrary(os.path.join(_base, 'liblouis64.dll'))
louis.lou_translateString.argtypes = [
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_int),
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_int
]
louis.lou_translateString.restype = ctypes.c_int

def translate_smb(tbl_name, text):
    tbl_path = os.path.join(_base, 'Tables', tbl_name)
    in_arr = (ctypes.c_uint32 * len(text))(*[ord(c) for c in text])
    in_len = ctypes.c_int(len(text))
    out_arr = (ctypes.c_uint32 * 512)()
    out_len = ctypes.c_int(512)
    
    ret = louis.lou_translateString(
        tbl_path.encode('utf-8'),
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
        return ''.join(chr(c) for c in chars)
    return f'ERROR {ret}'

# Convert SimBraille/Braille ASCII to Unicode Braille and Dot numbers
ASCII_TO_DOTS = {
    ' ': ' ', '!': '2346', '"': '5', '#': '3456', '$': '1246', '%': '146',
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

def to_dots(ascii_str):
    return ' '.join(ASCII_TO_DOTS.get(c, c) for c in ascii_str)

test_groups = {
    '1. สระหน้า': ['เก็บ', 'แตง', 'โม', 'ให้', 'ได้'],
    '2. สระเดี่ยว/ประสม': ['มะลิ', 'ชี', 'ผึ้ง', 'ตื่น', 'ดุ', 'ปู', 'ผัวะ', 'วัว', 'กำ'],
    '3. วรรณยุกต์กับสระหลัง (คู่มือ 2564 ข้อ 1.3)': ['บ้าน', 'พ่อ', 'ช่วย'],
    '4. สระเออ': ['เชิง', 'เดิม', 'เกิน', 'เธอ', 'เก้อ', 'เทอญ', 'เทอม', 'เกอย', 'เคย'],
    '5. สระเอา/เอาะ/เอีย/เอือ': ['เรา', 'เกาะ', 'เรียน', 'เมือง', 'ผัวะ'],
    '6. สระพิเศษ': ['ฤกษ์', 'ฤดู', 'ฤๅษี', 'อำเภอ', 'ไป', 'ใจ'],
    '7. บาลีสันสกฤต': ['ธมฺมา', 'เตสํ', 'พุทฺธํ'],
    '8. ตัวเลขไทย/อารบิก': ['123', '๑๒๓', '25.6', '10:30'],
    '9. เครื่องหมาย': ['พ.ศ.', 'กรุงเทพฯ', 'ต่างๆ']
}

for grp, items in test_groups.items():
    print(f'\n=== {grp} ===')
    for item in items:
        g0 = translate_smb('th-g0.utb', item)
        g1 = translate_smb('th-g1.utb', item)
        print(f'{item:12s} | G0: {g0:10s} (dots: {to_dots(g0):25s}) | G1: {g1:10s} (dots: {to_dots(g1)})')
