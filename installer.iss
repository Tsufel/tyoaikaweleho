; Tyoaikaweleho — Inno Setup 6 installer script
; Build with: ISCC.exe /DAppVersion=x.x.x installer.iss
; Or just run build.bat — it passes the version automatically.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName      "Tyoaikaweleho"
#define AppExeName   "Tyoaikaweleho.exe"
#define AppPublisher "Tsufel"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/{#AppPublisher}/tyoaikaweleho
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
OutputDir=Output
OutputBaseFilename=TyoaikawelehoSetup_{#AppVersion}
Compression=lzma2
SolidCompression=yes
; No admin rights needed — installs to %LOCALAPPDATA%
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
; Gracefully close any running instance before updating
CloseApplications=yes
RestartApplications=yes
; Wizard appearance
WizardStyle=modern
SetupIconFile=icon.ico

[InstallDelete]
; Drop the previous bundle first so files removed from a release (e.g. old
; frontend assets) don't linger. User data lives next to the exe, not here.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; Entire PyInstaller --onedir bundle (exe + _internal\, which holds the webui\ frontend and icon.ico)
; ignoreversion — always overwrite on update
; User data (data.json, shifts.txt, session.json, image_ocr.py) is NOT produced
; by the build so it never appears here — it survives updates automatically.
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
; Optional desktop shortcut (unchecked by default)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
; Launch the app after the installer finishes (user can uncheck this)
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; WebView2 browser cache/profile (not user data)
Type: filesandordirs; Name: "{userappdata}\Tyoaikaweleho\WebView2"
Type: dirifempty; Name: "{userappdata}\Tyoaikaweleho"

[Code]
const
  WebView2ClientKey = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2DownloadUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

function WebView2VersionOk(RootKey: Integer): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, WebView2ClientKey, 'pv', Version) and
            (Version <> '') and (Version <> '0.0.0.0');
end;

function WebView2Installed(): Boolean;
begin
  // 32-bit view = SOFTWARE\WOW6432Node on 64-bit Windows
  Result := WebView2VersionOk(HKLM32) or WebView2VersionOk(HKCU);
  if not Result and IsWin64 then
    Result := WebView2VersionOk(HKLM64);
end;

// ─────────────────────────────────────────────────────────────────────────────
// The app's window is drawn by the Microsoft Edge WebView2 Runtime (built into
// Windows 11 and most Windows 10 PCs). It is not bundled; if it is missing,
// point the user at Microsoft's installer and carry on.
// ─────────────────────────────────────────────────────────────────────────────
procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrorCode: Integer;
begin
  if (CurStep = ssPostInstall) and not WebView2Installed() then
  begin
    if SuppressibleMsgBox(
         '{#AppName} needs the Microsoft Edge WebView2 Runtime, which was not found on this PC.' + #13#10#13#10 +
         'Download it free from Microsoft:' + #13#10 + WebView2DownloadUrl + #13#10#13#10 +
         'Open the download page now?',
         mbInformation, MB_YESNO, IDNO) = IDYES then
      ShellExec('open', WebView2DownloadUrl, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
  end;
end;

// ─────────────────────────────────────────────────────────────────────────────
// On uninstall: ask whether to keep or delete user data.
// Files NOT in [Files] (data.json, shifts.txt, session.json, image_ocr.py)
// are left behind by default.  Only removed if the user clicks No here.
// ─────────────────────────────────────────────────────────────────────────────
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if FileExists(ExpandConstant('{app}\data.json')) or
       FileExists(ExpandConstant('{app}\shifts.txt')) then
    begin
      if MsgBox(
           'Keep your timesheet data and settings?' + #13#10 +
           '(data.json, shifts.txt)' + #13#10#13#10 +
           'Click Yes to keep them.' + #13#10 +
           'Click No to delete everything.',
           mbConfirmation, MB_YESNO) = IDNO then
      begin
        DeleteFile(ExpandConstant('{app}\data.json'));
        DeleteFile(ExpandConstant('{app}\data.json.bak'));
        DelTree(ExpandConstant('{app}\backups'), True, True, True);
        DeleteFile(ExpandConstant('{app}\shifts.txt'));
        DeleteFile(ExpandConstant('{app}\session.json'));
        DeleteFile(ExpandConstant('{app}\image_ocr.py'));
        DeleteFile(ExpandConstant('{app}\error.log'));
        // Remove the install directory itself if now empty
        RemoveDir(ExpandConstant('{app}'));
      end;
    end;
  end;
end;
