"""The main Textual application."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Header, Static

from ..engine import ComposeError, Composer, load_sonnet, save_sonnet
from .dialogs import (
    AboutScreen, HelpScreen, ManageWordsScreen, MessageScreen, PathScreen,
)
from .sonnet_view import SonnetView

SPINNER = "◐◓◑◒"


class ToasterApp(App):
    TITLE = "Presenting… Shakespeare In A Toaster"

    CSS = """
    #toolbar {
        height: 3;
        dock: top;
        background: $surface;
        padding: 0 1;
    }
    #toolbar Button { margin: 0 1 0 0; min-width: 14; }
    #sonnet-view {
        padding: 1 4;
        overflow-y: auto;
    }
    #sonnet-view LineWidget {
        height: 1;
        width: 100%;
    }
    #sonnet-view LineWidget:hover { background: $boost; }
    #sonnet-view LineWidget:focus { background: $accent 20%; }
    #sonnet-view LineWidget.frozen { color: $text-muted; text-style: italic; }
    #sonnet-view .spacer { height: 1; }
    #status { dock: bottom; height: 1; padding: 0 1; color: $text-muted; }

    ModalScreen { align: center middle; }
    .dialog {
        width: auto;
        max-width: 100;
        height: auto;
        max-height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    .dialog Button { margin: 1 1 0 0; }
    .dialog .buttons { height: auto; }
    .about Horizontal { width: auto; height: auto; }
    .about #portrait {
        width: auto;
        height: auto;
        margin-right: 2;
        color: black;
        background: white;
        padding: 0 1;
    }
    .about VerticalScroll { width: 46; height: 22; }
    .about VerticalScroll Static { width: 100%; }
    .manage { width: 100; }
    .manage #words { height: 20; }
    .form Select, .form Input { width: 60; }
    """

    BINDINGS = [
        ("n", "new_sonnet", "New sonnet"),
        ("r", "rewrite", "Rewrite"),
        ("s", "save", "Save"),
        ("o", "open", "Read"),
        ("m", "manage_words", "Manage words"),
        ("a", "about", "About"),
        ("question_mark", "help", "Help"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, composer: Composer):
        super().__init__()
        self.composer = composer
        self.sonnet = composer.new_sonnet()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="toolbar"):
            yield Button("✍  Rewrite", id="rewrite")
            yield Button("→💾 Save", id="save")
            yield Button("←💾 Read", id="read")
        yield SonnetView(self.sonnet)
        yield Static("", id="status")
        yield Footer()

    # -- helpers -------------------------------------------------------------

    @property
    def view(self) -> SonnetView:
        return self.query_one(SonnetView)

    def status(self, text: str):
        self.query_one("#status", Static).update(text)

    async def _compose_with_spinner(self, coro):
        """Run compose with a beach-ball nod in the status bar."""
        status = self.query_one("#status", Static)
        for ch in SPINNER:
            status.update(f"{ch} composing…")
            await asyncio.sleep(0.03)
        coro()
        status.update("")

    # -- actions ---------------------------------------------------------------

    async def action_new_sonnet(self):
        def make():
            self.sonnet = self.composer.new_sonnet()
        try:
            await self._compose_with_spinner(make)
        except ComposeError as exc:
            self.push_screen(MessageScreen(str(exc)))
            return
        await self.view.set_sonnet(self.sonnet)

    async def action_rewrite(self):
        try:
            await self._compose_with_spinner(
                lambda: self.composer.compose(self.sonnet))
        except ComposeError as exc:
            self.push_screen(MessageScreen(str(exc)))
            return
        self.view.refresh_lines()

    def action_save(self):
        def done(path: str | None):
            if not path:
                return
            try:
                save_sonnet(self.sonnet, Path(path).expanduser())
            except OSError as exc:
                self.push_screen(MessageScreen(f"Could not save: {exc}"))
                return
            self.status(f"Saved to {path}")
        self.push_screen(PathScreen("Save sonnet as:"), done)

    def action_open(self):
        def done(path: str | None):
            if not path:
                return
            try:
                text = Path(path).expanduser().read_text()
            except OSError as exc:
                self.push_screen(MessageScreen(f"Could not read: {exc}"))
                return
            self.sonnet = load_sonnet(text, self.composer.lexicon,
                                      self.composer.options.scheme)
            self.call_after_refresh(self._swap_view)
            self.status(f"Read {path}")
        self.push_screen(PathScreen("Open sonnet:"), done)

    async def _swap_view(self):
        await self.view.set_sonnet(self.sonnet)

    def action_manage_words(self):
        def done(changed: bool | None):
            if changed:
                self.status("Wordlist updated")
        self.push_screen(ManageWordsScreen(self.composer.lexicon), done)

    def action_about(self):
        self.push_screen(AboutScreen())

    def action_help(self):
        self.push_screen(HelpScreen())

    # -- toolbar ---------------------------------------------------------------

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "rewrite":
            await self.action_rewrite()
        elif event.button.id == "save":
            self.action_save()
        elif event.button.id == "read":
            self.action_open()
