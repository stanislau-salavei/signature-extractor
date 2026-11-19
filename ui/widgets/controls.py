"""Shared Win11 controls (stage 1): buttons, links, toggle, radio, checkbox, ComboBox,
TextBox with «×» and «✓», slider, segmented control.  All are canvases drawn with PIL
state images, re-rendered on theme / scale change."""
from __future__ import annotations

import logging
import math
import tkinter as tk
from typing import Callable, List, Optional, Sequence

from ui import gfx
from ui.theme import F, S, Scale, Theme, elide, text_width
from ui.widgets.base import Box, Control

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- buttons
class Button(Control):
    """Win11 button. kind: primary | secondary | ghost.  size: 'md' (32, 13.5 px) | 'lg' (36, 14 px)."""

    def __init__(self, master, text: str = "", kind: str = "secondary", icon: Optional[str] = None,
                 icon_right: bool = False, size: str = "md", bg: str = "bg", command=None, tooltip=None,
                 pad: Optional[float] = None, icon_size: Optional[float] = None):
        super().__init__(master, bg=bg, command=command, tooltip=tooltip)
        self.label, self.kind, self.icon_name, self.icon_right = text, kind, icon, icon_right
        self.size = size
        self.font_px = 14 if size == "lg" else 13.5
        self.height = 36 if size == "lg" else 32
        self.pad = pad if pad is not None else (20 if size == "lg" else 14)
        self.icon_px = icon_size or (17 if size == "lg" else 16)
        self.text_color: Optional[str] = None   # e.g. accent text while the eyedropper is active (08)
        self.weight = "normal"                  # InfoBar action «Показать» is 13 px / 600 (38–41)

    def set_text(self, text: str) -> None:
        if text != self.label:
            self.label = text
            self.redraw()

    def natural_width(self) -> float:
        w = text_width(self.label, self.font_px, self.weight) if self.label else 0
        if self.icon_name:
            w += self.icon_px + (8 if self.label else 0)
        return w + 2 * self.pad + 2

    def _colors(self):
        k = self.kind
        if k == "primary":
            if self.disabled:
                return "accent_disabled", None, None, "on_accent"
            fill = "accent_press" if self.pressed else ("accent_hover" if self.hover else "accent")
            return fill, "accent_stroke_top", "accent_stroke_bottom", "on_accent"
        if k == "danger":       # remark 37: red destructive button (Settings «Сбросить», its confirmation)
            if self.disabled:
                return "accent_disabled", None, None, "on_accent"
            fill = "danger_press" if self.pressed else ("danger_hover" if self.hover else "danger")
            return fill, "danger_stroke_top", "danger_stroke_bottom", "on_danger"
        if k == "ghost":
            fill = ("ctl_press" if self.pressed else "ctl_hover") if (self.hover and not self.disabled) else None
            return fill, None, None, "disabled" if self.disabled else "text"
        if self.disabled:
            return "ctl_disabled", "ctl_stroke", None, "disabled"
        fill = "ctl_press" if self.pressed else ("ctl_hover" if self.hover else "ctl")
        return fill, "ctl_stroke_top", "ctl_stroke_bottom", "text"

    def draw(self):
        fill, st, sb, tc = self._colors()
        if self.text_color and not self.disabled:
            tc = self.text_color
        w, h = self.lw, self.lh
        if fill:
            if st:
                self.rrect(0, 0, w, h, 4, fill, st, stroke_bottom=sb if sb else None)
            else:
                self.rrect(0, 0, w, h, 4, fill)
        tw = text_width(self.label, self.font_px, self.weight) if self.label else 0
        gap = 8 if (self.icon_name and self.label) else 0
        iw = self.icon_px if self.icon_name else 0
        total = tw + gap + iw
        x = (w - total) / 2
        cy = h / 2
        if self.icon_name and not self.icon_right:
            self.icon(self.icon_name, x, cy - self.icon_px / 2, self.icon_px, tc)
            x += iw + gap
        if self.label:
            self.text(x, cy, self.label, self.font_px, self.weight, color=tc)
            x += tw + gap
        if self.icon_name and self.icon_right:
            self.icon(self.icon_name, x, cy - self.icon_px / 2, self.icon_px, tc)


