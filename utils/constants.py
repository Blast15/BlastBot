"""Constants và messages cho bot"""

# Colors cho embeds
COLORS = {
    'primary': 0x5865F2,      # Discord Blurple
    'success': 0x57F287,      # Green
    'warning': 0xFEE75C,      # Yellow
    'error': 0xED4245,        # Red
    'info': 0x3498db,         # Blue
}

# Emojis
EMOJIS = {
    'success': '✅',
    'error': '❌',
    'warning': '⚠️',
    'info': 'ℹ️',
    'loading': '⏳',
    'wave': '👋',
    'shield': '🛡️',
    'fun': '🎉',
    'mod': '🔨',
    'role': '🎭',
    'bot': '🤖',
    '8ball': '🎱',
    'dice': '🎲',
    'coin': '🪙',
}

# Messages tiếng Việt
MESSAGES = {
    'welcome': {
        'title': 'Chào mừng đến với server!',
        'description': 'Chúc bạn có những trải nghiệm tuyệt vời! 👋',
    },
    'errors': {
        'missing_permissions': 'Bạn không có quyền thực hiện lệnh này!',
        'bot_missing_permissions': 'Bot không có đủ quyền để thực hiện hành động này!',
        'invalid_user': 'Người dùng không hợp lệ!',
        'unknown': 'Đã xảy ra lỗi không xác định!',
        'api_error': 'Lỗi kết nối với Discord API. Vui lòng thử lại sau.',
        'database_error': 'Lỗi database. Thao tác không thành công.',
        'rate_limit': 'Bạn đang dùng lệnh quá nhanh! Vui lòng đợi {remaining}s.',
        'invalid_input': 'Dữ liệu đầu vào không hợp lệ.',
        'user_not_found': 'Không tìm thấy người dùng.',
    },
    'success': {
        'operation_complete': 'Thao tác đã hoàn thành thành công!',
    }
}

# Bot info
BOT_INFO = {
    'name': 'BlastBot',
    'version': '1.0.0',
    'description': 'Discord bot hiện đại với slash commands',
    'author': 'Blast',
}
