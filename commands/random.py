import discord
from discord.ext import commands
import aiohttp
import random
from typing import Optional, Dict, Any, Tuple

class Random(commands.Cog):
    """A Discord bot cog for random Pokemon generation commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Màu sắc cho các thể loại Pokemon
        self.type_colors = {
            "normal": 0xA8A77A, "fire": 0xEE8130, "water": 0x6390F0, 
            "electric": 0xF7D02C, "grass": 0x7AC74C, "ice": 0x96D9D6, 
            "fighting": 0xC22E28, "poison": 0xA33EA1, "ground": 0xE2BF65, 
            "flying": 0xA98FF3, "psychic": 0xF95587, "bug": 0xA6B91A, 
            "rock": 0xB6A136, "ghost": 0x735797, "dragon": 0x6F35FC, 
            "dark": 0x705746, "steel": 0xB7B7CE, "fairy": 0xD685AD
        }
        # Giới hạn ID cho các thế hệ Pokemon
        self.gen_ranges = {
            1: (1, 151),      # Thế hệ 1: 1-151
            2: (152, 251),    # Thế hệ 2: 152-251
            3: (252, 386),    # Thế hệ 3: 252-386
            4: (387, 493),    # Thế hệ 4: 387-493
            5: (494, 649),    # Thế hệ 5: 494-649
            6: (650, 721),    # Thế hệ 6: 650-721
            7: (722, 809),    # Thế hệ 7: 722-809
            8: (810, 898),    # Thế hệ 8: 810-898
            9: (899, 1008)    # Thế hệ 9: 899-1008 (tính đến 2023)
        }

    async def fetch_pokemon_data(self, pokemon_id: int) -> Optional[Dict[str, Any]]:
        """Fetches Pokemon data from the PokeAPI.
        
        Args:
            pokemon_id: The ID of the Pokemon to fetch
            
        Returns:
            Optional dictionary containing Pokemon data or None if there was an error
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}') as response:
                    if response.status != 200:
                        return None
                    return await response.json()
        except Exception as e:
            self.bot.logger.error(f"Error fetching Pokemon data: {str(e)}")
            return None

    def create_pokemon_embed(self, pokemon: Dict[str, Any]) -> discord.Embed:
        """Creates an embed for Pokemon data.
        
        Args:
            pokemon: Dictionary containing Pokemon data from the API
            
        Returns:
            discord.Embed: A formatted embed with Pokemon information
        """
        # Xác định màu embed dựa trên loại Pokemon chính
        primary_type = pokemon['types'][0]['type']['name']
        embed_color = self.type_colors.get(primary_type, 0xFF5733)
        
        # Tạo embed với tiêu đề và màu
        embed = discord.Embed(
            title=f"#{pokemon['id']:03d} {pokemon['name'].title()}",
            color=embed_color
        )
        
        # Thêm hình ảnh Pokemon
        if sprite_url := pokemon['sprites']['front_default']:
            embed.set_thumbnail(url=sprite_url)
        
        # Thêm các loại Pokemon
        types = ", ".join(t['type']['name'].title() for t in pokemon['types'])
        
        # Thông tin cơ bản
        embed.add_field(
            name="📊 Thông tin cơ bản",
            value=f"**Chiều cao:** {pokemon['height']/10:.1f}m\n"
                  f"**Cân nặng:** {pokemon['weight']/10:.1f}kg\n"
                  f"**Kinh nghiệm cơ bản:** {pokemon['base_experience'] or 'N/A'}\n"
                  f"**Hệ:** {types}",
            inline=False
        )
        
        # Chỉ số
        stats = ""
        stat_names = {
            "hp": "HP", "attack": "Tấn Công", "defense": "Phòng Thủ",
            "special-attack": "Tấn Công Đặc Biệt", "special-defense": "Phòng Thủ Đặc Biệt",
            "speed": "Tốc Độ"
        }
        
        for stat in pokemon['stats']:
            stat_name = stat_names.get(stat['stat']['name'], stat['stat']['name'].title())
            stats += f"**{stat_name}:** {stat['base_stat']}\n"
            
        embed.add_field(name="💪 Chỉ số", value=stats, inline=False)
        
        # Khả năng đặc biệt
        abilities = ", ".join(
            f"**{ability['ability']['name'].title().replace('-', ' ')}**" + 
            (" (Ẩn)" if ability['is_hidden'] else "") 
            for ability in pokemon['abilities']
        )
        embed.add_field(name="⭐ Khả năng", value=abilities, inline=False)
        
        return embed

    async def get_random_pokemon_from_gen(self, ctx: commands.Context, generation: int) -> None:
        """Fetches and displays a random Pokemon from the specified generation.
        
        Args:
            ctx: The command context
            generation: The Pokemon generation number (1-9)
        """
        if generation not in self.gen_ranges:
            await ctx.send(f"❌ Thế hệ không hợp lệ. Vui lòng chọn từ 1-{len(self.gen_ranges)}")
            return
            
        min_id, max_id = self.gen_ranges[generation]
        pokemon_id = random.randint(min_id, max_id)
        
        # Hiển thị thông báo đang xử lý
        processing_msg = await ctx.send("🔍 Đang tìm kiếm Pokemon...")
        
        pokemon_data = await self.fetch_pokemon_data(pokemon_id)
        
        try:
            await processing_msg.delete()
        except:
            pass
            
        if not pokemon_data:
            await ctx.send("❌ Không thể lấy dữ liệu Pokemon. Vui lòng thử lại sau.")
            return
            
        embed = self.create_pokemon_embed(pokemon_data)
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name='random_pokemon',
        aliases=['rd'],
        description='Lấy thông tin về một Pokemon ngẫu nhiên'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def random_pokemon(self, ctx: commands.Context, generation: Optional[int] = None) -> None:
        """Gets information about a random Pokemon and displays it in an embedded message.
        
        Args:
            ctx: The command context
            generation: Optional Pokemon generation (1-9), random if not specified
        """
        # Nếu không chỉ định thế hệ, chọn ngẫu nhiên
        if generation is None:
            generation = random.randint(1, len(self.gen_ranges))
        
        await self.get_random_pokemon_from_gen(ctx, generation)
    
    @commands.hybrid_command(
        name='rd1',
        description='Lấy thông tin về một Pokemon ngẫu nhiên từ thế hệ 1'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rd1(self, ctx: commands.Context) -> None:
        """Gets information about a random Generation 1 Pokemon."""
        await self.get_random_pokemon_from_gen(ctx, 1)
    
    @commands.hybrid_command(
        name='rd2',
        description='Lấy thông tin về một Pokemon ngẫu nhiên từ thế hệ 2'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rd2(self, ctx: commands.Context) -> None:
        """Gets information about a random Generation 2 Pokemon."""
        await self.get_random_pokemon_from_gen(ctx, 2)
        
    @commands.hybrid_command(
        name='rdpoke',
        description='Lấy thông tin về một Pokemon ngẫu nhiên từ thế hệ cụ thể'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rdpoke(self, ctx: commands.Context, generation: int = 1) -> None:
        """Gets information about a random Pokemon from a specific generation.
        
        Args:
            ctx: The command context
            generation: The Pokemon generation number (1-9)
        """
        await self.get_random_pokemon_from_gen(ctx, generation)

    @random_pokemon.error
    @rd1.error
    @rd2.error
    @rdpoke.error
    async def pokemon_error(self, ctx: commands.Context, error: Exception) -> None:
        """Error handler for Pokemon commands."""
        if isinstance(error, commands.CommandOnCooldown):
            seconds = round(error.retry_after)
            await ctx.send(f"⏳ Vui lòng đợi **{seconds}** giây trước khi dùng lại lệnh này!")
        else:
            await ctx.send("❌ Đã xảy ra lỗi khi lấy thông tin Pokemon. Vui lòng thử lại sau.")
            self.bot.logger.error(f"Pokemon command error: {str(error)}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Random(bot))