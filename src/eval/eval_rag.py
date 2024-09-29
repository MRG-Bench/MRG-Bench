
import tqdm
import os
import pandas as pd
import json

from repocoder import eval_repo_coder
from naive_rag import eval_rag_project
from AIClient import BaseAIClient

def eval_rag(rag_type: str, llm: BaseAIClient, language_list=['py', 'java', 'go']):

    if any([1 for l in language_list if l not in ['py', 'java', 'go']]):
        raise ValueError('only support py, java, go')
    
    if rag_type not in ['repo_coder', 'embedding', 'bm25', 'mix']:
        raise ValueError('only support repo_coder, embedding, bm25, mix')
    
    with open('./config.json', 'r') as f:
        config = json.load(f)
        
    for lan in language_list:
        repo_root = f'../repo/{lan}_data'
        dataset = pd.read_excel(f'../data/{lan}_data_final.xlsx')
        predict_result = {}
        for project, dataset_df in dataset.groupby('project'):
            if rag_type == 'repocoder':
                cur_result = eval_repo_coder(dataset_df, project, llm, 
                                            repo_root, config['repo_coder'], lan)
                predict_result.update(cur_result)
            else:
                cur_result = eval_rag_project(rag_type, llm, repo_root, 
                                            dataset_df, lan, config['naive_rag'])
                predict_result.update(cur_result)
        with open(f'../result/rag/{rag_type}_{lan}.json', 'w') as f:
            json.dump(predict_result, f)
    
