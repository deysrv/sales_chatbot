

def top_k_mesasage(query, db, top_k=1):
  relevant_chunk=db.query(query_texts=[query], n_results=top_k)
  passage = relevant_chunk['documents'][0][0]
  return passage,relevant_chunk
