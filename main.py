import asyncio
from crawl4ai import *

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://blinkit.com/cn/chips-crisps/cid/1237/940",
        )
        print(result.markdown)

if __name__ == "__main__":
    asyncio.run(main())