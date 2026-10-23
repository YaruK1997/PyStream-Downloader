"""Process supervisor module with pause/resume and auto-reconnection capability."""

import os
import sys
import threading
import time
from typing import Callable, Optional

from .downloader import FFmpegDownloader


class ProcessSupervisor:
    """Supervises the FFmpeg download process.

    Provides keyboard-driven pause/resume (using psutil) and automated crash recovery.
    """

    def __init__(self, downloader: FFmpegDownloader, max_retries: int = 5):
        self.downloader = downloader
        self.max_retries = max_retries
        self.current_process = None
        self._psutil_proc = None
        self.is_paused = False
        self._stop_requested = False
        self._keyboard_thread = None

    def _get_psutil(self):
        try:
            import psutil
            return psutil
        except ImportError:
            return None

    def pause(self) -> bool:
        """Pause (freeze) the downloading process without killing connections."""
        if self.is_paused or not self.current_process:
            return False

        psutil = self._get_psutil()
        if psutil:
            try:
                self._psutil_proc = psutil.Process(self.current_process.pid)
                self._psutil_proc.suspend()
                self.is_paused = True
                return True
            except Exception as e:
                print(f"\n[Warning] 暫停進程失敗: {e}")
                return False
        else:
            print("\n[Warning] 缺少 psutil 套件，無法即時暫停進程。請執行: pip install psutil")
            return False

    def resume(self) -> bool:
        """Resume (unfreeze) the downloading process."""
        if not self.is_paused or not self._psutil_proc:
            return False

        try:
            self._psutil_proc.resume()
            self.is_paused = False
            return True
        except Exception as e:
            print(f"\n[Warning] 恢復進程失敗: {e}")
            return False

    def toggle_pause(self):
        """Toggle pause/resume state."""
        if self.is_paused:
            if self.resume():
                print("\n\033[92m[▶ RESUMED] 下載繼續中...\033[0m")
        else:
            if self.pause():
                print("\n\033[93m[⏸ PAUSED] 下載已暫停 (按 'p' 或空白鍵繼續)\033[0m")

    def _listen_keyboard(self):
        """Background thread listening for keypresses on Windows / Unix."""
        try:
            if sys.platform == "win32":
                import msvcrt
                while not self._stop_requested and self.current_process:
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        # 'p', 'P', or Space
                        if ch in (b"p", b"P", b" "):
                            self.toggle_pause()
                    time.sleep(0.1)
            else:
                # Unix basic check
                while not self._stop_requested and self.current_process:
                    time.sleep(0.5)
        except Exception:
            pass

    def stop(self):
        """Gracefully terminate downloading."""
        self._stop_requested = True
        if self.current_process and self.current_process.poll() is None:
            # If paused, resume first before terminating
            if self.is_paused:
                self.resume()
            try:
                # Send 'q' to ffmpeg for clean exit
                self.current_process.stdin.write("q\n")
                self.current_process.stdin.flush()
                self.current_process.wait(timeout=5)
            except Exception:
                try:
                    self.current_process.terminate()
                except Exception:
                    pass

    def run(self, on_progress: Optional[Callable[[dict], None]] = None, enable_hotkey: bool = True) -> bool:
        """Execute download with automated retries and supervisor monitoring."""
        retry_count = 0

        while retry_count <= self.max_retries and not self._stop_requested:
            try:
                self.current_process = self.downloader.start_process()
                self.is_paused = False

                if enable_hotkey and (not self._keyboard_thread or not self._keyboard_thread.is_alive()):
                    self._keyboard_thread = threading.Thread(target=self._listen_keyboard, daemon=True)
                    self._keyboard_thread.start()

                recent_stderr_lines = []

                # Read progress stream from stderr
                for line in self.current_process.stderr:
                    if self._stop_requested:
                        break
                    prog = self.downloader.parse_progress(line)
                    if prog and on_progress:
                        on_progress(prog)
                    else:
                        clean_line = line.strip()
                        if clean_line:
                            recent_stderr_lines.append(clean_line)
                            if len(recent_stderr_lines) > 20:
                                recent_stderr_lines.pop(0)

                ret_code = self.current_process.wait()

                # 0 is success
                if ret_code == 0:
                    return True
                elif self._stop_requested:
                    return True
                else:
                    # Non-zero return code indicates crash or network failure
                    retry_count += 1
                    error_details = ""
                    if recent_stderr_lines:
                        err_sample = [
                            l for l in recent_stderr_lines
                            if not l.startswith("frame=") and not l.startswith("size=")
                        ][-5:]
                        if err_sample:
                            error_details = "\n  FFmpeg 日誌片段:\n  " + "\n  ".join(err_sample)

                    if retry_count > self.max_retries:
                        print(f"\n[Error] FFmpeg 異常退出 (Exit code: {ret_code})，已達最大重試次數 ({self.max_retries})。{error_details}")
                        return False

                    backoff = min(30, 2 ** retry_count)
                    print(f"\n[Retry] 下載異常中斷 (Exit code: {ret_code})，第 {retry_count}/{self.max_retries} 次重試，{backoff} 秒後重新連接...{error_details}")
                    time.sleep(backoff)

            except Exception as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    print(f"\n[Error] 執行異常: {e}，重試次數超限。")
                    return False
                time.sleep(3)

        return False
