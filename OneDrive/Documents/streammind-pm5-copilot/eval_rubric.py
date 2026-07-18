#!/usr/bin/env python3
"""
PM Copilot — LLM-as-judge rubric scorer.

Scores a crew-generated story against a golden reference on 5 dimensions:
  clarity, testability, scope_fidelity, completeness, grounding

Usage:
    # Score a single crew output against a golden entry
    python eval_rubric.py --golden evals/golden_asks.json --entry G01 --crew-output output.json

    # Mock run: score the golden reference against itself (ceiling check)
    python eval_rubric.py --golden evals/golden_asks.json --self-check

    # Ablation: compare crew vs single-call on all asks (needs ANTHROPIC_API_KEY)
    python eval_rubric.py --golden evals/golden_asks.json --ablation

The rubric prompt is the source of truth for what each dimension means.
"""
import argparse
import json
import sys
from pathlib import Path

RUBRIC_PROMPT = """You are an expert PM evaluating an AI-generated user story against a
reference story. Score the generated story on each dimension using the scale:

5 — Excellent: matches or exceeds the reference
4 — Good: minor gaps only
3 — Adequate: usable but clearly weaker than the reference
2 — Weak: significant gaps that would require substantial revision
1 — Poor: fails the dimension

DIMENSIONS:

CLARITY — Is the story unambiguous and in plain product language? Is the "I
want" clause a single action? Are personas named specifically (never bare
"user"/"admin")? Is the title descriptive?

TESTABILITY — Can each acceptance criterion be turned directly into a test?
Does every GIVEN name a precondition, every WHEN describe one trigger, and
every THEN list observable, future-tense outcomes? Are edge cases (ACE)
covered where the reference includes them?

SCOPE_FIDELITY — Does the story stay within the ask without inventing
adjacent capabilities? If the ask was compound (contained "and"), did the
crew correctly narrow or split? Are out-of-scope items explicitly named?

COMPLETENESS — Are the obvious edge cases covered? Are dependencies and
assumptions surfaced? For well-grounded asks, is the AC count appropriate
(not too few, not inflated)? For ungrounded asks, is the PLACEHOLDER
pattern used rather than confident invention?

GROUNDING — Are claims tied to real product context with corpus citations?
Are assumptions flagged with A1/A2/... prefixes rather than fabricated? For
ungrounded asks, does the story maximally flag and minimally invent?

Output ONLY valid JSON — no fences, no preamble:
{
  "clarity": {"score": N, "reasoning": "..."},
  "testability": {"score": N, "reasoning": "..."},
  "scope_fidelity": {"score": N, "reasoning": "..."},
  "completeness": {"score": N, "reasoning": "..."},
  "grounding": {"score": N, "reasoning": "..."},
  "overall_notes": "..."
}"""


def build_judge_message(ask: str, reference: dict, generated: dict) -> str:
    return f"""ORIGINAL ASK:
"{ask}"

REFERENCE STORY (the gold standard):
{json.dumps(reference, indent=2)}

GENERATED STORY (to evaluate):
{json.dumps(generated, indent=2)}

Score the GENERATED story against the REFERENCE on each of the 5 dimensions.

Respond with ONLY the JSON object. No markdown fences, no preamble, no commentary."""


