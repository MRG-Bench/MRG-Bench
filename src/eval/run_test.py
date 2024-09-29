import os
import subprocess
import pandas as pd
import tqdm
import json
import argparse

import subprocess
from eval.parse_run_log import parse_log, extract_code_blocks

parser = argparse.ArgumentParser()
parser.add_argument("-df_path", help="Path to the input DataFrame file")
parser.add_argument("-result_path", help="Path to the output result file")
parser.add_argument("-lan", help="Programming language")

args = parser.parse_args()

df_path = args.df_path
result_path = args.result_path
lan = args.lan
dataset_root = "/root/repos/"
dataset_root = os.path.join(dataset_root, f'{lan}_data')

def get_tab_count(s:str):
    if s[0] == ' ' or s[0] == '\t':
        return 1
    else:
        return 0
    # tab_count = 0
    # if s[0] == ' ':
    #     for i in range(len(s)):
    #         if s[i] == ' ':
    #             tab_count += 1
    #         else:
    #             break
    #     tab_count = tab_count // 4
    # elif s[0] == '\t':
    #     for i in range(len(s)):
    #         if s[i] == '\t':
    #             tab_count += 1
    #         else:
    #             break
    # return tab_count

def run_command_with_timeout(command, timeout):
    try:
        # 创建并运行子进程
        result = subprocess.run(command, capture_output=True, timeout=timeout,
                                    shell=True, text=True,
                                    executable='/bin/bash', errors='ignore')        
        return result
    except subprocess.TimeoutExpired:
        # 如果超时，终止进程
        print("time out for command : ", command)
        return "TimeOut ERROR"

def run_cstest(row):
    
    base_command = "dotnet test --filter "
    test_funcs = row["test_funcs"].split(" ")
    args_func = []
    for t in test_funcs:
        path, func = t.split("::")
        args_func.append(func)
    command = base_command + '"' + " | ".join(args_func) + '"'

    # if "shesha-framework" in row["file_path"]:
    #     command = "cd shesha-core && " + command + "; cd .."

    result = run_command_with_timeout(command, 40)
    if isinstance(result, str):
        return result
    else:
        return result.stdout + "\n" + result.stderr

def run_pytest(row):
    base_command = "pytest "
    
    args = row['test_funcs']
    command = base_command + args
    result = run_command_with_timeout(command, 40)
    if isinstance(result, str):
        return result
    else:
        return result.stdout + "\n" + result.stderr

def run_javatest(row):
    
    result_log = ""
    result = run_command_with_timeout(row['test_command'], 40)
    if isinstance(result, str):
        result_log += result
    else:
        result_log += result.stdout + "\n" + result.stderr
    return result_log

def run_gotest(row):
    result_log = ""
    func_file_name = os.path.basename(row['file_path'])
    test_cases = row['test_funcs'].split(" ")
    for t in test_cases:
        file_path = t.split("::")[0]
        file_name = os.path.basename(file_path)
        if file_name.replace("_test", '') != func_file_name:
            print("not test file")
            continue
        test_func = t.split("::")[1]
        command = "go test -run " + test_func
        if '/' not in file_path:
            result = run_command_with_timeout(command, 40)
            if isinstance(result, str):
                result_log += result
            else:
                result_log += result.stdout + "\n" + result.stderr
        else:
            folder = os.path.dirname(file_path)
            cur_folder = os.getcwd()
            os.chdir(folder)
            result = run_command_with_timeout(command, 10)
            if isinstance(result, str):
                result_log += result
            else:
                result_log += result.stdout + "\n" + result.stderr
            os.chdir(cur_folder)
    return result_log

def save_generate_code(file_path, start_line, end_line, code: str):
    generated_code_lines = code.split('\n')
    generated_code_lines = [i+'\n' for i in generated_code_lines]
    with open(file_path, 'r') as f:
        data = f.readlines()

    # for method in class or inline method
    tab_count = get_tab_count(data[start_line])
    exist_tab_count = get_tab_count(generated_code_lines[0])
    need_tab = tab_count - exist_tab_count
    if need_tab > 0 :
        generated_code_lines = ['    '*need_tab + line for line in generated_code_lines]
    
    # remove existing code
    left_context = data[:start_line]
    gt_context = data[start_line:end_line+1]
    right_context = data[end_line+1:]
    new_data_lines = left_context + generated_code_lines + right_context

    with open(file_path, 'w') as f:
        f.write(''.join(new_data_lines))
    return data

def restore_file_lines(data_lines, file_path):
    with open(file_path, 'w') as f:
        f.write(''.join(data_lines))
    return

def check_code_style(code: str):
    code_blocks = extract_code_blocks(code)
    if len(code_blocks) == 0:
        return None
    else:
        max_len_code = code_blocks[0]
        for block in code_blocks:
            if len(block) > len(max_len_code):
                max_len_code = block
        return max_len_code

def eval(test_df: pd.DataFrame, response_dict: dict, dataset_root: str, lan: str):
    all_test_logs = {}
    cwd = os.getcwd()
    
    for index, row in test_df.iterrows():
        os.chdir(os.path.join(dataset_root, row['project']))
        task_id = row['task-id']
        file_path = os.path.join(dataset_root, row['project'], row['file_path'])
        start_line = row['func_start']
        end_line = row['func_end']
        responses = response_dict[task_id]["response"]
        test_logs = []
        for r in responses:
            code = check_code_style(r)
            if code is None:
                test_logs.append("FAILED: No code block")
                continue
            original_file_lines = save_generate_code(file_path, start_line, end_line, code)
            test_dir = os.path.join(dataset_root, row['project'])
            if lan == 'py':
                test_result = run_pytest(row)
            elif lan == 'go':
                test_result = run_gotest(row)
            elif lan == 'java':
                test_result = run_javatest(row)
            elif lan == 'cs':
                test_result = run_cstest(row)
            restore_file_lines(original_file_lines, file_path)
            print(f"task_id: {task_id} test_result: {test_result}")
            test_logs.append(test_result)
        os.chdir(cwd)
        all_test_logs[task_id] = test_logs
        
    return all_test_logs

def get_pass_k(all_test_log, lan):
    pass_result = {}
    for task_id, result in all_test_log.items():
        pass_result[task_id] = [parse_log(r, lan) for r in result]
    
    for i in range(1, 2):
        print(f"calculate pass@{i}")
        cur_pass_result = []
        for v in pass_result.values():
            cur_pass_result.append(any(v[:i]))
        passed_count = sum(cur_pass_result)
        print(f"pass@{i}: {round(passed_count/len(all_test_log), 4)}")
        

if __name__ == "__main__":
    test_data_df = pd.read_excel(df_path)
    # test_data_df = test_data_df[test_data_df['project']=='textual']
    with open(result_path, 'r') as f:
        response_dict = json.load(f)

    all_test_log = eval(test_data_df, response_dict, dataset_root, lan)
    with open(result_path+'_testresult.json', 'w') as f:
        json.dump(all_test_log, f)

    get_pass_k(all_test_log, lan)