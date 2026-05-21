from app.main import STORE, RAG

q = 'transformer'
matches = STORE.search(q, top_k=6, min_score=0.0, include_full=True)
print('Matches found:', len(matches))
print('--- fallback answer start ---')
print(RAG._fallback_answer(q, matches))
print('--- fallback answer end ---')
