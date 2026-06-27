"""
P3: 截图模块 — 问答区域定位 + 滚动分段截取 + 长图拼接
提供 ScreenshotManager 类，对 DeepSeek 最新回答区域进行截图，支持长回答拼接。
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image
from playwright.async_api import Page, ElementHandle


def _ts() -> str:
    """返回带时间戳的日志前缀。"""
    return datetime.now().strftime("[%H:%M:%S]")


# ------------------------------------------------------------------
# 回答区域定位选择器（多套备选）
# ------------------------------------------------------------------

ANSWER_AREA_SELECTORS = [
    '[class*="chat"] [class*="message"]:last-child',
    '[class*="chat"] [class*="assistant"]:last-of-type',
    '[class*="conversation"] [class*="message"]:last-child',
    '[class*="ds-markdown"]:last-of-type',
    '[class*="answer"]',
    '[class*="response"]',
    '[class*="conversation"]',
    '[class*="assistant"]',
]

# 备选：直接取所有消息元素中最后一个可视的
FALLBACK_MESSAGE_SELECTORS = [
    '[class*="message"]',
    '[class*="bubble"]',
    '[class*="turn"]',
]


class ScreenshotManager:
    """管理回答区域截图、长图分段截取与拼接。"""

    def __init__(self, config: dict):
        """
        初始化 ScreenshotManager。

        Args:
            config: 从 config.yaml 解析的完整配置字典。
        """
        self.config = config
        screenshot_cfg = config.get("screenshot", {})
        self.format: str = screenshot_cfg.get("format", "png")
        resolution = screenshot_cfg.get("min_resolution", [1920, 1080])
        self.viewport_width: int = resolution[0]
        self.viewport_height: int = resolution[1]
        self.stitch_overlap: int = 100  # 分段截取重叠像素

    # ------------------------------------------------------------------
    # 定位方法
    # ------------------------------------------------------------------

    async def locate_answer_area(self, page: Page) -> Tuple[Optional[ElementHandle], Optional[dict]]:
        """
        定位当前页面上最新问答对所在的容器元素。

        Args:
            page: Playwright Page 实例。

        Returns:
            (element, bounding_box) 或 (None, None) 表示未定位到。
        """
        # 多套选择器依次尝试
        for sel in ANSWER_AREA_SELECTORS:
            try:
                el = await page.query_selector(sel)
                if el is None:
                    continue
                visible = await el.is_visible()
                if not visible:
                    continue
                box = await el.bounding_box()
                if box and box["height"] > 0:
                    print(f"{_ts()} 定位到回答区域: {sel} ({box['width']:.0f}x{box['height']:.0f})")
                    return el, box
            except Exception:
                continue

        # 兜底1：取最后一个 message 元素
        for sel in FALLBACK_MESSAGE_SELECTORS:
            try:
                elements = await page.query_selector_all(sel)
                if not elements:
                    continue
                # 取最后一个可见的
                for el in reversed(elements):
                    try:
                        visible = await el.is_visible()
                        if not visible:
                            continue
                        box = await el.bounding_box()
                        if box and box["height"] > 0:
                            print(f"{_ts()} 兜底定位到回答区域: {sel} (最后一个, {box['width']:.0f}x{box['height']:.0f})")
                            return el, box
                    except Exception:
                        continue
            except Exception:
                continue

        # 兜底2：取 main 元素或 body
        try:
            main = await page.query_selector("main")
            if main:
                visible = await main.is_visible()
                if visible:
                    box = await main.bounding_box()
                    if box and box["height"] > 0:
                        print(f"{_ts()} 兜底定位到 <main> 元素 ({box['width']:.0f}x{box['height']:.0f})")
                        return main, box
        except Exception:
            pass

        print(f"{_ts()} 未能定位到回答区域")
        return None, None

    # ------------------------------------------------------------------
    # 截图主方法
    # ------------------------------------------------------------------

    async def capture_answer(self, page: Page, output_path: str) -> bool:
        """
        截取当前页面上最新回答区域，保存为 PNG。

        流程：
        1. 定位回答区域
        2. 判断高度：可视区域内直接截取，超出则调用 scroll_and_stitch
        3. 降级：定位不到回答区域就截取整个页面可见区域

        Args:
            page: Playwright Page 实例。
            output_path: 输出 PNG 文件路径。

        Returns:
            True 表示截图成功，False 表示失败。
        """
        output_path = str(output_path)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        element, box = await self.locate_answer_area(page)

        if element is None or box is None:
            print(f"{_ts()} 降级：截取整个页面可见区域")
            try:
                await page.screenshot(path=output_path, full_page=False, type="png")
                size = os.path.getsize(output_path)
                print(f"{_ts()} 全页截图已保存: {output_path} ({size} bytes)")
                return size > 0
            except Exception as e:
                print(f"{_ts()} 全页截图失败: {e}")
                return False

        visible_height = self.viewport_height

        if box["height"] <= visible_height * 1.2:
            # 回答在可视区域内，直接截取元素
            try:
                await element.screenshot(path=output_path, type="png")
                size = os.path.getsize(output_path)
                print(f"{_ts()} 直接截图已保存: {output_path} ({size} bytes)")
                return size > 0
            except Exception as e:
                print(f"{_ts()} 元素截图失败: {e}，降级为全页截图")
                try:
                    await page.screenshot(path=output_path, full_page=False, type="png")
                    size = os.path.getsize(output_path)
                    print(f"{_ts()} 降级全页截图已保存: {output_path} ({size} bytes)")
                    return size > 0
                except Exception as e2:
                    print(f"{_ts()} 降级全页截图也失败: {e2}")
                    return False
        else:
            # 长回答，走滚动分段截取 + 拼接
            print(f"{_ts()} 回答高度 {box['height']:.0f}px 超出可视区域，启动长图拼接")
            return await self.scroll_and_stitch(page, element, output_path)

    # ------------------------------------------------------------------
    # 滚动分段截取 + 拼接
    # ------------------------------------------------------------------

    async def scroll_and_stitch(self, page: Page, element: ElementHandle, output_path: str) -> bool:
        """
        对长回答元素进行滚动分段截取，然后拼接为一张长图。

        Args:
            page: Playwright Page 实例。
            element: 回答区域的 ElementHandle。
            output_path: 输出 PNG 文件路径。

        Returns:
            True 表示拼接成功，False 表示失败。
        """
        try:
            box = await element.bounding_box()
            if box is None:
                print(f"{_ts()} 获取元素尺寸失败")
                return False

            total_height = box["height"]
            element_y = box["y"]
            element_x = box["x"]
            element_width = box["width"]

            overlap = self.stitch_overlap
            viewport_h = self.viewport_height

            # 计算分段数量
            # 每段截取 viewport_h 高度（从元素顶部开始），相邻段有 overlap 重叠
            step = viewport_h - overlap
            num_segments = max(1, int((total_height - overlap) / step) + (1 if (total_height - overlap) % step > 0 else 0))

            print(f"{_ts()} 总高度 {total_height:.0f}px，分 {num_segments} 段截取（overlap={overlap}px）")

            segment_paths = []
            temp_dir = os.path.dirname(output_path)

            for i in range(num_segments):
                scroll_y = min(i * step, max(0, total_height - viewport_h))

                # 滚动到对应位置
                await page.evaluate(f"window.scrollTo({{top: {element_y + scroll_y - 50}, behavior: 'instant'}})")
                await asyncio.sleep(0.5)

                # 截取当前可见区域（全页 viewport）
                seg_path = os.path.join(temp_dir, f"_stitch_seg_{i:03d}.png")
                await page.screenshot(path=seg_path, full_page=False, type="png")
                segment_paths.append(seg_path)
                print(f"{_ts()}   分段 {i+1}/{num_segments} 已截取: scroll_y={scroll_y}")

            # 拼接分段
            success = self.stitch_images(segment_paths, output_path, overlap)

            # 清理临时分段文件
            for sp in segment_paths:
                try:
                    os.remove(sp)
                except Exception:
                    pass

            if success:
                size = os.path.getsize(output_path)
                print(f"{_ts()} 长图拼接完成: {output_path} ({size} bytes)")
            else:
                print(f"{_ts()} 长图拼接失败")

            return success

        except Exception as e:
            print(f"{_ts()} scroll_and_stitch 异常: {e}")
            # 降级为全页截图
            try:
                await page.screenshot(path=output_path, full_page=False, type="png")
                return os.path.getsize(output_path) > 0
            except Exception:
                return False

    # ------------------------------------------------------------------
    # Pillow 像素级拼接
    # ------------------------------------------------------------------

    def stitch_images(self, images: list, output_path: str, overlap: int = 100) -> bool:
        """
        使用 Pillow 将多张分段截图拼接为一张长图。
        相邻分段重叠区域去重对齐。

        Args:
            images: 分段截图文件路径列表（从上到下顺序）。
            output_path: 输出拼接后 PNG 文件路径。
            overlap: 相邻分段间的重叠像素数。

        Returns:
            True 表示拼接成功。
        """
        if not images:
            print(f"{_ts()} stitch_images: 空列表")
            return False

        if len(images) == 1:
            # 只有一张图，直接复制
            try:
                img = Image.open(images[0])
                img.save(output_path, "PNG")
                return True
            except Exception as e:
                print(f"{_ts()} 单图保存失败: {e}")
                return False

        try:
            # 加载所有图片
            pil_images = []
            for path in images:
                img = Image.open(path)
                pil_images.append(img)

            # 计算拼接后总尺寸
            widths = [im.width for im in pil_images]
            heights = [im.height for im in pil_images]

            # 要求所有图宽度一致（viewport 截图保证）
            max_width = max(widths)
            min_width = min(widths)
            if max_width != min_width:
                print(f"{_ts()} 警告：分段截图宽度不一致 ({min_width}-{max_width}px)，统一为 {max_width}px")

            # 总高度 = 第一张全高 + 后续每张去掉 overlap 后的高度
            total_height = heights[0]
            for h in heights[1:]:
                total_height += (h - overlap)

            # 创建画布
            canvas = Image.new("RGB", (max_width, total_height))

            # 粘贴第一张
            current_y = 0
            if pil_images[0].width == max_width:
                canvas.paste(pil_images[0], (0, 0))
            else:
                resized = pil_images[0].resize((max_width, heights[0]))
                canvas.paste(resized, (0, 0))
            current_y = heights[0]

            # 逐张粘贴后续图片，去掉 overlap 区域
            for i in range(1, len(pil_images)):
                im = pil_images[i]
                if im.width != max_width:
                    im = im.resize((max_width, im.height))

                # 从 overlap 像素处开始裁剪（上方与上一张重叠的部分跳过）
                crop_top = overlap
                crop_height = im.height - overlap
                if crop_height > 0:
                    cropped = im.crop((0, crop_top, max_width, im.height))
                    canvas.paste(cropped, (0, current_y))
                    current_y += crop_height

            canvas.save(output_path, "PNG")
            return True

        except Exception as e:
            print(f"{_ts()} stitch_images 异常: {e}")
            return False
