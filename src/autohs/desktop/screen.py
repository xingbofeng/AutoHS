"""Screen size. Tk is created only when a function here runs."""

_screen_size = None


def get_screen_resolution():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        return root.winfo_screenwidth(), root.winfo_screenheight()
    finally:
        root.destroy()


def screen_size():
    global _screen_size
    if _screen_size is None:
        _screen_size = get_screen_resolution()
    return _screen_size


if __name__ == "__main__":
    width, height = screen_size()
    print(f"Screen resolution: {width}x{height}")
