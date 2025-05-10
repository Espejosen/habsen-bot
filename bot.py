import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s:%(levelname)s:%(message)s",
    handlers=[
        logging.FileHandler("bot_errors.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("HabsenBot")

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    logger.info(f"{bot.user.name} aktif!")
    await bot.load_extension("cogs.registration")
    await bot.load_extension("cogs.ticket")
    await bot.load_extension("cogs.moderation")
    await bot.load_extension("cogs.developer")
    await bot.tree.sync()

bot.run(BOT_TOKEN)
