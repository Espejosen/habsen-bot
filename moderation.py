import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import aiosqlite
import json
import os

class WarningListView(discord.ui.View):
    def __init__(self, warnings, user, moderator, page=0):
        super().__init__(timeout=120)
        self.warnings = warnings
        self.user = user
        self.moderator = moderator
        self.page = page
        self.per_page = 5
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = self.page == 0
        self.children[1].disabled = (self.page + 1) * self.per_page >= len(self.warnings)

    def get_page_content(self):
        start = self.page * self.per_page
        end = start + self.per_page
        page_warnings = self.warnings[start:end]
        content = ""
        for warning in page_warnings:
            warning_id = warning[0]
            violation_type = warning[3].replace("_", " ").title()
            reason = warning[4]
            timestamp = datetime.fromisoformat(warning[6])
            content += f"**ID:** {warning_id} | **İhlal:** {violation_type}\n**Sebep:** {reason}\n**Tarih:** {timestamp.strftime('%Y-%m-%d %H:%M')}\n\n"
        return content if content else "Bu sayfada uyarı yok."

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message("Bu işlemi yalnızca işlemi başlatan moderatör yapabilir!", ephemeral=True)
            return
        self.page -= 1
        self.update_buttons()
        embed = discord.Embed(
            title=f"{self.user.display_name} - Uyarı Listesi",
            description=self.get_page_content(),
            color=0x800080,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.set_footer(text=f"Sayfa {self.page + 1}/{max(1, (len(self.warnings) + self.per_page - 1) // self.per_page)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message("Bu işlemi yalnızca işlemi başlatan moderatör yapabilir!", ephemeral=True)
            return
        self.page += 1
        self.update_buttons()
        embed = discord.Embed(
            title=f"{self.user.display_name} - Uyarı Listesi",
            description=self.get_page_content(),
            color=0x800080,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.set_footer(text=f"Sayfa {self.page + 1}/{max(1, (len(self.warnings) + self.per_page - 1) // self.per_page)}")
        await interaction.response.edit_message(embed=embed, view=self)

class UserInfoView(discord.ui.View):
    def __init__(self, user, moderator):
        super().__init__(timeout=120)
        self.user = user
        self.moderator = moderator
        self.VIOLATION_RULES = {
            "ailevi_kufur": [
                {"count": 1, "action": "warn", "description": "Uyarı"},
                {"count": 2, "action": "timeout", "duration": 3600, "description": "1 saat mute"}
            ],
            "dini_hakaret": [
                {"count": 1, "action": "timeout", "duration": 43200, "description": "12 saat mute"}
            ],
            "spam_flood": [
                {"count": 1, "action": "warn", "description": "Uyarı"},
                {"count": 2, "action": "timeout", "duration": 900, "description": "15 dakika mute"},
                {"count": 3, "action": "timeout", "duration": 3600, "description": "1 saat mute"}
            ],
            "irkcilik_ayrimcilik": [
                {"count": 1, "action": "warn", "description": "Uyarı"},
                {"count": 2, "action": "timeout", "duration": 7200, "description": "2 saat mute"},
                {"count": 3, "action": "timeout", "duration": 86400, "description": "1 gün mute"}
            ],
            "kufurlu_konusma": [
                {"count": 1, "action": "warn", "description": "Uyarı"},
                {"count": 2, "action": "timeout", "duration": 900, "description": "15 dakika mute"},
                {"count": 3, "action": "timeout", "duration": 10800, "description": "3 saat mute"}
            ],
            "kullanici_taklidi": [
                {"count": 1, "action": "timeout", "duration": 7200, "description": "2 saat mute"}
            ],
            "kiskirtma": [
                {"count": 1, "action": "warn", "description": "Uyarı"},
                {"count": 2, "action": "timeout", "duration": 10800, "description": "3 saat mute"}
            ],
            "cinsel_icerik": [
                {"count": 1, "action": "warn", "description": "Uyarı"},
                {"count": 2, "action": "timeout", "duration": 14400, "description": "4 saat mute"}
            ],
            "ahlak_aykiri": [
                {"count": 1, "action": "warn", "description": "Uyarı"},
                {"count": 2, "action": "timeout", "duration": 10800, "description": "3 saat mute"}
            ]
        }
        self.CEZA_TURLERI = [
            app_commands.Choice(name=name, value=value) for name, value in [
                ("Ailevi Küfür/Hakaret", "ailevi_kufur"),
                ("Dini Değerlere Hakaret", "dini_hakaret"),
                ("Spam/Flood", "spam_flood"),
                ("Irkçılık/Ayrımcılık", "irkcilik_ayrimcilik"),
                ("Küfürlü Konuşma", "kufurlu_konusma"),
                ("Kullanıcı Taklidi", "kullanici_taklidi"),
                ("Topluluğu Kışkırtma", "kiskirtma"),
                ("Cinsel İçerikli Sohbet", "cinsel_icerik"),
                ("Genel Ahlaka Aykırı Davranış", "ahlak_aykiri")
            ]
        ]

    async def check_permissions(self, interaction: discord.Interaction):
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message("Bu işlemi yalnızca işlemi başlatan moderatör yapabilir!", ephemeral=True)
            return False
        if self.user.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("Bu kullanıcı botun rolünden yüksek, işlem yapılamaz!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Uyarı Ekle", style=discord.ButtonStyle.red)
    async def warn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        class WarnSelect(discord.ui.View):
            def __init__(self, user, apply_punishment, log_warning):
                super().__init__(timeout=60)
                self.user = user
                self.apply_punishment = apply_punishment
                self.log_warning = log_warning

            @discord.ui.select(
                placeholder="Ceza Türü Seçin",
                options=[
                    discord.SelectOption(label="Ailevi Küfür/Hakaret", value="ailevi_kufur"),
                    discord.SelectOption(label="Dini Değerlere Hakaret", value="dini_hakaret"),
                    discord.SelectOption(label="Spam/Flood", value="spam_flood"),
                    discord.SelectOption(label="Irkçılık/Ayrımcılık", value="irkcilik_ayrimcilik"),
                    discord.SelectOption(label="Küfürlü Konuşma", value="kufurlu_konusma"),
                    discord.SelectOption(label="Kullanıcı Taklidi", value="kullanici_taklidi"),
                    discord.SelectOption(label="Topluluğu Kışkırtma", value="kiskirtma"),
                    discord.SelectOption(label="Cinsel İçerikli Sohbet", value="cinsel_icerik"),
                    discord.SelectOption(label="Genel Ahlaka Aykırı Davranış", value="ahlak_aykiri")
                ]
            )
            async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
                await interaction.response.defer(ephemeral=True)
                violation_type = select.values[0]
                async with aiosqlite.connect("warnings.db") as db:
                    expires_at = (datetime.now(ZoneInfo("UTC")) + timedelta(days=1)).isoformat()
                    await db.execute('''
                        INSERT INTO warnings (user_id, guild_id, violation_type, reason, moderator_id, timestamp, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (self.user.id, interaction.guild_id, violation_type, 
                          f"{violation_type.replace('_', ' ').title()} nedeniyle uyarı", 
                          interaction.user.id, datetime.now(ZoneInfo("UTC")).isoformat(), expires_at))
                    await db.commit()
                    cursor = await db.execute('''
                        SELECT COUNT(*) FROM warnings 
                        WHERE user_id = ? AND guild_id = ? AND violation_type = ? AND expires_at > ?
                    ''', (self.user.id, interaction.guild_id, violation_type, datetime.now(ZoneInfo("UTC")).isoformat()))
                    warn_count = (await cursor.fetchone())[0]

                action, action_description = await self.apply_punishment(self.user, violation_type, warn_count, interaction)
                await self.log_warning(interaction.guild, self.user, violation_type, 
                                      f"{violation_type.replace('_', ' ').title()} nedeniyle uyarı", 
                                      action, interaction.user)
                embed = discord.Embed(
                    title="Uyarı Uygulandı",
                    description=f"{self.user.mention} uyarıldı. **Ceza:** {action_description}",
                    color=0x00ff00,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.set_footer(text="Habsen Topluluğu")
                await interaction.followup.send(embed=embed, ephemeral=True)

        view = WarnSelect(self.user, self.apply_punishment, self.log_warning)
        embed = discord.Embed(
            title="Ceza Türü Seçimi",
            description="Aşağıdan bir ceza türü seçin.",
            color=0xffff00,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Jail", style=discord.ButtonStyle.red)
    async def jail(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT * FROM jails 
                WHERE user_id = ? AND guild_id = ? AND end_time > ?
            ''', (self.user.id, interaction.guild_id, datetime.now(ZoneInfo("UTC")).isoformat()))
            existing_jail = await cursor.fetchone()

        if existing_jail:
            end_time = datetime.fromisoformat(existing_jail[5])
            remaining_time = (end_time - datetime.now(ZoneInfo("UTC"))).total_seconds()
            hours, remainder = divmod(int(remaining_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            embed = discord.Embed(
                title="Hata",
                description=f"{self.user.mention} zaten jail'de! Kalan süre: {hours:02d}:{minutes:02d}:{seconds:02d}",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        class JailDurationSelect(discord.ui.View):
            def __init__(self, user):
                super().__init__(timeout=60)
                self.user = user

            @discord.ui.select(
                placeholder="Jail Süresi Seçin",
                options=[
                    discord.SelectOption(label="1 Saat", value="3600"),
                    discord.SelectOption(label="6 Saat", value="21600"),
                    discord.SelectOption(label="1 Gün", value="86400")
                ]
            )
            async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
                await interaction.response.defer(ephemeral=True)
                duration = int(select.values[0])
                start_time = datetime.now(ZoneInfo("UTC"))
                end_time = start_time + timedelta(seconds=duration)

                original_roles = [role.id for role in self.user.roles if role != interaction.guild.default_role]
                original_roles_json = json.dumps(original_roles)

                jail_role = interaction.guild.get_role(int(os.getenv("JAIL_ROLE_ID")))
                if not jail_role:
                    embed = discord.Embed(
                        title="Hata",
                        description="Jail rolü bulunamadı! Lütfen JAIL_ROLE_ID'yi kontrol edin.",
                        color=0xff0000,
                        timestamp=datetime.now(ZoneInfo("UTC"))
                    )
                    embed.set_footer(text="Habsen Topluluğu")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                await self.user.edit(roles=[jail_role], reason="Moderatör tarafından jail'e atıldı")

                async with aiosqlite.connect("warnings.db") as db:
                    await db.execute('''
                        INSERT INTO jails (user_id, guild_id, moderator_id, start_time, end_time, original_roles)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (self.user.id, interaction.guild_id, interaction.user.id, 
                          start_time.isoformat(), end_time.isoformat(), original_roles_json))
                    await db.commit()

                log_channel = interaction.guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
                if log_channel:
                    embed = discord.Embed(
                        title="Kullanıcı Jail'e Atıldı",
                        description=f"{self.user.mention} jail'e atıldı!",
                        color=0xff4500,
                        timestamp=datetime.now(ZoneInfo("UTC"))
                    )
                    embed.add_field(name="Kullanıcı", value=self.user.mention)
                    embed.add_field(name="Sebep", value=f"Moderatör tarafından jail'e atıldı (Süre: {duration//3600} saat)")
                    embed.add_field(name="Moderatör", value=interaction.user.mention)
                    embed.set_footer(text="Habsen Topluluğu")
                    await log_channel.send(embed=embed)

                embed = discord.Embed(
                    title="Jail Uygulandı",
                    description=f"{self.user.mention} {duration//3600} saat süreyle jail'e atıldı.",
                    color=0x00ff00,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.set_footer(text="Habsen Topluluğu")
                await interaction.followup.send(embed=embed, ephemeral=True)

        view = JailDurationSelect(self.user)
        embed = discord.Embed(
            title="Jail Süresi Seçimi",
            description="Aşağıdan bir jail süresi seçin.",
            color=0xffff00,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.red)
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await self.user.kick(reason="Moderatör tarafından atıldı")
            log_channel = interaction.guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
            if log_channel:
                embed = discord.Embed(
                    title="Kullanıcı Atıldı",
                    description=f"{self.user.mention} sunucudan atıldı!",
                    color=0xff0000,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.add_field(name="Kullanıcı", value=self.user.mention)
                embed.add_field(name="Sebep", value="Kullanıcı atıldı")
                embed.add_field(name="Moderatör", value=interaction.user.mention)
                embed.set_footer(text="Habsen Topluluğu")
                await log_channel.send(embed=embed)
            embed = discord.Embed(
                title="Kullanıcı Atıldı",
                description=f"{self.user.mention} sunucudan atıldı.",
                color=0x00ff00,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="Hata",
                description="Kullanıcıyı atma iznim yok!",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Mute", style=discord.ButtonStyle.red)
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            duration = 900
            until = datetime.now(ZoneInfo("UTC")) + timedelta(seconds=duration)
            await self.user.timeout(until, reason="Moderatör tarafından susturuldu")
            log_channel = interaction.guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
            if log_channel:
                embed = discord.Embed(
                    title="Zaman Aşımı Uygulandı",
                    description=f"{self.user.mention} susturuldu!",
                    color=0xffa500,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.add_field(name="Kullanıcı", value=self.user.mention)
                embed.add_field(name="Sebep", value="15 dakika susturuldu")
                embed.add_field(name="Moderatör", value=interaction.user.mention)
                embed.set_footer(text="Habsen Topluluğu")
                await log_channel.send(embed=embed)
            embed = discord.Embed(
                title="Zaman Aşımı Uygulandı",
                description=f"{self.user.mention} 15 dakika susturuldu.",
                color=0x00ff00,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="Hata",
                description="Kullanıcıyı susturma iznim yok!",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.red)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await self.user.ban(reason="Moderatör tarafından banlandı")
            log_channel = interaction.guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
            if log_channel:
                embed = discord.Embed(
                    title="Kullanıcı Banlandı",
                    description=f"{self.user.mention} sunucudan banlandı!",
                    color=0xff0000,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.add_field(name="Kullanıcı", value=self.user.mention)
                embed.add_field(name="Sebep", value="Kullanıcı banlandı")
                embed.add_field(name="Moderatör", value=interaction.user.mention)
                embed.set_footer(text="Habsen Topluluğu")
                await log_channel.send(embed=embed)
            embed = discord.Embed(
                title="Kullanıcı Banlandı",
                description=f"{self.user.mention} sunucudan banlandı.",
                color=0x00ff00,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="Hata",
                description="Kullanıcıyı banlama iznim yok!",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="ID Göster", style=discord.ButtonStyle.grey)
    async def show_id(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message("Bu işlemi yalnızca işlemi başlatan moderatör yapabilir!", ephemeral=True)
            return
        await interaction.response.send_message(f"Kullanıcı ID: {self.user.id}", ephemeral=True)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.grey)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message("Bu işlemi yalnızca işlemi başlatan moderatör yapabilir!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        member = await interaction.guild.fetch_member(self.user.id)
        embed, view = await self.get_user_info_embed(member, interaction.user)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Avatar", style=discord.ButtonStyle.grey)
    async def avatar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message("Bu işlemi yalnızca işlemi başlatan moderatör yapabilir!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title=f"{self.user.display_name} - Avatar", 
                             color=0x800080, 
                             timestamp=datetime.now(ZoneInfo("UTC")))
        embed.set_image(url=self.user.display_avatar.url)
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Moderations", style=discord.ButtonStyle.grey)
    async def moderations(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message("Bu işlemi yalnızca işlemi başlatan moderatör yapabilir!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT * FROM warnings 
                WHERE user_id = ? AND guild_id = ? AND expires_at > ?
            ''', (self.user.id, interaction.guild_id, datetime.now(ZoneInfo("UTC")).isoformat()))
            warnings = await cursor.fetchall()
        view = WarningListView(warnings, self.user, interaction.user)
        embed = discord.Embed(
            title=f"{self.user.display_name} - Uyarı Listesi",
            description=view.get_page_content(),
            color=0x800080,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.set_footer(text=f"Sayfa 1/{max(1, (len(warnings) + view.per_page - 1) // view.per_page)}")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def get_user_info_embed(self, member, moderator):
        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT COUNT(*) FROM warnings 
                WHERE user_id = ? AND guild_id = ? AND expires_at > ?
            ''', (member.id, member.guild.id, datetime.now(ZoneInfo("UTC")).isoformat()))
            warn_count = (await cursor.fetchone())[0]
        roles = ", ".join([role.mention for role in member.roles if role != member.guild.default_role]) or "Rol yok"
        embed = discord.Embed(
            title=f"{member.display_name} - Kullanıcı Bilgileri",
            color=0x800080,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Kullanıcı", value=member.mention, inline=False)
        embed.add_field(name="Sunucuya Katılım", value=member.joined_at.strftime('%Y-%m-%d %H:%M'), inline=False)
        embed.add_field(name="Roller", value=roles, inline=False)
        embed.add_field(name="Uyarı Sayısı", value=str(warn_count), inline=False)
        embed.set_footer(text="Habsen Topluluğu")
        return embed, self

    async def apply_punishment(self, member: discord.Member, violation_type: str, warn_count: int, interaction: discord.Interaction):
        rules = self.VIOLATION_RULES.get(violation_type, [])
        for rule in rules:
            if warn_count == rule["count"]:
                action = rule["action"]
                description = rule["description"]
                duration = rule.get("duration")
                if action == "warn":
                    return "warn", description
                elif action == "timeout":
                    try:
                        until = datetime.now(ZoneInfo("UTC")) + timedelta(seconds=duration)
                        await member.timeout(until, reason=description)
                        return "timeout", description
                    except discord.Forbidden:
                        return "error", f"{member.mention} için ceza uygulanamadı! Botun izinlerini kontrol edin."
        return "warn", "Uyarı"

    async def log_warning(self, guild: discord.Guild, user: discord.Member, violation_type: str, reason: str, action: str, moderator: discord.Member):
        log_channel = guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
        if not log_channel:
            return
        violation_display = violation_type.replace("_", " ").title()
        embed = discord.Embed(timestamp=datetime.now(ZoneInfo("UTC")))
        embed.set_footer(text="Habsen Topluluğu")
        if action == "warn":
            embed.title = "Uyarı Verildi"
            embed.description = f"{user.mention} {violation_display.lower()} nedeniyle uyarı aldı!"
            embed.color = 0xffff00
        elif action == "timeout":
            embed.title = "Zaman Aşımı Uygulandı"
            embed.description = f"{user.mention} {violation_display.lower()} nedeniyle susturuldu!"
            embed.color = 0xffa500
        elif action == "kick":
            embed.title = "Kullanıcı Atıldı"
            embed.description = f"{user.mention} sunucudan atıldı!"
            embed.color = 0xff0000
        elif action == "ban":
            embed.title = "Kullanıcı Banlandı"
            embed.description = f"{user.mention} sunucudan banlandı!"
            embed.color = 0xff0000
        elif action == "jail":
            embed.title = "Kullanıcı Jail'e Atıldı"
            embed.description = f"{user.mention} jail'e atıldı!"
            embed.color = 0xff4500
        elif action == "error":
            embed.title = "İşlem Başarısız"
            embed.description = reason
            embed.color = 0x808080
        embed.add_field(name="Kullanıcı", value=user.mention)
        embed.add_field(name="Sebep", value=reason)
        embed.add_field(name="Moderatör", value=moderator.mention)
        await log_channel.send(embed=embed)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_jails.start()

    async def check_moderator(self, interaction: discord.Interaction):
        moderator_role = interaction.guild.get_role(int(os.getenv("MODERATOR_ROLE_ID")))
        if not moderator_role or moderator_role not in interaction.user.roles:
            embed = discord.Embed(
                title="Yetkisiz İşlem",
                description="Bu komutu kullanmak için yetkili rolüne sahip olmalısınız.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    @app_commands.command(name="warn", description="Bir kullanıcıyı belirli bir ihlal türüyle uyarır")
    @app_commands.describe(violation_type="İhlal türü", member="Uyarılacak kullanıcı")
    @app_commands.choices(violation_type=[
        app_commands.Choice(name=name, value=value) for name, value in [
            ("Ailevi Küfür/Hakaret", "ailevi_kufur"),
            ("Dini Değerlere Hakaret", "dini_hakaret"),
            ("Spam/Flood", "spam_flood"),
            ("Irkçılık/Ayrımcılık", "irkcilik_ayrimcilik"),
            ("Küfürlü Konuşma", "kufurlu_konusma"),
            ("Kullanıcı Taklidi", "kullanici_taklidi"),
            ("Topluluğu Kışkırtma", "kiskirtma"),
            ("Cinsel İçerikli Sohbet", "cinsel_icerik"),
            ("Genel Ahlaka Aykırı Davranış", "ahlak_aykiri")
        ]
    ])
    async def warn(self, interaction: discord.Interaction, violation_type: str, member: discord.Member):
        if not await self.check_moderator(interaction):
            return
        if member.bot or member == interaction.user or member.top_role >= interaction.guild.me.top_role:
            embed = discord.Embed(
                title="Hata",
                description="Bu kullanıcıyı uyaramazsınız (bot, kendiniz veya botun rolünden yüksek).",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        reason = f"{violation_type.replace('_', ' ').title()} nedeniyle uyarı"
        async with aiosqlite.connect("warnings.db") as db:
            expires_at = (datetime.now(ZoneInfo("UTC")) + timedelta(days=1)).isoformat()
            await db.execute('''
                INSERT INTO warnings (user_id, guild_id, violation_type, reason, moderator_id, timestamp, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (member.id, interaction.guild_id, violation_type, reason, interaction.user.id, 
                  datetime.now(ZoneInfo("UTC")).isoformat(), expires_at))
            await db.commit()
            cursor = await db.execute('''
                SELECT COUNT(*) FROM warnings 
                WHERE user_id = ? AND guild_id = ? AND violation_type = ? AND expires_at > ?
            ''', (member.id, interaction.guild_id, violation_type, datetime.now(ZoneInfo("UTC")).isoformat()))
            warn_count = (await cursor.fetchone())[0]

        await interaction.response.defer(ephemeral=True)
        view = UserInfoView(member, interaction.user)
        action, action_description = await view.apply_punishment(member, violation_type, warn_count, interaction)
        await view.log_warning(interaction.guild, member, violation_type, reason, action, interaction.user)

        embed = discord.Embed(
            title="Uyarı Uygulandı",
            description=f"{member.mention} uyarıldı.\n**İhlal**: {violation_type.replace('_', ' ').title()}\n**Ceza**: {action_description}\n**Uyarı Sayısı**: {warn_count}",
            color=0x00ff00,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.followup.send(embed=embed, ephemeral=True)

        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT COUNT(*) FROM warnings 
                WHERE user_id = ? AND guild_id = ? AND expires_at > ?
            ''', (member.id, interaction.guild_id, datetime.now(ZoneInfo("UTC")).isoformat()))
            total_warnings = (await cursor.fetchone())[0]

        if total_warnings >= 3:
            try:
                duration = 900
                until = datetime.now(ZoneInfo("UTC")) + timedelta(seconds=duration)
                await member.timeout(until, reason="3 uyarıya ulaşıldı")
                await view.log_warning(interaction.guild, member, "otomatik_timeout", "3 uyarıya ulaşıldı", "timeout", interaction.user)
            except discord.Forbidden:
                pass

    @app_commands.command(name="user", description="Bir kullanıcının bilgilerini gösterir")
    @app_commands.describe(member="Bilgileri görüntülenecek kullanıcı")
    async def user(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.check_moderator(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        view = UserInfoView(member, interaction.user)
        embed, view = await view.get_user_info_embed(member, interaction.user)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="warnlist", description="Bir kullanıcının uyarılarını listeler")
    @app_commands.describe(member="Uyarıları görüntülenecek kullanıcı")
    async def warnlist(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.check_moderator(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT * FROM warnings 
                WHERE user_id = ? AND guild_id = ? AND expires_at > ?
            ''', (member.id, interaction.guild_id, datetime.now(ZoneInfo("UTC")).isoformat()))
            warnings = await cursor.fetchall()
        view = WarningListView(warnings, member, interaction.user)
        embed = discord.Embed(
            title=f"{member.display_name} - Uyarı Listesi",
            description=view.get_page_content(),
            color=0x800080,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Sayfa 1/{max(1, (len(warnings) + view.per_page - 1) // view.per_page)}")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="unwarn", description="Bir kullanıcının uyarısını kaldırır")
    @app_commands.describe(member="Uyarısı kaldırılacak kullanıcı")
    async def unwarn(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.check_moderator(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT * FROM warnings 
                WHERE user_id = ? AND guild_id = ? AND expires_at > ?
            ''', (member.id, interaction.guild_id, datetime.now(ZoneInfo("UTC")).isoformat()))
            warnings = await cursor.fetchall()

        if not warnings:
            embed = discord.Embed(
                title="Hata",
                description=f"{member.mention} kullanıcısının aktif uyarısı bulunamadı.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        class UnwarnSelect(discord.ui.View):
            def __init__(self, warnings, user, moderator):
                super().__init__(timeout=60)
                self.warnings = warnings
                self.user = user
                self.moderator = moderator

            @discord.ui.select(
                placeholder="Kaldırılacak Uyarıyı Seçin",
                options=[
                    discord.SelectOption(
                        label=f"ID: {w[0]} - {w[3].replace('_', ' ').title()}",
                        value=str(w[0]),
                        description=f"Sebep: {w[4][:50]}..."
                    ) for w in self.warnings
                ]
            )
            async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
                await interaction.response.defer(ephemeral=True)
                if interaction.user.id != self.moderator.id:
                    embed = discord.Embed(
                        title="Hata",
                        description="Bu işlemi yalnızca işlemi başlatan moderatör yapabilir!",
                        color=0xff0000,
                        timestamp=datetime.now(ZoneInfo("UTC"))
                    )
                    embed.set_footer(text="Habsen Topluluğu")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                warning_id = int(select.values[0])
                async with aiosqlite.connect("warnings.db") as db:
                    await db.execute('DELETE FROM warnings WHERE id = ?', (warning_id,))
                    await db.commit()

                log_channel = interaction.guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
                if log_channel:
                    embed = discord.Embed(
                        title="Uyarı Kaldırıldı",
                        description=f"{self.user.mention} kullanıcısının uyarısı kaldırıldı.",
                        color=0x00ff00,
                        timestamp=datetime.now(ZoneInfo("UTC"))
                    )
                    embed.add_field(name="Uyarı ID", value=str(warning_id))
                    embed.add_field(name="Moderatör", value=interaction.user.mention)
                    embed.set_footer(text="Habsen Topluluğu")
                    await log_channel.send(embed=embed)

                embed = discord.Embed(
                    title="Uyarı Kaldırıldı",
                    description=f"{self.user.mention} kullanıcısının uyarısı kaldırıldı.",
                    color=0x00ff00,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.set_footer(text="Habsen Topluluğu")
                await interaction.followup.send(embed=embed, view=None)

        view = UnwarnSelect(warnings, member, interaction.user)
        embed = discord.Embed(
            title="Uyarı Seçimi",
            description="Aşağıdan kaldırılacak uyarıyı seçin.",
            color=0xffff00,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="unjail", description="Bir kullanıcının jail durumunu kaldırır")
    @app_commands.describe(member="Jail'den çıkarılacak kullanıcı")
    async def unjail(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.check_moderator(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT * FROM jails 
                WHERE user_id = ? AND guild_id = ? AND end_time > ?
            ''', (member.id, interaction.guild_id, datetime.now(ZoneInfo("UTC")).isoformat()))
            jail = await cursor.fetchone()

        if not jail:
            embed = discord.Embed(
                title="Hata",
                description=f"{member.mention} şu anda jail'de değil!",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        jail_role = interaction.guild.get_role(int(os.getenv("JAIL_ROLE_ID")))
        if jail_role in member.roles:
            await member.remove_roles(jail_role, reason="Moderatör tarafından jail kaldırıldı")

        original_roles = json.loads(jail[6])
        roles = [interaction.guild.get_role(role_id) for role_id in original_roles if interaction.guild.get_role(role_id)]
        if roles:
            await member.add_roles(*roles, reason="Jail kaldırıldı, eski roller geri yüklendi")

        async with aiosqlite.connect("warnings.db") as db:
            await db.execute('DELETE FROM jails WHERE id = ?', (jail[0],))
            await db.commit()

        log_channel = interaction.guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
        if log_channel:
            embed = discord.Embed(
                title="Jail Kaldırıldı",
                description=f"{member.mention} jail'den çıkarıldı!",
                color=0x00ff00,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.add_field(name="Kullanıcı", value=member.mention)
            embed.add_field(name="Moderatör", value=interaction.user.mention)
            embed.set_footer(text="Habsen Topluluğu")
            await log_channel.send(embed=embed)

        embed = discord.Embed(
            title="Jail Kaldırıldı",
            description=f"{member.mention} jail'den çıkarıldı.",
            color=0x00ff00,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @tasks.loop(minutes=1)
    async def check_jails(self):
        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT * FROM jails 
                WHERE end_time <= ?
            ''', (datetime.now(ZoneInfo("UTC")).isoformat(),))
            expired_jails = await cursor.fetchall()

        for jail in expired_jails:
            guild = self.bot.get_guild(jail[2])
            if not guild:
                continue
            member = await guild.fetch_member(jail[1])
            if not member:
                continue

            jail_role = guild.get_role(int(os.getenv("JAIL_ROLE_ID")))
            if jail_role in member.roles:
                await member.remove_roles(jail_role, reason="Jail süresi doldu")

            original_roles = json.loads(jail[6])
            roles = [guild.get_role(role_id) for role_id in original_roles if guild.get_role(role_id)]
            if roles:
                await member.add_roles(*roles, reason="Jail süresi doldu, eski roller geri yüklendi")

            async with aiosqlite.connect("warnings.db") as db:
                await db.execute('DELETE FROM jails WHERE id = ?', (jail[0],))
                await db.commit()

            log_channel = guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
            if log_channel:
                embed = discord.Embed(
                    title="Jail Süresi Doldu",
                    description=f"{member.mention} kullanıcısının jail süresi doldu ve serbest bırakıldı.",
                    color=0x00ff00,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.set_footer(text="Habsen Topluluğu")
                await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        log_channel = member.guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
        if log_channel:
            embed = discord.Embed(
                title="Yeni Üye Katıldı",
                description=f"{member.mention} sunucuya katıldı!",
                color=0x00ff00,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.add_field(name="Kullanıcı", value=f"{member.name}#{member.discriminator}")
            embed.add_field(name="Katılım Tarihi", value=member.joined_at.strftime('%Y-%m-%d %H:%M'))
            embed.set_footer(text="Habsen Topluluğu")
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        log_channel = member.guild.get_channel(int(os.getenv("LOG_CHANNEL_ID")))
        if log_channel:
            embed = discord.Embed(
                title="Üye Ayrıldı",
                description=f"{member.mention} sunucudan ayrıldı.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.add_field(name="Kullanıcı", value=f"{member.name}#{member.discriminator}")
            embed.set_footer(text="Habsen Topluluğu")
            await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))

