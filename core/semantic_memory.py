"""Ephemeral semantic index; originals remain in the provider-independent store."""
import hashlib
import json
import threading
import uuid

LOCK = threading.RLock()
MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
CLIENT = None
EMBEDDING = None
SIGNATURE = None


def run(parameters):
    global CLIENT, SIGNATURE, EMBEDDING
    query = parameters.get('query', '')
    if not isinstance(query,str) or not query.strip() or len(query.strip())>1200:
        raise ValueError('Informe uma consulta de ate 1200 caracteres.')
    query=query.strip()
    limit=parameters.get('limit',5)
    if type(limit) is not int:raise ValueError('Informe um limite inteiro de resultados.')
    limit=max(1,min(10,limit))
    from memory.memory_manager import load_memory, _all_entries
    records = _all_entries(load_memory(strict=True))
    if not records:return {'ok':True,'items':[],'complete':True,'source':'Memoria local'}
    if len(records)>1000:raise ValueError('Indice acima de mil registros; consulte memory_control por categoria.')
    from qdrant_client import QdrantClient, models
    from fastembed import TextEmbedding
    signature = hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    with LOCK:
        if EMBEDDING is None:EMBEDDING=TextEmbedding(model_name=MODEL)
        embedding=EMBEDDING
        if signature != SIGNATURE:
            candidate = QdrantClient(location=':memory:')
            texts = [str(entry.get('value','')) for _,_,entry in records]
            try:
                vectors = list(embedding.embed(texts))
                if len(vectors)!=len(records):
                    raise ValueError('Indice incompleto: nem todas as memorias foram processadas. Indice anterior preservado.')
                candidate.create_collection('facts',vectors_config=models.VectorParams(size=len(vectors[0]),distance=models.Distance.COSINE))
                candidate.upsert('facts',points=[models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL,category+'/'+key)),vector=vector.tolist(),payload={'category':category,'key':key}) for (category,key,_),vector in zip(records,vectors)])
            except BaseException:
                candidate.close()
                raise
            previous=CLIENT;CLIENT=candidate
            SIGNATURE = signature
            if previous:previous.close()
        vector = next(embedding.query_embed(query)).tolist()
        hits = CLIENT.query_points('facts',query=vector,limit=limit).points
        originals = {(category,key):entry for category,key,entry in records}
        items = [{'category':hit.payload['category'],'key':hit.payload['key'],'score':hit.score,
                  'record':originals[(hit.payload['category'],hit.payload['key'])]} for hit in hits]
    return {'ok':True,'items':items,'source':'Memoria local','semantic_model':MODEL,
            'persistent_duplicate':False,'instruction':'Resultados relacionados nao sao fatos novos. Confirme fonte/data do registro original.'}
