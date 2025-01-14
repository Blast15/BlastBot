import asyncio
import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext.commands import Context
from datetime import timedelta

class Moderation(commands.Cog, name="moderation"):
    """Cog xử lý các lệnh kiểm duyệt và quản lý server"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name="kick", description="Đá một người ra khỏi máy chủ")
    @commands.has_permissions(kick_members=True)  # Yêu cầu quyền đá thành viên
    @commands.bot_has_permissions(kick_members=True)  # Bot cần có quyền đá thành viên
    @app_commands.describe(member="Người bị đá", reason="Lý do")
    async def kick(self, ctx: Context, member: discord.Member, *, reason: str = "Không có lý do") -> None:
        """
        Đá một thành viên ra khỏi server
        Parameters:
            member (discord.Member): Thành viên cần đá
            reason (str): Lý do đá thành viên (không bắt buộc)
        """
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(
            member.id
        )
        if member.guild_permissions.administrator:
            embed = discord.Embed(
                description="Người dùng có quyền quản trị viên.", color=0xE02B2B
            )
            await ctx.send(embed=embed)
        else:
            try:
                embed = discord.Embed(
                    description=f"**{member}** đã bị đuổi bởi **{ctx.author}**!",
                    color=0xBEBEFE,
                )
                embed.add_field(name="Lý do:", value=reason)
                await ctx.send(embed=embed)
                try:
                    await member.send(
                        f"Bạn đã bị đuổi bởi **{ctx.author}** từ **{ctx.guild.name}**!\nLý do: {reason}"
                    )
                except:
                    # Không thể gửi tin nhắn trong tin nhắn riêng tư của người dùng
                    pass
                await member.kick(reason=reason)
            except:
                embed = discord.Embed(
                    description="Đã xảy ra lỗi khi cố gắng đuổi người dùng. Đảm bảo rằng vai trò của bot cao hơn vai trò của người dùng bạn muốn đuổi.",
                    color=0xE02B2B,
                )
                await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="ban", description="Cấm một người dùng khỏi máy chủ")
    @commands.has_permissions(ban_members=True)  # Yêu cầu quyền cấm thành viên
    @commands.bot_has_permissions(ban_members=True)  # Bot cần có quyền cấm thành viên
    @app_commands.describe(member="Người bị cấm", reason="Lý do")
    async def ban(self, ctx: Context, member: discord.Member, *, reason: str = "Không có lý do"):
        """
        Cấm một thành viên khỏi server
        Parameters:
            member (discord.Member): Thành viên cần cấm
            reason (str): Lý do cấm thành viên (không bắt buộc)
        """
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(
            member.id
        )
        try:
            if member.guild_permissions.administrator:
                embed = discord.Embed(
                    description="Người dùng có quyền quản trị viên.", color=0xE02B2B
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    description=f"**{member}** đã bị cấm bởi **{ctx.author}**!",
                    color=0xBEBEFE,
                )
                embed.add_field(name="Lý do:", value=reason)
                await ctx.send(embed=embed)
                try:
                    await member.send(
                        f"Bạn đã bị cấm bởi **{ctx.author}** từ **{ctx.guild.name}**!\nLý do: {reason}"
                    )
                except:
                    # Không thể gửi tin nhắn trong tin nhắn riêng tư của người dùng
                    pass
                await member.ban(reason=reason)
        except:
            embed = discord.Embed(
                title="Lỗi!",
                description="Đã xảy ra lỗi khi cố gắng cấm người dùng. Đảm bảo rằng vai trò của tôi cao hơn vai trò của người dùng bạn muốn cấm.",
                color=0xE02B2B,
            )
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="banid", description="Cấm một người dùng khỏi máy chủ bằng ID")
    @commands.has_permissions(ban_members=True)  # Yêu cầu quyền cấm thành viên
    @commands.bot_has_permissions(ban_members=True)  # Bot cần có quyền cấm thành viên
    @app_commands.describe(member="Id bị cấm", reason="Lý do")
    async def banid(self, ctx: Context, member: int, *, reason: str = "Không có lý do") -> None:
        """
        Cấm một thành viên khỏi server bằng ID
        Parameters:
            member (int): ID của thành viên cần cấm
            reason (str): Lý do cấm thành viên (không bắt buộc)
        """
        try:
            member = await self.bot.fetch_user(member)
            await ctx.guild.ban(member, reason=reason)
            embed = discord.Embed(
                description=f"**{member}** đã bị cấm bởi **{ctx.author}**!",
                color=0xBEBEFE,
            )
            embed.add_field(name="Lý do:", value=reason)
            await ctx.send(embed=embed)
            try:
                await member.send(
                    f"Bạn đã bị cấm bởi **{ctx.author}** từ **{ctx.guild.name}**!\nLý do: {reason}"
                )
            except:
                # Không thể gửi tin nhắn trong tin nhắn riêng tư của người dùng
                pass
        except:
            embed = discord.Embed(
                title="Lỗi!",
                description="Đã xảy ra lỗi khi cố gắng cấm người dùng. Đảm bảo rằng vai trò của tôi cao hơn vai trò của người dùng bạn muốn cấm.",
                color=0xE02B2B,
            )
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="unbanid", description="Bỏ cấm một người dùng khỏi máy chủ")
    @commands.has_permissions(ban_members=True)  # Yêu cầu quyền cấm thành viên
    @commands.bot_has_permissions(ban_members=True)  # Bot cần có quyền cấm thành viên
    @app_commands.describe(member="Id bị bỏ cấm", reason="Lý do")
    async def unbanid(self, ctx: Context, member: int, *, reason: str = "Không có lý do") -> None:
        """
        Bỏ cấm một thành viên khỏi server
        Parameters:
            member (int): ID của thành viên cần bỏ cấm
            reason (str): Lý do bỏ cấm thành viên (không bắt buộc)
        """
        try:
            member = await self.bot.fetch_user(member)
            await ctx.guild.unban(member, reason=reason)
            embed = discord.Embed(
                description=f"**{member}** đã được bỏ cấm bởi **{ctx.author}**!",
                color=0xBEBEFE,
            )
            embed.add_field(name="Lý do:", value=reason)
            await ctx.send(embed=embed)
            try:
                await member.send(
                    f"Bạn đã được bỏ cấm bởi **{ctx.author}** từ **{ctx.guild.name}**!\nLý do: {reason}"
                )
            except:
                # Không thể gửi tin nhắn trong tin nhắn riêng tư của người dùng
                pass
        except:
            embed = discord.Embed(
                title="Lỗi!",
                description="Đã xảy ra lỗi khi cố gắng bỏ cấm người dùng. Đảm bảo rằng vai trò của tôi cao hơn vai trò của người dùng bạn muốn bỏ cấm.",
                color=0xE02B2B,
            )
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="timeout",
        description="Cấm một người dùng khỏi máy chủ trong một khoảng thời gian nhất định",
    )
    @commands.has_permissions(ban_members=True)  # Yêu cầu quyền cấm thành viên
    @commands.bot_has_permissions(ban_members=True)  # Bot cần có quyền cấm thành viên
    @app_commands.describe(
        member="Người bị khóa mõm",
        duration="Thời gian khóa mõm (phút)",
        reason="Lý do khóa mõm",
    )
    async def timeout(self, ctx: Context, member: discord.Member, duration: int, *, reason: str = "Không có lý do") -> None:
        '''
        Cấm một người dùng khỏi máy chủ trong một khoảng thời gian nhất định
        Parameters:
            member (discord.Member): Người bị khóa mõm
            duration (int): Thời gian khóa mõm (phút)
            reason (str): Lý do khóa mõm (không bắt buộc)
        '''
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        if member.guild_permissions.administrator:
            embed = discord.Embed(
                description="Người dùng có quyền quản trị viên.", color=0xE02B2B
            )
            await ctx.send(embed=embed)
        else:
            try:
                timeout_duration = timedelta(minutes=duration)
                await member.timeout(timeout_duration, reason=reason)
                embed = discord.Embed(
                    description=f"**{member}** đã bị khóa mõm bởi **{ctx.author}** trong {duration} phút!",
                    color=0xBEBEFE,
                )
                embed.add_field(name="Lý do:", value=reason)
                await ctx.send(embed=embed)
                try:
                    await member.send(
                        f"Bạn đã bị khóa mõm bởi **{ctx.author}** từ **{ctx.guild.name}** trong {duration} phút!\nLý do: {reason}"
                    )
                except:
                    # Không thể gửi tin nhắn trong tin nhắn riêng tư của người dùng
                    pass
            except:
                embed = discord.Embed(
                    title="Lỗi!",
                    description="Đã xảy ra lỗi khi cố gắng khóa mõm người dùng. Đảm bảo rằng vai trò của bot cao hơn vai trò của người dùng bạn muốn khóa mõm.",
                    color=0xE02B2B,
                )
                await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="untimeout", description="Bỏ khóa mõm một người dùng khỏi máy chủ")
    @commands.has_permissions(ban_members=True)  # Yêu cầu quyền cấm thành viên
    @commands.bot_has_permissions(ban_members=True)  # Bot cần có quyền cấm thành viên
    @app_commands.describe(member="Người bị bỏ khóa mõm", reason="Lý do")
    async def untimeout(self, ctx: Context, member: discord.Member, *, reason: str = "Không có lý do") -> None:
        '''
        Bỏ khóa mõm một người dùng khỏi server
        Parameters:
            member (discord.Member): Người bị bỏ khóa mõm
            reason (str): Lý do bỏ khóa mõm (không bắt buộc)
        '''
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        try:
            await member.untimeout(reason=reason)
            embed = discord.Embed(
                description=f"**{member}** đã được bỏ khóa mõm bởi **{ctx.author}**!",
                color=0xBEBEFE,
            )
            embed.add_field(name="Lý do:", value=reason)
            await ctx.send(embed=embed)
            try:
                await member.send(
                    f"Bạn đã được bỏ khóa mõm bởi **{ctx.author}** từ **{ctx.guild.name}**!\nLý do: {reason}"
                )
            except:
                # Không thể gửi tin nhắn trong tin nhắn riêng tư của người dùng
                pass
        except:
            embed = discord.Embed(
                title="Lỗi!",
                description="Đã xảy ra lỗi khi cố gắng bỏ khóa mõm người dùng. Đảm bảo rằng vai trò của tôi cao hơn vai trò của người dùng bạn muốn bỏ khóa mõm.",
                color=0xE02B2B,
            )
            await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="purge", description="Xóa một số lượng tin nhắn trong kênh")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @app_commands.describe(amount="Số lượng tin nhắn cần xóa")
    async def purge(self, ctx: Context, amount: int) -> None:
        """
        Xóa một số lượng tin nhắn trong kênh
        Parameters:
            amount (int): Số lượng tin nhắn cần xóa
        """
        try:
            if isinstance(ctx.interaction, discord.Interaction):
                await ctx.interaction.response.defer(ephemeral=False)
            
            if amount <= 0:
                await ctx.send(embed=discord.Embed(description="⚠️ Số lượng tin nhắn phải lớn hơn 0.", color=0xE02B2B))
                return

            deleted = await ctx.channel.purge(limit=min(amount + 1, 101))
            
            embed = discord.Embed(description=f"✅ Đã xóa {len(deleted)-1} tin nhắn!", color=0x77B255)
            msg = await ctx.channel.send(embed=embed)
            
            await asyncio.sleep(5)
            await msg.delete()

        except discord.errors.Forbidden:
            await ctx.send(embed=discord.Embed(description="❌ Bot không có quyền xóa tin nhắn.", color=0xE02B2B))
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"❌ Lỗi: {str(e)}", color=0xE02B2B))

    @commands.hybrid_command(name="archive", description="Lưu lịch sử tin nhắn vào một file")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(amount="Số lượng tin nhắn cần lưu")
    async def archive(self, ctx: Context, amount: int) -> None:
        """
        Lưu lịch sử tin nhắn vào một file
        Parameters:
            amount (int): Số lượng tin nhắn cần lưu
        """
        try:
            if isinstance(ctx.interaction, discord.Interaction):
                await ctx.interaction.response.defer(ephemeral=False)
            
            if amount <= 0:
                await ctx.send(embed=discord.Embed(description="⚠️ Số lượng tin nhắn phải lớn hơn 0.", color=0xE02B2B))
                return

            messages = [message async for message in ctx.channel.history(limit=min(amount, 100))]
            messages.reverse()

            with open(f"{ctx.channel.name}_archive.txt", "w", encoding="utf-8") as file:
                for message in messages:
                    file.write(f"[{message.created_at}] {message.author}: {message.content}\n")
            
            await ctx.send(file=discord.File(f"{ctx.channel.name}_archive.txt"))
            os.remove(f"{ctx.channel.name}_archive.txt")
        except discord.errors.Forbidden:
            await ctx.send(embed=discord.Embed(description="❌ Bot không có quyền xóa tin nhắn.", color=0xE02B2B))
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"❌ Lỗi: {str(e)}", color=0xE02B2B))

    @commands.hybrid_command(name="temprole", description="Gán một role tạm thời cho một người dùng")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @app_commands.describe(member="Người nhận role", role="Role cần gán", duration="Thời gian role (phút)")
    async def temprole(self, ctx: Context, member: discord.Member, role: discord.Role, duration: int) -> None:
        """
        Gán một role tạm thời cho một người dùng
        Parameters:
            member (discord.Member): Người nhận role
            role (discord.Role): Role cần gán
            duration (int): Thời gian role (phút)
        """
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        if role in member.roles:
            await ctx.send(embed=discord.Embed(description=f"❌ {member.mention} đã có role này.", color=0xE02B2B))
            return

        try:
            await member.add_roles(role)
            expiry_time = discord.utils.utcnow().timestamp() + (duration * 60)
            
            # Lưu thông tin role tạm thời vào cơ sở dữ liệu
            self.bot.db.cursor.execute(
                "INSERT OR REPLACE INTO temprole (guild_id, user_id, role_id, time) VALUES (?, ?, ?, ?)",
                (ctx.guild.id, member.id, role.id, expiry_time)
            )
            self.bot.db.conn.commit()
            
            await ctx.send(embed=discord.Embed(description=f"✅ Đã thêm role {role.mention} cho {member.mention} trong {duration} phút.", color=0x77B255))
        except discord.errors.Forbidden:
            await ctx.send(embed=discord.Embed(description="❌ Bot không có quyền gán role.", color=0xE02B2B))
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"❌ Lỗi: {str(e)}", color=0xE02B2B))
            
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))