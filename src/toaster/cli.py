"""Command-line entry point: TUI by default, --text for pipe mode."""

from __future__ import annotations

import argparse
import random
import sys

from .engine import Composer, Lexicon, Options


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="shakespeare-toaster",
        description="Presenting… Shakespeare In A Toaster — the 1989 Mac "
                    "sonnet generator, faithfully ported.")
    p.add_argument("--text", nargs="?", const=1, type=int, metavar="N",
                   help="print N sonnets to stdout instead of running the TUI")
    p.add_argument("--seed", type=int, help="RNG seed for reproducible output")
    p.add_argument("--scheme", default=None,
                   help='rhyme scheme string (default "ABAB CDCD EFEF GG")')
    p.add_argument("--line-length", type=int, default=None,
                   help="metrical positions per line (default 10)")
    p.add_argument("--no-repeats", action="store_true",
                   help="modern fix: never repeat a word within a sonnet")
    p.add_argument("--pristine", action="store_true",
                   help="ignore the user-edited wordlist; use the 1989 original")
    return p


def make_composer(args) -> Composer:
    lexicon = Lexicon.load(pristine_only=args.pristine)
    opts = Options()
    if args.scheme:
        opts.scheme = args.scheme
    if args.line_length:
        opts.line_length = args.line_length
    opts.no_repeats = args.no_repeats
    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    return Composer(lexicon, rng, opts)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.text is not None:
        composer = make_composer(args)
        for i in range(args.text):
            if i:
                print("\n" + "~" * 40 + "\n")
            print(composer.new_sonnet().text)
        return 0
    from .tui.app import ToasterApp
    ToasterApp(make_composer(args)).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
