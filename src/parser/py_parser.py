from parser.base_parser import BaseParser, FunctionData
from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspy
import os
import tqdm

class PyParser(BaseParser):
    """
    parse one file into: 1. {file_path: list of [FunctionData | className:[FunctionData]]}
    parse every file's import path
    for each file: parse import info, add all import info into the cur_file_context
    for each file: 
    """
    def __init__(self, project_path, exclude_dirs=[], package_base_path = ""):
        super().__init__(Language(tspy.language()))
        self.repo_path = project_path
        self.package_base_path = package_base_path
        self.all_file_paths = self.get_all_file_path(project_path, exclude_dirs)
        self.file_to_import_scope = self.get_file_to_import_scope()
        self.funcs = self.parse_project()
    
    def get_all_file_path(self, project_path, exclude_dirs=[]):
        all_file_paths = []
        for root, dirs, files in os.walk(project_path):
            for file in files:
                if any([exclude_dir in root for exclude_dir in exclude_dirs]):
                    continue
                if file.endswith(".py") and "ipynb" not in root:
                    file_path = os.path.join(root, file)
                    all_file_paths.append(file_path)
        return all_file_paths
    def get_file_to_import_scope(self):
        file_to_import_scope = {}
        for file_path in self.all_file_paths:
            relative_path = os.path.relpath(file_path, self.repo_path)
            if relative_path.startswith(self.package_base_path):
                relative_path = os.path.relpath(relative_path, self.package_base_path)
            relative_path = relative_path.replace('.py', '')
            file_to_import_scope[relative_path.replace('/', '.')] = file_path
        return file_to_import_scope
    
    def get_class_name(self, node: Node):
        class_body = node.parent
        if class_body.type == "block":
            class_node = class_body.parent
            class_name = class_node.child_by_field_name("name")
            if class_name:
                return class_name.text.decode('utf-8')
        elif class_body.type == "decorated_definition":
            return self.get_class_name(class_body)
        return ""
    
    def extract_import_info(self, node: Node):
        import_query = """
        (import_statement 
            name: (dotted_name)@import_name
        )
        (import_from_statement
            module_name: (dotted_name)@package_name
            name: (dotted_name)+ @class_or_method_name
        )
        (import_from_statement
            module_name: (dotted_name)@package_name
            name: (aliased_import)+ @class_or_method_name
        )
        """
        query = self.LANGUAGE.query(import_query)
        matches = query.matches(node)
        import_infos = []
        if matches:
            for match_item in matches:
                match_item = match_item[1]
                if 'import_name' in match_item:
                    import_info = match_item["import_name"].text.decode('utf-8')
                    import_path = import_info[:import_info.rfind('.')]
                    import_name = import_info[import_info.rfind('.')+1:]
                    import_infos.append({"import_path": import_path, "import_name": import_name})
                else:
                    import_path = match_item["package_name"].text.decode('utf-8')
                    for item in match_item["class_or_method_name"]:
                        import_infos.append({"import_path": import_path, "import_name": item.text.decode('utf-8')})
        return import_infos

    def extract_callee_name(self, node: Node): # TODO
        invocation_query = """
        (call
            function: (attribute
                        object: (identifier)
                        attribute: (identifier)@callee_name
                        )
        )
        (call function: (identifier)@callee_name)   
        """
        query = self.LANGUAGE.query(invocation_query)
        matches = query.matches(node)
        callees = []
        if matches:
            for match in matches:
                callee_name = match[1]["callee_name"]
                if callee_name:
                    callees.append(callee_name.text.decode('utf-8'))
        return callees

    def get_doc_node(self, func_body: Node):
        if func_body.child_count == 0:
            return None
        first_child = func_body.children[0]
        if first_child.type == "expression_statement":
            if first_child.child_count == 1 and first_child.children[0].type == "string":
                return first_child.children[0]
        return None

    def get_function_defintion(self, node: Node, file_path: str):
        func_query = """
        (
            (comment)* @comment
            .
            (function_definition
                name: (identifier)@func_name
                body: (block)@func_body
            )@method
        )
        """

        query = self.LANGUAGE.query(func_query)
        matches = query.matches(node)
        func_defs = []
        if matches:
            for match in matches:
                func_name = match[1]["func_name"]
                func_body = match[1]["func_body"]
                func = match[1]["method"]
                comment_node = match[1].get("comment", None)
                if not comment_node:
                    comment_node = self.get_doc_node(func_body)
                class_name = self.get_class_name(func)
                if func_name.text.decode('utf-8') == "start" and class_name=="AI":
                    print("debug")
                func_defs.append(FunctionData(func_name, func_body, func, 
                                            comment_node, class_name, "", file_path))
        return func_defs
    def parse_project(self):
        func_defs = {}
        func_imports = {}
        for file_path in self.all_file_paths:
            root_node = self.parse(file_path)
            defs = self.get_function_defintion(root_node, file_path)
            if len(defs) == 0:
                continue
            func_defs[file_path] = defs
            func_imports[file_path] = self.extract_import_info(root_node)

        print("build call relation")
        self.build_call_relation(func_defs, func_imports)
        all_funcs = []
        for key in func_defs.keys():
            all_funcs.extend(func_defs[key])
        return all_funcs
        
    
    def build_call_relation(self, func_defs: dict, func_imports: dict):
        """
        iter the func defs, add all the import context, and the context in the same file as the possible callees
        possible context:
        1. funcs in same package 
        2. funcs in import files
        """
        # build file possible context, add all the funcs defined in the import files and the same file
        print("get file possible context")
        file_possible_context = {}
        for path in func_defs.keys():
            file_possible_context[path] = []
            func_def = func_defs[path]
            import_infos = func_imports[path]
            for info in import_infos:
                if info['import_path'] in self.file_to_import_scope.keys():
                    imported_file_path = self.file_to_import_scope[info['import_path']]
                    if imported_file_path not in func_defs.keys():
                        continue
                    for f in func_defs[imported_file_path]:
                        if f.name == info['import_name']:
                            file_possible_context[path].append(f)
                        elif f.class_name == info['import_name']:
                            file_possible_context[path].append(f)
            file_possible_context[path].extend(func_def)
            file_possible_context[path] = list(set(file_possible_context[path]))
        
        # build call relation
        for path in tqdm.tqdm(func_defs.keys()):
            func_def = func_defs[path]
            for func in func_def:
                callee_names = self.extract_callee_name(func.func_node)
                for callee_name in callee_names:
                    for context_func in file_possible_context[path]:
                        if callee_name == context_func.name:
                            func.callee.add(context_func)
        return func_defs

