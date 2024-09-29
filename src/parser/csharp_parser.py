from parser.base_parser import BaseParser, FunctionData
from tree_sitter import Language, Parser, Node
import tree_sitter_c_sharp as tscs
import os
import tqdm

class CSParser(BaseParser):
    
    def __init__(self):
        super().__init__(Language(tscs.language()))
        self.class_heri = {}
    def parse_namespace(self, node: Node):
        namespace_query = """
        (file_scoped_namespace_declaration
            name: (qualified_name)@namespace
        )
        """
        query = self.LANGUAGE.query(namespace_query)
        matches = query.matches(node)
        if matches:
            namespace = matches[0][1]["namespace"].text.decode('utf-8')
        else:
            namespace = ""
        return namespace
#     def extract_class_heri(self, node: Node):
#         query_str = """
# (class_declaration 
#     name: (identifier)@class_name 
#     (base_list)@base_class_name_list
#     )
# """
#         query = self.LANGUAGE.query(query_str)
#         matches = query.matches(node)
#         for m in matches:
            
    def get_class_name(self, node: Node):
        class_node = node.parent.parent
        if class_node:
            class_name = class_node.child_by_field_name("name")
            if class_name:
                return class_name.text.decode('utf-8')
        return ""
    
    def extract_import_info(self, node: Node):
        import_query = """
        (using_directive
            (qualified_name) @import_scope
        )
        """
        query = self.LANGUAGE.query(import_query)
        matches = query.matches(node)
        import_info = []
        if matches:
            for match in matches:
                import_scope = match[1]["import_scope"]
                import_info.append(import_scope.text.decode('utf-8'))
        return import_info

    def extract_callee_name(self, node: Node): # TODO
        invocation_query = """
        (invocation_expression
            function: (member_access_expression
                expression: (identifier)
                name: (identifier)@callee_name
            )
                
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

    def get_function_defintion(self, node: Node, file_path: str):
        func_query = """
        (
            (comment)* @comment
            .
            (method_declaration
                name: (identifier)@func_name
                body: (arrow_expression_clause)@func_body
            )@method
        )
        (
            (comment)* @comment
            .
            (method_declaration
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
                class_name = self.get_class_name(func)
                namespace = self.parse_namespace(node)
                
                func_defs.append(FunctionData(func_name, func_body, func, 
                                            comment_node, class_name, namespace, file_path))
        return func_defs
    def parse_project(self, dir: str):
        func_defs = {}
        func_imports = {}
        if not os.path.exists(dir):
            raise FileNotFoundError("Directory not found")
        print("parse project")
        for root, dirs, files in os.walk(dir):
            if '.ipynb' in root:
                continue
            for file in files:
                if file.endswith(".cs"):
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
        self.build_class_method_call_relation(all_funcs)
        return all_funcs
        
    
    def build_call_relation(self, func_defs: dict, func_imports: dict):
        """
        iter the func defs, add all the import context, and the context in the same file as the possible callees
        possible context:
        1. funcs in same package 
        2. funcs in import files
        """
        # build file possible context, add all the funcs defined in the import files and the same file
        print("Grouping funcs according to namespace")
        namespace_funcs = {}  # group the funcs according to namespace
        import_info_to_path = {}
        for path in func_defs.keys():
            func_def = func_defs[path]
            namespace = func_def[0].package_name

            if namespace not in namespace_funcs.keys():
                namespace_funcs[namespace] = []
            namespace_funcs[namespace].extend(func_def)

            import_info_to_path[namespace] = path
        print("get file possible context")
        file_possible_context = {}
        for path in func_defs.keys():
            file_possible_context[path] = []
            func_def = func_defs[path]
            import_info = func_imports[path]
            for info in import_info:
                if info in import_info_to_path.keys():
                    file_possible_context[path].extend(func_defs[import_info_to_path[info]])
            file_possible_context[path].extend(func_def)
            file_possible_context[path].extend(namespace_funcs[func_def[0].package_name])
            file_possible_context[path] = list(set(file_possible_context[path]))
        
        # build call relation
        for path in tqdm.tqdm(func_defs.keys()):
            func_def = func_defs[path]
            for func in func_def:
                callee_names = self.extract_callee_name(func.func_node)
                func.callee_names = callee_names
                for callee_name in callee_names:
                    for context_func in file_possible_context[path]:
                        if callee_name == context_func.name:
                            func.callee.add(context_func)
        return func_defs

    def build_class_method_call_relation(self, func_defs: list):
        class_create_query = """
            (object_creation_expression
                    type: (identifier)@class_name
            )
            """
        query = self.LANGUAGE.query(class_create_query)

        class_context = {}
        for f in func_defs:
            if f.class_name  == '':
                continue
            if f.class_name not in class_context.keys():
                class_context[f.class_name] = [f]
            else:
                class_context[f.class_name].append(f)

        for f in func_defs:
            matches = query.matches(f.func_node)
            used_classes = [m[1]['class_name'].text.decode('utf-8') for m in matches]
            used_class_context = []
            for c in used_classes:
                if c in class_context.keys():
                    used_class_context.extend(class_context[c])
            
            for callee_name in f.callee_names:
                for context_func in used_class_context:
                    if callee_name == context_func.name:
                        f.callee.add(context_func)
            

def get_func_and_tests(func_defs):
    func_defs = [f for f in func_defs if len(f.callee) != 0]
    test_funcs = [f for f in func_defs if f.is_test_func]

    for t in test_funcs:
        for callee in t.callee:
            if callee.is_test_func and 'test' not in callee.name.lower():## test utils
                for c in callee.callee:
                    c.test_funcs.add(t)
            else:
                callee.test_funcs.add(t)
    self_def_func_with_test = [i for i in func_defs if len(i.test_funcs) != 0]
    self_def_func_with_test = [i for i in self_def_func_with_test if i.comment_node]
    return self_def_func_with_test

def test_repo(repo_path):
    parser = CSParser()
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
    repo_path = "/home/lihaiyang/codegen/repos/cs_data/R3"
    test_repo(repo_path)