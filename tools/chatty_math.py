import ast
import math

from .llm_tool_base import LLMTool, LLMToolParameter


# Allow a small, explicit set of math functions so the model can answer
# slightly richer questions (trig, logs, etc.) without exposing Python internals.
ALLOWED_MATH_FUNCTIONS = {
    name: getattr(math, name)
    for name in [
        "acos", "asin", "atan", "atan2", "ceil", "cos", "cosh", "degrees",
        "exp", "fabs", "floor", "fmod", "log", "log10", "pow", "radians",
        "sin", "sinh", "sqrt", "tan", "tanh"
    ]
}
ALLOWED_MATH_FUNCTIONS["abs"] = abs
ALLOWED_MATH_FUNCTIONS["round"] = round


ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.FloorDiv,
    ast.USub,
    ast.UAdd,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.Num,  # Python <3.8 compatibility
)


def _validate_node(node: ast.AST) -> None:
    """Recursively ensure the AST only contains safe math constructs."""
    if not isinstance(node, ALLOWED_AST_NODES):
        raise ValueError(f"Unsupported syntax: {ast.dump(node, include_attributes=False)}")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_MATH_FUNCTIONS:
            raise ValueError("Only approved math functions are allowed")
    elif isinstance(node, ast.Name):
        if node.id not in ALLOWED_MATH_FUNCTIONS:
            raise ValueError("Unknown identifier in expression")
    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ValueError("Only numeric constants are allowed")

    for child in ast.iter_child_nodes(node):
        _validate_node(child)


def safe_math_eval(expression: str) -> float:
    """Evaluate a math expression while blocking unsafe constructs."""
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid math expression") from exc

    _validate_node(parsed)

    compiled = compile(parsed, filename="<chatty-math>", mode="eval")
    return eval(compiled, {"__builtins__": {}}, ALLOWED_MATH_FUNCTIONS)


class MathTool(LLMTool):
    def __init__(self, master_state):
        expression = LLMToolParameter("expression","a math calculation to perform in pyton eval format that does not require any imports or packages", required=True)

        super().__init__("math_tool", 
                         "use this tool when the user asks to perform a math calculation",
                         [expression], 
                         master_state)
        
    async def invoke(self, args):
        try:
            result = safe_math_eval(args["expression"])
            return "The answer is " + str(result)
        except Exception as exc:
            return f"The calculation failed: {str(exc)}."
