"""docs/TEST_RESULTS.md from tests/test_set/results/latest.json."""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tests" / "test_set" / "results" / "latest.json"
OUT = ROOT / "docs" / "TEST_RESULTS.md"


def main() -> None:
    data = json.loads(SRC.read_text())
    results = data["results"]
    by_action = defaultdict(lambda: [0, 0])
    by_lang = defaultdict(lambda: [0, 0])
    by_source = defaultdict(lambda: [0, 0])
    for r in results:
        for bucket, key in (
            (by_action, r["expected_tool_action"]),
            (by_lang, r["language"]),
            (by_source, r["source"]),
        ):
            bucket[key][1] += 1
            bucket[key][0] += int(r["passed"])
    secs = [r["seconds"] for r in results if r["outcome"] == "ok"]
    lines = [
        "# Test set results",
        "",
        f"**{data['passed']} / {data['total']} passed.** "
        f"{data['total']} cases (100 from the synthetic pack plus 15 supplementary) run against the real model "
        f"on {data['started_at'][:10]}, each as its own employee; a case passes only when every check "
        f"for its scenario holds (tool used, refusal, citation theme, ERP status, nothing written). "
        f"Median turn {sorted(secs)[len(secs) // 2]:.1f} s."
        if secs
        else f"**{data['passed']} / {data['total']} passed.**",
        "",
        "## By scenario",
        "",
        "| Expected tool action | Passed | Total |",
        "|---|---|---|",
        *[f"| {k} | {v[0]} | {v[1]} |" for k, v in sorted(by_action.items())],
        "",
        "## By language and source",
        "",
        "| Group | Passed | Total |",
        "|---|---|---|",
        *[f"| language: {k} | {v[0]} | {v[1]} |" for k, v in sorted(by_lang.items())],
        *[f"| source: {k} | {v[0]} | {v[1]} |" for k, v in sorted(by_source.items())],
        "",
        "## Controls demonstrated",
        "",
        f"- Own records only: {by_action['Deny cross-employee read'][0]}/{by_action['Deny cross-employee read'][1]} cross-employee reads denied; "
        f"{sum(1 for r in results if r['outcome'] == 'denied_inactive')} inactive identities refused at sign-in.",
        f"- Confirmation before writes: {by_action['Prepare request'][0]}/{by_action['Prepare request'][1]} drafts stopped at the confirmation gate with nothing written.",
        f"- Prompt injection: {by_action['No write action'][0]}/{by_action['No write action'][1]} attached documents with embedded instructions produced no tool call and no write"
        f" (flagged as injection: {sum(1 for r in results if r['expected_tool_action'] == 'No write action' and r['response'] and 'injection_suspected' in r['response']['flags'])}"
        f" of {sum(1 for r in results if r['expected_tool_action'] == 'No write action' and r['response'])} that reached the assistant;"
        f" the rest were inactive identities refused at sign-in).",
        f"- Citations: {by_action['Answer policy with citation'][0]}/{by_action['Answer policy with citation'][1]} policy answers carried a matching citation.",
        f"- Refusals: {by_action['Refuse unsupported answer'][0]}/{by_action['Refuse unsupported answer'][1]} unanswerable questions refused without citations.",
        "",
        "## Failures",
        "",
    ]
    fails = [r for r in results if not r["passed"]]
    if not fails:
        lines.append("None.")
    for r in fails:
        bad = [k for k, v in r["checks"].items() if not v]
        ans = (
            (r["response"] or {})
            .get("answer", r.get("note", ""))[:160]
            .replace("\n", " ")
        )
        lines.append(
            f"- **{r['id']}** ({r['employee_id']}, {r['language']}) {r['expected_tool_action']}: failed {bad}. Answer: {ans}"
        )
    lines += [
        "",
        "## All cases",
        "",
        "| Case | Employee | Lang | Expected action | Outcome | Pass | Tools | Citations | Flags | s |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        resp = r["response"] or {}
        tools = ", ".join(f"{n}:{s}" for n, s in resp.get("tool_calls", []))
        lines.append(
            f"| {r['id']} | {r['employee_id']} | {r['language']} | {r['expected_tool_action']} | {r['outcome']} | "
            f"{'pass' if r['passed'] else 'FAIL'} | {tools} | {', '.join(resp.get('citations', []))} | {', '.join(resp.get('flags', []))} | {r['seconds']} |"
        )
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT} ({data['passed']}/{data['total']})")


if __name__ == "__main__":
    if not SRC.exists():
        sys.exit("no results yet: run `pdm run test-set` first")
    main()
