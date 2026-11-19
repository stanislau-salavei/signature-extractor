; Stage 6: per-user Inno Setup 6 installer of «Извлечение подписи / Signature Extractor».
; Built by packaging/build.py:  ISCC /DAppVersion=1.0 /DAppNumVersion=1.0.0.0 packaging\installer.iss
; Input: dist\SignatureExtractor\ (PyInstaller onedir).  Output: dist\SignatureExtractor-<ver>-setup.exe.
; The file is UTF-8 with BOM (Russian texts).

#ifndef AppVersion
  #define AppVersion "1.0"
#endif
#ifndef AppNumVersion
  #define AppNumVersion "1.0.0.0"
#endif
#define AppExe "SignatureExtractor.exe"
#define AppTitle "Извлечение подписи (Signature Extractor)"
#define RepoUrl "https://github.com/stanislau-salavei/signature-extractor"
; must equal ui/platform_win.INSTANCE_MUTEX (the running app holds it)
#define AppMutexName "StanislauSalavei.SignatureExtractor.Running"
#define AppUserModelID "StanislauSalavei.SignatureExtractor"

[Setup]
; the same AppId in every version: one entry in «Installed apps», updates install over it
AppId={{A610AA29-D7B2-4BD1-8564-F1469C0509C5}
AppName={#AppTitle}
AppVersion={#AppVersion}
AppVerName={#AppTitle} {#AppVersion}
UninstallDisplayName={#AppTitle}
UninstallDisplayIcon={app}\{#AppExe}
AppPublisher=Stanislau Salavei
AppCopyright=© 2026 Stanislau Salavei
AppPublisherURL={#RepoUrl}
AppSupportURL={#RepoUrl}/issues
AppUpdatesURL={#RepoUrl}/releases
VersionInfoVersion={#AppNumVersion}
VersionInfoProductName=Signature Extractor
VersionInfoProductVersion={#AppNumVersion}
VersionInfoDescription=Signature Extractor {#AppVersion} Setup
VersionInfoCompany=Stanislau Salavei
VersionInfoCopyright=© 2026 Stanislau Salavei
; per-user, no administrator rights and no UAC — first install and updates
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Signature Extractor
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=no
UsePreviousAppDir=no
UsePreviousLanguage=no
UsePreviousTasks=yes
; Windows 10 1809 (build 17763) or later, 64-bit only
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; language of Windows; anything other than Russian -> English (the first language below)
ShowLanguageDialog=no
LanguageDetectionMethod=uilanguage
; the running app: AppMutex asks to close it; Restart Manager closes what still holds files
AppMutex={#AppMutexName}
CloseApplications=yes
RestartApplications=no
; D6: GNU GPLv3 shown read-only (no «I accept»)
InfoBeforeFile=..\LICENSE
SetupIconFile=..\assets\app.ico
WizardStyle=modern
OutputDir=..\dist
OutputBaseFilename=SignatureExtractor-{#AppVersion}-setup
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Messages]
en.WizardInfoBefore=License
en.InfoBeforeLabel=Signature Extractor is free software under the GNU General Public License, version 3. Please read the license:
ru.WizardInfoBefore=Лицензия
ru.InfoBeforeLabel=«Извлечение подписи» — свободная программа под лицензией GNU GPL версии 3. Прочитайте текст лицензии:

[CustomMessages]
en.ShortcutName=Signature Extractor
ru.ShortcutName=Извлечение подписи
; the language of the installation becomes the first interface language (stage 1, read_installer_language)
en.LangArg=en
ru.LangArg=ru

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; an update replaces the program files completely (no libraries of the old version left)
Type: filesandordirs; Name: "{app}\_internal"
; shortcuts of an installation in the other language (they are created again below)
Type: files; Name: "{autoprograms}\Signature Extractor.lnk"
Type: files; Name: "{autoprograms}\Извлечение подписи.lnk"
Type: files; Name: "{autodesktop}\Signature Extractor.lnk"; Tasks: desktopicon
Type: files; Name: "{autodesktop}\Извлечение подписи.lnk"; Tasks: desktopicon

[Files]
Source: "..\dist\SignatureExtractor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\assets\app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start menu — always; desktop — only with the check box (off by default)
Name: "{autoprograms}\{cm:ShortcutName}"; Filename: "{app}\{#AppExe}"; Parameters: "--installer-language {cm:LangArg}"; WorkingDir: "{app}"; AppUserModelID: "{#AppUserModelID}"
Name: "{autodesktop}\{cm:ShortcutName}"; Filename: "{app}\{#AppExe}"; Parameters: "--installer-language {cm:LangArg}"; WorkingDir: "{app}"; AppUserModelID: "{#AppUserModelID}"; Tasks: desktopicon

[Run]
; also after a silent update (/SILENT from the app): no skipifsilent, the new version opens
Filename: "{app}\{#AppExe}"; Parameters: "--installer-language {cm:LangArg}"; Description: "{cm:LaunchProgram,{cm:ShortcutName}}"; Flags: nowait postinstall

; %APPDATA%\Signature Extractor (settings.json, log) is never touched (no uninstall-delete entries)