class ToolButton(Control):
    """Toolbar button (32 high, radius 4, text 12.5, icon 16, padding 0 11); ``on`` = selected tool."""

    def __init__(self, master, text: str = "", icon: Optional[str] = None, bg: str = "card", command=None,
                 tooltip=None):
        super().__init__(master, bg=bg, command=command, tooltip=tooltip)
        self.label, self.icon_name, self.on = text, icon, False
        self.icon_only = False

    def natural_width(self, icon_only: bool = False) -> float:
        if icon_only or not self.label:
            return 32
        return 11 + 16 + 8 + text_width(self.label, 12.5) + 11

    def set_on(self, on: bool):
        if on != self.on:
            self.on = on
            self.redraw()

    def draw(self):
        w, h = self.lw, self.lh
        if self.on:
            self.rrect(0, 0, w, h, 4, "tool_on", "tool_on_stroke")
        elif (self.hover or self.pressed) and not self.disabled:
            self.rrect(0, 0, w, h, 4, "tool_hover")
        color = "disabled" if self.disabled else "text"
        icol = "accent" if (self.on and not self.disabled) else color   # selected tool: accent glyph
        if self.icon_only or not self.label:
            self.icon(self.icon_name, (w - 16) / 2, (h - 16) / 2, 16, icol)
        else:
            self.icon(self.icon_name, 11, (h - 16) / 2, 16, icol)
            self.text(11 + 16 + 8, h / 2, self.label, 12.5, color=color)


class IconButton(Control):
    """Square transparent icon button (⋯ 36×36 icon 20, «Назад» 36×36 icon 16, «×» 24×24 icon 10)."""

    def __init__(self, master, icon: str, icon_px: float = 16, bg: str = "bg", command=None, tooltip=None,
                 color: str = "text", radius: float = 4, hover_token: str = "ctl_hover"):
        super().__init__(master, bg=bg, command=command, tooltip=tooltip)
        self.icon_name, self.icon_px, self.color, self.radius = icon, icon_px, color, radius
        self.hover_token = hover_token

    def draw(self):
        w, h = self.lw, self.lh
        if (self.hover or self.pressed) and not self.disabled:
            self.rrect(0, 0, w, h, self.radius, "ctl_press" if self.pressed else self.hover_token)
        self.icon(self.icon_name, (w - self.icon_px) / 2, (h - self.icon_px) / 2, self.icon_px,
                  "disabled" if self.disabled else self.color)


class Link(Control):
    """Hyperlink text (no underline, Win11 style); hover = slightly lighter."""

    def __init__(self, master, text: str, px: float = 13.5, color: str = "link", bg: str = "bg",
                 command=None, weight: str = "normal"):
        super().__init__(master, bg=bg, command=command, cursor="hand2")
        self.label, self.px, self.color, self.weight = text, px, color, weight

    def natural_width(self) -> float:
        return text_width(self.label, self.px, self.weight) + 1

    def set_text(self, t: str):
        if t != self.label:
            self.label = t
            self.redraw()

    def draw(self):
        c = Theme.c(self.color)
        if self.hover and not self.disabled:
            c = gfx_mix(c, Theme.c(self.bg_token), 0.2)
        if self.disabled:
            c = Theme.c("disabled")
        self.create_text(0, S(self.lh / 2), text=self.label, font=F(self.px, self.weight), fill=c, anchor="w")


def gfx_mix(c1: str, c2: str, t: float) -> str:
    from ui.theme import rgb, _hex
    a, b = rgb(c1), rgb(c2)
    return _hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


