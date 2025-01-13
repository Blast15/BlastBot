from discord.ext import commands
import discord
import aiohttp
import random

class Random(commands.Cog):
    """Cog xử lý các lệnh liên quan đến Pokemon ngẫu nhiên"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name='rd',
        description='Lấy thông tin về một Pokemon ngẫu nhiên từ thế hệ 1'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)  # Giới hạn 1 lệnh/5 giây/người dùng
    async def rd(self, ctx: commands.Context) -> None:
        """Lấy và hiển thị thông tin về một Pokemon ngẫu nhiên từ thế hệ 1."""
        async with aiohttp.ClientSession() as session:
            try:
                # Chọn ngẫu nhiên một Pokemon từ thế hệ 1 (ID: 1-151)
                pokemon_id = random.randint(1, 151)
                async with session.get(f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}') as response:
                    if response.status != 200:
                        await ctx.send("Không thể lấy dữ liệu Pokemon. Vui lòng thử lại sau.")
                        return
                    
                    pokemon = await response.json()
                    
                    # Tạo embed hiển thị thông tin
                    embed = discord.Embed(
                        title=f"#{pokemon['id']:03d} {pokemon['name'].title()}",
                        color=0xFF5733
                    )
                    
                    # Thêm hình ảnh Pokemon
                    embed.set_thumbnail(url=pokemon['sprites']['front_default'])
                    
                    # Thông tin cơ bản
                    embed.add_field(
                        name="📊 Thông tin cơ bản",
                        value=f"Chiều cao: {pokemon['height']/10:.1f}m\n"
                              f"Cân nặng: {pokemon['weight']/10:.1f}kg\n"
                              f"Kinh nghiệm cơ bản: {pokemon['base_experience']}\n"
                              f"Hệ: {', '.join(t['type']['name'].title() for t in pokemon['types'])}",
                        inline=False
                    )
                    
                    # Chỉ số
                    stats = ""
                    for stat in pokemon['stats']:
                        stats += f"{stat['stat']['name'].title()}: {stat['base_stat']}\n"
                    embed.add_field(name="💪 Chỉ số", value=stats, inline=False)
                    
                    # Khả năng đặc biệt
                    abilities = ", ".join(ability['ability']['name'].title().replace('-', ' ') 
                                        for ability in pokemon['abilities'])
                    embed.add_field(name="⭐ Khả năng", value=abilities, inline=False)
                    
                    await ctx.send(embed=embed)
                    
            except aiohttp.ClientError as e:
                await ctx.send("Đã xảy ra lỗi khi lấy dữ liệu Pokemon. Vui lòng thử lại sau.")
            except Exception as e:
                await ctx.send("Đã xảy ra lỗi không mong muốn. Vui lòng thử lại sau.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Random(bot))