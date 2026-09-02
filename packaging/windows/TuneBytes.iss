#define MyAppName "TuneBytes"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Craig Coleman"
#define MyAppExeName "TuneBytes.exe"

[Setup]
AppId={{E7AC28A5-6107-4D43-86F8-777E31C2FA0C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist-installer
OutputBaseFilename=TuneBytes-Setup
SetupIconFile=..\..\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Files]
Source: "..\..\dist\TuneBytes\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\TuneBytes"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\TuneBytes"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall TuneBytes"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch TuneBytes"; Flags: nowait postinstall skipifsilent
