import zipfile
import os
import shutil

def extract_repo(zip_path, extract_to="repo_temp"):

    # Clean up existing temp directory
    if os.path.exists(extract_to):
        shutil.rmtree(extract_to)
    
    os.makedirs(extract_to)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Extract files one by one with error handling
        for member in zip_ref.namelist():
            try:
                # Shorten the path by using a flatter structure
                filename = os.path.basename(member)
                
                # Skip if it's a directory or empty filename
                if not filename or member.endswith('/'):
                    continue
                
                # Create a shorter path
                target_path = os.path.join(extract_to, filename)
                
                # Handle duplicate filenames
                counter = 1
                base_name, ext = os.path.splitext(filename)
                while os.path.exists(target_path):
                    target_path = os.path.join(extract_to, f"{base_name}_{counter}{ext}")
                    counter += 1
                
                # Extract the file
                with zip_ref.open(member) as source, open(target_path, 'wb') as target:
                    target.write(source.read())
            except Exception as e:
                print(f"Warning: Could not extract {member}: {e}")
                continue

    return extract_to