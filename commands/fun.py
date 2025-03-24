import discord
from discord.ext import commands
from discord import app_commands
import random
import aiohttp
import json
from typing import Optional, List
import asyncio

from utils.constants import Colors
from utils.embed_helpers import create_error_embed, create_processing_embed

class Fun(commands.Cog):
    """Fun commands to entertain server members."""
    
    def __init__(self, bot):
        self.bot = bot
        
        # 8ball responses
        self.ball_responses = [
            # Positive responses
            "Chắc chắn rồi.", "Không thể nghi ngờ.", "Dĩ nhiên là thế.", 
            "Có, chắc chắn là vậy.", "Bạn có thể tin vào điều đó.",
            # Neutral responses
            "Có lẽ vậy.", "Triển vọng tốt đấy.", "Trông có vẻ tốt.", 
            "Khó nói lắm.", "Tốt hơn là đừng nói với bạn bây giờ.",
            # Negative responses
            "Đừng có mơ.", "Trả lời là không.", "Nguồn tin của tôi nói không.", 
            "Không có triển vọng.", "Rất đáng ngờ."
        ]
        
        # Rock Paper Scissors choices
        self.rps_choices = ["👊 Búa", "✌️ Kéo", "📄 Bao"]
        self.rps_wins = {
            "👊 Búa": "✌️ Kéo", 
            "✌️ Kéo": "📄 Bao", 
            "📄 Bao": "👊 Búa"
        }
    
    @commands.hybrid_command(name="8ball", description="Hỏi quả cầu ma thuật 8 ball")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @app_commands.describe(question="Câu hỏi cần được trả lời")
    async def eightball(self, ctx: commands.Context, *, question: str):
        """Ask the magic 8ball a question."""
        response = random.choice(self.ball_responses)
        
        embed = discord.Embed(
            title="🎱 Quả cầu ma thuật",
            color=Colors.INFO
        )
        embed.add_field(name="Câu hỏi:", value=question, inline=False)
        embed.add_field(name="Trả lời:", value=response, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="roll", description="Tung xúc xắc")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @app_commands.describe(
        sides="Số mặt của xúc xắc (mặc định: 6)",
        count="Số lượng xúc xắc (mặc định: 1)"
    )
    async def roll(self, ctx: commands.Context, sides: Optional[int] = 6, count: Optional[int] = 1):
        """Roll one or more dice with a specified number of sides."""
        if sides < 1 or sides > 100:
            await ctx.send(embed=create_error_embed("❌ Số mặt xúc xắc phải từ 1 đến 100."))
            return
            
        if count < 1 or count > 10:
            await ctx.send(embed=create_error_embed("❌ Số lượng xúc xắc phải từ 1 đến 10."))
            return
            
        results = [random.randint(1, sides) for _ in range(count)]
        total = sum(results)
        
        # Detailed results of each die
        details = ", ".join([str(r) for r in results])
        
        embed = discord.Embed(
            title="🎲 Kết quả tung xúc xắc",
            description=f"Tung {count}d{sides}",
            color=Colors.INFO
        )
        
        if count > 1:
            embed.add_field(name="Chi tiết", value=details, inline=False)
            embed.add_field(name="Tổng", value=str(total), inline=False)
        else:
            embed.add_field(name="Kết quả", value=str(total), inline=False)
            
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="coinflip", aliases=["flip"], description="Tung đồng xu")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def coinflip(self, ctx: commands.Context):
        """Flip a coin and get heads or tails."""
        result = random.choice(["Mặt sấp", "Mặt ngửa"])
        
        embed = discord.Embed(
            title="🪙 Tung đồng xu",
            description=f"Kết quả: **{result}**",
            color=Colors.INFO
        )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="rps", description="Chơi kéo búa bao với bot")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @app_commands.describe(choice="Lựa chọn của bạn: búa, kéo, hoặc bao")
    async def rps(self, ctx: commands.Context, choice: Optional[str] = None):
        """Play rock-paper-scissors with the bot."""
        if choice:
            choice = choice.lower()
            # Map user input to proper choices
            if choice in ["búa", "bua", "rock", "r", "👊"]:
                user_choice = "👊 Búa"
            elif choice in ["kéo", "keo", "scissors", "s", "✌️"]:
                user_choice = "✌️ Kéo"
            elif choice in ["bao", "paper", "p", "📄"]:
                user_choice = "📄 Bao"
            else:
                await ctx.send(embed=create_error_embed(
                    "❌ Lựa chọn không hợp lệ! Hãy chọn: búa, kéo, hoặc bao."
                ))
                return
                
            bot_choice = random.choice(self.rps_choices)
            
            # Determine winner
            if user_choice == bot_choice:
                result = "Hòa!"
                color = Colors.WARNING
            elif self.rps_wins[user_choice] == bot_choice:
                result = "Bạn thắng!"
                color = Colors.SUCCESS
            else:
                result = "Bot thắng!"
                color = Colors.ERROR
                
            embed = discord.Embed(
                title="✂️ Kéo Búa Bao",
                description=f"**{result}**",
                color=color
            )
            embed.add_field(name="Bạn chọn", value=user_choice, inline=True)
            embed.add_field(name="Bot chọn", value=bot_choice, inline=True)
            
            await ctx.send(embed=embed)
            
        else:
            # If no choice was given, create button interaction
            view = RPSView(self.rps_choices, self.rps_wins)
            await ctx.send(
                embed=discord.Embed(
                    title="✂️ Kéo Búa Bao",
                    description="Chọn một lựa chọn dưới đây:",
                    color=Colors.INFO
                ),
                view=view
            )
    
    @commands.hybrid_command(name="fact", description="Hiển thị một fact ngẫu nhiên")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def fact(self, ctx: commands.Context):
        """Show a random fun fact."""
        processing_msg = await ctx.send(embed=create_processing_embed("🔍 Đang tìm kiếm fact..."))
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en") as response:
                    if response.status != 200:
                        await processing_msg.edit(embed=create_error_embed(
                            "❌ Không thể lấy fact. Hãy thử lại sau!"
                        ))
                        return
                        
                    data = await response.json()
                    fact = data.get("text", "Không tìm thấy fact nào.")
                    
                    embed = discord.Embed(
                        title="📚 Fact ngẫu nhiên",
                        description=fact,
                        color=Colors.INFO
                    )
                    
                    if source := data.get("source"):
                        embed.set_footer(text=f"Nguồn: {source}")
                    
                    await processing_msg.edit(embed=embed)
        except Exception as e:
            await processing_msg.edit(embed=create_error_embed(
                f"❌ Đã xảy ra lỗi: {str(e)}"
            ))
            self.bot.logger.error(f"Error fetching fact: {str(e)}")
    
    @commands.hybrid_command(name="joke", description="Kể một câu chuyện cười")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def joke(self, ctx: commands.Context):
        """Tell a random joke."""
        processing_msg = await ctx.send(embed=create_processing_embed("🔍 Đang tìm kiếm chuyện cười..."))
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://official-joke-api.appspot.com/random_joke") as response:
                    if response.status != 200:
                        await processing_msg.edit(embed=create_error_embed(
                            "❌ Không thể lấy chuyện cười. Hãy thử lại sau!"
                        ))
                        return
                        
                    data = await response.json()
                    setup = data.get("setup", "")
                    punchline = data.get("punchline", "")
                    
                    embed = discord.Embed(
                        title="😂 Chuyện cười",
                        color=Colors.INFO
                    )
                    
                    if setup and punchline:
                        # First send just the setup
                        embed.description = setup
                        await processing_msg.edit(embed=embed)
                        
                        # Wait 2 seconds for dramatic effect
                        await asyncio.sleep(2)
                        
                        # Then add the punchline
                        embed.description = f"{setup}\n\n**{punchline}**"
                        await processing_msg.edit(embed=embed)
                    else:
                        await processing_msg.edit(embed=create_error_embed(
                            "❌ Không thể lấy chuyện cười. Hãy thử lại sau!"
                        ))
        except Exception as e:
            await processing_msg.edit(embed=create_error_embed(
                f"❌ Đã xảy ra lỗi: {str(e)}"
            ))
            self.bot.logger.error(f"Error fetching joke: {str(e)}")

