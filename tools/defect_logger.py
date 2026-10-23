#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defect Logger & Ticket Generator
落實 workflow.md 階段 3B 瑕疵工單與 Log 留存資料流機制：
1. 完整測試日誌捕獲至 .scratch/logs/test_run_<timestamp>.log
2. 自動解析失敗斷言與行號
3. 生成結構化 JSONL 記錄至 .scratch/logs/defects.jsonl
4. 同步更新 docs/04_test_report.md 瑕疵工單章節
"""

import os
import sys
import re
import json
import subprocess
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.path.join(PROJECT_ROOT, ".scratch", "logs")
REPORT_PATH = os.path.join(PROJECT_ROOT, "docs", "04_test_report.md")


def ensure_dirs():
    os.makedirs(LOG_DIR, exist_ok=True)


def run_tests_and_capture(cmd=None):
    if cmd is None:
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]

    ensure_dirs()
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_log_file = os.path.join(LOG_DIR, f"test_run_{timestamp_str}.log")

    print(f"[INFO] 正在執行測試命令: {' '.join(cmd)}")
    print(f"[INFO] 原始日誌留存路徑: {raw_log_file}")

    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    full_output = []
    with open(raw_log_file, "w", encoding="utf-8") as f_out:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            f_out.write(line)
            full_output.append(line)

    proc.wait()
    return proc.returncode, "".join(full_output), raw_log_file


def parse_unittest_failures(output_text):
    defects = []
    # Pattern to match: FAIL: test_name (module.Class) or ERROR: test_name (module.Class)
    pattern = re.compile(
        r"={5,}\n(FAIL|ERROR):\s+(.+?)\s+\((.+?)\)\n-{5,}\n([\s\S]*?)(?=\n={5,}|\n-{5,}\nRan |\Z)",
        re.MULTILINE
    )

    matches = pattern.findall(output_text)
    ticket_counter = 1
    today_str = datetime.now().strftime("%Y%m%d")

    for kind, test_func, test_class, body in matches:
        body_clean = body.strip()
        lines = body_clean.split("\n")

        # Extract file and line number from traceback
        file_line_matches = re.findall(r'File "([^"]+)", line (\d+), in (.+)', body_clean)
        if file_line_matches:
            last_file, last_line, last_func = file_line_matches[-1]
            # normalize relative path
            rel_file = os.path.relpath(last_file, PROJECT_ROOT) if os.path.isabs(last_file) else last_file
            location = f"{rel_file}:{last_line}"
        else:
            location = "unknown"

        # Extract last error line (assertion or exception)
        error_lines = [l for l in lines if re.search(r'(Error|Exception|FAIL|FAILED):', l)]
        error_msg = error_lines[-1] if error_lines else (lines[-1] if lines else "Unknown error")

        ticket_id = f"DEF-3B-{today_str}-{ticket_counter:03d}"
        ticket_counter += 1

        defects.append({
            "ticket_id": ticket_id,
            "kind": kind,
            "test_id": f"{test_class}.{test_func}",
            "location": location,
            "error_msg": error_msg,
            "snippet": "\n".join(lines[-25:]),  # last 25 lines of traceback
            "assigned_role": "Gemini 3.8 Flash",
            "severity": "Important",
            "status": "OPEN",
            "created_at": datetime.now().isoformat()
        })

    return defects


def save_defects_jsonl(defects, raw_log_file):
    jsonl_path = os.path.join(LOG_DIR, "defects.jsonl")
    with open(jsonl_path, "a", encoding="utf-8") as f:
        for d in defects:
            record = dict(d)
            record["raw_log_file"] = os.path.relpath(raw_log_file, PROJECT_ROOT)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[INFO] 瑕疵工單結構化記錄已附加至: {jsonl_path}")


def update_test_report_with_defects(defects, raw_log_file, returncode):
    if not os.path.exists(REPORT_PATH):
        print(f"[WARN] 找不到測試報告: {REPORT_PATH}")
        return

    content = open(REPORT_PATH, encoding="utf-8").read()

    # Section for defect tickets
    defect_section_header = "## 5. 瑕疵工單與修復追蹤清單 (Defect Tickets & Remediation)"
    
    if len(defects) == 0 and returncode == 0:
        defect_block = f"""{defect_section_header}

- **當前工單狀態**：**0 項未決瑕疵工單 (0 Open Tickets)**
- **最新測試日誌**：`{os.path.relpath(raw_log_file, PROJECT_ROOT)}`
- **全數驗收結論**：所有測試全數通過，無須發派修復工單。
"""
    else:
        items = []
        for d in defects:
            items.append(f"""### 工單編號：`{d['ticket_id']}` ({d['kind']})
- **所屬階段**：階段 3B 測試執行
- **測試項目**：`{d['test_id']}`
- **失敗位置**：`{d['location']}`
- **失敗原因**：`{d['error_msg']}`
- **指派修復角色**：`{d['assigned_role']}`
- **嚴重度分級**：`{d['severity']}`
- **處理狀態**：`{d['status']}`
- **重現指令**：
  ```bash
  python -m unittest {d['test_id']}
  ```
- **精華診斷日誌 (Snippet)**：
  ```text
{d['snippet']}
  ```
""")
        defect_block = f"""{defect_section_header}

> **注意**：發現 {len(defects)} 項測試瑕疵。依循 `workflow.md` 閉環規範，已自動立單指派 **{defects[0]['assigned_role']}** 進行修復。修復完成後須從 R1 重新執行全套件測試。

- **原始日誌參照**：`{os.path.relpath(raw_log_file, PROJECT_ROOT)}`
- **工單清單**：

{"".join(items)}
"""

    # Replace existing Section 5 or append
    if defect_section_header in content:
        # replace from defect_section_header to next header or end
        parts = content.split(defect_section_header)
        prefix = parts[0]
        # find if there is another section after
        rest = parts[1]
        next_sec = re.search(r"\n##\s+", rest)
        if next_sec:
            suffix = rest[next_sec.start():]
            new_content = prefix.rstrip() + "\n\n" + defect_block.strip() + "\n" + suffix.lstrip()
        else:
            new_content = prefix.rstrip() + "\n\n" + defect_block.strip() + "\n"
    else:
        new_content = content.rstrip() + "\n\n---\n\n" + defect_block.strip() + "\n"

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"[INFO] 測試報告瑕疵清單已更新: {REPORT_PATH}")


def main():
    returncode, output_text, raw_log_file = run_tests_and_capture()
    defects = parse_unittest_failures(output_text)

    if defects:
        print(f"\n[ALERT] 測試未完全通過！捕獲 {len(defects)} 項瑕疵工單：")
        for d in defects:
            print(f"  - [{d['ticket_id']}] {d['test_id']} -> {d['error_msg']}")
        save_defects_jsonl(defects, raw_log_file)
    else:
        print("\n[SUCCESS] 測試全數通過，無任何瑕疵工單！")

    update_test_report_with_defects(defects, raw_log_file, returncode)
    sys.exit(returncode)


if __name__ == "__main__":
    main()
