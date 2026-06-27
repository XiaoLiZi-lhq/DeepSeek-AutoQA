"""
DeepSeek AutoQA - 自动问答截图工具
主程序入口，串联 P1-P4 所有模块。
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.browser import BrowserManager
from core.deepseek_client import DeepSeekClient
from core.excel_reader import ExcelReader
from core.screenshot import ScreenshotManager


def _ts() -> str:
    return datetime.now().strftime("[%H:%M:%S]")


def load_config(config_path: str = None) -> dict:
    """加载 config.yaml 并返回解析后的字典。"""
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    print(f"{_ts()} 配置已加载: {config_path}")
    return config


async def process_question(
    client: DeepSeekClient,
    screenshot_mgr: ScreenshotManager,
    brand_name: str,
    question: str,
    seq: int,
    output_dir: Path,
) -> dict:
    """
    处理单个问题：打开新对话 → 发送 → 等待 → 截图。

    Returns:
        {"seq": int, "brand": str, "question": str, "success": bool, "screenshot": str, "error": str}
    """
    result = {
        "seq": seq,
        "brand": brand_name,
        "question": question,
        "success": False,
        "screenshot": "",
        "error": "",
    }

    try:
        await client.open_new_chat()

        sent = await client.send_question(question)
        if not sent:
            result["error"] = "发送问题失败"
            return result

        answer_result = await client.wait_for_answer()
        if answer_result["timeout"]:
            print(f"{_ts()} [警告] 回答超时，尝试提取已有内容")

        date_str = datetime.now().strftime("%Y%m%d")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        brand_dir = output_dir / date_str / brand_name
        brand_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = brand_dir / f"{seq}_{brand_name}_{timestamp}.png"

        captured = await screenshot_mgr.capture_answer(
            client._page,
            str(screenshot_path),
        )

        if captured:
            result["success"] = True
            result["screenshot"] = str(screenshot_path)
        else:
            result["error"] = "截图失败"

    except Exception as e:
        result["error"] = str(e)
        print(f"{_ts()} [错误] 处理问题时异常: {e}")

    return result


async def main():
    """主流程入口。"""
    print("=" * 60)
    print(f"{_ts()} DeepSeek AutoQA 启动")
    print("=" * 60)

    config = load_config()

    excel_path = PROJECT_ROOT / config["paths"]["excel_file"]
    reader = ExcelReader(str(excel_path))

    if not reader.validate():
        print(f"{_ts()} [致命] Excel 校验失败，程序退出")
        return

    questions = reader.read_questions()
    if not questions:
        print(f"{_ts()} [致命] 没有可处理的问题，程序退出")
        return

    print(f"{_ts()} 共加载 {len(questions)} 个问题")

    browser = BrowserManager(config)
    await browser.start()

    try:
        await browser.ensure_login()
        client = DeepSeekClient(browser, config)
        screenshot_mgr = ScreenshotManager(config)

        output_dir = PROJECT_ROOT / config["paths"]["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        total = len(questions)
        for idx, q in enumerate(questions, start=1):
            print(f"\n{'─' * 40}")
            print(f"{_ts()} [{idx}/{total}] {q['brand_name']}: {q['question'][:50]}...")

            result = await process_question(
                client=client,
                screenshot_mgr=screenshot_mgr,
                brand_name=q["brand_name"],
                question=q["question"],
                seq=idx,
                output_dir=output_dir,
            )
            results.append(result)

            status = "成功" if result["success"] else "失败"
            print(f"{_ts()} [{idx}/{total}] {status}")

            if result["screenshot"]:
                print(f"       截图: {result['screenshot']}")

            if idx < total:
                await asyncio.sleep(5)

    finally:
        await browser.close()

    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count

    print("\n" + "=" * 60)
    print(f"{_ts()} 运行摘要")
    print("=" * 60)
    print(f"  总问题数: {len(results)}")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")

    if fail_count > 0:
        print("\n失败明细:")
        for r in results:
            if not r["success"]:
                print(f"  [{r['seq']}] {r['brand']}: {r['question'][:40]}... — {r['error']}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
