"""Read public Douyin pages through a dedicated Playwright browser profile."""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from .catalog import HANDLE, VIDEO_ID, StudyError, douyin_id, duration_seconds, post_url, public_metrics, published, read_json, utc_now, write_json

HOME = "https://www.douyin.com"
SESSION_COOKIES = {"sessionid", "sessionid_ss", "sid_guard"}
PROFILE = re.compile(r"/user/([a-zA-Z0-9_-]{8,180})/?")
HANDLE_LABEL = re.compile(r"抖音号[：:\s]*([a-zA-Z0-9_.-]{1,64})(?![a-zA-Z0-9_.-])")

# Capture only cards whose nearby DOM identifies a single author. Broad
# ancestor matches could pair one account's handle with another card's link.
SEARCH_CARDS = """() => Array.from(document.querySelectorAll('a[href*="/user/"]'))
  .flatMap(anchor => {
    const url = anchor.href;
    if (!anchor.getClientRects().length) return [];
    const cards = [];
    for (let node = anchor, i = 0; node && i < 6; i++, node = node.parentElement) {
      const links = Array.from(node.querySelectorAll('a[href*="/user/"]'), link => link.href);
      if (links.some(link => new URL(link).pathname !== new URL(url).pathname)) break;
      const text = node.innerText || '';
      if (text.length > 1400) break;
      if (text.includes('抖音号')) cards.push({url, text});
    }
    return cards;
  })"""

POST_CARDS = """() => Array.from(document.querySelectorAll('a[href*="/video/"]'))
  .filter(link => link.getClientRects().length && !link.closest('footer, nav, aside, [role=dialog], [class*=page-footer]'))
  .map(link => ({
    url: link.href,
    title: link.querySelector('img[alt]')?.getAttribute('alt') || link.title ||
      link.querySelector('[title]')?.getAttribute('title') || ''
  }))"""


def profile_url(value: str) -> str | None:
    parsed = urlparse(value)
    match = PROFILE.fullmatch(parsed.path)
    if parsed.scheme == "https" and parsed.hostname in {"www.douyin.com", "douyin.com"} and match:
        return f"{HOME}/user/{match[1]}"
    return None


def profile_candidates(cards: list[dict], handle: str) -> set[str]:
    candidates = set()
    for card in cards:
        labels = {match.casefold() for match in HANDLE_LABEL.findall(card["text"])}
        url = profile_url(card["url"])
        if url and labels == {handle.casefold()}:
            candidates.add(url)
    return candidates


@contextmanager
def browser(directory: Path, *, visible: bool = False):
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError as exc:
        raise StudyError("抖音网页采集需要 Playwright。请运行 uv sync --extra douyin") from exc
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(directory), headless=not visible, locale="zh-CN", timeout=25_000
            )
            try:
                yield context.pages[0] if context.pages else context.new_page()
            finally:
                if context.pages:
                    context.close()
    except Error as exc:
        details = str(exc)
        if "Executable doesn't exist" in details:
            raise StudyError("Chromium 未安装。请在当前 Skill 的运行环境执行 playwright install chromium") from exc
        lock_messages = ("ProcessSingleton", "SingletonLock", "Opening in existing browser session", "现有的浏览器会话中打开")
        if any(message in details for message in lock_messages):
            raise StudyError("抖音专用浏览器正在使用这个资料目录。等当前登录或采集完成后再试。") from exc
        raise StudyError("抖音网页未能打开或完成读取。检查网络，或检查专用浏览器是否还开着。") from exc


def is_signed_in(page) -> bool:
    return any(item["name"] in SESSION_COOKIES for item in page.context.cookies(HOME))


def open_login(directory: Path) -> None:
    with browser(directory, visible=True) as page:
        from playwright.sync_api import Error

        page.goto(HOME, wait_until="domcontentloaded", timeout=30_000)
        if not page.is_closed() and not is_signed_in(page):
            try:
                choice = page.get_by_text("登录", exact=True).first
                choice.click(timeout=7_000)
            except Error:
                pass
        print("请在项目专用 Chromium 中完成抖音登录。检测到登录后窗口会自动关闭。", flush=True)
        while not page.is_closed():
            if is_signed_in(page):
                print("已确认项目专用浏览器登录。", flush=True)
                return
            try:
                page.wait_for_timeout(500)
            except Error:
                break
        raise StudyError("专用窗口关闭前未检测到有效登录。")


def body_text(page) -> str:
    return page.locator("body").inner_text(timeout=5_000)


def require_public_page(text: str) -> None:
    if re.search(r"验证码中间页|请拖动滑块|请完成安全验证|访问过于频繁|请登录后查看|登录后才能查看", text):
        raise StudyError("抖音页面需要登录或验证。可开启专用浏览器完成登录，或提供作品清单。")


