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
SINGLE_DIR = ROOT / "evals" / "results_single"
SUMMARY_PATH = ROOT / "evals" / "eval_summary.csv"
ABLATION_PATH = ROOT / "evals" / "ablation_summary.csv"

HAIKU = "anthropic/claude-haiku-4-5"
SONNET = "anthropic/claude-sonnet-4-6"
SONNET_DIRECT = "claude-sonnet-4-6"  # for direct anthropic SDK calls


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


def run_single_call(ask, corpus):
    """Single Sonnet call — no crew, no Researcher/Analyst. The ablation baseline."""
    import anthropic

    system = (
        "You are a senior Product Manager. Given a rough feature ask and product "
        "context, write a developer-ready user story with acceptance criteria.\n\n"
        "Output ONLY valid JSON. No markdown fences, no preamble.\n\n"
        "JSON SCHEMA:\n"
        '{\n'
        '  "title": "[Feature Name] – [Story Name]",\n'
        '  "story": "As a [specific role], I want [one action], so that [outcome].",\n'
        '  "acs": [\n'
        '    {\n'
        '      "id": "AC1",\n'
        '      "name": "Short Descriptive Name",\n'
        '      "given": "[role] [precondition]",\n'
        '      "when": "[single triggering action]",\n'
        '      "thens": ["Observable outcome in future tense."]\n'
        '    }\n'
        '  ],\n'
        '  "assumptions_carried": ["A1 — ..."]\n'
        '}\n\n'
        "RULES:\n"
        "- AC prefix for happy path, ACE for edge cases, numbered sequentially.\n"
        "- Every GIVEN names a specific role. Every WHEN is one action.\n"
        "- Every THEN bullet is future tense.\n"
        "- Keep scope narrow — the smallest slice that satisfies the ask.\n"
        "- Flag assumptions as A1, A2, ... rather than inventing product detail.\n"
        "- If the ask names multiple features, pick ONE and note the rest as assumptions."
    )

    user_msg = (
        f'Feature ask: "{ask}"\n\n'
        f"Product context:\n{corpus}\n\n"
        "Write the user story as JSON."
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=SONNET_DIRECT,
        max_tokens=4000,
        temperature=0.3,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = response.content[0].text.strip()
    usage = response.usage

    return {
        "researcher": "(single-call mode — no Researcher)",
        "analyst": "(single-call mode — no Analyst)",
        "writer_raw": raw,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
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


def run_batch(entries, mock=False, single=False, output_dir=None):
    """Run the crew (or single call) on each entry and save outputs."""
    out_dir = output_dir or (SINGLE_DIR if single else RESULTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    corpus = (ROOT / "product_context.md").read_text("utf-8")

    if mock:
        run_fn = run_crew_mock
        label = "mock"
    elif single:
        run_fn = run_single_call
        label = "single-call"
    else:
        run_fn = run_crew_live
        label = "crew"

    for i, entry in enumerate(entries):
        eid = entry["id"]
        result_path = out_dir / f"{eid}.json"

        if result_path.exists():
            print(f"  [{i+1}/{len(entries)}] {eid} — already exists, skipping")
            continue

        print(f"  [{i+1}/{len(entries)}] {eid} — running {label}...")
        t0 = time.time()

        try:
            outputs = run_fn(entry["ask"], corpus)
            story = parse_story(outputs["writer_raw"])
            errors, warnings = validate_story(story)
            duration = round(time.time() - t0, 1)

            result = {
                "id": eid,
                "ask": entry["ask"],
                "category": entry["category"],
                "difficulty": entry["difficulty"],
                "mode": label,
                "ts": datetime.now(timezone.utc).isoformat(),
                "duration_s": duration,
                "story": story,
                "validation": {
                    "errors": errors,
                    "warnings": warnings,
                    "passed": len(errors) == 0,
                },
                "researcher_brief": outputs["researcher"][:500],
                "analyst_spec": outputs["analyst"][:500],
            }
            if "input_tokens" in outputs:
                result["input_tokens"] = outputs["input_tokens"]
                result["output_tokens"] = outputs["output_tokens"]

            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            status = "✓" if not errors else f"✗ {len(errors)} errors"
            print(f"           {status} · {len(warnings)} warnings · {duration}s")

        except Exception as e:
            print(f"           ✗ FAILED: {e}")
            result = {
                "id": eid,
                "ask": entry["ask"],
                "error": str(e),
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def score_batch(entries, results_dir=None, label=""):
    """Score all existing results against their golden references."""
    rdir = results_dir or RESULTS_DIR
    DIMS = ["clarity", "testability", "scope_fidelity", "completeness", "grounding"]
    rows = []

    if label:
        print(f"\n── {label} ──")
    print(f"\n{'ID':<6} {'Cat':<20} {'Diff':<8} ", end="")
    print(f"{'Clar':>4} {'Test':>4} {'Scop':>4} {'Comp':>4} {'Grnd':>4} {'Avg':>5}")
    print("─" * 72)

    for entry in entries:
        eid = entry["id"]
        result_path = rdir / f"{eid}.json"

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


def ablation_compare(entries):
    """Compare crew vs single-call results side by side."""
    DIMS = ["clarity", "testability", "scope_fidelity", "completeness", "grounding"]
    rows = []

    print("\n" + "=" * 80)
    print("ABLATION: Crew (3 calls) vs Single Call (1 call)")
    print("=" * 80)
    print(f"\n{'ID':<6} {'Cat':<18}  {'Crew':>5} {'Singl':>5}  {'Δ':>5}  {'Crew$':>8} {'Singl$':>8}  {'CrewT':>6} {'SnglT':>6}")
    print("─" * 80)

    crew_avgs, single_avgs = [], []
    crew_times, single_times = [], []

    for entry in entries:
        eid = entry["id"]
        crew_path = RESULTS_DIR / f"{eid}.json"
        single_path = SINGLE_DIR / f"{eid}.json"

        if not crew_path.exists() or not single_path.exists():
            continue

        crew_r = json.loads(crew_path.read_text("utf-8"))
        single_r = json.loads(single_path.read_text("utf-8"))

        if "rubric_avg" not in crew_r or "rubric_avg" not in single_r:
            continue

        c_avg = crew_r["rubric_avg"]
        s_avg = single_r["rubric_avg"]
        delta = round(c_avg - s_avg, 2)
        c_time = crew_r.get("duration_s", 0)
        s_time = single_r.get("duration_s", 0)

        # Estimate costs
        c_cost = "$0.015"  # ~$0.013-0.023 per ARCHITECTURE.md
        s_tokens_in = single_r.get("input_tokens", 0)
        s_tokens_out = single_r.get("output_tokens", 0)
        s_cost_val = (s_tokens_in * 3 / 1_000_000) + (s_tokens_out * 15 / 1_000_000)
        s_cost = f"${s_cost_val:.3f}" if s_tokens_in else "—"

        crew_avgs.append(c_avg)
        single_avgs.append(s_avg)
        crew_times.append(c_time)
        single_times.append(s_time)

        sign = "+" if delta > 0 else "" if delta == 0 else ""
        print(f"{eid:<6} {entry['category']:<18}  {c_avg:>5.1f} {s_avg:>5.1f}  {sign}{delta:>+5.2f}"
              f"  {c_cost:>8} {s_cost:>8}  {c_time:>5.1f}s {s_time:>5.1f}s")

        row = {
            "id": eid, "category": entry["category"],
            "crew_avg": c_avg, "single_avg": s_avg, "delta": delta,
            "crew_time": c_time, "single_time": s_time,
        }
        # Per-dimension comparison
        if "rubric_scores" in crew_r and "rubric_scores" in single_r:
            for d in DIMS:
                row[f"crew_{d}"] = crew_r["rubric_scores"][d]["score"]
                row[f"single_{d}"] = single_r["rubric_scores"][d]["score"]
        rows.append(row)

    if crew_avgs and single_avgs:
        c_mean = round(sum(crew_avgs) / len(crew_avgs), 2)
        s_mean = round(sum(single_avgs) / len(single_avgs), 2)
        c_t_mean = round(sum(crew_times) / len(crew_times), 1)
        s_t_mean = round(sum(single_times) / len(single_times), 1)

        print("─" * 80)
        print(f"{'MEAN':<26} {c_mean:>5.1f} {s_mean:>5.1f}  {c_mean - s_mean:>+5.2f}"
              f"{'':>18} {c_t_mean:>5.1f}s {s_t_mean:>5.1f}s")

        print(f"\n  Crew wins:   {sum(1 for c,s in zip(crew_avgs, single_avgs) if c > s)}")
        print(f"  Single wins: {sum(1 for c,s in zip(crew_avgs, single_avgs) if s > c)}")
        print(f"  Ties:        {sum(1 for c,s in zip(crew_avgs, single_avgs) if c == s)}")
        print(f"  Speed ratio: single is {c_t_mean / s_t_mean:.1f}× faster" if s_t_mean > 0 else "")

        # Per-dimension comparison
        if rows and f"crew_{DIMS[0]}" in rows[0]:
            print(f"\n  Per-dimension means:")
            for d in DIMS:
                c_d = round(sum(r.get(f"crew_{d}", 0) for r in rows) / len(rows), 2)
                s_d = round(sum(r.get(f"single_{d}", 0) for r in rows) / len(rows), 2)
                marker = "← crew" if c_d > s_d else "← single" if s_d > c_d else "= tie"
                print(f"    {d:<18} crew {c_d:.1f}  single {s_d:.1f}  Δ{c_d-s_d:>+.1f}  {marker}")

        # Write CSV
        if rows:
            fieldnames = list(rows[0].keys())
            with open(ABLATION_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"\n  Ablation summary written to {ABLATION_PATH}")


def main():
    ap = argparse.ArgumentParser(description="PM Copilot golden set batch runner")
    ap.add_argument("--mock", action="store_true", help="Mock crew runs (no API calls for crew)")
    ap.add_argument("--score-only", action="store_true", help="Skip crew runs, score existing results")
    ap.add_argument("--ids", nargs="+", help="Run specific entries only (e.g. G01 G05)")
    ap.add_argument("--no-score", action="store_true", help="Run crew only, skip scoring")
    ap.add_argument("--single", action="store_true", help="Run single-call mode (no crew)")
    ap.add_argument("--ablation", action="store_true",
                    help="Run single-call on all asks, score, then compare with existing crew results")
    args = ap.parse_args()

    entries = load_golden(args.ids)
    print(f"PM Copilot golden set — {len(entries)} asks\n")

    if args.ablation:
        # Phase 1: run single-call
        print("Phase 1: Running SINGLE-CALL on each ask...")
        run_batch(entries, single=True, output_dir=SINGLE_DIR)
        # Phase 2: score single-call results
        print("\nPhase 2: Scoring single-call results...")
        score_batch(entries, results_dir=SINGLE_DIR, label="SINGLE-CALL SCORES")
        # Phase 3: compare
        print("\nPhase 3: Comparing crew vs single-call...")
        ablation_compare(entries)
        return

    if args.single:
        out_dir = SINGLE_DIR
        if not args.score_only:
            print("Phase 1: Running SINGLE-CALL on each ask...")
            run_batch(entries, single=True, output_dir=out_dir)
        if not args.no_score:
            print("\nPhase 2: Scoring single-call results...")
            score_batch(entries, results_dir=out_dir, label="SINGLE-CALL SCORES")
        return

    if not args.score_only:
        print("Phase 1: Running crew on each ask...")
        run_batch(entries, mock=args.mock)

    if not args.no_score:
        print("\nPhase 2: Scoring with LLM-as-judge rubric...")
        score_batch(entries)


if __name__ == "__main__":
    main()