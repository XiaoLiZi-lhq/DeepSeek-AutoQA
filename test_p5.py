"""
P5 测试脚本
测试 Archiver：目录路径、截图归档、Q&A 缓存、TXT 汇总写入。
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/Users/lihongqin/Desktop/DeepSeek-AutoQA")
sys.path.insert(0, str(PROJECT_ROOT))

import yaml
from core.archiver import Archiver

PASS_COUNT = 0
FAIL_COUNT = 0


def test(name: str, condition: bool, detail: str = ""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  [v] {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL_COUNT += 1
        print(f"  [X] {name}" + (f" — {detail}" if detail else ""))


def run_tests():
    global PASS_COUNT, FAIL_COUNT
    PASS_COUNT = 0
    FAIL_COUNT = 0

    print("=" * 60)
    print("P5 测试 — TXT 汇总生成 + 目录归档")
    print("=" * 60)

    # 加载配置
    config = yaml.safe_load(
        (PROJECT_ROOT / "config" / "config.yaml").read_text(encoding="utf-8")
    )
    test("加载 config.yaml", "deepseek" in config)

    # ---- Part 1: 实例化 Archiver ----
    print("\n--- Part 1: Archiver 实例化 & get_output_dir ---")

    archiver = Archiver(config)
    test("实例化 Archiver", isinstance(archiver, Archiver))

    # 测试 get_output_dir（指定日期）
    dir1 = archiver.get_output_dir("20260627")
    expected_suffix = "output/20260627"
    test("get_output_dir 返回路径包含 output/20260627",
         expected_suffix in dir1.replace("\\", "/"),
         dir1)

    # 测试 get_output_dir（不传日期，使用当天）
    dir2 = archiver.get_output_dir()
    today = datetime.now().strftime("%Y%m%d")
    test(f"get_output_dir() 默认当天日期包含 {today}",
         today in dir2, dir2)

    # ---- Part 2: append_qa + write_summary ----
    print("\n--- Part 2: append_qa + write_summary ---")

    archiver.append_qa(
        seq=1,
        brand_name="华为",
        timestamp="2026-06-27 14:30:22",
        question="华为2024年营收是多少？",
        answer="根据华为2024年年报，华为全年实现全球销售收入约8621亿元人民币。",
    )
    archiver.append_qa(
        seq=2,
        brand_name="华为",
        timestamp="2026-06-27 14:32:18",
        question="华为Mate 70系列主要卖点有哪些？",
        answer="Mate 70系列搭载HarmonyOS NEXT系统、AI摄影、卫星通信等核心卖点。",
    )
    test("append_qa 缓存 2 条记录", len(archiver._qa_cache) == 2)

    # 写入 TXT
    date_str = datetime.now().strftime("%Y%m%d")
    summary_path = archiver.write_summary(date_str)
    test("write_summary 返回路径", bool(summary_path),
         summary_path)

    summary_file = Path(summary_path)
    test("TXT 文件已生成", summary_file.exists())

    content = summary_file.read_text(encoding="utf-8")
    test("TXT 包含 #001", "#001" in content)
    test("TXT 包含品牌名", "华为" in content)
    test("TXT 包含时间戳", "2026-06-27 14:30:22" in content)
    test("TXT 包含【问题】标记", "【问题】" in content)
    test("TXT 包含【回答】标记", "【回答】" in content)
    test("TXT 包含分隔线", "====" in content)
    test("TXT 包含两条记录", content.count("#001") + content.count("#002") >= 2)

    lines = content.strip().split("\n")
    test("TXT 非空", len(lines) > 0, f"{len(lines)} 行")

    # ---- Part 3: archive_screenshot ----
    print("\n--- Part 3: archive_screenshot ---")

    # 创建测试用截图
    test_img_dir = PROJECT_ROOT / "output" / "test"
    test_img_dir.mkdir(parents=True, exist_ok=True)
    test_src = test_img_dir / "P5_test_source.png"

    # 用 Python 创建一个最小的 1x1 PNG
    from PIL import Image
    img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    img.save(str(test_src))

    test("创建测试截图", test_src.exists(),
         f"{test_src.stat().st_size} bytes")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived_path = archiver.archive_screenshot(
        src_path=str(test_src),
        brand_name="华为",
        seq=1,
        timestamp=timestamp,
    )
    test("archive_screenshot 返回路径", bool(archived_path),
         archived_path)

    archived_file = Path(archived_path)
    test("归档文件存在", archived_file.exists())
    test("归档文件大小 > 0", archived_file.stat().st_size > 0,
         f"{archived_file.stat().st_size} bytes")

    # 验证目标路径结构
    relative = archived_path.replace(str(PROJECT_ROOT), "").replace("\\", "/")
    test("归档路径包含品牌目录", "/华为/" in relative, relative)
    test("归档路径包含日期", today in relative, relative)

    # 清理测试截图源文件
    test_src.unlink(missing_ok=True)

    # ---- 汇总 ----
    print("\n" + "=" * 60)
    total = PASS_COUNT + FAIL_COUNT
    print(f"测试汇总: {PASS_COUNT}/{total} 通过")
    if FAIL_COUNT > 0:
        print(f"  {FAIL_COUNT} 项失败")
    else:
        print("  全部通过！")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
