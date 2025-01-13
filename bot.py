import discord
from discord.ext import commands
from database.database import Database
from dotenv import load_dotenv
import os
import sys

# Load environment variables
try:
    load_dotenv()
    TOKEN = os.getenv('TOKEN')
    if not TOKEN:
        raise ValueError("Token not found in .env file")
except Exception as e:
    print(f"Error loading environment variables: {e}")
    sys.exit(1)

class Bot(commands.Bot):
    def __init__(self):
        intent = discord.Intents.default()
        intent.message_content = True
        super().__init__(command_prefix=self.get_prefix, intents=intent, description="Đố ông biết đấy!!", help_command=None)
        self.db = Database()



    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f'Connected to {len(self.guilds)} guilds')
        print('------')
        
        # Set bot's status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, 
                name=f'{len(self.guilds)} servers'
            ),
            status=discord.Status.online
        )


    async def setup_hook(self):
        try:
            # Dỡ toàn bộ extension
            for extension in list(bot.extensions):
                try:
                    await bot.unload_extension(extension)
                except Exception as e:
                    print(f"Failed to unload extension {extension}: {e}")

            # Tải toàn bộ extension từ các thư mục commands và events
            if not os.path.exists('./commands'):
                print("Commands directory not found")
                return

            for filename in os.listdir('./commands'):
                if filename.endswith(".py"):
                    extension = filename[:-3]
                    try:
                        await bot.load_extension(f"commands.{extension}")
                        print(f"Loaded extension '{extension}'")
                    except Exception as e:
                        print(f"Failed to load extension {extension}: {e}")
             
            if not os.path.exists('./events'):
                print("Events directory not found")
                return
            
            for filename in os.listdir('./events'):
                if filename.endswith(".py"):
                    extension = filename[:-3]
                    try:
                        await bot.load_extension(f"events.{extension}")
                        print(f"Loaded extension '{extension}'")
                    except Exception as e:
                        print(f"Failed to load extension {extension}: {e}")

        except Exception as e:
            print(f"Error in setup_hook: {e}")

    async def get_prefix(self, message):
        default_prefix = '!'

        if message.guild is None:
            return default_prefix
        
        try:
            self.db.cursor.execute(
                "SELECT prefix FROM guilds WHERE guild_id = ?",
                (message.guild.id,)
            )
            prefix = self.db.cursor.fetchone()
            return prefix[0] if prefix else default_prefix
        except Exception as e:
            return default_prefix

# Start bot
try:
    bot = Bot()
    bot.run(TOKEN)
except discord.LoginFailure:
    print("Failed to login: Invalid token")
    sys.exit(1)
except Exception as e:
    print(f"Error running bot: {e}")
    sys.exit(1)