def score_with_judge(ask, reference, generated, model="claude-sonnet-4-6"):
    """Call the LLM judge. Returns parsed scores dict."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=1200,
        temperature=0,
        system=RUBRIC_PROMPT,
        messages=[
            {"role": "user", "content": build_judge_message(ask, reference, generated)},
        ],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:raw.rfind("```")].strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end + 1]
    return json.loads(raw)


def load_golden(path: str) -> dict:
    data = json.loads(Path(path).read_text("utf-8"))
    return {e["id"]: e for e in data["golden_set"]}


def self_check(golden_path: str):
    """Score every reference against itself — expect all 5s (ceiling test)."""
    entries = load_golden(golden_path)
    print(f"Self-check: scoring {len(entries)} references against themselves\n")
    print(f"{'ID':<6} {'Cat':<20} {'Clar':>4} {'Test':>4} {'Scop':>4} {'Comp':>4} {'Grnd':>4} {'Avg':>5}")
    print("─" * 60)

    all_scores = []
    for eid, entry in entries.items():
        ref = entry["reference_story"]
        try:
            scores = score_with_judge(entry["ask"], ref, ref)
            vals = [scores[d]["score"] for d in
                    ("clarity", "testability", "scope_fidelity", "completeness", "grounding")]
            avg = sum(vals) / len(vals)
            all_scores.append(vals)
            print(f"{eid:<6} {entry['category']:<20} {vals[0]:>4} {vals[1]:>4} "
                  f"{vals[2]:>4} {vals[3]:>4} {vals[4]:>4} {avg:>5.1f}")
        except Exception as e:
            print(f"{eid:<6} {entry['category']:<20} ERROR: {e}")

    if all_scores:
        means = [sum(col) / len(col) for col in zip(*all_scores)]
        print("─" * 60)
        print(f"{'MEAN':<26} {means[0]:>4.1f} {means[1]:>4.1f} "
              f"{means[2]:>4.1f} {means[3]:>4.1f} {means[4]:>4.1f} "
              f"{sum(means)/len(means):>5.1f}")
    non_fives = sum(1 for row in all_scores for v in row if v < 5)
    if non_fives:
        print(f"\n⚠ {non_fives} dimension(s) scored below 5 on self-check — "
              "review the rubric prompt or the golden reference.")
    else:
        print("\n✓ All self-check scores are 5/5 — ceiling is clean.")


def score_entry(golden_path: str, entry_id: str, crew_output_path: str):
    """Score a single crew output against a golden entry."""
    entries = load_golden(golden_path)
    if entry_id not in entries:
        print(f"Entry {entry_id} not found. Available: {', '.join(entries.keys())}")
        sys.exit(1)
    entry = entries[entry_id]
    generated = json.loads(Path(crew_output_path).read_text("utf-8"))
    scores = score_with_judge(entry["ask"], entry["reference_story"], generated)

    print(f"\nScoring {entry_id}: \"{entry['ask'][:60]}...\"")
    print(f"Category: {entry['category']} | Difficulty: {entry['difficulty']}\n")
    for dim in ("clarity", "testability", "scope_fidelity", "completeness", "grounding"):
        s = scores[dim]
        print(f"  {dim:<16} {s['score']}/5  {s['reasoning']}")
    print(f"\n  Notes: {scores.get('overall_notes', '—')}")


def mock_report(golden_path: str):
    """Print the golden set structure without calling the API."""
    entries = load_golden(golden_path)
    by_cat = {}
    for e in entries.values():
        by_cat.setdefault(e["category"], []).append(e)

    print(f"Golden set: {len(entries)} asks across {len(by_cat)} categories\n")
    for cat, items in by_cat.items():
        print(f"  {cat} ({len(items)})")
        for item in items:
            acs = item["reference_story"]["acs"]
            ac_count = sum(1 for a in acs if a["id"].startswith("AC") and not a["id"].startswith("ACE"))
            ace_count = sum(1 for a in acs if a["id"].startswith("ACE"))
            assum = len(item["reference_story"].get("assumptions_carried", []))
            print(f"    {item['id']} [{item['difficulty']}] "
                  f"{ac_count} AC + {ace_count} ACE, {assum} assumptions  "
                  f"\"{item['ask'][:55]}{'...' if len(item['ask'])>55 else ''}\"")

    print(f"\nCorpus sections referenced: "
          f"{sorted(set(s for e in entries.values() for s in e['corpus_sections_expected']))}")
    print(f"Expected behaviors total: "
          f"{sum(len(e['expected_behaviors']) for e in entries.values())}")

    print("\nCategory distribution:")
    for cat, items in by_cat.items():
        difficulties = [i["difficulty"] for i in items]
        print(f"  {cat:<22} {len(items)} asks  "
              f"(easy: {difficulties.count('easy')}, "
              f"medium: {difficulties.count('medium')}, "
              f"hard: {difficulties.count('hard')})")


def main():
    ap = argparse.ArgumentParser(description="PM Copilot rubric scorer")
    ap.add_argument("--golden", default="evals/golden_asks.json")
    ap.add_argument("--entry", help="Score a specific golden entry")
    ap.add_argument("--crew-output", help="Path to crew-generated story JSON")
    ap.add_argument("--self-check", action="store_true",
                    help="Score every reference against itself (ceiling check)")
    ap.add_argument("--ablation", action="store_true",
                    help="Run crew + single-call on all asks; compare scores")
    ap.add_argument("--report", action="store_true",
                    help="Print golden set structure (no API calls)")
    args = ap.parse_args()

    if args.report:
        mock_report(args.golden)
    elif args.self_check:
        self_check(args.golden)
    elif args.entry and args.crew_output:
        score_entry(args.golden, args.entry, args.crew_output)
    elif args.ablation:
        print("Ablation mode: run 'python crew.py' on each ask in crew mode "
              "and single mode, then score both. (Not yet automated — wire "
              "after live mode is verified.)")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()