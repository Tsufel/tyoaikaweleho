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
SetupIconFile=

[Files]
; App bundle from PyInstaller --onedir
; Flags: ignoreversion — always overwrite (needed for updates)
; User data (data.json, shifts.txt, image_ocr.py) is NOT listed here
; so it is never touched by install or update.
Source: "dist\{#AppName}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\{#AppName}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

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

[Code]
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
        DeleteFile(ExpandConstant('{app}\shifts.txt'));
        DeleteFile(ExpandConstant('{app}\session.json'));
        DeleteFile(ExpandConstant('{app}\image_ocr.py'));
        // Remove the install directory itself if now empty
        RemoveDir(ExpandConstant('{app}'));
      end;
    end;
  end;
end;
