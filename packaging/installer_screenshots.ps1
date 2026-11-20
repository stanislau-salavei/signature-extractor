# CI only (best effort): run the built installer in Russian and English on the Windows runner, capture every
# wizard page as PNG and check the licence link of the Welcome page.  Installs into the runner's profile.
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
}
