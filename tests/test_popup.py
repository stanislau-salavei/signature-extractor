"""Popup placement, the ⋯ menu, round step badges, and the drop-zone canvas."""

from __future__ import annotations

import os
import sys
import unittest

from signature_extractor.ui.popup import popup_position
from signature_extractor.ui.widgets.thin_scroll import wheel_steps
from signature_extractor.ui.theme import DARK, LIGHT
from signature_extractor.ui.widgets.drop_zone import canvas_colors


class PopupPositionTests(unittest.TestCase):
    def test_right_aligns_under_the_anchor(self) -> None:
        x, y = popup_position(400, 40, 36, 36, 228, 180, (0, 0, 1280, 800))
        self.assertEqual(x, 400 + 36 - 228)
        self.assertEqual(y, 40 + 36 + 4)

    def test_stays_on_a_150_percent_screen(self) -> None:
        # 36 px button at 150 % is 54 physical px, near the right of a 1920-wide screen.
        x, y = popup_position(1800, 30, 54, 54, 228, 190, (0, 0, 1920, 1080))
        self.assertEqual(x, 1800 + 54 - 228)
        self.assertEqual(y, 30 + 54 + 4)
        self.assertLessEqual(x + 228, 1920)
        self.assertLessEqual(y + 190, 1080)

    def test_clamps_when_the_anchor_is_at_the_left_edge(self) -> None:
        x, _y = popup_position(10, 40, 36, 36, 228, 180, (0, 0, 800, 600))
        self.assertEqual(x, 0)

    def test_flips_above_when_there_is_no_room_below(self) -> None:
        _x, y = popup_position(100, 500, 36, 36, 228, 180, (0, 0, 800, 600))
        self.assertEqual(y, 500 - 180 - 4)

    def test_windows_wheel_delta_is_a_notch_of_120(self) -> None:
        self.assertEqual(wheel_steps(120), -48)
        self.assertEqual(wheel_steps(-240), 96)
        self.assertEqual(wheel_steps(0, number=4), -48)
        self.assertEqual(wheel_steps(0, number=5), 48)

    def test_drop_canvas_uses_the_window_colour_outside_the_curve(self) -> None:
        self.assertEqual(canvas_colors(LIGHT), ("#F3F3F3", "#FBFBFB"))
        self.assertEqual(canvas_colors(DARK), ("#202020", "#2B2B2B"))


