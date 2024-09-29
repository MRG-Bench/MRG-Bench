from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers import LanguageParser
from langchain_text_splitters import Language
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
# import
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import (
    Language,
    RecursiveCharacterTextSplitter,
)
import tqdm
import pandas as pd

from AIClient import BaseAIClient

def load_embedding_model(model_name="BAAI/bge-m3"):

    encode_kwargs = {"normalize_embeddings": True}
    hf = HuggingFaceBgeEmbeddings(
        model_name=model_name, encode_kwargs=encode_kwargs
    )
    return hf

def load_code_data(folder, lan, chunk_size=500, chunk_overlap=50):
    
    if lan == 'py':
        language = Language.PYTHON
    elif lan == 'java':
        language = Language.JAVA
    elif lan == 'go':
        language = Language.GO

    loader = GenericLoader.from_filesystem(
        folder,
        glob=f"**/*.{lan}",
        suffixes=[f".{lan}"],
        parser=LanguageParser(language),
    )
    docs = loader.load()
    
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=language, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    result = splitter.split_documents(docs)
    print(len(result))
    result = [i for i in result if i.page_content is not None]
    print(len(result))
    return result

def get_final_prompt(docs, row):
    code_chunk_prompt = "-"*30 + "\n" + "{code_chunk}\n" + "-"*30 + "\n"
    code_chunk_context = ""
    for doc in docs:
        code_chunk_context += code_chunk_prompt.format(code_chunk=doc.page_content)
    final_prompt = "# Below are some relevant code snippets for the given query:\n" \
                    "{code_chunks}" \
                    "# You are a prefessional programmer, please create a function based on the function signature and natural language annotations"\
                    "# Function Signature: {signature}\n"\
                    "# Natural Language Annotations: {description}\n"\
                    "Please only return the code surrounded by ```, do not reply any explaination\n"
    return final_prompt.format(code_chunks=code_chunk_context, signature=row["signature"], description=row["comment"])

def get_retriever(rag_type: str, repo_root: str, lan, config):
    chunk_size = config["chunk_size"]
    chunk_overlap = config["chunk_overlap"]
    k = config['k']
    
    docs = load_code_data(repo_root, lan, chunk_size=chunk_size, chunk_overlap=chunk_overlap, chunk_overlap=chunk_overlap)
    
    if rag_type == "embedding":
        hf = load_embedding_model()
        db = FAISS.from_documents(docs, hf)
        db_retriever = db.as_retriever(search_kwargs={"k": k})
        return db_retriever
    elif rag_type == "bm25":
        bm25_retriever = BM25Retriever.from_documents(docs)
        bm25_retriever.k = k
        return bm25_retriever
    else:
        ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, db_retriever], weights=[0.5, 0.5]
        )
        return ensemble_retriever

def eval_rag_project(rag_type: str, llm: BaseAIClient, 
                    repo_root: str, dataset_df: pd.DataFrame, 
                    lan: str, config: dict):
    retriever = get_retriever(rag_type, repo_root, lan, config)
    result_dict = {}
    for index, row in tqdm.tqdm(dataset_df.iterrows()):
        # print(row['comment'])
        related_docs = retriever.invoke(row["comment"])
        final_query = get_final_prompt(related_docs, row)
        message = [{"role": "user", "content": final_query}]
        response = llm.inference(message, 3)
        result_dict[row['task-id']] = {"final_query": final_query, "response": response}
    return result_dict

    