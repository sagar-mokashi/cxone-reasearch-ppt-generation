import ast

def analyze_python_file(code_files):
    """
    Analyze multiple Python files from repository.
    code_files: dict with file paths as keys and code content as values
    """
    all_functions = []
    all_classes = []
    file_structure = {}

    for file_path, code in code_files.items():
        if not file_path.endswith('.py'):
            continue
            
        try:
            tree = ast.parse(code)
            functions = []
            classes = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                    all_functions.append(node.name)

                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                    all_classes.append(node.name)
            
            file_structure[file_path] = {
                "functions": functions,
                "classes": classes
            }
        except:
            pass

    summary = f"""Total Files: {len(code_files)}
Python Files: {len(file_structure)}
Total Functions: {len(all_functions)}
Total Classes: {len(all_classes)}

File Structure:
"""
    
    for path, data in file_structure.items():
        summary += f"\n{path}:\n"
        if data['classes']:
            summary += f"  Classes: {', '.join(data['classes'])}\n"
        if data['functions']:
            summary += f"  Functions: {', '.join(data['functions'])}\n"
    
    return summary