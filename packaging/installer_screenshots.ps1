# CI only (best effort): run the built installer in Russian and English on the Windows runner, capture every
# wizard page as PNG and check the licence link of the Welcome page; then the uninstaller (remark 122): its dialog,
# «Remove settings» ticked (RU) and unticked (EN), a silent update and a silent uninstall keep the settings.  Installs into the runner's profile.
#   powershell -File packaging/installer_screenshots.ps1 -Setup dist\SignatureExtractor-1.0.1-setup.exe -OutDir shots
param([Parameter(Mandatory)] [string]$Setup, [Parameter(Mandatory)] [string]$OutDir)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT r);
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr hwnd, int attr, out RECT r, int size);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr hwnd, ref POINT p);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr hwnd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, System.Text.StringBuilder l);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(IntPtr h, System.Text.StringBuilder s, int n);
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc f, IntPtr l);
    // visible child windows as "class|text" (text via WM_GETTEXT)
    public static System.Collections.Generic.List<string> Children(IntPtr parent, System.Collections.Generic.List<IntPtr> handles) {
        var list = new System.Collections.Generic.List<string>();
        EnumChildWindows(parent, (h, l) => {
            if (!IsWindowVisible(h)) return true;
            var c = new System.Text.StringBuilder(256); GetClassName(h, c, 256);
            int n = (int)SendMessage(h, 0x000E, IntPtr.Zero, IntPtr.Zero);
            var t = new System.Text.StringBuilder(n + 1); SendMessage(h, 0x000D, (IntPtr)(n + 1), t);
            list.Add(c + "|" + (IsWindowEnabled(h) ? "" : "(disabled)") + t); handles.Add(h); return true; }, IntPtr.Zero);
        return list;
    }
}
"@
$UIA = [System.Windows.Automation.AutomationElement]
$Tree = [System.Windows.Automation.TreeScope]
$CT = [System.Windows.Automation.ControlType]
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Get-Wizards {
    $UIA::RootElement.FindAll($Tree::Children, [System.Windows.Automation.Condition]::TrueCondition) |
        Where-Object { $_.Current.ClassName -like "TWizardForm*" }
}

# the wizard window of the setup started by $p (it runs in the child process «…setup.tmp»)
function Find-Wizard($p, [int]$TimeoutS = 60) {
    $end = (Get-Date).AddSeconds($TimeoutS)
    while ((Get-Date) -lt $end) {
        $kids = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.Id)" | ForEach-Object { [int]$_.ProcessId })
        foreach ($w in Get-Wizards) { if ($kids -contains $w.Current.ProcessId) { return $w } }
        Start-Sleep -Milliseconds 300
    }
    throw "wizard window not found"
}

function Save-Shot($w, [string]$name) {
    Start-Sleep -Milliseconds 700
    $h = [IntPtr]$w.Current.NativeWindowHandle
    [Win]::SetForegroundWindow($h) | Out-Null
    $r = New-Object Win+RECT; [Win]::GetWindowRect($h, [ref]$r) | Out-Null
    $f = New-Object Win+RECT; [Win]::DwmGetWindowAttribute($h, 9, [ref]$f, 16) | Out-Null   # extended frame bounds
    $crop = New-Object System.Drawing.Rectangle ($f.Left - $r.Left), ($f.Top - $r.Top), ($f.Right - $f.Left), ($f.Bottom - $f.Top)
    $out = $null
    for ($try = 1; $try -le 5 -and -not $out; $try++) {
        $bmp = New-Object System.Drawing.Bitmap ($r.Right - $r.Left), ($r.Bottom - $r.Top)
        $g = [System.Drawing.Graphics]::FromImage($bmp); $g.Clear([System.Drawing.Color]::Magenta); $hdc = $g.GetHdc()
        $ok = [Win]::PrintWindow($h, $hdc, 2)                                                # PW_RENDERFULLCONTENT
        $g.ReleaseHdc($hdc); $g.Dispose()
        $px = $bmp.GetPixel([int]($bmp.Width / 2), [int]($bmp.Height / 2))
        if ($ok -and -not ($px.R -eq 255 -and $px.G -eq 0 -and $px.B -eq 255)) { $out = $bmp.Clone($crop, $bmp.PixelFormat) }
        else { "  PrintWindow failed (try $try)"; Start-Sleep -Milliseconds 700 }
        $bmp.Dispose()
    }
    if (-not $out) {                                                                         # the screen itself
        $out = New-Object System.Drawing.Bitmap $crop.Width, $crop.Height
        $g = [System.Drawing.Graphics]::FromImage($out)
        $g.CopyFromScreen($f.Left, $f.Top, 0, 0, $out.Size); $g.Dispose()
        "  captured from the screen"
    }
    $path = Join-Path $OutDir "$name.png"
    $out.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $texts = Get-Controls $w | Where-Object { $_.Text -like "TNewStaticText|*" } | Select-Object -First 2 | ForEach-Object { ($_.Text -split "\|", 2)[1] }
    $script:LastFrame = $f
    "{0}: {1}x{2}  [{3}]" -f $path, $out.Width, $out.Height, ($texts -join " / ")
    $out.Dispose()
}

