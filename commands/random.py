from discord.ext import commands
import discord
import aiohttp
import random

class Random(commands.Cog):
    """A Discord bot cog for random Pokemon generation commands.
    This cog provides functionality to get random Pokemon information from Generation 1
    using the PokeAPI. It includes a command to fetch and display detailed Pokemon stats
    and information in an embedded message format.
    Attributes:
        bot (commands.Bot): The Discord bot instance this cog is attached to.
    Commands:
        rd: Fetches and displays information about a random Generation 1 Pokemon.
            The information includes:
            - Basic stats (height, weight, base experience, types)
            - Base statistics (HP, Attack, Defense, etc.)
            - Special abilities
    Usage:
        /rd: Get information about a random Pokemon from Generation 1
    Cooldown:
        5 seconds per user
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name='rd',
        description='Lấy thông tin về một Pokemon ngẫu nhiên từ thế hệ 1'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)  # Giới hạn 1 lệnh/5 giây/người dùng
    async def rd(self, ctx: commands.Context) -> None:
        """Gets information about a random Generation 1 Pokemon and displays it in an embedded message.
        This command fetches data from the PokeAPI for a randomly selected Pokemon from ID 1-151 (Gen 1)
        and creates a Discord embed containing the Pokemon's:
        - Name and ID number
        - Sprite image
        - Basic information (height, weight, base experience, types)
        - Base stats
        - Abilities
        Parameters
        ----------
        ctx : commands.Context
            The context of the command invocation
        Returns
        -------
        None
        Raises
        ------
        aiohttp.ClientError
            If there is an error connecting to the PokeAPI
        Exception
            For any other unexpected errors
        Example
        -------
        !rd -> Returns an embed with random Pokemon information
        """
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