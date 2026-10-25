"""GlowDL entry point.

Usage:
    python -m app.main                 # launch the desktop GUI
    python -m app.main --diagnose      # print an environment report
    python -m app.main --cli URL       # headless download
"""

from __future__ import annotations

import os
import sys


def _bootstrap_ssl() -> None:
    """Make HTTPS verification work in frozen builds and python.org installs.

    Some Windows/macOS Python distributions ship without a CA bundle, which
    shows up as ``CERTIFICATE_VERIFY_FAILED`` inside yt-dlp. Prefer certifi
    (bundled with the app), then fall back to the OS bundle so an intercepting
    proxy CA trusted by the OS can still verify.
    """
    current = os.environ.get("SSL_CERT_FILE", "")
    if current and os.path.exists(current):
        return

    bundle = ""
    try:
        import certifi

        candidate = certifi.where()
        if candidate and os.path.exists(candidate):
            bundle = candidate
    except Exception:
        pass

    if not bundle:
        for candidate in (
            "/etc/ssl/cert.pem",  # macOS system roots
            "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
            "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/Fedora
            "/usr/local/etc/openssl/cert.pem",  # Homebrew OpenSSL
        ):
            if os.path.exists(candidate):
                bundle = candidate
                break

    if bundle:
        os.environ.setdefault("SSL_CERT_FILE", bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)


def _bootstrap_core() -> None:
    """Prefer a user-updated yt-dlp core over the bundled one."""
    try:
        from app.core import updater

        core = updater.activate_user_core()
        if core:
            os.environ["GLOWDL_CORE"] = str(core)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _bootstrap_ssl()
    _bootstrap_core()

    if "--cli" in argv or "--diagnose" in argv or "--version" in argv:
        from app.cli import main as cli_main

        return cli_main(argv)

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app import APP_ID, APP_NAME, APP_NAME_ZH, __version__
    from app.core.settings import Settings
    from app.ui import icons, theme
    from app.ui.main_window import MainWindow

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv[:1] + argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(f"{APP_NAME} · {APP_NAME_ZH}")
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(icons.app_icon())

    settings = Settings.load()
    theme.apply_theme(app, settings.theme)

    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