def find_profile(page, handle: str) -> str:
    page.goto(f"{HOME}/search/{quote(handle, safe='')}?type=user",
              wait_until="domcontentloaded", timeout=30_000)
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        matches = profile_candidates(page.evaluate(SEARCH_CARDS), handle)
        if len(matches) > 1:
            raise StudyError(f"抖音号 {handle} 匹配到多个主页。请提供准确主页链接。")
        if matches:
            return matches.pop()
        page.wait_for_timeout(450)
    require_public_page(page.title() + "\n" + body_text(page))
    raise StudyError(f"网页搜索未能确认抖音号 {handle}。请提供主页链接，或先配置专用浏览器登录。")


def listed_posts(payload: dict, author_id: str) -> dict:
    posts = {}
    for raw in payload.get("aweme_list") or []:
        if not isinstance(raw, dict) or (raw.get("author") or {}).get("sec_uid") != author_id:
            continue
        post_id = str(raw.get("aweme_id", ""))
        if not VIDEO_ID.fullmatch(post_id) or raw.get("images") or raw.get("aweme_type") in (68, 150):
            continue
        posts[post_id] = {
            "id": post_id, "url": post_url(post_id), "title": str(raw.get("desc") or ""),
            "published_at": published(raw.get("create_time")),
            "listed_duration": duration_seconds(None, (raw.get("video") or {}).get("duration")),
            **public_metrics({}, raw.get("statistics") or {}),
        }
    return posts


def collect_profile(target: str, directory: Path, cap: int, expected: str | None = None) -> dict:
    profile = profile_url(target)
    if expected and not profile:
        raise StudyError("--expect-handle 必须与主页链接一起使用")
    handle = (expected or "").strip().removeprefix("@") if profile else target.strip().removeprefix("@")
    handle = handle or None
    if handle and not HANDLE.fullmatch(handle):
        raise StudyError("请输入抖音号或 https://www.douyin.com/user/… 主页链接")
    known_path = directory / "verified-accounts.json"
    with browser(directory, visible=bool(directory.joinpath("Default").is_dir())) as page:
        known = read_json(known_path) if known_path.is_file() else {}
        if not profile and handle:
            profile = profile_url(known.get(handle.casefold()) or "") or find_profile(page, handle)
        author_id = profile.rsplit("/", 1)[-1]
        responses = []
        page.on("response", lambda response: responses.append(response)
                if urlparse(response.url).hostname == "www.douyin.com"
                and urlparse(response.url).path.rstrip("/") == "/aweme/v1/web/aweme/post"
                and response.ok else None)
        page.goto(profile, wait_until="domcontentloaded", timeout=30_000)
        # Wait for the profile itself or its access gate to become visible.
        for _ in range(20):
            text = body_text(page)
            require_public_page(page.title() + "\n" + text)
            if HANDLE_LABEL.search(text):
                break
            page.wait_for_timeout(400)
        labels = {label.casefold() for label in HANDLE_LABEL.findall(text)}
        if handle and handle.casefold() not in labels:
            raise StudyError(f"打开的主页未显示与 {handle} 一致的抖音号。")
        if profile_url(page.url) != profile:
            raise StudyError("抖音将主页请求重定向到了其他页面。")
        if handle:
            known[handle.casefold()] = profile
            write_json(known_path, known)
        posts = {}
        structured = {}
        idle = 0
        for _ in range(16):
            cards = page.evaluate(POST_CARDS)
            before = len(posts)
            for response in responses[:]:
                responses.remove(response)
                try:
                    payload = response.json()
                except (ValueError, RuntimeError):
                    continue
                if isinstance(payload, dict):
                    structured.update(listed_posts(payload, author_id))
            for post_id, record in structured.items():
                posts[post_id] = record
            for card in cards:
                url = urljoin(HOME, card["url"])
                post_id = douyin_id(url)
                if post_id and post_id not in posts:
                    posts[post_id] = {"id": post_id, "url": url, "title": card["title"]}
                    if len(posts) >= cap:
                        break
            if len(posts) >= cap:
                break
            idle = idle + 1 if before == len(posts) else 0
            if idle >= 4 and posts:
                break
            page.mouse.wheel(0, 1600)
            page.wait_for_timeout(600)
        if not posts:
            text = body_text(page)
            require_public_page(page.title() + "\n" + text)
            if "服务异常" in text:
                raise StudyError("主页加载作品失败。可先完成抖音登录后重试，或导入作品快照。")
            raise StudyError("主页没有读到可访问的视频作品。可补充作品链接或本地视频。")
        name = page.title().split("的抖音", 1)[0].strip()
        if structured:
            # The structured endpoint proved the author. Omit unrelated DOM links.
            posts = structured
    return {
        "origin": "douyin_browser",
        "account": {"handle": handle or (next(iter(labels)) if len(labels) == 1 else None),
                    "name": name, "profile_url": profile},
        "collected_at": utc_now(),
        "posts": list(posts.values())[:cap],
    }
