"""Modal dialogs: Help, About, save/open prompts, and the wordlist editor."""

from __future__ import annotations

from importlib import resources

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from ..engine import Lexicon, LexiconError, user_lexicon_path
from ..engine.rhyme import (
    CONSONANT_LEGEND, FOOT_LEGEND, VOWEL_LEGEND,
    consonant_label, vowel_label,
)

HELP_TEXT = """\
[b]Presenting… Shakespeare In A Toaster[/b]

  ✍   Rewrite current sonnet   [dim](r)[/dim]
  →💾  Save to disk             [dim](s)[/dim]
  ←💾  Read from disk           [dim](o)[/dim]

"New Sonnet…" generates a new sonnet [dim](n)[/dim]
"Manage Words…" allows editing the wordlist [dim](m)[/dim]

[b]Click to "freeze" a line[/b] — frozen lines survive rewrites,
so freeze the ones you like and rewrite the rest.

Everything else is pretty much what you'd expect!
"""

CREDITS = """\
[b]Shakespeare v1.0[/b]
© 1989–1991 by Bob Schumaker, all rights reserved.

Rewritten for the Macintosh by Bob Schumaker
Overhauled by /rich $alz
Composer code written by Chris Wilbur
Thanks to Paul DuBois for the original TransSkel
(now much modified). Portions © by THINK
Technologies, Inc.

No warranties expressed or implied. The suitability
of this product for any purpose in not gauranteed.

Python port, 2026 — a preservation project.
"""


class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(HELP_TEXT, markup=True)
            yield Button("OK", variant="primary", id="ok")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss()


class AboutScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        portrait = resources.files("toaster.data").joinpath("portrait.txt").read_text()
        with Vertical(classes="dialog about"):
            with Horizontal():
                yield Static(portrait, id="portrait")
                yield VerticalScroll(Static(CREDITS, markup=True))
            yield Button("OK", variant="primary", id="ok")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss()


