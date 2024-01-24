import webbrowser

from .. import __version__ as APP_VERSION

APP_TITLE: str = "SQC"
APP_COPY: str = "Copyright &copy; 2022-2024 HEPHY"
APP_LICENSE: str = "This software is licensed under the GNU General Public License v3.0"
APP_DECRIPTION: str = """Sensor Quality Control (SQC) characterises a sample of
sensors from each batch delivered by the producer and ensures that they
fully satisfy the specifications so they can be used to build modules for
the CMS Tracker."""
APP_CONTENTS_URL: str = "https://hephy-dd.github.io/sqc/"
APP_GITHUB_URL: str = "https://github.com/hephy-dd/sqc"


def aboutMessage() -> str:
    """Returns a RichText formatted about message for the application."""
    return f"<h1>{APP_TITLE}</h1><p>Version {APP_VERSION}</p><p>{APP_DECRIPTION}</p><p>{APP_COPY}</p><p>{APP_LICENSE}</p>"


def showContents() -> None:
    """Opens contents URL in default web browser."""
    try:
        webbrowser.open(APP_CONTENTS_URL)
    except Exception:
        ...

def showGithub() -> None:
    """Opens Github URL in default web browser."""
    try:
        webbrowser.open(APP_GITHUB_URL)
    except Exception:
        ...
