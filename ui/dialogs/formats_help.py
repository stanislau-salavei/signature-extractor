"""Help dialog. «formats» = dialog 21; other topics (start / prep / process / batch) use the same dialog
and are built from the help.<topic>.* rows of the i18n table (the full help centre 22–26 is a later stage).

Remark 24 (2026-11-17): an in-window ContentDialog like «О программе» — no system title bar, bold title
inside, the text scrolls inside the panel (thin Win11 bar, mouse wheel, ↑/↓, PgUp/PgDn), footer with
«Понятно»; Esc and Enter close.  The panel height fits the window (the minimum 1024 × 648 included)."""
from __future__ import annotations

import re
from typing import List, Tuple

from ui import gfx
from ui.dialogs.content import ContentDialog, wrap_runs
from ui.theme import F, S, Theme
from ui.widgets.base import Box
from ui.widgets.scroll import ScrollArea

W, SCROLL_H, FOOT_H = 718, 518, 64      # W = content width (panel 720); SCROLL_H = max text area height
TITLE_H = 24 + 25 + 12                   # body padding + title line + gap above the text
PAD_L, PAD_R, PAD_T, PAD_B = 24, 28, 8, 36
TEXT_W = W - PAD_L - PAD_R
LH = 19.5
TILE = {"PNG": (("#0F7B0F", "#E7F5EA"), ("#6CCB5F", "#1E3A23")),
        "SVG": (("#8A5A00", "#FFF3D6"), ("#FCE100", "#3D3414")),
        "DXF": (("#005FB8", "#E3F0FB"), ("#60CDFF", "#16304A"))}


def split_key(text: str) -> List[Tuple[str, str]]:
    """«Для чего: …» → bold «Для чего:»; «"«15 × 5 мм» (по умолчанию)…» → bold quote; «Цвет подписи. …»."""
    m = re.match(r"^([^:.…«(]{1,28}:)\s", text)
    if not m:
        m = re.match(r"^(«[^»]+»\.?|[^.…:«(]{1,30}[.…])(?=\s)", text)
    if not m:
        return [(text, "normal")]
    return [(m.group(1), "semibold"), (text[m.end(1):], "normal")]


