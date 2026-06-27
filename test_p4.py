"""
P4 测试脚本
测试 ExcelReader、数据校验、主流程串联。
建议先跑 1 个问题验证全流程，再跑完整的 3 个问题。
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path("/Users/lihongqin/Desktop/DeepSeek-AutoQA")
sys.path.insert(0, str(PROJECT_ROOT))

import yaml
from core.excel_reader import ExcelReader
from core.browser import BrowserManager
from core.deepseek_client import DeepSeekClient
from core.screenshot import ScreenshotManager


PASS_COUNT = 0
FAIL_COUNT = 0


def test(name: str, condition: bool, detail: str = ""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  [{chr(8730)}] {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL_COUNT += 1
        print(f"  [X] {name}" + (f" — {detail}" if detail else ""))


async def run_tests():
    global PASS_COUNT, FAIL_COUNT
    PASS_COUNT = 0
    FAIL_COUNT = 0

    print("=" * 60)
    print("P4 测试 — Excel 读取 + 数据校验 + 主流程串联")
    print("=" * 60)

    # ---- Part 1: ExcelReader 单元测试 ----
    print("\n--- Part 1: ExcelReader 单元测试 ---")

    excel_path = PROJECT_ROOT / "data" / "questions.xlsx"
    test("文件存在", excel_path.exists(), str(excel_path))

    reader = ExcelReader(str(excel_path))
    test("实例化 ExcelReader", True)

    valid = reader.validate()
    test("validate() 返回 True", valid)

    questions = reader.read_questions()
    test("read_questions() 非空", len(questions) > 0, f"共 {len(questions)} 条")
    test("返回格式正确", isinstance(questions, list) and "brand_name" in questions[0])

    expected = [
        {"brand_name": "华为", "question": "华为2024年营收是多少？"},
        {"brand_name": "华为", "question": "华为Mate 70系列主要卖点有哪些？"},
        {"brand_name": "华为", "question": "华为在AI领域的战略布局是怎样的？"},
    ]
    test("数据内容匹配", questions == expected)

    # ---- Part 2: 模块导入测试 ----
    print("\n--- Part 2: 模块导入测试 ---")
    test("import yaml", True)
    test("import ExcelReader", True)
    test("import BrowserManager", True)
    test("import DeepSeekClient", True)
    test("import ScreenshotManager", True)

    # 加载配置
    config = yaml.safe_load(
        (PROJECT_ROOT / "config" / "config.yaml").read_text(encoding="utf-8")
    )
    test("加载 config.yaml", "deepseek" in config)

    # ---- Part 3: 全流程测试（仅 1 个问题）----
    print("\n--- Part 3: 全流程测试（仅 1 个问题，避免触发限流）---")

    browser = BrowserManager(config)
    await browser.start()
    test("启动浏览器", True)

    try:
        await browser.ensure_login()
        test("登录成功", True)

        client = DeepSeekClient(browser, config)
        screenshot_mgr = ScreenshotManager(config)

        q = questions[0]
        print(f"\n  测试问题: [{q['brand_name']}] {q['question']}")

        await client.open_new_chat()
        test("打开新对话", True)

        sent = await client.send_question(q["question"])
        test("发送问题", sent)

        answer = await client.wait_for_answer()
        test("等待回答完成", answer["completed"], f"timeout={answer['timeout']}")
        test("回答文本非空", len(answer["answer_text"]) > 0,
             f"{len(answer['answer_text'])} 字符")

        # 截图
        date_str = datetime.now().strftime("%Y%m%d")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = PROJECT_ROOT / "output" / "test"
        output_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = output_dir / f"P4_test_{q['brand_name']}_{timestamp}.png"

        captured = await screenshot_mgr.capture_answer(
            client._page, str(screenshot_path)
        )
        test("截图成功", captured)

        if captured and screenshot_path.exists():
            size = screenshot_path.stat().st_size
            test("截图文件大小 > 0", size > 0, f"{size} bytes")
        else:
            test("截图文件存在", False, "截图未生成")

    finally:
        await browser.close()
        test("关闭浏览器", True)

    # ---- 汇总 ----
    print("\n" + "=" * 60)
    print(f"测试汇总: {PASS_COUNT}/{PASS_COUNT + FAIL_COUNT} 通过")
    if FAIL_COUNT > 0:
        print(f"  {FAIL_COUNT} 项失败")
    else:
        print("  全部通过！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
