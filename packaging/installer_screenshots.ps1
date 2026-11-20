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

function Find-Wizard([int]$TimeoutS = 60) {
    $end = (Get-Date).AddSeconds($TimeoutS)
    while ((Get-Date) -lt $end) {
        foreach ($w in $UIA::RootElement.FindAll($Tree::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
            if ($w.Current.Name -like "*Signature Extractor*" -and $w.Current.ClassName -like "TWizardForm*") { return $w }
        }
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
        foreach ($n in $names) { if ($parts[1].StartsWith($n)) { return $c } }
    }
    return $null
}

function Click-Button($w, [string[]]$names) {
    $b = Find-Button $w $names
    if (-not $b) { throw ("no button " + ($names -join "/") + "; have: " + ((Get-Controls $w | ForEach-Object { $_.Text }) -join ", ")) }
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

function Stop-Setup {
    Get-Process | Where-Object { $_.Path -and ($_.Path -like "*\is-*\*.tmp" -or $_.Name -like "SignatureExtractor*") } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

$T = @{
    ru = @{ Next = "Далее"; Install = "Установить"; Finish = "Завершить" }
    en = @{ Next = "Next"; Install = "Install"; Finish = "Finish" }
}
foreach ($lang in "ru", "en") {
    $t = $T[$lang]
    $p = Start-Process -FilePath $Setup -ArgumentList "/LANG=$lang" -PassThru
    try {
        $w = Find-Wizard
        "[$lang] title: " + $w.Current.Name
        Save-Shot $w "${lang}_1_welcome"
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
