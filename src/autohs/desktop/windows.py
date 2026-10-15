"""Windows hwnd helpers. pywin32 loads inside each function."""


def find_window(title):
    import win32gui

    return win32gui.FindWindow(None, title)


def bring_to_front(hwnd):
    import win32com.client
    import win32con
    import win32gui

    try:
        win32gui.BringWindowToTop(hwnd)
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys("%")
        win32gui.SetForegroundWindow(hwnd)
    finally:
        win32gui.ShowWindow(hwnd, win32con.SW_NORMAL)


def window_rect(hwnd):
    import win32gui

    return win32gui.GetWindowRect(hwnd)


def desktop_snapshot(width, height):
    import numpy as np
    import win32con
    import win32gui
    import win32ui

    hwnd = win32gui.GetDesktopWindow()
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    save_bitmap = win32ui.CreateBitmap()
    save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(save_bitmap)
    save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)
    signed_ints = save_bitmap.GetBitmapBits(True)
    win32gui.DeleteObject(save_bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    image = np.frombuffer(signed_ints, dtype="uint8")
    image.shape = (height, width, 4)
    return image.copy()


def terminate_process(hwnd):
    import win32api
    import win32con
    import win32process

    _, process_id = win32process.GetWindowThreadProcessId(hwnd)
    handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE, 0, process_id)
    win32api.TerminateProcess(handle, 0)
    win32api.CloseHandle(handle)
