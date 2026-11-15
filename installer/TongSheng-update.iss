; TongSheng update package (1.1.4 -> 1.1.6)
; Finds the previous install directory from the uninstall registry key, so a
; copy installed to D:\TongSheng is updated in place instead of landing in
; Program Files.
;
; Build:  python tools\build_update_package.py  &&  ISCC.exe installer\TongSheng-update.iss

#define MyAppName "TongSheng"
#define MyAppVersion "1.1.6"
#define SourceDir "..\dist\TongSheng-1.1.6-update"
#define AssetsDir "..\dist\installer_assets"

[Setup]
AppId={{7F3C2B90-4E15-4C7A-9E86-2A5D1F8B3C42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} update
AppPublisher=TongSheng
DefaultDirName={code:GetPreviousDir}
DisableDirPage=yes
DisableProgramGroupPage=yes
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
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
Uninstallable=no
VersionInfoVersion=1.1.6.0
VersionInfoCompany=TongSheng
VersionInfoDescription=TongSheng 1.1.6 update (code, tools, docs, default voice)
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=1.1.6

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Update TongSheng to {#MyAppVersion}
WelcomeLabel2=This update replaces the program code, tools and documentation of the existing TongSheng installation found on this machine, and restores the bundled default voice if it is missing.%n%nVoices you trained, recordings, configuration and model files are left untouched. Close TongSheng before continuing.
FinishedLabel=Update complete. TongSheng is now version {#MyAppVersion}.

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "voice-repository\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\voice-repository\*"; DestDir: "{app}\voice-repository"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist

[Run]
Filename: "{app}\runtime\python.exe"; Parameters: """{app}\tools\selftest.py"""; WorkingDir: "{app}"; Description: "Run the self-test now (~1 min)"; Flags: postinstall nowait skipifsilent

[Code]
function GetPreviousDir(Param: string): string;
var
  Value: string;
  Key: string;
begin
  Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{7F3C2B90-4E15-4C7A-9E86-2A5D1F8B3C42}_is1';
  if RegQueryStringValue(HKLM64, Key, 'InstallLocation', Value) and (Value <> '') then
  begin
    Result := Value;
    exit;
  end;
  if RegQueryStringValue(HKLM, Key, 'InstallLocation', Value) and (Value <> '') then
  begin
    Result := Value;
    exit;
  end;
  Result := ExpandConstant('{autopf}\TongSheng');
end;
