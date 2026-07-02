"""TUI tests via Textual's pilot harness."""

import random

import pytest

from toaster.engine import Composer, Lexicon, Options
from toaster.tui.app import ToasterApp
from toaster.tui.sonnet_view import LineWidget


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    lexicon = Lexicon.load_pristine()
    return ToasterApp(Composer(lexicon, random.Random(1), Options()))


async def test_renders_fourteen_lines(app):
    async with app.run_test(size=(100, 40)):
        assert len(app.query(LineWidget)) == 14
        for w in app.query(LineWidget):
            assert w.line.text


async def test_click_freezes_line(app):
    async with app.run_test(size=(100, 40)) as pilot:
        first = list(app.query(LineWidget))[0]
        assert not first.line.frozen
        await pilot.click(first)
        assert first.line.frozen
        assert first.has_class("frozen")
        await pilot.click(first)
        assert not first.line.frozen


async def test_rewrite_respects_frozen(app):
    async with app.run_test(size=(100, 40)) as pilot:
        widgets = list(app.query(LineWidget))
        frozen, partner = widgets[0], widgets[2]  # both 'A' rhyme group
        await pilot.click(frozen)
        frozen_text = frozen.line.text
        await pilot.press("r")
        await pilot.pause()
        assert frozen.line.text == frozen_text
        assert partner.line.end_word.vowel == frozen.line.end_word.vowel


async def test_new_sonnet_replaces_lines(app):
    async with app.run_test(size=(100, 40)) as pilot:
        before = app.sonnet.text
        await pilot.press("n")
        await pilot.pause()
        assert app.sonnet.text != before
        assert len(app.query(LineWidget)) == 14


async def test_save_and_open_roundtrip(app, tmp_path):
    path = tmp_path / "sonnet.out"
    async with app.run_test(size=(100, 40)) as pilot:
        original = app.sonnet.text
        await pilot.press("s")
        await pilot.pause()
        from textual.widgets import Input
        field = app.screen.query_one("#path", Input)
        field.value = str(path)
        await pilot.press("enter")
        await pilot.pause()
        assert path.read_text().strip() == original.strip()

        await pilot.press("n")
        await pilot.pause()
        assert app.sonnet.text != original

        await pilot.press("o")
        await pilot.pause()
        field = app.screen.query_one("#path", Input)
        field.value = str(path)
        await pilot.press("enter")
        await pilot.pause()
        assert app.sonnet.text.strip() == original.strip()


async def test_manage_words_add_persists(app, tmp_path):
    from textual.widgets import Input, Select
    from toaster.engine import user_lexicon_path

    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.press("m")
        await pilot.pause()
        await pilot.click("#add")
        await pilot.pause()
        app.screen.query_one("#word", Input).value = "zorkmid"
        app.screen.query_one("#foot", Select).value = 3      # trochee
        app.screen.query_one("#vowel", Select).value = "i"
        app.screen.query_one("#consonant", Select).value = "d"
        await pilot.click("#ok")
        await pilot.pause()
        assert app.composer.lexicon.lookup("zorkmid") is not None
        assert user_lexicon_path().exists()

        fresh = Lexicon.load()
        assert fresh.lookup("zorkmid") is not None


async def test_open_literal_with_markup_brackets_no_crash(app, tmp_path):
    """Loaded literal lines containing [brackets] must not parse as markup."""
    from textual.widgets import Input
    path = tmp_path / "weird.out"
    path.write_text("xyzzy [/bold] not a real closing tag\n")
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.press("o")
        await pilot.pause()
        app.screen.query_one("#path", Input).value = str(path)
        await pilot.press("enter")
        await pilot.pause()
        first = list(app.query(LineWidget))[0]
        assert first.line.frozen
        assert "[/bold]" in first.line.text


async def test_open_non_utf8_shows_message(app, tmp_path):
    from textual.widgets import Input
    from toaster.tui.dialogs import MessageScreen
    path = tmp_path / "binary.out"
    path.write_bytes(b"\xff\xfe\x00garbage\x9c")
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.press("o")
        await pilot.pause()
        app.screen.query_one("#path", Input).value = str(path)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, MessageScreen)


async def test_change_word_with_stray_code_no_crash(app):
    """'adamant' carries the off-legend consonant 'o'; Change must not crash."""
    from toaster.tui.dialogs import ManageWordsScreen, WordFormScreen
    from textual.widgets import DataTable
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.press("m")
        await pilot.pause()
        assert isinstance(app.screen, ManageWordsScreen)
        table = app.screen.query_one(DataTable)
        cls_id, idx = next(
            (c, i) for c, words in app.composer.lexicon.classes.items()
            for i, w in enumerate(words) if w.text == "adamant")
        row = table.get_row_index(f"{cls_id}:{idx}")
        table.move_cursor(row=row)
        await pilot.click("#change")
        await pilot.pause()
        assert isinstance(app.screen, WordFormScreen)


async def test_help_and_about_open(app):
    from toaster.tui.dialogs import AboutScreen, HelpScreen
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, AboutScreen)
