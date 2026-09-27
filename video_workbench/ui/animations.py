from __future__ import annotations

import ctypes
import os

SPI_GETCLIENTAREAANIMATION = 0x1042


def animations_enabled_for_setting(setting: int) -> bool:
    return bool(setting)


def system_animations_enabled() -> bool:
    """Read the Windows client-area animation preference."""
    if os.name != "nt":
        return True

    enabled = ctypes.c_int()
    try:
        success = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETCLIENTAREAANIMATION,
            0,
            ctypes.byref(enabled),
            0,
        )
    except (AttributeError, OSError):
        return True

    if not success:
        return True
    return animations_enabled_for_setting(enabled.value)