@unittest.skipUnless(
    sys.platform.startswith("win") or os.environ.get("DISPLAY"),
    "needs a display",
)
class WidgetChromeTests(unittest.TestCase):
    def setUp(self) -> None:
        import tkinter as tk

        self.tk = tk
        self.root = tk.Tk()
        self.root.geometry("900x600+30+30")
        self.root.update_idletasks()

    def tearDown(self) -> None:
        try:
            self.root.destroy()
        except self.tk.TclError:
            pass

    def test_stepper_padding_is_equal_for_long_and_short_labels(self) -> None:
        from signature_extractor.ui.widgets.stepper import STEPPER_PAD, Stepper

        for labels in (("Загрузка", "Обработка", "Экспорт"), ("Import", "Processing", "Export")):
            with self.subTest(labels=labels):
                host = self.tk.Frame(self.root, bg="#F3F3F3")
                host.pack()
                stepper = Stepper(host, lambda _step: None)
                stepper.pack()
                stepper.set_labels(list(labels))
                stepper.set_state(1, {1: True, 2: False, 3: False})
                self.root.update()
                left, top, right, bottom = _stepper_gaps(stepper)
                self.assertAlmostEqual(left, top, delta=1)
                self.assertAlmostEqual(top, bottom, delta=1)
                self.assertAlmostEqual(left, right, delta=1)
                self.assertAlmostEqual(left, STEPPER_PAD, delta=1)
                host.destroy()
                self.root.update()

    def test_step_badges_stay_circles_with_a_wide_font(self) -> None:
        import customtkinter as ctk

        from signature_extractor.ui.widgets.stepper import BADGE_SIZE, CircleBadge

        # Wider than the badge on purpose: Segoe UI at 125–150 % does this.
        badge = CircleBadge(self.root)
        badge.number.configure(font=ctk.CTkFont(size=18, weight="bold"))
        badge.set_number(1)
        badge.pack()
        self.root.update()
        self.assertEqual(badge.winfo_width(), badge.winfo_height())
        self.assertEqual(badge.winfo_width(), BADGE_SIZE)
        badge.set_active(True)
        self.root.update()
        self.assertEqual(badge.winfo_width(), badge.winfo_height())

    def test_drop_zone_canvas_background_matches_the_window(self) -> None:
        import customtkinter as ctk

        from signature_extractor.ui.widgets.drop_zone import DropZone

        ctk.set_appearance_mode("light")
        zone = DropZone(self.root)
        zone.pack(fill="both", expand=True)
        self.root.update()
        self.assertEqual(zone._canvas.cget("bg").lower(), LIGHT.bg.lower())
        fills = {zone._canvas.itemcget(item, "fill").lower() for item in zone._canvas.find_all()}
        self.assertIn(LIGHT.drop.lower(), fills)
        ctk.set_appearance_mode("dark")
        zone._drawn = None
        zone._redraw()
        self.root.update()
        self.assertEqual(zone._canvas.cget("bg").lower(), DARK.bg.lower())

    def test_overflow_menu_opens_under_the_button_and_closes(self) -> None:
        from signature_extractor.ui.widgets.menu import OverflowMenu

        anchor = self.tk.Frame(self.root, width=36, height=36, bg="#005FB8")
        anchor.place(x=700, y=24)
        anchor.pack_propagate(False)
        self.root.update()
        clicked: list[str] = []
        menu = OverflowMenu(self.root)
        menu.set_items(
            [
                ("Open", None, lambda: clicked.append("open")),
                ("Folder", None, lambda: None),
                ("Settings", None, lambda: None),
            ]
        )
        menu.show(anchor)
        self.root.update()
        self.assertTrue(menu.is_open())
        popup = menu._popup.window
        self.assertIsNotNone(popup)
        assert popup is not None
        self.assertTrue(popup.winfo_viewable())
        self.assertGreater(popup.winfo_width(), 100)
        self.assertGreater(popup.winfo_height(), 40)
        button_bottom = anchor.winfo_rooty() + anchor.winfo_height()
        self.assertLess(popup.winfo_rooty(), button_bottom + 24)
        self.assertGreater(popup.winfo_rooty() + popup.winfo_height(), button_bottom)

        popup.event_generate("<Escape>")
        self.root.update()
        self.assertFalse(menu.is_open())

        menu.show(anchor)
        self.root.update()
        self.assertTrue(menu.is_open())
        # The opening update arms the outside-click listener. A click elsewhere closes it.
        self.root.event_generate("<Button-1>", x=8, y=200)
        self.root.update()
        self.assertFalse(menu.is_open())

        menu.show(anchor)
        self.root.update()
        label = _find_label(menu._popup.window, "Open")
        label.event_generate("<Button-1>")
        self.root.update()
        self.assertEqual(clicked, ["open"])
        self.assertFalse(menu.is_open())

        menu.show(anchor)
        self.root.update()
        event = self.tk.Event()
        event.widget = anchor
        menu._popup._handle_click(event)
        self.assertFalse(menu.is_open())
        menu.show(anchor)
        self.assertFalse(menu.is_open())
        menu.show(anchor)
        self.root.update()
        self.assertTrue(menu.is_open())
        menu.hide()


def _stepper_gaps(stepper):
    stepper.update_idletasks()
    origin_x = stepper.winfo_rootx()
    origin_y = stepper.winfo_rooty()
    width = stepper.winfo_width()
    height = stepper.winfo_height()
    chips = [step["chip"] for step in stepper._steps]
    first = chips[0]
    last = chips[-1]
    left = first.winfo_rootx() - origin_x
    right = origin_x + width - (last.winfo_rootx() + last.winfo_width())
    top = min(chip.winfo_rooty() for chip in chips) - origin_y
    bottom = origin_y + height - max(chip.winfo_rooty() + chip.winfo_height() for chip in chips)
    return left, top, right, bottom


def _find_label(widget, text: str):
    import tkinter as tk

    if isinstance(widget, tk.Label):
        try:
            if widget.cget("text") == text:
                return widget
        except tk.TclError:
            pass
    for child in widget.winfo_children():
        found = _find_label(child, text)
        if found is not None:
            return found
    raise AssertionError(f"label {text!r} not found")


if __name__ == "__main__":
    unittest.main()
