import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import aiosqlite
import os

class BadgeRequestView(discord.ui.View):
    def __init__(self, pending_badge_requests):
        super().__init__(timeout=None)
        self.pending_badge_requests = pending_badge_requests

    @discord.ui.button(label="Rozet Talebi Oluştur", style=discord.ButtonStyle.primary, custom_id="badge_create_button")
    async def create_badge(self, interaction: discord.Interaction):
        BADGE_REQUEST_CHANNEL_ID = int(os.getenv("BADGE_REQUEST_CHANNEL_ID"))
        if interaction.channel_id != BADGE_REQUEST_CHANNEL_ID:
            embed = discord.Embed(
                title="Hatalı Kanal",
                description="Bu buton sadece rozet talebi kanalında kullanılabilir.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.pending_badge_requests[interaction.user.id] = datetime.now(ZoneInfo("UTC")).timestamp() + 5 * 60

        embed = discord.Embed(
            title="Rozet Talebi Oluşturma",
            description=(
                f"Lütfen {interaction.channel.mention} kanalına bir **PNG veya JPG** görseli yükleyin.\n"
                "- Görseliniz otomatik olarak silinecek ve bir talep formu gönderilecektir.\n"
                "- Saatte en fazla 3 talep gönderebilirsiniz.\n"
                "- Bu talimat 5 dakika geçerlidir, ardından tekrar butona tıklayın."
            ),
            color=0x800080,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Rozet Durum", style=discord.ButtonStyle.secondary, custom_id="badge_status_button")
    async def badge_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT id, status, submitted_at, reason FROM badges 
                WHERE user_id = ? AND guild_id = ?
                ORDER BY submitted_at DESC
            ''', (interaction.user.id, interaction.guild_id))
            badges = await cursor.fetchall()

        if not badges:
            embed = discord.Embed(
                title="Rozet Talebi Bulunamadı",
                description="Henüz rozet talebi göndermediniz.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="Rozet Talepleriniz",
            description="Aşağıda rozet taleplerinizin durumu listeleniyor.",
            color=0x800080,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        for badge in badges:
            status = {"pending": "Beklemede ⏳", "approved": "Onaylandı ✅", "rejected": "Reddedildi ❌"}[badge[1]]
            submitted_at = datetime.fromisoformat(badge[2]).strftime('%Y-%m-%d %H:%M')
            reason = f"\n**Sebep**: {badge[3]}" if badge[3] and badge[1] == "rejected" else ""
            embed.add_field(
                name=f"Talep ID: {badge[0]}",
                value=f"**Durum**: {status}\n**Gönderilme**: {submitted_at}{reason}",
                inline=False
            )
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Rozet İptal", style=discord.ButtonStyle.red, custom_id="badge_cancel_button")
    async def badge_cancel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT id, submitted_at FROM badges 
                WHERE user_id = ? AND guild_id = ? AND status = 'pending'
                ORDER BY submitted_at DESC
            ''', (interaction.user.id, interaction.guild_id))
            badges = await cursor.fetchall()

        if not badges:
            embed = discord.Embed(
                title="Beklemede Talep Yok",
                description="İptal edilecek beklemede rozet talebiniz bulunamadı.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        class CancelSelect(discord.ui.View):
            def __init__(self, badges, user):
                super().__init__(timeout=60)
                self.user = user
                self.add_item(discord.ui.Select(
                    placeholder="İptal Edilecek Talebi Seçin",
                    options=[
                        discord.SelectOption(
                            label=f"ID: {badge[0]} - Gönderilme: {datetime.fromisoformat(badge[1]).strftime('%Y-%m-%d %H:%M')}",
                            value=str(badge[0])
                        ) for badge in badges
                    ],
                    custom_id="cancel_badge_select"
                ))

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                return interaction.user.id == self.user.id

            @discord.ui.button(label="İptal Et", style=discord.ButtonStyle.red)
            async def confirm_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                badge_id = int(self.children[0].values[0])
                async with aiosqlite.connect("warnings.db") as db:
                    cursor = await db.execute('SELECT message_id FROM badges WHERE id = ?', (badge_id,))
                    message_id = (await cursor.fetchone())[0]
                    await db.execute('DELETE FROM badges WHERE id = ?', (badge_id,))
                    await db.commit()

                if message_id:
                    log_channel = interaction.guild.get_channel(int(os.getenv("BADGE_MOD_LOG_CHANNEL_ID")))
                    if log_channel:
                        try:
                            log_message = await log_channel.fetch_message(message_id)
                            await log_message.delete()
                        except discord.NotFound:
                            pass

                embed = discord.Embed(
                    title="Rozet Talebi İptal Edildi",
                    description=f"Talep ID: {badge_id} başarıyla iptal edildi.",
                    color=0x00ff00,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.set_footer(text="Habsen Topluluğu")
                await interaction.response.edit_message(embed=embed, view=None)

        view = CancelSelect(badges, interaction.user)
        embed = discord.Embed(
            title="Rozet Talebi İptal",
            description="İptal etmek istediğiniz talebi seçin.",
            color=0xffff00,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class BadgeApprovalView(discord.ui.View):
    def __init__(self, badge_id, user):
        super().__init__(timeout=None)
        self.badge_id = badge_id
        self.user = user
        self.add_item(discord.ui.Button(
            label="Onayla",
            style=discord.ButtonStyle.green,
            custom_id=f"approve_badge_{self.badge_id}",
            callback=self.approve_badge
        ))
        self.add_item(discord.ui.Button(
            label="Reddet",
            style=discord.ButtonStyle.red,
            custom_id=f"reject_badge_{self.badge_id}",
            callback=self.reject_badge
        ))

    async def approve_badge(self, interaction: discord.Interaction, button: discord.ui.Button):
        moderator_role = interaction.guild.get_role(int(os.getenv("MODERATOR_ROLE_ID")))
        if not moderator_role or moderator_role not in interaction.user.roles:
            embed = discord.Embed(
                title="Yetkisiz İşlem",
                description="Bu işlemi yapmak için moderatör rolüne sahip olmalısınız.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('SELECT * FROM badges WHERE id = ?', (self.badge_id,))
            badge = await cursor.fetchone()
            if not badge or badge[4] != 'pending':
                embed = discord.Embed(
                    title="Hata",
                    description="Bu rozet talebi zaten işlenmiş veya bulunamadı.",
                    color=0xff0000,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.set_footer(text="Habsen Topluluğu")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await db.execute('''
                UPDATE badges 
                SET status = ?, moderator_id = ?, reviewed_at = ?
                WHERE id = ?
            ''', ('approved', interaction.user.id, datetime.now(ZoneInfo("UTC")).isoformat(), self.badge_id))
            await db.commit()

        try:
            embed = discord.Embed(
                title="Rozet Talebiniz Onaylandı",
                description="Rozet talebiniz moderatörler tarafından onaylandı. Rozetiniz hesabınıza eklendi!",
                color=0x00ff00,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await self.user.send(embed=embed)
        except discord.Forbidden:
            pass

        log_channel = interaction.guild.get_channel(int(os.getenv("BADGE_MOD_LOG_CHANNEL_ID")))
        if log_channel and badge[9]:
            try:
                original_message = await log_channel.fetch_message(badge[9])
                embed = discord.Embed(
                    title="Rozet Talebi Onaylandı",
                    description=f"{self.user.mention} kullanıcısının rozet talebi onaylandı.",
                    color=0x00ff00,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.add_field(name="Kullanıcı", value=self.user.mention)
                embed.add_field(name="Moderatör", value=interaction.user.mention)
                embed.set_image(url=badge[3])
                embed.set_footer(text=f"Talep ID: {self.badge_id} | Habsen Topluluğu")
                await original_message.reply(embed=embed)
                await interaction.response.edit_message(embed=embed, view=None)
            except discord.NotFound:
                embed = discord.Embed(
                    title="Rozet Talebi Onaylandı",
                    description=f"{self.user.mention} kullanıcısının rozet talebi onaylandı.",
                    color=0x00ff00,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.add_field(name="Kullanıcı", value=self.user.mention)
                embed.add_field(name="Moderatör", value=interaction.user.mention)
                embed.set_image(url=badge[3])
                embed.set_footer(text=f"Talep ID: {self.badge_id} | Habsen Topluluğu")
                await log_channel.send(embed=embed)
                await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = discord.Embed(
                title="Rozet Talebi Onaylandı",
                description=f"{self.user.mention} kullanıcısının rozet talebi onaylandı.",
                color=0x00ff00,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.add_field(name="Kullanıcı", value=self.user.mention)
            embed.add_field(name="Moderatör", value=interaction.user.mention)
            embed.set_image(url=badge[3])
            embed.set_footer(text=f"Talep ID: {self.badge_id} | Habsen Topluluğu")
            await interaction.response.edit_message(embed=embed, view=None)

    async def reject_badge(self, interaction: discord.Interaction, button: discord.ui.Button):
        moderator_role = interaction.guild.get_role(int(os.getenv("MODERATOR_ROLE_ID")))
        if not moderator_role or moderator_role not in interaction.user.roles:
            embed = discord.Embed(
                title="Yetkisiz İşlem",
                description="Bu işlemi yapmak için moderatör rolüne sahip olmalısınız.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        modal = discord.ui.Modal(title="Rozet Reddetme")
        modal.add_item(discord.ui.TextInput(
            label="Reddetme Sebebi",
            placeholder="Rozetin reddedilme sebebini yazın",
            required=True
        ))

        async def on_submit(modal_interaction: discord.Interaction):
            reason = modal_interaction.data['components'][0]['components'][0]['value']
            await modal_interaction.response.defer(ephemeral=True)

            async with aiosqlite.connect("warnings.db") as db:
                cursor = await db.execute('SELECT * FROM badges WHERE id = ?', (self.badge_id,))
                badge = await cursor.fetchone()
                if not badge or badge[4] != 'pending':
                    embed = discord.Embed(
                        title="Hata",
                        description="Bu rozet talebi zaten işlenmiş veya bulunamadı.",
                        color=0xff0000,
                        timestamp=datetime.now(ZoneInfo("UTC"))
                    )
                    embed.set_footer(text="Habsen Topluluğu")
                    await modal_interaction.followup.send(embed=embed, ephemeral=True)
                    return

                await db.execute('''
                    UPDATE badges 
                    SET status = ?, moderator_id = ?, reviewed_at = ?, reason = ?
                    WHERE id = ?
                ''', ('rejected', modal_interaction.user.id, datetime.now(ZoneInfo("UTC")).isoformat(), 
                      reason, self.badge_id))
                await db.commit()

            try:
                embed = discord.Embed(
                    title="Rozet Talebiniz Reddedildi",
                    description=f"Rozet talebiniz reddedildi.\n**Sebep**: {reason}",
                    color=0xff0000,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.set_footer(text="Habsen Topluluğu")
                await self.user.send(embed=embed)
            except discord.Forbidden:
                pass

            embed = discord.Embed(
                title="Rozet Talebi Reddedildi",
                description=f"{self.user.mention} kullanıcısının rozet talebi reddedildi.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.add_field(name="Kullanıcı", value=self.user.mention)
            embed.add_field(name="Moderatör", value=modal_interaction.user.mention)
            embed.add_field(name="Sebep", value=reason)
            embed.set_image(url=badge[3])
            embed.set_footer(text=f"Talep ID: {self.badge_id} | Habsen Topluluğu")
            await modal_interaction.followup.edit_message(message_id=modal_interaction.message.id, 
                                                        embed=embed, view=None)

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_badge_requests = {}
        self.TICKET_SYSTEMS = {
            "rozetbilgilendirme": {
                "name": "Rozet Bilgilendirme",
                "channel_id": int(os.getenv("BADGE_REQUEST_CHANNEL_ID")),
                "embed": {
                    "title": "Rozet Talebi",
                    "description": (
                        "Rozet talebi oluşturmak için aşağıdaki **Rozet Talebi Oluştur** butonuna tıklayın.\n"
                        "- Butona tıkladıktan sonra rozet talebi kanalına bir **PNG veya JPG** görseli yükleyin.\n"
                        "- Görseliniz otomatik olarak silinecek ve bir talep formu gönderilecektir.\n"
                        "- Saatte en fazla 3 talep gönderebilirsiniz.\n"
                        "- Talebiniz moderatörler tarafından incelenecek.\n"
                        "Rozet taleplerinizin durumunu kontrol etmek veya iptal etmek için diğer butonları kullanabilirsiniz."
                    ),
                    "color": 0x800080,
                    "footer": "Habsen Topluluğu"
                },
                "view": "BadgeRequestView"
            }
        }

    async def check_owner(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id:
            embed = discord.Embed(
                title="Yetkisiz İşlem",
                description="Bu komut yalnızca sunucu sahibi tarafından kullanılabilir.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    @app_commands.command(name="ticketsistem", description="Ticket sistemini seçilen kanala gönderir veya kaldırır (yalnızca sunucu sahibi)")
    async def ticketsistem(self, interaction: discord.Interaction):
        if not await self.check_owner(interaction):
            return

        class TicketSystemSelect(discord.ui.View):
            def __init__(self, owner_id):
                super().__init__(timeout=60)
                self.owner_id = owner_id
                self.add_item(discord.ui.Select(
                    placeholder="Bir ticket sistemi seçin",
                    options=[
                        discord.SelectOption(
                            label=system["name"],
                            value=system_id,
                            description=f"Kanal: <#{system['channel_id']}>"
                        ) for system_id, system in self.TICKET_SYSTEMS.items()
                    ],
                    custom_id="ticket_system_select"
                ))

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                return interaction.user.id == self.owner_id

            @discord.ui.button(label="Gönder", style=discord.ButtonStyle.green)
            async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.owner_id:
                    await interaction.response.send_message("Bu işlemi yalnızca sunucu sahibi yapabilir!", ephemeral=True)
                    return
                selected_system_id = self.children[0].values[0]
                system = self.TICKET_SYSTEMS[selected_system_id]
                
                channel = interaction.guild.get_channel(system["channel_id"])
                if not channel:
                    embed = discord.Embed(
                        title="Hata",
                        description=f"Kanal bulunamadı: <#{system['channel_id']}>",
                        color=0xff0000,
                        timestamp=datetime.now(ZoneInfo("UTC"))
                    )
                    embed.set_footer(text="Habsen Topluluğu")
                    await interaction.response.edit_message(embed=embed, view=None)
                    return

                async for message in channel.history(limit=100):
                    if message.author == interaction.client.user and system["embed"]["title"] in message.embeds[0].title:
                        await message.delete()

                embed = discord.Embed(
                    title=system["embed"]["title"],
                    description=system["embed"]["description"],
                    color=system["embed"]["color"],
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.set_footer(text=system["embed"]["footer"])
                view = BadgeRequestView(self.pending_badge_requests)
                message = await channel.send(embed=embed, view=view)
                interaction.client.persistent_views[message.id] = view

                embed = discord.Embed(
                    title="Ticket Sistemi Gönderildi",
                    description=f"{system['name']} ticket sistemi {channel.mention} kanalına gönderildi.",
                    color=0x00ff00,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.set_footer(text="Habsen Topluluğu")
                await interaction.response.edit_message(embed=embed, view=None)

            @discord.ui.button(label="Kaldır", style=discord.ButtonStyle.red)
            async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.owner_id:
                    await interaction.response.send_message("Bu işlemi yalnızca sunucu sahibi yapabilir!", ephemeral=True)
                    return
                selected_system_id = self.children[0].values[0]
                system = self.TICKET_SYSTEMS[selected_system_id]
                
                channel = interaction.guild.get_channel(system["channel_id"])
                if not channel:
                    embed = discord.Embed(
                        title="Hata",
                        description=f"Kanal bulunamadı: <#{system['channel_id']}>",
                        color=0xff0000,
                        timestamp=datetime.now(ZoneInfo("UTC"))
                    )
                    embed.set_footer(text="Habsen Topluluğu")
                    await interaction.response.edit_message(embed=embed, view=None)
                    return

                removed = False
                async for message in channel.history(limit=100):
                    if message.author == interaction.client.user and system["embed"]["title"] in message.embeds[0].title:
                        await message.delete()
                        if message.id in interaction.client.persistent_views:
                            del interaction.client.persistent_views[message.id]
                        removed = True
                        break

                embed = discord.Embed(
                    title="Ticket Sistemi Kaldırıldı" if removed else "Ticket Sistemi Bulunamadı",
                    description=f"{system['name']} ticket sistemi {channel.mention} kanalından kaldırıldı." if removed else f"{system['name']} ticket sistemi {channel.mention} kanalında bulunamadı.",
                    color=0x00ff00 if removed else 0xff0000,
                    timestamp=datetime.now(ZoneInfo("UTC"))
                )
                embed.set_footer(text="Habsen Topluluğu")
                await interaction.response.edit_message(embed=embed, view=None)

        view = TicketSystemSelect(interaction.user.id)
        embed = discord.Embed(
            title="Ticket Sistemi Seçimi",
            description="Aşağıdan göndermek veya kaldırmak istediğiniz ticket sistemini seçin ve uygun butona basın.",
            color=0xffff00,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel_id != int(os.getenv("BADGE_REQUEST_CHANNEL_ID")):
            return

        if message.author.id not in self.pending_badge_requests or datetime.now(ZoneInfo("UTC")).timestamp() > self.pending_badge_requests[message.author.id]:
            await message.delete()
            if message.author.id in self.pending_badge_requests:
                del self.pending_badge_requests[message.author.id]
            embed = discord.Embed(
                title="Geçersiz İşlem",
                description="Lütfen önce **Rozet Talebi Oluştur** butonuna tıklayın.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await message.author.send(embed=embed)
            return

        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                SELECT COUNT(*) FROM badges 
                WHERE user_id = ? AND guild_id = ? AND submitted_at > ?
            ''', (message.author.id, message.guild.id, 
                  (datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)).isoformat()))
            request_count = (await cursor.fetchone())[0]

        if request_count >= 3:
            await message.delete()
            embed = discord.Embed(
                title="Sınır Aşıldı",
                description="Saatte en fazla 3 rozet talebi gönderebilirsiniz. Lütfen bir süre bekleyin.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await message.author.send(embed=embed)
            return

        if not message.attachments or not any(attachment.content_type in ['image/png', 'image/jpeg'] for attachment in message.attachments):
            await message.delete()
            embed = discord.Embed(
                title="Geçersiz Dosya",
                description="Lütfen sadece **PNG veya JPG** formatında bir görsel yükleyin.",
                color=0xff0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Topluluğu")
            await message.author.send(embed=embed)
            return

        attachment = message.attachments[0]
        badge_url = attachment.url
        await message.delete()

        async with aiosqlite.connect("warnings.db") as db:
            cursor = await db.execute('''
                INSERT INTO badges (user_id, guild_id, badge_url, status, submitted_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (message.author.id, message.guild.id, badge_url, 'pending', 
                  datetime.now(ZoneInfo("UTC")).isoformat()))
            await db.commit()
            badge_id = cursor.lastrowid

        log_channel = message.guild.get_channel(int(os.getenv("BADGE_MOD_LOG_CHANNEL_ID")))
        if log_channel:
            embed = discord.Embed(
                title="Yeni Rozet Talebi",
                description=f"{message.author.mention} tarafından yeni bir rozet talebi gönderildi.",
                color=0xffff00,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_image(url=badge_url)
            embed.set_footer(text=f"Talep ID: {badge_id} | Habsen Topluluğu")
            view = BadgeApprovalView(badge_id, message.author)
            log_message = await log_channel.send(embed=embed, view=view)
            self.bot.persistent_views[log_message.id] = view

            async with aiosqlite.connect("warnings.db") as db:
                await db.execute('UPDATE badges SET message_id = ? WHERE id = ?', (log_message.id, badge_id))
                await db.commit()

        embed = discord.Embed(
            title="Rozet Talebi Gönderildi",
            description=(
                f"Rozet talebiniz başarıyla gönderildi. Talep ID: **{badge_id}**\n"
                "Talebiniz moderatörler tarafından incelenecek.\n"
                f"Durumu kontrol etmek için {message.channel.mention} kanalındaki **Rozet Durum** butonunu kullanabilirsiniz."
            ),
            color=0x00ff00,
            timestamp=datetime.now(ZoneInfo("UTC"))
        )
        embed.set_footer(text="Habsen Topluluğu")
        await message.author.send(embed=embed)

        del self.pending_badge_requests[message.author.id]

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.persistent_views = {}
        request_channel = self.bot.get_channel(int(os.getenv("BADGE_REQUEST_CHANNEL_ID")))
        if request_channel:
            async for message in request_channel.history(limit=100):
                if message.author == self.bot.user and "Rozet Talebi" in message.embeds[0].title:
                    view = BadgeRequestView(self.pending_badge_requests)
                    self.bot.persistent_views[message.id] = view
                    await message.edit(view=view)
                    break

        log_channel = self.bot.get_channel(int(os.getenv("BADGE_MOD_LOG_CHANNEL_ID")))
        if log_channel:
            async with aiosqlite.connect("warnings.db") as db:
                cursor = await db.execute('SELECT id, user_id, message_id FROM badges WHERE status = ?', ('pending',))
                pending_badges = await cursor.fetchall()

            for badge in pending_badges:
                badge_id, user_id, message_id = badge
                try:
                    user = await self.bot.fetch_user(user_id)
                    message = await log_channel.fetch_message(message_id)
                    view = BadgeApprovalView(badge_id, user)
                    self.bot.persistent_views[message_id] = view
                    await message.edit(view=view)
                except discord.NotFound:
                    embed = discord.Embed(
                        title="Yeni Rozet Talebi",
                        description=f"<@{user_id}> tarafından yeni bir rozet talebi gönderildi.",
                        color=0xffff00,
                        timestamp=datetime.now(ZoneInfo("UTC"))
                    )
                    async with aiosqlite.connect("warnings.db") as db:
                        cursor = await db.execute('SELECT badge_url FROM badges WHERE id = ?', (badge_id,))
                        badge_url = (await cursor.fetchone())[0]
                    embed.set_image(url=badge_url)
                    embed.set_footer(text=f"Talep ID: {badge_id} | Habsen Topluluğu")
                    view = BadgeApprovalView(badge_id, user)
                    new_message = await log_channel.send(embed=embed, view=view)
                    async with aiosqlite.connect("warnings.db") as db:
                        await db.execute('UPDATE badges SET message_id = ? WHERE id = ?', (new_message.id, badge_id))
                        await db.commit()
                    self.bot.persistent_views[new_message.id] = view
                except Exception as e:
                    from utils.helpers import log_error_to_discord
                    logger.error(f"Rozet talebi yeniden bağlanırken hata (badge_id: {badge_id}): {str(e)}")
                    await log_error_to_discord(f"Rozet talebi yeniden bağlanırken hata (badge_id: {badge_id}): {str(e)}")

async def setup(bot):
    await bot.add_cog(Ticket(bot))
