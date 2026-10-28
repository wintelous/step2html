; Inno Setup script for the Step2HTML Windows installer. Built by packaging\build_windows.ps1:
;   ISCC /DAppVersion=<version> /DRoot=<repo dir> packaging\windows\step2html.iss
; Installs per user by default (no admin prompt); "Install for all users" is offered in the wizard.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef Root
  #define Root "..\.."
#endif

[Setup]
AppId={{8F3C2A51-6D7E-4B9A-9C21-5E7A0F3B2D44}
AppName=Step2HTML
AppVersion={#AppVersion}
AppVerName=Step2HTML {#AppVersion}
AppPublisher=step2html contributors
DefaultDirName={autopf}\Step2HTML
DefaultGroupName=Step2HTML
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile={#Root}\LICENSE
SetupIconFile={#Root}\build\icons\step2html.ico
UninstallDisplayIcon={app}\Step2HTML.exe
UninstallDisplayName=Step2HTML
OutputDir={#Root}\dist\windows
OutputBaseFilename=Step2HTML-{#AppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "openwith"; Description: "Offer Step2HTML in ""Open with"" for STEP files (.step, .stp)"; GroupDescription: "File types:"

[Files]
Source: "{#Root}\dist\Step2HTML\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Step2HTML"; Filename: "{app}\Step2HTML.exe"
Name: "{autodesktop}\Step2HTML"; Filename: "{app}\Step2HTML.exe"; Tasks: desktopicon

[Registry]
; "Open with" entry only - it never takes over STEP files from your CAD application
Root: HKA; Subkey: "Software\Classes\Applications\Step2HTML.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Step2HTML"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\Step2HTML.exe\shell\open\command"; ValueType: string; ValueData: """{app}\Step2HTML.exe"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\Step2HTML.exe\SupportedTypes"; ValueType: string; ValueName: ".step"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\Step2HTML.exe\SupportedTypes"; ValueType: string; ValueName: ".stp"; ValueData: ""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.step\OpenWithList\Step2HTML.exe"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.stp\OpenWithList\Step2HTML.exe"; Flags: uninsdeletekey; Tasks: openwith

[Run]
Filename: "{app}\Step2HTML.exe"; Description: "{cm:LaunchProgram,Step2HTML}"; Flags: nowait postinstall skipifsilent
