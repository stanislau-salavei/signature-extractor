"""Version of the application — the one place it is written (stage 6).

The installer build (``packaging/build.py``) reads ``VERSION`` from here; a test build with another version
(``build.py --version 1.0.1``) rewrites this file only in the CI checkout.  Git tag = ``"v" + VERSION``
(remark 84: ``v1.0``, not ``v1.0.0``); next versions: ``v1.0.1`` for fixes, ``v1.1`` for features (D8)."""
VERSION = "1.0"
RELEASE_TAG = "v" + VERSION
