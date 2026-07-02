"""The sonnet display: one clickable widget per line, click = freeze."""

from __future__ import annotations

from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static

from ..engine import Line, Sonnet

FROZEN_MARK = "❄ "
PAD = "  "


class LineWidget(Static, can_focus=True):
    """A single sonnet line. Click / Enter / Space toggles freeze."""

    BINDINGS = [
        Binding("enter", "toggle", "Freeze/unfreeze", show=False),
        Binding("space", "toggle", "Freeze/unfreeze", show=False),
    ]

    class FreezeToggled(Message):
        def __init__(self, widget: "LineWidget"):
            self.widget = widget
            super().__init__()

    def __init__(self, line: Line):
        super().__init__()
        self.line = line
        self.refresh_text()

    def refresh_text(self):
        prefix = FROZEN_MARK if self.line.frozen else PAD
        # Rich Text, not str: loaded literal lines may contain [brackets]
        # that must never be parsed as markup.
        self.update(Text(prefix + self.line.text))
        self.set_class(self.line.frozen, "frozen")

    def on_click(self):
        self.action_toggle()

    def action_toggle(self):
        self.post_message(self.FreezeToggled(self))


class SonnetView(Vertical):
    """Renders a Sonnet as LineWidgets with blank-line spacers."""

    def __init__(self, sonnet: Sonnet):
        super().__init__(id="sonnet-view")
        self.sonnet = sonnet

    def compose(self):
        for line in self.sonnet.lines:
            if line.blank:
                yield Static("", classes="spacer")
            else:
                yield LineWidget(line)

    def refresh_lines(self):
        for widget in self.query(LineWidget):
            widget.refresh_text()

    async def set_sonnet(self, sonnet: Sonnet):
        self.sonnet = sonnet
        await self.remove_children()
        for line in sonnet.lines:
            if line.blank:
                await self.mount(Static("", classes="spacer"))
            else:
                await self.mount(LineWidget(line))

    def on_line_widget_freeze_toggled(self, event: LineWidget.FreezeToggled):
        line = event.widget.line
        line.frozen = not line.frozen
        event.widget.refresh_text()
