import ast
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

@dataclass
class ParsedEntity:
    entity_type: str  # function, class, method
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent_name: Optional[str] = None

@dataclass
class ParsedDependency:
    source_name: str  # file relative path or entity qualified name
    target_name: str  # imported module, called function, inherited class
    relation_type: str  # imports, calls, inherits, references
    line_number: int

@dataclass
class FileParseResult:
    relative_path: str
    language: str
    entities: List[ParsedEntity] = field(default_factory=list)
    dependencies: List[ParsedDependency] = field(default_factory=list)
    syntax_valid: bool = True
    error_message: Optional[str] = None

class PythonASTParser:
    def __init__(self, relative_path: str, content: str):
        self.relative_path = relative_path
        self.content = content
        self.lines = content.splitlines()
        # Compute module path from relative path: e.g. "auth/service.py" -> "auth.service"
        clean_path = relative_path.replace("\\\\", "/")
        if clean_path.endswith(".py"):
            clean_path = clean_path[:-3]
        if clean_path.endswith("/__init__"):
            clean_path = clean_path[:-9]
        self.module_name = clean_path.replace("/", ".")

    def get_signature_from_node(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        try:
            arg_names = []
            for arg in node.args.args:
                arg_str = arg.arg
                if arg.annotation:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                arg_names.append(arg_str)
            returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
            return f"{prefix}{node.name}({', '.join(arg_names)}){returns}"
        except Exception:
            return f"def {node.name}(...)"

    def get_call_name(self, call_node: ast.Call) -> Optional[str]:
        func = call_node.func
        if isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Attribute):
            val = func.value
            if isinstance(val, ast.Name):
                return f"{val.id}.{func.attr}"
            return func.attr
        return None

    def parse(self) -> FileParseResult:
        result = FileParseResult(relative_path=self.relative_path, language="python")
        try:
            tree = ast.parse(self.content, filename=self.relative_path)
        except SyntaxError as e:
            result.syntax_valid = False
            result.error_message = f"SyntaxError at line {e.lineno}: {e.msg}"
            logger.warning("Python syntax error in %s: %s", self.relative_path, result.error_message)
            return result

        # 1. Module-level imports
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result.dependencies.append(ParsedDependency(
                        source_name=self.relative_path,
                        target_name=alias.name,
                        relation_type="imports",
                        line_number=node.lineno
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                # Handle relative imports: node.level
                for alias in node.names:
                    target = f"{module}.{alias.name}" if module else alias.name
                    result.dependencies.append(ParsedDependency(
                        source_name=self.relative_path,
                        target_name=target,
                        relation_type="imports",
                        line_number=node.lineno
                    ))

        # 2. Extract Classes and Functions
        class EntityVisitor(ast.NodeVisitor):
            def __init__(self, parser: 'PythonASTParser', result: FileParseResult):
                self.parser = parser
                self.result = result
                self.current_class: Optional[str] = None

            def visit_ClassDef(self, node: ast.ClassDef):
                qname = f"{self.parser.module_name}.{node.name}"
                doc = ast.get_docstring(node)
                self.result.entities.append(ParsedEntity(
                    entity_type="class",
                    name=node.name,
                    qualified_name=qname,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=f"class {node.name}",
                    docstring=doc,
                    parent_name=None
                ))

                # Inheritance dependencies
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        self.result.dependencies.append(ParsedDependency(
                            source_name=qname,
                            target_name=base.id,
                            relation_type="inherits",
                            line_number=node.lineno
                        ))
                    elif isinstance(base, ast.Attribute):
                        self.result.dependencies.append(ParsedDependency(
                            source_name=qname,
                            target_name=ast.unparse(base),
                            relation_type="inherits",
                            line_number=node.lineno
                        ))

                prev_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = prev_class

            def visit_FunctionDef(self, node: ast.FunctionDef):
                self._handle_func(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                self._handle_func(node)

            def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
                is_method = self.current_class is not None
                entity_type = "method" if is_method else "function"
                if is_method:
                    qname = f"{self.parser.module_name}.{self.current_class}.{node.name}"
                    parent = self.current_class
                else:
                    qname = f"{self.parser.module_name}.{node.name}"
                    parent = None

                sig = self.parser.get_signature_from_node(node)
                doc = ast.get_docstring(node)

                self.result.entities.append(ParsedEntity(
                    entity_type=entity_type,
                    name=node.name,
                    qualified_name=qname,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=sig,
                    docstring=doc,
                    parent_name=parent
                ))

                # Extract calls inside this function
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_name = self.parser.get_call_name(child)
                        if call_name:
                            self.result.dependencies.append(ParsedDependency(
                                source_name=qname,
                                target_name=call_name,
                                relation_type="calls",
                                line_number=child.lineno
                            ))

                # Visit inner definitions
                self.generic_visit(node)

        visitor = EntityVisitor(self, result)
        visitor.visit(tree)

        return result

class JavaScriptParser:
    """Enhanced parser for JS/TS extracting imports, classes, functions, route handlers, and calls."""
    def __init__(self, relative_path: str, content: str):
        self.relative_path = relative_path
        self.content = content
        clean_path = relative_path.replace("\\\\", "/")
        for ext in (".js", ".jsx", ".ts", ".tsx"):
            if clean_path.endswith(ext):
                clean_path = clean_path[:-len(ext)]
                break
        self.module_name = clean_path.replace("/", ".")

    def _find_matching_brace(self, lines: List[str], start_idx: int) -> int:
        """Finds the ending line of a block by counting braces."""
        open_braces = 0
        found_first = False
        for i in range(start_idx, min(len(lines), start_idx + 400)):
            line = lines[i]
            clean = re.sub(r'//.*', '', line)
            clean = re.sub(r'/\*.*?\*/', '', clean)
            for ch in clean:
                if ch == '{':
                    open_braces += 1
                    found_first = True
                elif ch == '}':
                    open_braces -= 1
                    if found_first and open_braces <= 0:
                        return i + 1
        return start_idx + 1

    def parse(self) -> FileParseResult:
        result = FileParseResult(relative_path=self.relative_path, language="javascript")
        lines = self.content.splitlines()

        # 1. Imports
        import_pattern = re.compile(r'''import\s+(?:(?:\*\s+as\s+\w+)|(?:\{[^}]+\})|(?:[\w\s,]+))\s+from\s+['"]([^'"]+)['"]''')
        require_pattern = re.compile(r'''(?:const|let|var)\s+[\w\s{},:]+\s*=\s*require\s*\(\s*['"]([^'"]+)['"]\s*\)''')

        for i, line in enumerate(lines, start=1):
            for m in import_pattern.finditer(line):
                result.dependencies.append(ParsedDependency(
                    source_name=self.relative_path,
                    target_name=m.group(1),
                    relation_type="imports",
                    line_number=i
                ))
            for m_req in require_pattern.finditer(line):
                result.dependencies.append(ParsedDependency(
                    source_name=self.relative_path,
                    target_name=m_req.group(1),
                    relation_type="imports",
                    line_number=i
                ))

        # 2. Classes & Functions
        class_pattern = re.compile(r'class\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$.]+))?\s*\{?')
        func_pattern = re.compile(r'(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)')
        assigned_func_pattern = re.compile(r'(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:function\s*\(([^)]*)\)|\(([^)]*)\)\s*=>)')
        exports_func_pattern = re.compile(r'(?:exports|module\.exports)\.([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:function\s*\(([^)]*)\)|\(([^)]*)\)\s*=>)')
        route_pattern = re.compile(r'''(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]''')

        js_keywords = {'if', 'for', 'while', 'switch', 'catch', 'function', 'return', 'require', 'import', 'super', 'typeof', 'delete', 'void', 'new'}
        call_pattern = re.compile(r'\b([A-Za-z0-9_$]+(?:\.[A-Za-z0-9_$]+)?)\s*\(')

        for i, line in enumerate(lines, start=1):
            # Class match
            c_match = class_pattern.search(line)
            if c_match:
                c_name = c_match.group(1)
                inherits = c_match.group(2)
                qname = f"{self.module_name}.{c_name}"
                end_l = self._find_matching_brace(lines, i - 1)
                result.entities.append(ParsedEntity(
                    entity_type="class",
                    name=c_name,
                    qualified_name=qname,
                    start_line=i,
                    end_line=end_l,
                    signature=f"class {c_name}",
                    docstring=None
                ))
                if inherits:
                    result.dependencies.append(ParsedDependency(
                        source_name=qname,
                        target_name=inherits,
                        relation_type="inherits",
                        line_number=i
                    ))
                continue

            # Route match: app.post('/api/signup', ...)
            r_match = route_pattern.search(line)
            if r_match:
                method = r_match.group(1).upper()
                route_path = r_match.group(2)
                route_name = f"{method} {route_path}"
                qname = f"{self.module_name}.[{route_name}]"
                end_l = self._find_matching_brace(lines, i - 1)
                result.entities.append(ParsedEntity(
                    entity_type="route_handler",
                    name=route_name,
                    qualified_name=qname,
                    start_line=i,
                    end_line=end_l,
                    signature=f"app.{r_match.group(1)}('{route_path}', ...)",
                    docstring=None
                ))
                continue

            # Function match
            f_match = func_pattern.search(line)
            if f_match:
                f_name = f_match.group(1)
                args = f_match.group(2).strip()
                qname = f"{self.module_name}.{f_name}"
                end_l = self._find_matching_brace(lines, i - 1)
                result.entities.append(ParsedEntity(
                    entity_type="function",
                    name=f_name,
                    qualified_name=qname,
                    start_line=i,
                    end_line=end_l,
                    signature=f"function {f_name}({args})",
                    docstring=None
                ))
                continue

            # Assigned function match: const foo = (...) => or const foo = function(...)
            a_match = assigned_func_pattern.search(line)
            if a_match:
                a_name = a_match.group(1)
                args = (a_match.group(2) or a_match.group(3) or "").strip()
                qname = f"{self.module_name}.{a_name}"
                end_l = self._find_matching_brace(lines, i - 1)
                result.entities.append(ParsedEntity(
                    entity_type="function",
                    name=a_name,
                    qualified_name=qname,
                    start_line=i,
                    end_line=end_l,
                    signature=f"const {a_name} = ({args}) =>",
                    docstring=None
                ))
                continue

            # Exports match: exports.foo = ...
            e_match = exports_func_pattern.search(line)
            if e_match:
                e_name = e_match.group(1)
                args = (e_match.group(2) or e_match.group(3) or "").strip()
                qname = f"{self.module_name}.{e_name}"
                end_l = self._find_matching_brace(lines, i - 1)
                result.entities.append(ParsedEntity(
                    entity_type="function",
                    name=e_name,
                    qualified_name=qname,
                    start_line=i,
                    end_line=end_l,
                    signature=f"exports.{e_name} = ({args}) =>",
                    docstring=None
                ))

        # 3. Extract Function Calls and associate with enclosing entity
        for i, line in enumerate(lines, start=1):
            for cm in call_pattern.finditer(line):
                target_call = cm.group(1)
                base_call = target_call.split('.')[0]
                if base_call in js_keywords or target_call in js_keywords:
                    continue

                # Find which entity encloses line i
                enclosing = None
                for ent in result.entities:
                    if ent.start_line <= i <= ent.end_line:
                        enclosing = ent.qualified_name
                        break

                source = enclosing if enclosing else self.relative_path
                result.dependencies.append(ParsedDependency(
                    source_name=source,
                    target_name=target_call,
                    relation_type="calls",
                    line_number=i
                ))

        return result

class CodeParser:
    @staticmethod
    def parse_file(relative_path: str, content: str, language: str) -> FileParseResult:
        if language == "python":
            parser = PythonASTParser(relative_path, content)
            return parser.parse()
        elif language in ("javascript", "typescript"):
            parser = JavaScriptParser(relative_path, content)
            return parser.parse()
        else:
            return FileParseResult(relative_path=relative_path, language=language)

