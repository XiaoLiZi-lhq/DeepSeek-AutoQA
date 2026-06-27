"""
P6 测试脚本：日志系统（文件轮转 + 7天清理 + 控制台输出）
"""

import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.logger import LogManager

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(PROJECT_DIR, "logs")


def main():
    results = []
    print("=" * 60)
    print("P6 测试：日志系统")
    print("=" * 60)

    # ── 1. 创建 LogManager 实例 ──
    mgr = LogManager(log_dir=LOG_DIR, retention_days=7)
    results.append(("LogManager 实例化", "PASS", f"log_dir={LOG_DIR}, retention_days=7"))

    # ── 2. setup() 获取 logger ──
    logger = mgr.setup()
    results.append(("setup() 获取 logger", "PASS", f"logger 名称: {logger.name}"))

    # ── 3. 各日志级别写入测试消息 ──
    logger.debug("这是一条 DEBUG 测试消息")
    logger.info("这是一条 INFO 测试消息")
    logger.warning("这是一条 WARNING 测试消息")
    logger.error("这是一条 ERROR 测试消息")
    results.append(("各日志级别写入", "PASS", "debug / info / warning / error 已写入"))

    # ── 4. 验证日志文件已生成 ──
    log_path = mgr.get_log_path()
    if os.path.isfile(log_path):
        results.append(("日志文件已生成", "PASS", log_path))
    else:
        results.append(("日志文件已生成", "FAIL", f"未找到 {log_path}"))

    # ── 5. 验证日志内容格式 ──
    with open(log_path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    format_ok = True
    detail = ""
    for line in lines:
        parts = line.split("] [", 1)
        if len(parts) != 2 or not parts[0].startswith("[20"):
            format_ok = False
            detail = f"格式异常行: {line[:80]}"
            break
        time_and_level = parts[0] + "] [" + parts[1].split("]", 1)[0] + "]"
        # 期望格式: [YYYY-MM-DD HH:MM:SS] [LEVEL]
        # 简单校验时间戳和级别部分
        if not time_and_level.startswith("[") or "] [" not in time_and_level:
            format_ok = False
            detail = f"格式异常行: {line[:80]}"
            break

    if format_ok:
        results.append(("日志内容格式", "PASS", f"{len(lines)} 行格式正确"))
    else:
        results.append(("日志内容格式", "FAIL", detail))

    # ── 6. 测试 cleanup_old_logs ──
    # 创建模拟旧日志文件
    old_files = []
    for days_ago in [8, 9, 3]:
        old_date = datetime.now() - timedelta(days=days_ago)
        old_name = f"log_{old_date.strftime('%Y-%m-%d')}.log"
        old_path = os.path.join(LOG_DIR, old_name)
        with open(old_path, "w") as f:
            f.write("old log\n")
        # 设置文件修改时间为 days_ago 天前
        ts = time.time() - days_ago * 86400
        os.utime(old_path, (ts, ts))
        old_files.append((old_path, days_ago))

    # 也创建一个非 log_ 前缀文件，应被保留
    other_file = os.path.join(LOG_DIR, "other.txt")
    with open(other_file, "w") as f:
        f.write("not a log\n")

    mgr.cleanup_old_logs()

    # 验证：8天和9天前文件应被删除，3天前应保留，other.txt 应保留
    cleanup_ok = True
    cleanup_detail = []
    for old_path, days_ago in old_files:
        exists = os.path.isfile(old_path)
        if days_ago > 7 and exists:
            cleanup_ok = False
            cleanup_detail.append(f"{os.path.basename(old_path)} 应被删除但未删除")
        elif days_ago <= 7 and not exists:
            cleanup_ok = False
            cleanup_detail.append(f"{os.path.basename(old_path)} 不应被删除但已删除")
    if not os.path.isfile(other_file):
        cleanup_ok = False
        cleanup_detail.append("other.txt 不应被删除但已删除")

    if cleanup_ok:
        results.append(("cleanup_old_logs", "PASS", "旧文件正确清理，保留期内文件正确保留"))
    else:
        results.append(("cleanup_old_logs", "FAIL", "; ".join(cleanup_detail)))

    # 清理模拟文件
    for old_path, _ in old_files:
        if os.path.isfile(old_path):
            os.remove(old_path)
    if os.path.isfile(other_file):
        os.remove(other_file)

    # ── 7. 输出测试报告 ──
    print("\n" + "=" * 60)
    print("P6 测试报告")
    print("=" * 60)
    all_pass = True
    for name, status, detail in results:
        status_mark = "✓" if status == "PASS" else "✗"
        if status != "PASS":
            all_pass = False
        print(f"  [{status_mark}] {name}")
        if detail:
            print(f"       {detail}")

    print("-" * 60)
    print(f"  总结: {'全部通过' if all_pass else '存在失败项'}")
    print(f"  日志文件: {log_path}")
    print("=" * 60)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
