import os
import json
import datetime
import traceback
import inspect
import sys
import ast
from typing import Optional, Any, Dict, Callable

def safe_str(obj: Any) -> str:
    """
    Safely convert any object to a string representation.
    """
    try:
        return str(obj)
    except Exception:
        return f"<Unprintable {type(obj).__name__} object>"

def get_function_source(func: Callable) -> tuple[list[str], int]:
    """
    Get function source code using AST and inspect.
    Returns tuple of (source_lines, start_line).
    """
    # First try to get source directly from file
    if hasattr(func, '__code__') and hasattr(func.__code__, 'co_filename'):
        file_path = func.__code__.co_filename
        with open(file_path, 'r') as f:
            source = f.read()
            
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func.__name__:
                start_line = node.lineno
                end_line = node.end_lineno
                
                with open(file_path, 'r') as f:
                    all_lines = f.readlines()
                    source_lines = all_lines[start_line-1:end_line]
                    return source_lines, start_line
                    
    # Fallback to inspect
    return inspect.getsourcelines(func)

def handle_exception(
    error: Exception,
    func: Optional[Callable] = None,
    args: Optional[tuple] = None,
    kwargs: Optional[dict] = None,
    config: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Captures execution context and saves exception details to a file.
    
    Args:
        error: The caught exception
        func: Optional function object that raised the exception
        args: Optional positional arguments passed to the function
        kwargs: Optional keyword arguments passed to the function
        
    Returns:
        dict: The captured context
    """
    # Reset/initialize important variables
    caller_frame = None
    exc_type = None 
    exc_value = None
    exc_traceback = None
    trace = None
    error_frame = None
    context = {}

    # Get the frame of the caller
    caller_frame = inspect.currentframe().f_back

    # Get exception info early
    exc_type, exc_value, exc_traceback = sys.exc_info()
    trace = traceback.extract_tb(exc_traceback)
    
    # # Capture enhanced context
    # context = {
    #     'timestamp': datetime.datetime.now().isoformat(),
    #     'python_version': sys.version,
    #     'platform': sys.platform,
               
    #     # # Local and global variables
    #     # 'locals': {
    #     #     k: {
    #     #         'value': safe_str(v),
    #     #         'type': str(type(v).__name__),
    #     #         'id': id(v)
    #     #     } for k, v in caller_frame.f_locals.items()
    #     # },
    #     # 'globals': {
    #     #     k: {
    #     #         'value': safe_str(v),
    #     #         'type': str(type(v).__name__)
    #     #     } for k, v in caller_frame.f_globals.items() 
    #     #     if not k.startswith('_') and not inspect.ismodule(v)
    #     # },
        
    #     # # Current working directory
    #     # 'cwd': str(Path.cwd()),
        
    #     # # Environment variables (filtered)
    #     # 'env_vars': {
    #     #     k: v for k, v in os.environ.items() 
    #     #     if not any(secret in k.lower() for secret in ['key', 'password', 'token', 'secret'])
    #     # }
    # }

    # Find the frame where the actual error occurred
    error_frame = None
    for frame in reversed(trace):
        if func and frame.filename == inspect.getfile(func):
            error_frame = frame
            break
    
    # If we couldn't find the frame in the function, use the last frame
    if not error_frame:
        error_frame = trace[-1]

    context = {}
    
    # Enhanced error context
    context['error'] = {
        'type': exc_type.__name__,
        'message': str(exc_value),
        'traceback': traceback.format_exc(),
        'line_number': error_frame.lineno if error_frame else None,
        'file': error_frame.filename if error_frame else None,
        'function_name': error_frame.name if error_frame else None,
        'error_line': error_frame.line if error_frame else None,
        'exception_attrs': {
            attr: safe_str(getattr(error, attr))
            for attr in dir(error)
            if not attr.startswith('_') and not callable(getattr(error, attr))
        }
    }

    # Add full traceback information for debugging
    context['error']['traceback_frames'] = [{
        'filename': frame.filename,
        'line_number': frame.lineno,
        'function': frame.name,
        'code': frame.line
    } for frame in trace]

    # Enhance function_info with both sets of argument data
    if func:
        try:
            # Get source code using AST
            try:
                source_lines, start_line = get_function_source(func)
                source_code = ''.join(source_lines)
                
                # Get the signature
                sig = inspect.signature(func)
                
                # Collect argument information
                arguments_info = {
                    k: {
                        'value': str(v),
                        'type': str(type(v).__name__)
                    } 
                    for k, v in inspect.getcallargs(func, *(args or []), **(kwargs or {})).items()
                }

                context['function_info'] = {
                    'name': func.__name__,
                    'qualname': func.__qualname__,
                    'module': func.__module__,
                    'filename': inspect.getfile(func),
                    'line_number': start_line,
                    'source_code': source_code.strip(),
                    'signature': str(sig),
                    'source_lines': {
                        i + start_line: line.rstrip()
                        for i, line in enumerate(source_lines)
                    }
                }
                
                if config.get('DEBUG'):
                    print("\nFunction Source Information:")
                    print(f"♣ Function: {func.__name__}")
                    print(f"♣ Starting at line: {start_line}")
                    print(f"♣ Source verification: {'PASSED' if func.__name__ in source_code else 'FAILED'}")
                    print("♣ Source code:")
                    for line_no, line in context['function_info']['source_lines'].items():
                        print(f"  {line_no}: {line}")

            except Exception as source_error:
                print(f"♣ Warning: Failed to capture source code: {str(source_error)}")
                # Fallback to basic function info
                context['function_info'] = {
                    'name': func.__name__,
                    'qualname': func.__qualname__,
                    'module': func.__module__,
                    'filename': inspect.getfile(func),
                    'source_error': str(source_error)
                }

            context['function_arguments'] = arguments_info

        except Exception as e:
            context['function_info'] = {
                'note': f'Failed to capture function details: {str(e)}',
                'error_traceback': traceback.format_exc()
            }
    
    # Print detailed error information
    print(f"\n{'='*60}")
    print(f"♣ Error caught: {context['error']['type']} - {context['error']['message']}")
    print(f"♣ In file: {context['error']['file']}, line {context['error']['line_number']}")
    print(f"{'='*60}\n")
    
    # Save exception details with improved error handling
    try:
        if config.get('SAVE_EXCEPTIONS'):
            # Create exceptions directory if it doesn't exist
            exceptions_dir_path = config['EXCEPTION_FOLDER']
            os.makedirs(exceptions_dir_path, exist_ok=True)

            # Create a timestamp-based filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            func_name = func.__name__ if func else "unknown"
            file_path = os.path.join(exceptions_dir_path, f"{timestamp}_{func_name}.json")
            
            # Write exception details to file
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(context, f, indent=2, ensure_ascii=False)
                if config.get('DEBUG'):
                    print(f"♣ Exception details saved to: {file_path}")
                    print(f"♣ To investigate, check the saved context at: {file_path}")
            except Exception as write_error:
                print(f"♣ Failed to write exception details to {file_path}: {str(write_error)}")
                print(f"♣ Write error traceback: {traceback.format_exc()}")
    except Exception as save_error:
        print(f"♣ Failed to save exception details: {str(save_error)}")
        print(f"♣ Save error traceback: {traceback.format_exc()}")
    
    # Add after context creation
    if config.get('DEBUG'):
        print("\nDetailed Error Information:")
        print(f"♣ Error occurred in function: {context['error']['function_name']}")
        print(f"♣ Error line: {context['error']['error_line']}")
        print("\nTraceback Frames:")
        for frame in context['error']['traceback_frames']:
            print(f"  • {frame['filename']}:{frame['line_number']} - {frame['function']}")
            print(f"    {frame['code']}")
    
    return context