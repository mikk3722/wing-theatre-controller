; Wing Theatre Controller - Windows installer (Inno Setup 6)
; Built by GitHub Actions:
;   ISCC.exe /DMyAppVersion=1.9.11 installer\wing-theatre-controller.iss
; The user chooses: install for all users (Program Files, asks for admin)
; or only for themselves (no admin needed).

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName   "Wing Theatre Controller"
#define MyAppExe    "Wing Theatre Controller.exe"
#define MyPublisher "Mikkel Peter Larsen"

[Setup]
AppId={{9C3E5B71-2A4D-4E8F-B6C1-7D2A9F4E3B58}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyPublisher}
AppPublisherURL=https://github.com/mikk3722/wing-theatre-controller
AppSupportURL=https://github.com/mikk3722/wing-theatre-controller
VersionInfoVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
OutputDir=..\installer-out
OutputBaseFilename=WingTheatreController-Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "danish";  MessagesFile: "compiler:Languages\Danish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole PyInstaller folder (exe, wingmon.exe, propmap, Qt, Python)
Source: "..\dist\Wing Theatre Controller\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; Double-clicking a .wts show file opens it in Wing Theatre Controller
Root: HKA; Subkey: "Software\Classes\.wts"; ValueType: string; ValueName: ""; ValueData: "WingTheatreController.Show"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.wts\OpenWithProgids"; ValueType: string; ValueName: "WingTheatreController.Show"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\WingTheatreController.Show"; ValueType: string; ValueName: ""; ValueData: "Wing Theatre Show"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\WingTheatreController.Show\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExe},0"
Root: HKA; Subkey: "Software\Classes\WingTheatreController.Show\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExe}"" ""%1"""

[Run]
; Allow incoming OSC (UDP) and Companion (TCP) remote control through the
; Windows Firewall -- only possible when installing for all users (admin).
; A per-user install gets the normal Windows prompt the first time instead.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#MyAppName}"""; Flags: runhidden; Check: IsAdminInstallMode
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#MyAppName}"" dir=in action=allow program=""{app}\{#MyAppExe}"" enable=yes profile=any"; Flags: runhidden; Check: IsAdminInstallMode
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#MyAppName}"""; Flags: runhidden; RunOnceId: "DelFirewallRule"; Check: IsAdminInstallMode
