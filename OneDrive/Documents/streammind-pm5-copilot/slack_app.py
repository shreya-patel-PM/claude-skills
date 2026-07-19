#!/usr/bin/env python3
"""
PM Copilot — Slack Bolt app.

A PM types a rough ask in #pm-copilot or DMs the bot. The crew runs
(Researcher → Analyst → Writer), validates, and posts the story with
approve/edit/reject buttons. The decision logs to Supabase.

Environment variables required:
    SLACK_BOT_TOKEN        — xoxb-... from Slack app OAuth
    SLACK_SIGNING_SECRET   — from Slack app Basic Information
    ANTHROPIC_API_KEY      — for the crew's model calls
    SUPABASE_URL           — from Supabase project settings
    SUPABASE_KEY           — from Supabase project settings (anon or service key)

Usage:
    python slack_app.py                # runs on port 3000
    SLACK_PORT=8080 python slack_app.py  # custom port
"""
import json
import os
import time
import threading
from pathlib import Path

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from prompts import (
    researcher_task, analyst_task, writer_task,
    RESEARCHER, ANALYST, WRITER,
    RESEARCHER_EXPECTED, ANALYST_EXPECTED, WRITER_EXPECTED,
)
from validate import parse_story, validate_story, render_markdown

# Supabase is optional — app works without it (logs to console instead)
try:
    from supabase_store import log_feedback, save_memory, get_recent_memory
    _has_supabase = True
except Exception:
    _has_supabase = False

def _safe_log_feedback(entry):
    if _has_supabase:
        try:
            log_feedback(entry)
            return
        except Exception as e:
            print(f"  [supabase] feedback log failed: {e}")
    # Fallback: print to console
    print(f"  [feedback] {entry.get('decision', '?')} — {entry.get('ask', '')[:60]}")

def _safe_save_memory(user_id, channel_id, ask, story):
    if _has_supabase:
        try:
            save_memory(user_id, channel_id, ask, story)
            return
        except Exception as e:
            print(f"  [supabase] memory save failed: {e}")

def _safe_get_memory(user_id, channel_id, limit=3):
    if _has_supabase:
        try:
            return get_recent_memory(user_id, channel_id, limit)
        except Exception as e:
            print(f"  [supabase] memory read failed: {e}")
    return []

ROOT = Path(__file__).parent
CONTEXT_PATH = ROOT / "product_context.md"
HAIKU = "anthropic/claude-haiku-4-5"
SONNET = "anthropic/claude-sonnet-4-6"

app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
)


# ── Crew runner (same as crew.py but returns structured output) ──────────

def run_crew(ask: str, corpus: str):
    """Run the 3-agent crew. Returns dict with stage outputs."""
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


# ── Slack message formatting ─────────────────────────────────────────────

def format_story_blocks(story: dict, warnings: list, duration: float):
    """Build Slack Block Kit blocks for the story output."""
    title = story.get("title", "Untitled Story")
    statement = story.get("story", "")
    acs = story.get("acs", [])
    assumptions = story.get("assumptions_carried", [])

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📋 {title}", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Story:* {statement}"},
        },
        {"type": "divider"},
    ]

    # Acceptance criteria
    ac_lines = []
    for ac in acs:
        prefix = "🟢" if ac["id"].startswith("AC") and not ac["id"].startswith("ACE") else "🟡"
        thens = "\n".join(f"  • {t}" for t in ac.get("thens", []))
        ac_lines.append(
            f"{prefix} *{ac['id']}- {ac['name']}*\n"
            f"  *GIVEN* {ac['given']}\n"
            f"  *WHEN* {ac['when']}\n"
            f"  *THEN:*\n{thens}"
        )

    # Split into chunks (Slack has a 3000 char limit per text block)
    ac_text = "\n\n".join(ac_lines)
    if len(ac_text) > 2800:
        mid = len(ac_lines) // 2
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n\n".join(ac_lines[:mid])},
        })
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n\n".join(ac_lines[mid:])},
        })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": ac_text},
        })

    # Assumptions
    if assumptions:
        blocks.append({"type": "divider"})
        assumption_text = "\n".join(f"• {a}" for a in assumptions)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Assumptions carried for PM confirmation:*\n{assumption_text}",
            },
        })

    # Warnings
    if warnings:
        warn_text = "\n".join(f"⚠️ {w}" for w in warnings)
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Self-check warnings:\n{warn_text}"}],
        })

    # Footer
    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"⏱ {duration}s · Haiku×2 + Sonnet×1 · create-user-story skill"}
        ],
    })

    # Action buttons
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                "style": "primary",
                "action_id": "approve_story",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✏️ Needs edits", "emoji": True},
                "action_id": "needs_edits",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                "style": "danger",
                "action_id": "reject_story",
            },
        ],
    })

    return blocks


# ── Message handler ──────────────────────────────────────────────────────

# In-memory store for pending stories (keyed by message ts)
_pending = {}


@app.event("app_mention")
def handle_mention(event, say, client):
    """Triggered when someone @mentions the bot."""
    _handle_ask(event, say, client)


@app.event("message")
def handle_dm(event, say, client):
    """Triggered for DMs to the bot."""
    # Only handle DMs (channel type 'im'), skip bot messages
    if event.get("channel_type") == "im" and not event.get("bot_id"):
        _handle_ask(event, say, client)


