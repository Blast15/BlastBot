import asyncio
import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext.commands import Context
from datetime import timedelta

class Moderation(commands.Cog, name="moderation"):
    """
    A cog that handles moderation and server management commands for a Discord bot.
    This cog provides various moderation commands including kick, ban, timeout, role management,
    and message management functionalities.
    Commands:
        - kick: Kicks a member from the server
        - ban: Bans a member from the server
        - banid: Bans a user by their ID
        - unbanid: Unbans a user by their ID
        - timeout: Temporarily mutes a member
        - untimeout: Removes timeout from a member
        - purge: Deletes a specified number of messages
        - archive: Saves message history to a file
        - temprole: Assigns a temporary role to a member
    Attributes:
        bot: The bot instance that the cog is attached to
    Required Permissions:
        - Bot must have appropriate permissions for each command (kick_members, ban_members, manage_messages, manage_roles)
        - Users must have corresponding permissions to use moderation commands
    Note:
        All commands support both prefix and slash command syntax through hybrid commands
    """
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name="kick", description="Đá một người ra khỏi máy chủ")
    @commands.has_permissions(kick_members=True)  # Yêu cầu quyền đá thành viên
    @commands.bot_has_permissions(kick_members=True)  # Bot cần có quyền đá thành viên
    @app_commands.describe(member="Người bị đá", reason="Lý do")
    async def kick(self, ctx: Context, member: discord.Member, *, reason: str = "Không có lý do") -> None:
        """Kicks a member from the guild.
        This command kicks the specified member from the guild if the bot has proper permissions
        and the target member doesn't have administrator permissions.
        Parameters
        ----------
        ctx : Context
            The context in which the command was invoked
        member : discord.Member 
            The member to kick from the guild
        reason : str, optional
            The reason for kicking the member (default is "Không có lý do")
        Returns
        -------
        None
        Raises
        ------
        discord.Forbidden
            If the bot doesn't have permission to kick members
        discord.HTTPException
            If kicking the member failed
        Notes
        -----
        - Bot's role must be higher than the target member's highest role
        - Target member must not have administrator permissions
        - Bot will attempt to DM the kicked member with the reason
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
        """Ban a member from the server.

        This command bans the specified member from the server. If the member has administrator permissions,
        the ban will not be executed. The bot will attempt to send a DM to the banned member with the reason.

        Parameters
        ----------
        ctx : Context
            The context of the command invocation
        member : discord.Member
            The member to ban from the server
        reason : str, optional
            The reason for the ban (defaults to "Không có lý do")

        Raises
        ------
        discord.Forbidden
            If the bot doesn't have permission to ban members
        discord.HTTPException
            If banning the user failed

        Notes
        -----
        - The bot's role must be higher than the target member's role
        - The command executor must have ban permissions
        - Administrators cannot be banned using this command
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
        Ban a member from the server using their ID.

        This command allows moderators to ban users by their Discord ID, even if they are not currently in the server.
        If possible, the bot will send a DM to the banned user with the ban reason.

        Args:
            ctx (Context): The context in which the command is being executed
            member (int): The Discord ID of the member to ban
            reason (str, optional): The reason for the ban. Defaults to "Không có lý do"

        Raises:
            discord.Forbidden: If the bot doesn't have permission to ban members
            discord.HTTPException: If banning the user failed

        Example:
            $banid 123456789 Spam và quảng cáo

        Note:
            - The bot's role must be higher than the target user's role
            - The bot must have the "Ban Members" permission
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
        """Unbans a user from the guild using their ID.
        This command allows moderators to unban users from the guild using their user ID.
        If successful, sends an embed message confirming the unban and attempts to DM the unbanned user.
        Parameters
        ----------
        ctx : Context
            The context in which the command was called
        member : int
            The ID of the user to unban
        reason : str, optional
            The reason for unbanning the user (default is "Không có lý do")
        Returns
        -------
        None
        Raises
        ------
        None
            Catches all exceptions and sends an error embed if unban fails
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
        """
        Timeout a member for a specified duration.

        This command temporarily restricts a member's ability to send messages, add reactions, 
        join voice channels, or speak in voice channels for a specified duration.

        Parameters
        ----------
        ctx : Context
            The context in which the command is being invoked
        member : discord.Member
            The member to timeout
        duration : int
            The duration of the timeout in minutes
        reason : str, optional
            The reason for the timeout (default is "Không có lý do")

        Returns
        -------
        None

        Raises
        ------
        Exception
            If the bot doesn't have sufficient permissions to timeout the member
            or if the member has administrator permissions

        Notes
        -----
        - The member will be notified via DM about their timeout if their DMs are open
        - The command will fail if the target member has administrator permissions
        - The bot's role must be higher than the target member's role
        """
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
        """Removes timeout from a member in the guild.

        This command allows moderators to remove timeout (unmute) from a specified member.
        If successful, it sends a confirmation message in the channel and attempts to notify the member via DM.

        Parameters
        ----------
        ctx : Context
            The context in which the command was called
        member : discord.Member
            The member to remove timeout from
        reason : str, optional
            The reason for removing the timeout (default is "Không có lý do")

        Returns
        -------
        None

        Raises
        ------
        None
            Catches all exceptions and sends an error message if timeout removal fails
        """
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
        """Purges (deletes) a specified number of messages from the current channel.
        This command deletes a given number of most recent messages in the channel where it's invoked.
        The command message itself is included in the count and deleted as well.
        Parameters
        ----------
        ctx : Context
            The context in which the command is being invoked
        amount : int
            The number of messages to delete (must be positive)
        Returns
        -------
        None
        Raises
        ------
        discord.errors.Forbidden
            If the bot doesn't have permission to delete messages
        Exception
            For any other unexpected errors during execution
        Notes
        -----
        - Maximum number of messages that can be deleted at once is 100 (excluding the command message)
        - The success message is automatically deleted after 5 seconds
        - The command requires proper message management permissions
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
        """Archive a specified number of messages from the current channel into a text file.
        This command saves the message history into a temporary text file and sends it to the channel.
        The file is then automatically deleted after being sent.
        Parameters:
            ctx (Context): The context of the command invocation.
            amount (int): The number of messages to archive (maximum 100).
        Raises:
            discord.errors.Forbidden: If the bot lacks permissions to access message history.
            Exception: For any other unexpected errors during execution.
        Example:
            /archive 50  # Archives the last 50 messages from the channel
        Note:
            - Messages are saved in the format: [timestamp] author: content
            - The file is named after the channel: {channel_name}_archive.txt
            - Messages are ordered from oldest to newest
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
        """Gives a temporary role to a member for a specified duration.
        This command adds a role to a member that will be automatically removed after the specified duration.
        The role information is stored in a database to track when it should be removed.
        Parameters
        ----------
        ctx : Context
            The context in which the command is being executed
        member : discord.Member
            The member to give the temporary role to
        role : discord.Role
            The role to be assigned temporarily
        duration : int
            The duration in minutes for how long the role should last
        Returns
        -------
        None
        Raises
        ------
        discord.errors.Forbidden
            If the bot doesn't have permission to manage roles
        Exception
            If any other error occurs during role assignment
        Notes
        -----
        The role expiry time is stored in UTC timestamp format
        """
        member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        if role in member.roles:
            await ctx.send(embed=discord.Embed(description=f"❌ {member.mention} đã có role này.", color=0xE02B2B))
            return

        try:
            await member.add_roles(role)
            expiry_time = duration * 60
            await self.bot.get_cog('TempRoleCleanup').add_temp_role(
                guild_id=ctx.guild.id, 
                user_id=member.id, 
                role_id=role.id, 
                duration=expiry_time,
                )
            
            await ctx.send(embed=discord.Embed(description=f"✅ Đã thêm role {role.mention} cho {member.mention} trong {duration} phút.", color=0x77B255))
        except discord.errors.Forbidden:
            await ctx.send(embed=discord.Embed(description="❌ Bot không có quyền gán role.", color=0xE02B2B))
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"❌ Lỗi: {str(e)}", color=0xE02B2B))
            
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))