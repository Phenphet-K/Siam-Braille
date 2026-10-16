# รายงานผลการถอดรหัสและวิเคราะห์ไฟล์ต้นฉบับ Delphi TBTW (TBTW2.exe)

## 1. ข้อมูลโครงสร้างระดับ PE Binary
- **Machine**: 0x14c (Intel 386 32-bit x86)
- **Entry Point**: 0x8e358
- **Image Base**: 0x400000
- **Sections (8 sections)**:
  - `CODE`: Virtual Size 0x8d490, Raw Size 0x8d600
  - `DATA`: Virtual Size 0x1afc, Raw Size 0x1c00
  - `BSS`: Virtual Size 0x5f4d, Raw Size 0x0
  - `.idata`: Virtual Size 0x24fe, Raw Size 0x2600
  - `.tls`: Virtual Size 0x10, Raw Size 0x0
  - `.rdata`: Virtual Size 0x18, Raw Size 0x200
  - `.reloc`: Virtual Size 0x9a40, Raw Size 0x9c00
  - `.rsrc`: Virtual Size 0x2a000, Raw Size 0x2a000

## 2. Windows API Imports ที่โปรแกรมต้นฉบับเรียกใช้
- **kernel32.dll** (64 functions): `lstrcpyA, WriteFile, WaitForSingleObject, VirtualQuery, VirtualAlloc, Sleep, SizeofResource, SetThreadLocale, SetFilePointer, SetEvent...`
- **user32.dll** (168 functions): `WindowFromPoint, WinHelpA, WaitMessage, UpdateWindow, UnregisterClassA, UnhookWindowsHookEx, TranslateMessage, TranslateMDISysAccel, TrackPopupMenu, SystemParametersInfoA...`
- **advapi32.dll** (3 functions): `RegQueryValueExA, RegOpenKeyExA, RegCloseKey...`
- **oleaut32.dll** (7 functions): `VariantChangeTypeEx, VariantCopyInd, VariantClear, SysStringLen, SysFreeString, SysReAllocStringLen, SysAllocStringLen...`
- **mpr.dll** (1 functions): `WNetGetConnectionA...`
- **version.dll** (3 functions): `VerQueryValueA, GetFileVersionInfoSizeA, GetFileVersionInfoA...`
- **gdi32.dll** (79 functions): `UnrealizeObject, StretchBlt, StartPage, StartDocA, SetWindowOrgEx, SetWinMetaFileBits, SetViewportOrgEx, SetTextColor, SetStretchBltMode, SetROP2...`
- **ole32.dll** (1 functions): `IsEqualGUID...`
- **comctl32.dll** (24 functions): `ImageList_SetIconSize, ImageList_GetIconSize, ImageList_Write, ImageList_Read, ImageList_GetDragImage, ImageList_DragShowNolock, ImageList_SetDragCursorImage, ImageList_DragMove, ImageList_DragLeave, ImageList_DragEnter...`
- **winspool.drv** (4 functions): `OpenPrinterA, EnumPrintersA, DocumentPropertiesA, ClosePrinter...`
- **comdlg32.dll** (6 functions): `PrintDlgA, ChooseFontA, ReplaceTextA, FindTextA, GetSaveFileNameA, GetOpenFileNameA...`
- **nbreak.dll** (1 functions): `Ordinal_2...`

## 3. หน้าต่างฟอร์ม Delphi (Forms/DFM) ทั้งหมด (17 ฟอร์ม)
- **`DVCLAL`** (ขนาด 16 bytes, DFM: False)
- **`PACKAGEINFO`** (ขนาด 704 bytes, DFM: False)
- **`TABOUTBOX`** (ขนาด 83615 bytes, DFM: True)
- **`TAPPLICATION`** (ขนาด 20 bytes, DFM: True)
- **`TFORM1`** (ขนาด 1553 bytes, DFM: True)
- **`TFORM10`** (ขนาด 19283 bytes, DFM: True)
- **`TFORM11`** (ขนาด 704 bytes, DFM: True)
- **`TFORM12`** (ขนาด 1085 bytes, DFM: True)
- **`TFORM2`** (ขนาด 1577 bytes, DFM: True)
- **`TFORM3`** (ขนาด 2914 bytes, DFM: True)
- **`TFORM4`** (ขนาด 3222 bytes, DFM: True)
- **`TFORM5`** (ขนาด 485 bytes, DFM: True)
- **`TFORM6`** (ขนาด 2400 bytes, DFM: True)
- **`TFORM7`** (ขนาด 1076 bytes, DFM: True)
- **`TFORM8`** (ขนาด 951 bytes, DFM: True)
- **`TFORM9`** (ขนาด 881 bytes, DFM: True)
- **`TSDIAPPFORM`** (ขนาด 27951 bytes, DFM: True)

