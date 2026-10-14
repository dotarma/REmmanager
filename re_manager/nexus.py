"""Nexus v1 API, registered-app SSO, NXM parsing and streamed downloads."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

from . import __version__
from .safety import ModError, relative_name

API = "https://api.nexusmods.com/v1"
KEY_PAGE = "https://www.nexusmods.com/users/myaccount?tab=api+access"
MAX_DOWNLOAD = 16 * 1024**3


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ModError("API chuyển hướng ngoài dự kiến; đã dừng để bảo vệ API key.")


class HTTPSRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != "https":
            raise ModError("Từ chối chuyển hướng tải xuống qua HTTP không mã hóa.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def domain(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,80}", value):
        raise ModError("Domain game Nexus không hợp lệ.")
    return value


def positive(value) -> int:
    try:
        result = int(value)
    except (ValueError, TypeError) as exc:
        raise ModError("Mod ID và File ID phải là số nguyên dương.") from exc
    if result <= 0:
        raise ModError("ID phải lớn hơn 0.")
    return result


@dataclass(frozen=True)
class NxmLink:
    game: str
    mod_id: int
    file_id: int
    key: str | None = None
    expires: int | None = None
    user_id: int | None = None


def parse_nxm(value: str) -> NxmLink:
    if len(value) > 8192:
        raise ModError("Liên kết NXM quá dài.")
    parsed = urlparse(value.strip())
    match = re.fullmatch(r"/mods/(\d+)/files/(\d+)/?", parsed.path)
    if parsed.scheme != "nxm" or not match or parsed.username or parsed.password or parsed.port:
        raise ModError("Liên kết cần có dạng nxm://game/mods/123/files/456?key=…&expires=…")
    query = parse_qs(parsed.query, max_num_fields=12)
    key = query.get("key", [None])[0]
    expires = positive(query["expires"][0]) if "expires" in query else None
    user_id = positive(query["user_id"][0]) if "user_id" in query else None
    if bool(key) != bool(expires):
        raise ModError("Liên kết NXM phải có cả key và expires, hoặc không có cả hai.")
    if expires and expires <= time.time():
        raise ModError("Liên kết NXM đã hết hạn. Tạo lại từ Download with Manager.")
    return NxmLink(domain(parsed.hostname or ""), positive(match[1]), positive(match[2]), key, expires, user_id)


def parse_mod_input(value: str, expected_domain: str) -> int:
    if value.strip().isdigit():
        return positive(value.strip())
    parsed = urlparse(value.strip())
    match = re.fullmatch(r"/([^/]+)/mods/(\d+)/?", parsed.path)
    if parsed.scheme != "https" or parsed.hostname not in ("www.nexusmods.com", "nexusmods.com") or not match:
        raise ModError("Nhập Mod ID hoặc URL https://www.nexusmods.com/<game>/mods/<id>.")
    if match[1] != expected_domain:
        raise ModError("URL mod thuộc game khác với game đang chọn.")
    return positive(match[2])


class NexusClient:
    def __init__(self, key: str = ""):
        self.key = key.strip()
        self.account: dict | None = None
        self.limits: dict = {}
        self.opener = build_opener(NoRedirect())

    def request(self, endpoint: str, query: dict | None = None):
        if not self.key or any(c in self.key for c in "\r\n"):
            raise ModError("Cần đăng nhập bằng Nexus API key hợp lệ.")
        url = API + endpoint + ("?" + urlencode(query) if query else "")
        request = Request(url, headers={
            "apikey": self.key, "Accept": "application/json",
            "Application-Name": "REmmanager", "Application-Version": __version__,
            "User-Agent": f"REmmanager/{__version__}",
        })
        try:
            with self.opener.open(request, timeout=30) as response:
                for period in ("hourly", "daily"):
                    self.limits[period] = response.headers.get(f"x-rl-{period}-remaining", "?")
                raw = response.read(16 * 1024**2 + 1)
                if len(raw) > 16 * 1024**2:
                    raise ModError("Phản hồi API vượt giới hạn dung lượng.")
                return json.loads(raw)
        except HTTPError as exc:
            exc.close()
            messages = {
                401: "API key không hợp lệ hoặc đã bị thu hồi. Đăng nhập lại.",
                403: "Nexus từ chối truy cập. Tài khoản miễn phí cần liên kết NXM từ Download with Manager; Premium có thể tải trực tiếp.",
                404: "Không tìm thấy game/mod/file trên Nexus Mods.",
                429: "Đã chạm giới hạn API Nexus. Đợi rồi thử lại.",
            }
            raise ModError(messages.get(exc.code, f"Nexus API trả về lỗi HTTP {exc.code}.")) from None
        except (URLError, TimeoutError, OSError):
            raise ModError("Không kết nối được Nexus Mods. Kiểm tra mạng và thử lại.") from None
        except (ValueError, UnicodeError):
            raise ModError("Nexus trả về dữ liệu không hợp lệ.") from None

    def login(self) -> dict:
        result = self.request("/users/validate.json")
        if not isinstance(result, dict) or not result.get("user_id"):
            raise ModError("Phản hồi xác thực Nexus không hợp lệ.")
        self.account = {k: result.get(k) for k in ("user_id", "name", "is_premium", "is_supporter")}
        return self.account

    def list_mods(self, game: str, category: str = "trending") -> list[dict]:
        if category not in ("trending", "latest_added", "latest_updated"):
            raise ModError("Bộ lọc Nexus không hợp lệ.")
        return self.request(f"/games/{domain(game)}/mods/{category}.json")

    def mod_info(self, game: str, mod_id: int) -> dict:
        return self.request(f"/games/{domain(game)}/mods/{positive(mod_id)}.json")

    def files(self, game: str, mod_id: int) -> list[dict]:
        return self.request(f"/games/{domain(game)}/mods/{positive(mod_id)}/files.json").get("files", [])

    def file_info(self, game: str, mod_id: int, file_id: int) -> dict:
        return self.request(f"/games/{domain(game)}/mods/{positive(mod_id)}/files/{positive(file_id)}.json")

    def download_links(self, link: NxmLink) -> list[dict]:
        if not self.account:
            raise ModError("Đăng nhập Nexus trước khi tải mod.")
        if link.user_id and link.user_id != int(self.account["user_id"]):
            raise ModError("Liên kết tải xuống thuộc tài khoản Nexus khác.")
        if link.expires and link.expires <= time.time():
            raise ModError("Liên kết tải xuống đã hết hạn.")
        if not self.account.get("is_premium") and not (link.key and link.expires):
            raise ModError("Tài khoản miễn phí: dùng Download with Manager trên Nexus rồi mở/dán liên kết nxm://, hoặc tải bằng trình duyệt và thêm mod thủ công.")
        query = {"key": link.key, "expires": link.expires} if link.key else None
        result = self.request(f"/games/{domain(link.game)}/mods/{positive(link.mod_id)}/files/{positive(link.file_id)}/download_link.json", query)
        if not isinstance(result, list) or not result or not result[0].get("URI"):
            raise ModError("Nexus chưa cung cấp máy chủ tải xuống.")
        return result


def download(url: str, directory: Path, filename: str, cancel: threading.Event,
             progress=lambda current, total: None) -> Path:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ModError("Nexus cung cấp URL tải xuống không hợp lệ.")
    # No API key or auth header is ever sent to a download CDN.
    filename = relative_name(filename)
    if "/" in filename or Path(filename).suffix.lower() not in (".zip", ".7z", ".rar", ".lua", ".dll", ".pak"):
        raise ModError("Định dạng file Nexus chưa được hỗ trợ.")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (uuid.uuid4().hex[:10] + "-" + filename)
    fd, temp = tempfile.mkstemp(suffix=".part", dir=directory)
    try:
        with os.fdopen(fd, "wb") as output:
            request = Request(url, headers={"User-Agent": f"REmmanager/{__version__}"})
            with build_opener(HTTPSRedirect()).open(request, timeout=30) as response:
                if urlparse(response.geturl()).scheme != "https":
                    raise ModError("Tải xuống cần HTTPS.")
                try:
                    total = int(response.headers.get("Content-Length", "0"))
                except ValueError:
                    total = 0
                if total > MAX_DOWNLOAD:
                    raise ModError("File vượt giới hạn tải xuống 16 GiB.")
                current = 0
                while True:
                    if cancel.is_set():
                        raise ModError("Đã hủy tải xuống.")
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    current += len(chunk)
                    if current > MAX_DOWNLOAD:
                        raise ModError("File vượt giới hạn tải xuống 16 GiB.")
                    output.write(chunk)
                    progress(current, total)
                if not current or (total and current != total):
                    raise ModError("Tải xuống chưa hoàn tất. Thử lại.")
                if cancel.is_set():
                    raise ModError("Đã hủy tải xuống.")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, target)
        return target
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        if isinstance(exc, HTTPError):
            exc.close()
        raise ModError("Tải xuống thất bại. Kiểm tra mạng hoặc tạo lại liên kết Nexus.") from None
    finally:
        Path(temp).unlink(missing_ok=True)


def browser_sso(slug: str, open_browser, cancel: threading.Event) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", slug):
        raise ModError("SSO cần application slug được Nexus cấp cho ứng dụng này.")
    try:
        import websocket
    except ImportError as exc:
        raise ModError("Cài phần mở rộng sso để dùng đăng nhập trình duyệt.") from exc
    connection = None
    try:
        request_id = str(uuid.uuid4())
        connection = websocket.create_connection("wss://sso.nexusmods.com", timeout=15)
        connection.send(json.dumps({"id": request_id, "token": None, "protocol": 2}))
        connection.settimeout(1)
        opened = False
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and not cancel.is_set():
            try:
                message = json.loads(connection.recv())
            except websocket.WebSocketTimeoutException:
                continue
            if not message.get("success"):
                raise ModError("Nexus SSO từ chối phiên đăng nhập. Thử lại hoặc dùng API key.")
            data = message.get("data", {})
            if data.get("api_key"):
                return data["api_key"]
            if data.get("connection_token") and not opened:
                opened = True
                open_browser("https://www.nexusmods.com/sso?" + urlencode({"id": request_id, "application": slug}))
        raise ModError("SSO đã hủy hoặc hết thời gian chờ.")
    except (OSError, ValueError, websocket.WebSocketException):
        raise ModError("Không kết nối được Nexus SSO. Thử lại hoặc đăng nhập API key.") from None
    finally:
        if connection:
            connection.close()
