import asyncio
from app.database import engine, Base
from sqlalchemy import text

async def main():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        tables = res.fetchall()
        print("SQLAlchemy Tables:", tables)
        for table in tables:
            name = table[0]
            schema = await conn.execute(text(f"PRAGMA table_info({name});"))
            print(f"Table {name} Info:", schema.fetchall())

if __name__ == "__main__":
    asyncio.run(main())
