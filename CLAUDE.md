# Discord Time Management Bot

## Overview
A personal Discord bot that accepts natural language messages to create tasks, set reminders, and manage a daily/weekly routine. Message it from your phone, it figures out what you need.

## Tech Stack
- **Python 3.11+**
- **discord.py 2.3.2** — Discord bot framework
- **Groq API (groq 0.11.0)** — LLM (`llama-3.3-70b-versatile`) for natural language parsing
- **MongoDB Atlas** — persistent storage via `motor 3.5.1` async driver
- **APScheduler 3.10.4** — in-process scheduler for reminders and routines
- **httpx 0.27.2** — pinned to this version (newer versions break groq due to `proxies` kwarg removal)

## Conda Environment
```bash
conda create -n discord-bot python=3.11
conda activate discord-bot
pip install -r requirements.txt
```

## Running
```bash
conda activate discord-bot
python bot.py
```

## Project Structure
```
discord-bot/
├── CLAUDE.md
├── .env                  # secrets — never commit
├── .env.example          # template
├── .gitignore
├── requirements.txt
├── bot.py                # entry point — message router, event loop
├── cogs/
│   ├── tasks.py          # add/list/complete/delete tasks + reminder firing
│   └── routine.py        # recurring routine CRUD + cron firing
├── services/
│   ├── llm.py            # Groq API — natural language → structured JSON
│   ├── db.py             # MongoDB CRUD (tasks, routines, settings)
│   └── scheduler.py      # APScheduler setup, one-time & cron jobs
└── models/
    └── schemas.py        # Task and Routine dataclasses
```

## Environment Variables (.env)
```
DISCORD_BOT_TOKEN=
DISCORD_USER_ID=        # your personal Discord user ID (right-click self → Copy ID)
GROQ_API_KEY=
MONGO_URI=              # mongodb+srv://user:pass@cluster.mongodb.net/discord_bot
TIMEZONE=Asia/Karachi   # default timezone if not set via bot command
```

## Data Models (MongoDB)

### tasks collection
```json
{
  "_id": "ObjectId",
  "title": "string",
  "description": "string | null",
  "due_at": "datetime | null",
  "reminders": ["datetime"],
  "recurrence": "string | null",
  "status": "pending | done",
  "created_at": "datetime"
}
```

### routines collection
```json
{
  "_id": "ObjectId",
  "name": "string",
  "time": "HH:MM",
  "days": ["mon","tue","wed","thu","fri","sat","sun"],
  "items": ["string"],
  "enabled": true,
  "created_at": "datetime"
}
```

### settings collection
```json
{ "key": "timezone", "value": "Asia/Karachi" }
```

## Intents (LLM Output)

| Intent | Trigger |
|---|---|
| `add_task` | single task/reminder |
| `add_multiple_tasks` | list of tasks for a specific day |
| `list_tasks` | view pending tasks |
| `complete_task` | mark task done |
| `delete_task` | remove a task |
| `set_routine` | create a **recurring** routine (repeats weekly) |
| `list_routines` | view all routines |
| `delete_routine` | remove a routine |
| `set_timezone` | change timezone |
| `unknown` | fallback |

## Reminder Logic
- `"at X"` → reminder fires **at** X (same as due time)
- `"by X"` → reminder fires **30 min before** X
- Explicit reminder time always wins
- AM/PM ambiguous → pick whichever is sooner in the future from now
- `set_routine` is for **recurring** schedules only — if user says "tomorrow", it becomes `add_multiple_tasks`

## Known Fixes Applied
- **httpx pinned to 0.27.2** — groq 0.11.0 passes `proxies` to httpx which was removed in newer versions
- **System prompt uses `.replace()` not `.format()`** — prompt contains JSON with `{}` which broke Python's str.format
- **LLM logs added** — every message prints `[LLM] User:`, `[LLM] Raw response:`, `[LLM] Parsed intent:` to terminal
- **Error handler in `on_message`** — wraps entire handler in try/except, sends error to Discord DM so failures are visible

## Usage Examples

**Single task:**
```
remind me to submit assignment by friday 11pm
call doctor tomorrow at 2pm
buy groceries
```

**Day schedule (multiple tasks):**
```
tomorrow: 8am entrepreneurship class, 10am DBMS lab, 5pm study time, 7pm study
```

**Mark done / delete:**
```
done with groceries
delete dentist task
```

**Recurring routine:**
```
every weekday at 7am: drink water, stretch, check calendar
every sunday at 9pm: plan the week, review goals
```

**Manage:**
```
what's on my plate?
show my routines
delete morning routine
set timezone Asia/Karachi
```

## Key Decisions
- **DM-only**: bot ignores server messages, only responds in DMs
- **Single user**: only responds to `DISCORD_USER_ID`, no multi-user auth
- **LLM-first**: no slash commands — type naturally
- **APScheduler in-process**: no external cron/celery needed
- **Startup reload**: on every restart, pending reminders and enabled routines are reloaded from MongoDB and rescheduled
