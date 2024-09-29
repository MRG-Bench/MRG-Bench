# MRGBench
This is the Official Repository for the repository level code generation benchmark: MRGBench

## Structure
```
.
├── data
│   ├── all_context_project_dict.json  # context information in project
│   ├── context_info.json # context information in file, 
│   ├── go_data_final.xlsx # data for Go
│   ├── java_data_final.xlsx # data for Java
│   └── py_data_final.xlsx # data for Python
├── repo # repository data
│   ├── go_data.7z
│   ├── java_data.7z
│   └── py_data.7z
├── result 
│   ├── cache_result # result of each model with different context in our experiment
│   │   ├── callee
│   │   ├── infile
│   │   ├── llms
│   │   ├── long_context
│   │   └── rag
│   ├── llms 
│   └── rag
└── src
    ├── eval  # code for evaluation and test 
    │   ├── AIClient.py
    │   ├── config.json
    │   ├── eval_llm.py
    │   ├── eval_rag.py
    │   ├── naive_rag.py
    │   ├── parse_run_log.py
    │   ├── repocoder.py
    │   └── run_test.py
    ├── parser  # code for parse repository into dataset
    │   ├── base_parser.py
    │   ├── csharp_parser.py
    │   ├── go_parser.py
    │   ├── java_parser.py
    │   └── py_parser.py
```

## Usage

### `eval_llm.py`

`eval_llm.py` is used to evaluate the performance of language models (LLMs).

#### Entry Function

```python
def eval_llm(llm: BaseAIClient, context_type: str, language_list: list):
    """
    Evaluate the performance of LLMs under different context types and languages.

    Parameters:
    - llm: BaseAIClient instance
    - context_type: Context type, can be "no_context", "callee_func", "callee_sig", "in_file", "project"
    - language_list: List of languages, e.g., ['py', 'java', 'go']
    """
```

#### Usage
```bash
python eval_llm.py -context_type <context_type> -lang_list <language_list> -model_name <model_name>
```
Here is an example command to run the evaluation script:
```bash
python eval_llm.py -context_type callee_func -lang_list py,java -model_name gpt-3.5-turbo
```
### `eval_rag.py`
`eval_rag.py` is used to evaluate the performance of RAG methods.
#### Entry Function
```python
def eval_rag(rag_type: str, llm: BaseAIClient, language_list=['py', 'java', 'go']):
    """
    Evaluate the performance of RAG models under different retrieval types and languages.

    Parameters:
    - rag_type: RAG type, can be 'repo_coder', 'embedding', 'bm25', 'mix'
    - llm: BaseAIClient instance
    - language_list: List of languages, e.g., ['py', 'java', 'go']
    """
```
#### Usage
```bash
python eval_rag.py -rag_type <rag_type> -lang_list <language_list> -model_name <model_name>
```
Here is an example command to run the evaluation script:
```bash
python eval_rag.py -rag_type embedding -lang_list py,java -model_name gpt-3.5-turbo
```
## Configuration
Before running the above commands, make sure to properly configure the config.json file located in the eval directory. This file should include the URL and key for the AI client:
```json
{
    "repo_coder": {
        "chunk_size": 20,
        "chunk_overlap" : 5,
        "k": 5
    },
    "naive_rag": {
        "chunk_size": 500,
        "chunk_overlap" : 50,
        "k": 5
    },
    "ai_client": {
        "url": "<your_ai_client_url>",
        "key": "<your_ai_client_key>"
    }
}
```

## Usage for Building new Algorithms
### Usage for RAG based and Agent based Algorithms
1. unzip the repository data
```
cd repo
7z x py_data.7z
7z x java_data.7z
7z x go_data.7z
```
2. build you own knowledge base by different methods for each repository
3. run your own algorithm to generate the code, you can refer to the `eval_rag.py` for the usage.
4. evaluate your result using docker container and test cases.
