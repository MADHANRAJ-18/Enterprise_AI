import os
import zipfile

def create_clean_project_zip(root_dir, output_zip_path):
    # Directories to ignore
    ignore_dir_names = {
        'node_modules',
        '__pycache__',
        '.git',
        '.vscode',
        'dist',
        'build',
        'scratch',
        '.venv',
        'venv',
        'env',
        'faiss_index',
        '.gemini',
        '.pytest_cache',
        'tmp',
        '.tmp'
    }
    
    # Extensions to ignore
    ignore_extensions = {
        '.pyc',
        '.pyo',
        '.pyd',
        '.index',
        '.pkl',
        '.log',
        '.tmp',
        '.DS_Store'
    }

    # Specific files to ignore
    ignore_file_names = {
        'Thumbs.db',
        'Enterprise_AI_Assistant.zip',
        'Enterprise_AI_Assistant_Clean.zip'
    }

    added_files = []
    
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(root_dir):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in ignore_dir_names]
            
            for file in files:
                if file in ignore_file_names:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in ignore_extensions:
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, root_dir)
                
                # Check if path contains any ignored directory
                parts = rel_path.replace('\\', '/').split('/')
                if any(p in ignore_dir_names for p in parts[:-1]):
                    continue
                
                # Avoid zipping the target zip itself
                if os.path.abspath(full_path) == os.path.abspath(output_zip_path):
                    continue
                    
                zipf.write(full_path, arcname=os.path.join('Enterprise_AI_Assistant', rel_path))
                added_files.append(rel_path)
                
    return added_files

if __name__ == '__main__':
    project_root = r'c:\Users\Madhan\Enterprise_AI_Assisstant'
    zip_output = os.path.join(project_root, 'Enterprise_AI_Assistant.zip')
    
    files = create_clean_project_zip(project_root, zip_output)
    size_mb = os.path.getsize(zip_output) / (1024 * 1024)
    print(f'Successfully created {zip_output}')
    print(f'Total files added: {len(files)}')
    print(f'Archive size: {size_mb:.2f} MB')
