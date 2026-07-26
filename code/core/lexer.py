from .errors import FMS_Error

class Token:
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []
        # REMOVED: SET, TO, THEN, END, FUNCTION
        # ADDED: DEF
        self.keywords = {
            'DEF', 'IF', 'ELSE', 'FOR', 'IN', 'WHILE',
            'BREAK', 'CONTINUE', 'TRY', 'CATCH', 'RETURN',
            'TRUE', 'FALSE', 'NULL', 'AND', 'OR', 'NOT', 'STEP', 'INCLUDE'
        }
        self.tokenize()

    def advance(self):
        if self.pos < len(self.text):
            if self.text[self.pos] == '\n':
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.pos += 1

    def peek(self, offset=1):
        pos = self.pos + offset
        return self.text[pos] if pos < len(self.text) else '\0'

    def tokenize(self):
        while self.pos < len(self.text):
            char = self.text[self.pos]
            
            # Whitespace & Comments
            if char in ' \t\r\n':
                self.advance()
                continue
            if char == '#':
                while self.pos < len(self.text) and self.text[self.pos] != '\n':
                    self.advance()
                continue

            # Strings
            if char in ('"', "'"):
                start_line, start_col = self.line, self.col
                quote = char
                self.advance()
                start = self.pos
                string_value = []
                while self.pos < len(self.text) and self.text[self.pos] != quote:
                    c = self.text[self.pos]
                    if c == '\\' and self.pos + 1 < len(self.text):
                        self.advance()
                        next_c = self.text[self.pos]
                        if next_c == 'n': string_value.append('\n')
                        elif next_c == 't': string_value.append('\t')
                        elif next_c == 'r': string_value.append('\r')
                        elif next_c == '\\': string_value.append('\\')
                        elif next_c == '"': string_value.append('"')
                        elif next_c == "'": string_value.append("'")
                        else:
                            string_value.append('\\')
                            string_value.append(next_c)
                    elif c == '\n':
                        string_value.append('\n')
                    else:
                        string_value.append(c)
                    self.advance()
                if self.pos >= len(self.text):
                    current_line_text = self.text.split('\n')[self.line - 1] if self.line <= len(self.text.split('\n')) else ""
                    raise FMS_Error(message="Unterminated string", line=start_line, col=start_col, error_type="Syntax Error", source_line=current_line_text)
                final_string = ''.join(string_value)
                self.tokens.append(Token('STRING', final_string, start_line, start_col))
                self.advance()
                continue

            # Numbers
            if char.isdigit() or (char == '.' and self.peek().isdigit()):
                start_line, start_col = self.line, self.col
                start = self.pos
                while self.pos < len(self.text):
                    c = self.text[self.pos]
                    if c.isdigit(): self.advance()
                    elif c == '.':
                        if self.peek() == '.': break
                        if '.' in self.text[start:self.pos]: break
                        self.advance()
                    else: break
                val_str = self.text[start:self.pos]
                self.tokens.append(Token('NUMBER', float(val_str) if '.' in val_str else int(val_str), start_line, start_col))
                continue

            # DotDot
            if char == '.' and self.peek() == '.':
                self.tokens.append(Token('DOTDOT', '..', self.line, self.col))
                self.advance()
                self.advance()
                continue

            # Identifiers & Keywords
            if char.isalpha() or char == '_':
                start_line, start_col = self.line, self.col
                start = self.pos
                while self.pos < len(self.text) and (self.text[self.pos].isalnum() or self.text[self.pos] == '_'):
                    self.advance()
                word = self.text[start:self.pos]
                upper_word = word.upper()
                if upper_word in self.keywords:
                    self.tokens.append(Token(upper_word, word, start_line, start_col))
                else:
                    self.tokens.append(Token('IDENT', word, start_line, start_col))
                continue

            # --- NEW: Assignment (=) vs Equality (==) ---
            if char == '=':
                if self.peek() == '=':
                    self.tokens.append(Token('EQ', '==', self.line, self.col))
                    self.advance()
                    self.advance()
                else:
                    self.tokens.append(Token('ASSIGN', '=', self.line, self.col))
                    self.advance()
                continue

            # Standard Operators
            if char == '!' and self.peek() == '=':
                self.tokens.append(Token('NEQ', '!=', self.line, self.col)); self.advance(); self.advance(); continue
            if char == '<' and self.peek() == '=':
                self.tokens.append(Token('LTE', '<=', self.line, self.col)); self.advance(); self.advance(); continue
            if char == '>' and self.peek() == '=':
                self.tokens.append(Token('GTE', '>=', self.line, self.col)); self.advance(); self.advance(); continue
                
            # REMOVED: AMP (&) operator to force use of '+' for concatenation
            # if char == '&':
            #     self.tokens.append(Token('AMP', '&', self.line, self.col)); self.advance(); continue

            # Catch-all for single characters (includes { and })
            if char in r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""":
                self.tokens.append(Token(char, char, self.line, self.col))
                self.advance()
                continue

            current_line_text = self.text.split('\n')[self.line - 1] if self.line <= len(self.text.split('\n')) else ""
            raise FMS_Error(message=f"Unexpected character '{char}'", line=self.line, col=self.col, error_type="Syntax Error", source_line=current_line_text)

        self.tokens.append(Token('EOF', None, self.line, self.col))