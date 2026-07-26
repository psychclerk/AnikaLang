import datetime
from .ast_nodes import *

# ==============================================================================
# RUNTIME PREAMBLE — emitted verbatim at column 0 of every compiled file.
# (No backslashes / no triple-quotes inside, so it is safe as a ''' literal.)
# ==============================================================================
PREAMBLE = '''import sys as _sys, os as _os

_HERE = _os.path.dirname(_os.path.abspath(__file__))

def _find_root(start):
    d = _os.path.abspath(start)
    for _ in range(10):
        if _os.path.isdir(_os.path.join(d, "plugins")) and _os.path.isdir(_os.path.join(d, "core")):
            return d
        p = _os.path.dirname(d)
        if p == d:
            break
        d = p
    return None

_ROOT = _find_root(_HERE) or _find_root(_os.getcwd())
if _ROOT and _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

_ANIKALANG_AVAILABLE = False
_Interpreter = None
_NativeFunction = None
_PluginManager = None
try:
    from core.interpreter import Interpreter as _Interpreter
    from core.interpreter import NativeFunction as _NativeFunction
    from core.plugin_manager import PluginManager as _PluginManager
    _ANIKALANG_AVAILABLE = True
except Exception:
    _ANIKALANG_AVAILABLE = False

_interp = None
if _ANIKALANG_AVAILABLE:
    try:
        _interp = _Interpreter()
        if _ROOT:
            _PluginManager(_os.path.join(_ROOT, "plugins")).load_plugins(_interp.environment, _interp)
    except Exception as _e:
        _sys.stderr.write("[anika-compiled] runtime init warning: " + str(_e) + chr(10))
        _interp = None

def _add(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return str(a) + str(b)
    return a + b

def _dot(o, n):
    if isinstance(o, dict):
        return o.get(n)
    return getattr(o, n)

def _fms(name, *args):
    if _interp is None:
        raise RuntimeError("AnikaLang runtime unavailable for call: %s" % name)
    env = _interp.environment
    if env.has(name):
        return env.get(name).call(_interp, list(args))
    up = name.upper()
    if env.has(up):
        return env.get(up).call(_interp, list(args))
    lo = name.lower()
    if env.has(lo):
        return env.get(lo).call(_interp, list(args))
    raise RuntimeError("Undefined AnikaLang function: %s" % name)

def _reg(name, fn):
    if _interp is not None and _NativeFunction is not None:
        try:
            # Mirror the interpreter's zip(params, args) semantics: a UI
            # callback always forwards the widget (and sometimes x,y), but a
            # handler may declare fewer parameters. Drop the extras instead of
            # raising TypeError. Only forward everything when fn is variadic.
            _code = getattr(fn, "__code__", None)
            if _code is not None and not (_code.co_flags & 0x04):   # no *args
                _n = _code.co_argcount
                _wrapper = lambda i, a, _f=fn, _n=_n: _f(*a[:_n])
            else:
                _wrapper = lambda i, a, _f=fn: _f(*a)
            _interp.environment.define(name, _NativeFunction(name, -1, _wrapper))
        except Exception:
            pass

def _include(path):
    if _interp is None:
        return
    cand = []
    if _os.path.isabs(path):
        cand.append(path)
    else:
        cand.append(_os.path.normpath(_os.path.join(_HERE, path)))
        if _ROOT:
            cand.append(_os.path.normpath(_os.path.join(_ROOT, path)))
    fp = None
    for c in cand:
        if _os.path.exists(c):
            fp = c
            break
    if fp is None:
        raise RuntimeError("Included module not found: %s" % path)
    from core.lexer import Lexer as _Lx
    from core.parser import Parser as _Ps
    with open(fp, "r", encoding="utf-8") as _fh:
        _code = _fh.read()
    _ast = _Ps(_Lx(_code).tokens).parse()
    _interp.set_source(_code, source_file=fp)
    _interp.execute_block(_ast.statements, _interp.environment)
'''

AUTO_MAINLOOP = '''try:
    if 'win' in dir() and win is not None and _interp is not None and getattr(_interp, 'wx_app', None) is not None:
        _interp.wx_app.MainLoop()
except Exception:
    pass
'''


