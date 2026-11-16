"""Borderless popups that map on Windows as well as on X11.

Creating a ``Toplevel`` and then calling ``overrideredirect(True)`` plus
``transient()`` leaves the window unmapped on Windows 11: it exists, but
nothing is drawn. The window has to be withdrawn first, given an explicit
size and position, then shown. ``transient()`` is intentionally not used.

Positions use screen pixels (``ClientToScreen`` on Windows) so 125 % and
150 % scaling do not place the menu off the button.
"""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable

# Virtual-screen metrics. Physical pixels when the process is DPI aware.
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79

_OPEN: list[BorderlessPopup] = []
_listener_root: tk.Misc | None = None


def popup_position(
    anchor_x: int,
    anchor_y: int,
    anchor_w: int,
    anchor_h: int,
    popup_w: int,
    popup_h: int,
    screen: tuple[int, int, int, int],
    gap: int = 4,
) -> tuple[int, int]:
    """Place a popup under an anchor, right edges aligned, kept on screen.

    ``screen`` is ``(origin_x, origin_y, width, height)`` in the same pixels
    as the anchor. If the popup would leave the bottom edge it flips above
    the anchor.
    """
    origin_x, origin_y, screen_w, screen_h = screen
    x = anchor_x + anchor_w - popup_w
    y = anchor_y + anchor_h + gap
    right = origin_x + screen_w
    bottom = origin_y + screen_h
    if x < origin_x:
        x = origin_x
    if screen_w > popup_w and x + popup_w > right:
        x = right - popup_w
    if screen_h > popup_h and y + popup_h > bottom:
        above = anchor_y - popup_h - gap
        y = above if above >= origin_y else max(origin_y, bottom - popup_h)
    return int(x), int(y)


def widget_screen_rect(widget: tk.Widget) -> tuple[int, int, int, int]:
    """Top-left, width and height of ``widget`` in screen pixels."""
    widget.update_idletasks()
    if sys.platform.startswith("win"):
        rect = _windows_client_rect(widget)
        if rect is not None:
            return rect
    return (
        int(widget.winfo_rootx()),
        int(widget.winfo_rooty()),
        max(int(widget.winfo_width()), 1),
        max(int(widget.winfo_height()), 1),
    )


def screen_bounds(widget: tk.Widget) -> tuple[int, int, int, int]:
    """Virtual screen origin and size, in the same pixels as ``widget_screen_rect``."""
    if sys.platform.startswith("win"):
        bounds = _windows_virtual_screen()
        if bounds is not None:
            return bounds
    top = widget.winfo_toplevel()
    return 0, 0, int(top.winfo_screenwidth()), int(top.winfo_screenheight())


def widget_contains(widget: tk.Misc | None, container: tk.Misc | None) -> bool:
    current = widget
    while current is not None:
        if current is container:
            return True
        current = getattr(current, "master", None)
    return False


