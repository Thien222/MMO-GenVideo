# ============================================================
#  Script chay nhanh - tu lo ffmpeg PATH + venv.
#
#  CACH DUNG (mo PowerShell tai thu muc MMO):
#    .\run.ps1 "why honesty matters"                 # 1 video whiteboard ke chuyen
#    .\run.ps1 -Batch topics_story.txt               # chay hang loat
#    .\run.ps1 "3 ways to say hello" -Shorts          # dung pipeline English shorts
# ============================================================
param(
    [Parameter(Position = 0)]
    [string]$Topic,
    [string]$Batch,
    [switch]$Shorts,
    [switch]$Web
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Dam bao ffmpeg co tren PATH (tu tim trong winget neu chua co)
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    $ff = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter ffmpeg.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ff) { $env:PATH = (Split-Path $ff.FullName) + ";" + $env:PATH }
    else { Write-Warning "Khong tim thay ffmpeg. Cai bang: winget install Gyan.FFmpeg" }
}

$py = ".\venv\Scripts\python.exe"

if ($Web) {
    Write-Host "Dang chay Web UI (Streamlit)..." -ForegroundColor Cyan
    & $py -m streamlit run app.py
    exit
}

$module = if ($Shorts) { "src.pipeline" } else { "src.pipeline_whiteboard" }

if ($Batch) {
    & $py -m $module --batch $Batch
}
elseif ($Topic) {
    & $py -m $module --topic $Topic
}
else {
    Write-Host "Thieu chu de. Vi du:  .\run.ps1 `"why honesty matters`"" -ForegroundColor Yellow
    Write-Host "Chay Web UI: .\run.ps1 -Web" -ForegroundColor Yellow
}
