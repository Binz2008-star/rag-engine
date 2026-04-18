from app.pipeline import Pipeline
from router.intent_router import IntentRouter
from retrieval.embeddings import Embedder
from retrieval.faiss_index import FaissIndex
from retrieval.multi_retriever import MultiRetriever
from retrieval.reranker import Reranker
from generation.llm import LLMClient
from pathlib import Path

router = IntentRouter.from_active_model()
embedder = Embedder()
indexes = {}
for name in ('cv', 'eco', 'general'):
    try:
        indexes[name] = FaissIndex.load(name, out_dir=Path('models'))
    except:
        pass

retriever = MultiRetriever(indexes=indexes)
reranker = Reranker(embed_fn=embedder.embed_batch)
llm = LLMClient()
pipeline = Pipeline(router=router, embedder=embedder, retriever=retriever, llm=llm, reranker=reranker)

try:
    result = pipeline.run('What is Eco company?', 'test')
    print('Result:', result)
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()