class BorderlessPopup:
    """One borderless menu. Several may exist; clicks and Esc close all of them."""

    def __init__(self, master: tk.Misc, *, on_anchor_press: Callable[[], None] | None = None):
        self.master = master.winfo_toplevel()
        self.window = tk.Toplevel(self.master)
        self.window.withdraw()
        self.window.overrideredirect(True)
        try:
            self.window.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.window.bind("<Escape>", lambda _event: self.close())
        self._anchor: tk.Widget | None = None
        self._armed = False
        self._on_anchor_press = on_anchor_press
        self._arm_job: str | None = None
        self._closed = False
        _OPEN.append(self)
        _ensure_listeners(self.master)

    def is_open(self) -> bool:
        if self._closed or self.window is None:
            return False
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def reveal_body(
        self,
        anchor: tk.Widget,
        *,
        body_width: int,
        body_height: int,
        align_right: tk.Widget | None = None,
        gap: int = 0,
        margin: int = 0,
    ) -> None:
        """Show the window so the menu body (inside ``margin``) sits under the anchor.

        ``align_right`` is the widget whose right edge the menu body should
        share — the drop zone, not the ⋯ button, which sits further right.
        """
        if not self.is_open():
            return
        self._anchor = anchor
        _ax, ay, _aw, ah = widget_screen_rect(anchor)
        if align_right is not None:
            rx, _ry, rw, _rh = widget_screen_rect(align_right)
            body_right = rx + rw
        else:
            ax, _ay, aw, _ah = widget_screen_rect(anchor)
            body_right = ax + aw
        body_x = body_right - body_width
        body_y = ay + ah + gap
        screen = screen_bounds(anchor)
        body_x, body_y = popup_position(
            body_x,
            body_y - gap - ah,
            body_width,
            ah,
            body_width,
            body_height,
            screen,
            gap=gap,
        )
        self._place_card(body_x, body_y, body_width, body_height, margin)

    def reveal_card(self, x: int, y: int, body_width: int, body_height: int, margin: int = 0) -> None:
        """Put the card's top-left at ``(x, y)`` in screen pixels, kept on the anchor window."""
        if not self.is_open():
            return
        top = self.master.winfo_toplevel()
        left = int(top.winfo_rootx())
        top_y = int(top.winfo_rooty())
        right = left + int(top.winfo_width())
        bottom = top_y + int(top.winfo_height())
        x = max(left, min(int(x), right - body_width))
        y = max(top_y, min(int(y), bottom - body_height))
        self._place_card(x, y, body_width, body_height, margin)

    def _place_card(self, body_x: int, body_y: int, body_width: int, body_height: int, margin: int) -> None:
        self._map(body_x - margin, body_y - margin, body_width + margin * 2, body_height + margin * 2)
        self._armed = False
        if self._arm_job is not None:
            try:
                self.master.after_cancel(self._arm_job)
            except tk.TclError:
                pass
        self._arm_job = self.master.after(0, self._arm)

    def reveal_under(self, anchor: tk.Widget, *, min_width: int = 0, min_height: int = 0) -> None:
        """Show the window under ``anchor`` after its contents have been packed."""
        if not self.is_open():
            return
        self._anchor = anchor
        self.window.update_idletasks()
        width = max(int(self.window.winfo_reqwidth()), min_width, 1)
        height = max(int(self.window.winfo_reqheight()), min_height, 1)
        ax, ay, aw, ah = widget_screen_rect(anchor)
        x, y = popup_position(ax, ay, aw, ah, width, height, screen_bounds(anchor))
        self._map(x, y, width, height)
        self._armed = False
        if self._arm_job is not None:
            try:
                self.master.after_cancel(self._arm_job)
            except tk.TclError:
                pass
        # Arm on a later turn so the click that opened the menu cannot close it.
        self._arm_job = self.master.after(0, self._arm)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self in _OPEN:
            _OPEN.remove(self)
        if self._arm_job is not None:
            try:
                self.master.after_cancel(self._arm_job)
            except tk.TclError:
                pass
            self._arm_job = None
        window = self.window
        self.window = None
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

    def _arm(self) -> None:
        self._arm_job = None
        if self.is_open():
            self._armed = True

    def _map(self, x: int, y: int, width: int, height: int) -> None:
        geometry = f"{int(width)}x{int(height)}+{int(x)}+{int(y)}"
        window = self.window
        if window is None:
            return
        window.geometry(geometry)
        window.deiconify()
        window.lift()
        try:
            window.attributes("-topmost", True)
        except tk.TclError:
            pass
        # Windows ignores the first geometry on an overrideredirect window
        # until it has been mapped. Apply it again after the map.
        if sys.platform.startswith("win"):
            window.update()
        else:
            window.update_idletasks()
        if self.window is None:
            return
        window.geometry(geometry)
        window.lift()

    def _handle_click(self, event: tk.Event) -> None:
        if not self._armed or not self.is_open():
            return
        if widget_contains(event.widget, self.window):
            return
        on_anchor = self._anchor is not None and widget_contains(event.widget, self._anchor)
        self.close()
        if on_anchor and self._on_anchor_press is not None:
            self._on_anchor_press()

    @classmethod
    def close_all(cls) -> bool:
        """Close every open popup. Returns whether any were open."""
        open_popups = [popup for popup in list(_OPEN) if popup.is_open()]
        for popup in open_popups:
            popup.close()
        return bool(open_popups)


def _ensure_listeners(master: tk.Misc) -> None:
    global _listener_root
    if _listener_root is not None:
        try:
            if _listener_root.winfo_exists():
                return
        except tk.TclError:
            pass
    root = master.winfo_toplevel()
    # add="+" keeps CustomTkinter's own <Button-1> focus handler.
    root.bind_all("<Button-1>", _on_global_click, add="+")
    root.bind_all("<Escape>", _on_global_escape, add="+")
    _listener_root = root


def _on_global_click(event: tk.Event) -> None:
    for popup in list(_OPEN):
        popup._handle_click(event)


def _on_global_escape(_event: tk.Event) -> str | None:
    if BorderlessPopup.close_all():
        return "break"
    return None


def _windows_client_rect(widget: tk.Widget) -> tuple[int, int, int, int] | None:
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return None
    hwnd = int(widget.winfo_id() or 0)
    if hwnd == 0:
        return None
    user = ctypes.windll.user32
    point = wintypes.POINT(0, 0)
    if not user.ClientToScreen(hwnd, ctypes.byref(point)):
        parent = int(user.GetParent(hwnd) or 0)
        if parent == 0 or not user.ClientToScreen(parent, ctypes.byref(point)):
            return None
        hwnd = parent
    rect = wintypes.RECT()
    if not user.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    if width <= 0 or height <= 0:
        return None
    return int(point.x), int(point.y), width, height


def _windows_virtual_screen() -> tuple[int, int, int, int] | None:
    try:
        import ctypes
    except ImportError:
        return None
    user = ctypes.windll.user32
    width = int(user.GetSystemMetrics(_SM_CXVIRTUALSCREEN))
    height = int(user.GetSystemMetrics(_SM_CYVIRTUALSCREEN))
    if width <= 0 or height <= 0:
        return None
    return (
        int(user.GetSystemMetrics(_SM_XVIRTUALSCREEN)),
        int(user.GetSystemMetrics(_SM_YVIRTUALSCREEN)),
        width,
        height,
    )
