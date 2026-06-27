"""
P1: 浏览器上下文管理 + 登录态持久化
基于 Playwright 异步 API，管理 Chromium 浏览器生命周期和 DeepSeek 登录状态。
"""

import os
import asyncio
import json
from datetime import datetime
from typing import Optional
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


def _ts() -> str:
    """返回带时间戳的日志前缀。"""
    return datetime.now().strftime("[%H:%M:%S]")


class BrowserManager:
    """管理 Playwright Chromium 浏览器实例与 DeepSeek 登录会话。"""

    def __init__(self, config: dict):
        """
        初始化 BrowserManager。

        Args:
            config: 从 config.yaml 解析的完整配置字典。
        """
        self.config = config
        self.deepseek_url: str = config["deepseek"]["url"]
        self.auth_file_rel: str = config["deepseek"]["auth_file"]
        self.viewport: dict = {
            "width": 1920,
            "height": 1080,
        }
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # 将 auth_file 相对路径解析为绝对路径
        project_root = Path(__file__).resolve().parent.parent
        self.auth_file_path: Path = project_root / self.auth_file_rel

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """启动 Playwright Chromium 浏览器（非无头模式）。"""
        print(f"{_ts()} 正在启动 Chromium 浏览器...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,
        )
        self._context = await self._browser.new_context(viewport=self.viewport)
        self._page = await self._context.new_page()
        print(f"{_ts()} 浏览器启动完成（视口 {self.viewport['width']}x{self.viewport['height']}）")

    async def load_session(self) -> bool:
        """
        检查 auth.json 是否存在并加载 storage_state 恢复会话。

        Returns:
            True 表示成功加载并恢复了会话，False 表示 auth.json 不存在。
        """
        if not self.auth_file_path.exists():
            print(f"{_ts()} auth.json 不存在，需要全新登录")
            return False

        print(f"{_ts()} 找到 auth.json，正在恢复会话...")
        await self._context.close()
        self._context = await self._browser.new_context(
            viewport=self.viewport,
            storage_state=str(self.auth_file_path),
        )
        self._page = await self._context.new_page()
        print(f"{_ts()} 会话恢复完成")
        return True

    async def save_session(self) -> None:
        """导出当前 storage_state 到 auth.json。"""
        state = await self._context.storage_state()
        self.auth_file_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"{_ts()} 登录态已保存至 {self.auth_file_path}")

    async def check_login(self) -> bool:
        """
        检测当前页面是否已登录 DeepSeek。

        检测逻辑：
        1. 先检查当前页面 URL——如果已在 chat 页面且不是登录页，直接检测 DOM
        2. 仅当当前页面不在目标 URL 时才执行导航（避免重复刷新）
        3. DOM 检测：聊天输入框存在 → 已登录；登录按钮存在 → 未登录

        Returns:
            True 表示已登录，False 表示未登录。
        """
        if self._page is None:
            raise RuntimeError("浏览器尚未启动，请先调用 start()")

        current_url = self._page.url

        # 只在当前页面不是 DeepSeek 页面时才导航（避免重复刷新）
        if self.deepseek_url not in current_url:
            print(f"{_ts()} 正在导航至 {self.deepseek_url} ...")
            await self._page.goto(self.deepseek_url, wait_until="domcontentloaded")
        else:
            # 已在目标域名下，静默检测
            pass

        current_url = self._page.url
        if "sign_in" in current_url or "/login" in current_url:
            return False

        # 检查聊天输入框（已登录标志）
        chat_input = await self._page.query_selector(
            'textarea[placeholder*="DeepSeek"], '
            '#chat-input, '
            'textarea[placeholder*="发送消息"], '
            'div[contenteditable="true"]'
        )
        if chat_input:
            return True

        # 检查是否有"登录"按钮
        login_btn = await self._page.query_selector(
            'button:has-text("登录"), '
            'a:has-text("登录"), '
            'button:has-text("Sign in"), '
            'button:has-text("Log in")'
        )
        if login_btn:
            return False

        # 兜底：检查聊天列表等已登录特征元素
        chat_list = await self._page.query_selector(
            '[class*="chat-list"], '
            '[class*="conversation"], '
            '[class*="sidebar"]'
        )
        if chat_list:
            return True

        return False

    async def ensure_login(self) -> None:
        """
        完整登录流程：
        1. 尝试 load_session 恢复会话
        2. 若恢复成功且 check_login 通过，直接返回
        3. 否则打开登录页，等待用户手动登录，最多 180 秒
        4. 检测到登录成功后 save_session
        """
        session_loaded = await self.load_session()

        if session_loaded:
            logged_in = await self.check_login()
            if logged_in:
                print(f"{_ts()} 会话恢复成功，已登录")
                return
            else:
                print(f"{_ts()} 会话恢复后登录态已过期，需要重新登录")

        # 访问登录页
        print(f"{_ts()} 正在打开 DeepSeek 登录页，请在浏览器中手动登录...")
        await self._page.goto(self.deepseek_url, wait_until="domcontentloaded")

        # 等待用户手动登录
        max_wait = 180
        check_interval = 2
        elapsed = 0
        print(f"{_ts()} 请在 {max_wait} 秒内完成登录（扫码或手机号）...")

        while elapsed < max_wait:
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            logged_in = await self.check_login()
            if logged_in:
                print(f"{_ts()} 登录成功！已耗时 {elapsed} 秒")
                await self.save_session()
                return
            if elapsed % 10 == 0:
                remaining = max_wait - elapsed
                print(f"{_ts()} 等待登录中... 剩余 {remaining} 秒")

        raise TimeoutError(f"登录超时：在 {max_wait} 秒内未完成登录")

    async def close(self) -> None:
        """关闭浏览器并释放资源。"""
        print(f"{_ts()} 正在关闭浏览器...")
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        print(f"{_ts()} 浏览器已关闭")
