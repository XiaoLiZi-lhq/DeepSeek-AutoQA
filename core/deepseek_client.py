"""
P2: DeepSeek 页面交互
提供 DeepSeekClient 类，封装打开对话、输入问题、发送、等待完成检测等功能。
"""

import asyncio
from datetime import datetime

from playwright.async_api import Page


def _ts() -> str:
    """返回带时间戳的日志前缀。"""
    return datetime.now().strftime("[%H:%M:%S]")


# ------------------------------------------------------------------
# 元素定位选择器（多套备选）
# ------------------------------------------------------------------

# 输入框
INPUT_SELECTORS = [
    'textarea[placeholder*="DeepSeek"]',
    'textarea[placeholder*="deepseek"]',
    'textarea[placeholder*="发送消息"]',
    'textarea[placeholder*="输入"]',
    '#chat-input',
    'div[contenteditable="true"]',
    'textarea',
]

# 发送按钮
SEND_BUTTON_SELECTORS = [
    'button[aria-label*="发送"]',
    'button[aria-label*="send"]',
    'button:has(svg)',
    '[data-testid="send"]',
    'button[class*="send"]',
]

# 停止生成按钮（检测回答是否完成的关键标志）
STOP_BUTTON_SELECTORS = [
    'button:has-text("停止")',
    'button:has-text("停止生成")',
    'button[aria-label*="停止"]',
    'button[aria-label*="stop"]',
    '[data-testid="stop"]',
    'button[class*="stop"]',
    'button[class*="abort"]',
    'svg[class*="stop"]',
    'svg[class*="pause"]',
]

# 新建对话按钮
NEW_CHAT_SELECTORS = [
    'button:has-text("新建对话")',
    'button:has-text("新对话")',
    'button:has-text("New Chat")',
    'button[aria-label*="新建"]',
    'button[aria-label*="new"]',
    'a:has-text("新建对话")',
    '[data-testid="new-chat"]',
    'button[class*="new"]',
    'button[class*="chat"]',
]

# 回答区域
ANSWER_SELECTORS = [
    '[class*="assistant"]',
    '[class*="ds-markdown"]',
    '[class*="message"]',
    '[class*="response"]',
    '[class*="answer"]',
    'main [class*="content"]',
]