class MessageScreen(ModalScreen):
    """Simple message/error dialog."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(self.message)
            yield Button("OK", variant="primary", id="ok")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss()


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, message: str, action_label: str = "OK"):
        super().__init__()
        self.message = message
        self.action_label = action_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(self.message)
            with Horizontal(classes="buttons"):
                yield Button(self.action_label, variant="error", id="confirm")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "confirm")

    def action_cancel(self):
        self.dismiss(False)


class PathScreen(ModalScreen[str | None]):
    """Prompt for a file path (save / open)."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, default: str = "sonnet.out"):
        super().__init__()
        self.title_text = title
        self.default = default

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.title_text)
            yield Input(value=self.default, id="path")
            with Horizontal(classes="buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_input_submitted(self, event: Input.Submitted):
        self.dismiss(event.value or None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "ok":
            self.dismiss(self.query_one("#path", Input).value or None)
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class WordFormScreen(ModalScreen["tuple[str, int, str, str] | None"]):
    """Add/Change a word: text + foot class + vowel + consonant."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, word: str = "", cls_id: int | None = None,
                 vowel: str | None = None, consonant: str | None = None):
        super().__init__()
        self.form_title = title
        self.initial = (word, cls_id, vowel, consonant)

    def compose(self) -> ComposeResult:
        word, cls_id, vowel, consonant = self.initial
        with Vertical(classes="dialog form"):
            yield Label(self.form_title)
            yield Label("Word")
            yield Input(value=word, id="word")
            yield Label("Scans like")
            yield Select(((label, c) for c, label in FOOT_LEGEND.items()),
                         value=cls_id if cls_id is not None else Select.NULL,
                         prompt="choose a foot…", id="foot")
            # The 1989 lexicon contains a few off-legend codes (adamant='o');
            # include the word's current code as an option so Change never
            # crashes on a value the Select doesn't know.
            vowel_opts = [(f"{code}  {label}", code)
                          for code, label in VOWEL_LEGEND.items()]
            if vowel is not None and vowel not in VOWEL_LEGEND:
                vowel_opts.append((f"{vowel}  {vowel_label(vowel)}", vowel))
            cons_opts = [(f"{code}  {label}" if code != " " else label, code)
                         for code, label in CONSONANT_LEGEND.items()]
            if consonant is not None and consonant not in CONSONANT_LEGEND:
                cons_opts.append(
                    (f"{consonant}  {consonant_label(consonant)}", consonant))
            yield Label("Vowel type")
            yield Select(vowel_opts,
                         value=vowel if vowel is not None else Select.NULL,
                         prompt="choose a vowel sound…", id="vowel")
            yield Label("Consonant")
            yield Select(cons_opts,
                         value=consonant if consonant is not None else Select.NULL,
                         prompt="choose a final consonant…", id="consonant")
            with Horizontal(classes="buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id != "ok":
            self.dismiss(None)
            return
        word = self.query_one("#word", Input).value.strip()
        foot = self.query_one("#foot", Select).value
        vowel = self.query_one("#vowel", Select).value
        consonant = self.query_one("#consonant", Select).value
        if not word or Select.NULL in (foot, vowel, consonant):
            self.app.push_screen(MessageScreen(
                "All fields are required: word, foot, vowel, consonant."))
            return
        self.dismiss((word, foot, vowel, consonant))

    def action_cancel(self):
        self.dismiss(None)


class ManageWordsScreen(ModalScreen[bool]):
    """The Manage Wordlist dialog. Dismisses True if the lexicon changed."""

    BINDINGS = [("escape", "close", "Close")]

    def __init__(self, lexicon: Lexicon):
        super().__init__()
        self.lexicon = lexicon
        self.changed = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog manage"):
            yield Label("Manage Wordlist", id="manage-title")
            yield DataTable(id="words", cursor_type="row")
            with Horizontal(classes="buttons"):
                yield Button("Add", id="add")
                yield Button("Change", id="change")
                yield Button("Delete", variant="error", id="delete")
                yield Button("Restore original", id="restore")
                yield Button("Close", variant="primary", id="close")

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns("Word", "Scans like", "Vowel type", "Consonant")
        self.reload_table()

    def reload_table(self):
        table = self.query_one(DataTable)
        table.clear()
        for cls_id, words in self.lexicon.classes.items():
            if cls_id not in FOOT_LEGEND:
                continue
            for idx, w in enumerate(words):
                table.add_row(
                    w.text,
                    FOOT_LEGEND[cls_id],
                    vowel_label(w.vowel),
                    consonant_label(w.consonant),
                    key=f"{cls_id}:{idx}",
                )

    def selected(self) -> tuple[int, int] | None:
        table = self.query_one(DataTable)
        if table.row_count == 0:
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        cls_id, idx = str(row_key.value).split(":")
        return int(cls_id), int(idx)

    def _persist(self):
        self.lexicon.save_user_copy()
        self.changed = True
        self.reload_table()

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "close":
            self.dismiss(self.changed)
        elif bid == "add":
            def done(result):
                if result:
                    try:
                        self.lexicon.add_word(*result)
                    except LexiconError as exc:
                        self.app.push_screen(MessageScreen(str(exc)))
                        return
                    self._persist()
            self.app.push_screen(WordFormScreen("Add word"), done)
        elif bid == "change":
            sel = self.selected()
            if sel is None:
                return
            cls_id, idx = sel
            w = self.lexicon.word_at(cls_id, idx)

            def done(result):
                if result:
                    text, new_cls, vowel, consonant = result
                    try:
                        self.lexicon.change_word(
                            cls_id, idx, text, new_cls, vowel, consonant)
                    except LexiconError as exc:
                        self.app.push_screen(MessageScreen(str(exc)))
                        return
                    self._persist()
            self.app.push_screen(
                WordFormScreen("Change word", w.text, cls_id, w.vowel,
                               w.consonant), done)
        elif bid == "delete":
            sel = self.selected()
            if sel is None:
                return
            cls_id, idx = sel
            self.lexicon.delete_word(cls_id, idx)
            self._persist()
        elif bid == "restore":
            def done(confirmed):
                if confirmed:
                    user_lexicon_path().unlink(missing_ok=True)
                    fresh = Lexicon.load_pristine()
                    self.lexicon.classes = fresh.classes
                    self.lexicon._index = None
                    self.changed = True
                    self.reload_table()
            self.app.push_screen(ConfirmScreen(
                "Discard all wordlist edits and restore the original "
                "1989 wordlist?", "Restore"), done)

    def action_close(self):
        self.dismiss(self.changed)