function Get-Controls($w) {
    $h = New-Object System.Collections.Generic.List[IntPtr]
    $names = [Win]::Children([IntPtr]$w.Current.NativeWindowHandle, $h)
    for ($i = 0; $i -lt $names.Count; $i++) { [pscustomobject]@{ Handle = $h[$i]; Text = ($names[$i] -replace "&", "") } }
}

# a visible, enabled button whose text starts with one of the names («Далее» / «Next», with or without « >»)
function Find-Button($w, [string[]]$names) {
    foreach ($c in Get-Controls $w) {
        $parts = $c.Text -split "\|", 2
        if ($parts[0] -notlike "*Button*" -or $parts[1].StartsWith("(disabled)")) { continue }
        foreach ($n in $names) { if ($n -and $parts[1].StartsWith($n)) { return $c } }
    }
    return $null
}

function Click-Button($w, [string[]]$names) {
    $b = Find-Button $w $names
    if (-not $b) { throw ("no button " + ($names -join "/") + "; have: " + ((Get-Controls $w | ForEach-Object { $_.Text }) -join ", ")) }
    "  click: " + $b.Text + "  (buttons: " + ((Get-Controls $w | Where-Object { $_.Text -like "*Button|*" } | ForEach-Object { $_.Text }) -join ", ") + ")"
    [Win]::SendMessage($b.Handle, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null            # BM_CLICK
    Start-Sleep -Milliseconds 1200
}

function Wait-Button($w, [string[]]$names, [int]$TimeoutS) {
    $end = (Get-Date).AddSeconds($TimeoutS)
    while ((Get-Date) -lt $end) {
        if (Find-Button $w $names) { return }
        Start-Sleep -Milliseconds 500
    }
    throw ("timeout waiting for " + ($names -join "/"))
}

# click the licence link like a user (mouse down/up on the blue link text) and report whether a browser starts
function Test-LicenseLink($w, [string]$shot) {
    $link = Get-Controls $w | Where-Object { $_.Text -like "TNewLinkLabel|*" } | Select-Object -First 1
    if (-not $link) { return "no TNewLinkLabel" }
    $img = New-Object System.Drawing.Bitmap $shot
    $hit = $null                                    # the first pixel of the Windows link colour #0066CC
    for ($y = 40; $y -lt $img.Height - 60 -and -not $hit; $y++) {
        for ($x = 200; $x -lt $img.Width - 20; $x++) {
            $c = $img.GetPixel($x, $y)
            if ($c.R -eq 0 -and $c.G -eq 102 -and $c.B -eq 204) { $hit = @($x, $y); break }
        }
    }
    $img.Dispose()
    if (-not $hit) { return "no link-coloured text found" }
    $pt = New-Object Win+POINT; $pt.X = $script:LastFrame.Left + $hit[0] + 2; $pt.Y = $script:LastFrame.Top + $hit[1] + 4
    [Win]::ScreenToClient($link.Handle, [ref]$pt) | Out-Null
    $before = @(Get-Process msedge, chrome, firefox -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    $lp = [IntPtr](($pt.Y -shl 16) -bor ($pt.X -band 0xFFFF))
    [Win]::PostMessage($link.Handle, 0x0201, [IntPtr]1, $lp) | Out-Null                     # WM_LBUTTONDOWN
    Start-Sleep -Milliseconds 80
    [Win]::PostMessage($link.Handle, 0x0202, [IntPtr]0, $lp) | Out-Null                     # WM_LBUTTONUP
    $end = (Get-Date).AddSeconds(15); $new = @()
    while (-not $new.Count -and (Get-Date) -lt $end) {
        Start-Sleep -Milliseconds 500
        $new = @(Get-Process msedge, chrome, firefox -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id })
    }
    $res = "clicked at client ($($pt.X), $($pt.Y)): " + $(if ($new.Count) { "browser started (" + $new[0].Name + ")" } else { "no browser process in 15 s" })
    Get-Process msedge, chrome, firefox -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    return $res
}

function Stop-Setup {
    Get-Process | Where-Object { $_.Path -and ($_.Path -like "*\is-*\*.tmp" -or $_.Name -like "SignatureExtractor*") } |
        ForEach-Object { "  stop: " + $_.Path; $_ | Stop-Process -Force -ErrorAction SilentlyContinue }
    $end = (Get-Date).AddSeconds(20)
    while (@(Get-Wizards).Count -and (Get-Date) -lt $end) { Start-Sleep -Milliseconds 500 }
}


# ---------------------------------------------------------------- uninstall (remark 122)
$DataDir = Join-Path $env:APPDATA "Signature Extractor"
$UpdDir = Join-Path ([System.IO.Path]::GetTempPath()) "SignatureExtractor-update"
$ExportDir = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Signatures"
$UninstKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{A610AA29-D7B2-4BD1-8564-F1469C0509C5}_is1"

function New-AppData {
    New-Item -ItemType Directory -Force -Path $DataDir, $UpdDir, $ExportDir | Out-Null
    '{"language": "system", "custom_sizes": [{"w": 40, "h": 15}], "custom_colors": ["#123456"]}' |
        Set-Content -Path (Join-Path $DataDir "settings.json") -Encoding UTF8
    "log" | Set-Content (Join-Path $DataDir "signature_extractor.log")
    "old log" | Set-Content (Join-Path $DataDir "signature_extractor.log.1")
    "partial" | Set-Content (Join-Path $UpdDir "SignatureExtractor-9.9-setup.exe.part")
    "png" | Set-Content (Join-Path $ExportDir "signature_ci.png")             # an exported signature
}

function Show-AppData([string]$tag) {
    $files = @(Get-ChildItem $DataDir -File -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
    "[$tag] data folder: " + $(if (Test-Path $DataDir) { "present (" + ($files -join ", ") + ")" } else { "REMOVED" }) +
        "; update folder: " + $(if (Test-Path $UpdDir) { "present" } else { "REMOVED" }) +
        "; exported signature: " + $(if (Test-Path (Join-Path $ExportDir "signature_ci.png")) { "kept" } else { "DELETED" })
}

function Get-UninstWindows([string]$class) {
    $ids = @(Get-Process | Where-Object { $_.Name -like "_iu*" -or $_.Name -like "unins*" } | ForEach-Object { $_.Id })
    $UIA::RootElement.FindAll($Tree::Children, [System.Windows.Automation.Condition]::TrueCondition) |
        Where-Object { $ids -contains $_.Current.ProcessId -and $_.Current.ClassName -like $class }
}

function Wait-UninstWindow([string]$class, [int]$TimeoutS = 60) {
    $end = (Get-Date).AddSeconds($TimeoutS)
    while ((Get-Date) -lt $end) {
        $w = Get-UninstWindows $class | Select-Object -First 1
        if ($w) { return $w }
        Start-Sleep -Milliseconds 300
    }
    throw "uninstall window $class not found"
}

function Invoke-Uninstall([string]$lang, [bool]$untick) {
    $u = Get-ItemProperty -Path $UninstKey
    $exe = ($u.UninstallString -replace '"', '')
    $names = @{ ru = "Удалить"; en = "Remove" }
    $p = Start-Process -FilePath $exe -PassThru
    try {
        $w = Wait-UninstWindow "TSetupForm*"
        "[$lang] uninstall dialog: " + $w.Current.Name
        Get-Controls $w | ForEach-Object { "[$lang]   control: " + $_.Text }
        Save-Shot $w "${lang}_5_uninstall"
        if ($untick) {
            $cb = Get-Controls $w | Where-Object { $_.Text -like "TNewCheckBox|*" } | Select-Object -First 1
            [Win]::SendMessage($cb.Handle, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null    # BM_CLICK
            $state = [Win]::SendMessage($cb.Handle, 0x00F0, [IntPtr]::Zero, [IntPtr]::Zero)      # BM_GETCHECK
            "[$lang] check box after click: " + $state
            Save-Shot $w "${lang}_5b_uninstall_unticked"
        }
        Click-Button $w @($names[$lang])
        $c = Wait-UninstWindow "#32770"
        Save-Shot $c "${lang}_6_uninstall_confirm"
        Click-Button $c @("Да", "Yes")
        $d = $null; $end = (Get-Date).AddSeconds(120)
        while (-not $d -and (Get-Date) -lt $end) {
            $d = Get-UninstWindows "#32770" | Where-Object { Find-Button $_ @("OK") } | Select-Object -First 1
            Start-Sleep -Milliseconds 500
        }
        if ($d) { Save-Shot $d "${lang}_7_uninstall_done"; Click-Button $d @("OK") }
        $end = (Get-Date).AddSeconds(60)
        while (@(Get-Process | Where-Object { $_.Name -like "_iu*" }).Count -and (Get-Date) -lt $end) { Start-Sleep -Milliseconds 500 }
    } finally {
        Get-Process | Where-Object { $_.Name -like "_iu*" -or $_.Name -like "unins*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    "[$lang] uninstall entry after: " + $(if (Test-Path $UninstKey) { "still present" } else { "removed" })
}

$Checks = @()
function Check([string]$what, [bool]$ok) { $script:Checks += ("{0}: {1}" -f $(if ($ok) { "PASS" } else { "FAIL" }), $what) }

$ButtonNames = @{
    ru = @{ Next = "Далее"; Install = "Установить"; Finish = "Завершить" }
    en = @{ Next = "Next"; Install = "Install"; Finish = "Finish" }
}
foreach ($lang in "ru", "en") {
    $t = $ButtonNames[$lang]          # (PowerShell names are case-insensitive: not $T)
    $left = @(Get-Wizards)
    if ($left.Count) { throw "a wizard window is still open: " + $left[0].Current.Name }
    $p = Start-Process -FilePath $Setup -ArgumentList "/LANG=$lang" -PassThru
    try {
        $w = Find-Wizard $p
        "[$lang] title: " + $w.Current.Name
        Save-Shot $w "${lang}_1_welcome"
        if ($lang -eq "ru") { "[$lang] licence link: " + (Test-LicenseLink $w (Join-Path $OutDir "${lang}_1_welcome.png")) }
        Get-Controls $w | ForEach-Object { "[$lang]   control: " + $_.Text }
        $link = Get-Controls $w | Where-Object { $_.Text -like "SysLink|*" }
        "[$lang] link control: " + $(if ($link) { "SysLink, " + (($link.Text -split "\|", 2)[1]) } else { "NONE" })
        Click-Button $w @($t.Next)
        Save-Shot $w "${lang}_2_tasks"
        Click-Button $w @($t.Next)
        Save-Shot $w "${lang}_3_ready"
        Click-Button $w @($t.Install)
        Wait-Button $w @($t.Finish) 240
        Save-Shot $w "${lang}_4_finished"
    } finally {
        Stop-Setup                       # do not press «Finish»: it would start the program
        if (-not $p.HasExited) { $p.Kill() }
    }
    # what Windows shows in «Installed apps» / «Programs and Features», and the Start menu shortcut
    $key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{A610AA29-D7B2-4BD1-8564-F1469C0509C5}_is1"
    $u = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
    if ($u) {
        "[$lang] registry DisplayName: " + $u.DisplayName
        "[$lang] registry DisplayVersion: " + $u.DisplayVersion + "; Comments: " + $u.Comments
        "[$lang] registry InstallLocation: " + $u.InstallLocation + "; Inno Setup: Language: " + $u."Inno Setup: Language"
    } else { "[$lang] registry: no uninstall entry" }
    $menu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    Get-ChildItem $menu -Filter *.lnk | Where-Object { $_.Name -match "Signature|подписи" } |
        ForEach-Object { "[$lang] Start menu shortcut: " + $_.Name }

    New-AppData
    if ($lang -eq "en") {
        # an update installs over the old version silently: the settings stay
        $q = Start-Process -FilePath $Setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LANG=en" -PassThru
        $q.WaitForExit(240000) | Out-Null
        Stop-Setup
        Show-AppData "en, after a silent update"
        Check "silent update keeps the settings" (Test-Path (Join-Path $DataDir "settings.json"))
    }
    $untick = $lang -eq "en"
    Invoke-Uninstall $lang $untick
    Show-AppData ("$lang, after uninstall (Remove settings " + $(if ($untick) { "unticked" } else { "ticked" }) + ")")
    Check "$lang uninstall: exported signature kept" (Test-Path (Join-Path $ExportDir "signature_ci.png"))
    if ($untick) {
        Check "en unticked keeps settings.json and the log" ((Test-Path (Join-Path $DataDir "settings.json")) -and (Test-Path (Join-Path $DataDir "signature_extractor.log")))
    } else {
        Check "ru ticked removes the data folder" (-not (Test-Path $DataDir))
        Check "ru ticked removes downloaded updates" (-not (Test-Path $UpdDir))
    }
}

# silent uninstall: no dialog, the settings stay
$q = Start-Process -FilePath $Setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LANG=ru" -PassThru
$q.WaitForExit(240000) | Out-Null
Stop-Setup
New-AppData
$exe = ((Get-ItemProperty -Path $UninstKey).UninstallString -replace '"', '')
$q = Start-Process -FilePath $exe -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -PassThru
$q.WaitForExit(120000) | Out-Null
$end = (Get-Date).AddSeconds(60)
while (@(Get-Process | Where-Object { $_.Name -like "_iu*" }).Count -and (Get-Date) -lt $end) { Start-Sleep -Milliseconds 500 }
Show-AppData "silent uninstall"
Check "silent uninstall keeps the settings" (Test-Path (Join-Path $DataDir "settings.json"))
Check "silent uninstall removes the program" (-not (Test-Path $UninstKey))

$Checks | ForEach-Object { "CHECK " + $_ }
if ($Checks -match "^FAIL") { throw "uninstall checks failed" }
