#!/usr/bin/env python3
"""
PM Copilot — batch runner for golden set evaluation.

Runs every ask in golden_asks.json through the crew, saves each Writer
output, then scores the full set with the LLM-as-judge rubric.

Usage:
    # Full live run (needs ANTHROPIC_API_KEY)
    python run_golden_set.py

    # Mock run — exercises the pipeline without API calls
    python run_golden_set.py --mock

    # Score only — skip the crew runs, score existing outputs
    python run_golden_set.py --score-only

    # Run a subset
    python run_golden_set.py --ids G01 G02 G05

Results land in evals/results/ as individual JSON files + a summary CSV.
"""
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from prompts import (
    RESEARCHER, ANALYST, WRITER,
    researcher_task, analyst_task, writer_task,
    RESEARCHER_EXPECTED, ANALYST_EXPECTED, WRITER_EXPECTED,
)
from validate import parse_story, validate_story, render_markdown, strip_fences

ROOT = Path(__file__).parent
GOLDEN_PATH = ROOT / "evals" / "golden_asks.json"
RESULTS_DIR = ROOT / "evals" / "results"
SUMMARY_PATH = ROOT / "evals" / "eval_summary.csv"

HAIKU = "anthropic/claude-haiku-4-5"
SONNET = "anthropic/claude-sonnet-4-6"


def load_golden(ids=None):
    data = json.loads(GOLDEN_PATH.read_text("utf-8"))
    entries = data["golden_set"]
    if ids:
        entries = [e for e in entries if e["id"] in ids]
    return entries


def run_crew_live(ask, corpus):
    from crewai import Agent, Task, Crew, Process, LLM

    haiku = LLM(model=HAIKU, temperature=0.2)
    sonnet = LLM(model=SONNET, temperature=0.3)

    researcher = Agent(llm=haiku, verbose=False, allow_delegation=False, **RESEARCHER)
    analyst = Agent(llm=haiku, verbose=False, allow_delegation=False, **ANALYST)
    writer = Agent(llm=sonnet, verbose=False, allow_delegation=False, **WRITER)

    t_research = Task(
        description=researcher_task(ask, corpus),
        expected_output=RESEARCHER_EXPECTED,
        agent=researcher,
    )
    t_analyze = Task(
        description=analyst_task(ask),
        expected_output=ANALYST_EXPECTED,
        agent=analyst,
        context=[t_research],
    )
    t_write = Task(
        description=writer_task(ask),
        expected_output=WRITER_EXPECTED,
        agent=writer,
        context=[t_research, t_analyze],
    )

    crew = Crew(
        agents=[researcher, analyst, writer],
        tasks=[t_research, t_analyze, t_write],
        process=Process.sequential,
        verbose=False,
    )
    result = crew.kickoff()
    return {
        "researcher": str(t_research.output),
        "analyst": str(t_analyze.output),
        "writer_raw": str(result),
    }


def run_crew_mock(ask, corpus):
    """Return a minimal valid story so the scoring pipeline can be tested."""
    return {
        "researcher": "Mock context brief — no API calls.",
        "analyst": "Mock scoped spec — no API calls.",
        "writer_raw": json.dumps({
            "title": f"Mock – {ask[:40]}",
            "story": f"As a job seeker, I want {ask.lower()[:50]}, so that the need is met.",
            "acs": [
                {
                    "id": "AC1",
                    "name": "Mock Happy Path",
                    "given": "a job seeker is on the platform",
                    "when": "they perform the action",
                    "thens": ["The expected outcome will occur."],
                }
            ],
            "assumptions_carried": ["A1 — Mock run; no real analysis performed."],
        }),
    }


def score_story(ask, reference, generated, model="claude-sonnet-4-6"):
    """Score using the rubric judge. Returns dict of dimension scores."""
    import anthropic

    rubric_prompt = """You are an expert PM evaluating an AI-generated user story against a
reference story. Score the generated story on each dimension using the scale:

5 — Excellent: matches or exceeds the reference
4 — Good: minor gaps only
3 — Adequate: usable but clearly weaker than the reference
2 — Weak: significant gaps that would require substantial revision
1 — Poor: fails the dimension

DIMENSIONS:
CLARITY — Unambiguous, plain product language, single-action "I want", named personas.
TESTABILITY — GIVEN/WHEN/THEN structure, observable future-tense outcomes, edge cases covered.
SCOPE_FIDELITY — Stays within the ask, no invented scope, compound asks narrowed or split.
COMPLETENESS — Edge cases covered, dependencies and assumptions surfaced, appropriate AC count.
GROUNDING — Claims tied to context, assumptions flagged with A1/A2 prefixes, PLACEHOLDER for ungrounded.

Output ONLY valid JSON — no fences, no preamble:
{
  "clarity": {"score": N, "reasoning": "..."},
  "testability": {"score": N, "reasoning": "..."},
  "scope_fidelity": {"score": N, "reasoning": "..."},
  "completeness": {"score": N, "reasoning": "..."},
  "grounding": {"score": N, "reasoning": "..."}
}"""

    user_msg = f"""ORIGINAL ASK:
"{ask}"

REFERENCE STORY (gold standard):
{json.dumps(reference, indent=2)}

GENERATED STORY (to evaluate):
{json.dumps(generated, indent=2)}

Score the GENERATED story against the REFERENCE on each of the 5 dimensions.

Respond with ONLY the JSON object. No markdown fences, no preamble, no commentary."""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=1200,
        temperature=0,
        system=rubric_prompt,
        messages=[
            {"role": "user", "content": user_msg},
        ],
    )
    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:raw.rfind("```")].strip()
    # Find the JSON object
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end + 1]
    return json.loads(raw)


