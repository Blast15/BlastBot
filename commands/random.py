import discord
from discord.ext import commands
from discord import app_commands  # Add this import
import aiohttp
import random
from typing import Optional, Dict, Any, Tuple

from utils.constants import POKEMON_TYPE_COLORS, POKEMON_GEN_RANGES, Colors
from utils.embed_helpers import create_error_embed, create_processing_embed

class Random(commands.Cog):
    """A Discord bot cog for random generation commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Reference to type colors and generation ranges from constants
        self.type_colors = POKEMON_TYPE_COLORS
        self.gen_ranges = POKEMON_GEN_RANGES
        self.waifu_api_base = "https://api.waifu.pics"

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
            await ctx.send(
                embed=create_error_embed(f"❌ Thế hệ không hợp lệ. Vui lòng chọn từ 1-{len(self.gen_ranges)}")
            )
            return
            
        min_id, max_id = self.gen_ranges[generation]
        pokemon_id = random.randint(min_id, max_id)
        
        # Hiển thị thông báo đang xử lý
        processing_msg = await ctx.send(
            embed=create_processing_embed("🔍 Đang tìm kiếm Pokemon...")
        )
        
        pokemon_data = await self.fetch_pokemon_data(pokemon_id)
        
        try:
            await processing_msg.delete()
        except:
            pass
            
        if not pokemon_data:
            await ctx.send(
                embed=create_error_embed("❌ Không thể lấy dữ liệu Pokemon. Vui lòng thử lại sau.")
            )
            return
            
        embed = self.create_pokemon_embed(pokemon_data)
        await ctx.send(embed=embed)

    async def fetch_waifu_data(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Fetches data from the waifu.pics API.
        
        Args:
            endpoint: API endpoint to fetch data from
            
        Returns:
            The JSON response data or None if an error occurs
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.waifu_api_base}/{endpoint}") as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        self.bot.logger.error(f"Waifu API error: {response.status}")
                        return None
        except Exception as e:
            self.bot.logger.error(f"Error fetching waifu data: {str(e)}")
            return None
    
    def create_waifu_embed(self, data: Dict[str, Any], title: str) -> discord.Embed:
        """Creates an embed for displaying waifu information.
        
        Args:
            data: The waifu data from the API
            title: The title for the embed
            
        Returns:
            A Discord embed with waifu information
        """
        embed = discord.Embed(
            title=title,
            color=0xF8C8DC  # Sử dụng màu hồng nhạt thay vì Colors.PRIMARY
        )
        
        # Waifu.pics API chỉ trả về URL của hình ảnh
        if "url" in data:
            embed.set_image(url=data["url"])
        
        embed.set_footer(text="Powered by Waifu.pics API")
        return embed

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

    @commands.hybrid_command(
        name='rwf',
        description='Lấy ảnh waifu ngẫu nhiên'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def random_waifu(self, ctx: commands.Context) -> None:
        """Gets a random waifu image."""
        await ctx.defer()
        
        processing_embed = create_processing_embed("⏳ Đang tìm waifu ngẫu nhiên...")
        message = await ctx.send(embed=processing_embed)
        
        # Cập nhật endpoint theo API mới
        data = await self.fetch_waifu_data("sfw/waifu")
        if not data:
            await message.edit(embed=create_error_embed("❌ Không thể lấy dữ liệu waifu. Vui lòng thử lại sau."))
            return
        
        waifu_embed = self.create_waifu_embed(data, "Random Waifu")
        await message.edit(embed=waifu_embed)
    
    @commands.hybrid_command(
        name='rwfc',
        description='Lấy thông tin về một nhân vật waifu ngẫu nhiên'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def random_waifu_character(self, ctx: commands.Context) -> None:
        """Gets information about a random waifu character."""
        await ctx.defer()
        
        processing_embed = create_processing_embed("⏳ Đang tìm nhân vật waifu ngẫu nhiên...")
        message = await ctx.send(embed=processing_embed)
        
        # Cập nhật endpoint theo API mới
        data = await self.fetch_waifu_data("sfw/waifu")
        if not data:
            await message.edit(embed=create_error_embed("❌ Không thể lấy dữ liệu nhân vật waifu. Vui lòng thử lại sau."))
            return
        
        waifu_embed = self.create_waifu_embed(data, "Random Waifu Character")
        await message.edit(embed=waifu_embed)
    
    @commands.hybrid_command(
        name='rwfi',
        description='Lấy ảnh waifu ngẫu nhiên theo thể loại'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    @app_commands.describe(category="Thể loại ảnh (vd: waifu, neko, shinobu, megumin, bully, cuddle, cry, ...)") 
    async def random_waifu_image(self, ctx: commands.Context, category: str = "waifu") -> None:
        """Gets a random waifu image from a specific category.
        
        Args:
            ctx: The command context
            category: The image category (waifu, neko, shinobu, etc.)
        """
        await ctx.defer()
        
        processing_embed = create_processing_embed(f"⏳ Đang tìm ảnh waifu '{category}' ngẫu nhiên...")
        message = await ctx.send(embed=processing_embed)
        
        # Cập nhật endpoint theo API mới
        data = await self.fetch_waifu_data(f"sfw/{category}")
        if not data:
            await message.edit(embed=create_error_embed(f"❌ Không thể lấy ảnh waifu '{category}'. Thể loại không hợp lệ hoặc lỗi API."))
            return
        
        waifu_embed = self.create_waifu_embed(data, f"Random {category.title()} Waifu")
        await message.edit(embed=waifu_embed)

    @random_pokemon.error
    @rdpoke.error
    @random_waifu.error
    @random_waifu_character.error
    @random_waifu_image.error
    async def command_error(self, ctx: commands.Context, error: Exception) -> None:
        """Error handler for Random commands."""
        if isinstance(error, commands.CommandOnCooldown):
            seconds = round(error.retry_after)
            await ctx.send(
                embed=create_error_embed(f"⏳ Vui lòng đợi **{seconds}** giây trước khi dùng lại lệnh này!")
            )
        else:
            await ctx.send(
                embed=create_error_embed("❌ Đã xảy ra lỗi khi thực hiện lệnh. Vui lòng thử lại sau.")
            )
            self.bot.logger.error(f"Random command error: {str(error)}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Random(bot))