"""
P5: TXT 汇总生成 + 目录归档
提供 Archiver 类，负责截图归档和 Q&A 汇总 TXT。
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


class Archiver:
    """截图归档与 Q&A 汇总管理器。"""

    def __init__(self, config: dict):
        """
        接收 config.yaml 解析后的字典。

        Args:
            config: 完整配置字典，paths.output_dir 指定输出根目录。
        """
        self.config = config
        self._qa_cache: list[dict] = []

    # ------------------------------------------------------------------
    # 路径辅助
    # ------------------------------------------------------------------

    def get_output_dir(self, date_str: Optional[str] = None) -> str:
        """
        获取输出目录路径：output/YYYYMMDD/。

        Args:
            date_str: 日期字符串，格式 YYYYMMDD。不传则用当天日期。

        Returns:
            输出目录的绝对路径字符串。
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")

        output_root = self.config["paths"]["output_dir"]
        if not os.path.isabs(output_root):
            project_root = Path(__file__).resolve().parent.parent
            output_root = str(project_root / output_root)

        return str(Path(output_root) / date_str)

    # ------------------------------------------------------------------
    # 截图归档
    # ------------------------------------------------------------------

    def archive_screenshot(
        self, src_path: str, brand_name: str, seq: int, timestamp: str
    ) -> str:
        """
        将截图复制到归档目录。

        目标路径：output/YYYYMMDD/{brand_name}/{序号}_{brand_name}_{timestamp}.png

        Args:
            src_path: 原始截图路径。
            brand_name: 品牌名称。
            seq: 序号（从 1 开始）。
            timestamp: 时间戳字符串，格式 YYYYMMDD_HHMMSS。

        Returns:
            归档后的目标绝对路径。
        """
        date_str = timestamp[:8]
        dest_dir = Path(self.get_output_dir(date_str)) / brand_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        ext = os.path.splitext(src_path)[1] or ".png"
        dest_filename = f"{seq}_{brand_name}_{timestamp}{ext}"
        dest_path = dest_dir / dest_filename

        shutil.copy2(src_path, str(dest_path))
        return str(dest_path)

    # ------------------------------------------------------------------
    # Q&A 缓存
    # ------------------------------------------------------------------

    def append_qa(
        self,
        seq: int,
        brand_name: str,
        timestamp: str,
        question: str,
        answer: str,
    ):
        """
        追加一条 Q&A 记录到内存缓存。

        Args:
            seq: 序号。
            brand_name: 品牌名称。
            timestamp: 时间戳字符串，格式 "YYYY-MM-DD HH:MM:SS"。
            question: 问题文本。
            answer: 回答文本。
        """
        self._qa_cache.append({
            "seq": seq,
            "brand_name": brand_name,
            "timestamp": timestamp,
            "question": question,
            "answer": answer,
        })

    # ------------------------------------------------------------------
    # TXT 汇总写入
    # ------------------------------------------------------------------

    def write_summary(self, date_str: Optional[str] = None) -> str:
        """
        将所有缓存的 Q&A 写入 output/qa_summary_YYYYMMDD.txt。

        Args:
            date_str: 日期字符串 YYYYMMDD。不传则用当天日期。

        Returns:
            生成的 TXT 文件绝对路径。
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")

        output_root = self.config["paths"]["output_dir"]
        if not os.path.isabs(output_root):
            project_root = Path(__file__).resolve().parent.parent
            output_root = str(project_root / output_root)

        output_dir = Path(output_root) / date_str
        output_dir.mkdir(parents=True, exist_ok=True)

        file_path = output_dir / f"qa_summary_{date_str}.txt"

        lines = []
        for record in self._qa_cache:
            seq = record["seq"]
            brand = record["brand_name"]
            ts = record["timestamp"]
            question = record["question"].strip()
            answer = record["answer"].strip()

            lines.append("=" * 40)
            lines.append(f"#{seq:03d} | {brand} | {ts}")
            lines.append(f"【问题】{question}")
            lines.append(f"【回答】{answer}")
            lines.append("=" * 40)
            lines.append("")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return str(file_path)
