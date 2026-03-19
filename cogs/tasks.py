import discord
from discord.ext import commands
from datetime import datetime
import pytz

from services import db, llm, scheduler
from models.schemas import Task


class TasksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _send_dm(self, user_id: int, message: str):
        user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
        if user:
            await user.send(message)

    async def handle_add_task(self, message: discord.Message, parsed: dict, timezone: str):
        title = parsed.get("title", "Untitled task")
        description = parsed.get("description")
        recurrence = parsed.get("recurrence")

        # Parse due_at
        due_at = await llm.parse_datetime_str(parsed.get("due_at"), timezone)

        # Parse reminders
        reminder_strs = parsed.get("reminders") or []
        reminders = []
        for r in reminder_strs:
            dt = await llm.parse_datetime_str(r, timezone)
            if dt:
                reminders.append(dt)

        task = Task(
            title=title,
            description=description,
            due_at=due_at,
            reminders=reminders,
            recurrence=recurrence,
        )
        task = await db.create_task(task)

        # Schedule reminder jobs
        for i, remind_at in enumerate(reminders):
            job_id = f"task_{task._id}_reminder_{i}"
            scheduler.schedule_reminder(
                job_id,
                remind_at,
                self._fire_task_reminder,
                message.author.id,
                title,
                due_at,
            )

        # Build confirmation
        lines = [f"**Task added:** {title}"]
        if description:
            lines.append(f"> {description}")
        if due_at:
            tz = pytz.timezone(timezone)
            local = due_at.astimezone(tz)
            lines.append(f"**Due:** {local.strftime('%a %b %d at %I:%M %p %Z')}")
        if reminders:
            tz = pytz.timezone(timezone)
            times = [r.astimezone(tz).strftime('%I:%M %p %Z') for r in reminders]
            lines.append(f"**Reminders:** {', '.join(times)}")
        if recurrence:
            lines.append(f"**Repeats:** {recurrence}")

        await message.reply("\n".join(lines))

    async def _fire_task_reminder(self, user_id: int, title: str, due_at: datetime | None):
        lines = [f"**Reminder:** {title}"]
        if due_at:
            lines.append(f"Due soon!")
        await self._send_dm(user_id, "\n".join(lines))

    async def handle_add_multiple_tasks(self, message: discord.Message, parsed: dict, timezone: str):
        tasks_data = parsed.get("tasks", [])
        if not tasks_data:
            await message.reply("Couldn't parse any tasks from that.")
            return

        added = []
        for t in tasks_data:
            due_at = await llm.parse_datetime_str(t.get("due_at"), timezone)
            reminders = []
            for r in (t.get("reminders") or []):
                dt = await llm.parse_datetime_str(r, timezone)
                if dt:
                    reminders.append(dt)

            task = Task(title=t["title"], due_at=due_at, reminders=reminders)
            task = await db.create_task(task)

            for i, remind_at in enumerate(reminders):
                job_id = f"task_{task._id}_reminder_{i}"
                scheduler.schedule_reminder(
                    job_id, remind_at,
                    self._fire_task_reminder,
                    message.author.id, task.title, due_at,
                )
            added.append((task.title, due_at))

        tz = pytz.timezone(timezone)
        lines = [f"**Added {len(added)} tasks:**"]
        for title, due_at in added:
            line = f"- {title}"
            if due_at:
                line += f" — {due_at.astimezone(tz).strftime('%I:%M %p')}"
            lines.append(line)
        await message.reply("\n".join(lines))

    async def handle_list_tasks(self, message: discord.Message, timezone: str):
        tasks = await db.get_pending_tasks()
        if not tasks:
            await message.reply("No pending tasks.")
            return

        tz = pytz.timezone(timezone)
        lines = ["**Your pending tasks:**"]
        for i, t in enumerate(tasks, 1):
            line = f"{i}. **{t.title}**"
            if t.due_at:
                local = t.due_at.astimezone(tz)
                line += f" — due {local.strftime('%a %b %d %I:%M %p')}"
            lines.append(line)

        await message.reply("\n".join(lines))

    async def handle_complete_task(self, message: discord.Message, parsed: dict):
        title = parsed.get("title", "")
        done = await db.complete_task_by_title(title)
        if done:
            await message.reply(f"Done! Marked **{title}** as complete.")
        else:
            await message.reply(f"Couldn't find a pending task matching \"{title}\".")

    async def handle_delete_task(self, message: discord.Message, parsed: dict):
        title = parsed.get("title", "")
        deleted = await db.delete_task_by_title(title)
        if deleted:
            await message.reply(f"Deleted task matching \"{title}\".")
        else:
            await message.reply(f"No task found matching \"{title}\".")

    async def reload_task_reminders(self, user_id: int):
        """Called on startup to reschedule all pending reminders."""
        tasks = await db.get_pending_tasks()
        now = datetime.now(pytz.utc)
        for task in tasks:
            for i, remind_at in enumerate(task.reminders):
                if remind_at > now:
                    job_id = f"task_{task._id}_reminder_{i}"
                    scheduler.schedule_reminder(
                        job_id,
                        remind_at,
                        self._fire_task_reminder,
                        user_id,
                        task.title,
                        task.due_at,
                    )
        print(f"[Tasks] Reloaded reminders for {len(tasks)} pending tasks")
