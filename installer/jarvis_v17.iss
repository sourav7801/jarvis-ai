#define MyAppName "JARVIS V17"
#define MyAppVersion "17.0.1"
#define MyAppPublisher "JARVIS"
#define MyAppExeName "Launch-JARVIS-V17.cmd"

[Setup]
AppId={{D84367A9-9E58-4E7B-9C13-A7F13B714917}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\JARVIS\V17
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=JARVIS-V17-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\build\v17_payload\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\installer\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\installer\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoLogo -NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\bootstrap_v17.ps1"""; WorkingDir: "{app}"; StatusMsg: "Preparing the isolated JARVIS V17 Python runtime..."; Flags: waituntilterminated runascurrentuser
Filename: "{app}\installer\{#MyAppExeName}"; Description: "Launch JARVIS V17"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent runascurrentuser
