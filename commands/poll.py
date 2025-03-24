import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional
import asyncio
import datetime

from utils.constants import Colors
from utils.embed_helpers import create_success_embed, create_error_embed

class Poll(commands.Cog):
    """A cog for creating and managing polls in Discord."""
    
    def __init__(self, bot):
        self.bot = bot
        self.emoji_numbers = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    @commands.hybrid_command(name="poll", description="Tạo một cuộc thăm dò ý kiến")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(
        question="Câu hỏi thăm dò",
        option1="Lựa chọn 1", 
        option2="Lựa chọn 2",
        option3="Lựa chọn 3",
        option4="Lựa chọn 4",
        option5="Lựa chọn 5",
        option6="Lựa chọn 6",
        option7="Lựa chọn 7",
        option8="Lựa chọn 8",
        option9="Lựa chọn 9",
        option10="Lựa chọn 10"
    )
    async def poll(
        self, 
        ctx: commands.Context, 
        question: str,
        option1: str,
        option2: str,
        option3: Optional[str] = None,
        option4: Optional[str] = None,
        option5: Optional[str] = None,
        option6: Optional[str] = None,
        option7: Optional[str] = None,
        option8: Optional[str] = None,
        option9: Optional[str] = None,
        option10: Optional[str] = None
    ):
        """Create a poll with up to 10 options."""
        # Gather all options
        options = [opt for opt in [option1, option2, option3, option4, option5, 
                                 option6, option7, option8, option9, option10] if opt]
        
        # Create the poll embed
        embed = discord.Embed(
            title="📊 " + question,
            description="\n\n".join([f"{self.emoji_numbers[i]} {option}" for i, option in enumerate(options)]),
            color=Colors.INFO,
            timestamp=datetime.datetime.now()
        )
        
        embed.set_footer(text=f"Thăm dò bởi {ctx.author.display_name}", 
                         icon_url=ctx.author.display_avatar.url)
        
        # Send the poll
        poll_message = await ctx.send(embed=embed)
        
        # Add reaction options
        for i in range(len(options)):
            await poll_message.add_reaction(self.emoji_numbers[i])
    
    @commands.hybrid_command(name="quickpoll", description="Tạo nhanh một cuộc thăm dò đơn giản")
    @app_commands.describe(question="Câu hỏi thăm dò")
    async def quickpoll(self, ctx: commands.Context, *, question: str):
        """Create a simple yes/no poll."""
        embed = discord.Embed(
            title="📊 " + question,
            color=Colors.INFO,
            timestamp=datetime.datetime.now()
        )
        
        embed.set_footer(text=f"Thăm dò bởi {ctx.author.display_name}", 
                         icon_url=ctx.author.display_avatar.url)
        
        poll_message = await ctx.send(embed=embed)
        
        # Add reactions: ✅ for yes, ❌ for no
        await poll_message.add_reaction("✅")
        await poll_message.add_reaction("❌")
    
    @commands.hybrid_command(name="timepoll", description="Tạo một cuộc thăm dò có thời hạn")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(
        duration="Thời gian thăm dò (phút)",
        question="Câu hỏi thăm dò",
        options="Các lựa chọn, phân cách bằng dấu | (ví dụ: Có|Không|Không chắc)"
    )
    async def timepoll(self, ctx: commands.Context, duration: int, question: str, *, options: str):
        """Create a poll that automatically shows results after a specified duration."""
        if duration < 1 or duration > 1440:  # 1440 minutes = 24 hours
            await ctx.send(embed=create_error_embed("❌ Thời gian phải từ 1 đến 1440 phút (24 giờ)."))
            return
            
        option_list = options.split('|')
        if len(option_list) < 2:
            await ctx.send(embed=create_error_embed("❌ Cần ít nhất 2 lựa chọn, phân cách bằng dấu |."))
            return
            
        if len(option_list) > 10:
            await ctx.send(embed=create_error_embed("❌ Tối đa 10 lựa chọn."))
            return
            
        # Create the poll embed
        embed = discord.Embed(
            title="⏱️ " + question,
            description="\n\n".join([f"{self.emoji_numbers[i]} {option}" for i, option in enumerate(option_list)]),
            color=Colors.INFO,
            timestamp=datetime.datetime.now()
        )
        
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration)
        embed.add_field(name="Thời hạn", value=f"<t:{int(end_time.timestamp())}:R>", inline=False)
        
        embed.set_footer(text=f"Thăm dò bởi {ctx.author.display_name}", 
                         icon_url=ctx.author.display_avatar.url)
        
        # Send the poll
        poll_message = await ctx.send(embed=embed)
        
        # Add reaction options
        for i in range(len(option_list)):
            await poll_message.add_reaction(self.emoji_numbers[i])
            
        # Success message
        await ctx.send(embed=create_success_embed(
            f"✅ Đã tạo thăm dò có thời hạn! Kết quả sẽ được hiển thị sau {duration} phút."
        ))
        
        # Wait for the duration
        await asyncio.sleep(duration * 60)
        
        try:
            # Fetch the updated message to get latest reactions
            poll_message = await ctx.channel.fetch_message(poll_message.id)
            
            # Count reactions
            results = []
            total_votes = 0
            
            for i, option in enumerate(option_list):
                emoji = self.emoji_numbers[i]
                reaction = next((r for r in poll_message.reactions if str(r.emoji) == emoji), None)
                count = reaction.count - 1 if reaction else 0  # Subtract 1 to exclude bot's reaction
                total_votes += count
                results.append((option, count))
            
            # Create results embed
            results_embed = discord.Embed(
                title="📊 Kết quả thăm dò",
                description=question,
                color=Colors.SUCCESS,
                timestamp=datetime.datetime.now()
            )
            
            # Format results
            for option, count in results:
                percentage = (count / total_votes) * 100 if total_votes > 0 else 0
                bar_length = 20  # Length of the progress bar
                filled_length = int(bar_length * percentage / 100)
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                
                results_embed.add_field(
                    name=option,
                    value=f"{bar} {percentage:.1f}% ({count} phiếu)",
                    inline=False
                )
                
            results_embed.set_footer(text=f"Tổng số phiếu: {total_votes}")
            
            await ctx.send(embed=results_embed)
            
        except Exception as e:
            self.bot.logger.error(f"Error in timepoll: {str(e)}")
            await ctx.send(embed=create_error_embed(f"❌ Lỗi khi hiển thị kết quả: {str(e)}"))

async def setup(bot):
    await bot.add_cog(Poll(bot))
