import aiohttp
from config import API_BASE_URL

TIMEOUT = aiohttp.ClientTimeout(total=10)

async def list_jobs(search, page):
    url = f"{API_BASE_URL}/jobs/"
    params = {"search": search, "page": page}
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                print(f"list_jobs response: {data}")
                return data
    except Exception as e:
        print(f"list_jobs error: {str(e)}")
        return {"results": [], "next": None}

async def get_job(job_id):
    url = f"{API_BASE_URL}/jobs/{job_id}/"
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.get(url) as response:
                return await response.json()
    except:
        return {}