class Compiler:
    def __init__(self):
        self.indent_level = 0
        self.output = []
        self.functions_defined = []   # names of user fns in this file (-> direct calls)
        self.global_vars = set()      # module-level bindings
        self._enclosing_locals = []   # stack of name-sets bound by enclosing funcs

    # --------------------------------------------------------------- helpers
    def indent(self):
        return "    " * self.indent_level

    def emit(self, code):
        self.output.append(f"{self.indent()}{code}")

    def _calls_mainloop(self, node):
        if isinstance(node, Call) and isinstance(node.callee, Variable):
            return node.callee.name.lower() == "ui_mainloop"
        return False

    # Module-level bindings: top-level assignments + function defs,
    # recursing through top-level if/while/try (which execute in the
    # global environment) but NOT through for-loops (own loop env) or
    # function bodies (separate scopes).
    def _collect_globals(self, stmts):
        for node in stmts:
            if isinstance(node, SetStmt):
                self.global_vars.add(node.name)
            elif isinstance(node, FunctionDef):
                self.global_vars.add(node.name)
            elif isinstance(node, IfStmt):
                if node.true_block: self._collect_globals(node.true_block)
                if node.false_block: self._collect_globals(node.false_block)
            elif isinstance(node, WhileStmt):
                if node.body: self._collect_globals(node.body)
            elif isinstance(node, TryStmt):
                if node.try_block: self._collect_globals(node.try_block)

    # Names assigned (SetStmt) anywhere in a block, recursing through all
    # control-flow bodies but STOPPING at nested function defs and NOT
    # counting for-loop / catch variables (those are not function bindings).
    def _collect_assigned_names(self, stmts):
        names = set()
        for node in stmts:
            if isinstance(node, SetStmt):
                names.add(node.name)
            elif isinstance(node, IfStmt):
                if node.true_block: names |= self._collect_assigned_names(node.true_block)
                if node.false_block: names |= self._collect_assigned_names(node.false_block)
            elif isinstance(node, WhileStmt):
                if node.body: names |= self._collect_assigned_names(node.body)
            elif isinstance(node, ForStmt):
                if node.body: names |= self._collect_assigned_names(node.body)
            elif isinstance(node, ForRangeStmt):
                if node.body: names |= self._collect_assigned_names(node.body)
            elif isinstance(node, TryStmt):
                if node.try_block: names |= self._collect_assigned_names(node.try_block)
                if node.catch_block: names |= self._collect_assigned_names(node.catch_block)
            # nested FunctionDef -> separate scope, do not descend
        return names

    # --------------------------------------------------------------- compile
    def compile(self, program):
        self._collect_globals(program.statements)

        self.output.append("# Auto-generated Python code from the AnikaLang 1.2 compiler")
        self.output.append("# Generated: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.output.append(PREAMBLE)

        has_mainloop = any(self._calls_mainloop(s) for s in program.statements)

        for stmt in program.statements:
            self.compile_stmt(stmt)

        if not has_mainloop:
            self.output.append(AUTO_MAINLOOP)

        return "\n".join(self.output)

    # ----------------------------------------------------------- compile_stmt
    def compile_stmt(self, node):
        if isinstance(node, SetStmt):
            # NOTE: no inline 'global' here any more — declarations are
            # hoisted to the top of the enclosing function (see FunctionDef).
            self.emit(f"{node.name} = {self.compile_expr(node.value)}")

        elif isinstance(node, IfStmt):
            self.emit(f"if {self.compile_expr(node.condition)}:")
            self.indent_level += 1
            if node.true_block:
                for s in node.true_block: self.compile_stmt(s)
            else:
                self.emit("pass")
            self.indent_level -= 1
            if node.false_block:
                self.emit("else:")
                self.indent_level += 1
                for s in node.false_block: self.compile_stmt(s)
                self.indent_level -= 1

        elif isinstance(node, WhileStmt):
            self.emit(f"while {self.compile_expr(node.condition)}:")
            self.indent_level += 1
            if node.body:
                for s in node.body: self.compile_stmt(s)
            else:
                self.emit("pass")
            self.indent_level -= 1

        elif isinstance(node, ForStmt):
            self.emit(f"for {node.var_name} in {self.compile_expr(node.collection)}:")
            self.indent_level += 1
            if node.body:
                for s in node.body: self.compile_stmt(s)
            else:
                self.emit("pass")
            self.indent_level -= 1

        elif isinstance(node, ForRangeStmt):
            start = self.compile_expr(node.start)
            end = self.compile_expr(node.end)
            step = self.compile_expr(node.step)
            self.emit(f"for {node.var_name} in range(int({start}), int({end}) + (1 if ({step}) > 0 else -1), int({step})):")
            self.indent_level += 1
            if node.body:
                for s in node.body: self.compile_stmt(s)
            else:
                self.emit("pass")
            self.indent_level -= 1

        elif isinstance(node, FunctionDef):
            self.functions_defined.append(node.name)
            params_src = ", ".join(node.params) if node.params else ""
            self.emit(f"def {node.name}({params_src}):")
            self.indent_level += 1

            # ---- hoist global / nonlocal declarations to the top ----
            param_set = set(node.params)
            assigned = self._collect_assigned_names(node.body)
            enc_union = set()
            for s in self._enclosing_locals:
                enc_union |= s
            # enclosing-function scope wins over module global
            nset = (assigned & enc_union) - param_set
            gset = (assigned & self.global_vars) - param_set - nset
            own_locals = assigned - param_set - gset - nset
            if gset:
                self.emit("global " + ", ".join(sorted(gset)))
            if nset:
                self.emit("nonlocal " + ", ".join(sorted(nset)))

            # publish this function's bindings for any nested functions
            self._enclosing_locals.append(param_set | own_locals)
            if node.body:
                for s in node.body:
                    self.compile_stmt(s)
            else:
                self.emit("pass")
            self._enclosing_locals.pop()
            self.indent_level -= 1

            # register top-level functions so UI string callbacks resolve
            if self.indent_level == 0:
                self.emit(f"_reg({node.name!r}, {node.name})")
            self.emit("")

        elif isinstance(node, ReturnStmt):
            self.emit(f"return {self.compile_expr(node.value) if node.value else 'None'}")

        elif isinstance(node, BreakStmt):
            self.emit("break")

        elif isinstance(node, ContinueStmt):
            self.emit("continue")

        elif isinstance(node, TryStmt):
            self.emit("try:")
            self.indent_level += 1
            if node.try_block:
                for s in node.try_block: self.compile_stmt(s)
            else:
                self.emit("pass")
            self.indent_level -= 1
            if node.catch_block:
                self.emit(f"except Exception as {node.catch_var or '_err'}:")
                self.indent_level += 1
                for s in node.catch_block: self.compile_stmt(s)
                self.indent_level -= 1
            else:
                self.emit("except Exception:")
                self.indent_level += 1
                self.emit("pass")
                self.indent_level -= 1

        elif isinstance(node, IncludeStmt):
            self.emit(f"_include({node.filepath!r})")

        elif isinstance(node, Call):
            self.emit(self.compile_expr(node))

    # ----------------------------------------------------------- compile_expr
    def compile_expr(self, node):
        if isinstance(node, Literal):
            if node.value is None: return "None"
            if isinstance(node.value, bool): return "True" if node.value else "False"
            if isinstance(node.value, str): return self._escape_string(node.value)
            return str(node.value)

        if isinstance(node, Variable):
            return node.name

        if isinstance(node, UnaryOp):
            right = self.compile_expr(node.right)
            if node.op == 'NOT': return f"(not {right})"
            if node.op == '-': return f"(-{right})"
            return right

        if isinstance(node, BinaryOp):
            left = self.compile_expr(node.left)
            right = self.compile_expr(node.right)
            if node.op == '+':                       # AnikaLang auto-coerces strings
                return f"_add({left}, {right})"
            op_map = {'-': '-', '*': '*', '/': '/',
                      'AND': 'and', 'OR': 'or',
                      'EQ': '==', 'NEQ': '!=',
                      '<': '<', '>': '>', 'LTE': '<=', 'GTE': '>='}
            return f"({left} {op_map.get(node.op, node.op)} {right})"

        if isinstance(node, Call):
            return self._compile_call(node)

        if isinstance(node, ListLiteral):
            return "[" + ", ".join(self.compile_expr(el) for el in node.elements) + "]"

        if isinstance(node, DictLiteral):
            pairs = ", ".join(f"{self.compile_expr(k)}: {self.compile_expr(v)}" for k, v in node.pairs)
            return "{" + pairs + "}"

        if isinstance(node, IndexAccess):
            return f"{self.compile_expr(node.obj)}[{self.compile_expr(node.index)}]"

        if isinstance(node, MemberAccess):           # d.key -> dict-aware access
            return f"_dot({self.compile_expr(node.obj)}, {node.name!r})"

        return "None"

    def _compile_call(self, node):
        if not isinstance(node.callee, Variable):
            return f"{self.compile_expr(node.callee)}({', '.join(self.compile_expr(a) for a in node.args)})"
        func_name = node.callee.name
        args_str = ", ".join(self.compile_expr(a) for a in node.args)
        # Same-file user functions compile to direct Python calls (keeps
        # recursion / closures / nesting correct); everything else routes
        # through the runtime so semantics match the interpreter.
        if func_name in self.functions_defined:
            return f"{func_name}({args_str})" if args_str else f"{func_name}()"
        return f"_fms({func_name!r}, {args_str})" if args_str else f"_fms({func_name!r})"

    def _escape_string(self, s):
        s = str(s).replace('\\', '\\\\').replace('"', '\\"')
        s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return f'"{s}"'