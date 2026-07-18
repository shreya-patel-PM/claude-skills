"""
PM Copilot — programmatic self-check for the Writer's output.

This is the create-user-story skill's Phase 4 checklist turned into code:
structural rules are HARD FAILURES (the draft is rejected before the human
gate), style rules are WARNINGS (surfaced at the gate for the human to
judge). Reject-over-repair: a failing draft is never silently fixed.
"""
import json
import re

BARE_ROLES = re.compile(r"^(a |an |the )?(user|admin)\b", re.IGNORECASE)
AC_ID = re.compile(r"^(AC|ACE)(\d+)$")
FUTURE_HINT = re.compile(r"\bwill\b|\bwill not\b|^no ", re.IGNORECASE)


def strip_fences(text: str) -> str:
    """Standard fence-stripping (same guard used across the Make agents)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # If the model added preamble despite instructions, cut to the outermost object.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return text


def parse_story(raw: str):
    """Parse the Writer's raw output into a story dict. Raises ValueError."""
    cleaned = strip_fences(raw)
    try:
        story = json.loads(cleaned)
    except json.JSONDecodeError:
        # Attempt repair: CrewAI sometimes truncates long JSON.
        # Try closing unclosed arrays and objects.
        repaired = _try_repair_json(cleaned)
        if repaired is not None:
            story = repaired
        else:
            raise ValueError(
                f"Writer output is not valid JSON and could not be repaired. "
                f"First 200 chars: {cleaned[:200]}"
            )
    if not isinstance(story, dict):
        raise ValueError("Writer output is not a JSON object.")
    return story


def _try_repair_json(text: str):
    """Best-effort repair of truncated JSON by closing open brackets."""
    # Count unmatched brackets (outside strings)
    opens = 0
    open_sq = 0
    in_string = False
    escape = False
    last_good = 0  # track last position after a complete value

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            if not in_string:
                last_good = i + 1
            continue
        if in_string:
            continue
        if ch == '{': opens += 1
        elif ch == '}':
            opens -= 1
            last_good = i + 1
        elif ch == '[': open_sq += 1
        elif ch == ']':
            open_sq -= 1
            last_good = i + 1

    if opens <= 0 and open_sq <= 0:
        return None  # Not a truncation issue

    # If we ended inside a string, truncate to the last complete value
    if in_string and last_good > 0:
        text = text[:last_good]
        # Recount after truncation
        opens = 0
        open_sq = 0
        in_string = False
        escape = False
        for ch in text:
            if escape: escape = False; continue
            if ch == '\\' and in_string: escape = True; continue
            if ch == '"': in_string = not in_string; continue
            if in_string: continue
            if ch == '{': opens += 1
            elif ch == '}': opens -= 1
            elif ch == '[': open_sq += 1
            elif ch == ']': open_sq -= 1

    # Strip trailing comma or incomplete key/value
    text = re.sub(r',\s*$', '', text.rstrip())
    text = re.sub(r':\s*$', ': null', text)

    # Close brackets
    text += ']' * max(open_sq, 0)
    text += '}' * max(opens, 0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Second attempt: more aggressive — cut back to the last } or ]
        # and try again
        for cutpoint in range(len(text) - 1, 0, -1):
            if text[cutpoint] in ('}', ']', '"'):
                attempt = text[:cutpoint + 1]
                # Recount and close
                o, s, ins, esc = 0, 0, False, False
                for ch in attempt:
                    if esc: esc = False; continue
                    if ch == '\\' and ins: esc = True; continue
                    if ch == '"': ins = not ins; continue
                    if ins: continue
                    if ch == '{': o += 1
                    elif ch == '}': o -= 1
                    elif ch == '[': s += 1
                    elif ch == ']': s -= 1
                attempt += ']' * max(s, 0) + '}' * max(o, 0)
                try:
                    return json.loads(attempt)
                except json.JSONDecodeError:
                    continue
        return None


def validate_story(story: dict):
    """Return (errors, warnings). Errors block the gate; warnings display at it."""
    errors, warnings = [], []

    # ── structural: hard failures ────────────────────────────────────────
    for key in ("title", "story", "acs"):
        if key not in story:
            errors.append(f"Missing required key: '{key}'")
    if errors:
        return errors, warnings

    if not isinstance(story["acs"], list) or not story["acs"]:
        errors.append("'acs' must be a non-empty list.")
        return errors, warnings

    happy_ids, edge_ids, seen_edge = [], [], False
    for i, ac in enumerate(story["acs"]):
        loc = f"acs[{i}]"
        for key in ("id", "name", "given", "when", "thens"):
            if key not in ac:
                errors.append(f"{loc}: missing '{key}'")
        if any(k not in ac for k in ("id", "name", "given", "when", "thens")):
            continue

        m = AC_ID.match(ac["id"])
        if not m:
            errors.append(f"{loc}: id '{ac['id']}' is not AC[n] or ACE[n].")
            continue
        prefix, num = m.group(1), int(m.group(2))
        if prefix == "AC":
            if seen_edge:
                errors.append(
                    f"{loc}: happy-path {ac['id']} appears after an ACE — "
                    "happy path must come first."
                )
            happy_ids.append(num)
        else:
            seen_edge = True
            edge_ids.append(num)

        if not isinstance(ac["thens"], list) or not ac["thens"]:
            errors.append(f"{loc}: 'thens' must be a non-empty bullet list.")

        # ── style: warnings ─────────────────────────────────────────────
        if BARE_ROLES.match(ac["given"].strip()):
            warnings.append(
                f"{ac['id']}: GIVEN uses a bare role ('user'/'admin') — "
                "name the specific persona."
            )
        if " and " in ac["when"].lower():
            warnings.append(
                f"{ac['id']}: WHEN contains 'and' — likely two ACs."
            )
        for b, bullet in enumerate(ac.get("thens", []) or []):
            if isinstance(bullet, str) and not FUTURE_HINT.search(bullet):
                warnings.append(
                    f"{ac['id']} bullet {b + 1}: not obviously future tense "
                    "('The system will...')."
                )

    for label, ids in (("AC", happy_ids), ("ACE", edge_ids)):
        if ids and ids != list(range(1, len(ids) + 1)):
            errors.append(
                f"{label} numbering is not sequential from 1: {ids}"
            )
    if len(happy_ids) > 15:
        errors.append(
            f"{len(happy_ids)} happy-path ACs (> 15) — the skill requires "
            "splitting the story."
        )
    elif len(happy_ids) > 5:
        warnings.append(
            f"{len(happy_ids)} happy-path ACs — typical stories have 2-4. "
            "Check whether scope has expanded beyond the ask."
        )

    if "assumptions_carried" not in story:
        warnings.append(
            "No 'assumptions_carried' — fine only if the Analyst flagged none."
        )
    return errors, warnings


def render_markdown(story: dict) -> str:
    """Render the story dict in the skill's document shape for the human gate."""
    lines = [
        f"# {story['title']}",
        "",
        f"**Story:** {story['story']}",
        "",
        "## Acceptance Criteria",
        "",
    ]
    for ac in story["acs"]:
        lines.append(f"### {ac['id']}- {ac['name']}")
        lines.append(f"**GIVEN** {ac['given']}")
        lines.append(f"**WHEN** {ac['when']}")
        lines.append("**THEN** the following should be true:")
        lines.extend(f"- {b}" for b in ac["thens"])
        lines.append("")
    carried = story.get("assumptions_carried") or []
    if carried:
        lines.append("## Assumptions carried for PM confirmation")
        lines.extend(f"- {a}" for a in carried)
        lines.append("")
    return "\n".join(lines)