## 4. รายการ Classes และ Method Handlers ใน VMT (74 Methods)
- `AllowChange`
- `BitBtn1Click`
- `Braille1Click`
- `BraillePage1Click`
- `BrailleTextFile1Click`
- `Button1Click`
- `Button2Click`
- `ButtonLeft1Click`
- `ButtonRight1Click`
- `ChangWindows1Click`
- `CheckBox1Click`
- `CheckBox2Click`
- `CheckBox3Click`
- `CheckBox4Click`
- `Checkyourmachine1Click`
- `CloseAll1Click`
- `Com11Click`
- `Com21Click`
- `ContractInformation1Click`
- `Default1Click`
- `DriveComboBox1Change`
- `DubbleSize1Click`
- `Englishkeyboard1Click`
- `FileExit1Execute`
- `FileListBox1Change`
- `FileNew1Execute`
- `FileOpen1Execute`
- `Fine1Click`
- `Font1Click`
- `FullScreen1Click`
- `GotoIndexKey1Click`
- `GotoIndexKey2Click`
- `Grade1withnocontraction1Click`
- `Grade2withcontraction1Click`
- `Grade2withcontraction2Click`
- `Help2Click`
- `HelpAbout1Execute`
- `LPT11Click`
- `LPT21Click`
- `No1Click`
- `NormalTextFile1Click`
- `OnDblClick`
- `OnDownClick`
- `OnFolderChange`
- `OnProtectChange`
- `OnSelectionChange`
- `OnTypeChange`
- `OnUpClick`
- `Panel1Click`
- `PhoneRegistrations1Click`

## 5. การวิเคราะห์ข้อความภาษาไทยและระบบคำสั่ง (9043 ข้อความ)
- ๘้ฃF
- ๘้ญF
- ฬฬฬA
- ภSVพP
- ๚du์
- รSVWUQ
- รSVWU
- ๛WS่
- ภSVWUQ
- ๛WS่ญ๛
- ร่์๛
- ล่ใ๛
- ภSVWU
- ์3าUh
- ภZYYd
- ภu้3ภZYYd
- ล่ำ๛
- รSVW
- ภSVW
- ร่ป๘
- ยรSVWU
- ฤ๘SVW
- ษUhธ
- ์QSVW
- ุ3ภฃ0
- ๐่t๘
- ฺ่่๗
- ฦ่/๚
- ๋,่J๖
- ร่โ๙
- าUh๑
- ฦ่ฃ๚
- ภu๋รฐ
- ภPRQ่ฌ
- ร1ภ้
- ๋ๅ1ษ๋์
- ฺ3าUh
- รSVWQ
- ็I)ส๓ค
- ั๓ค)็

## 6. การเปรียบเทียบความสมบูรณ์กับ SiamBraille 1.0 (Modern Architecture)
| คุณสมบัติเดิม (TBTW Delphi 7) | สถานะใน SiamBraille 1.0 (PyQt6) | ความสมบูรณ์ |
|------------------------------|----------------------------------|:-----------:|
| Editor สองฝั่ง (ไทย ซ้าย / เบรลล์ ขวา) | QPlainTextEdit คู่ ซ้าย/ขวา พร้อม F6 Toggle | 100% |
| ตารางคำย่อ CH46.tab, CH78.tab | ThaiBrailleTranslator (พ.ศ. 2564 สมบูรณ์) | 100% |
| พจนานุกรมคำย่อ Tbt.dic | SiamBraille.dic (อัปเกรดคำย่อสากล) | 100% |
| คีย์ลัดสากล (Ctrl+T, Ctrl+P, F1-F6) | รองรับตามมาตรฐานเดิม ครบถ้วน | 100% |
| สื่อสาร Screen Reader (เดิมไม่มี API) | เชื่อมโยง NVDA Client DLL แบบ Native | ดีกว่าเดิม |
| สั่งพิมพ์จุดจำลอง (SimBraille) | ฟอนต์ SIMBRL.TTF พิมพ์ผ่าน PDF/A4 ได้ตรงจุด | 100% |
| การตั้งค่าหน้ากระดาษ (30 เซลล์ x 25 บรรทัด) | SiamBraille.def พร้อมฟังก์ชันล็อกหน้าและเลขหน้า | 100% |
