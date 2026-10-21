"""Command line interface and interactive orchestration for PyStream-Downloader."""

import argparse
import os
import sys

from . import __version__
from .downloader import FFmpegDownloader
from .extractor import EXIT_CODE_NEED_FULL_SNIFFER, NeedsFullSnifferError, StreamExtractor
from .supervisor import ProcessSupervisor
from .utils import (
    check_impersonate_support,
    check_system_dependencies,
    sanitize_filename,
    verify_mp4_integrity,
)
from .watcher import StreamWatcher


def parse_arguments(args=None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="pystream-downloader",
        description="PyStream-Downloader: 基於 yt-dlp 與 FFmpeg 的智慧串流下載工具",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("url", nargs="?", help="目標影片或串流網址 (URL)")
    parser.add_argument("-q", "--quality", help="指定畫質 (例如: 1080p, 720p, 480p, best)")
    parser.add_argument("-o", "--output", default="./downloads", help="指定儲存目錄 (預設: ./downloads)")
    parser.add_argument("--wait", action="store_true", help="啟用開播輪詢監聽 (若串流未開播則自動等待)")
    parser.add_argument("--poll-interval", type=int, default=15, help="開播輪詢監聽間隔秒數 (預設: 15)")
    parser.add_argument("--max-retries", type=int, default=5, help="斷線最大重試次數 (預設: 5)")
    parser.add_argument("--no-pause", action="store_true", help="停用鍵盤熱鍵即時暫停功能 (適用於背景排程)")
    parser.add_argument(
        "--impersonate",
        default="chrome",
        help="啟用瀏覽器網路指紋偽裝以繞過 Cloudflare 等反爬蟲機制 (預設: chrome，可設為 none 停用，或指定 firefox, safari 等)",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        help="從本機瀏覽器提取 Cookies (例如: chrome, firefox, edge, safari, brave, opera)",
    )
    parser.add_argument(
        "--sniff",
        choices=["auto", "always", "never"],
        default="auto",
        help="無頭瀏覽器動態串流嗅探模式 (auto: 遇未支援網站自動啟動; always: 強制啟用; never: 停用, 預設: auto)",
    )
    parser.add_argument(
        "--sniff-timeout",
        type=int,
        default=15,
        help="動態串流嗅探最長等待秒數 (預設: 15)",
    )
    return parser.parse_args(args)


def interactive_select_quality(formats: list[dict]) -> str:
    """Display format options in console and prompt user for selection."""
    if not formats:
        return "best"

    print("\n" + "=" * 60)
    print("可用畫質清單：")
    print(f"  [0] 自動選擇最佳畫質 (Best Quality)")
    for idx, fmt in enumerate(formats, start=1):
        res = fmt.get("resolution", "N/A")
        bitrate = fmt.get("bitrate_kbps", 0)
        vcodec = fmt.get("vcodec", "N/A")
        print(f"  [{idx}] {res:<8} | 碼率: ~{bitrate} kbps | 編碼: {vcodec}")
    print("=" * 60)

    while True:
        try:
            choice = input(f"\n請選擇畫質編號 [0-{len(formats)}] (預設 0): ").strip()
            if not choice or choice == "0":
                return formats[0]["format_id"]

            idx = int(choice)
            if 1 <= idx <= len(formats):
                return formats[idx - 1]["format_id"]
            else:
                print("輸入超出範圍，請重新輸入。")
        except (ValueError, KeyboardInterrupt):
            print("\n採用預設最佳畫質。")
            return formats[0]["format_id"]


def run_app():
    """Main application flow."""
    args = parse_arguments()

    if not args.url:
        args.url = input("請輸入影片或串流網址 (URL): ").strip()
        if not args.url:
            print("未提供網址，程式結束。")
            sys.exit(1)

    # 判斷 impersonate 設定與系統支援狀態
    impersonate_target = None
    if args.impersonate and args.impersonate.lower() not in ("none", "false", "off"):
        impersonate_target = args.impersonate
        if not check_impersonate_support():
            print(
                "[WARN] 未檢測到 curl_cffi 套件或不支援 Impersonate，將嘗試標準模式連線。"
                "若遇 Cloudflare 403 請執行: pip install curl_cffi"
            )

    print(f"\n[INFO] 正在分析串流: {args.url}")
    if impersonate_target:
        print(f"[INFO] 已啟用瀏覽器指紋偽裝模式: {impersonate_target}")
    if args.cookies_from_browser:
        print(f"[INFO] 已啟用瀏覽器 Cookies 提取: {args.cookies_from_browser}")

    # 1. 檢查開播狀態 (若指定 --wait 或直播可能未開始)
    if args.wait:
        print(f"[INFO] 啟用開播監聽模式 (輪詢間隔: {args.poll_interval}s)...")
        watcher = StreamWatcher(
            args.url,
            poll_interval=args.poll_interval,
            impersonate=impersonate_target,
            cookies_from_browser=args.cookies_from_browser,
        )

        def on_tick(rem, attempt):
            print(f"\r[WAIT] 串流尚未開始 (第 {attempt} 次檢測)，倒數 {rem} 秒後重試...", end="", flush=True)

        is_live = watcher.wait_until_live(on_tick=on_tick)
        print("\n")
        if not is_live:
            print("[INFO] 等候已取消或中斷。")
            sys.exit(0)
        print("[SUCCESS] 串流已正式開播！啟動下載準備...")

    # 2. 提取規格與畫質
    extractor = StreamExtractor(
        args.url,
        impersonate=impersonate_target,
        cookies_from_browser=args.cookies_from_browser,
        sniff_mode=args.sniff,
        sniff_timeout=args.sniff_timeout,
    )
    try:
        title = extractor.get_title()
        formats = extractor.get_available_formats()
    except NeedsFullSnifferError as e:
        print(f"\n[Auto-Detect] {e}")
        print("[Auto-Detect] 正在向調度器發送自適應升級信號 (Exit code: 42)...")
        sys.exit(EXIT_CODE_NEED_FULL_SNIFFER)
    except Exception as e:
        print(f"[ERROR] 解析串流失敗: {e}")
        sys.exit(1)

    safe_title = sanitize_filename(title)
    print(f"[INFO] 影片標題: {title}")

    # 3. 畫質選擇
    selected_format_id = None
    if args.quality:
        if args.quality.lower() == "best":
            selected_format_id = None
        else:
            selected_format_id = args.quality
    else:
        selected_format_id = interactive_select_quality(formats)

    stream_url, quality_label, headers = extractor.resolve_stream_details(selected_format_id)
    print(f"[INFO] 已選定畫質: {quality_label}")

    # 4. 準備輸出路徑
    os.makedirs(args.output, exist_ok=True)
    out_filename = f"{safe_title}_{quality_label}.mp4"
    output_path = os.path.join(args.output, out_filename)
    print(f"[INFO] 目標儲存路徑: {output_path}")

    # 5. 啟動守護進程下載 (攜帶 HTTP Headers 避免分片取片遭遇 403)
    downloader = FFmpegDownloader(
        stream_url=stream_url,
        output_path=output_path,
        headers=headers,
    )
    supervisor = ProcessSupervisor(downloader=downloader, max_retries=args.max_retries)

    def on_progress(p):
        sys.stdout.write(f"\r[錄製中] 時間: {p['time']} | 大小: {p['size']} | 速率: {p['bitrate']} | 速度: {p['speed']}  ")
        sys.stdout.flush()

    if not args.no_pause:
        print("[TIP] 下載進行中可隨時按「空白鍵」或「p」暫停/恢復錄製。按 Ctrl+C 安全停止。")

    success = False
    try:
        success = supervisor.run(on_progress=on_progress, enable_hotkey=not args.no_pause)
    except KeyboardInterrupt:
        print("\n\n[INFO] 接收到中斷指令，正在安全停止並儲存 MP4 索引...")
        supervisor.stop()
        success = True

    print("\n")
    if success:
        if verify_mp4_integrity(output_path):
            print(f"[SUCCESS] 影片下載完成且完整性檢驗通過！檔案位置: {output_path}")
        else:
            print(f"[WARNING] 下載完成，但檔案格式驗證異常，請檢查內容: {output_path}")
    else:
        print(f"[FAILED] 下載失敗，請檢查網路連線或日誌。")
        sys.exit(1)
