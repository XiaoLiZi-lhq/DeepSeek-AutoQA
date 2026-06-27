"""
P1 测试脚本：浏览器上下文管理 + 登录态持久化

用法：
    python test_p1.py              # 完整测试（会打开浏览器）
    python test_p1.py --dry-run    # 干跑模式，仅做模块导入和配置检查
"""

import os
import sys
import argparse
import asyncio
import yaml
from pathlib import Path
from datetime import datetime

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS = []
AUTH_FILE = PROJECT_ROOT / "auth.json"


def _ts() -> str:
    return datetime.now().strftime("[%H:%M:%S]")


def report(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    RESULTS.append((name, passed, detail))


def load_config():
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ------------------------------------------------------------------
# Dry-run 测试
# ------------------------------------------------------------------
def dry_run():
    print("=" * 60)
    print("P1 Dry-Run 测试")
    print("=" * 60)

    # 1. 导入 browser 模块
    try:
        from core.browser import BrowserManager  # noqa: F811
        report("导入 BrowserManager", True)
    except Exception as e:
        report("导入 BrowserManager", False, str(e))
        return

    # 2. 读取 config.yaml
    try:
        config = load_config()
        report("读取 config.yaml", True, f"deepseek.url={config['deepseek']['url']}")
    except Exception as e:
        report("读取 config.yaml", False, str(e))
        return

    # 3. 创建 BrowserManager 实例
    try:
        bm = BrowserManager(config)
        report("创建 BrowserManager 实例", True, f"auth_file={bm.auth_file_path}")
    except Exception as e:
        report("创建 BrowserManager 实例", False, str(e))
        return

    # 4. verify auth_file_path
    expected_auth = PROJECT_ROOT / config["deepseek"]["auth_file"]
    if bm.auth_file_path == expected_auth:
        report("auth_file 路径正确", True, str(expected_auth))
    else:
        report("auth_file 路径正确", False, f"{bm.auth_file_path} != {expected_auth}")

    # 5. verify viewport config
    if bm.viewport == {"width": 1920, "height": 1080}:
        report("视口配置", True, "1920x1080")
    else:
        report("视口配置", False, str(bm.viewport))

    print("\nDry-Run 测试完成。")
    print_summary()


# ------------------------------------------------------------------
# 真实浏览器测试
# ------------------------------------------------------------------
async def live_test():
    print("=" * 60)
    print("P1 真实浏览器测试")
    print("=" * 60)

    from core.browser import BrowserManager

    config = load_config()

    # 1. 导入模块
    report("导入 BrowserManager", True)

    # 2. 读取配置
    report("读取 config.yaml", True, f"deepseek.url={config['deepseek']['url']}")

    # 3. 创建实例
    bm = BrowserManager(config)
    report("创建 BrowserManager 实例", True, f"auth_file={bm.auth_file_path}")

    # 清理旧的 auth.json（确保从头开始测试）
    if AUTH_FILE.exists():
        AUTH_FILE.unlink()
        print(f"  [INFO] 已删除旧的 auth.json")

    # 4. 启动浏览器
    try:
        await bm.start()
        report("启动浏览器", True, "Chromium 已启动")
    except Exception as e:
        report("启动浏览器", False, str(e))
        return

    # 5. 首次 ensure_login（用户需手动登录）
    try:
        await bm.ensure_login()
        report("ensure_login（首次）", True, "登录成功")
    except Exception as e:
        report("ensure_login（首次）", False, str(e))
        await bm.close()
        return

    # 6. 验证 auth.json 已生成
    if AUTH_FILE.exists():
        size = AUTH_FILE.stat().st_size
        report("auth.json 已生成", True, f"{size} 字节")
    else:
        report("auth.json 已生成", False, "文件不存在")

    # 7. 关闭浏览器
    await bm.close()
    report("关闭浏览器", True)

    # 8. 重新启动，测试会话恢复
    print(f"\n{_ts()} --- 重新启动浏览器，测试会话恢复 ---")
    bm2 = BrowserManager(config)
    await bm2.start()
    report("第二次启动浏览器", True)

    session_loaded = await bm2.load_session()
    if session_loaded:
        report("load_session 恢复会话", True)
    else:
        report("load_session 恢复会话", False, "auth.json 加载失败")

    logged_in = await bm2.check_login()
    if logged_in:
        report("会话恢复后 check_login", True, "已登录")
    else:
        report("会话恢复后 check_login", False, "未登录（可能已过期）")

    await bm2.close()
    report("第二次关闭浏览器", True)

    print("\n所有真实浏览器测试完成。")
    print_summary()


# ------------------------------------------------------------------
# 输出汇总
# ------------------------------------------------------------------
def print_summary():
    total = len(RESULTS)
    passed = sum(1 for _, p, _ in RESULTS if p)
    print(f"\n{'=' * 60}")
    print(f"测试汇总: {passed}/{total} 通过")
    for name, ok, detail in RESULTS:
        status = "PASS" if ok else "FAIL"
        line = f"  [{status}] {name}"
        if detail:
            line += f" — {detail}"
        print(line)
    print(f"{'=' * 60}")


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="P1 测试脚本")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干跑模式，仅检查模块导入和配置",
    )
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
    else:
        asyncio.run(live_test())


if __name__ == "__main__":
    main()
