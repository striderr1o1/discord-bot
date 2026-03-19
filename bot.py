import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web

from services import db, llm, scheduler
from cogs.tasks import TasksCog
from cogs.routine import RoutineCog

load_dotenv()

DISCORD_USER_ID = int(os.environ["DISCORD_USER_ID"])
DEFAULT_TIMEZONE = os.environ.get("TIMEZONE", "UTC")

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

tasks_cog: TasksCog = None
routine_cog: RoutineCog = None


@bot.event
async def on_ready():
    global tasks_cog, routine_cog
    print(f"[Bot] Logged in as {bot.user} (ID: {bot.user.id})")

    await db.connect()
    scheduler.start_scheduler()

    tasks_cog = TasksCog(bot)
    routine_cog = RoutineCog(bot)
    await bot.add_cog(tasks_cog)
    await bot.add_cog(routine_cog)

    # Reload persisted state
    timezone = await db.get_setting("timezone", DEFAULT_TIMEZONE)
    await tasks_cog.reload_task_reminders(DISCORD_USER_ID)
    await routine_cog.reload_routines(DISCORD_USER_ID, timezone)

    print("[Bot] Ready.")


@bot.event
async def on_message(message: discord.Message):
    # Only respond to the owner, only in DMs
    if message.author.bot:
        return
    if message.author.id != DISCORD_USER_ID:
        return
    if not isinstance(message.channel, discord.DMChannel):
        return

    content = message.content.strip()
    if not content:
        return

    # Show typing indicator while processing
    try:
      async with message.channel.typing():
        timezone = await db.get_setting("timezone", DEFAULT_TIMEZONE)

        # Handle timezone command manually
        if content.lower().startswith("set timezone"):
            tz_name = content.split(None, 2)[-1].strip()
            try:
                import pytz
                pytz.timezone(tz_name)  # validate
                await db.set_setting("timezone", tz_name)
                await message.reply(f"Timezone set to **{tz_name}**.")
            except Exception:
                await message.reply(f"Unknown timezone: `{tz_name}`\nUse a valid tz name like `Asia/Karachi`, `America/New_York`, etc.")
            return

        parsed = await llm.parse_message(content, timezone)
        intent = parsed.get("intent", "unknown")

        if intent == "add_task":
            await tasks_cog.handle_add_task(message, parsed, timezone)
        elif intent == "add_multiple_tasks":
            await tasks_cog.handle_add_multiple_tasks(message, parsed, timezone)
        elif intent == "list_tasks":
            await tasks_cog.handle_list_tasks(message, timezone)
        elif intent == "complete_task":
            await tasks_cog.handle_complete_task(message, parsed)
        elif intent == "delete_task":
            await tasks_cog.handle_delete_task(message, parsed)
        elif intent == "set_routine":
            await routine_cog.handle_set_routine(message, parsed, timezone)
        elif intent == "list_routines":
            await routine_cog.handle_list_routines(message)
        elif intent == "delete_routine":
            await routine_cog.handle_delete_routine(message, parsed)
        elif intent == "set_timezone":
            tz_name = parsed.get("timezone", "")
            try:
                import pytz
                pytz.timezone(tz_name)
                await db.set_setting("timezone", tz_name)
                await message.reply(f"Timezone set to **{tz_name}**.")
            except Exception:
                await message.reply(f"Unknown timezone: `{tz_name}`")
        else:
            await message.reply(
                "I didn't understand that. Try:\n"
                "- *remind me to review PR by tomorrow 3pm*\n"
                "- *what's on my plate?*\n"
                "- *done with grocery shopping*\n"
                "- *every weekday at 7am: stretch, journal, plan day*\n"
                "- *show routines*\n"
                "- `set timezone Asia/Karachi`"
            )

    except Exception as e:
        print(f"[Error] on_message: {e}", flush=True)
        import traceback; traceback.print_exc()
        await message.channel.send(f"Error: `{e}`")

    await bot.process_commands(message)


async def run_web_server():
    async def handle(request):
        return web.Response(text="OK")
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[Web] Listening on port {port}")


async def main():
    token = os.environ["DISCORD_BOT_TOKEN"]
    try:
        await asyncio.gather(
            bot.start(token),
            run_web_server(),
        )
    finally:
        scheduler.stop_scheduler()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
