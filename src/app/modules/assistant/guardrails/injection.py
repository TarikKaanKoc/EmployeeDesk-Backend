"""Spot text that tries to instruct the assistant rather than ask it.

Heuristic by design: the patterns catch the common shapes in both
languages (override the rules, change identity, reveal the prompt, do a
write). A hit does not block the turn. It is recorded, the model is told
the content is data, and the output check later verifies that no tool
was driven by it. The real defence is structural: tools take the caller
from the session and writes need a separate confirmation call.
"""

import re
from dataclasses import dataclass
from typing import List

_PATTERNS = [
    (
        r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instruction|rule|prompt|polic|guideline)",
        "override_instructions",
    ),
    (
        r"\b(you are now|act as|pretend (to be|you are)|new persona|developer mode|jailbreak)\b",
        "identity_change",
    ),
    (
        r"\b(reveal|print|show|repeat)\b.{0,30}\b(system prompt|hidden|secret|instructions)\b",
        "prompt_extraction",
    ),
    (
        r"\b(bypass|skip|disable|turn off)\b.{0,30}\b(access|check|control|verification|confirmation|guardrail)",
        "bypass_controls",
    ),
    (
        r"\b(alter|modify|change|update|delete|approve)\b.{0,30}\b(record|balance|request|database|table)\b",
        "unauthorised_write",
    ),
    (r"\b(embedded|hidden) (test )?instruction\b", "embedded_instruction"),
    (
        r"\b(as|for) (employee )?E1\d{3}\b.{0,30}\b(show|get|read|submit|approve)",
        "impersonation",
    ),
    (r"(تجاهل|انس|تخط)\s.{0,30}(التعليمات|القواعد|السياسة)", "override_instructions"),
    (r"(أنت الآن|تصرف ك|تظاهر)", "identity_change"),
    (r"(اكشف|اعرض|اطبع)\s.{0,30}(التعليمات|المخفية|السرية)", "prompt_extraction"),
    (r"(تجاوز|تخط|عطل)\s.{0,30}(الصلاحيات|التحقق|التأكيد|الضوابط)", "bypass_controls"),
    (
        r"(عدل|غير|احذف|وافق على)\s.{0,30}(السجل|الرصيد|الطلب|قاعدة البيانات)",
        "unauthorised_write",
    ),
]
_COMPILED = [(re.compile(p, re.I | re.S), name) for p, name in _PATTERNS]


@dataclass
class InjectionReport:
    source: str
    matches: List[str]

    @property
    def suspected(self) -> bool:
        return bool(self.matches)


def scan(text: str, *, source: str) -> InjectionReport:
    found: List[str] = []
    for pattern, name in _COMPILED:
        if pattern.search(text) and name not in found:
            found.append(name)
    return InjectionReport(source=source, matches=found)
