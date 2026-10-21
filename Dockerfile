# ==============================================================
# Target 1: slim (預設輕量版 ~420MB，適合 90% YouTube/Twitch/標準串流)
# ==============================================================
FROM python:3.10-slim AS slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# 安裝系統相依：FFmpeg, curl, ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安裝基礎 Python 依賴 (yt-dlp, psutil, curl_cffi)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式原始碼
COPY src/ ./src/
COPY main.py .

# 建立下載目錄與非 root 帳號 appuser
RUN mkdir -p /app/downloads && \
    useradd -u 1000 -m appuser && \
    chown -R appuser:appuser /app

USER appuser

# 輕量版健康檢查 (檢驗 FFmpeg、yt-dlp、curl_cffi)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import yt_dlp, psutil, curl_cffi, shutil; assert shutil.which('ffmpeg')" || exit 1

VOLUME ["/app/downloads"]
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]

# ==============================================================
# Target 2: full (完整動態嗅探版 ~1.4GB，含 Playwright 與 Chromium)
# ==============================================================
FROM slim AS full

USER root

# 設定全域 Playwright 瀏覽器存放路徑
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 安裝 Playwright 套件並下載 Chromium 二進位檔及其 Linux 系統相依庫
COPY requirements-full.txt .
RUN pip install --no-cache-dir -r requirements-full.txt && \
    playwright install chromium --with-deps && \
    mkdir -p /ms-playwright && \
    chmod -R 777 /ms-playwright && \
    rm -rf /var/lib/apt/lists/*

# 切回非 root 帳號
USER appuser

# 完整版健康檢查 (額外檢驗 Playwright 模組)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import yt_dlp, psutil, curl_cffi, playwright, shutil; assert shutil.which('ffmpeg')" || exit 1