def bold_quotes(runs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """«Открыть файл» and other quoted UI names are semibold, as in the mockups 22–26 (quotes stay)."""
    out: List[Tuple[str, str]] = []
    for text, wt in runs:
        if wt != "normal":
            out.append((text, wt))
            continue
        for i, part in enumerate(re.split(r"(«[^»]{1,60}»)", text)):
            if part:
                out.append((part, "semibold" if i % 2 else "normal"))
    return out


def _li(text):
    """List item with a bold «Key:» lead (formats: «Для чего:», «Разрешение:» …)."""
    return ("li", bold_quotes(split_key(text)))


def _lq(text):
    """Plain list item; only quoted UI names are bold (22–25: «Сбросить к авто», «Чувствительность» …)."""
    return ("li", bold_quotes([(text, "normal")]))


def _p(text):
    return ("p", bold_quotes([(text, "normal")]))


def _pk(text):
    """Paragraph in text colour with a bold lead («Цвет подписи. …») — cards without a title."""
    return ("pk", bold_quotes(split_key(text)))


def _card(icon, title, items):
    return ("card", (icon, title, items))


# ----------------------------------------------------------------------------- topics (remark 41)
# Every help section is a card with an icon on the left, as in the mockups 22–26; texts are unchanged.
def formats_blocks(t):
    """«Форматы экспорта» (26, also dialog 21): PNG / SVG / DXF tiles, size, colour, file name template."""
    li = lambda k: _li(t(f"help.formats.{k}"))
    b = [("intro", t("help.formats.lead"))]
    b.append(_card("PNG", t("help.formats.png"), [_p(t("help.formats.png_text"))] +
                   [li(k) for k in ("png_use", "png_res", "png_limit")]))
    b.append(_card("SVG", t("help.formats.svg"), [_p(t("help.formats.svg_text"))] +
                   [li(k) for k in ("svg_use", "svg_thickness", "svg_limit")]))
    b.append(_card("DXF", t("help.formats.dxf"), [_p(t("help.formats.dxf_text")), li("dxf_compat"),
                                                 ("li", bold_quotes([(t("help.formats.toggles"), "normal")]))]))
    b.append(_card("hc_size", t("export.size"), [li(k) for k in ("size_original", "size_15x5", "size_custom", "png_margin")] +
                   [("li", bold_quotes([(t("help.formats.size_templates"), "normal")]))]))
    b.append(_card("hc_color", None, [_pk(t("help.formats.color"))]))
    b.append(_card("filename", None, [_pk(t("help.formats.name_template"))]))     # remark 44
    return b


def _start(t):
    k = lambda tail: t(f"help.start.{tail}")
    return [("intro_logo", k("lead")),
            _card("hc_what", k("what"), [_lq(k(f"what{i}")) for i in range(1, 5)]),
            _card("hc_how", k("how"), [_p(k("how_lead"))] +
                  [("ol", (i, bold_quotes(split_key(k(f"how{i}"))))) for i in range(1, 4)]),
            _card("hc_privacy", k("privacy"), [_p(k("privacy_text"))]),
            _card("gear", k("settings"), [_p(k("settings_text"))])]                  # remark 49, item 10


def _prep(t):
    k = lambda tail: t(f"help.prep.{tail}")
    ex = {"good": k("ex_good"), "good_text": k("ex_good_text"), "bad": [k(f"ex_{n}") for n in EX_BAD]}
    return [("intro", k("lead")), ("examples", ex),                                 # remark 42
            _card("hc_shoot", k("shoot"), [_lq(k(f"shoot{i}")) for i in range(1, 6)]),
            _card("hc_paper", k("paper"), [_p(k("paper_text"))]),
            _card("hc_add", k("add"), [_p(k("add_text"))])]


def _process(t):
    k = lambda tail: t(f"help.process.{tail}")
    return [("intro", k("lead")),
            _card("hc_frame", t("process.tool.frame"), [_p(k("frame1"))] + [_lq(k(f"frame{i}")) for i in (2, 3, 4)]),
            _card("hc_eraser", t("process.tool.eraser"), [_p(k("eraser"))]),
            _card("hc_flatten", t("process.filter.flatten"), [_p(k("flatten"))]),
            _card("hc_ink", t("process.filter.ink"), [_p(k("ink")), _lq(k("ink_auto")), _lq(k("ink_manual")),
                                                                 _lq(k("ink_exclude"))]),          # remarks 66, 69
            _card("hc_ai", t("process.ai"), [_p(k("ai"))]),
            _card("hc_tune", t("process.finetune"), [_p(k("finetune"))] +
                  [_lq(k(x)) for x in ("sensitivity", "denoise", "thickness", "reset")]),
            _card("hc_bg", k("bg"), [_p(k("bg_text"))])]


def _batch(t):
    k = lambda tail: t(f"help.batch.{tail}")
    return [("intro", k("lead")),
            _card("hc_strip", k("strip"), [_p(k("strip_text"))]),
            _card("hc_tune", k("all"), [_p(k("all_text"))]),
            _card("hc_attention", k("attention"), [_p(k("attention_text")),
                                                   _p(k("attention_reasons"))]),                    # remark 69
            _card("hc_add_remove", k("add_remove"), [_p(k("add_remove_text")), _p(k("skipped_text"))]),
            _card("hc_save", t("settings.save"), [_p(k("save_text")), _p(k("exists_text"))])]


TOPIC_BLOCKS = {"start": _start, "prep": _prep, "process": _process, "batch": _batch}


def generic_blocks(app, topic):
    return TOPIC_BLOCKS[topic](app.t)


def topic_blocks(app, topic):
    return formats_blocks(app.t) if topic == "formats" else generic_blocks(app, topic)


def card_titles(blocks):
    return [d[1] for k, d in blocks if k == "card"]


# ----------------------------------------------------------------------------- metrics (mockups 22–26, r42)
CARD_PAD_X, CARD_PAD_Y, CARD_GAP = 16, 9, 8
TILE_PX, TILE_GAP = 32, 14
TEXT_X = CARD_PAD_X + TILE_PX + TILE_GAP          # 62
TITLE_LH, P_LH = 18.0, 18.85                       # 13.5 / 1.33, 13 / 1.45
EX_COLS = (330, 281, 281)                          # «Хорошо» : bad : bad  (mockup_r42 v2, proportional)
EX_GAP, EX_PAD, EX_PAD_B, EX_CAP_GAP = 8, 8, 10, 8
EX_ASPECT = 265 / 124
CAP_LH, SMALL_LH = 17.94, 17.25
EX_BAD = ("shadow", "glare", "tiny", "skew")


def _blend_hex(fg, a, base):
    from ui.theme import blend
    return blend(fg, a, base)


def _photo(name, w, h, radius, bg):
    """Example photo (assets/help/ex_<name>.png) cover-cropped to w × h logical px, rounded corners."""
    from PIL import Image, ImageDraw
    from ui.theme import Scale
    W, H = max(1, int(round(w * Scale.factor))), max(1, int(round(h * Scale.factor)))
    src = Image.open(gfx.ASSETS / "help" / f"ex_{name}.png").convert("RGB")
    sw, sh = src.size
    k = max(W / sw, H / sh)
    im = src.resize((max(W, int(round(sw * k))), max(H, int(round(sh * k)))), Image.Resampling.LANCZOS)
    l, tp = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((l, tp, l + W, tp + H)).convert("RGBA")
    r = radius * Scale.factor
    mask = Image.new("L", (W * 4, H * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W * 4 - 1, H * 4 - 1), r * 4, fill=255)
    im.putalpha(mask.resize((W, H), Image.Resampling.LANCZOS))
    base = Image.new("RGBA", (W, H), gfx.rgba(bg))
    base.alpha_composite(im)
    return base


class _Content(Box):
    """Help renderer shared by the dialog (fixed width) and the «Справка» page (remark 30: width and left
    padding follow the page; ``title`` draws the 20 px topic title).  Remark 41: sections are cards with an
    icon tile; remark 42: «Подготовка фото» starts with the good / bad photo examples."""

    def __init__(self, master, blocks, bg="dialog", text_w=TEXT_W, pad_l=PAD_L, pad_t=PAD_T, page=False):
        super().__init__(master, bg=bg)
        self.blocks = blocks
        self.text_w, self.pad_l, self.pad_t = text_w, pad_l, pad_t
        self.page = page          # page: lead 13.5 in text colour; dialog: 13 muted (as before)

    def measure(self):
        return self._layout(draw=False)

    @staticmethod
    def measure_blocks(master, blocks, **kw):
        """Content height without placing a widget (text metrics only)."""
        probe = _Content(master, blocks, **kw)
        try:
            return probe.measure()
        finally:
            probe.destroy()

    def draw(self):
        self._layout(draw=True)

    # ------------------------------------------------------------------ text helpers
    def _runs(self, x, y, runs, width, px, lh, color="text", draw=True):
        from ui.theme import text_width
        lines = wrap_runs(runs, width, px)
        if draw:
            for i, ln in enumerate(lines):
                xx = x
                for s, wt in ln:
                    self.text(xx, y + lh * i + lh / 2, s, px, wt, color=color)
                    xx += text_width(s, px, wt)
        return lh * len(lines)

    # ------------------------------------------------------------------ cards
    def _card_body(self, x0, y, w, icon, title, items, draw):
        """Text column of a card; returns its height."""
        tw = w - TEXT_X - CARD_PAD_X
        x = x0 + TEXT_X
        yy = y
        if title:
            yy += self._runs(x, yy, [(title, "semibold")], tw, 13.5, TITLE_LH, "text", draw) + 3
        prev = None
        for kind, data in items:
            if kind == "p":
                if prev == "p":
                    yy += 6
                elif prev in ("li", "ol"):
                    yy += 4
                yy += self._runs(x, yy, data, tw, 13, P_LH, "muted", draw)
            elif kind == "pk":
                yy += self._runs(x, yy, data, tw, 13, P_LH, "text", draw)
            elif kind == "li":
                yy += 4 if prev is not None else 0
                if draw:
                    self.put_cached(x, yy + 7, ("bul", Theme.c("accent")), lambda: gfx.circle(5, Theme.c("accent")))
                yy += self._runs(x + 16, yy, data, tw - 16, 13, P_LH, "text", draw)
            elif kind == "ol":
                n, runs = data
                yy += 8
                if draw:
                    self.text(x, yy + P_LH / 2, f"{n}.", 13, "semibold", color="accent")
                yy += self._runs(x + 24, yy, runs, tw - 24, 13, P_LH, "text", draw)
            prev = kind
        return yy - y

    def _card(self, x0, y, w, data, draw):
        icon, title, items = data
        body_h = self._card_body(x0, y + CARD_PAD_Y, w, icon, title, items, draw=False)
        h = CARD_PAD_Y * 2 + max(body_h, TILE_PX + 1) + 2
        if draw:
            self.rrect(x0, y, w, h, 8, "card", "card_stroke")
            tx, ty = x0 + CARD_PAD_X, y + CARD_PAD_Y + 1 + 1
            if icon in TILE:
                fg, bgc = TILE[icon][1 if Theme.dark() else 0]
                self.put_cached(tx, ty, ("htile", icon, Theme.mode, TILE_PX), lambda: gfx.rrect(TILE_PX, TILE_PX, 4, bgc, bg=Theme.c("card")))
                self.create_text(S(tx + TILE_PX / 2), S(ty + TILE_PX / 2), text=icon, font=F(10.5, "bold"), fill=fg)
            else:
                soft = _blend_hex(Theme.c("accent"), 0.16 if Theme.dark() else 0.14, Theme.c("card"))
                self.put_cached(tx, ty, ("htile_soft", soft, TILE_PX), lambda: gfx.rrect(TILE_PX, TILE_PX, 4, soft, bg=Theme.c("card")))
                self.icon(icon, tx + 8, ty + 8, 16, "accent")
            self._card_body(x0, y + CARD_PAD_Y + 1, w, icon, title, items, draw=True)
        return h

    # ------------------------------------------------------------------ examples (remark 42)
    def _examples(self, x0, y, w, ex, draw):
        avail = w - 2 * EX_GAP
        tot = sum(EX_COLS)
        gw = avail * EX_COLS[0] / tot
        bw = (avail - gw) / 2
        pw = bw - 2 - 2 * EX_PAD
        ph = pw / EX_ASPECT
        caps = ex["bad"]
        cap_w = pw - 4 - 18 - 8
        cap_h = [max(18.0, len(wrap_runs([(c, "normal")], cap_w, 13)) * CAP_LH) for c in caps]
        tile_h = [2 + EX_PAD + ph + EX_CAP_GAP + ch + EX_PAD_B for ch in cap_h]
        row1, row2 = max(tile_h[0], tile_h[1]), max(tile_h[2], tile_h[3])
        good_cap_w = gw - 2 - 2 * EX_PAD - 4 - 18 - 8
        g_small = len(wrap_runs([(ex["good_text"], "normal")], good_cap_w, 12.5))
        g_cap = 18.6 + 2 + g_small * SMALL_LH
        total = max(row1 + EX_GAP + row2, 2 + EX_PAD + 120 + EX_CAP_GAP + g_cap + EX_PAD_B)
        if not draw:
            return total
        card = Theme.c("card")
        # «Хорошо»
        good_stroke = _blend_hex(Theme.c("success"), 0.55, card)
        self.rrect(x0, y, gw, total, 8, "card", good_stroke)
        gpw, gph = gw - 2 - 2 * EX_PAD, total - 2 - EX_PAD - EX_CAP_GAP - g_cap - EX_PAD_B
        self.put_cached(x0 + 1 + EX_PAD, y + 1 + EX_PAD, ("exph", "good", round(gpw, 1), round(gph, 1), card),
                        lambda: _photo("good", gpw, gph, 4, card))
        cy = y + 1 + EX_PAD + gph + EX_CAP_GAP
        self._mark(x0 + 1 + EX_PAD + 2, cy + 0.3, True)
        tx = x0 + 1 + EX_PAD + 2 + 18 + 8
        self.text(tx, cy + 9.3, ex["good"], 13.5, "semibold")
        self._runs(tx, cy + 18.6 + 2, [(ex["good_text"], "normal")], good_cap_w, 12.5, SMALL_LH, "muted")
        # bad 2 × 2
        for i, name in enumerate(EX_BAD):
            col, row = i % 2, i // 2
            bx = x0 + gw + EX_GAP + col * (bw + EX_GAP)
            by = y + (0 if row == 0 else row1 + EX_GAP)
            bh = row1 if row == 0 else (total - row1 - EX_GAP)
            self.rrect(bx, by, bw, bh, 8, "card", "card_stroke")
            self.put_cached(bx + 1 + EX_PAD, by + 1 + EX_PAD, ("exph", name, round(pw, 1), round(ph, 1), card),
                            lambda n=name: _photo(n, pw, ph, 4, card))
            cyy = by + 1 + EX_PAD + ph + EX_CAP_GAP
            self._mark(bx + 1 + EX_PAD + 2, cyy, False)
            self._runs(bx + 1 + EX_PAD + 2 + 18 + 8, cyy, [(caps[i], "normal")], cap_w, 13, CAP_LH, "text")
        return total

    def _mark(self, x, y, ok):
        fill = Theme.c("success" if ok else "error_icon")
        self.put_cached(x, y, ("exmark", fill, Theme.c("card")), lambda: gfx.circle(18, fill, bg=Theme.c("card")))
        self.icon("check" if ok else "dismiss", x + 3.5, y + 3.5, 11, "on_accent")

    # ------------------------------------------------------------------ layout
    def _layout(self, draw):
        PAD_L, TEXT_W = self.pad_l, self.text_w   # noqa: N806 (instance values shadow the dialog constants)
        y = self.pad_t
        prev = None
        for kind, data in self.blocks:
            if kind == "title":
                if draw:
                    self.text(PAD_L, y + 14, data, 20, "semibold")
                y += 28 + 8
                prev = "title"
                continue
            if prev in ("intro", "intro_logo"):
                y += 12 if self.page else 10
            elif prev in ("card", "examples"):
                y += CARD_GAP
            if kind == "intro":
                px, lh = (13.5, 20.25) if self.page else (13, LH)
                y += self._runs(PAD_L, y, [(data, "normal")], TEXT_W, px, lh, "text" if self.page else "muted", draw)
            elif kind == "intro_logo":
                px, lh = (13.5, 20.25) if self.page else (13, LH)
                lines = wrap_runs([(data, "normal")], TEXT_W - 64, px)
                th = lh * len(lines)
                hh = max(48.0, th)
                if draw:
                    self.put_cached(PAD_L, y + (hh - 48) / 2, ("logo", 48), lambda: gfx.icon("app_tile", 48, None))
                    self._runs(PAD_L + 64, y + (hh - th) / 2, [(data, "normal")], TEXT_W - 64, px, lh,
                               "text" if self.page else "muted", True)
                y += hh
            elif kind == "card":
                y += self._card(PAD_L, y, TEXT_W, data, draw)
            elif kind == "examples":
                y += self._examples(PAD_L, y, TEXT_W, data, draw)
            prev = kind
        return y + (28 if self.page else 20)


class HelpWindow(ContentDialog):
    button_w = 120

    @classmethod
    def open(cls, app, topic="formats"):
        return cls(app, topic)

    def __init__(self, app, topic):
        t = app.t
        self.topic = topic
        self.blocks = topic_blocks(app, topic)
        self.area = None
        self._scroll = 0.0
        self._content_h = _Content.measure_blocks(app.root, self.blocks, text_w=TEXT_W - 0)
        super().__init__(app, t(f"help.nav.{topic}"), "", [(t("common.got_it"), "primary", None)], width=W + 2)

    def scroll_h(self):
        avail = self.app.height() - 2 * 16 - 2 - 81 - TITLE_H   # panel ≥ 16 px from the window edges
        return max(120.0, min(SCROLL_H, self._content_h, avail))

    def _body_h(self):
        return TITLE_H + self.scroll_h()

    def render(self):
        if self.area is not None:
            self._scroll = self.area.scroll
            self._drop_area()
        super().render()
        sh = self.scroll_h()
        area = ScrollArea(self.root, bg="dialog")
        area.in_popup = True
        content = _Content(area.inner, self.blocks)
        area.geom(self.px + 1, self.py + 1 + TITLE_H, W, sh, self._content_h)
        content.geom(0, 0, W - 14, self._content_h)
        content.redraw()
        area.lift()
        area.bar.lift()
        area.scroll_to(self._scroll)
        area.bind_wheel()
        self.area, self.content = area, content
        self.cv.focus_force()     # modal: take the keyboard even if focus was on a widget that just went away

    def key(self, d):
        if self.area is not None and d:
            self.area.scroll_by(d * 40)

    def _drop_area(self):
        a = self.area
        self.area = None
        if a is None:
            return
        a.unbind_wheel()
        for wd in (a.bar, a):
            try:
                wd.destroy()
            except Exception:
                pass

    def close(self):
        self._drop_area()
        super().close()