# --------------------------------------------------------------------------- toggle
class Toggle(Control):
    """Win11 toggle with «Вкл.»/«Откл.» label 14 px on the left (gap 12)."""

    def __init__(self, master, value: bool = False, bg: str = "card", command=None, show_label: bool = True,
                 label_fn: Optional[Callable[[bool], str]] = None):
        super().__init__(master, bg=bg)
        self.value = value
        self.on_change = command
        self.show_label = show_label
        self.label_fn = label_fn or (lambda v: "")
        self.command = self._flip

    def natural_width(self) -> float:
        if not self.show_label:
            return 40
        return max(text_width(self.label_fn(True), 14), text_width(self.label_fn(False), 14)) + 12 + 40

    def _flip(self):
        self.value = not self.value
        self.redraw()
        if self.on_change:
            self.on_change(self.value)

    def set(self, v: bool):
        if v != self.value:
            self.value = v
            self.redraw()

    def draw(self):
        w, h = self.lw, self.lh
        tx = w - 40
        if self.show_label:
            self.text(tx - 12, h / 2, self.label_fn(self.value), 14,
                      color="disabled" if self.disabled else "text", anchor="e")
        bg = Theme.c(self.bg_token)
        key = ("tg", self.value, self.hover and not self.disabled, self.disabled, bg, Theme.mode)
        self.put_cached(tx, (h - 20) / 2, key, lambda: gfx.toggle(
            self.value, Theme.c("accent"), Theme.c("toggle_off_fill"), Theme.c("toggle_off_stroke"),
            Theme.c("toggle_off_knob"), Theme.c("on_accent"), bg, self.hover and not self.disabled,
            self.disabled, Theme.c("disabled")))


# --------------------------------------------------------------------------- radio / checkbox
class Radio(Control):
    def __init__(self, master, text: str, selected: bool = False, bg: str = "card", command=None):
        super().__init__(master, bg=bg, command=command)
        self.label, self.selected = text, selected

    def set(self, sel: bool):
        if sel != self.selected:
            self.selected = sel
            self.redraw()

    def draw(self):
        bg = Theme.c(self.bg_token)
        hov = self.hover and not self.disabled
        stroke = "text" if (hov and not self.selected) else "check_off_stroke"
        fill = "check_off_hover" if hov else "check_off_fill"
        key = ("radio", self.selected, hov, bg, Theme.mode)
        self.put_cached(0, (self.lh - 20) / 2, key, lambda: gfx.radio(
            self.selected, Theme.c("accent"), Theme.c("on_accent"), Theme.c(fill), Theme.c(stroke), bg, hov))
        self.text(28, self.lh / 2, self.label, 14)


class CheckRow(Control):
    """Checkbox 20×20 with a title 14/18 and a grey description 12/16 right under it."""

    def __init__(self, master, title: str, desc: str = "", checked: bool = False, bg: str = "card", command=None):
        super().__init__(master, bg=bg)
        self.title, self.desc, self.checked = title, desc, checked
        self.on_change = command
        self.command = self._flip

    def _flip(self):
        self.checked = not self.checked
        self.redraw()
        if self.on_change:
            self.on_change(self.checked)

    def set(self, v: bool):
        if v != self.checked:
            self.checked = v
            self.redraw()

    def draw(self):
        bg = Theme.c(self.bg_token)
        hov = self.hover
        stroke = "check_off_stroke"
        fill = "check_off_hover" if hov else "check_off_fill"
        key = ("cbx", self.checked, hov, bg, Theme.mode)
        # checkbox top 1 px above the text top (title line box starts at 0)
        self.put_cached(0, 0, key, lambda: gfx.checkbox(
            self.checked, Theme.c("accent_hover" if (hov and self.checked) else "accent"), Theme.c("on_accent"),
            Theme.c(fill), Theme.c(stroke), bg))
        self.text(28, 1 + 9, self.title, 14, color="text_card")
        if self.desc:
            self.text(28, 1 + 18 + 8, self.desc, 12, color="muted")


