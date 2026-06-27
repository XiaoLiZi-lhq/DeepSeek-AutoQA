"""
P3 测试脚本：整合 P1+P2+P3 全流程端到端测试
测试截图模块 — 直接截图 + 长图拼接
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import yaml
from core.browser import BrowserManager
from core.deepseek_client import DeepSeekClient
from core.screenshot import ScreenshotManager

RESULTS = []


def _ts() -> str:
    return datetime.now().strftime("[%H:%M:%S]")


def log_result(test_name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    msg = f"  [{status}] {test_name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    RESULTS.append({"test": test_name, "passed": passed, "detail": detail})


async def main():
    print("=" * 60)
    print("P3 截图模块集成测试")
    print("=" * 60)

    # ----------------------------------------------------------------
    # 1. 加载配置
    # ----------------------------------------------------------------
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    log_result("读取 config.yaml", True, f"deepseek.url={config['deepseek']['url']}")

    # ----------------------------------------------------------------
    # 2. 导入模块验证
    # ----------------------------------------------------------------
    try:
        from core.screenshot import ScreenshotManager  # noqa: F811
        log_result("导入 ScreenshotManager", True)
    except Exception as e:
        log_result("导入 ScreenshotManager", False, str(e))
        return print_report()

    # ----------------------------------------------------------------
    # 3. 创建 ScreenshotManager 实例
    # ----------------------------------------------------------------
    try:
        sm = ScreenshotManager(config)
        log_result(
            "创建 ScreenshotManager 实例",
            True,
            f"viewport={sm.viewport_width}x{sm.viewport_height}, overlap={sm.stitch_overlap}px",
        )
    except Exception as e:
        log_result("创建 ScreenshotManager 实例", False, str(e))
        return print_report()

    # ----------------------------------------------------------------
    # 4. 启动浏览器 + 加载会话
    # ----------------------------------------------------------------
    bm = BrowserManager(config)
    try:
        await bm.start()
        log_result("启动浏览器", True)
    except Exception as e:
        log_result("启动浏览器", False, str(e))
        return print_report()

    try:
        logged_in = await bm.ensure_login()
        log_result("ensure_login", True)
    except Exception as e:
        log_result("ensure_login", False, str(e))
        return print_report()

    # ----------------------------------------------------------------
    # 5. 创建 DeepSeekClient
    # ----------------------------------------------------------------
    try:
        client = DeepSeekClient(bm, config)
        log_result("创建 DeepSeekClient", True)
    except Exception as e:
        log_result("创建 DeepSeekClient", False, str(e))
        return print_report()

    # 准备输出目录
    output_dir = PROJECT_ROOT / "output" / "test"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------
    # 6. 测试问题1：短回答（直接截图）
    # ----------------------------------------------------------------
    test1_path = output_dir / "p3_test_q1_short.png"
    question1 = "请写一首关于夏天的五言绝句"

    print(f"\n{_ts()} === 测试问题1（短回答）: {question1} ===")

    try:
        await client.open_new_chat()
        log_result("Q1: open_new_chat", True)
    except Exception as e:
        log_result("Q1: open_new_chat", False, str(e))
        return print_report()

    # 等待页面稳定
    await asyncio.sleep(2)

    try:
        sent = await client.send_question(question1)
        log_result("Q1: send_question", sent)
    except Exception as e:
        log_result("Q1: send_question", False, str(e))
        return print_report()

    try:
        result1 = await client.wait_for_answer()
        log_result(
            "Q1: wait_for_answer",
            result1["completed"] or result1["timeout"],
            f"completed={result1['completed']}, timeout={result1['timeout']}, text_len={len(result1['answer_text'])}",
        )
    except Exception as e:
        log_result("Q1: wait_for_answer", False, str(e))
        return print_report()

    # 截图
    await asyncio.sleep(3)  # 等待渲染完成
    try:
        ok1 = await sm.capture_answer(bm._page, str(test1_path))
        log_result(
            "Q1: capture_answer",
            ok1,
            f"path={test1_path}, size={os.path.getsize(test1_path) if ok1 else 0}",
        )
    except Exception as e:
        log_result("Q1: capture_answer", False, str(e))

    # ----------------------------------------------------------------
    # 7. 测试问题2：长回答（触发长图拼接）
    # ----------------------------------------------------------------
    await asyncio.sleep(5)  # 间隔，避免限流

    test2_path = output_dir / "p3_test_q2_long.png"
    question2 = "请详细介绍人工智能的发展历程，从1950年代开始"

    print(f"\n{_ts()} === 测试问题2（长回答）: {question2} ===")

    try:
        await client.open_new_chat()
        log_result("Q2: open_new_chat", True)
    except Exception as e:
        log_result("Q2: open_new_chat", False, str(e))

    await asyncio.sleep(2)

    try:
        sent2 = await client.send_question(question2)
        log_result("Q2: send_question", sent2)
    except Exception as e:
        log_result("Q2: send_question", False, str(e))

    try:
        result2 = await client.wait_for_answer()
        log_result(
            "Q2: wait_for_answer",
            result2["completed"] or result2["timeout"],
            f"completed={result2['completed']}, timeout={result2['timeout']}, text_len={len(result2['answer_text'])}",
        )
    except Exception as e:
        log_result("Q2: wait_for_answer", False, str(e))

    # 截图（长回答，应走拼接逻辑）
    await asyncio.sleep(3)
    try:
        ok2 = await sm.capture_answer(bm._page, str(test2_path))
        size2 = os.path.getsize(test2_path) if ok2 else 0
        log_result(
            "Q2: capture_answer（长图拼接）",
            ok2 and size2 > 0,
            f"path={test2_path}, size={size2} bytes",
        )
    except Exception as e:
        log_result("Q2: capture_answer", False, str(e))

    # ----------------------------------------------------------------
    # 8. 清理
    # ----------------------------------------------------------------
    try:
        await bm.close()
        log_result("关闭浏览器", True)
    except Exception as e:
        log_result("关闭浏览器", False, str(e))

    print_report()


def print_report():
    print("\n" + "=" * 60)
    print("P3 测试报告")
    print("=" * 60)

    passed = sum(1 for r in RESULTS if r["passed"])
    failed = len(RESULTS) - passed

    for r in RESULTS:
        status = "PASS" if r["passed"] else "FAIL"
        detail = f" — {r['detail']}" if r["detail"] else ""
        print(f"  [{status}] {r['test']}{detail}")

    print(f"\n测试汇总: {passed}/{len(RESULTS)} 通过")

    if failed > 0:
        print(f"\n{_ts()} 有 {failed} 项未通过，请检查上述 FAIL 项")
    else:
        print(f"\n{_ts()} P3 全部测试通过！")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
