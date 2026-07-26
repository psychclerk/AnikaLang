from .errors import FMS_Error
from .ast_nodes import *

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.current_token = self.tokens[0]
        self.previous_token = None

    def advance(self):
        self.previous_token = self.current_token
        if not self.is_at_end():
            self.pos += 1
            self.current_token = self.tokens[self.pos]

    def is_at_end(self): return self.current_token.type == 'EOF'
    def check(self, type_): return not self.is_at_end() and self.current_token.type == type_
    
    def match(self, *types):
        for t in types:
            if self.check(t):
                self.advance()
                return True
        return False

    def eat(self, type_):
        if self.check(type_):
            self.advance()
            return
        raise FMS_Error(f"Expected '{type_}', got '{self.current_token.type}'", self.current_token.line, self.current_token.col)

    def parse(self):
        statements = []
        while not self.is_at_end():
            statements.append(self.parse_statement())
        return Program(statements)

    def parse_statement(self):
        # 1. Check for Assignment: x = 10
        if self.check('IDENT') and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == 'ASSIGN':
            return self.parse_assignment()

        if self.check('IF'): self.advance(); return self.parse_if()
        if self.check('WHILE'): self.advance(); return self.parse_while()
        if self.check('FOR'): self.advance(); return self.parse_for()
        if self.check('BREAK'): self.advance(); return BreakStmt()
        if self.check('CONTINUE'): self.advance(); return ContinueStmt()
        if self.check('TRY'): self.advance(); return self.parse_try()
        if self.check('DEF'): self.advance(); return self.parse_function_def() # Changed from FUNCTION
        if self.check('RETURN'): self.advance(); return self.parse_return()
        if self.check('INCLUDE'):
            self.advance()
            if self.check('STRING'):
                filepath = self.current_token.value; self.advance()
                return IncludeStmt(filepath)
            else: raise FMS_Error("Expected string filepath after INCLUDE", self.current_token.line, self.current_token.col)
        return self.parse_expression()

    def parse_assignment(self):
        line, col = self.current_token.line, self.current_token.col
        name = self.current_token.value
        self.eat('IDENT')
        self.eat('ASSIGN') # Expects '='
        return SetStmt(name, self.parse_expression(), line, col)

    def parse_if(self):
        line, col = self.current_token.line, self.current_token.col
        condition = self.parse_expression()
        self.eat('{') # Expects opening brace
        true_block = []
        while not self.check('}') and not self.check('ELSE') and not self.is_at_end():
            true_block.append(self.parse_statement())
        self.eat('}') # Expects closing brace

        false_block = None
        if self.match('ELSE'):
            self.eat('{')
            false_block = []
            while not self.check('}') and not self.is_at_end():
                false_block.append(self.parse_statement())
            self.eat('}')
        return IfStmt(condition, true_block, false_block, line, col)

    def parse_while(self):
        line, col = self.current_token.line, self.current_token.col
        condition = self.parse_expression()
        self.eat('{')
        body = []
        while not self.check('}') and not self.is_at_end():
            body.append(self.parse_statement())
        self.eat('}')
        return WhileStmt(condition, body, line, col)

    def parse_for(self):
        line, col = self.current_token.line, self.current_token.col
        var_name = self.current_token.value; self.eat('IDENT'); self.eat('IN')
        is_range = False; start_expr = None; end_expr = None; step_expr = Literal(1); collection = None
        
        if self.check('['):
            self.advance(); start_expr = self.parse_expression()
            if self.match('DOTDOT'):
                is_range = True; end_expr = self.parse_expression(); self.eat(']')
            else:
                elements = [start_expr]
                while self.match(','): elements.append(self.parse_expression())
                self.eat(']'); collection = ListLiteral(elements)
        else:
            start_expr = self.parse_expression()
            # REMOVED 'TO' keyword support, relying on '..' (DOTDOT) for ranges
            if self.match('DOTDOT'):
                is_range = True; end_expr = self.parse_expression()
            else: collection = start_expr

        if is_range:
            if self.match('STEP'): step_expr = self.parse_expression()
            self.eat('{') # Changed from THEN
            body = []
            while not self.check('}') and not self.is_at_end(): body.append(self.parse_statement())
            self.eat('}') # Changed from END FOR
            return ForRangeStmt(var_name, start_expr, end_expr, step_expr, body, line, col)
        else:
            self.eat('{') # Changed from THEN
            body = []
            while not self.check('}') and not self.is_at_end(): body.append(self.parse_statement())
            self.eat('}') # Changed from END FOR
            return ForStmt(var_name, collection, body, line, col)

    def parse_try(self):
        self.eat('{')
        try_block = []
        while not self.check('}') and not self.check('CATCH') and not self.is_at_end():
            try_block.append(self.parse_statement())
        self.eat('}')
        
        catch_var, catch_block = None, None
        if self.match('CATCH'):
            catch_var = self.current_token.value; self.eat('IDENT')
            self.eat('{')
            catch_block = []
            while not self.check('}') and not self.is_at_end(): catch_block.append(self.parse_statement())
            self.eat('}')
        return TryStmt(try_block, catch_var, catch_block)

    def parse_function_def(self):
        line, col = self.current_token.line, self.current_token.col
        name = self.current_token.value; self.eat('IDENT'); self.eat('(')
        params = []
        if not self.check(')'):
            params.append(self.current_token.value); self.eat('IDENT')
            while self.match(','): params.append(self.current_token.value); self.eat('IDENT')
        self.eat(')')
        
        self.eat('{') # Expects opening brace
        body = []
        while not self.check('}') and not self.is_at_end(): body.append(self.parse_statement())
        self.eat('}') # Expects closing brace
        
        return FunctionDef(name, params, body, line, col)

    def parse_return(self):
        if self.check('}') or self.is_at_end(): return ReturnStmt(None)
        return ReturnStmt(self.parse_expression())

    def parse_expression(self): return self.parse_or()
    def parse_or(self):
        expr = self.parse_and()
        while self.match('OR'): expr = BinaryOp(expr, self.previous_token.type, self.parse_and())
        return expr
    def parse_and(self):
        expr = self.parse_equality()
        while self.match('AND'): expr = BinaryOp(expr, self.previous_token.type, self.parse_equality())
        return expr
    def parse_equality(self):
        expr = self.parse_comparison()
        while self.match('EQ', 'NEQ'): expr = BinaryOp(expr, self.previous_token.type, self.parse_comparison())
        return expr
    def parse_comparison(self):
        expr = self.parse_term()
        while self.match('<', '>', 'LTE', 'GTE'): expr = BinaryOp(expr, self.previous_token.type, self.parse_term())
        return expr
        
    def parse_term(self):
        expr = self.parse_factor()
        # REMOVED 'AMP' (&) so AI only uses '+' for concatenation
        while self.match('+', '-'): 
            expr = BinaryOp(expr, self.previous_token.type, self.parse_factor())
        return expr
        
    def parse_factor(self):
        expr = self.parse_unary()
        while self.match('*', '/'): expr = BinaryOp(expr, self.previous_token.type, self.parse_unary())
        return expr
    def parse_unary(self):
        if self.match('-', 'NOT'): return UnaryOp(self.previous_token.type, self.parse_unary())
        return self.parse_call()
        
    def parse_call(self):
        expr = self.parse_primary()
        while True:
            if self.match('('):
                args = []
                if not self.check(')'):
                    args.append(self.parse_expression())
                    while self.match(','): args.append(self.parse_expression())
                self.eat(')'); expr = Call(expr, args)
            elif self.match('['):
                index = self.parse_expression(); self.eat(']'); expr = IndexAccess(expr, index)
            elif self.match('.'):
                name = self.current_token.value; self.eat('IDENT'); expr = MemberAccess(expr, name)
            else: break
        return expr

    def parse_primary(self):
        if self.match('TRUE'): return Literal(True, self.previous_token.line, self.previous_token.col)
        if self.match('FALSE'): return Literal(False, self.previous_token.line, self.previous_token.col)
        if self.match('NULL'): return Literal(None, self.previous_token.line, self.previous_token.col)
        if self.match('NUMBER'): return Literal(self.previous_token.value, self.previous_token.line, self.previous_token.col)
        if self.match('STRING'): return Literal(self.previous_token.value, self.previous_token.line, self.previous_token.col)
        if self.match('IDENT'): return Variable(self.previous_token.value, self.previous_token.line, self.previous_token.col)
        if self.match('('):
            expr = self.parse_expression(); self.eat(')'); return expr
        if self.match('['):
            elements = []
            if not self.check(']'):
                elements.append(self.parse_expression())
                while self.match(','): elements.append(self.parse_expression())
            self.eat(']'); return ListLiteral(elements)
        if self.match('{'):
            pairs = []
            if not self.check('}'):
                key = self.parse_expression(); self.eat(':'); val = self.parse_expression(); pairs.append((key, val))
                while self.match(','):
                    key = self.parse_expression(); self.eat(':'); val = self.parse_expression(); pairs.append((key, val))
            self.eat('}'); return DictLiteral(pairs)
        raise FMS_Error("Expected expression", self.current_token.line, self.current_token.col)