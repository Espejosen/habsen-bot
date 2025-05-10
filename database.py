import aiosqlite

class Database:
    @staticmethod
    async def init():
        async with aiosqlite.connect("warnings.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    guild_id INTEGER,
                    violation_type TEXT,
                    reason TEXT,
                    moderator_id INTEGER,
                    timestamp TEXT,
                    expires_at TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS jails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    guild_id INTEGER,
                    moderator_id INTEGER,
                    start_time TEXT,
                    end_time TEXT,
                    original_roles TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS badges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    guild_id INTEGER,
                    badge_url TEXT,
                    status TEXT,
                    moderator_id INTEGER,
                    submitted_at TEXT,
                    reviewed_at TEXT,
                    reason TEXT,
                    message_id INTEGER
                )
            ''')
            await db.commit()