class RPSView(discord.ui.View):
    """View for Rock Paper Scissors buttons."""
    def __init__(self, choices, wins_against):
        super().__init__(timeout=30)
        self.choices = choices
        self.wins_against = wins_against
        
        # Add buttons for each choice
        for choice in choices:
            emoji = choice.split()[0]
            self.add_item(RPSButton(choice, emoji))
    
    async def on_timeout(self):
        """Disable buttons when the view times out."""
        for item in self.children:
            item.disabled = True

class RPSButton(discord.ui.Button):
    """Button for a Rock Paper Scissors choice."""
    def __init__(self, choice, emoji):
        super().__init__(style=discord.ButtonStyle.primary, label=choice.split()[1], emoji=emoji)
        self.choice = choice
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button press."""
        view: RPSView = self.view
        
        # Bot choice
        bot_choice = random.choice(view.choices)
        
        # Determine winner
        if self.choice == bot_choice:
            result = "Hòa!"
            color = Colors.WARNING
        elif view.wins_against[self.choice] == bot_choice:
            result = "Bạn thắng!"
            color = Colors.SUCCESS
        else:
            result = "Bot thắng!"
            color = Colors.ERROR
            
        embed = discord.Embed(
            title="✂️ Kéo Búa Bao",
            description=f"**{result}**",
            color=color
        )
        embed.add_field(name="Bạn chọn", value=self.choice, inline=True)
        embed.add_field(name="Bot chọn", value=bot_choice, inline=True)
        
        # Disable all buttons after a choice is made
        for button in view.children:
            button.disabled = True
            
        await interaction.response.edit_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Fun(bot))
