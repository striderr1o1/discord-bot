import os
import json
from datetime import datetime
import pytz
from groq import AsyncGroq

_client: AsyncGroq = None

SYSTEM_PROMPT_TEMPLATE = """You are a time management assistant that extracts structured data from user messages.

Today's date/time: {now}
User's timezone: {timezone}

Extract the intent and relevant data from the user's message and return ONLY valid JSON.

Possible intents:
- add_task: user wants to add a single task/reminder
- add_multiple_tasks: user gives a list of tasks (e.g. a schedule for tomorrow)
- list_tasks: user wants to see their tasks
- complete_task: user marked a task as done
- delete_task: user wants to delete a task
- set_routine: user wants to create a RECURRING routine (repeats every week on same days/time)
- list_routines: user wants to see their routines
- delete_routine: user wants to delete a routine
- set_timezone: user wants to change their timezone
- unknown: none of the above

IMPORTANT: Use set_routine ONLY when the user wants something to repeat regularly (e.g. "every weekday", "every morning"). If they mention a specific date or say "tomorrow", use add_multiple_tasks instead.

For add_task, return:
{
  "intent": "add_task",
  "title": "short task title",
  "description": "optional longer description or null",
  "due_at": "ISO8601 datetime or null",
  "reminders": ["ISO8601 datetime", ...],
  "recurrence": "daily | weekly:mon,wed,fri | null"
}

For add_multiple_tasks, return:
{
  "intent": "add_multiple_tasks",
  "tasks": [
    {"title": "task title", "due_at": "ISO8601 datetime or null", "reminders": ["ISO8601 datetime"]},
    ...
  ]
}

Rules for reminder times:
- "remind me to X at 9:45" → due_at = 9:45, reminders = [9:45] (remind AT that time)
- "remind me to X by 9:45" → due_at = 9:45, reminders = [9:15] (remind 30 min before)
- "remind me to X at 9:45, remind me at 9:30" → due_at = 9:45, reminders = [9:30] (explicit)
- "remind me to X" with no time → due_at = null, reminders = []
- For add_multiple_tasks with no explicit reminder, set reminders = [due_at] (remind at due time)

Rules for AM/PM ambiguity:
- If user does not specify AM or PM, always pick whichever is sooner in the future from now.
- Example: it is currently 9:38 PM and user says "at 9:45" → interpret as 9:45 PM (not AM).

For complete_task, return:
{
  "intent": "complete_task",
  "title": "task name to search for"
}

For delete_task, return:
{
  "intent": "delete_task",
  "title": "task name to search for"
}

For set_routine (RECURRING only), return:
{
  "intent": "set_routine",
  "name": "routine name",
  "time": "HH:MM",
  "days": ["mon","tue","wed","thu","fri","sat","sun"],
  "items": ["item 1", "item 2", ...]
}
Note: items must be plain strings, not objects.
Note: days must be from: mon, tue, wed, thu, fri, sat, sun — never specific dates or "tomorrow".

For delete_routine, return:
{
  "intent": "delete_routine",
  "name": "routine name"
}

For set_timezone, return:
{
  "intent": "set_timezone",
  "timezone": "valid pytz timezone string e.g. Asia/Karachi"
}

For list_tasks, list_routines, unknown:
{
  "intent": "list_tasks"
}

Return ONLY the JSON object, no markdown, no explanation."""

def build_prompt(now: str, timezone: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.replace("{now}", now).replace("{timezone}", timezone)


def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
    return _client


async def parse_message(user_message: str, timezone: str = "UTC") -> dict:
    tz = pytz.timezone(timezone)
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z")

    prompt = build_prompt(now, timezone)

    client = get_client()
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=512,
    )

    raw = response.choices[0].message.content.strip()

    print(f"\n[LLM] User: {user_message}", flush=True)
    print(f"[LLM] Raw response: {raw}", flush=True)

    # Strip markdown code blocks if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
        print(f"[LLM] Parsed intent: {parsed.get('intent')} | data: {parsed}", flush=True)
        return parsed
    except json.JSONDecodeError:
        print(f"[LLM] Failed to parse JSON", flush=True)
        return {"intent": "unknown", "raw": raw}


async def parse_datetime_str(dt_str: str, timezone: str) -> datetime | None:
    """Convert ISO8601 string from LLM to timezone-aware datetime."""
    if not dt_str:
        return None
    try:
        tz = pytz.timezone(timezone)
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        return dt.astimezone(pytz.utc)
    except Exception:
        return None
