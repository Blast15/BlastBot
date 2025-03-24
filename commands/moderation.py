import asyncio
import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext.commands import Context
from datetime import timedelta
from typing import Optional, Union, Literal

class Moderation(commands.Cog, name="moderation"):
    """
    A cog that handles moderation and server management commands for a Discord bot.
    This cog provides various moderation commands including kick, ban, timeout, role management,
    and message management functionalities.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.error_color = 0xE02B2B
        self.success_color = 0xBEBEFE
        self.green_color = 0x77B255
    
    async def send_mod_action_response(self, ctx: Context, title: str, member: Union[discord.Member, discord.User], 
                              reason: str, action_type: str, success: bool = True) -> None:
        """Helper method to send consistent mod action response embeds"""
        if success:
            embed = discord.Embed(
                description=f"**{member}** đã bị {action_type} bởi **{ctx.author}**!",
                color=self.success_color
            )
            embed.add_field(name="Lý do:", value=reason)
            
            # Thử gửi tin nhắn thông báo cho người dùng bị xử lý
            try:
                await member.send(
                    f"Bạn đã bị {action_type} bởi **{ctx.author}** từ **{ctx.guild.name}**!\nLý do: {reason}"
                )
            except:
                pass  # Không thể gửi tin nhắn riêng tư
        else:
            embed = discord.Embed(
                title=title,
                description=f"Đã xảy ra lỗi khi cố gắng {action_type} người dùng. Đảm bảo rằng vai trò của bot cao hơn vai trò của người dùng.",
                color=self.error_color
            )
        await ctx.send(embed=embed)
    
    async def check_admin_permissions(self, ctx: Context, member: discord.Member) -> bool:
        """Check if the target member has administrator permissions"""
        if member.guild_permissions.administrator:
            embed = discord.Embed(
                description="Người dùng có quyền quản trị viên.", 
                color=self.error_color
            )
            await ctx.send(embed=embed)
            return True
        return False
    
    @commands.hybrid_command(name="kick", description="Đá một người ra khỏi máy chủ")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @app_commands.describe(member="Người bị đá", reason="Lý do")
    async def kick(self, ctx: Context, member: discord.Member, *, reason: str = "Không có lý do") -> None:
        """Kicks a member from the guild."""
        
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        
        # Kiểm tra nếu người dùng có quyền admin
        if await self.check_admin_permissions(ctx, member):
            return
            
        try:
            await member.kick(reason=reason)
            await self.send_mod_action_response(ctx, "Lỗi!", member, reason, "đuổi")
        except Exception as e:
            await self.send_mod_action_response(ctx, "Lỗi!", member, reason, "đuổi", False)
            self.bot.logger.error(f"Lỗi khi kick: {str(e)}")
    
    @commands.hybrid_command(name="ban", description="Cấm một người dùng khỏi máy chủ")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(member="Người bị cấm", reason="Lý do")
    async def ban(self, ctx: Context, member: discord.Member, *, reason: str = "Không có lý do"):
        """Ban a member from the server."""
        
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        
        # Kiểm tra nếu người dùng có quyền admin
        if await self.check_admin_permissions(ctx, member):
            return
            
        try:
            await member.ban(reason=reason)
            await self.send_mod_action_response(ctx, "Lỗi!", member, reason, "cấm")
        except Exception as e:
            await self.send_mod_action_response(ctx, "Lỗi!", member, reason, "cấm", False)
            self.bot.logger.error(f"Lỗi khi ban: {str(e)}")
    
    @commands.hybrid_command(name="banid", description="Cấm một người dùng khỏi máy chủ bằng ID")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(member_id="Id bị cấm", reason="Lý do")
    async def banid(self, ctx: Context, member_id: int, *, reason: str = "Không có lý do") -> None:
        """Ban a member from the server using their ID."""
        
        try:
            member = await self.bot.fetch_user(member_id)
            await ctx.guild.ban(member, reason=reason)
            await self.send_mod_action_response(ctx, "Lỗi!", member, reason, "cấm")
        except Exception as e:
            embed = discord.Embed(
                title="Lỗi!",
                description=f"Đã xảy ra lỗi khi cấm người dùng với ID {member_id}. {str(e)}",
                color=self.error_color
            )
            await ctx.send(embed=embed)
            self.bot.logger.error(f"Lỗi khi ban ID {member_id}: {str(e)}")
    
    @commands.hybrid_command(name="unbanid", description="Bỏ cấm một người dùng khỏi máy chủ")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(member_id="Id bị bỏ cấm", reason="Lý do")
    async def unbanid(self, ctx: Context, member_id: int, *, reason: str = "Không có lý do") -> None:
        """Unbans a user from the guild using their ID."""
        
        try:
            member = await self.bot.fetch_user(member_id)
            await ctx.guild.unban(member, reason=reason)
            await self.send_mod_action_response(ctx, "Lỗi!", member, reason, "bỏ cấm")
        except Exception as e:
            embed = discord.Embed(
                title="Lỗi!",
                description=f"Đã xảy ra lỗi khi bỏ cấm người dùng với ID {member_id}. {str(e)}",
                color=self.error_color
            )
            await ctx.send(embed=embed)
            self.bot.logger.error(f"Lỗi khi unban ID {member_id}: {str(e)}")
    
    @commands.hybrid_command(
        name="timeout",
        description="Tạm thời khóa chat của thành viên trong một khoảng thời gian"
    )
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.describe(
        member="Người bị khóa chat",
        duration="Thời gian khóa chat",
        time_unit="Đơn vị thời gian",
        reason="Lý do khóa chat"
    )
    async def timeout(
        self, 
        ctx: Context, 
        member: discord.Member, 
        duration: int, 
        time_unit: Literal["giây", "phút", "giờ", "ngày"] = "phút", 
        *, 
        reason: str = "Không có lý do"
    ) -> None:
        """Timeout a member for a specified duration."""
        
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        
        # Kiểm tra nếu người dùng có quyền admin
        if await self.check_admin_permissions(ctx, member):
            return
        
        # Chuyển đổi thời gian sang giây
        seconds = duration
        if time_unit == "phút":
            seconds *= 60
            time_display = f"{duration} phút"
        elif time_unit == "giờ":
            seconds *= 3600
            time_display = f"{duration} giờ"
        elif time_unit == "ngày":
            seconds *= 86400
            time_display = f"{duration} ngày"
        else:  # giây
            time_display = f"{duration} giây"
            
        try:
            await member.timeout(discord.utils.utcnow() + timedelta(seconds=seconds), reason=reason)
            
            embed = discord.Embed(
                description=f"**{member}** đã bị khóa chat bởi **{ctx.author}** trong {time_display}!",
                color=self.success_color
            )
            embed.add_field(name="Lý do:", value=reason)
            await ctx.send(embed=embed)
            
            try:
                await member.send(
                    f"Bạn đã bị khóa chat bởi **{ctx.author}** từ **{ctx.guild.name}** trong {time_display}!\nLý do: {reason}"
                )
            except:
                pass  # Không thể gửi tin nhắn riêng tư
                
        except Exception as e:
            embed = discord.Embed(
                title="Lỗi!",
                description=f"Đã xảy ra lỗi khi khóa chat: {str(e)}",
                color=self.error_color
            )
            await ctx.send(embed=embed)
            self.bot.logger.error(f"Lỗi khi timeout: {str(e)}")
    
    @commands.hybrid_command(name="untimeout", description="Bỏ khóa chat thành viên")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.describe(member="Người bị bỏ khóa chat", reason="Lý do")
    async def untimeout(self, ctx: Context, member: discord.Member, *, reason: str = "Không có lý do") -> None:
        """Removes timeout from a member in the guild."""
        
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        
        try:
            await member.timeout(None, reason=reason)
            await self.send_mod_action_response(ctx, "Lỗi!", member, reason, "bỏ khóa chat")
        except Exception as e:
            embed = discord.Embed(
                title="Lỗi!",
                description=f"Đã xảy ra lỗi khi bỏ khóa chat: {str(e)}",
                color=self.error_color
            )
            await ctx.send(embed=embed)
            self.bot.logger.error(f"Lỗi khi untimeout: {str(e)}")
    
    @commands.hybrid_command(name="purge", description="Xóa một số lượng tin nhắn trong kênh")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @app_commands.describe(amount="Số lượng tin nhắn cần xóa (tối đa 100)")
    async def purge(self, ctx: Context, amount: int) -> None:
        """Purges (deletes) a specified number of messages from the current channel."""
        
        try:
            if isinstance(ctx.interaction, discord.Interaction):
                await ctx.interaction.response.defer(ephemeral=False)
            
            if amount <= 0:
                await ctx.send(embed=discord.Embed(
                    description="⚠️ Số lượng tin nhắn phải lớn hơn 0.", 
                    color=self.error_color
                ))
                return
            
            if amount > 100:
                amount = 100
                await ctx.send(embed=discord.Embed(
                    description="⚠️ Số lượng tin nhắn quá lớn, sẽ chỉ xóa 100 tin nhắn.", 
                    color=self.error_color
                ), delete_after=3)

            deleted = await ctx.channel.purge(limit=min(amount + 1, 101))
            
            embed = discord.Embed(
                description=f"✅ Đã xóa {len(deleted)-1} tin nhắn!", 
                color=self.green_color
            )
            msg = await ctx.channel.send(embed=embed)
            
            await asyncio.sleep(5)
            try:
                await msg.delete()
            except:
                pass

        except discord.errors.Forbidden:
            await ctx.send(embed=discord.Embed(
                description="❌ Bot không có quyền xóa tin nhắn.", 
                color=self.error_color
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Lỗi: {str(e)}", 
                color=self.error_color
            ))
            self.bot.logger.error(f"Lỗi khi purge: {str(e)}")

    @commands.hybrid_command(name="archive", description="Lưu lịch sử tin nhắn vào một file")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(amount="Số lượng tin nhắn cần lưu")
    async def archive(self, ctx: Context, amount: int = 100) -> None:
        """Archive a specified number of messages from the current channel into a text file."""
        
        try:
            if isinstance(ctx.interaction, discord.Interaction):
                await ctx.interaction.response.defer(ephemeral=False)
            
            if amount <= 0:
                await ctx.send(embed=discord.Embed(
                    description="⚠️ Số lượng tin nhắn phải lớn hơn 0.", 
                    color=self.error_color
                ))
                return
            
            if amount > 1000:
                amount = 1000
                await ctx.send(embed=discord.Embed(
                    description="⚠️ Số lượng tin nhắn được giới hạn tối đa 1000.", 
                    color=self.error_color
                ), delete_after=3)

            # Thông báo đang xử lý
            processing_msg = await ctx.send(embed=discord.Embed(
                description=f"⏳ Đang xử lý {amount} tin nhắn...", 
                color=self.success_color
            ))

            messages = [message async for message in ctx.channel.history(limit=amount)]
            messages.reverse()

            file_path = f"{ctx.channel.name}_archive.txt"
            with open(file_path, "w", encoding="utf-8") as file:
                for message in messages:
                    # Thêm attachments vào tin nhắn nếu có
                    attachments = ""
                    if message.attachments:
                        attachments = " [Files: " + ", ".join(a.url for a in message.attachments) + "]"
                    
                    # Định dạng tin nhắn với thời gian, tác giả và nội dung
                    file.write(f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {message.author} ({message.author.id}): {message.content}{attachments}\n")
            
            await processing_msg.delete()
            await ctx.send(
                embed=discord.Embed(
                    description=f"✅ Đã lưu {len(messages)} tin nhắn.", 
                    color=self.green_color
                ),
                file=discord.File(file_path)
            )
            
            # Xóa tệp tạm thời
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except discord.errors.Forbidden:
            await ctx.send(embed=discord.Embed(
                description="❌ Bot không có quyền đọc lịch sử tin nhắn.", 
                color=self.error_color
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Lỗi: {str(e)}", 
                color=self.error_color
            ))
            self.bot.logger.error(f"Lỗi khi archive: {str(e)}")
            # Đảm bảo xóa tệp tạm thời nếu có lỗi
            if os.path.exists(f"{ctx.channel.name}_archive.txt"):
                os.remove(f"{ctx.channel.name}_archive.txt")

    @commands.hybrid_command(name="temprole", description="Gán một role tạm thời cho một người dùng")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @app_commands.describe(
        member="Người nhận role", 
        role="Role cần gán", 
        duration="Thời gian giữ role", 
        time_unit="Đơn vị thời gian"
    )
    async def temprole(
        self, 
        ctx: Context, 
        member: discord.Member, 
        role: discord.Role, 
        duration: int = 30, 
        time_unit: Literal["phút", "giờ", "ngày"] = "phút"
    ) -> None:
        """Gives a temporary role to a member for a specified duration."""
        
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        
        if role in member.roles:
            await ctx.send(embed=discord.Embed(
                description=f"❌ {member.mention} đã có role {role.mention}.", 
                color=self.error_color
            ))
            return
        
        # Chuyển đổi thời gian sang giây
        seconds = duration * 60  # Mặc định là phút
        if time_unit == "giờ":
            seconds *= 60
            time_display = f"{duration} giờ"
        elif time_unit == "ngày":
            seconds *= 1440
            time_display = f"{duration} ngày"
        else:  # phút
            time_display = f"{duration} phút"

        try:
            await member.add_roles(role)
            temp_role_cog = self.bot.get_cog('TempRoleCleanup')
            
            if temp_role_cog:
                await temp_role_cog.add_temp_role(
                    guild_id=ctx.guild.id, 
                    user_id=member.id, 
                    role_id=role.id, 
                    duration=seconds
                )
                
                await ctx.send(embed=discord.Embed(
                    description=f"✅ Đã thêm role {role.mention} cho {member.mention} trong {time_display}.", 
                    color=self.green_color
                ))
            else:
                await member.remove_roles(role)  # Hoàn tác nếu không tìm thấy cog
                await ctx.send(embed=discord.Embed(
                    description="❌ Không thể cài đặt role tạm thời vì thành phần cần thiết không khả dụng.", 
                    color=self.error_color
                ))
                
        except discord.errors.Forbidden:
            await ctx.send(embed=discord.Embed(
                description="❌ Bot không có quyền gán role.",
                color=self.error_color
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Lỗi: {str(e)}", 
                color=self.error_color
            ))
            self.bot.logger.error(f"Lỗi khi temprole: {str(e)}")
            
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))