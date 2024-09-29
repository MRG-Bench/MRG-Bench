from tree_sitter import Language, Parser
from tree_sitter import Node
import os

class BaseParser:
    def __init__(self, specific_language):
        self.LANGUAGE = specific_language
        self.parser = Parser(self.LANGUAGE)
        self.function_data = []
    

    def parse(self, file_path: str):
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                code = file.read()
                tree = self.parser.parse(bytes(code, "utf8"))
                return tree.root_node
        else:
            raise FileNotFoundError("File not found")

class FunctionData:
    def __init__(self, func_name: Node, func_body: Node, func: Node,
                    comment_node: Node, 
                    class_name: str, package_name: str, file_path: str):
        self.name_node = func_name
        self.body_node = func_body
        self.func_node = func
        self.comment_node = comment_node
        self.file_path = file_path
        self.class_name = class_name
        self.package_name = package_name

        self.name = self.get_name()
        self.body = self.get_body()
        self.is_test_func = self.is_test()
        self.callee = set([])
        self.test_funcs = set([])
    
    def is_test(self):
        if self.name and "test" in self.name.lower():
            return True
        if self.class_name and "test" in self.class_name.lower():
            return True
        return False
    def __eq__(self, value: object) -> bool:
        if isinstance(value, FunctionData):
            return self.file_path == value.file_path and self.get_name() == value.get_name()
        return False
    
    def __hash__(self) -> int:
        return hash(self.file_path + self.get_name())
    def get_name(self):
        return self.name_node.text.decode('utf-8')
    
    def get_body(self):
        return self.body_node.text.decode('utf-8')

    def get_func(self):
        return self.func_node.text.decode('utf-8')
    
    def get_class_name(self):
        return self.class_name.text.decode('utf-8')
    
    def get_comment(self):
        if isinstance(self.comment_node, list):
            return '\n'.join([i.text.decode('utf-8') for i in self.comment_node])
        else:
            return self.comment_node.text.decode('utf-8')
