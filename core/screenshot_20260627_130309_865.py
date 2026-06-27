"""
P3: 截图模块 — 问答区域定位 + 滚动分段截取 + 长图拼接
基于 Playwright + Pillow，对 DeepSeek 回答区域进行智能截图。
"""

import asyncio
from datetime import datetime
from pathlib import Path
from io import BytesIO

from playwright.async_api import Page, ElementHandle
from PIL import Image


def _ts() -> str:
    """返回带时间戳的日志前缀。"""
    return datetime.now().strftime("[%H:%M:%S]")


# ------------------------------------------------------------------
# 回答区域定位选择器（多套备选，按优先级排列）
# ------------------------------------------------------------------

ANSWER_AREA_SELECTORS = [
    # 优先：会话消息列表中的最后一条消息
    '[class*="chat"] [class*="message"]:last-child',
    '[class*="conversation"] [class*="message"]:last-child',
    # 带 assistant 标识的区块（取最后一个）
    '[class*="assistant"]:last-of-type',
    # 通用回答/响应区块
    '[class*="answer"]',
    '[class*="response"]',
    '[class*="reply"]',
    # ds-markdown 是 DeepSeek 答复合集
    '[class*="ds-markdown"]',
    # 主内容区最后一块
    'main [class*="content"] > :last-child',
    # 更宽泛的兜底
    '[class*="chat"] [class*="text"]',
    '[class*="chat"] [class*="body"]',
]


