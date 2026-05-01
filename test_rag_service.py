import sys
sys.path.insert(0, r'd:\AI\assistant')
from api.server.services.rag_service import RagService
from pathlib import Path
import asyncio

async def test():
    service = RagService(index_dir=Path(r'd:\AI\assistant\models'))
    print('Starting RAG service...')
    await service.startup()
    print(f'RAG ready: {service.ready}')
    print(f'Index count: {service.index_count}')
    if service.ready:
        result = await service.query('What services does ECO Technology provide?')
        print(f"Answer: {result.get('answer', 'N/A')[:200]}...")
        print(f"Sources: {len(result.get('sources', []))}")

asyncio.run(test())
