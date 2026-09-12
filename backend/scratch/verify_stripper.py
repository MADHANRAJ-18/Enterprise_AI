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

test_code = """
\"\"\"
Module docstring.
\"\"\"
import os # inline comment

# A standalone comment
def func():
    \"\"\"Func docstring.\"\"\"
    x = 10  # assign x
    return x
"""

cleaned = strip_comments_and_docstrings(test_code)
print("=== CLEANED CODE ===")
print(cleaned)
print("====================")