class ScreenshotManager:
    """管理 DeepSeek 回答区域的截图、长图分段截取与拼接。"""

    def __init__(self, config: dict):
        """
        初始化 ScreenshotManager。

        Args:
            config: 从 config.yaml 解析后的配置字典。
        """
        self.config = config
        sc = config.get("screenshot", {})
        self.format: str = sc.get("format", "png")
        resolution = sc.get("min_resolution", [1920, 1080])
        self.viewport_width: int = resolution[0]
        self.viewport_height: int = resolution[1]

    # ------------------------------------------------------------------
    # 定位方法
    # ------------------------------------------------------------------

    async def locate_answer_area(self, page: Page) -> tuple:
        """
        定位当前页面上最新问答对所在的容器元素。

        依次尝试 ANSWER_AREA_SELECTORS 中的选择器，返回第一个匹配
        且可见的元素及其 bounding_box。

        Args:
            page: Playwright Page 实例。

        Returns:
            (element, bounding_box) 或 (None, None)。
            bounding_box 为 {'x','y','width','height'} 的 dict。
        """
        for sel in ANSWER_AREA_SELECTORS:
            try:
                el = await page.query_selector(sel)
                if el is None:
                    continue
                try:
                    visible = await el.is_visible()
                except Exception:
                    visible = False
                if not visible:
                    continue
                box = await el.bounding_box()
                if box is None or box.get("height", 0) <= 0:
                    continue
                print(f"{_ts()} 回答区域已定位，选择器: {sel}")
                return el, box
            except Exception:
                continue

        print(f"{_ts()} [警告] 未定位到回答区域，将降级为截取页面可见区域")
        return None, None

    # ------------------------------------------------------------------
    # 截图主方法
    # ------------------------------------------------------------------

    async def capture_answer(self, page: Page, output_path: str) -> bool:
        """
        截取当前页面上的最新回答并保存为 PNG。

        流程：
        1. 定位回答区域元素
        2. 若高度在可视区域内，直接元素截图
        3. 若高度超出，调用 scroll_and_stitch 分段拼接
        4. 保存到 output_path

        Args:
            page: Playwright Page 实例。
            output_path: 输出 PNG 文件的绝对路径。

        Returns:
            True 表示截图成功，False 表示失败。
        """
        print(f"{_ts()} 开始截图，输出: {output_path}")

        # 等待页面渲染稳定
        await asyncio.sleep(1)

        # 1. 定位回答区域
        element, box = await self.locate_answer_area(page)

        if element is None:
            # 降级：截取整个页面可见区域
            print(f"{_ts()} 降级为全页面可见区域截图")
            try:
                await page.screenshot(path=output_path, full_page=False)
                print(f"{_ts()} 全页面截图已保存")
                return True
            except Exception as e:
                print(f"{_ts()} [错误] 全页面截图失败: {e}")
                return False

        # 2. 判断是否需要长图拼接
        viewport_height = page.viewport_size.get("height", self.viewport_height)
        element_height = box["height"]

        print(f"{_ts()} 回答区域高度: {element_height:.0f}px, 视口高度: {viewport_height}px")

        if element_height <= viewport_height * 1.2:
            # 可视范围内，直接截取元素
            success = await self._capture_element(page, element, output_path)
            return success
        else:
            # 长回答，分段截取 + 拼接
            print(f"{_ts()} 回答较长，启动分段截取 + 拼接流程")
            return await self.scroll_and_stitch(page, element, output_path)

    async def _capture_element(self, page: Page, element: ElementHandle,
                                output_path: str) -> bool:
        """对单个元素直接截图并保存。"""
        try:
            await element.screenshot(path=output_path)
            print(f"{_ts()} 元素截图已保存")
            return True
        except Exception as e:
            print(f"{_ts()} [错误] 元素截图失败: {e}")
            try:
                await page.screenshot(path=output_path, full_page=False)
                print(f"{_ts()} 已降级为全页面截图")
                return True
            except Exception as e2:
                print(f"{_ts()} [错误] 降级截图也失败: {e2}")
                return False

    # ------------------------------------------------------------------
    # 长图分段截取 + 拼接
    # ------------------------------------------------------------------

    async def scroll_and_stitch(self, page: Page, element: ElementHandle,
                                 output_path: str, overlap: int = 100) -> bool:
        """
        对超长回答元素进行分段截取并拼接为一张长图。

        流程：
        1. 获取元素总高度
        2. 按视口高度分段截取，段间重叠 overlap px
        3. 调用 stitch_images 拼接
        4. 保存到 output_path

        Args:
            page: Playwright Page 实例。
            element: 回答区域 ElementHandle。
            output_path: 输出 PNG 路径。
            overlap: 段间重叠像素数（默认 100）。

        Returns:
            True 表示成功。
        """
        try:
            box = await element.bounding_box()
            total_height = box["height"]
        except Exception as e:
            print(f"{_ts()} [错误] 无法获取元素高度: {e}")
            await page.screenshot(path=output_path, full_page=False)
            return True

        viewport_height = page.viewport_size.get("height", self.viewport_height)
        step = max(1, viewport_height - overlap)
        total_segments = max(1, int((total_height + step - 1) // step))

        print(f"{_ts()} 总高度 {total_height:.0f}px, 分 {total_segments} 段截取")

        segment_images: list[Image.Image] = []

        for i in range(total_segments):
            scroll_y = i * step
            try:
                # 滚动页面使对应区域可见
                await page.evaluate(f"window.scrollTo(0, {scroll_y})")
                await asyncio.sleep(0.5)  # 等待渲染

                # 截取当前视口
                screenshot_bytes = await page.screenshot(full_page=False)
                img = Image.open(BytesIO(screenshot_bytes))
                segment_images.append(img)
                print(f"{_ts()} 第 {i+1}/{total_segments} 段已截取")
            except Exception as e:
                print(f"{_ts()} [错误] 第 {i+1}/{total_segments} 段截取失败: {e}")

        if not segment_images:
            print(f"{_ts()} [错误] 所有分段截取均失败")
            return False

        # 拼接
        return self.stitch_images(segment_images, output_path, overlap)

    # ------------------------------------------------------------------
    # Pillow 拼接
    # ------------------------------------------------------------------

    def stitch_images(self, images: list, output_path: str,
                       overlap: int = 100) -> bool:
        """
        使用 Pillow 将多张分段截图拼接为一张长图。

        像素级去重对齐：相邻两张图片在重叠区域内扫描对齐，
        找到差异最小的行作为最佳接缝，避免重复内容。

        Args:
            images: PIL Image 对象列表（按从上到下顺序）。
            output_path: 输出 PNG 路径。
            overlap: 固定重叠像素数（默认 100）。

        Returns:
            True 表示拼接成功。
        """
        if not images:
            return False

        if len(images) == 1:
            images[0].save(output_path, format="PNG")
            print(f"{_ts()} 单段截图，直接保存")
            return True

        print(f"{_ts()} 开始拼接 {len(images)} 张图片（overlap={overlap}px）...")

        result = images[0].copy()
        total_overlap_found = 0

        for idx, current in enumerate(images[1:], start=2):
            # 前一张的底部区域
            prev_bottom = result.crop((
                0,
                max(0, result.height - overlap),
                result.width,
                result.height,
            ))

            # 当前张的顶部区域
            current_top = current.crop((
                0,
                0,
                current.width,
                min(overlap, current.height),
            ))

            # 在重叠区域内找最佳对齐行（像素级差异最小）
            best_offset = overlap  # 默认完整 overlap
            best_diff = float("inf")

            search_range = min(overlap, prev_bottom.height, current_top.height)
            for offset in range(search_range):
                if offset >= prev_bottom.height or offset >= current_top.height:
                    break
                # 比较行
                row_prev = prev_bottom.crop((
                    0, prev_bottom.height - 1 - offset,
                    prev_bottom.width, prev_bottom.height - offset,
                ))
                row_curr = current_top.crop((
                    0, offset,
                    current_top.width, offset + 1,
                ))
                if row_prev.size != row_curr.size:
                    continue
                try:
                    # 简化的像素差异计算（采样比较）
                    diff = 0
                    px_prev = list(row_prev.getdata())
                    px_curr = list(row_curr.getdata())
                    for p1, p2 in zip(px_prev, px_curr):
                        diff += sum(abs(a - b) for a, b in zip(p1, p2))
                    if diff < best_diff:
                        best_diff = diff
                        best_offset = offset
                except Exception:
                    continue

            actual_overlap = overlap - best_offset
            total_overlap_found += actual_overlap
            seam = result.height - actual_overlap

            # 创建新画布，拼接两张图
            new_height = seam + current.height
            new_img = Image.new("RGB", (result.width, new_height))
            new_img.paste(result.crop((0, 0, result.width, seam)), (0, 0))
            new_img.paste(current, (0, seam))
            result = new_img

            print(f"{_ts()} 已拼接第 {idx}/{len(images)} 张 (接缝偏差 {best_offset}px)")

        # 保存
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path, format="PNG")
        file_size = Path(output_path).stat().st_size
        print(f"{_ts()} 长图拼接完成 — {result.width}x{result.height}px, "
              f"{file_size/1024:.1f}KB")
        return True