# --------------------------------------------------------------------------- ComboBox
class ComboBox(Control):
    """Win11 ComboBox (closed: 32 high, radius 4, padding 0 10 0 12, text 14, chevron 14).
    Opens a ``ListPopup`` over the field.

    Remark 35: the closed field is as wide as its longest item (so it does not jump when the choice
    changes); ``width`` is a minimum and ``max_width`` a cap — a longer item is shortened with «…»
    before the chevron.  The list measures every item itself (see ``ListPopup``)."""

    def __init__(self, master, app, items: Sequence[Optional[str]] = (), index: int = 0, bg: str = "card",
                 command: Optional[Callable[[int], None]] = None, width: Optional[float] = None,
                 swatch_fn: Optional[Callable[[int], Optional[str]]] = None, min_list_width: float = 0,
                 value_text: Optional[Callable[[], str]] = None, font_px: float = 14, chev_px: float = 14,
                 max_list_height: float = 392, max_width: Optional[float] = None,
                 context_fn: Optional[Callable[[int, float, float], None]] = None):
        super().__init__(master, bg=bg)
        self.app = app
        self.context_fn = context_fn        # stage 5: right click on a list item (ListPopup)
        self.font_px, self.chev_px, self.max_list_height = font_px, chev_px, max_list_height
        self.items = list(items)
        self.index = index
        self.on_select = command
        self.fixed_width = width            # minimum width (remark 35)
        self.max_width = max_width
        self.swatch_fn = swatch_fn
        self.min_list_width = min_list_width
        self.value_text = value_text
        self.open = False
        self.command = self.show_list

    def set_items(self, items, index):
        self.items, self.index = list(items), index
        self.redraw()

    def set_index(self, i):
        if i != self.index:
            self.index = i
            self.redraw()

    def current_text(self) -> str:
        if self.value_text:
            return self.value_text()
        if 0 <= self.index < len(self.items) and self.items[self.index] is not None:
            return self.items[self.index]
        return ""

    def item_width(self, text: str, swatch: bool = False) -> float:
        """Closed-field width that shows ``text`` in full: 12 + swatch 24 + text + 8 + chevron + 10 + 2."""
        return round(12 + (24 if swatch else 0) + text_width(text, self.font_px) + 8 + self.chev_px + 10 + 2 + 0.5)

    def natural_width(self) -> float:
        texts = [(it, bool(self.swatch_fn and self.swatch_fn(i))) for i, it in enumerate(self.items) if it]
        if self.value_text:
            texts.append((self.value_text(), False))
        w = max((self.item_width(t, sw) for t, sw in texts), default=self.item_width(self.current_text()))
        if self.fixed_width:
            w = max(w, self.fixed_width)
        if self.max_width:
            w = min(w, max(self.max_width, self.fixed_width or 0))
        return w

    def text_room(self, w: Optional[float] = None) -> float:
        """Room for the value text in the closed field (it never runs under the chevron)."""
        w = self.lw if w is None else w
        sw = 24 if (self.swatch_fn and self.swatch_fn(self.index)) else 0
        return w - 12 - sw - 8 - self.chev_px - 10

    def show_list(self):
        from ui.widgets.overlay import ListPopup, widget_rect
        if not self.items:
            return
        self.open = True
        self.redraw()
        sw = {}
        if self.swatch_fn:
            for i in range(len(self.items)):
                c = self.swatch_fn(i)
                if c:
                    sw[i] = c
        self.popup = ListPopup(self.app, self.items, self.index, widget_rect(self.app.root, self), self._picked,
                               min_width=self.min_list_width, swatches=sw, on_close=self._closed,
                               context_fn=self.context_fn)

    def _closed(self):
        self.open = False
        self.hover = False
        try:
            self.redraw()
        except tk.TclError:
            log.debug("ComboBox._closed: tk.TclError caught", exc_info=True)   # remark 81

    def _picked(self, i):
        self.index = i
        self.redraw()
        if self.on_select:
            self.on_select(i)

    def draw(self):
        w, h = self.lw, self.lh
        if self.disabled:
            fill = "ctl_disabled"
        elif self.open or self.pressed:
            fill = "ctl_hover"
        else:
            fill = "ctl_hover" if self.hover else "ctl"
        self.rrect(0, 0, w, h, 4, fill, "ctl_stroke_top", stroke_bottom="combo_stroke_bottom")
        x = 12
        sw = self.swatch_fn(self.index) if self.swatch_fn else None
        if sw:
            self.rrect(x, (h - 16) / 2, 16, 16, 4, sw, "swatch_stroke", bg=fill)
            x += 24
        self.text(x, h / 2, elide(self.current_text(), self.text_room(w), self.font_px), self.font_px,
                  color="disabled" if self.disabled else "text")
        c = self.chev_px
        self.icon("chev_down", w - 10 - c, (h - c) / 2, c, "muted")


