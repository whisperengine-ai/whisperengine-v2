import math
import sympy
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger

class MathInput(BaseModel):
    query: str = Field(description="The math problem to solve. Can be arithmetic, algebra, calculus, or geometry. Examples: '2 + 2', 'solve x^2 + 2x + 1 = 0', 'derivative of sin(x)', 'integrate x^2', 'is 29 prime?'. Use Python syntax for expressions where possible.")

class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = (
        "A comprehensive math tool powered by Python's SymPy library. "
        "Use this for ANY mathematical task including:\n"
        "- Basic Arithmetic: 2 + 2, 5 * 10^3\n"
        "- Algebra: Solving equations (e.g., 'solve x^2 - 4 = 0')\n"
        "- Calculus: Derivatives ('diff(sin(x))'), Integrals ('integrate(x**2)')\n"
        "- Geometry & Trigonometry: sin(pi/4), degrees(atan(0.5))\n"
        "- Number Theory: isprime(17), factor(100)\n"
        "Input should be a clear mathematical query or Python expression."
    )
    args_schema: Type[BaseModel] = MathInput

    def _run(self, query: str) -> str:
        try:
            # 1. Pre-processing to make natural language friendlier
            # SymPy prefers '**' for power, but users might use '^'
            # We'll do a naive replacement if it looks like a math expression
            clean_query = query.replace("^", "**")
            
            # 2. Setup the execution environment with SymPy symbols and functions
            # We import everything from sympy into the local namespace
            local_env = {}
            exec("from sympy import *", {}, local_env)
            exec("from math import degrees, radians, pi, e", {}, local_env) # Add standard math constants/funcs if missing from sympy
            
            # Define common symbols to avoid "name 'x' is not defined" errors
            x, y, z, t, a, b, c = sympy.symbols('x y z t a b c')
            local_env.update({'x': x, 'y': y, 'z': z, 't': t, 'a': a, 'b': b, 'c': c})

            # 3. Handle "solve" commands specifically
            # If the user says "solve x^2 - 4 = 0", we need to parse it
            if clean_query.lower().startswith("solve "):
                equation_part = clean_query[6:]
                # Handle "=" sign for equations
                if "=" in equation_part:
                    lhs, rhs = equation_part.split("=", 1)
                    # SymPy Eq(lhs, rhs)
                    expr = f"solve(Eq({lhs}, {rhs}))"
                else:
                    # Assume = 0
                    expr = f"solve({equation_part})"
            
            # 4. Handle "derivative of" or "derive"
            elif "derivative of" in clean_query.lower():
                target = clean_query.lower().split("derivative of")[1].strip()
                expr = f"diff({target})"
            
            # 5. Handle "integrate"
            elif clean_query.lower().startswith("integrate "):
                target = clean_query[10:].strip()
                expr = f"integrate({target})"

            else:
                # Default: try to evaluate as an expression
                expr = clean_query

            # 6. Execute safely
            # We use sympify for parsing strings into SymPy expressions, 
            # but for full flexibility (like calling functions), eval is often needed with the restricted env.
            # Given this is an internal tool, we'll use eval with the populated local_env.
            
            # Safety check: prevent import or file operations
            if any(bad in expr for bad in ["import ", "open(", "exec(", "eval(", "system(", "__"]):
                return "Error: Unsafe code detected."

            result = eval(expr, {"__builtins__": {}}, local_env)
            
            return f"Result: {result}"

        except Exception as e:
            # Fallback: Try simple math eval if SymPy failed (e.g. for simple arithmetic that might have failed parsing)
            try:
                # Basic math fallback
                import math
                safe_dict = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
                return str(eval(query, {"__builtins__": {}}, safe_dict))
            except:
                return f"Error calculating '{query}': {str(e)}"

    async def _arun(self, query: str) -> str:
        """Async implementation with LLM fallback for natural language queries."""
        try:
            # Try direct execution first (fastest)
            return self._run(query)
        except Exception:
            # If direct execution failed, it might be natural language.
            # Use a small LLM to translate it to code.
            try:
                from src_v2.agents.llm_factory import create_llm
                from langchain_core.messages import SystemMessage, HumanMessage
                
                # Use utility mode (fast/cheap)
                llm = create_llm(temperature=0.0, mode="utility")
                
                system_prompt = (
                    "You are a mathematical expression translator. "
                    "Convert the user's natural language math problem into a valid Python/SymPy expression. "
                    "Use 'degrees()', 'radians()', 'sin()', 'cos()', 'tan()', 'atan()', 'sqrt()', 'solve()', 'integrate()', 'diff()'. "
                    "For FOV: 2 * degrees(atan(sensor / (2 * focal))). "
                    "Return ONLY the expression. No markdown, no explanation."
                )
                
                response = await llm.ainvoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=query)
                ])
                
                expression = response.content.strip().replace("`", "").replace("python", "")
                logger.info(f"Math Tool: Translated '{query}' to '{expression}'")
                
                return self._run(expression)
                
            except Exception as e:
                return f"Error calculating '{query}': {str(e)}"
