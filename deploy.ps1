# PyStream-Downloader Windows 一鍵部署與啟動腳本
[CmdletBinding()]
param (
    [string]$Url = "",
    [string]$Quality = "",
    [switch]$BuildOnly
)

# 強制設定控制台編碼為 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host '==========================================================' -ForegroundColor Cyan
Write-Host ' PyStream-Downloader 容器化部署與執行腳本 (Windows)       ' -ForegroundColor Cyan
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
Write-Host '[2/3] 正在建置 pystream-downloader:latest 映像檔...' -ForegroundColor Yellow
docker build -t pystream-downloader:latest .
if ($LASTEXITCODE -ne 0) {
    Write-Host '[Error] 映像檔建置失敗！' -ForegroundColor Red
    exit 1
}
Write-Host '[OK] 映像檔建置完成。' -ForegroundColor Green

if ($BuildOnly) {
    Write-Host '[SUCCESS] 映像檔已就緒。可使用 docker-compose 或 docker run 啟動。' -ForegroundColor Green
    exit 0
}

# 3. 啟動容器下載
Write-Host '[3/3] 準備啟動下載任務...' -ForegroundColor Yellow
$downloadsPath = Join-Path (Get-Location) 'downloads'
if (-not (Test-Path $downloadsPath)) {
    New-Item -ItemType Directory -Path $downloadsPath | Out-Null
}

# 檢測終端是否支援互動式 TTY
$interactiveFlags = @('-i')
try {
    if (-not [Console]::IsInputRedirected) {
        $interactiveFlags = @('-it')
    }
} catch {
    $interactiveFlags = @('-i')
}

$cmdArgs = @('run', '--rm') + $interactiveFlags + @('-v', "${downloadsPath}:/app/downloads", 'pystream-downloader:latest')

if ($Url -ne "") {
    $cmdArgs += $Url
    if ($Quality -ne "") {
        $cmdArgs += @("-q", $Quality)
    }
}

Write-Host "執行指令: docker $($cmdArgs -join ' ')" -ForegroundColor Cyan
& docker $cmdArgs
