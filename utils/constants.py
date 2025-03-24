import discord

class Colors:
    """
    Color constants for embeds
    """
    PRIMARY = 0x5865F2      # Discord Blurple
    SUCCESS = 0x57F287      # Green
    ERROR = 0xED4245        # Red
    WARNING = 0xFEE75C      # Yellow
    INFO = 0x5865F2         # Blurple
    LEVELING = 0x9C84EF     # Purple

# Predefined messages for various bot responses
MESSAGES = {
    "NO_PERMISSION": "Bạn không có quyền thực hiện lệnh này.",
    "COMMAND_ERROR": "Đã xảy ra lỗi khi thực hiện lệnh.",
    "INVALID_ARGUMENT": "Tham số không hợp lệ.",
    "USER_NOT_FOUND": "Không tìm thấy người dùng.",
    "CHANNEL_NOT_FOUND": "Không tìm thấy kênh.",
    "ROLE_NOT_FOUND": "Không tìm thấy role.",
    "SUCCESS": "Thành công!",
}

# Emoji mappings for commands and categories
EMOJI_MAP = {
    "moderation": "🛡️",
    "fun": "🎮",
    "info": "ℹ️",
    "leveling": "📊",
    "settings": "⚙️",
    "utility": "🔧",
    "music": "🎵",
    "random": "🎲",
    "poll": "📊",
    "reactionroles": "🎭",
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
}

# Category names with display names
CATEGORY_NAMES = {
    "moderation": "Quản trị",
    "fun": "Giải trí",
    "info": "Thông tin",
    "leveling": "Hệ thống cấp độ",
    "settings": "Cài đặt",
    "utility": "Tiện ích",
    "music": "Âm nhạc",
    "random": "Ngẫu nhiên",
    "poll": "Bình chọn",
    "reactionroles": "Role phản ứng",
    "sync": "Đồng bộ",
    "help": "Trợ giúp",
}

# Pokemon type colors for the random pokemon command
POKEMON_TYPE_COLORS = {
    "normal": 0xA8A77A,
    "fire": 0xEE8130,
    "water": 0x6390F0,
    "electric": 0xF7D02C,
    "grass": 0x7AC74C,
    "ice": 0x96D9D6,
    "fighting": 0xC22E28,
    "poison": 0xA33EA1,
    "ground": 0xE2BF65,
    "flying": 0xA98FF3,
    "psychic": 0xF95587,
    "bug": 0xA6B91A,
    "rock": 0xB6A136,
    "ghost": 0x735797,
    "dragon": 0x6F35FC,
    "dark": 0x705746,
    "steel": 0xB7B7CE,
    "fairy": 0xD685AD,
}

# Pokemon generation ranges (National Pokedex numbers)
POKEMON_GEN_RANGES = {
    1: (1, 151),      # Generation 1: Kanto (1-151)
    2: (152, 251),    # Generation 2: Johto (152-251)
    3: (252, 386),    # Generation 3: Hoenn (252-386)
    4: (387, 493),    # Generation 4: Sinnoh (387-493)
    5: (494, 649),    # Generation 5: Unova (494-649)
    6: (650, 721),    # Generation 6: Kalos (650-721)
    7: (722, 809),    # Generation 7: Alola (722-809)
    8: (810, 905),    # Generation 8: Galar (810-905)
    9: (906, 1025)    # Generation 9: Paldea/Kitakami/Blueberry (906-1025)
}
