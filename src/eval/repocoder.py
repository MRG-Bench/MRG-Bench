import os
import tqdm
import pandas as pd
import tiktoken
import numpy as np

from repocoder import RepoCoderIndex
from AIClient import BaseAIClient


class LineChunkData():
    def __init__(self, file_path, code_chunk, start_line, end_line):
        self.file_path = file_path
        self.code_chunk = code_chunk
        self.start_line = start_line
        self.end_line = end_line
        

def line_splitter(file_path, chunk_size, chunk_overlap):
    """
    Reads a file and splits it into chunks of specified size with overlap.

    :param file_path: Path to the text file.
    :param chunk_size: Maximum number of lines in each chunk.
    :param chunk_overlap: Number of overlapping lines between adjacent chunks.
    :return: A list of chunks, where each chunk is a list of lines.
    """
    if chunk_size <= chunk_overlap:
        raise ValueError("chunk_size must be greater than chunk_overlap.")

    # read all file lines
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    #  make chunks list
    chunks = []
    start_index = 0
    total_lines = len(lines)
    final_chunk = False
    while final_chunk is False:
        end_index = start_index + chunk_size
        
        # if lines are less than chunk_size, then end_index will be greater than total_lines
        if end_index > total_lines:
            end_index = total_lines
            final_chunk = True
        
        # append chunk
        chunks.append(LineChunkData(file_path, ''.join(lines[start_index:end_index]), start_index, end_index))
        
        # update start_index
        start_index = end_index - chunk_overlap

    return chunks

class RepoCoderIndex:
    def __init__(self, repo_path, chunk_size, chunk_overlap, lan):
        self.tokenizer = tiktoken.encoding_for_model('gpt-3.5-turbo')
        self.dataset = []
        self.dataset_tokens = []
        self.lan = lan
        self.build(repo_path, chunk_size, chunk_overlap, lan)
        self.dataset_size = len(self.dataset)

    
    def build(self, repo_path, chunk_size, chunk_overlap, lan='py'):
        # 读取repo中所有文件
        code_files = []
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                if file.endswith(f".{lan}") and "test" not in file.lower() and ".ipynb" not in root:
                    code_files.append(os.path.join(root, file))
        print(len(code_files))
        # 为每个文件生成chunks
        for file in tqdm.tqdm(code_files):
            chunks = line_splitter(file, chunk_size, chunk_overlap)
            for chunk in chunks:
                self.dataset.append(chunk)
                self.dataset_tokens.append(self.tokenize(chunk.code_chunk))
    
    def tokenize(self, text):
        # return self.tokenizer.encode(text)
        return self.tokenizer.encode_ordinary(text)
    
    @staticmethod
    def jaccard_similarity(list1, list2):
        set1 = set(list1)
        set2 = set(list2)
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return float(intersection) / union

    def retrive(self, query, k):
        query_tokens = self.tokenize(query)
        sim_arr = []

        for i in range(self.dataset_size):
            sim_arr.append(self.jaccard_similarity(query_tokens, self.dataset_tokens[i]))
        sorted_index = np.argsort(sim_arr)
        return [self.dataset[i] for i in sorted_index[-k:]]


def eval_repocoder_project(dataset_df, repo_coder_index, llm, k):
    def preprocess(query):
        result = repo_coder_index.retrive(query, k)
        code_chunk_prompt = "-"*30 + "\n" + "{code_chunk}\n" + "-"*30 + "\n"
        final_prompt = "# Below are some relevant code snippets for the given query:\n" \
                        "{code_chunks}" \
                        "# You are a prefessional programmer, please create a function based on the function signature and natural language annotations"\
                        "# Function Signature: {signature}\n"\
                        "# Natural Language Annotations: {description}\n"\
                        "Please only return the code surrounded by ```, do not reply any explaination\n"
                        
        code_chunk_message = ""       
        for res in result:
            code_chunk_message += code_chunk_prompt.format(code_chunk=res.code_chunk)
        final_query = final_prompt.format(code_chunks=code_chunk_message, 
                                        signature=data["signature"], 
                                        description=data["comment"])
    
        messages = [{"role": "user", "content": final_query}]
        # print("="*15+"retrived final query: \n" +"="*15 + final_query)
        response = llm.inference(messages, 1)
        return response[0]
    
    predict_result = {}
    for index, data in tqdm.tqdm(dataset_df.iterrows()):
        # print("*"*15 + str(index)+ "*"*15)
        query = data["comment"]
        retrive_query = preprocess(query)
        result = repo_coder_index.retrive(retrive_query, k)
        code_chunk_prompt = "-"*30 + "\n" + "{code_chunk}\n" + "-"*30 + "\n"
        final_prompt = "# Below are some relevant code snippets for the given query:\n" \
                        "{code_chunks}" \
                        "# You are a prefessional programmer, please create a function based on the function signature and natural language annotations"\
                        "# Function Signature: {signature}\n"\
                        "# Natural Language Annotations: {description}\n"\
                        "Please only return the code surrounded by ```, do not reply any explaination\n"
                        
        code_chunk_message = ""       
        for res in result:
            code_chunk_message += code_chunk_prompt.format(code_chunk=res.code_chunk)
        final_query = final_prompt.format(
            code_chunks=code_chunk_message, 
            signature=data["signature"], 
            description=data["comment"]
            )
        messages = [{"role": "user", "content": final_query}]
        response = llm.inference(messages, 1)
        predict_result[data['task-id']] = {"final_query": final_query, "response": response}
        
    return predict_result

def eval_repo_coder(dataset_df: pd.DataFrame, project: str, 
                    llm: BaseAIClient, repo_root: str,
                    config: dict, lan: str):
    chunk_size, chunk_overlap, k = config['chunk_size'], config['chunk_overlap'], config['k']
    repo_path = os.path.join(repo_root, project)
    repo_coder_index = RepoCoderIndex(repo_path, chunk_size, chunk_overlap, lan)
    cur_predict_result = eval_repocoder_project(dataset_df, repo_coder_index, llm, k)
    return cur_predict_result