def _handle_ask(event, say, client):
    """Core handler: extract ask, run crew, post story."""
    raw_text = event.get("text", "").strip()
    user_id = event.get("user", "")
    channel_id = event.get("channel", "")

    # Strip the bot mention if present
    ask = raw_text
    if "<@" in ask:
        ask = ask.split(">", 1)[-1].strip()

    if not ask or len(ask) < 5:
        say("Give me a rough feature ask and I'll turn it into a developer-ready story. "
            "Example: _\"Users keep missing when their saved jobs get reposted.\"_")
        return

    # Acknowledge immediately — use client.chat_postMessage to get ts back
    ack_result = client.chat_postMessage(
        channel=channel_id,
        text=f"🔄 Running the crew on: _{ask}_\n"
             f"Researcher → Analyst → Writer — this takes ~30-50 seconds...",
    )
    ack_ts = ack_result.get("ts") if ack_result.get("ok") else None
    
    if not ack_ts:
        print(f"  ⚠ Could not get ack message ts — will post new message instead")

    # Run crew in background thread to avoid Slack timeout
    def _run():
        try:
            print(f"\n▸ Crew starting for: {ask[:60]}...")
            corpus = CONTEXT_PATH.read_text(encoding="utf-8")

            # Add conversation memory as context (if Supabase is available)
            memory = _safe_get_memory(user_id, channel_id, limit=3)
            if memory:
                memory_context = "\n\n## Recent asks in this conversation:\n"
                for m in reversed(memory):
                    memory_context += f"- Ask: \"{m['ask']}\" → {m['story_title']}\n"
                corpus += memory_context

            t0 = time.time()
            outputs = run_crew(ask, corpus)
            duration = round(time.time() - t0, 1)
            print(f"  ✓ Crew completed in {duration}s")

            story = parse_story(outputs["writer_raw"])
            errors, warnings = validate_story(story)
            print(f"  ✓ Validation: {len(errors)} errors, {len(warnings)} warnings")

            if errors:
                if ack_ts:
                    client.chat_update(
                        channel=channel_id, ts=ack_ts,
                        text=f"❌ Self-check failed — story rejected before review.\n"
                             f"Errors: {'; '.join(errors)}",
                    )
                else:
                    client.chat_postMessage(
                        channel=channel_id,
                        text=f"❌ Self-check failed — story rejected before review.\n"
                             f"Errors: {'; '.join(errors)}",
                    )
                return

            blocks = format_story_blocks(story, warnings, duration)

            if ack_ts:
                result = client.chat_update(
                    channel=channel_id, ts=ack_ts,
                    text=f"📋 {story.get('title', 'Story')}",
                    blocks=blocks,
                )
                msg_ts = result.get("ts", ack_ts)
            else:
                result = client.chat_postMessage(
                    channel=channel_id,
                    text=f"📋 {story.get('title', 'Story')}",
                    blocks=blocks,
                )
                msg_ts = result.get("ts", "")
            _pending[msg_ts] = {
                "ask": ask,
                "story": story,
                "warnings": warnings,
                "duration_s": duration,
                "user_id": user_id,
                "channel_id": channel_id,
            }

            # Save to memory
            _safe_save_memory(user_id, channel_id, ask, story)

        except Exception as e:
            print(f"  ✗ Crew failed: {e}")
            try:
                if ack_ts:
                    client.chat_update(
                        channel=channel_id, ts=ack_ts,
                        text=f"❌ Crew failed: {str(e)[:200]}",
                    )
                else:
                    client.chat_postMessage(
                        channel=channel_id,
                        text=f"❌ Crew failed: {str(e)[:200]}",
                    )
            except Exception:
                pass

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


# ── Button handlers ──────────────────────────────────────────────────────

def _handle_decision(ack, body, client, decision):
    """Shared logic for approve/edit/reject buttons."""
    ack()
    msg_ts = body.get("message", {}).get("ts", "")
    user = body.get("user", {}).get("username", "unknown")
    channel = body.get("channel", {}).get("id", "")

    pending = _pending.pop(msg_ts, None)
    if not pending:
        client.chat_postMessage(
            channel=channel,
            text=f"⚠️ Story context expired — decision not logged.",
            thread_ts=msg_ts,
        )
        return

    # Log to Supabase
    entry = {
        "ask": pending["ask"],
        "mode": "slack",
        "decision": decision,
        "self_check_warnings": pending["warnings"],
        "duration_s": pending["duration_s"],
        "story": pending["story"],
        "slack_user": user,
        "slack_channel": channel,
    }
    try:
        _safe_log_feedback(entry)
    except Exception as e:
        print(f"Supabase log failed: {e}")

    emoji = {"accepted": "✅", "edited": "✏️", "rejected": "❌"}[decision]
    label = {"accepted": "Approved", "edited": "Marked for edits", "rejected": "Rejected"}[decision]

    client.chat_postMessage(
        channel=channel,
        text=f"{emoji} *{label}* by @{user} — logged to feedback store.",
        thread_ts=msg_ts,
    )


@app.action("approve_story")
def handle_approve(ack, body, client):
    _handle_decision(ack, body, client, "accepted")


@app.action("needs_edits")
def handle_edits(ack, body, client):
    _handle_decision(ack, body, client, "edited")


@app.action("reject_story")
def handle_reject(ack, body, client):
    _handle_decision(ack, body, client, "rejected")


# ── Entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("SLACK_PORT", 3000))

    # Use Socket Mode if SLACK_APP_TOKEN is set (easier for dev)
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if app_token:
        print(f"Starting PM Copilot in Socket Mode...")
        handler = SocketModeHandler(app, app_token)
        handler.start()
    else:
        print(f"Starting PM Copilot on port {port}...")
        app.start(port=port)