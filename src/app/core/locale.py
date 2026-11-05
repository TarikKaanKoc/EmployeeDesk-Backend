"""Language handling for a bilingual assistant.

Detection is by script: a message whose letters are mostly Arabic is
Arabic, otherwise English. Digits, punctuation and employee ids do not
count. A client may pass an explicit language and override this.
"""

import re
import unicodedata

from src.app.database.enums import Language

_ARABIC = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
_LATIN = re.compile(r"[A-Za-z]")


def detect(text: str) -> Language:
    arabic = len(_ARABIC.findall(text))
    latin = len(_LATIN.findall(text))
    if arabic == 0 and latin == 0:
        return Language.en
    return Language.ar if arabic >= latin else Language.en


def normalise_arabic(text: str) -> str:
    """Fold the usual Arabic variants so keyword search matches: alef
    forms, taa marbuta / haa, yaa / alef maqsura; strip tashkeel."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ً-ْـ]", "", text)
    text = re.sub(r"[آأإ]", "ا", text)
    text = text.replace("ة", "ه").replace("ى", "ي")
    return text
