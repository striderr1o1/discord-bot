import discord
from discord.ext import commands

from services import db, scheduler
from models.schemas import Routine


class RoutineCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _send_dm(self, user_id: int, message: str):
        user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
        if user:
            await user.send(message)

    async def handle_set_routine(self, message: discord.Message, parsed: dict, timezone: str):
        name = parsed.get("name", "My Routine")
        time_str = parsed.get("time", "08:00")
        days = parsed.get("days", ["mon","tue","wed","thu","fri","sat","sun"])
        items = parsed.get("items", [])

        routine = Routine(name=name, time=time_str, days=days, items=items)
        routine = await db.create_routine(routine)

        # Schedule the cron job
        job_id = f"routine_{routine._id}"
        scheduler.schedule_routine(
            job_id,
            time_str,
            days,
            timezone,
            self._fire_routine,
            message.author.id,
            name,
            items,
        )

        day_str = ", ".join(d.capitalize() for d in days)
        lines = [
            f"**Routine set:** {name}",
            f"**Time:** {time_str} — {day_str}",
            "**Items:**",
        ]
        for i, item in enumerate(items, 1):
            lines.append(f"  {i}. {item}")

        await message.reply("\n".join(lines))

    async def handle_list_routines(self, message: discord.Message):
        routines = await db.get_all_routines()
        if not routines:
            await message.reply("No routines set up yet.")
            return

        lines = ["**Your routines:**"]
        for r in routines:
            status = "enabled" if r.enabled else "disabled"
            day_str = ", ".join(d.capitalize() for d in r.days)
            lines.append(f"\n**{r.name}** ({status})")
            lines.append(f"  {r.time} — {day_str}")
            for i, item in enumerate(r.items, 1):
                lines.append(f"  {i}. {item}")

        await message.reply("\n".join(lines))

    async def handle_delete_routine(self, message: discord.Message, parsed: dict):
        name = parsed.get("name", "")
        deleted = await db.delete_routine_by_name(name)
        if deleted:
            scheduler.remove_jobs_by_prefix(f"routine_")
            await message.reply(f"Deleted routine \"{name}\".")
        else:
            await message.reply(f"No routine found matching \"{name}\".")

    async def _fire_routine(self, user_id: int, name: str, items: list[str]):
        lines = [f"**{name}** — time to go!"]
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. {item}")
        await self._send_dm(user_id, "\n".join(lines))

    async def reload_routines(self, user_id: int, timezone: str):
        """Called on startup to reschedule all enabled routines."""
        routines = await db.get_enabled_routines()
        for routine in routines:
            job_id = f"routine_{routine._id}"
            scheduler.schedule_routine(
                job_id,
                routine.time,
                routine.days,
                timezone,
                self._fire_routine,
                user_id,
                routine.name,
                routine.items,
            )
        print(f"[Routine] Reloaded {len(routines)} routines")
