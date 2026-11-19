"""Dialog 28 «О программе»: 380 wide; name, version, ©, links (repo, release notes, licence GNU GPLv3);
footer «Сообщить о проблеме» + «ОК»."""
from __future__ import annotations

from core.version import LICENSE_URL, RELEASE_TAG, REPO_URL, VERSION
from ui.dialogs.content import ContentDialog
from ui.theme import text_width
from ui.widgets.base import Box
from ui.widgets.controls import Link


class _Meta(Box):
    def __init__(self, master, app):
        super().__init__(master, bg="dialog")
        self.app = app

    def draw(self):
        t = self.app.t
        self.text(0, 8.75, t("app.name"), 14)
        self.text(0, 19.5 + 8.75, t("about.version", version=self.app.VERSION_STR), 14)
        self.text(0, 45 + 8.4, "© 2026 Stanislau Salavei", 12.5, color="muted")
        self.text(0, 138.2 + 9.1, t("settings.license"), 12.5, color="muted")


class AboutDialog(ContentDialog):
    def __init__(self, app):
        app.VERSION_STR = VERSION
        t = app.t
        super().__init__(app, t("menu.about"), "", [
            (t("settings.report_issue"), "secondary", app.report_issue),
            (t("common.ok"), "primary", None)], width=380)
        self.cv.bind("<Return>", lambda e: self._activate(1))

    def _body_h(self):
        return 240.4

    def _activate(self, i):
        # «ОК» is the default (Enter) button although it is drawn second
        return super()._activate(i)

    def render(self):
        super().render()
        app = self.app
        t = app.t
        x, y = self.px + 25, self.py + 1 + 64
        meta = _Meta(self.root, app)
        meta.geom(x, y, 330, 160)
        meta.lift()
        self.widgets.append(meta)
        links = [(t("settings.source_code"), REPO_URL, 0, 78),
                 (t("settings.release_notes"), f"{REPO_URL}/releases/tag/{RELEASE_TAG}", 0, 108.1),
                 ("GNU GPLv3", LICENSE_URL, text_width(t("settings.license"), 12.5) + 5.6, 138.2)]
        for label, url, lx, ly in links:
            lk = Link(self.root, label, 14, "link", bg="dialog", command=lambda u=url: app.open_url(u))
            lk.geom(x + lx, y + ly, lk.natural_width(), 18.2)
            lk.lift()
            self.widgets.append(lk)