# --------------------------------------------------------------------------- TextBox
class TextBox(Box):
    """Win11 TextBox: 32 high, radius 4, padding 0 4 0 11, text 14; thin stroke + darker bottom line;
    focus = 2 px accent line at the bottom only; «×» 24×24 inside (visible with text + focus);
    separate square «✓» 36×32 8 px to the right (part of this widget when ``apply_button``).
    Enter applies like «✓».  ``validate(text)`` filters keystrokes, ``on_apply(text)`` applies.

    Remark 33: ``fit`` = sample text the field must show in full next to a visible «×» (measured
    with the real font: 11 + text + caret + 30 px «×» area), e.g. «12,34» for numbers, «255» for
    R/G/B; ``width`` is then a minimum.  «×» / «✓» keep the keyboard focus in the entry (their
    press is handled here and stops the CustomTkinter «focus the clicked widget» binding), «×»
    stays visible while it is pressed, and a click anywhere on the field puts the caret in it."""

    CLEAR_AREA = 30     # «×» 24 + 4 right padding + 2 gap before the text (remark 33: 32 → 30)

    def __init__(self, master, app, value: str = "", width: float = 80, bg: str = "card",
                 on_apply: Optional[Callable[[str], bool]] = None,
                 allow: Optional[Callable[[str], bool]] = None, apply_button: bool = True,
                 placeholder: str = "", font_px: float = 14, chip: Optional[Callable[[], str]] = None,
                 on_change: Optional[Callable[[str], None]] = None, fit: Optional[str] = None):
        super().__init__(master, bg=bg)
        self.app = app
        self.font_px, self.chip, self.on_change = font_px, chip, on_change
        self.min_w = width
        self.fit = fit
        self.apply_button = apply_button
        self.on_apply = on_apply
        self.allow = allow
        self.placeholder = placeholder
        self.focused = False
        self.hover = False
        self.value = value
        vcmd = (self.register(self._validate), "%P")
        self.entry = tk.Entry(self, bd=0, highlightthickness=0, relief="flat",
                              validate="key", validatecommand=vcmd)
        self.entry.insert(0, value)
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.entry.bind("<Return>", lambda e: self.apply())
        self.entry.bind("<KP_Enter>", lambda e: self.apply())
        self.entry.bind("<Escape>", self._esc)
        self.entry.bind("<KeyRelease>", self._key_release)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", self._click_field)
        self.clear_btn = IconButton(self, "clear", 10, bg="input_focus", command=self.clear,
                                    tooltip=lambda: app.t("common.textbox.clear.tooltip"), color="muted")
        self.apply_btn = Button(self, "", kind="secondary", icon="check", bg=bg, command=self.apply,
                                tooltip=lambda: app.t("common.textbox.apply.tooltip")) if apply_button else None
        for b in (self.clear_btn, self.apply_btn):
            if b is not None:
                b.bind("<ButtonPress-1>", self._keep_focus, add="+")
        self._win = None

    # geometry ---------------------------------------------------------------
    def fit_width(self) -> float:
        """Field width (without «✓») that shows ``fit`` in full with «×» visible."""
        if not self.fit:
            return 0.0
        left = 39 if self.chip else 11
        return float(math.ceil(left + text_width(self.fit, self.font_px) + 3 + self.CLEAR_AREA))

    @property
    def box_w(self) -> float:
        return max(self.min_w, self.fit_width())

    @box_w.setter
    def box_w(self, v: float) -> None:
        self.min_w = v

    def natural_width(self) -> float:
        return self.box_w + (8 + 36 if self.apply_button else 0)

    def _key_release(self, _e=None):
        self._update_clear()
        if self.on_change:
            self.on_change(self.entry.get())

    # behaviour --------------------------------------------------------------
    def _keep_focus(self, _e=None):
        """«×» / «✓» press: keep the caret in the entry, don't let the click move the focus."""
        if self.focus_get() is not self.entry:
            self.entry.focus_set()
        return "break"

    def _click_field(self, _e=None):
        """Click on the padding / placeholder / empty field: caret into the entry (remark 33).

        With the placeholder shown the entry sits off-canvas (unmapped) and cannot take the focus,
        so it is put in place first.  The «break» stops CustomTkinter's «focus the clicked widget»."""
        if self.focus_get() is not self.entry:
            if not self.focused:
                self.focused = True
                self.redraw()
                self.update_idletasks()
            self.entry.focus_set()
            self.after(60, self._check_focus)
        self.entry.icursor("end")
        return "break"

    def _check_focus(self):
        try:
            if self.focused and self.focus_get() is not self.entry:
                self.focused = False
                self.redraw()
        except (tk.TclError, KeyError):
            log.debug("TextBox._check_focus: (tk.TclError, KeyError) caught", exc_info=True)   # remark 81

    def _validate(self, proposed: str) -> bool:
        if self.allow is None:
            return True
        try:
            return bool(self.allow(proposed))
        except Exception:
            log.exception("validator failed")
            return False

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str) -> None:
        changed = value != self.entry.get()
        self.value = value
        v = self.entry.cget("validate")
        self.entry.configure(validate="none")
        self.entry.delete(0, "end")
        self.entry.insert(0, value)
        self.entry.configure(validate=v)
        if changed and self.visible:
            self.redraw()          # placeholder / text area depend on the value
        else:
            self._update_clear()

    def clear(self):
        self.entry.delete(0, "end")
        self.entry.focus_set()
        self._update_clear()
        if self.on_change:
            self.on_change("")

    def apply(self):
        text = self.entry.get()
        ok = True
        if self.on_apply:
            try:
                ok = self.on_apply(text) is not False
            except Exception:
                log.exception("apply failed")
                ok = False
        if ok:
            self.value = self.entry.get()
        else:
            self.set(self.value)  # invalid / empty: keep the previous value
        return "break"

    def _revert(self):
        self.set(self.value)
        self.app.root.focus_set()

    def _esc(self, _e=None):
        """Stage 5: Esc in a field only drops the edit and the focus; the next Esc closes the page.
        Inside a dialog it goes on to the dialog (Esc = «Отмена»)."""
        self._revert()
        from ui.widgets.overlay import Popup
        if Popup.current is not None:
            return None
        try:
            self.winfo_toplevel().focus_set()
        except Exception:
            log.warning("TextBox._esc: Exception caught", exc_info=True)   # remark 81
        return "break"

    def _focus_in(self, _e=None):
        self.focused = True
        self.redraw()

    def _focus_out(self, _e=None):
        if self.clear_btn.pressed:   # «×» being pressed: keep it (and the focus look) until release
            return
        self.focused = False
        self.redraw()

    def _set_hover(self, h):
        if h != self.hover:
            self.hover = h
            self.redraw()

    def _update_clear(self):
        show = (self.focused and bool(self.entry.get())) or self.clear_btn.pressed
        if show:
            self.clear_btn.set_bg("input_focus")
            self.clear_btn.geom(self.box_w - 4 - 24, (32 - 24) / 2, 24, 24)
            self.clear_btn.lift()
        else:
            self.clear_btn.hide()

    # drawing ----------------------------------------------------------------
    def draw(self):
        w = self.box_w
        if self.focused:
            fill = "input_focus"
            self.rrect(0, 0, w, 32, 4, fill, "ctl_stroke", stroke_bottom="accent", bottom_w=2)
        else:
            fill = "input_hover" if self.hover else "input"
            self.rrect(0, 0, w, 32, 4, fill, "ctl_stroke", stroke_bottom="input_bottom")
        c = Theme.c(fill)
        right = 4 + (self.CLEAR_AREA - 4 if (self.focused and self.entry.get()) else 0)
        left = 11
        if self.chip:
            self.rrect(13, 7, 18, 18, 4, self.chip(), "check_off_stroke")
            left = 39
        fpx = self.font_px
        self.entry.configure(bg=c, fg=Theme.c("text"), insertbackground=Theme.c("text"), font=F(fpx),
                             selectbackground=Theme.c("accent"), selectforeground=Theme.c("on_accent"),
                             disabledbackground=c, readonlybackground=c, insertwidth=max(1, S(1)))
        eh = F(fpx).metrics("linespace")
        ph = bool(self.placeholder and not self.focused and not self.entry.get())
        if ph:
            self.text(left + 1, 16, self.placeholder, fpx, color="muted")
            # keep the entry alive but off-canvas; a click on the field focuses it (_click_field)
            self._win = self.create_window(S(-500), S(16), window=self.entry, anchor="w", width=4, height=eh)
        else:
            self._win = self.create_window(S(left), S(16), window=self.entry, anchor="w",
                                           width=max(4, S(w - left - right)), height=eh)
        if self.apply_btn:
            self.apply_btn.set_bg(self.bg_token)
            self.apply_btn.geom(w + 8, 0, 36, 32)
        self._update_clear()


