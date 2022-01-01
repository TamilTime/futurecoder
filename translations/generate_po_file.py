import json
import re
import urllib.parse
from collections import defaultdict
from pathlib import Path
from textwrap import indent, dedent

from littleutils import group_by_key
from polib import POEntry, POFile

from core import linting
from core import translation as t
from core.text import pages, get_predictions, chapters
from core.utils import markdown_codes

code_blocks = defaultdict(dict)
code_bits = defaultdict(set)
page_link = ""

po = POFile(wrapwidth=120)


def entry(msgid, msgstr, comment=""):
    po.append(
        POEntry(
            msgid=msgid,
            msgstr=msgstr,
            comment=comment,
        )
    )


def main():
    global page_link
    for page_slug, page in pages.items():
        page_link = "https://futurecoder.io/course/#" + page_slug
        entry(t.page_title(page_slug), page.raw_title, page_link)

        for step_name, text in zip(page.step_names, page.step_texts(raw=True)):
            step_msgid = t.step(page_slug, step_name)
            text_entry(t.step_text(page_slug, step_name), text)
            if step_name == "final_text":
                continue

            step = page.get_step(step_name)
            comments = [search_link(step_msgid)]
            for message_step in step.messages:
                msgid = t.message_step_text(step, message_step)
                text = message_step.raw_text
                text_entry(msgid, text, comments)

            for i, hint in enumerate(step.hints):
                msgid = t.hint(step, i)
                text_entry(msgid, hint, comments)

            if step.auto_translate_program:
                for _, node_text in t.get_code_bits(step.program):
                    code_bits[node_text].add(f"{search_link(step_msgid)}\n\n{step.program}")
            else:
                entry(t.step_program(step), step.program, search_link(step_msgid))

            if step.translate_output_choices:
                output_prediction_choices = get_predictions(step)["choices"] or []
                for i, choice in enumerate(output_prediction_choices[:-1]):
                    if (
                        not re.search(r"[a-zA-Z]", choice)
                        or choice in ("True", "False")
                    ):
                        continue
                    entry(t.prediction_choice(step, i), choice, search_link(step_msgid))

    for code_bit, comments in code_bits.items():
        entry(
            t.code_bit(code_bit),
            code_bit,
            "\n\n------\n\n".join(sorted(comments)),
        )

    for message_cls, message_format in linting.MESSAGES.items():
        entry(t.pyflakes_message(message_cls), message_format.strip())

    for chapter in chapters:
        entry(t.chapter_title(chapter["slug"]), chapter["title"])

    entry(
        "output_predictions.Error",
        "Error",
        "Special choice at the end of all output prediction multiple choice questions",
    )

    po.sort(key=lambda e: e.msgid)
    po.save(str(Path(__file__).parent / "english.po"))

    t.codes_path.write_text(json.dumps(code_blocks))


def text_entry(msgid, text, comments=()):
    codes = [c for c in markdown_codes(text) if not c["no_auto_translate"]]
    codes_grouped = group_by_key(codes, "text")
    code_comments = []
    comments = set(comments)
    for i, (code_text, group) in sorted(
        enumerate(codes_grouped.items()),
        key=lambda it: -len(it[1][0]),
    ):
        code_text = code_text.rstrip()
        code = group[0]["code"]
        assert code.startswith(dedent(code_text))
        code_blocks[msgid][i] = dict(code=code, code_text_length=len(dedent(code_text)))

        code_text = indent(code_text, "    ")
        assert code_text in text
        text = text.replace(code_text, f"__code{i}__")
        assert code_text not in text
        code_comments.append(f"    # __code{i}__:\n{code_text}")

        for _, node_text in t.get_code_bits(code):
            code_bits[node_text].add(f"{search_link(msgid)}\n\n{code_text}")
            comments.add(search_link(t.code_bit(node_text)))

    comment = "\n\n".join([page_link, *code_comments, *sorted(comments)])
    entry(msgid, text, comment)


def search_link(msgid):
    return (
        "https://poeditor.com/projects/view_terms?id=490053&search="
        + urllib.parse.quote_plus(msgid)
    )


main()
