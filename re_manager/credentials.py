"""Windows DPAPI: API keys are encrypted for the current Windows user."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import tempfile

from .safety import ModError


def crypt(data: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise ModError("Lưu đăng nhập chỉ hỗ trợ Windows DPAPI; hệ điều hành khác dùng đăng nhập trong phiên.")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        function = crypt32.CryptUnprotectData
        second_type = ctypes.POINTER(wintypes.LPWSTR)
    else:
        function = crypt32.CryptProtectData
        second_type = wintypes.LPCWSTR
    function.argtypes = [ctypes.POINTER(Blob), second_type, ctypes.POINTER(Blob), ctypes.c_void_p,
                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ModError("Windows không mã hóa/giải mã được thông tin đăng nhập.")
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel32.LocalFree(ctypes.cast(result.data, ctypes.c_void_p))


class CredentialStore:
    def __init__(self, path: Path):
        self.path = path

    def save(self, key: str):
        encrypted = crypt(key.encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)

    def load(self) -> str:
        if not self.path.is_file():
            return ""
        return crypt(self.path.read_bytes(), decrypt=True).decode("utf-8")

    def clear(self):
        self.path.unlink(missing_ok=True)