# --------------------------------------------------------------------------- slider
class Slider(Control):
    """Win11 slider: rail 4 px, accent fill, thumb 20 with accent inner dot."""

    def __init__(self, master, lo: float, hi: float, value: float, bg: str = "card",
                 command: Optional[Callable[[float], None]] = None, on_release: Optional[Callable[[float], None]] = None):
        super().__init__(master, bg=bg)
        self.lo, self.hi, self.value = lo, hi, value
        self.on_change, self.on_release = command, on_release
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonPress-1>", self._drag, add="+")
        self.bind("<ButtonRelease-1>", self._rel, add="+")

    def set(self, v):
        self.value = v
        self.redraw()

    def _val_at(self, x_dev):
        x = x_dev / Scale.factor
        t = (x - 10) / max(1, self.lw - 20)
        t = max(0.0, min(1.0, t))
        return round(self.lo + t * (self.hi - self.lo))

    def _drag(self, e):
        if self.disabled:
            return
        v = self._val_at(e.x)
        if v != self.value:
            self.value = v
            self.redraw()
            if self.on_change:
                self.on_change(v)

    def _rel(self, e):
        if self.on_release and not self.disabled:
            self.on_release(self.value)

    def draw(self):
        w, h = self.lw, self.lh
        t = (self.value - self.lo) / ((self.hi - self.lo) or 1)
        cy = h / 2
        # rail spans the thumb-centre range (10 … w − 10) like the mockup track
        self.rrect(10, cy - 2, w - 20, 4, 2, "slider_rail")
        fx = 10 + t * (w - 20)
        if fx > 10:
            self.rrect(10, cy - 2, max(4, fx - 10), 4, 2, "accent", bg=self.bg_token)
        bg = Theme.c(self.bg_token)
        key = ("thumb", self.hover, self.pressed, bg, Theme.mode)

        def mk():
            im = gfx.circle(20, Theme.c("slider_thumb"), Theme.c("slider_thumb_stroke"), bg=None)
            r = 7 if (self.hover or self.pressed) else 6
            if self.pressed:
                r = 5
            dot = gfx.circle(2 * r, Theme.c("accent"))
            im.alpha_composite(dot, (S(10 - r), S(10 - r)))
            return im
        self.put_cached(fx - 10, cy - 10, key, mk)


