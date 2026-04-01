import os

def read_repo(repo_path):

    code_files = {}

    for root, dirs, files in os.walk(repo_path):

        for file in files:

            if file.endswith((".py",".js",".ts",".java",".go",".md",".json",".yaml",".yml")):

                path = os.path.join(root,file)

                try:
                    with open(path,"r",encoding="utf-8") as f:
                        code_files[path] = f.read()
                except:
                    pass

    return code_files