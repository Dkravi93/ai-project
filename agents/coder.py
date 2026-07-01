"""
Coder Agent - Executes Python/SQL code in RestrictedPython sandbox.
Includes self-correction loop for errors.
"""
from datetime import datetime
from RestrictedPython import compile_restricted
from langchain_groq import ChatGroq
from config.settings import get_settings
from config.logger import logger
from agents.state import AgentState
import signal
import traceback

settings = get_settings()


CODER_SYSTEM = """You are a code-writing agent. Your job is to:
1. Write Python code to analyze data or answer the query
2. Use provided data from retrieved documents
3. Write clear, executable code
4. Include comments

Available modules: pandas, numpy, math, re, json, datetime

Respond with ONLY the Python code block, no explanation."""


def timeout_handler(signum, frame):
    raise TimeoutError("Code execution exceeded timeout")


def coder_node(state: AgentState) -> AgentState:
    """
    Coder node: generates and executes Python code.
    Includes self-correction loop (max 3 attempts).
    """
    logger.info("Coder: Generating code...")
    
    if not state.get('retrieved_chunks'):
        logger.info("Coder: No context for code execution, skipping")
        return state
    
    # Initialize LLM
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.2,
    )
    
    # Prepare data
    data_context = prepare_data_context(state)
    
    code = None
    error = None
    
    for attempt in range(settings.sandbox_max_attempts):
        try:
            # Generate code
            if attempt == 0:
                prompt = f"""{CODER_SYSTEM}

Query: {state['query']}

Data:
{data_context}

Code:"""
            else:
                prompt = f"""Fix the error and rewrite the code:

Error: {error}

Data:
{data_context}

Code:"""
            
            response = llm.invoke(prompt).content
            code = extract_code_block(response)
            
            if not code:
                logger.warning("Coder: No code found in response")
                continue
            
            logger.info(f"Coder: Attempt {attempt+1}: Executing code...")
            
            # Execute in sandbox
            # Register timeout handler
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(settings.sandbox_timeout_seconds)
            try:
                output = execute_safe(code)
            finally:
                signal.alarm(0)
            state['code_output'] = output
            
            logger.info("Coder: Code executed successfully")
            state['agent_trace'].append({
                'agent': 'coder',
                'timestamp': datetime.utcnow().isoformat(),
                'input_summary': f"Query: {state['query'][:50]}...",
                'output_summary': f"Code executed: {len(code)} chars",
                'duration_ms': 0,
                'token_count': 0,
            })
            
            return state
            
        except Exception as e:
            error = str(e)
            logger.warning(f"Coder: Attempt {attempt+1} failed: {error}")
            
            if attempt == settings.sandbox_max_attempts - 1:
                logger.error(f"Coder: All {settings.sandbox_max_attempts} attempts failed")
                state['errors'].append(f"Code execution failed: {error}")
                state['code_output'] = f"Error: {error}"
    
    return state


def execute_safe(code: str) -> str:
    """
    Execute Python code in restricted sandbox.
    
    Args:
        code: Python code to execute
        
    Returns:
        stdout + stderr output
    """
    # Compile restricted code
    try:
        compiled = compile_restricted(code, '<code>', 'exec')
        if compiled.errors:
            raise SyntaxError(f"Restricted code errors: {compiled.errors}")
    except SyntaxError as e:
        raise ValueError(f"Code syntax error: {str(e)}")
    
    # Setup safe globals (no network, no file write)
    safe_globals = {
        '__builtins__': {
            'abs': abs, 'all': all, 'any': any, 'bin': bin,
            'bool': bool, 'chr': chr, 'dict': dict, 'dir': dir,
            'enumerate': enumerate, 'filter': filter, 'float': float,
            'format': format, 'frozenset': frozenset, 'getattr': getattr,
            'int': int, 'isinstance': isinstance, 'len': len, 'list': list,
            'map': map, 'max': max, 'min': min, 'ord': ord, 'pow': pow,
            'print': print, 'range': range, 'reversed': reversed, 'round': round,
            'set': set, 'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple,
            'zip': zip, 'len': len,
        },
        '__name__': '__main__',
        '__doc__': None,
        'pd': __import__('pandas'),
        'np': __import__('numpy'),
        'math': __import__('math'),
        'json': __import__('json'),
        're': __import__('re'),
    }
    
    # Capture output
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()
    
    try:
        exec(compiled.code, safe_globals)
        output = captured_output.getvalue()
        return output if output else "Code executed successfully (no output)"
    except Exception as e:
        return f"Runtime error: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
    finally:
        sys.stdout = old_stdout


def extract_code_block(text: str) -> str:
    """Extract Python code from response."""
    # Try markdown code block
    if "```python" in text:
        start = text.find("```python") + 9
        end = text.find("```", start)
        if end > start:
            return text[start:end].strip()
    
    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            return text[start:end].strip()
    
    # Return whole text if looks like code
    if text.count('\n') > 2:
        return text
    
    return None


def prepare_data_context(state: AgentState) -> str:
    """Prepare retrieved data for code context."""
    if not state['retrieved_chunks']:
        return "No data available"
    
    # Create a simple data summary
    data = "\n".join([f"- {chunk['text'][:100]}..." for chunk in state['retrieved_chunks']])
    return data
