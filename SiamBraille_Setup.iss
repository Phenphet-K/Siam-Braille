; Script generated for SiamBraille 1.0 Professional Setup
; ระบบติดตั้ง SiamBraille 1.0 พร้อมติดตั้งฟอนต์ SimBraille เข้าสู่ระบบ Windows อัตโนมัติ

#define MyAppName "SiamBraille"
#define MyAppVersion "1.0"
#define MyAppPublisher "SiamBraille Team"
#define MyAppExeName "SiamBraille.exe"

[Setup]
AppId={{E8B7F538-4C89-4D61-A173-F292B4A1D572}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=SiamBraille_Setup_v1.0
SetupIconFile=SiamBraille.ico
UninstallDisplayIcon={app}\SiamBraille.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=none

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; 1. ไฟล์โปรแกรมและทรัพยากรทั้งหมด (ย้ายได้ทุกที่)
Source: "dist\SiamBraille\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; 2. ติดตั้งฟอนต์ SimBraille เข้า Windows Fonts อัตโนมัติ (TrueType Font Registration)
Source: "SIMBRL.TTF"; DestDir: "{autofonts}"; FontInstall: "SimBraille"; Flags: onlyifdoesntexist uninsneveruninstall

; 3. ไฟล์ลิขสิทธิ์อัตโนมัติ (ถ้ามี license.key อยู่ตอนสั่งคอมไพล์หรือแจกลูกค้า จะเปิดใช้งานได้ทันที)
Source: "license.key"; DestDir: "{app}"; Flags: skipifsourcedoesntexist ignoreversion

[Registry]
; บันทึกหลักฐานสิทธิ์ทดลองใช้ระดับเครื่อง (Machine-level) ป้องกันการถอนการติดตั้งแล้วลงใหม่เพื่อรีเซ็ตวันทดลอง
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\.sb_state"; ValueType: string; ValueName: "SecInstallTag"; ValueData: "{#MyAppVersion}"; Flags: createvalueifdoesntexist
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Explorer\.sb_state"; ValueType: string; ValueName: "SecInstallTag"; ValueData: "{#MyAppVersion}"; Flags: createvalueifdoesntexist

[Icons]
Name: "{group}\{#MyAppName} 1.0"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\SiamBraille.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName} 1.0"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\SiamBraille.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
