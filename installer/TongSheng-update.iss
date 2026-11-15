; TongSheng update package (1.1.3 -> 1.1.4)
; Installs over an existing %ProgramFiles%\TongSheng and only replaces code,
; docs and tools - no models, no runtime. Small download (< 5 MB).
;
; Build:
;   python tools\build_update_package.py
;   ISCC.exe installer\TongSheng-update.iss

#define MyAppName "TongSheng"
#define MyAppVersion "1.1.4"
#define SourceDir "..\dist\TongSheng-1.1.4-update"
#define AssetsDir "..\dist\installer_assets"

[Setup]
AppId={{7F3C2B90-4E15-4C7A-9E86-2A5D1F8B3C42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} update
AppPublisher=TongSheng
DefaultDirName={autopf}\{#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
OutputDir=..\dist\installer
OutputBaseFilename=TongSheng-{#MyAppVersion}-Update
SetupIconFile={#AssetsDir}\app.ico
WizardStyle=modern
WizardImageFile={#AssetsDir}\wizard_image.bmp
WizardSmallImageFile={#AssetsDir}\wizard_small.bmp
WizardImageStretch=yes
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
Uninstallable=no
VersionInfoVersion=1.1.4.0
VersionInfoCompany=TongSheng
VersionInfoDescription=TongSheng 1.1.4 update (code, tools and docs only)
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=1.1.4

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Update TongSheng to {#MyAppVersion}
WelcomeLabel2=This update replaces the program code, tools and documentation of an existing TongSheng {#MyAppName} installation. Voices, recordings, configuration and model files are left untouched.%n%nClose TongSheng before continuing.
FinishedLabel=Update complete. TongSheng is now version {#MyAppVersion}.

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Run]
Filename: "{app}\runtime\python.exe"; Parameters: """{app}\tools\selftest.py"""; WorkingDir: "{app}"; Description: "Run the self-test now (~1 min)"; Flags: postinstall nowait skipifsilent
