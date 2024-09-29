from parser.base_parser import BaseParser, FunctionData
from tree_sitter import Language, Parser, Node
import tree_sitter_go as tsgo
import os
import tqdm

class GOParser(BaseParser):
    
    def __init__(self, repo_path, project_name):
        super().__init__(Language(tsgo.language()))
        self.project_name = project_name
        self.repo_path = repo_path
    
    def extract_import_info(self, node: Node):
        import_query = """
        (import_spec_list
            (import_spec
                path: (interpreted_string_literal)@import_path
            )
        )
        """
        query = self.LANGUAGE.query(import_query)
        matches = query.matches(node)
        import_infos = []
        if matches:
            for match in matches:
                import_path = match[1]["import_path"].text.decode('utf-8').replace('"', '')
                if import_path.startswith("github.com"):
                    import_path_split = import_path.split("/")
                    if len(import_path_split) >= 3 and import_path_split[2] == self.project_name:
                        if len(import_path_split) >=4:
                            import_path = self.repo_path +'/'+ '/'.join(import_path_split[3:])
                        else:
                            import_path = self.repo_path
                        import_infos.append(import_path)
        return import_infos

    def extract_callee_name(self, node: Node): # TODO
        invocation_query = """
        (call_expression
            function: (selector_expression
                field: (field_identifier)@callee_name
            )
        )
        (call_expression
            function: (identifier)@callee_name
        )
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
    
    def get_class_name(self, node: Node):
        if node.type != "method_declaration":
            return ""
        receiver = node.child_by_field_name("receiver")
        if receiver == None:
            return ""
        def search_node(root: Node, target_type: str):
            if node.child_count == 1:
                if node.type == target_type:
                    return node
            else:
                return None
                
            for child in node.children:
                if child.type == target_type:
                    return child
                else:
                    return search_node(child, target_type)
            return None
        type_child = search_node(receiver, "type_identifier")
        if type_child:
            return type_child.text.decode('utf-8')
        else:
            return ""
    def get_function_defintion(self, node: Node, file_path: str):
        func_query = """
        (
            (comment)* @comment
            .
            (function_declaration
                name: (identifier)@func_name
                parameters: (parameter_list)
                body: (block)@func_body 
            )@method
        )
        (
            (comment)* @comment
            .
            (method_declaration
                receiver: (parameter_list)
                name: (field_identifier)@func_name
                parameters: (parameter_list)
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
                class_name = self.get_class_name(func)
                func_defs.append(FunctionData(func_name, func_body, func, 
                                            comment_node, class_name, "", file_path))
        return func_defs
    def parse_project(self, dir: str):
        func_defs = {}
        func_imports = {}
        if not os.path.exists(dir):
            raise FileNotFoundError("Directory not found")
        print("parse project")
        for root, dirs, files in os.walk(dir):
            if ".ipynb" in root:
                continue
            for file in files:
                if file.endswith(".go"):
                    file_path = os.path.join(root, file)
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

        file_possible_context = {}
        package_context = {}
        for path in func_defs.keys():
            file_possible_context[path] = []
            func_def = func_defs[path]
            dir_name = os.path.dirname(path)
            if dir_name in package_context.keys():
                package_context[dir_name].extend(func_def)
            else:
                tmp = []
                tmp.extend(func_def)
                package_context[dir_name] = tmp
            import_info = func_imports[path]
            for info in import_info:
                if info in package_context.keys():
                    file_possible_context[path].extend(package_context[info])
            file_possible_context[path].extend(func_def)
            file_possible_context[path] = list(set(file_possible_context[path]))
        
        # build call relation
        for path in tqdm.tqdm(func_defs.keys()):
            func_def = func_defs[path]
            dir_name = os.path.dirname(path)
            # if "stream" in path:
            #         print("debug")
            for func in func_def:
                callee_names = self.extract_callee_name(func.func_node)
            
                for callee_name in callee_names:
                    for context_func in file_possible_context[path]:
                        if callee_name == context_func.name:
                            func.callee.add(context_func)
                            break
                    if dir_name in package_context.keys():
                        for package_func in package_context[dir_name]:
                            if callee_name == package_func.name:
                                func.callee.add(package_func)
                                break
                    
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
    parser = GOParser(repo_path, "conc")
    func_defs = parser.parse_project(repo_path)
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
    
if __name__ == "__main__":
    # repo_root = "/home/lihaiyang/codegen/repos/others/spring-ai"
    # for repo in os.listdir(repo_root):
    #     if repo.startswith('spring-ai'):
    #         repo_path = os.path.join(repo_root, repo)
    #         test_repo(repo_path)
    repo_path = "/home/lihaiyang/codegen/repos/go_data/conc"
    test_repo(repo_path)