import asyncio
import aiohttp
from multiprocessing import Process
import time

async def make_request(session, url, num):
    """Async function to make a request to the specified URL."""
    try:
        async with session.get(url) as response:
            # print(f"[{num}] Request to {url}: Status Code: {response.status}")
            # Optionally, you can read the response content
            # content = await response.text()
            pass
    except Exception as e:
        # print(f"[{num}] Error making request to {url}: {e}")
        pass

async def stress_test(url, num_requests):
    """Function to perform the stress test using asyncio and aiohttp."""
    async with aiohttp.ClientSession() as session:
        tasks = [make_request(session, url, _) for _ in range(num_requests)]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    target_url = "http://127.0.0.1"
    number_of_requests = 512

    _i = 0
    while True:
        _i += 1
        asyncio.run(stress_test(target_url, number_of_requests))
        print(_i)
    # for i in range(2):
    #     p = Process(target=asyncio.run, args=(stress_test(target_url, number_of_requests, )))
    #     p.run()
