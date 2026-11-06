import json
from functools import cache, partial
from pathlib import Path

LANGUAGES = ("tr", "en", "fr", "de")


@cache
def messages(language):
    if language not in LANGUAGES:
        language = "en"
    return json.loads(Path(__file__).with_name(f"{language}.json").read_text(encoding="utf-8"))


def translate(section, key, language):
    return messages(language)[section][key]


def translator(section):
    return partial(translate, section)
