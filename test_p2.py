"""
P2 测试脚本：验证 DeepSeekClient 所有核心功能。
"""

import sys
import os
import asyncio

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.browser import BrowserManager
from core.deepseek_client import DeepSeekClient
import yaml


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def main():
    results = []
    browser = None

    def report(name, passed, detail=""):
        status = "PASS" if passed else "FAIL"
        results.append((name, passed, detail))
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

    print("=" * 60)
    print("P2 真实浏览器测试")
    print("=" * 60)

    # --- 1. 导入模块 ---
    try:
        from core.deepseek_client import DeepSeekClient
        report("导入 DeepSeekClient", True)
    except Exception as e:
        report("导入 DeepSeekClient", False, str(e))
        return

    # --- 2. 读取配置 ---
    try:
        config = load_config()
        report("读取 config.yaml", True,
               f"deepseek.url={config['deepseek']['url']}")
    except Exception as e:
        report("读取 config.yaml", False, str(e))
        return

    # --- 3. 创建 BrowserManager ---
    try:
        browser = BrowserManager(config)
        report("创建 BrowserManager 实例", True,
               f"auth_file={browser.auth_file_path}")
    except Exception as e:
        report("创建 BrowserManager 实例", False, str(e))
        return

    # --- 4. 启动浏览器 ---
    try:
        await browser.start()
        report("启动浏览器", True, "Chromium 已启动")
    except Exception as e:
        report("启动浏览器", False, str(e))
        return

    # --- 5. 加载会话 ---
    try:
        session_loaded = await browser.load_session()
        if session_loaded:
            report("load_session 恢复会话", True)
        else:
            report("load_session", False, "auth.json 不存在，无法继续测试")
            await browser.close()
            return
    except Exception as e:
        report("load_session", False, str(e))
        await browser.close()
        return

    # --- 6. 检测登录 ---
    try:
        logged_in = await browser.check_login()
        report("check_login", logged_in,
               "已登录" if logged_in else "未登录")
        if not logged_in:
            print("  需要手动登录，请运行 P1 测试先获取 auth.json")
            await browser.close()
            return
    except Exception as e:
        report("check_login", False, str(e))
        await browser.close()
        return

    # --- 7. 创建 DeepSeekClient ---
    try:
        client = DeepSeekClient(browser, config)
        report("创建 DeepSeekClient 实例", True)
    except Exception as e:
        report("创建 DeepSeekClient 实例", False, str(e))
        await browser.close()
        return

    # --- 8. 打开新对话 ---
    try:
        ok = await client.open_new_chat()
        report("open_new_chat", ok, "新对话已就绪" if ok else "失败")
    except Exception as e:
        report("open_new_chat", False, str(e))
        await browser.close()
        return

    # --- 9. 发送测试问题 ---
    test_question = "请用一句话介绍你自己"
    try:
        ok = await client.send_question(test_question)
        report("send_question", ok,
               f"问题已发送" if ok else "发送失败")
    except Exception as e:
        report("send_question", False, str(e))
        await browser.close()
        return

    # --- 10. 等待回答 ---
    try:
        result = await client.wait_for_answer()
        completed = result["completed"]
        timeout = result["timeout"]
        answer = result["answer_text"]
        report("wait_for_answer", completed or timeout,
               f"completed={completed}, timeout={timeout}, text_len={len(answer)}")
    except Exception as e:
        report("wait_for_answer", False, str(e))
        await browser.close()
        return

    # --- 11. 验证回答非空 ---
    try:
        non_empty = bool(answer and len(answer.strip()) > 0)
        report("回答文本非空", non_empty,
               f"长度={len(answer)} 字符" if non_empty else "回答为空")
    except Exception as e:
        report("回答文本非空", False, str(e))

    # --- 12. 打印回答文本 ---
    print()
    print("--- 回答文本预览（前 300 字符）---")
    if answer:
        print(answer[:300])
        if len(answer) > 300:
            print("...（截断）")
    else:
        print("（无回答文本）")
    print("--- 回答文本预览结束 ---")

    # --- 13. 关闭浏览器 ---
    try:
        await browser.close()
        report("关闭浏览器", True)
    except Exception as e:
        report("关闭浏览器", False, str(e))

    # --- 汇总 ---
    print()
    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    print(f"测试汇总: {passed}/{total} 通过")
    for name, p, detail in results:
        status = "PASS" if p else "FAIL"
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
