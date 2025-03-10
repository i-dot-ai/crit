from langchain.indexes import SQLRecordManager, index
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_openai import AzureOpenAIEmbeddings
from crit.logging import logger


def generate_comparison_pairs_by_vector(chunk_map):
    vector_store = Chroma(
        collection_name="crit",
        embedding_function=AzureOpenAIEmbeddings(
            azure_deployment="text-embedding-3-large"
        ),
        persist_directory="./chroma.db",
    )

    namespace = "chroma/crit"
    record_manager = SQLRecordManager(
        namespace, db_url="sqlite:///embedding_cache.db")

    record_manager.create_schema()

    docs = []
    for _chunk_id, chunk in chunk_map.items():
        metadata = {"document": chunk.document, "id": chunk.id}
        docs.append(Document(page_content=chunk.text, metadata=metadata))

    index(docs, record_manager, vector_store,
          cleanup="full", source_id_key="document")

    pairs = set()  # we'll add each sorted pair at most once

    k = 5
    logger.info(f"Collecting {k} nearest chunks")

    for current_chunk_id, chunk in chunk_map.items():
        similar_chunks = vector_store.similarity_search_with_score(
            chunk.text,
            k=k + 1,  # we will get this doc plus k others
        )

        similar_chunk_ids = []
        for chunk, _score in similar_chunks:
            similar_chunk_ids.append(chunk.metadata["id"])

            if len(similar_chunk_ids) == k + 1:
                break

        for similar_chunk_id in similar_chunk_ids:
            pair = tuple(sorted([current_chunk_id, similar_chunk_id]))
            pairs.add(pair)

    return pairs
