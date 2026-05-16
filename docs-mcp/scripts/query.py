import argparse, asyncio
from core.retrieval.hybrid import HybridRetriever
async def main():
    p=argparse.ArgumentParser(); p.add_argument('query'); p.add_argument('--repo-name'); p.add_argument('--limit', type=int, default=5)
    a=p.parse_args();
    for r in await HybridRetriever().search(a.query, a.limit, a.repo_name): print(r.model_dump())
if __name__ == '__main__': asyncio.run(main())
