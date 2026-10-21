# PyStream-Downloader Windows 一鍵部署與自適應啟動腳本
[CmdletBinding()]
param (
    [string]$Url = "",
    [string]$Quality = "",
    [switch]$BuildOnly,
    [switch]$Full
)

# 強制設定控制台編碼為 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host '==========================================================' -ForegroundColor Cyan
Write-Host ' PyStream-Downloader 容器化智慧調度腳本 (Windows)         ' -ForegroundColor Cyan
Write-Host '==========================================================' -ForegroundColor Cyan

# 1. 檢查 Docker 服務狀態
Write-Host '[1/3] 正在檢測 Docker 運行環境...' -ForegroundColor Yellow
$dockerCheck = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host '[Error] Docker Daemon 尚未啟動！請先啟動 Docker Desktop 後再執行此腳本。' -ForegroundColor Red
    exit 1
}
Write-Host '[OK] Docker 運行中。' -ForegroundColor Green

# 2. 建置映像檔
if ($Full) {
    Write-Host '[2/3] 正在建置完整版映像檔 pystream-downloader:full (含 Playwright Chromium)...' -ForegroundColor Yellow
    docker-compose --profile full build downloader-full
} else {
    Write-Host '[2/3] 正在建置輕量版映像檔 pystream-downloader:slim (~420MB)...' -ForegroundColor Yellow
    docker-compose build downloader
}

if ($LASTEXITCODE -ne 0) {
    Write-Host '[Error] 映像檔建置失敗！' -ForegroundColor Red
    exit 1
}
Write-Host '[OK] 映像檔建置完成。' -ForegroundColor Green

if ($BuildOnly) {
    Write-Host '[SUCCESS] 映像檔已就緒。' -ForegroundColor Green
    exit 0
}

# 3. 準備啟動下載任務
Write-Host '[3/3] 準備啟動下載任務...' -ForegroundColor Yellow
$downloadsPath = Join-Path (Get-Location) 'downloads'
if (-not (Test-Path $downloadsPath)) {
    New-Item -ItemType Directory -Path $downloadsPath | Out-Null
}

$appArgs = @()
if ($Url -ne "") {
    $appArgs += $Url
    if ($Quality -ne "") {
        $appArgs += @("-q", $Quality)
    }
}

if ($Full) {
    Write-Host "[INFO] 以完整版容器直接啟動 (--profile full)..." -ForegroundColor Cyan
    & docker-compose --profile full run --rm downloader-full $appArgs
    exit $LASTEXITCODE
}

# 預設以輕量版容器執行
Write-Host "[INFO] 啟動預設輕量容器 (downloader:slim)..." -ForegroundColor Cyan
& docker-compose run --rm downloader $appArgs
$initialExitCode = $LASTEXITCODE

# 雙階段自適應晉升：若捕獲狀態碼 42，自動升級至 full 容器
if ($initialExitCode -eq 42) {
    Write-Host "`n[Auto-Detect] 捕獲晉升信號 (Exit Code 42)：目標網頁需無頭瀏覽器動態嗅探。" -ForegroundColor Yellow
    Write-Host "[Auto-Detect] 自動升級為完整版容器 (profile: full) 接續執行..." -ForegroundColor Cyan
    & docker-compose --profile full run --rm downloader-full $appArgs
    exit $LASTEXITCODE
}

exit $initialExitCode
