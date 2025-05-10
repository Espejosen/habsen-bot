import discord
from discord import app_commands
from discord.ext import commands
import random
import string
from datetime import datetime
from zoneinfo import ZoneInfo
from utils.helpers import check_username_validity, check_motto
import os

class VerifyButton(discord.ui.View):
    def __init__(self, user_id, username, code, verification_codes):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.username = username
        self.code = code
        self.verification_codes = verification_codes

    @discord.ui.button(label="Kontrol Et", style=discord.ButtonStyle.primary)
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            embed = discord.Embed(
                title="Yetkisiz İşlem",
                description="Bu butonu sadece doğrulama sahibi kullanabilir.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if self.user_id not in self.verification_codes or datetime.now(ZoneInfo("UTC")).timestamp() > self.verification_codes[self.user_id]["expires_at"]:
            del self.verification_codes[self.user_id]
            self.children[0].disabled = True
            await interaction.message.edit(view=self)
            embed = discord.Embed(
                title="Süre Doldu",
                description="Doğrulama kodunun süresi doldu. Lütfen tekrar /kayıt komutunu kullanın.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        is_valid = await check_motto(self.username, self.code)
        if is_valid:
            member = await interaction.guild.fetch_member(self.user_id)
            role = interaction.guild.get_role(int(os.getenv("VERIFIED_ROLE_ID")))
            if role:
                try:
                    await member.add_roles(role)
                    embed = discord.Embed(
                        title="Doğrulama Başarılı",
                        description="Habsen profilindeki kod doğrulandı. **Doğrulanmış** rolü verildi.",
                        color=0x00ff00,
                        timestamp=datetime.now(ZoneInfo("UTC"))
                    )
                    embed.add_field(name="Habsen Kullanıcı Adı", value=f"**{self.username}**", inline=False)
                    embed.set_footer(text="Habsen Topluluğu")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                except discord.Forbidden:
                    embed = discord.Embed(
                        title="İzin Hatası",
                        description="Rol eklenemedi. Botun izinlerini kontrol edin.",
                        color=0xffff00,
                        timestamp=datetime.now(ZoneInfo("UTC"))
                    )
                    embed.set_footer(text="Habsen Topluluğu")
                    await interaction.followup.send(embed=embed, ephemeral=True)
            del self.verification_codes[self.user_id]
            self.children[0].disabled = True
            await interaction.message.edit(view=self)
        else:
            embed = discord.Embed(
                title="Geçersiz Kod",
                description=f"Habsen profilindeki motto kısmı **{self.code}** kodunu içermiyor.\n"
                            f"1. Profiline git: https://habsen.com.tr/profile/{self.username}\n"
                            f"2. Motto kısmına sadece **{self.code}** yaz.\n"
                            f"3. Profili kaydet ve tekrar 'Kontrol Et' butonuna bas.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)

class Registration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verification_codes = {}

    @app_commands.command(name="kayıt", description="Habsen kullanıcı adınızı doğrulayın")
    @app_commands.describe(username="Habsen kullanıcı adınız")
    async def register(self, interaction: discord.Interaction, username: str):
        REGISTRATION_CHANNEL_ID = int(os.getenv("REGISTRATION_CHANNEL_ID"))
        if interaction.channel_id != REGISTRATION_CHANNEL_ID:
            embed = discord.Embed(
                title="Hatalı Kanal",
                description=f"Doğrulama işlemi sadece <#{REGISTRATION_CHANNEL_ID}> kanalında yapılabilir.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        is_valid = await check_username_validity(username)
        if not is_valid:
            embed = discord.Embed(
                title="Geçersiz Kullanıcı Adı",
                description=f"**{username}** adında bir Habsen kullanıcısı bulunamadı.\n"
                            f"Lütfen geçerli bir kullanıcı adı girin ve tekrar deneyin.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        role = interaction.guild.get_role(int(os.getenv("VERIFIED_ROLE_ID")))
        if role in interaction.user.roles:
            embed = discord.Embed(
                title="Zaten Doğrulanmış",
                description="Hesabınız zaten doğrulanmış ve **Doğrulanmış** rolüne sahipsiniz.",
                color=0xffff00,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        code = f"KOD-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
        self.verification_codes[interaction.user.id] = {
            "username": username,
            "code": code,
            "expires_at": datetime.now(ZoneInfo("UTC")).timestamp() + 15 * 60
        }

        embed = discord.Embed(
            title="Doğrulama Kodu",
            description=(
                f"Habsen hesabınızı doğrulamak için aşağıdaki adımları izleyin:\n"
                f"1. Profilinize gidin: https://habsen.com.tr/profile/{username}\n"
                f"2. Motto kısmına sadece **{code}** yazın.\n"
                f"3. Profilinizi kaydedin.\n"
                f"4. Ardından aşağıdaki **Kontrol Et** butonuna basın.\n"
                f"*Bu kod 15 dakika geçerlidir.*"
            ),
            color=0x800080,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        view = VerifyButton(interaction.user.id, username, code, self.verification_codes)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Registration(bot))
