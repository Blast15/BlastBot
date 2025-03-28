# BlastBot

A feature-rich Discord bot built with Python and discord.py, offering moderation, fun commands, leveling, polls, YouTube integration, and more.

## Features

- **Moderation** - Manage your server with commands for banning, kicking, muting, and more
- **Leveling System** - Reward active members with an XP-based leveling system
- **Reaction Roles** - Allow members to self-assign roles through reactions
- **Polls** - Create interactive polls for your server members
- **YouTube Notifications** - Get notified when your favorite YouTubers upload new content
- **Fun Commands** - Entertain your server with various fun and random commands
- **Temporary Roles** - Assign roles that automatically expire after a set time

## Installation

1. Clone this repository
   ```
   git clone https://github.com/Blast15/BlastBot.git
   cd BlastBot
   ```

2. Install required dependencies
   ```
   pip install -r requirements.txt
   ```

3. Configure the bot
   - Copy `.env.example` to `.env`
   - Add your Discord bot token to the `.env` file

4. Set up the database
   ```
   python -m database.database
   ```

5. Start the bot
   ```
   python bot.py
   ```

## Configuration

Configuration is done through the `.env` file. At minimum, you need to set:
```
TOKEN=your_discord_bot_token_here
```

Additional configuration options can be set in `utils/config.py`.

## Commands

### Moderation
- Ban/kick/mute members
- Clear messages
- Set up auto-moderation

### Fun
- Random games and activities
- Memes and jokes

### Leveling
- XP system for members
- Level roles and rewards

### Polls
- Create polls with multiple options
- Timed poll closing

### Reaction Roles
- Set up role assignment via reactions
- Custom emoji support

### YouTube
- Subscribe to YouTube channels
- Notification system for new videos

## Project Structure

```
.
├── .env.example        # Example environment variables file
├── .gitignore          # Git ignore file
├── bot.py              # Main bot file
├── LICENSE             # License file
├── README.md           # This file
├── requirements.txt    # Python dependencies
├── commands/           # Command modules
│   ├── fun.py          # Fun commands
│   ├── help.py         # Help commands
│   ├── info.py         # Information commands
│   ├── leveling.py     # User leveling system
│   ├── moderation.py   # Moderation commands
│   ├── poll.py         # Poll creation and management
│   ├── random.py       # Random generators
│   ├── reactionroles.py # Reaction role system
│   ├── sync.py         # Command synchronization
│   └── youtube.py      # YouTube integration
├── database/           # Database handling
│   ├── database.py     # Database connection and queries
│   └── schema.sql      # Database schema
├── events/             # Event handlers
│   ├── error_handler.py # Error handling
│   └── temprole_cleanup.py # Temporary role management
└── utils/              # Utility modules
    ├── cache.py        # Caching functionality
    ├── config.py       # Configuration management
    ├── constants.py    # Constant values
    └── embed_helpers.py # Discord embed utilities
```

## License

This project is licensed under the terms included in the [LICENSE](LICENSE) file.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

If you encounter any issues or have questions, please open an issue on the repository.

## Acknowledgements

- [discord.py](https://github.com/Rapptz/discord.py) - The Python library used for Discord API integration
- [Contributors](https://github.com/Blast15/BlastBot/contributors) - Everyone who has contributed to this project