import os
import traceback
from .errors import FMS_Error, show_error_dialog
from .ast_nodes import *

class Environment:
    def __init__(self, enclosing=None): self.values = {}; self.enclosing = enclosing
    def define(self, name, value): self.values[name] = value
    def has(self, name):
        if name in self.values: return True
        if self.enclosing: return self.enclosing.has(name)
        return False
    def get(self, name):
        if name in self.values: return self.values[name]
        if self.enclosing: return self.enclosing.get(name)
        raise FMS_Error(f"Undefined variable '{name}'")
    def assign(self, name, value):
        if name in self.values: self.values[name] = value; return
        if self.enclosing: self.enclosing.assign(name, value); return
        raise FMS_Error(f"Undefined variable '{name}' for assignment")

class Callable:
    def arity(self): return 0
    def call(self, interpreter, args): pass

class NativeFunction(Callable):
    def __init__(self, name, arity, func): self.name = name; self._arity = arity; self.func = func
    def arity(self): return self._arity
    def call(self, interpreter, args): return self.func(interpreter, args)

class UserFunction(Callable):
    def __init__(self, name, params, body, closure): self.name = name; self.params = params; self.body = body; self.closure = closure
    def arity(self): return len(self.params)
    def call(self, interpreter, args):
        env = Environment(self.closure)
        for param, arg in zip(self.params, args): env.define(param, arg)
        try: interpreter.execute_block(self.body, env)
        except ReturnException as e: return e.value
        return None

class ReturnException(Exception):
    def __init__(self, value): self.value = value
class BreakException(Exception): pass
class ContinueException(Exception): pass