def get_func_and_tests(func_defs):
    func_defs = [f for f in func_defs if len(f.callee) != 0]
    test_funcs = [f for f in func_defs if f.is_test_func]

    for t in test_funcs:
        for callee in t.callee:
            callee.test_funcs.add(t)
    self_def_func_with_test = [i for i in func_defs if len(i.test_funcs) != 0]
    self_def_func_with_test = [i for i in self_def_func_with_test if i.comment_node]
    return self_def_func_with_test

def test_repo(repo_path):
    parser = PyParser(repo_path, exclude_dirs=[], package_base_path="src/")
    func_defs = parser.funcs
    func_with_tests = get_func_and_tests(func_defs)
    print("project:", os.path.basename(repo_path), len(func_with_tests))
    for f in func_with_tests:
        print("=="*10)
        print(f.name)
        if isinstance(f.comment_node, list):
            for c in f.comment_node:
                print(c.text.decode('utf-8'))
        else:
            print(f.comment_node.text.decode('utf-8'))
        print("--"*10)
        print(' '.join([i.name for i in f.test_funcs]))
    


def test_pyparser():
    code = """"
class RunResult:
    def __init__(self, prompt_id: str):
        \"\"\"
        aaaaaaa
        \"\"\"
        self.outputs: Dict[str,Dict] = {}
        self.runs: Dict[str,bool] = {}
        self.prompt_id: str = prompt_id
    """
    parser = Parser(Language(tspy.language()))
    tree = parser.parse(bytes(code, "utf-8"))
    print(str(tree.root_node))


if __name__ == "__main__":
    # repo_root = "/home/lihaiyang/codegen/repos/others/spring-ai"
    # for repo in os.listdir(repo_root):
    #     if repo.startswith('spring-ai'):
    #         repo_path = os.path.join(repo_root, repo)
    #         test_repo(repo_path)
    repo_path = "/home/lihaiyang/codegen/repos/others/lonboard"
    
    test_repo(repo_path)
    # test_pyparser()