# --------------------------------------------------------------------------- segmented
class Segmented(Control):
    """Segmented control like the stepper: track with 2 px padding, selected segment white with
    an inner stroke and a 16×3 accent bar 2 px from the bottom (text 11.5 / 12.5)."""

    def __init__(self, master, labels: Sequence[str], index: int = 0, bg: str = "card",
                 command: Optional[Callable[[int], None]] = None, font_px: float = 11.5,
                 equal: bool = True, track: str = "seg_track", seg_pad=(8, 8), text_dy: float = -2):
        super().__init__(master, bg=bg)
        self.labels, self.index = list(labels), index
        self.on_select = command
        self.font_px = font_px
        self.equal = equal
        self.track = track
        self.seg_pad = seg_pad
        self.text_dy = text_dy
        self.hover_i = -1
        self.bind("<Motion>", self._motion)
        self.command = None

    def set_index(self, i):
        if i != self.index:
            self.index = i
            self.redraw()

    def seg_widths(self, total: Optional[float] = None) -> List[float]:
        n = len(self.labels)
        inner = (total if total is not None else self.lw) - 2 - 4
        if self.equal:
            return [(inner - 2 * (n - 1)) / n] * n
        return [text_width(l, self.font_px) + self.seg_pad[0] + self.seg_pad[1] for l in self.labels]

    def natural_width(self) -> float:
        ws = [text_width(l, self.font_px) + self.seg_pad[0] + self.seg_pad[1] for l in self.labels]
        return sum(ws) + 2 * (len(ws) - 1) + 4 + 2

    def _seg_at(self, x):
        ws = self.seg_widths()
        cx = 1 + 2
        for i, w in enumerate(ws):
            if cx <= x < cx + w + 2:
                return i
            cx += w + 2
        return -1

    def _motion(self, e):
        i = self._seg_at(e.x / Scale.factor)
        if i != self.hover_i:
            self.hover_i = i
            self.redraw()

    def _on_leave(self, _e=None):
        self.hover_i = -1
        super()._on_leave(_e)

    def _on_release(self, e=None):
        super()._on_release(None)
        if e is None or self.disabled:
            return
        i = self._seg_at(e.x / Scale.factor)
        if i >= 0 and i != self.index:
            self.index = i
            self.redraw()
            if self.on_select:
                self.on_select(i)

    def draw(self):
        w, h = self.lw, self.lh
        self.rrect(0, 0, w, h, 4, self.track, "seg_track_stroke")
        ws = self.seg_widths()
        x = 1 + 2
        for i, sw in enumerate(ws):
            sh = h - 6
            if i == self.index:
                self.rrect(x, 3, sw, sh, 4, "seg_on", "seg_on_stroke", bg=self.track)
                self.rrect(x + sw / 2 - 8, 3 + sh - 2 - 3, 16, 3, 1.5, "accent", bg="seg_on")
                color = "text"
            else:
                if i == self.hover_i and not self.disabled:
                    self.rrect(x, 3, sw, sh, 4, "seg_hover", bg=self.track)
                color = "muted"
            self.text(x + sw / 2, 3 + sh / 2 + self.text_dy, self.labels[i], self.font_px, color=color,
                      anchor="center")
            x += sw + 2
