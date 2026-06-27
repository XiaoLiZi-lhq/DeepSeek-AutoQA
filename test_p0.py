"""P0 测试验证脚本
验证：Python 版本、依赖包 import、config.yaml 解析、目录结构完整性
"""
import sys
import os
import importlib

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def test_python_version():
    """检查 Python 版本 >= 3.8"""
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 8)
    return ok, f"{v.major}.{v.minor}.{v.micro}"

def test_imports():
    """检查四个关键包能否正常导入"""
    results = {}
    for pkg in ["playwright", "openpyxl", "PIL", "yaml"]:
        try:
            mod = importlib.import_module(pkg)
            ver = getattr(mod, "__version__", "N/A")
            results[pkg] = (True, ver)
        except ImportError as e:
            results[pkg] = (False, str(e))
    return results

def test_config_yaml():
    """检查 config.yaml 能否正常读取解析"""
    import yaml
    config_path = os.path.join(PROJECT_ROOT, "config", "config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return True, config

def test_directory_structure():
    """检查项目目录结构完整性"""
    expected = [
        "main.py",
        "setup.py",
        "requirements.txt",
        "README.md",
        "core/__init__.py",
        "core/browser.py",
        "core/deepseek_client.py",
        "core/excel_reader.py",
        "core/screenshot.py",
        "core/archiver.py",
        "core/logger.py",
        "config/config.yaml",
        "data/.gitkeep",
        "output/.gitkeep",
        "logs/.gitkeep",
    ]
    missing = []
    for rel_path in expected:
        full_path = os.path.join(PROJECT_ROOT, rel_path)
        if not os.path.exists(full_path):
            missing.append(rel_path)
    return len(missing) == 0, missing

def main():
    print("=" * 60)
    print("  P0 测试报告 — DeepSeek AutoQA")
    print("=" * 60)

    all_pass = True

    # 1. Python 版本
    ok, ver = test_python_version()
    status = "PASS" if ok else "FAIL"
    print(f"\n[1] Python 版本: {status}  ({ver})")
    if not ok:
        all_pass = False

    # 2. 依赖导入
    imports = test_imports()
    print("\n[2] 关键依赖包导入:")
    for pkg, (ok, ver) in imports.items():
        status = "PASS" if ok else "FAIL"
        print(f"    {pkg}: {status}  (version: {ver})")
        if not ok:
            all_pass = False

    # 3. config.yaml 解析
    ok, config = test_config_yaml()
    status = "PASS" if ok else "FAIL"
    print(f"\n[3] config.yaml 解析: {status}")
    for key in ["deepseek", "timeout", "retry", "screenshot", "paths", "schedule"]:
        print(f"    - {key}: {'OK' if key in config else 'MISSING'}")

    # 4. 目录结构
    ok, missing = test_directory_structure()
    status = "PASS" if ok else "FAIL"
    print(f"\n[4] 目录结构完整性: {status}")
    if missing:
        for m in missing:
            print(f"    MISSING: {m}")
        all_pass = False

    print("\n" + "=" * 60)
    final_status = "全部通过" if all_pass else "存在失败项"
    print(f"  测试结果: {final_status}")
    print("=" * 60)
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
