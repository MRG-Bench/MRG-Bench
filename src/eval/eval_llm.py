import json
import os
import pandas as pd
import tqdm
import time
import argparse

from AIClient import OpenAIClient, VertextAIClient, BaseAIClient

def check_response(response: dict):
    """
    check if all the query have been responded correctly.
    """
    if len(response) == 0:
        return 1
    count = 0
    for k, v in response.items():
        if v is None:
            count += 1
    return count

def build_final_prompt(context_type: str, query_data):
    prompt_no_context  = "# You are a professional programmer, please create a function based on the function signature and natural language annotations"\
                    "# Function Signature: {signature}\n"\
                    "# Natural Language Annotations: {description}\n"\
                    "Please only return the code surrounded by ```.\n"
    prompt_in_file_context = "# You are a professional programmer, please create a function based on the function signature and natural language annotations"\
                    "# Here is the related information in the same file:{file_path}:\n"\
                    "```\n{file_content}\n```\n"\
                    "# Function Signature: {signature}\n"\
                    "# Natural Language Annotations: {description}\n"\
                    "Please return the generated code surrounded by ```\n"
    prompt_callee_context = "# You are a professional programmer, please create a function based on the function signature and natural language annotations"\
                    "# Here is the related information useful: \n{callee_context}"\
                    "# Function Signature: {signature}\n"\
                    "# Natural Language Annotations: {description}\n"\
                    "Please return the generated code surrounded by ```\n"
    prompt_project_context = "# You are a professional programmer, please create a function based on the function signature and natural language annotations"\
                    "# Here is the related information in the same directory:\n"\
                    "{file_content}\n"\
                    "# Function Signature: {signature}\n"\
                    "# Natural Language Annotations: {description}\n"\
                    "Please return the generated code surrounded by ```\n"
    context_dict = load_context(context_type)
    signature = query_data["signature"]
    query = query_data["comment"]
    task_id = query_data["task-id"]
    if context_type == "project":
        return prompt_project_context.format(signature=signature, description=query, file_content=context_dict[task_id])
    elif context_type == "callee_func" or context_type == "callee_sig":
        return prompt_callee_context.format(signature=signature, description=query, callee_context=context_dict[task_id])
    elif context_type == "in_file":
        return prompt_in_file_context.format(signature=signature, description=query, 
                                            file_path=query_data["file_path"], file_content=context_dict[task_id])
    else:
        return prompt_no_context.format(signature=signature, description=query)
    
def load_context(context_type):
    if context_type == "no_context":
        return {}
    with open('../data/context_info.json', 'r', encoding='utf-8') as f:
        all_context = json.load(f)
    result_context = {}
    if context_type == "project":
        with open('../data/all_context_project_dict.json', 'r', encoding='utf-8') as f:
            project_context = json.load(f)
        for k in all_context.keys():
            project_name = k.split('-')[0]
            result_context[k] = project_context[project_name]
    else:
        if context_type == "callee_func":
            key = "func"
        elif context_type == "callee_sig":
            key = "signature"
        elif context_type == "in_file":
            key = "in_file_context"
        for k, v in all_context.items():
            result_context[k] = v[key]
    return result_context
def eval_llm(llm: BaseAIClient, context_type: str, language_list: list):
    if context_type not in ["no_context", "callee_func", "callee_sig", "in_file", "project"]:
        raise NotImplementedError("Error context type")
    all_result = {}
    for language in language_list:
        if language not in ['py', 'java', 'go']:
            raise NotImplementedError("Error language type")
        data_df = pd.read_excel(f"../data/{language}_data_final.xlsx")
        print(f"running {language}, data shape: {data_df.shape}")
        
        response_dict = {}
        for index, row  in tqdm.tqdm(data_df.iterrows()):
            final_prompt = build_final_prompt(context_type, row)
            message = [{"role": "user", "content": final_prompt}]
            response = llm.inference(message, 1)
            response_dict[row["task-id"]] = {"response": response}
        all_result[language] = response_dict
        # Note! If you meet some rps limit or network unstable, you can use the following code.
        
        # query_dict = {}
        # for index, row in data_df.iterrows():
        #     final_prompt = build_final_prompt(context_type, row)
        #     message = [{"role": "user", "content": final_prompt}]
        #     query_dict[row["task-id"]] = message
        # response_dict = {}
    
        # while check_response(response_dict) != 0:
        #     for task_id, query in tqdm.tqdm(query_dict.items()):
        #         if task_id in response_dict and response_dict[task_id] != None:
        #             continue
        #         try:
        #             response = llm.inference(query, 1)
        #             response_dict[task_id] = {"response": response}
        #         except:
        #             response_dict[task_id] = None
        #             time.sleep(10)
        #     print(f"There are {check_response(response_dict)} queries failed, start to try again.")
    return all_result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('-context_type', type=str, help='what context will be provide to the model, should be: callee_func, callee_sig, in_file, project or None')
    parser.add_argument('-lang_list', type=str, help='languages, comma separated, one or more in [py, java, go]')
    parser.add_argument('-model_name', type=str, help='model name, any model using open ai client')
    args = parser.parse_args()
    
    context_type = args.context_type
    language_list = args.lang_list.split(',')
    model_name = args.model_name
    
    with open('./config.json', 'r') as f:
        config = json.load(f)
    config = config['ai_client']
    if config['url'] == "" or config['key'] == "":
        raise NotImplementedError("Please provide the url and key for the AI client in config.json")
    llm = OpenAIClient(url=config['url'], key=config['key'], model=model_name)
    all_result = eval_llm(llm, context_type, language_list)
    for lan, gen_dict in all_result.items():
        with open(f"../data/llms/{model_name}_{context_type}_{lan}.json", 'w') as f:
            json.dump(gen_dict, f)