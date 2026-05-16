import argparse, asyncio
from apps.ingestion.service import IngestionService
from core.models import IngestRequest

async def main():
    p=argparse.ArgumentParser(); p.add_argument('path'); p.add_argument('--repo-name'); p.add_argument('--force', action='store_true')
    a=p.parse_args(); print(await IngestionService().ingest(IngestRequest(path=a.path, repo_name=a.repo_name, force=a.force)))
if __name__ == '__main__': asyncio.run(main())
