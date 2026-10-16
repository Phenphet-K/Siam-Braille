; Script generated for SiamBraille 1.0 Professional Setup
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
OutputDir=G:\TBTW\dist
OutputBaseFilename=SiamBraille_Setup_v1.0
SetupIconFile=G:\TBTW\SiamBraille.ico
UninstallDisplayIcon={app}\SiamBraille.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "G:\TBTW\dist\SiamBraille\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Register SimBraille Font
Source: "G:\TBTW\dist\SiamBraille\SIMBRL.TTF"; DestDir: "{autofonts}"; FontInstall: "SimBraille"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\{#MyAppName} 1.0"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\SiamBraille.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName} 1.0"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\SiamBraille.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
