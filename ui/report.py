"""«Сообщить о проблеме»: a GitHub issue with the version, Windows and the language (remark 112;
mixed into ``ui.app.App``)."""
from __future__ import annotations

import logging

from core.version import REPO_URL

log = logging.getLogger(__name__)


class ReportMixin:
    def report_issue(self):
        """«Сообщить о проблеме» (stage 5): a new GitHub issue with the app version, Windows and the language
        already filled in (English body, no title — user decision; remark 88: no graphics card / DirectX 12)."""
        self.open_url(self.issue_url())

    def issue_url(self) -> str:
        import urllib.parse
        from ui import platform_win as pw
        body = self.t("issue.body", version=self.VERSION_STR, windows=pw.windows_version(),
                      lang=self.i18n.lang).replace("\\n", "\n")
        url = f"{REPO_URL}/issues/new?" + urllib.parse.urlencode({"body": body})
        return url[:2000]
