import httpx
import asyncio
from api.api import API

async def test_login():
    api = API("http://192.168.1.172:13378")
    success = await api.login("csj7701", "Chri$7701")
    if success:
        print("Login successful")
    else:
        print("Login failed")

# Run the test
asyncio.run(test_login())
