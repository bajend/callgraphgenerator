#!/usr/bin/env python3
"""
Simple Python Call Graph Generator
Analyzes Python code in a Git repository to create JSON call graphs
"""

import ast
import os
import json
import subprocess
import tempfile
import shutil
import time
import stat
import errno
from typing import Dict, List, Set, Optional

class CallGraphAnalyzer(ast.NodeVisitor):
    """AST visitor to analyze Python code and build call graph"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.functions = {}
        self.current_function = None
        
    def visit_FunctionDef(self, node):
        """Handle function definitions"""
        func_name = node.name
        self.functions[func_name] = {
            'name': func_name,
            'file': os.path.basename(self.file_path),
            'line': node.lineno,
            'calls': []
        }
        self.current_function = func_name
        self.generic_visit(node)
        self.current_function = None
    
    def visit_Call(self, node):
        """Handle function calls"""
        if self.current_function:
            called_func = self._get_call_name(node)
            if called_func:
                self.functions[self.current_function]['calls'].append(called_func)
        self.generic_visit(node)
    
    def _get_call_name(self, node) -> Optional[str]:
        """Extract function name from call node"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

def remove_readonly(func, path, _):
    """Handle read-only file deletion errors"""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"Failed to delete {path}: {e}")

def clone_repo(repo_url: str) -> str:
    """Clone repository to temporary directory"""
    temp_dir = tempfile.mkdtemp()
    try:
        print(f"Cloning into: {temp_dir}")
        subprocess.run(['git', 'clone', repo_url, temp_dir], 
                      check=True, capture_output=True, text=True)
        time.sleep(1)  # Wait for Git to release file handles
        return temp_dir
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to clone repository: {e}")

def find_python_files(directory: str) -> List[str]:
    """Find all Python files in directory"""
    python_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

def analyze_file(file_path: str) -> Dict:
    """Analyze a single Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=file_path)
        analyzer = CallGraphAnalyzer(file_path)
        analyzer.visit(tree)
        return analyzer.functions
        
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return {}

def generate_call_graph(repo_url: str) -> Dict:
    """Generate call graph for repository"""
    print(f"Cloning repository: {repo_url}")
    project_path = clone_repo(repo_url)
    print(f"Temporary directory created: {project_path}")
    
    try:
        python_files = find_python_files(project_path)
        print(f"Found {len(python_files)} Python files")
        
        all_functions = {}
        
        for file_path in python_files:
            print(f"Analyzing: {os.path.basename(file_path)}")
            functions = analyze_file(file_path)
            all_functions.update(functions)
        
        # Build call relationships
        call_graph = {
            'repository': repo_url,
            'total_functions': len(all_functions),
            'functions': all_functions,
            'call_relationships': []
        }
        
        # Create call relationships
        for func_name, func_info in all_functions.items():
            for called_func in func_info['calls']:
                call_graph['call_relationships'].append({
                    'caller': func_name,
                    'callee': called_func,
                    'caller_file': func_info['file']
                })
        
        return call_graph
        
    finally:
        print(f"Attempting to clean up: {project_path}")
        if os.path.exists(project_path):
            time.sleep(1)  # Additional delay for safety
            shutil.rmtree(project_path, onerror=remove_readonly)
            print(f"Cleaned up: {project_path}")

def main():
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python call_graph_generator.py <repo_url>")
        sys.exit(1)
    
    repo_url = sys.argv[1]
    
    try:
        call_graph = generate_call_graph(repo_url)
        
        output_file = 'call_graph.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(call_graph, f, indent=2, ensure_ascii=False)
        
        print(f"\nCall graph generated!")
        print(f"Output: {output_file}")
        print(f"Functions: {call_graph['total_functions']}")
        print(f"Relationships: {len(call_graph['call_relationships'])}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()