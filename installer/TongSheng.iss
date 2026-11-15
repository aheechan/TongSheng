; TongSheng installer (Inno Setup 6)
; English-only wizard, dark artwork matching the app icon.
;
; Build:
;   python tools\build_package.py --stage
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer\TongSheng.iss
;
; Output: dist\installer\TongSheng-1.1.9-Setup.exe  +  -1.bin, -2.bin ...
; Each slice stays below 1.9 GB so GitHub Releases accepts it (< 2 GB/file).

#define MyAppName "TongSheng"
#define MyAppVersion "1.1.9"
#define MyAppPublisher "TongSheng"
#define MyAppURL "https://github.com/"
#define MyAppExeName "run.bat"
#define SourceDir "..\dist\TongSheng-1.1.9"
#define AssetsDir "..\dist\installer_assets"

[Setup]
AppId={{7F3C2B90-4E15-4C7A-9E86-2A5D1F8B3C42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir=..\dist\installer
OutputBaseFilename=TongSheng-{#MyAppVersion}-Setup
SetupIconFile={#AssetsDir}\app.ico
UninstallDisplayIcon={app}\app.ico
UninstallDisplayName={#MyAppName} {#MyAppVersion}
WizardStyle=modern
WizardImageFile={#AssetsDir}\wizard_image.bmp
WizardSmallImageFile={#AssetsDir}\wizard_small.bmp
WizardImageStretch=yes
Compression=lzma2/fast
SolidCompression=no
DiskSpanning=yes
DiskSliceSize=1900000000
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=1.1.9.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=TongSheng - local voice translation with your own cloned voice
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=1.1.9

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to the [name] Setup Wizard
WelcomeLabel2=This will install [name/ver] on your computer.%n%nTongSheng recognises what you say, translates it, and speaks the translation in the voice you trained. Everything runs locally on this machine - audio never leaves the computer.%n%nAbout 14 GB of disk space is required. The first start loads the speech and voice models and can take up to a minute.
FinishedLabel=Setup has finished installing [name] on your computer.%n%nTongSheng now lives in the system tray. Press the right Alt key, speak one sentence, and press it again - the translation is spoken back in your cloned voice.
ClickFinish=Click Finish to close Setup.

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\tools\dev_run.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Comment: "TongSheng - local voice translation"
Name: "{group}\Self-test"; Filename: "{app}\runtime\python.exe"; Parameters: """{app}\tools\selftest.py"""; WorkingDir: "{app}"; Comment: "Check models, GPU, audio and voice synthesis"
Name: "{group}\Documentation"; Filename: "{app}\README.md"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\tools\dev_run.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Comment: "TongSheng - local voice translation"; Tasks: desktopicon

[Run]
Filename: "{app}\runtime\python.exe"; Parameters: """{app}\tools\selftest.py"""; WorkingDir: "{app}"; Description: "Run the self-test now (models, GPU, audio, ~1 min)"; Flags: postinstall nowait skipifsilent
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\tools\dev_run.py"""; WorkingDir: "{app}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\tongsheng\__pycache__"
Type: files; Name: "{app}\config.yaml"