class Interpreter:
    def __init__(self):
        self.environment = Environment()
        self.current_line = None; self.current_col = None
        self.source_lines = []; self.last_result = None
        self.source_files = []; self.current_source_file = None

    def set_source(self, source_text, source_file=None):
        self.source_lines = source_text.split('\n')
        self.current_source_file = source_file
        self.source_files = [source_file] if source_file else []

    def _get_source_line(self, line_num):
        if line_num and 0 < line_num <= len(self.source_lines): return self.source_lines[line_num - 1]
        return None

    def interpret(self, program):
        try: self.execute_block(program.statements, self.environment)
        except FMS_Error as e:
            if e.line is None: e.line = self.current_line
            if e.col is None: e.col = self.current_col
            if e.source_line is None: e.source_line = self._get_source_line(e.line)
            if e.source_file is None: e.source_file = self.current_source_file
            show_error_dialog("Runtime Error", str(e), source_file=e.source_file); raise
        except ReturnException:
            err = FMS_Error("RETURN statement used outside of a function", source_file=self.current_source_file)
            show_error_dialog("Runtime Error", str(err), source_file=self.current_source_file); raise err
        except BreakException:
            err = FMS_Error("BREAK statement used outside of a loop", source_file=self.current_source_file)
            show_error_dialog("Runtime Error", str(err), source_file=self.current_source_file); raise err
        except ContinueException:
            err = FMS_Error("CONTINUE statement used outside of a loop", source_file=self.current_source_file)
            show_error_dialog("Runtime Error", str(err), source_file=self.current_source_file); raise err
        except Exception as e:
            tb = traceback.format_exc()
            error_msg = f"{str(e)}"
            if self.current_line: error_msg += f"\nat line {self.current_line}"
            if self.current_col: error_msg += f", col {self.current_col}"
            source_line = self._get_source_line(self.current_line)
            if source_line: error_msg += f"\n--> {source_line}"
            err = FMS_Error(error_msg, source_file=self.current_source_file)
            show_error_dialog("Internal Error", str(err), source_file=self.current_source_file, traceback_str=tb); raise err

    def execute_block(self, statements, env):
        previous = self.environment
        try:
            self.environment = env
            for stmt in statements: self.execute(stmt)
        finally: self.environment = previous

    def execute(self, node):
        if hasattr(node, 'line'): self.current_line = node.line
        if hasattr(node, 'col'): self.current_col = node.col
        
        if isinstance(node, Program): self.execute_block(node.statements, self.environment)
        elif isinstance(node, SetStmt):
            val = self.evaluate(node.value)
            if self.environment.has(node.name): self.environment.assign(node.name, val)
            else: self.environment.define(node.name, val)
        elif isinstance(node, IfStmt):
            if self.is_truthy(self.evaluate(node.condition)): self.execute_block(node.true_block, self.environment)
            elif node.false_block: self.execute_block(node.false_block, self.environment)
        elif isinstance(node, WhileStmt):
            while self.is_truthy(self.evaluate(node.condition)):
                try: self.execute_block(node.body, self.environment)
                except BreakException: break
                except ContinueException: continue
        elif isinstance(node, ForStmt):
            collection = self.evaluate(node.collection)
            if not isinstance(collection, (list, dict, str)):
                raise FMS_Error("FOR loop collection must be a list, dict, or string", line=self.current_line, col=self.current_col, source_line=self._get_source_line(self.current_line), source_file=self.current_source_file)
            items = list(collection.keys()) if isinstance(collection, dict) else collection
            for item in items:
                loop_env = Environment(self.environment)
                loop_env.define(node.var_name, collection[item] if isinstance(collection, dict) else item)
                try: self.execute_block(node.body, loop_env)
                except BreakException: break
                except ContinueException: continue
        elif isinstance(node, ForRangeStmt):
            start_val, end_val, step_val = self.evaluate(node.start), self.evaluate(node.end), self.evaluate(node.step)
            if not all(isinstance(v, (int, float)) for v in [start_val, end_val, step_val]):
                raise FMS_Error("FOR range loop requires numeric start, end, and step values", line=self.current_line, col=self.current_col, source_line=self._get_source_line(self.current_line), source_file=self.current_source_file)
            if step_val == 0: raise FMS_Error("STEP cannot be zero in FOR loop", line=self.current_line, col=self.current_col, source_line=self._get_source_line(self.current_line), source_file=self.current_source_file)
            current, end, step = float(start_val), float(end_val), float(step_val)
            condition = (lambda c: c <= end) if step > 0 else (lambda c: c >= end)
            while condition(current):
                loop_env = Environment(self.environment)
                loop_env.define(node.var_name, int(current) if current.is_integer() else current)
                try: self.execute_block(node.body, loop_env)
                except BreakException: break
                except ContinueException: continue
                current += step
        elif isinstance(node, BreakStmt): raise BreakException()
        elif isinstance(node, ContinueStmt): raise ContinueException()
        elif isinstance(node, TryStmt):
            try: self.execute_block(node.try_block, self.environment)
            except Exception as e:
                if node.catch_block:
                    catch_env = Environment(self.environment); catch_env.define(node.catch_var, str(e))
                    self.execute_block(node.catch_block, catch_env)
                else: raise
        elif isinstance(node, FunctionDef):
            self.environment.define(node.name, UserFunction(node.name, node.params, node.body, self.environment))
        elif isinstance(node, ReturnStmt):
            raise ReturnException(self.evaluate(node.value) if node.value else None)
        elif isinstance(node, IncludeStmt):
            filepath = node.filepath
            if not os.path.isabs(filepath):
                base_dir = os.path.dirname(os.path.abspath(self.current_source_file)) if self.current_source_file else os.getcwd()
                filepath = os.path.normpath(os.path.join(base_dir, filepath))
            previous_source_file, previous_source_lines = self.current_source_file, self.source_lines
            self.current_source_file, self.source_files = filepath, self.source_files + [filepath]
            try:
                from .lexer import Lexer; from .parser import Parser
                with open(filepath, 'r', encoding='utf-8') as f: module_code = f.read()
                module_ast = Parser(Lexer(module_code).tokens).parse()
                self.source_lines = module_code.split('\n')
                self.execute_block(module_ast.statements, self.environment)
            except FileNotFoundError:
                raise FMS_Error(f"Module file not found: '{filepath}'", line=self.current_line, col=self.current_col, error_type="Import Error", source_line=self._get_source_line(self.current_line), source_file=previous_source_file)
            except FMS_Error as e:
                if e.source_file is None: e.source_file = self.current_source_file
                if e.source_line is None and e.line is not None: e.source_line = self._get_source_line(e.line)
                raise
            except Exception as e:
                raise FMS_Error(f"Error loading module '{filepath}': {str(e)}", line=self.current_line, col=self.current_col, error_type="Import Error", source_line=self._get_source_line(self.current_line), source_file=filepath)
            finally:
                if self.source_files: self.source_files.pop()
                self.current_source_file, self.source_lines = previous_source_file, previous_source_lines
        else: self.last_result = self.evaluate(node)

    def evaluate(self, node):
        if hasattr(node, 'line'): self.current_line = node.line
        if hasattr(node, 'col'): self.current_col = node.col
        
        if isinstance(node, Literal): return node.value
        if isinstance(node, Variable): return self.environment.get(node.name)
        if isinstance(node, UnaryOp):
            right = self.evaluate(node.right)
            if node.op == '-': return -right
            if node.op == 'NOT': return not self.is_truthy(right)
        if isinstance(node, BinaryOp):
            left, right = self.evaluate(node.left), self.evaluate(node.right)
            if node.op == '+': return str(left) + str(right) if isinstance(left, str) or isinstance(right, str) else left + right
            # REMOVED: if node.op == 'AMP': return str(left) + str(right)
            if node.op == '-': return left - right
            if node.op == '*': return left * right
            if node.op == '/':
                if right == 0: raise FMS_Error("Division by zero", line=self.current_line, col=self.current_col, source_line=self._get_source_line(self.current_line), source_file=self.current_source_file)
                return left / right
            if node.op == 'EQ': return left == right
            if node.op == 'NEQ': return left != right
            if node.op == '<': return left < right
            if node.op == '>': return left > right
            if node.op == 'LTE': return left <= right
            if node.op == 'GTE': return left >= right
            if node.op == 'AND': return self.is_truthy(left) and self.is_truthy(right)
            if node.op == 'OR': return self.is_truthy(left) or self.is_truthy(right)
        if isinstance(node, Call):
            callee_name = node.callee.name if isinstance(node.callee, Variable) else "expression"
            try: callee = self.environment.get(callee_name)
            except FMS_Error: callee = self.environment.get(callee_name.upper()) if isinstance(node.callee, Variable) else self.evaluate(node.callee)
            args = [self.evaluate(arg) for arg in node.args]
            if isinstance(callee, Callable):
                if callee.arity() != -1 and len(args) != callee.arity():
                    raise FMS_Error(f"Expected {callee.arity()} arguments but got {len(args)}", line=self.current_line, col=self.current_col, source_line=self._get_source_line(self.current_line), source_file=self.current_source_file)
                return callee.call(self, args)
            raise FMS_Error(f"Cannot call '{callee_name}': it is not a function.", line=self.current_line, col=self.current_col, source_line=self._get_source_line(self.current_line), source_file=self.current_source_file)
        if isinstance(node, ListLiteral): return [self.evaluate(el) for el in node.elements]
        if isinstance(node, DictLiteral):
            d = {}
            for k, v in node.pairs: d[self.evaluate(k)] = self.evaluate(v)
            return d
        if isinstance(node, IndexAccess):
            obj, index = self.evaluate(node.obj), self.evaluate(node.index)
            if isinstance(obj, (list, str)): return obj[int(index)]
            if isinstance(obj, dict): return obj[index]
            raise FMS_Error("Only lists, strings, and dicts support indexing", line=self.current_line, col=self.current_col, source_line=self._get_source_line(self.current_line), source_file=self.current_source_file)
        if isinstance(node, MemberAccess):
            obj = self.evaluate(node.obj)
            if isinstance(obj, dict): return obj.get(node.name)
            raise FMS_Error("Member access only supported on dictionaries", line=self.current_line, col=self.current_col, source_line=self._get_source_line(self.current_line), source_file=self.current_source_file)
        return None

    def is_truthy(self, value):
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, (int, float)): return value != 0
        if isinstance(value, str): return len(value) > 0
        if isinstance(value, (list, dict)): return len(value) > 0
        return True