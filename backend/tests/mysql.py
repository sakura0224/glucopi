import asyncio
import aiomysql

async def test_conn():
    conn = await aiomysql.connect(
        host='localhost',
        port=3306,
        user='root',
        password='root',
        db='glucopi'
    )
    print("✅ MySQL connected!")
    conn.close()

asyncio.run(test_conn())
