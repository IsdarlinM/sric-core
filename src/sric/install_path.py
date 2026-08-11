from __future__ import annotations

import ntpath
import os
import sys
from collections.abc import Sequence


def _normalized_windows_path(value: str) -> str:
    return ntpath.normcase(ntpath.normpath(value.strip().strip('"')))


def path_contains(existing: str, candidate: str) -> bool:
    wanted = _normalized_windows_path(candidate)
    return any(
        _normalized_windows_path(part) == wanted
        for part in existing.split(";")
        if part.strip()
    )


def append_path(existing: str, candidate: str) -> str:
    if path_contains(existing, candidate):
        return existing
    clean = existing.rstrip(";")
    return f"{clean};{candidate}" if clean else candidate


def ensure_windows_user_path(candidate: str) -> bool:
    r"""Append candidate to HKCU\Environment\Path without setx truncation.

    Returns True when the registry value changed. Existing REG_SZ/REG_EXPAND_SZ
    type is preserved and a WM_SETTINGCHANGE broadcast informs Explorer/new shells.
    """

    if os.name != "nt":
        raise RuntimeError("Windows user PATH management is only available on Windows")

    import ctypes
    import winreg

    access = winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, "Environment", 0, access) as key:
        try:
            existing, value_type = winreg.QueryValueEx(key, "Path")
            if value_type not in {winreg.REG_SZ, winreg.REG_EXPAND_SZ}:
                raise RuntimeError("HKCU\\Environment\\Path has an unsupported registry type")
        except FileNotFoundError:
            existing, value_type = "", winreg.REG_EXPAND_SZ

        updated = append_path(str(existing), candidate)
        changed = updated != str(existing)
        if changed:
            winreg.SetValueEx(key, "Path", 0, value_type, updated)

    if changed:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_ulong()
        user32 = getattr(ctypes, "windll").user32
        user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result),
        )
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or not args[0].strip():
        print("usage: python -m sric.install_path DIRECTORY", file=sys.stderr)
        return 2
    try:
        changed = ensure_windows_user_path(args[0])
    except (OSError, RuntimeError, AttributeError) as exc:
        print(f"Failed to update user PATH safely: {exc}", file=sys.stderr)
        return 3
    print("PATH updated" if changed else "PATH already configured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
