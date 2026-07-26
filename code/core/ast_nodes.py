class ASTNode: pass
class Program(ASTNode):
    def __init__(self, statements, line=None, col=None): self.statements = statements; self.line = line; self.col = col
class SetStmt(ASTNode):
    def __init__(self, name, value, line=None, col=None): self.name = name; self.value = value; self.line = line; self.col = col
class IfStmt(ASTNode):
    def __init__(self, condition, true_block, false_block, line=None, col=None): self.condition = condition; self.true_block = true_block; self.false_block = false_block; self.line = line; self.col = col
class WhileStmt(ASTNode):
    def __init__(self, condition, body, line=None, col=None): self.condition = condition; self.body = body; self.line = line; self.col = col
class ForStmt(ASTNode):
    def __init__(self, var_name, collection, body, line=None, col=None): self.var_name = var_name; self.collection = collection; self.body = body; self.line = line; self.col = col
class ForRangeStmt(ASTNode):
    def __init__(self, var_name, start, end, step, body, line=None, col=None): self.var_name = var_name; self.start = start; self.end = end; self.step = step; self.body = body; self.line = line; self.col = col
class BreakStmt(ASTNode): pass
class ContinueStmt(ASTNode): pass
class TryStmt(ASTNode):
    def __init__(self, try_block, catch_var, catch_block, line=None, col=None): self.try_block = try_block; self.catch_var = catch_var; self.catch_block = catch_block; self.line = line; self.col = col
class FunctionDef(ASTNode):
    def __init__(self, name, params, body, line=None, col=None): self.name = name; self.params = params; self.body = body; self.line = line; self.col = col
class ReturnStmt(ASTNode):
    def __init__(self, value, line=None, col=None): self.value = value; self.line = line; self.col = col
class IncludeStmt(ASTNode):
    def __init__(self, filepath): self.filepath = filepath
class BinaryOp(ASTNode):
    def __init__(self, left, op, right, line=None, col=None): self.left = left; self.op = op; self.right = right; self.line = line; self.col = col
class UnaryOp(ASTNode):
    def __init__(self, op, right, line=None, col=None): self.op = op; self.right = right; self.line = line; self.col = col
class Call(ASTNode):
    def __init__(self, callee, args, line=None, col=None): self.callee = callee; self.args = args; self.line = line; self.col = col
class Variable(ASTNode):
    def __init__(self, name, line=None, col=None): self.name = name; self.line = line; self.col = col
class Literal(ASTNode):
    def __init__(self, value, line=None, col=None): self.value = value; self.line = line; self.col = col
class ListLiteral(ASTNode):
    def __init__(self, elements, line=None, col=None): self.elements = elements; self.line = line; self.col = col
class DictLiteral(ASTNode):
    def __init__(self, pairs, line=None, col=None): self.pairs = pairs; self.line = line; self.col = col
class IndexAccess(ASTNode):
    def __init__(self, obj, index, line=None, col=None): self.obj = obj; self.index = index; self.line = line; self.col = col
class MemberAccess(ASTNode):
    def __init__(self, obj, name, line=None, col=None): self.obj = obj; self.name = name; self.line = line; self.col = col