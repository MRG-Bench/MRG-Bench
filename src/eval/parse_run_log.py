import re
def parse_py_log(log):
    if "passed" not in log.lower():
        return False
    log_lines = log.split("\n")
    result_lines = [i for i in log_lines if i.startswith("====")]
    if len(result_lines) == 0: # no result
        return False
    
    passed = True
    for l in result_lines:
        # print(l)
        if "failed" in l.lower():
            passed = False
        if "error" in l.lower():
            passed = False
        if "no tests ran" in l.lower():
            passed = False
    # print(passed)
    return passed

def parse_go_log(log:str):
    if "fail" in log.lower():
        return False
    if "error" in log.lower():
        return False
    if "pass\nok" in log.lower():
        return True
    return False

import re
def parse_java_log_line(log: str):
    # 定义正则表达式模式来匹配 "Tests run"、"Failures"、"Errors" 和 "Skipped"
    pattern = r'Tests run:\s*(\d+)|Failures:\s*(\d+)|Errors:\s*(\d+)|Skipped:\s*(\d+)'
    
    # 使用 findall 函数查找所有匹配项
    matches = re.findall(pattern, log)
    # 初始化结果字典
    results = {
        'Tests run': 0,
        'Failures': 0,
        'Errors': 0,
        'Skipped': 0
    }
    
    # 遍历所有匹配项并更新结果字典
    for match in matches:
        if match[0]:
            results['Tests run'] = int(match[0])
        if match[1]:
            results['Failures'] = int(match[1])
        if match[2]:
            results['Errors'] = int(match[2])
        if match[3]:
            results['Skipped'] = int(match[3])
    
    return results

def parse_cs_log(log: str):
    log_lines = log.split("\n")
    passed = False
    for l in log_lines:
        if "Passed" in l:
            passed = True
    return passed

def parse_java_log(log:str):
    if "BUILD FAILURE" in log:
        return False
    log_lines = log.split("\n")
    passed = True
    has_test = False
    for l in log_lines:
        if "Tests run:" in l:
            result = parse_java_log_line(l)
            has_test = True
            if result['Failures'] > 0 \
                    or result['Errors'] > 0 \
                    or result['Tests run'] == 0\
                    or result['Tests run']==result['Skipped']:
                passed = False
    return passed and has_test


def parse_log(log: str, lang: str):
    if lang == "py":
        return parse_py_log(log)
    elif lang == "go":
        return parse_go_log(log)
    elif lang == "java":
        return parse_java_log(log)
    elif lang == "cs":
        return parse_cs_log(log)
    else:
        return False

def extract_code_blocks(markdown_text):
    # 正则表达式匹配Markdown中的代码块
    code_block_pattern = re.compile(r'```(?:\w+)?\n(.*?)```', re.DOTALL)
    # 查找所有匹配的代码块
    code_blocks = code_block_pattern.findall(markdown_text)
    return code_blocks

if __name__ == "__main__":
    # 示例Markdown文本
    markdown_text = """
    Here is some text.

    ```python
    import a.b.c
    def f():
    pass
    print("Hello, World!")
    ```
    """
    code_blocks = extract_code_blocks(markdown_text)
    # 打印所有代码块
    for code_block in code_blocks:
        print(code_block)
    # 输出代码块数量
    print(f"Found {len(code_blocks)} code blocks.")
