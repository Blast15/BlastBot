from discord.ext import commands
import discord
import aiohttp
import random

class Random(commands.Cog):
    """Cog for random Pokemon related commands"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name='rd',
        description='Get information about a random Pokemon from Gen 1'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rd(self, ctx: commands.Context) -> None:
        """Fetches and displays information about a random Pokemon from Generation 1."""
        async with aiohttp.ClientSession() as session:
            try:
                pokemon_id = random.randint(1, 151)
                async with session.get(f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}') as response:
                    if response.status != 200:
                        await ctx.send("Failed to fetch Pokemon data. Please try again later.")
                        return
                    
                    pokemon = await response.json()
                    
                    # Create embed
                    embed = discord.Embed(
                        title=f"#{pokemon['id']:03d} {pokemon['name'].title()}",
                        color=0xFF5733
                    )
                    
                    # Add sprite
                    embed.set_thumbnail(url=pokemon['sprites']['front_default'])
                    
                    # Basic info
                    embed.add_field(
                        name="📊 Basic Info",
                        value=f"Height: {pokemon['height']/10:.1f}m\n"
                              f"Weight: {pokemon['weight']/10:.1f}kg\n"
                              f"Base Exp: {pokemon['base_experience']}\n"
                              f"Types: {', '.join(t['type']['name'].title() for t in pokemon['types'])}",
                        inline=False
                    )
                    
                    # Stats
                    stats = ""
                    for stat in pokemon['stats']:
                        stats += f"{stat['stat']['name'].title()}: {stat['base_stat']}\n"
                    embed.add_field(name="💪 Stats", value=stats, inline=False)
                    
                    # Abilities
                    abilities = ", ".join(ability['ability']['name'].title().replace('-', ' ') 
                                        for ability in pokemon['abilities'])
                    embed.add_field(name="⭐ Abilities", value=abilities, inline=False)
                    
                    await ctx.send(embed=embed)
                    
            except aiohttp.ClientError as e:
                await ctx.send("An error occurred while fetching Pokemon data. Please try again later.")
            except Exception as e:
                await ctx.send("An unexpected error occurred. Please try again later.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Random(bot))