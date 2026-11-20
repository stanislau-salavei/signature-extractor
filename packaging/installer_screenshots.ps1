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
    $bmp = New-Object System.Drawing.Bitmap ($r.Right - $r.Left), ($r.Bottom - $r.Top)
    $g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
    [Win]::PrintWindow($h, $hdc, 2) | Out-Null                                              # PW_RENDERFULLCONTENT
    $g.ReleaseHdc($hdc); $g.Dispose()
    $crop = New-Object System.Drawing.Rectangle ($f.Left - $r.Left), ($f.Top - $r.Top), ($f.Right - $f.Left), ($f.Bottom - $f.Top)
    $out = $bmp.Clone($crop, $bmp.PixelFormat); $bmp.Dispose()
    $path = Join-Path $OutDir "$name.png"
    $out.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    "{0}: {1}x{2}" -f $path, $out.Width, $out.Height
    $out.Dispose()
}

function Get-Buttons($w) {
    $c = New-Object System.Windows.Automation.PropertyCondition($UIA::ControlTypeProperty, $CT::Button)
    $w.FindAll($Tree::Descendants, $c) | Where-Object { -not $_.Current.IsOffscreen -and $_.Current.IsEnabled }
}

function Click-Button($w, [string[]]$names) {
    $b = Get-Buttons $w | Where-Object { ($_.Current.Name -replace "&", "") -in $names } | Select-Object -First 1
    if (-not $b) { throw ("no button " + ($names -join "/") + "; have: " + ((Get-Buttons $w | ForEach-Object { $_.Current.Name }) -join ", ")) }
    $b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    Start-Sleep -Milliseconds 1200
}

function Wait-Button($w, [string[]]$names, [int]$TimeoutS) {
    $end = (Get-Date).AddSeconds($TimeoutS)
    while ((Get-Date) -lt $end) {
        if (Get-Buttons $w | Where-Object { ($_.Current.Name -replace "&", "") -in $names }) { return }
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
    ru = @{ Next = "Далее >"; Install = "Установить"; Finish = "Завершить" }
    en = @{ Next = "Next >"; Install = "Install"; Finish = "Finish" }
}
foreach ($lang in "ru", "en") {
    $t = $T[$lang]
    $p = Start-Process -FilePath $Setup -ArgumentList "/LANG=$lang" -PassThru
    try {
        $w = Find-Wizard
        "[$lang] title: " + $w.Current.Name
        Save-Shot $w "${lang}_1_welcome"
        $links = $w.FindAll($Tree::Descendants, (New-Object System.Windows.Automation.PropertyCondition($UIA::ControlTypeProperty, $CT::Hyperlink)))
        foreach ($l in $links) { "[$lang] link: '" + $l.Current.Name + "' invoke=" + [bool]($l.GetSupportedPatterns() | Where-Object { $_.ProgrammaticName -like "Invoke*" }) }
        if (-not $links -or $links.Count -eq 0) { "[$lang] link: NONE" }
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
