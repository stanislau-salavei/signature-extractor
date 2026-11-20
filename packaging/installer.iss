; Stage 6: per-user Inno Setup 6 installer of «Извлечение подписи» / Signature Extractor.
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
#define LicenseUrl "https://www.gnu.org/licenses/gpl-3.0.html"

; PNG wizard images in the Inno Setup 6.6 DPI sizes (packaging/installer/), TNewLinkLabel
#if Ver < EncodeVer(6, 6, 0)
  #error Inno Setup 6.6 or later is required
#endif

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
; «Programs and Features» (Control Panel) › Support info
AppComments={cm:AppComments}
VersionInfoVersion={#AppNumVersion}
VersionInfoProductName=Signature Extractor
VersionInfoProductVersion={#AppNumVersion}
VersionInfoDescription=Signature Extractor {#AppVersion} Setup
VersionInfoCompany=Stanislau Salavei
VersionInfoCopyright=© 2026 Stanislau Salavei
; per-user, no administrator rights and no UAC — first install and updates
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Signature Extractor
DisableWelcomePage=no
DisableDirPage=yes
; the folder is not asked for, but the Ready page lists it
AlwaysShowDirOnReadyPage=yes
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
; GNU GPLv3: a short note with a link on the Welcome page ([Code]); the full text is installed as LICENSE.txt
SetupIconFile=..\assets\app.ico
WizardStyle=modern
; left panel of Welcome / Finished (Russian name; English installs swap in the English image, [Code])
; and the icon of the inner pages; Setup picks the size that matches the DPI
WizardImageFile=installer\wizard_image_ru_*.png
WizardSmallImageFile=installer\wizard_small_*.png
OutputDir=..\dist
OutputBaseFilename=SignatureExtractor-{#AppVersion}-setup
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Messages]
; page texts use the short name; the window title keeps the full name with the version ([Code])
en.WelcomeLabel1=Install Signature Extractor
en.WelcomeLabel2=Signature Extractor turns a photo or scan of a signature into clean PNG, SVG and DXF files. Everything is processed on your computer.%n%nNo administrator rights are needed: the program is installed for your user account only.
en.ClickNext=Click Next to continue.
en.SelectTasksLabel2=Select the additional tasks to perform while installing Signature Extractor, then click Next.
en.ReadyLabel1=Setup is ready to install Signature Extractor on this computer.
en.ReadyLabel2a=Click Install to continue, or Back if you want to change the installation settings.
en.PreparingDesc=Setup is preparing to install Signature Extractor on this computer.
en.InstallingLabel=Please wait while Setup installs Signature Extractor on this computer.
en.FinishedHeadingLabel=Setup is complete
en.FinishedLabel=Signature Extractor has been installed. You can open it from the Start menu.
en.FinishedLabelNoIcons=Signature Extractor has been installed.
en.ClickFinish=Click Finish to close Setup.
ru.WelcomeLabel1=Установка программы «Извлечение подписи»
ru.WelcomeLabel2=Программа делает из фото или скана подписи чистые файлы PNG, SVG и DXF. Всё обрабатывается на вашем компьютере.%n%nПрава администратора не нужны: программа ставится только для вашей учётной записи.
ru.ClickNext=Нажмите «Далее», чтобы продолжить.
ru.SelectTasksLabel2=Выберите дополнительные задачи для установки программы «Извлечение подписи» и нажмите «Далее».
ru.ReadyLabel1=Программа установки готова установить «Извлечение подписи» на этот компьютер.
ru.ReadyLabel2a=Нажмите «Установить», чтобы продолжить, или «Назад», если хотите изменить параметры установки.
ru.PreparingDesc=Программа установки готовится установить «Извлечение подписи» на этот компьютер.
ru.InstallingLabel=Подождите, пока программа «Извлечение подписи» устанавливается на этот компьютер.
ru.FinishedHeadingLabel=Установка завершена
ru.FinishedLabel=Программа «Извлечение подписи» установлена. Её можно открыть из меню «Пуск».
ru.FinishedLabelNoIcons=Программа «Извлечение подписи» установлена.
ru.ClickFinish=Нажмите «Завершить», чтобы закрыть мастер установки.

[CustomMessages]
en.ShortcutName=Signature Extractor
ru.ShortcutName=Извлечение подписи
; the language of the installation becomes the first interface language (stage 1, read_installer_language)
en.LangArg=en
ru.LangArg=ru
en.LaunchApp=Launch the program
ru.LaunchApp=Запустить программу
en.AppComments=Turns a photo or scan of a signature into clean PNG, SVG and DXF files.
ru.AppComments=Делает из фото или скана подписи чистые файлы PNG, SVG и DXF.
; %1 = the link to the licence text
en.LicenseNote=Signature Extractor is free software under the GNU GPL, version 3. Full text: %1 and the LICENSE file in the program folder.
ru.LicenseNote=«Извлечение подписи» — свободная программа под лицензией GNU GPL версии 3. Полный текст: %1 и файл LICENSE в папке программы.

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
; English left-panel images, loaded by [Code] (not installed)
Source: "installer\wizard_image_en_*.png"; Flags: dontcopy

[Icons]
; Start menu — always; desktop — only with the check box (off by default)
Name: "{autoprograms}\{cm:ShortcutName}"; Filename: "{app}\{#AppExe}"; Parameters: "--installer-language {cm:LangArg}"; WorkingDir: "{app}"; AppUserModelID: "{#AppUserModelID}"
Name: "{autodesktop}\{cm:ShortcutName}"; Filename: "{app}\{#AppExe}"; Parameters: "--installer-language {cm:LangArg}"; WorkingDir: "{app}"; AppUserModelID: "{#AppUserModelID}"; Tasks: desktopicon

[Run]
; also after a silent update (/SILENT from the app): no skipifsilent, the new version opens
Filename: "{app}\{#AppExe}"; Parameters: "--installer-language {cm:LangArg}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall

; %APPDATA%\Signature Extractor (settings.json, log) is never touched (no uninstall-delete entries)

[Code]
var
  LicenseLink: TNewLinkLabel;
  ClickNextLabel: TNewStaticText;

procedure LicenseLinkClick(Sender: TObject; const Link: String; LinkType: TSysLinkType);
var
  ErrorCode: Integer;
begin
  if LinkType = sltURL then
    ShellExecAsOriginalUser('open', Link, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

{ The left-panel images carry the program name, so English installs replace the Russian image chosen by
  Setup with the English one of the nearest size (same sizes as WizardImageFile). }
function EnglishImageName(Width: Integer): String;
begin
  if Width <= 202 then Result := '202x386'
  else if Width <= 269 then Result := '269x515'
  else if Width <= 336 then Result := '336x643'
  else if Width <= 403 then Result := '403x772'
  else if Width <= 430 then Result := '430x824'
  else if Width <= 498 then Result := '498x953'
  else Result := '551x1055';
  Result := 'wizard_image_en_' + Result + '.png';
end;

procedure LoadPng(Image: TBitmapImage; const FileName: String);
var
  Stream: TFileStream;
begin
  Stream := TFileStream.Create(FileName, fmOpenRead);
  try
    Image.PngImage.LoadFromStream(Stream);
  finally
    Stream.Free;
  end;
end;

procedure UseEnglishWizardImage;
var
  Name: String;
begin
  Name := EnglishImageName(WizardForm.WizardBitmapImage.Width);
  ExtractTemporaryFile(Name);
  LoadPng(WizardForm.WizardBitmapImage, ExpandConstant('{tmp}\') + Name);
  LoadPng(WizardForm.WizardBitmapImage2, ExpandConstant('{tmp}\') + Name);
end;

{ Welcome page: the description, then the licence note with a clickable link, then «Click Next». }
procedure LayOutWelcomePage;
var
  Gap: Integer;
begin
  Gap := ScaleY(15);
  WizardForm.WelcomeLabel2.Caption := SetupMessage(msgWelcomeLabel2);
  WizardForm.AdjustLabelHeight(WizardForm.WelcomeLabel2);

  LicenseLink := TNewLinkLabel.Create(WizardForm);
  LicenseLink.Parent := WizardForm.WelcomePage;
  LicenseLink.AutoSize := False;
  LicenseLink.Left := WizardForm.WelcomeLabel2.Left;
  LicenseLink.Top := WizardForm.WelcomeLabel2.Top + WizardForm.WelcomeLabel2.Height + Gap;
  LicenseLink.Width := WizardForm.WelcomeLabel2.Width;
  LicenseLink.Caption := FmtMessage(CustomMessage('LicenseNote'),
    ['<a href="{#LicenseUrl}">{#LicenseUrl}</a>']);
  LicenseLink.OnLinkClick := @LicenseLinkClick;
  WizardForm.AdjustLinkLabelHeight(LicenseLink);

  ClickNextLabel := TNewStaticText.Create(WizardForm);
  ClickNextLabel.Parent := WizardForm.WelcomePage;
  ClickNextLabel.AutoSize := False;
  ClickNextLabel.WordWrap := True;
  ClickNextLabel.Left := LicenseLink.Left;
  ClickNextLabel.Top := LicenseLink.Top + LicenseLink.Height + Gap;
  ClickNextLabel.Width := LicenseLink.Width;
  ClickNextLabel.Caption := SetupMessage(msgClickNext);
  WizardForm.AdjustLabelHeight(ClickNextLabel);
end;

procedure InitializeWizard;
begin
  { with the Welcome page on, Setup would show only AppName in the title }
  WizardForm.Caption := FmtMessage(SetupMessage(msgSetupWindowTitle), ['{#AppTitle} {#AppVersion}']);
  if ActiveLanguage = 'en' then
    UseEnglishWizardImage;
  LayOutWelcomePage;
end;
