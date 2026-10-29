"""Private local configuration files and cross-process serialization (no memory data)."""

import contextlib
import ctypes
import os
import re
import stat
import subprocess
import tempfile
import threading
import time
from functools import lru_cache
from pathlib import Path

from contextbridge.inspection.provider_settings import SettingsError

_PROCESS_LOCK = threading.RLock()


@lru_cache(maxsize=1)
def _sid():
    directory = ctypes.create_unicode_buffer(32768)
    ctypes.windll.kernel32.GetWindowsDirectoryW(directory, len(directory))
    result = subprocess.run(
        [str(Path(directory.value) / "System32" / "whoami.exe"), "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    match = re.search(rb"S-\d-\d+(?:-\d+)+", result.stdout)
    if match is None:
        raise SettingsError("unavailable")
    return match[0].decode("ascii")


def _windows_security(path, *, protect=False):
    from ctypes import wintypes

    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    sid = _sid()
    if protect:
        descriptor = ctypes.c_void_p()
        convert = api.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
        ]
        if not convert(
            f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{sid})", 1, ctypes.byref(descriptor), None
        ):
            raise SettingsError("unavailable")
        try:
            apply = api.SetFileSecurityW
            apply.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
            if not apply(str(path), 4 | 0x80000000, descriptor):
                raise SettingsError("unavailable")
        finally:
            kernel.LocalFree(descriptor)
        return
    size = wintypes.DWORD()
    read = api.GetFileSecurityW
    read.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    read(str(path), 4, None, 0, ctypes.byref(size))
    buffer = ctypes.create_string_buffer(size.value)
    if not read(str(path), 4, buffer, size, ctypes.byref(size)):
        raise SettingsError("unavailable")
    value = wintypes.LPWSTR()
    convert = api.ConvertSecurityDescriptorToStringSecurityDescriptorW
    convert.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.c_void_p,
    ]
    if not convert(buffer, 1, 4, ctypes.byref(value), None):
        raise SettingsError("unavailable")
    try:
        sddl = value.value
        entries = re.findall(r"\(([^()]*)\)", sddl)
        if not sddl.startswith("D:P") or not entries:
            raise SettingsError("unavailable")
        for entry in entries:
            parts = entry.split(";")
            if len(parts) != 6 or parts[0] != "A" or parts[5] not in (sid, "SY", "S-1-5-18"):
                raise SettingsError("unavailable")
    finally:
        kernel.LocalFree(ctypes.cast(value, ctypes.c_void_p))


def checked_path(value):
    path = Path(value)
    if not path.is_absolute() or str(path).startswith("\\\\") or path.suffix != ".json":
        raise SettingsError("invalid")
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise SettingsError("invalid")
    return path


def check_private(path):
    info = path.stat()
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise SettingsError("unavailable")
    if os.name == "nt":
        _windows_security(path)
    elif info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise SettingsError("unavailable")


def prepare_directory(path):
    if not path.exists():
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name == "nt":
            _windows_security(path, protect=True)
    check_private(path)


def atomic_write(path, data):
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.pending-", dir=path.parent)
    temporary = Path(name)
    try:
        if os.name == "nt":
            _windows_security(temporary, protect=True)
        with os.fdopen(descriptor, "wb") as file:
            descriptor = None
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def configuration_lock(path, *, deadline=None):
    deadline = time.monotonic() + 10 if deadline is None else deadline
    acquired = _PROCESS_LOCK.acquire(timeout=max(0, deadline - time.monotonic()))
    if not acquired:
        raise SettingsError("timeout")
    file = None
    locked = False
    try:
        prepare_directory(path.parent)
        lock_path = path.with_suffix(".lock")
        if lock_path.is_symlink():
            raise SettingsError("unavailable")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        file = os.fdopen(descriptor, "r+b")
        if os.name == "nt":
            _windows_security(lock_path, protect=True)
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    file.seek(0)
                    msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise SettingsError("timeout") from None
                time.sleep(min(0.02, max(0, deadline - time.monotonic())))
        # A killed writer can leave a private temp file. Remove only this store's
        # abandoned writes under its lock, so replacement/removal leaves no copies.
        abandoned = list(path.parent.glob(f".{path.name}.pending-*"))
        if len(abandoned) > 100:
            raise SettingsError("unavailable")
        for temporary in abandoned:
            if temporary.is_symlink() or not temporary.is_file():
                raise SettingsError("unavailable")
            check_private(temporary)
            temporary.unlink()
        yield
    finally:
        if file is not None:
            if locked:
                if os.name == "nt":
                    import msvcrt

                    file.seek(0)
                    msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(file, fcntl.LOCK_UN)
            file.close()
        _PROCESS_LOCK.release()