class DeepSeekClient:
    """封装与 chat.deepseek.com 页面交互的客户端。"""

    def __init__(self, browser_manager, config: dict):
        """
        初始化 DeepSeekClient。

        Args:
            browser_manager: BrowserManager 实例，需已完成 start 和 ensure_login。
            config: 从 config.yaml 解析的完整配置字典。
        """
        self.browser = browser_manager
        self.config = config
        self.url: str = config["deepseek"]["url"]
        self._page: Page = browser_manager._page

    # ------------------------------------------------------------------
    # 私有辅助方法
    # ------------------------------------------------------------------

    async def _try_selectors(self, selectors: list[str], action: str = "query"):
        """
        依次尝试多个 CSS 选择器，返回第一个匹配的元素。

        Args:
            selectors: CSS 选择器列表。
            action: 'query' 返回 ElementHandle，
                    'click' 点击匹配元素，
                    'visible' 返回可见元素。

        Returns:
            ElementHandle 或 None。
        """
        for sel in selectors:
            try:
                el = await self._page.query_selector(sel)
                if el is None:
                    continue
                if action in ("click", "visible"):
                    try:
                        visible = await el.is_visible()
                    except Exception:
                        visible = False
                    if not visible:
                        continue
                if action == "click":
                    await el.click(timeout=5000)
                    return el
                return el
            except Exception:
                continue
        return None

    async def _is_element_present(self, selectors: list[str]) -> bool:
        """检查任一选择器匹配的元素是否存在于 DOM 中。"""
        for sel in selectors:
            try:
                el = await self._page.query_selector(sel)
                if el is not None:
                    return True
            except Exception:
                continue
        return False

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    async def open_new_chat(self) -> bool:
        """
        打开一个新的对话。

        先导航至 chat.deepseek.com（默认就是新对话页面），
        如果页面上有"新建对话"按钮则点击。

        Returns:
            True 表示成功打开新对话页面。
        """
        print(f"{_ts()} 正在打开新对话...")

        # 直接导航到首页，DeepSeek 首页默认即为新对话
        await self._page.goto(self.url, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # 等待页面稳定
        try:
            await self._page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        # 尝试点击"新建对话"按钮
        clicked = await self._try_selectors(NEW_CHAT_SELECTORS, action="click")
        if clicked:
            print(f"{_ts()} 已点击新建对话按钮")
            await asyncio.sleep(1)
        else:
            print(f"{_ts()} 未找到新建对话按钮，当前页面即为新对话页")

        print(f"{_ts()} 新对话已就绪")
        return True

    async def send_question(self, question: str) -> bool:
        """
        在输入框中填入问题文本并发送。

        Args:
            question: 要发送的问题文本。

        Returns:
            True 表示问题发送成功，False 表示失败。
        """
        preview = question[:50] + ('...' if len(question) > 50 else '')
        print(f"{_ts()} 正在输入问题: {preview}")

        # 1. 定位输入框
        input_box = await self._try_selectors(INPUT_SELECTORS, action="visible")
        if input_box is None:
            print(f"{_ts()} [错误] 未找到输入框")
            return False

        # 2. 清空并填入文本
        try:
            await input_box.click(timeout=5000)
            await asyncio.sleep(0.3)
            await self._page.keyboard.press("Meta+A")
            await asyncio.sleep(0.1)
            await input_box.fill(question)
        except Exception as e:
            print(f"{_ts()} fill 异常: {e}，尝试逐字键入...")
            await input_box.click(timeout=5000)
            await self._page.keyboard.press("Meta+A")
            await self._page.keyboard.press("Backspace")
            await self._page.keyboard.type(question, delay=10)

        await asyncio.sleep(0.5)

        # 3. 尝试点击发送按钮
        send_btn = await self._try_selectors(SEND_BUTTON_SELECTORS, action="click")
        if send_btn:
            print(f"{_ts()} 已点击发送按钮")
        else:
            print(f"{_ts()} 未找到发送按钮，使用 Enter 键发送")
            try:
                await self._page.keyboard.press("Enter")
            except Exception:
                pass

        await asyncio.sleep(1)
        print(f"{_ts()} 问题已发送")
        return True

    async def wait_for_answer(self, timeout: int = None) -> dict:
        """
        等待 AI 回答生成完毕（双保险策略）。

        主判定：每 500ms 检测「停止生成」按钮是否消失。
        超时兜底：timeout 秒后强制返回，提取已有内容。

        Args:
            timeout: 超时秒数，默认使用 config 中的 answer_complete (=120)。

        Returns:
            dict: {
                "completed": bool,
                "timeout": bool,
                "answer_text": str,
            }
        """
        if timeout is None:
            timeout = self.config.get("timeout", {}).get("answer_complete", 120)

        print(f"{_ts()} 等待回答生成（超时 {timeout}s）...")

        check_interval = 0.5
        elapsed = 0.0
        completed = False

        while elapsed < timeout:
            stop_present = await self._is_element_present(STOP_BUTTON_SELECTORS)

            if not stop_present and elapsed > 2:
                # 停止按钮已消失且至少等待了 2 秒
                await asyncio.sleep(1.5)
                completed = True
                print(f"{_ts()} 回答生成完毕（{elapsed:.1f}s）")
                break

            await asyncio.sleep(check_interval)
            elapsed += check_interval

            if int(elapsed) % 10 == 0 and elapsed > 0:
                print(f"{_ts()} 等待中... 已等待 {int(elapsed)}s")

        # 无论是否完成都提取当前已有内容
        answer_text = await self.get_answer_text()

        if not completed:
            print(f"{_ts()} 超时（{timeout}s），强制提取已有内容")
            return {"completed": False, "timeout": True, "answer_text": answer_text}

        return {"completed": True, "timeout": False, "answer_text": answer_text}

    async def get_answer_text(self) -> str:
        """
        提取当前页面上最新回答的纯文本内容。

        Returns:
            回答的纯文本字符串。提取失败返回空字符串。
        """
        try:
            # 策略1：找所有 assistant / ds-markdown 区域，取最后一个
            answer_blocks = await self._page.query_selector_all(
                '[class*="assistant"], [class*="ds-markdown"], '
                '[class*="message"]'
            )
            if answer_blocks:
                text = await answer_blocks[-1].inner_text()
                return text.strip() if text else ""

            # 策略2：通用选择器
            for sel in ANSWER_SELECTORS:
                try:
                    elements = await self._page.query_selector_all(sel)
                    if elements:
                        text = await elements[-1].inner_text()
                        if text and len(text) > 10:
                            return text.strip()
                except Exception:
                    continue

            # 策略3：body 兜底
            body_text = await self._page.inner_text("body")
            if body_text:
                lines = body_text.strip().split("\n")
                meaningful = [l for l in lines if len(l) > 10]
                return "\n".join(meaningful[-50:]) if meaningful else ""

        except Exception as e:
            print(f"{_ts()} 提取回答文本异常: {e}")

        return ""