def run_batch(entries, mock=False):
    """Run the crew on each entry and save outputs."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    corpus = (ROOT / "product_context.md").read_text("utf-8")
    run_fn = run_crew_mock if mock else run_crew_live

    for i, entry in enumerate(entries):
        eid = entry["id"]
        result_path = RESULTS_DIR / f"{eid}.json"

        if result_path.exists():
            print(f"  [{i+1}/{len(entries)}] {eid} — already exists, skipping crew run")
            continue

        print(f"  [{i+1}/{len(entries)}] {eid} — running {'mock' if mock else 'live'} crew...")
        t0 = time.time()

        try:
            outputs = run_fn(entry["ask"], corpus)
            story = parse_story(outputs["writer_raw"])
            errors, warnings = validate_story(story)

            result = {
                "id": eid,
                "ask": entry["ask"],
                "category": entry["category"],
                "difficulty": entry["difficulty"],
                "mode": "mock" if mock else "live",
                "ts": datetime.now(timezone.utc).isoformat(),
                "duration_s": round(time.time() - t0, 1),
                "story": story,
                "validation": {
                    "errors": errors,
                    "warnings": warnings,
                    "passed": len(errors) == 0,
                },
                "researcher_brief": outputs["researcher"][:500],
                "analyst_spec": outputs["analyst"][:500],
            }
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            status = "✓" if not errors else f"✗ {len(errors)} errors"
            print(f"           {status} · {len(warnings)} warnings · {result['duration_s']}s")

        except Exception as e:
            print(f"           ✗ FAILED: {e}")
            result = {
                "id": eid,
                "ask": entry["ask"],
                "error": str(e),
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def score_batch(entries):
    """Score all existing results against their golden references."""
    DIMS = ["clarity", "testability", "scope_fidelity", "completeness", "grounding"]
    rows = []

    print(f"\n{'ID':<6} {'Cat':<20} {'Diff':<8} ", end="")
    print(f"{'Clar':>4} {'Test':>4} {'Scop':>4} {'Comp':>4} {'Grnd':>4} {'Avg':>5}")
    print("─" * 72)

    for entry in entries:
        eid = entry["id"]
        result_path = RESULTS_DIR / f"{eid}.json"

        if not result_path.exists():
            print(f"{eid:<6} — no result file, skipping")
            continue

        result = json.loads(result_path.read_text("utf-8"))
        if "error" in result and "story" not in result:
            print(f"{eid:<6} — crew run failed, skipping")
            continue

        try:
            scores = score_story(
                entry["ask"],
                entry["reference_story"],
                result["story"],
            )
            vals = [scores[d]["score"] for d in DIMS]
            avg = sum(vals) / len(vals)

            row = {
                "id": eid,
                "category": entry["category"],
                "difficulty": entry["difficulty"],
                **{d: scores[d]["score"] for d in DIMS},
                **{f"{d}_reasoning": scores[d]["reasoning"] for d in DIMS},
                "avg": round(avg, 2),
            }
            rows.append(row)

            # Save scores back into the result file
            result["rubric_scores"] = scores
            result["rubric_avg"] = round(avg, 2)
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

            print(f"{eid:<6} {entry['category']:<20} {entry['difficulty']:<8} ", end="")
            print(f"{vals[0]:>4} {vals[1]:>4} {vals[2]:>4} {vals[3]:>4} {vals[4]:>4} {avg:>5.1f}")

        except Exception as e:
            print(f"{eid:<6} — scoring failed: {e}")

    if rows:
        print("─" * 72)
        means = {d: round(sum(r[d] for r in rows) / len(rows), 2) for d in DIMS}
        overall = round(sum(means.values()) / len(means), 2)
        print(f"{'MEAN':<35} {means['clarity']:>4} {means['testability']:>4} "
              f"{means['scope_fidelity']:>4} {means['completeness']:>4} "
              f"{means['grounding']:>4} {overall:>5}")

        # Category breakdown
        print(f"\n{'Category breakdown':}")
        cats = sorted(set(r["category"] for r in rows))
        for cat in cats:
            cat_rows = [r for r in rows if r["category"] == cat]
            cat_means = {d: round(sum(r[d] for r in cat_rows) / len(cat_rows), 2) for d in DIMS}
            cat_avg = round(sum(cat_means.values()) / len(cat_means), 2)
            print(f"  {cat:<22} n={len(cat_rows):<3} "
                  f"clar={cat_means['clarity']:.1f}  test={cat_means['testability']:.1f}  "
                  f"scop={cat_means['scope_fidelity']:.1f}  comp={cat_means['completeness']:.1f}  "
                  f"grnd={cat_means['grounding']:.1f}  avg={cat_avg:.1f}")

        # Write CSV
        fieldnames = ["id", "category", "difficulty"] + DIMS + ["avg"] + \
                     [f"{d}_reasoning" for d in DIMS]
        with open(SUMMARY_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nSummary written to {SUMMARY_PATH}")

    return rows


def main():
    ap = argparse.ArgumentParser(description="PM Copilot golden set batch runner")
    ap.add_argument("--mock", action="store_true", help="Mock crew runs (no API calls for crew)")
    ap.add_argument("--score-only", action="store_true", help="Skip crew runs, score existing results")
    ap.add_argument("--ids", nargs="+", help="Run specific entries only (e.g. G01 G05)")
    ap.add_argument("--no-score", action="store_true", help="Run crew only, skip scoring")
    args = ap.parse_args()

    entries = load_golden(args.ids)
    print(f"PM Copilot golden set — {len(entries)} asks\n")

    if not args.score_only:
        print("Phase 1: Running crew on each ask...")
        run_batch(entries, mock=args.mock)

    if not args.no_score:
        print("\nPhase 2: Scoring with LLM-as-judge rubric...")
        score_batch(entries)


if __name__ == "__main__":
    main()