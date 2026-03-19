# Discord Time Management Bot

## Overview
A personal Discord bot that accepts natural language messages to create tasks, set reminders, and manage a daily/weekly routine. Message it from your phone, it figures out what you need.

## Tech Stack
- **Python 3.11+**
- **discord.py** — Discord bot framework
- **Groq API** — LLM for natural language parsing (extract tasks, times, intents)
- **MongoDB Atlas** — persistent storage (via `motor` async driver)
- **APScheduler** — in-process scheduler for firing reminders

## Project Structure
```
discord-bot/
├── CLAUDE.md
├── .env                  # BOT_TOKEN, GROQ_API_KEY, MONGO_URI
├── requirements.txt
├── bot.py                # entry point — bot setup, event loop
├── cogs/
│   ├── tasks.py          # task CRUD (add/list/complete/delete)
│   ├── reminders.py      # reminder scheduling & firing
│   └── routine.py        # routine management
├── services/
│   ├── llm.py            # Groq API calls — parse natural language → structured data
│   ├── db.py             # MongoDB connection & helpers
│   └── scheduler.py      # APScheduler setup, add/remove jobs
└── models/
    └── schemas.py        # data shapes (Task, Reminder, Routine)
```

## Data Models (MongoDB)

### tasks collection
```json
{
  "_id": "ObjectId",
  "title": "string",
  "description": "string | null",
  "due_at": "datetime | null",
  "reminders": ["datetime"],       // list of times to send reminder DMs
  "recurrence": "string | null",   // e.g. "daily", "weekly:mon,wed,fri"
  "status": "pending | done",
  "created_at": "datetime"
}
```

### routines collection
```json
{
  "_id": "ObjectId",
  "name": "string",                // e.g. "Morning Routine"
  "time": "string",                // e.g. "07:00"
  "days": ["mon","tue","wed","thu","fri","sat","sun"],
  "items": ["string"],             // ordered list of things to do
  "enabled": true,
  "created_at": "datetime"
}
```

## How It Works

### 1. Message Flow
- User sends a DM (or message in a designated channel) to the bot
- Bot sends the raw message to **Groq LLM** with a system prompt that extracts:
  - `intent`: one of `add_task`, `list_tasks`, `complete_task`, `delete_task`, `set_routine`, `list_routines`, `delete_routine`, `unknown`
  - `task_title`, `description`, `due_at`, `reminders[]`, `recurrence` (for task intents)
  - `routine_name`, `time`, `days`, `items` (for routine intents)
- Bot acts on the parsed intent, confirms back to user

### 2. Natural Language Examples
```
"remind me to submit the report by friday 5pm"
→ { intent: "add_task", title: "submit the report", due_at: "2026-03-20T17:00", reminders: ["2026-03-20T16:30"] }

"every weekday at 7am remind me: stretch, journal, review calendar"
→ { intent: "set_routine", name: "Morning Routine", time: "07:00", days: ["mon"-"fri"], items: [...] }

"what's on my plate?"
→ { intent: "list_tasks" }

"done with grocery shopping"
→ { intent: "complete_task", title: "grocery shopping" }
```

### 3. Reminder System
- When a task is created with reminder times, **APScheduler** jobs are scheduled
- When a routine is created/enabled, APScheduler cron jobs are scheduled
- On bot startup, all pending reminders and active routines are loaded from MongoDB and re-scheduled
- When a job fires, bot sends a Discord DM to the user

### 4. Routine System
- Routines are recurring schedules (e.g. "every weekday at 7am: stretch, journal, plan day")
- Stored in MongoDB, managed via natural language or explicit commands
- Each active routine becomes an APScheduler cron job
- Reminder DM lists the routine items in order

## Implementation Order
1. **Scaffold** — project setup, .env, requirements.txt, bot.py skeleton
2. **Database** — MongoDB connection via motor, basic CRUD in `services/db.py`
3. **LLM parsing** — Groq integration in `services/llm.py`, system prompt, structured output
4. **Task cog** — handle add/list/complete/delete tasks via parsed intents
5. **Scheduler** — APScheduler setup, schedule reminders on task creation, reload on startup
6. **Reminder cog** — fire DMs when reminders trigger
7. **Routine cog** — routine CRUD + cron-based scheduling
8. **Polish** — error handling, timezone support, edge cases

## Key Decisions
- **DM-based**: bot works in DMs so you can message it from phone like texting
- **Single user**: no auth complexity, bot owner = the user
- **LLM-first**: no slash commands needed — just type naturally. The LLM figures out intent.
- **APScheduler**: runs in the same process as the bot, no need for external cron/celery
- **Timezone**: user sets their timezone once (stored in DB), all times interpreted in that TZ
