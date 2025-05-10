import discord
from discord import app_commands
from discord.ext import commands
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

class Developer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_developer(self, interaction: discord.Interaction):
        DEVELOPER_ID = int(os.getenv("DEVELOPER_ID"))
        if interaction.user.id != DEVELOPER_ID:
            embed = discord.Embed(
                title="Yetkisiz İşlem",
                description="Bu komut yalnızca bot geliştiricisi tarafından kullanılabilir.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    @app_commands.command(name="restart", description="Botu yeniden başlatır (yalnızca geliştirici)")
    async def restart(self, interaction: discord.Interaction):
        if not await self.check_developer(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="Yeniden Başlatılıyor",
            description="Bot yeniden başlatılıyor. Lütfen birkaç saniye bekleyin.",
            color=0xffff00,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Botu yeniden başlat
        python = sys.executable
        os.execl(python, python, *sys.argv)

async def setup(bot):
    await bot.add_cog(Developer(bot))
