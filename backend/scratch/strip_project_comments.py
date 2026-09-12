import ast
import tokenize
import io
import os

def get_docstring_lines(source):
    try:
        tree = ast.parse(source)
    except Exception:
        return set()

    docstring_lines = set()

    def visit(node):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            try:
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    if hasattr(node, 'body') and node.body:
                        first_stmt = node.body[0]
                        if isinstance(first_stmt, ast.Expr) and isinstance(first_stmt.value, ast.Constant) and isinstance(first_stmt.value.value, str):
                            start = getattr(first_stmt, 'lineno', None)
                            end = getattr(first_stmt, 'end_lineno', None)
                            if start is not None and end is not None:
                                for line in range(start, end + 1):
                                    docstring_lines.add(line)
            except Exception:
                pass
        
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return docstring_lines

def strip_comments_and_docstrings(source):
    doc_lines = get_docstring_lines(source)
    
    io_obj = io.StringIO(source)
    try:
        tokens = list(tokenize.generate_tokens(io_obj.readline))
    except Exception:
        return source
    
    out = []
    prev_end_row, prev_end_col = 1, 0
    
    for tok in tokens:
        start_row, start_col = tok.start
        end_row, end_col = tok.end
        
        if tok.type == tokenize.COMMENT:
            continue
            
        if start_row in doc_lines or end_row in doc_lines:
            continue
            
        if start_row > prev_end_row:
            out.append('\n' * (start_row - prev_end_row))
            prev_end_col = 0
            
        out.append(' ' * (start_col - prev_end_col))
        out.append(tok.string)
        
        prev_end_row, prev_end_col = end_row, end_col
        
    raw_code = "".join(out)
    
    # Post-process: collapse excessive consecutive blank lines to at most 1 blank line
    lines = raw_code.split('\n')
    cleaned_lines = []
    prev_was_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank:
            # Avoid empty lines at the very beginning of def/class bodies
            if cleaned_lines and cleaned_lines[-1].strip().endswith(':'):
                continue
            if not prev_was_blank:
                cleaned_lines.append("")
                prev_was_blank = True
        else:
            cleaned_lines.append(line.rstrip())
            prev_was_blank = False
            
    # Remove leading/trailing blank lines
    while cleaned_lines and not cleaned_lines[0].strip():
        cleaned_lines.pop(0)
    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()
        
    return "\n".join(cleaned_lines) + "\n"

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        cleaned = strip_comments_and_docstrings(content)
        
        # Verify the syntax of the cleaned code before writing it back
        try:
            ast.parse(cleaned)
        except Exception as e:
            print(f"Error parsing cleaned AST for {filepath}: {e}. Skipping to avoid syntax corruption.")
            return False
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        print(f"Successfully cleaned: {filepath}")
        return True
    except Exception as e:
        print(f"Failed to process {filepath}: {e}")
        return False

def main():
    backend_dir = r"c:\Users\Madhan\Enterprise_AI_Assisstant\backend"
    
    ignore_dirs = {"venv", ".venv", "scratch", "__pycache__", ".git", ".gemini", "build", "dist"}
    
    count = 0
    for root, dirs, files in os.walk(backend_dir):
        # Modify dirs in-place to prune ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if process_file(filepath):
                    count += 1
                    
    print(f"\nFinished. Processed {count} Python files.")

if __name__ == "__main__":
    main()
