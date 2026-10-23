"""Post input directly to Hearthstone without moving the desktop pointer."""

import ctypes

import Quartz

_CORE_GRAPHICS = ctypes.CDLL(
    "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
)
_CORE_GRAPHICS.CGEventCreateMouseEvent.restype = ctypes.c_void_p
_CORE_GRAPHICS.CGEventCreateMouseEvent.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_double,
    ctypes.c_double,
    ctypes.c_uint32,
]
_CORE_GRAPHICS.CGEventPostToPid.restype = None
_CORE_GRAPHICS.CGEventPostToPid.argtypes = [ctypes.c_int32, ctypes.c_void_p]
_CORE_GRAPHICS.CFRelease.argtypes = [ctypes.c_void_p]


def _post(pid, event_type, x, y):
    event = _CORE_GRAPHICS.CGEventCreateMouseEvent(None, event_type, x, y, 0)
    if not event:
        raise RuntimeError("CGEventCreateMouseEvent failed")
    try:
        _CORE_GRAPHICS.CGEventPostToPid(pid, event)
    finally:
        _CORE_GRAPHICS.CFRelease(event)


def move(pid, x, y):
    _post(pid, Quartz.kCGEventMouseMoved, x, y)


def click(pid, x, y, mouse_button="left"):
    down, up = (
        (Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp)
        if mouse_button == "right"
        else (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp)
    )
    _post(pid, Quartz.kCGEventMouseMoved, x, y)
    _post(pid, down, x, y)
    _post(pid, up, x, y)


def drag(pid, x1, y1, x2, y2):
    _post(pid, Quartz.kCGEventMouseMoved, x1, y1)
    _post(pid, Quartz.kCGEventLeftMouseDown, x1, y1)
    _post(pid, Quartz.kCGEventLeftMouseDragged, x2, y2)
    _post(pid, Quartz.kCGEventLeftMouseUp, x2, y2)
