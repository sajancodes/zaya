"""Zaya — created by Sajan Rai — static analysis of the Zaya source tree.

A self-contained, read-only analyzer that answers the questions an owner
actually asks about a project folder: how big is it, how is it shaped, what
does it depend on, which files carry the risk, and is the interpreter on this
machine able to run it at all.

It uses only the Python standard library, and only open-source tooling that
ships with CPython:

  * ``ast``       — real syntax tree, so every count below is measured, not
                    estimated by counting lines that start with a keyword.
  * ``tokenize``  — exact comment and string-token positions.
  * ``importlib`` — the installed distribution metadata used to check
                    requirements.txt against this interpreter.

Nothing here imports the Zaya application, opens a socket, writes to the
project tree, or reads anything other than source code and metadata files.
The only writes are the report files this script is asked to produce.

Python compatibility
--------------------
This file is deliberately written to run on Python 3.3 and newer: no f-strings,
no pathlib, no ``os.scandir``, no variable annotations, no ``dataclasses``.
Everything newer than 3.3 is either avoided or guarded at the import site.
``check_python_compatibility()`` re-checks that claim from the outside, and the
``--self-check`` flag runs it against this very file.

Usage
-----
    python tools/analyze_codebase.py
    python tools/analyze_codebase.py --root C:\\path\\to\\project --out docs/generated
    python tools/analyze_codebase.py --json-only
    python tools/analyze_codebase.py --strict      # non-zero exit on findings

Created and developed by Sajan Rai for Zaya.
"""

from __future__ import print_function

import argparse
import ast
import io
import json
import os
import platform
import re
import sys
import time
import tokenize
import warnings

# ── Configuration ─────────────────────────────────────────────────────────────

#: The floor this tool promises to run on.
MIN_PYTHON = (3, 3)

#: Directories that hold build output, caches or vendored code. Skipping them
#: keeps the numbers about *the project* rather than about Gradle.
SKIP_DIRECTORIES = frozenset([
    '.git', '.hg', '.svn',
    '.venv', 'venv', 'env', 'ENV', 'site-packages',
    '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache',
    '.benchmarks', '.tox', '.gradle', '.idea', '.vscode',
    'node_modules', 'build', 'dist',
    'logs', 'downloads', 'screenshots',
])

#: Test folders. The owner asked for the product code, not the regression
#: suite, so these are excluded from the analysis scope by default. Pass
#: ``--include-tests`` to bring them back in.
TEST_DIRECTORIES = frozenset([
    'tests', 'test', 'testing', '__tests__', 'androidTest',
])

#: File names that identify a test even when they sit outside a test folder.
TEST_FILE_PATTERNS = (
    re.compile(r'^test_[^/]*\.py$'),
    re.compile(r'.*_test\.py$'),
    re.compile(r'.*_tests\.py$'),
    re.compile(r'^conftest\.py$'),
    re.compile(r'.*_test\.kt$'),
    re.compile(r'.*Tests?\.kt$'),
    re.compile(r'.*Test\.java$'),
)

#: Extensions whose contents are read for line metrics. Deliberately excludes
#: .json/.xml/.yml/.md/.txt: those hold settings and notes, not code, and the
#: report never needs their contents.
CODE_EXTENSIONS = frozenset([
    '.py', '.kt', '.java', '.js', '.jsx', '.ts', '.tsx',
    '.sh', '.ps1', '.cmd', '.bat', '.c', '.h', '.cpp', '.hpp', '.cs',
])

#: Files above this size are counted but not parsed (they are generated blobs).
MAX_PARSE_BYTES = 4 * 1024 * 1024

#: Where a declared distribution is actually imported from.
DISTRIBUTION_IMPORTS = {
    'beautifulsoup4': ['bs4'],
    'pillow': ['PIL'],
    'opencv-python': ['cv2'],
    'google-genai': ['google.genai', 'genai'],
    'google-api-python-client': ['googleapiclient'],
    'google-auth-oauthlib': ['google_auth_oauthlib'],
    'numpy': ['numpy'],
    'requests': ['requests'],
    'playwright': ['playwright'],
    'sounddevice': ['sounddevice'],
    'webrtcvad-wheels': ['webrtcvad'],
    'yt-dlp': ['yt_dlp'],
    'pyautogui': ['pyautogui'],
    'pyperclip': ['pyperclip'],
    'mss': ['mss'],
    'psutil': ['psutil'],
    'send2trash': ['send2trash'],
    'python-pptx': ['pptx'],
    'reportlab': ['reportlab'],
    'fastapi': ['fastapi'],
    'uvicorn': ['uvicorn'],
    'cryptography': ['cryptography'],
    'python-multipart': ['multipart'],
    'qrcode': ['qrcode'],
    'comtypes': ['comtypes'],
    'pycaw': ['pycaw'],
    'win10toast': ['win10toast'],
    'pywin32': ['win32api', 'win32con', 'win32gui', 'win32com', 'win32service',
                'win32event', 'pythoncom', 'winerror', 'winshell'],
    'wmi': ['wmi'],
    'pywinauto': ['pywinauto'],
    'ddgs': ['ddgs', 'duckduckgo_search'],
    'pdfplumber': ['pdfplumber'],
    'PyPDF2': ['PyPDF2'],
    'python-docx': ['docx'],
    'pynvml': ['pynvml', 'nvidia_ml_py'],
    'tinytuya': ['tinytuya'],
    'paho-mqtt': ['paho'],
    'openpyxl': ['openpyxl'],
    'youtube-transcript-api': ['youtube_transcript_api'],
    'pygetwindow': ['pygetwindow'],
    'PyQt6': ['PyQt6'],
}

#: Thresholds used to raise a finding. Documented in the generated report.
LONG_FUNCTION_LINES = 80
HIGH_COMPLEXITY = 12
DEEP_NESTING = 4
LONG_LINE = 120

#: Node types that add one decision point to a function's complexity.
DECISION_NODES = frozenset([
    'If', 'IfExp', 'For', 'AsyncFor', 'While', 'ExceptHandler',
    'With', 'AsyncWith', 'Assert',
])

#: Node types that increase nesting depth.
NESTING_NODES = frozenset([
    'If', 'For', 'AsyncFor', 'While', 'With', 'AsyncWith', 'Try', 'Match',
])


# ── Small helpers ─────────────────────────────────────────────────────────────

def format_bytes(size):
    """Human readable byte count."""
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024.0 or unit == 'GB':
            if unit == 'B':
                return '%d B' % int(value)
            return '%.1f %s' % (value, unit)
        value /= 1024.0
    return '%d B' % int(size)


def median(values):
    """Median without the statistics module (which is newer than 3.3)."""
    if not values:
        return 0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def percentile(values, fraction):
    """Nearest-rank percentile."""
    if not values:
        return 0
    ordered = sorted(values)
    index = int(round(fraction * (len(ordered) - 1)))
    return ordered[max(0, min(index, len(ordered) - 1))]


def read_text(path):
    """Read a text file, replacing undecodable bytes instead of failing."""
    handle = io.open(path, 'r', encoding='utf-8', errors='replace')
    try:
        return handle.read()
    finally:
        handle.close()


def relative_path(path, root):
    """Path relative to the project root, using forward slashes."""
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        rel = path
    return rel.replace('\\', '/')


def node_end_line(node):
    """Last line of a node, falling back to its first line before Python 3.8."""
    end = getattr(node, 'end_lineno', None)
    if end:
        return end
    return getattr(node, 'lineno', 0)


def is_function_node(node):
    """True for def and async def, on any supported interpreter."""
    return type(node).__name__ in ('FunctionDef', 'AsyncFunctionDef')


def is_class_node(node):
    """True for class definitions."""
    return isinstance(node, ast.ClassDef)


def scope_map(tree):
    """Map every function/class node to the class that holds it.

    A function is a method when it sits directly in a class body. A function
    nested inside another function is not a method, so entering a function
    clears the class scope.
    """
    owners = {}

    def visit(node, scope):
        for child in ast.iter_child_nodes(node):
            name = type(child).__name__
            if name in ('FunctionDef', 'AsyncFunctionDef'):
                owners[id(child)] = scope[-1] if scope else ''
                visit(child, [])
            elif name == 'ClassDef':
                owners[id(child)] = scope[-1] if scope else ''
                visit(child, scope + [child.name])
            else:
                visit(child, scope)

    visit(tree, [])
    return owners


def base_class_name(base):
    """Readable name of a base class."""
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return type(base).__name__


# ── Python source analysis ───────────────────────────────────────────────────

def _comment_line_numbers(source, lines):
    """Line numbers carrying a comment token."""
    found = set()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            reader = io.StringIO(source).readline
            for token in tokenize.generate_tokens(reader):
                if token.type == tokenize.COMMENT:
                    found.add(token.start[0])
    except Exception:
        # A file that does not tokenize cleanly still gets its comment lines
        # counted by the cheap prefix rule, so the totals stay useful.
        for number, text in enumerate(lines, 1):
            if text.strip().startswith('#'):
                found.add(number)
    return found


def _decision_points(node):
    """Complexity contribution of a single statement node."""
    name = type(node).__name__
    if name in DECISION_NODES:
        return 1
    return 0


def _expression_points(node):
    """Complexity contribution of an expression tree.

    Conditional expressions, boolean operators and comprehension filters are
    decisions too, and they live in expressions rather than in statements.
    Statements are skipped here: they are walked separately so nothing is
    counted twice.
    """
    total = 0
    name = type(node).__name__
    if name == 'IfExp':
        total += 1
    elif name == 'BoolOp':
        total += max(0, len(node.values) - 1)
    elif name == 'comprehension':
        total += len(node.ifs)
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.stmt) or isinstance(child, ast.excepthandler):
            continue
        total += _expression_points(child)
    return total


def _walk_block(statements, depth):
    """Return (complexity added, deepest nesting) for a block of statements.

    Nested function and class bodies are skipped: they are measured on their
    own and must not inflate the complexity of the function that holds them.
    """
    complexity = 0
    deepest = depth

    for statement in statements:
        complexity += _decision_points(statement)
        name = type(statement).__name__

        if name in ('FunctionDef', 'AsyncFunctionDef', 'ClassDef'):
            # Measured separately, as its own function or class.
            continue

        # Decisions that live in the expressions of this statement.
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.stmt) or isinstance(child, ast.excepthandler):
                continue
            complexity += _expression_points(child)

        child_depth = depth + 1 if name in NESTING_NODES else depth

        # The main suite of the statement.
        block = getattr(statement, 'body', None)
        if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
            sub_complexity, sub_depth = _walk_block(block, child_depth)
            complexity += sub_complexity
            deepest = max(deepest, sub_depth)

        # `else` and `finally` suites sit at the same level as the main suite.
        for attribute in ('orelse', 'finalbody'):
            block = getattr(statement, attribute, None)
            if not isinstance(block, list) or not block:
                continue
            if not isinstance(block[0], ast.stmt):
                continue
            if name == 'If' and attribute == 'orelse' and \
                    len(block) == 1 and isinstance(block[0], ast.If):
                # An `elif` continues the `if` it follows; it is the same
                # level of nesting, not one deeper.
                sub_complexity, sub_depth = _walk_block(block, depth)
            else:
                sub_complexity, sub_depth = _walk_block(block, child_depth)
            complexity += sub_complexity
            deepest = max(deepest, sub_depth)

        # `except` handlers each add a decision of their own.
        for handler in getattr(statement, 'handlers', None) or []:
            complexity += 1
            sub_complexity, sub_depth = _walk_block(handler.body, child_depth)
            complexity += sub_complexity
            deepest = max(deepest, sub_depth)

    return complexity, deepest


def guarded_imports(tree):
    """Names imported inside a try/except block.

    The Zaya plugins import their optional extras inside a try/except so an
    uninstalled extra disables exactly one plugin. An import that is guarded
    is therefore a deliberate choice, not a broken dependency.
    """
    guarded = set()
    for node in ast.walk(tree):
        if type(node).__name__ not in ('Try', 'TryStar'):
            continue
        for statement in node.body:
            for child in ast.walk(statement):
                if isinstance(child, ast.Import):
                    for alias in child.names:
                        guarded.add(alias.asname or alias.name.split('.')[0])
                elif isinstance(child, ast.ImportFrom):
                    for alias in child.names:
                        guarded.add(alias.asname or alias.name)
    return guarded


def _unused_imports(tree, source):
    """Imported names that never appear again in the file."""
    imported = []
    star = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == '*':
                    star = True
                    continue
                bound = alias.asname or alias.name.split('.')[0]
                imported.append((bound, alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == '*':
                    star = True
                    continue
                bound = alias.asname or alias.name
                imported.append((bound, '%s.%s' % (node.module or '', alias.name),
                                 node.lineno))

    if star or not imported:
        return [], star

    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            base = node
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                used.add(base.id)

    unused = []
    for bound, full, line in imported:
        if bound not in used:
            unused.append({'name': bound, 'module': full, 'line': line})
    return unused, star


def _mutable_defaults(node):
    """Function arguments that default to a mutable object."""
    found = []
    arguments = node.args
    groups = [
        list(getattr(arguments, 'defaults', []) or []),
        list(getattr(arguments, 'kw_defaults', []) or []) if hasattr(arguments, 'kw_defaults') else [],
    ]
    for index, group in enumerate(groups):
        for default in group:
            if default is None:
                continue
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                found.append({'line': getattr(default, 'lineno', node.lineno),
                              'kind': 'mutable default'})
            elif isinstance(default, ast.Call):
                name = getattr(default.func, 'id', None)
                if name == 'dict':
                    found.append({'line': getattr(default, 'lineno', node.lineno),
                                  'kind': 'mutable default'})
                elif name == 'list':
                    found.append({'line': getattr(default, 'lineno', node.lineno),
                                  'kind': 'mutable default'})
    return found


def check_python_compatibility(source, filename='<string>',
                               minimum=MIN_PYTHON):
    """Check that a source file only uses syntax available in ``minimum``.

    Three independent checks are combined:

    1. ``ast.parse(feature_version=minimum)`` rejects keywords, operators and
       statements that did not exist in that version (await/async, ``:=``,
       ``match``, positional-only parameters).
    2. The tokenizer is asked for every string literal, because an f-string is
       a syntax error before Python 3.6 but the parser happily accepts one on
       a modern interpreter — the tokenizer is the only place that difference
       shows.
    3. A scan for names that only exist in newer standard libraries is not
       attempted: those are runtime concerns, handled by guarded imports in
       the analyzer itself.
    """
    problems = []
    features = {'feature_version': None, 'fstring': False,
                'minimum': '%d.%d' % minimum}

    try:
        ast.parse(source, filename=filename, feature_version=minimum)
        features['feature_version'] = 'ok'
    except SyntaxError as exc:
        features['feature_version'] = 'error'
        problems.append('syntax not valid on Python %d.%d (line %s): %s'
                        % (minimum[0], minimum[1], exc.lineno, exc.msg))
    except ValueError:
        # Older interpreters do not know feature_version; the tokenizer check
        # below still applies.
        features['feature_version'] = 'unsupported'

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            reader = io.StringIO(source).readline
            for token in tokenize.generate_tokens(reader):
                if token.type == tokenize.STRING:
                    prefix = token.string[:token.string.index(token.string.lstrip('bBuUrRfF')[0])] \
                        if token.string.lstrip('bBuUrRfF') else ''
                    if 'f' in prefix.lower():
                        features['fstring'] = True
                        problems.append('f-string on line %s needs Python 3.6+'
                                        % token.start[0])
                        break
    except Exception:
        pass

    return {'compatible': not problems, 'problems': problems,
            'features': features}


def analyze_python_source(source, filename='<string>', project_minimum=None):
    """Full metric set for one Python source file."""
    result = {
        'filename': filename,
        'syntax_ok': False,
        'error': None,
        'total_lines': 0,
        'blank_lines': 0,
        'comment_lines': 0,
        'docstring_lines': 0,
        'code_lines': 0,
        'classes': 0,
        'functions': 0,
        'methods': 0,
        'max_line_length': 0,
        'long_lines': 0,
        'imports': [],
        'function_details': [],
        'class_details': [],
        'definitions': [],
        'unused_imports': [],
        'star_imports': [],
        'mutable_defaults': [],
        'bare_excepts': [],
        'todo_count': 0,
        'compat': None,
        'project_compat': None,
    }

    lines = source.splitlines()
    result['total_lines'] = len(lines)
    result['blank_lines'] = sum(1 for text in lines if not text.strip())
    longest = 0
    long_lines = 0
    for text in lines:
        length = len(text.rstrip('\n'))
        if length > longest:
            longest = length
        if length > LONG_LINE:
            long_lines += 1
    result['max_line_length'] = longest
    result['long_lines'] = long_lines

    todo_pattern = re.compile(r'\b(TODO|FIXME|HACK|XXX|BUG)\b')
    result['todo_count'] = sum(
        1 for text in lines if todo_pattern.search(text))

    try:
        tree = ast.parse(source, filename=filename)
        result['syntax_ok'] = True
    except SyntaxError as exc:
        result['error'] = 'line %s: %s' % (exc.lineno, exc.msg)
        comment_lines = _comment_line_numbers(source, lines)
        result['comment_lines'] = len(comment_lines)
        result['code_lines'] = (result['total_lines']
                                - result['blank_lines']
                                - result['comment_lines'])
        result['compat'] = check_python_compatibility(source, filename)
        if project_minimum:
            result['project_compat'] = check_python_compatibility(
                source, filename, project_minimum)
        return result

    comment_lines = _comment_line_numbers(source, lines)
    result['comment_lines'] = len(comment_lines)

    docstring_lines = 0
    docstring_nodes = [tree]
    for node in ast.walk(tree):
        if is_function_node(node) or is_class_node(node):
            docstring_nodes.append(node)
    for node in docstring_nodes:
        body = getattr(node, 'body', None)
        if not body:
            continue
        first = body[0]
        if not isinstance(first, ast.Expr):
            continue
        if not isinstance(getattr(first, 'value', None), str):
            continue
        start = getattr(first, 'lineno', 0)
        end = node_end_line(first)
        docstring_lines += max(1, end - start + 1)
    result['docstring_lines'] = docstring_lines

    result['code_lines'] = (result['total_lines']
                            - result['blank_lines']
                            - result['comment_lines'])

    imported_modules = []
    guarded = guarded_imports(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append({'module': alias.name,
                                         'line': node.lineno,
                                         'asname': alias.asname,
                                         'guarded': alias.asname
                                         or alias.name.split('.')[0] in guarded})
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                imported_modules.append({
                    'module': '%s.%s' % (module, alias.name) if module else alias.name,
                    'line': node.lineno,
                    'asname': alias.asname,
                    'from_module': module,
                    'guarded': alias.asname or alias.name in guarded,
                })
    result['imports'] = imported_modules

    unused, star = _unused_imports(tree, source)
    result['unused_imports'] = unused
    result['star_imports'] = star

    owners = scope_map(tree)
    for node in ast.walk(tree):
        if is_function_node(node):
            complexity, depth = _walk_block(node.body, 0)
            length = node_end_line(node) - node.lineno + 1
            owner = owners.get(id(node), '')
            is_method = bool(owner)
            result['functions'] += 1
            if is_method:
                result['methods'] += 1
            detail = {
                'name': node.name,
                'line': node.lineno,
                'length': length,
                'complexity': 1 + complexity,
                'nesting': depth,
                'arguments': len(node.args.args) + len(node.args.kwonlyargs),
                'is_method': is_method,
                'class': owner,
            }
            result['function_details'].append(detail)
            result['definitions'].append({
                'name': node.name,
                'kind': 'method' if is_method else 'function',
                'line': node.lineno,
                'owner': owner,
            })
            for bad in _mutable_defaults(node):
                bad['name'] = node.name
                result['mutable_defaults'].append(bad)
        elif is_class_node(node):
            result['classes'] += 1
            result['class_details'].append({
                'name': node.name,
                'line': node.lineno,
                'bases': [base_class_name(base) for base in node.bases],
            })
            result['definitions'].append({
                'name': node.name,
                'kind': 'class',
                'line': node.lineno,
                'owner': '',
            })
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            result['bare_excepts'].append({'line': node.lineno})

    result['compat'] = check_python_compatibility(source, filename)
    if project_minimum:
        result['project_compat'] = check_python_compatibility(
            source, filename, project_minimum)
    return result


def analyze_text_source(source, filename='<string>'):
    """Line metrics for a non-Python source file."""
    lines = source.splitlines()
    blank = sum(1 for text in lines if not text.strip())
    comment = 0
    for text in lines:
        stripped = text.strip()
        if stripped.startswith('//') or stripped.startswith('#') or stripped.startswith('*'):
            comment += 1
    longest = 0
    long_lines = 0
    for text in lines:
        length = len(text.rstrip())
        if length > longest:
            longest = length
        if length > LONG_LINE:
            long_lines += 1
    return {
        'filename': filename,
        'total_lines': len(lines),
        'blank_lines': blank,
        'comment_lines': comment,
        'code_lines': len(lines) - blank - comment,
        'max_line_length': longest,
        'long_lines': long_lines,
    }


# ── Filesystem scan ──────────────────────────────────────────────────────────

def is_test_file(name):
    """True when a file name marks it as a test file."""
    for pattern in TEST_FILE_PATTERNS:
        if pattern.match(name):
            return True
    return False


def count_files(directory):
    """How many files live under a directory."""
    total = 0
    for current, directories, names in os.walk(directory):
        total += len(names)
    return total


def iter_source_files(root, include_generated=False, include_tests=False,
                      excluded=None):
    """Walk the project and yield every file that should be analysed.

    Test folders and test files are skipped unless ``include_tests`` is set;
    each skip is recorded in ``excluded`` so the report can show exactly what
    was left out and why.
    """
    for current, directories, names in os.walk(root):
        if not include_generated:
            directories[:] = [name for name in directories
                               if name not in SKIP_DIRECTORIES]
        if not include_tests:
            kept = []
            for name in directories:
                if name in TEST_DIRECTORIES:
                    if excluded is not None:
                        skipped = os.path.join(current, name)
                        excluded.append({
                            'path': relative_path(skipped, root),
                            'kind': 'test directory',
                            'files': count_files(skipped),
                        })
                    continue
                kept.append(name)
            directories[:] = kept
        for name in sorted(names):
            path = os.path.join(current, name)
            if not include_tests and is_test_file(name):
                if excluded is not None:
                    excluded.append({
                        'path': relative_path(path, root),
                        'kind': 'test file',
                    })
                continue
            yield path


def scan_tree(root, include_generated=False, include_tests=False,
              excluded=None):
    """Collect the structural picture of the project."""
    entries = []
    for path in iter_source_files(root, include_generated, include_tests,
                                  excluded):
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        extension = os.path.splitext(path)[1].lower()
        entries.append({
            'path': path,
            'relative': relative_path(path, root),
            'extension': extension or '(none)',
            'size': size,
        })
    return entries


def directory_map(root, include_generated=False, include_tests=False):
    """Per-directory file counts, for the permission and structure reports."""
    mapping = {}
    for path in iter_source_files(root, include_generated, include_tests):
        current = os.path.dirname(path)
        while True:
            if current not in mapping:
                mapping[current] = {'files': 0, 'bytes': 0}
            try:
                mapping[current]['files'] += 1
                mapping[current]['bytes'] += os.path.getsize(path)
            except OSError:
                pass
            parent = os.path.dirname(current)
            if parent == current or len(current) <= len(root):
                break
            current = parent
    return mapping


# ── Environment, permissions, dependencies ───────────────────────────────────

def python_runtime_info():
    """What interpreter is running, and can it run this tool."""
    version = sys.version_info
    return {
        'executable': sys.executable,
        'version': '%d.%d.%d' % (version[0], version[1], version[2]),
        'version_info': [version[0], version[1], version[2]],
        'meets_minimum': tuple(version[:2]) >= MIN_PYTHON,
        'minimum_required': '%d.%d' % MIN_PYTHON,
        'implementation': platform.python_implementation(),
        'platform': platform.platform(),
        'system': platform.system(),
        'prefix': sys.prefix,
        'cwd': os.getcwd(),
    }


def project_venv_info(root):
    """Is there a project-local virtual environment, and which Python is in it."""
    for relative in (os.path.join('.venv', 'Scripts', 'python.exe'),
                      os.path.join('.venv', 'bin', 'python')):
        candidate = os.path.join(root, relative)
        if os.path.exists(candidate):
            return {'path': candidate, 'relative': relative.replace('\\', '/')}
    return None


def setup_python_floor(root):
    """Read the app's own Python floor out of setup.py."""
    path = os.path.join(root, 'setup.py')
    if not os.path.exists(path):
        return None
    try:
        source = read_text(path)
    except OSError:
        return None
    minimum = re.search(r'MIN_PY\s*=\s*\((\d+),\s*(\d+)\)', source)
    maximum = re.search(r'MAX_PY\s*=\s*\((\d+),\s*(\d+)\)', source)
    floor = None
    ceiling = None
    if minimum:
        floor = (int(minimum.group(1)), int(minimum.group(2)))
    if maximum:
        ceiling = (int(maximum.group(1)), int(maximum.group(2)))
    return {'minimum': floor, 'maximum': ceiling}


def check_permissions(root, include_generated=False):
    """Confirm the project directory and its subfolders can be read."""
    result = {'root': root, 'directories': 0, 'files': 0, 'unreadable': [],
              'root_readable': False, 'root_executable': False}
    try:
        result['root_readable'] = os.access(root, os.R_OK)
        result['root_executable'] = os.access(root, os.X_OK)
    except OSError as exc:
        result['unreadable'].append({'path': root, 'reason': str(exc)})
        return result

    for current, directories, names in os.walk(root):
        if not include_generated:
            directories[:] = [name for name in directories
                               if name not in SKIP_DIRECTORIES]
        result['directories'] += 1
        readable = os.access(current, os.R_OK)
        traversable = os.access(current, os.X_OK)
        result['files'] += len(names)
        if not readable or not traversable:
            result['unreadable'].append({
                'path': relative_path(current, root),
                'reason': 'read=%s traverse=%s' % (readable, traversable),
            })

    # Prove it with a real read, not just the permission bits.
    probe = None
    for entry in sorted(os.listdir(root)):
        candidate = os.path.join(root, entry)
        if os.path.isfile(candidate):
            probe = candidate
            break
    if probe:
        try:
            with io.open(probe, 'rb') as handle:
                handle.read(1)
            result['probe'] = relative_path(probe, root)
            result['probe_ok'] = True
        except OSError as exc:
            result['probe'] = relative_path(probe, root)
            result['probe_ok'] = False
            result['unreadable'].append({'path': relative_path(probe, root),
                                         'reason': str(exc)})
    return result


def parse_requirements(path):
    """Parse requirements.txt into structured entries."""
    entries = []
    if not os.path.exists(path):
        return entries
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        # An inline comment ends the requirement: "pkg>=1  # why".
        comment = re.search(r'\s+#', line)
        if comment:
            line = line[:comment.start()].strip()
            if not line:
                continue
        if line.startswith('-') or line.startswith('http'):
            entries.append({'raw': line, 'name': line, 'specifier': '',
                            'marker': '', 'extras': '', 'editable': True})
            continue
        marker = ''
        if ';' in line:
            line, marker = line.split(';', 1)
            line = line.strip()
            marker = marker.strip()
        extras = ''
        match = re.match(r'^([A-Za-z0-9._-]+)\s*\[([^\]]*)\]', line)
        if match:
            name = match.group(1)
            extras = match.group(2)
            remainder = line[match.end():].strip()
        else:
            match = re.match(r'^([A-Za-z0-9._-]+)', line)
            if not match:
                continue
            name = match.group(1)
            remainder = line[match.end():].strip()
        entries.append({
            'raw': raw.strip(),
            'name': name,
            'specifier': remainder,
            'marker': marker,
            'extras': extras,
            'editable': False,
        })
    return entries


def _version_tuple(value):
    """Numeric tuple for a version string, for a dependency-free comparison."""
    numbers = []
    for chunk in re.split(r'[._\-+]', value):
        digits = re.match(r'^(\d+)', chunk)
        numbers.append(int(digits.group(1)) if digits else 0)
    return tuple(numbers) or (0,)


def _compare_versions(installed, required, operator):
    """Compare two version strings under one of the common operators."""
    left = _version_tuple(installed)
    right = _version_tuple(required)
    length = max(len(left), len(right))
    left = left + (0,) * (length - len(left))
    right = right + (0,) * (length - len(right))
    if operator == '>=':
        return left >= right
    if operator == '<=':
        return left <= right
    if operator == '>':
        return left > right
    if operator == '<':
        return left < right
    if operator == '==':
        return left == right
    if operator == '!=':
        return left != right
    return True


def specifier_satisfied(installed, specifier):
    """Does the installed version satisfy the declared specifier."""
    if not installed or not specifier:
        return True
    specifier = specifier.strip()
    if specifier.startswith('(') or specifier.startswith('['):
        return True
    for clause in specifier.split(','):
        clause = clause.strip()
        if not clause:
            continue
        match = re.match(r'^(>=|<=|==|!=|>|<)\s*(.+)$', clause)
        if not match:
            continue
        if not _compare_versions(installed, match.group(2).strip(), match.group(1)):
            return False
    return True


def installed_version(name):
    """Installed version of a distribution, or None."""
    try:
        from importlib import metadata
    except ImportError:  # Python < 3.8
        try:
            import importlib_metadata as metadata  # noqa: F401
        except ImportError:
            metadata = None
    if metadata is not None:
        try:
            return metadata.version(name)
        except Exception:
            try:
                return metadata.version(name.replace('_', '-'))
            except Exception:
                return None
    return None


def module_importable(name):
    """Can this interpreter import the given top-level module."""
    try:
        import importlib.util
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def stdlib_module_names():
    """Top-level standard library module names, on any supported interpreter."""
    names = getattr(sys, 'stdlib_module_names', None)
    if names:
        return set(names)
    # Python 3.3-3.9 have no such table; derive it from the stdlib folder.
    import os as _os
    try:
        import sysconfig
        stdlib = sysconfig.get_paths().get('stdlib', '')
        base = _os.path.dirname(_os.__file__)
        directory = stdlib or base
        found = set()
        for entry in _os.listdir(directory):
            if entry.endswith('.py'):
                found.add(entry[:-3])
            elif _os.path.isdir(_os.path.join(directory, entry)) and \
                    _os.path.exists(_os.path.join(directory, entry, '__init__.py')):
                found.add(entry)
        found.discard('__pycache__')
        return found
    except Exception:
        return set()


def local_module_names(root):
    """Modules that belong to this project rather than to the environment.

    A directory counts as a local package when it holds Python files, even
    without an ``__init__.py``: Python 3 treats it as a namespace package and
    ``from actions.browser_control import ...`` still resolves.
    """
    names = set()
    for entry in os.listdir(root):
        full = os.path.join(root, entry)
        if os.path.isdir(full):
            has_init = os.path.exists(os.path.join(full, '__init__.py'))
            has_code = False
            try:
                for item in os.listdir(full):
                    if item.endswith('.py'):
                        has_code = True
                        break
            except OSError:
                has_code = False
            if has_init or has_code:
                names.add(entry)
        elif entry.endswith('.py') and entry != 'setup.py':
            names.add(entry[:-3])
    return names


def check_dependencies(root, requirements, imported_modules,
                       guarded_modules=None):
    """Reconcile requirements.txt with the interpreter and the source tree."""
    guarded_modules = guarded_modules or set()
    declared = {}
    for entry in requirements:
        declared[entry['name'].lower().replace('_', '-')] = entry

    rows = []
    missing = []
    unsatisfied = []
    for entry in requirements:
        if entry.get('editable'):
            rows.append({'name': entry['name'], 'installed': 'n/a',
                         'specifier': '', 'status': 'skipped (not a package)'})
            continue
        version = installed_version(entry['name'])
        if version is None:
            version = installed_version(entry['name'].replace('-', '_'))
        status = 'installed'
        if version is None:
            status = 'MISSING'
            missing.append(entry['name'])
        elif not specifier_satisfied(version, entry['specifier']):
            status = 'version mismatch'
            unsatisfied.append({'name': entry['name'], 'installed': version,
                                'specifier': entry['specifier']})
        rows.append({
            'name': entry['name'],
            'installed': version or 'not installed',
            'specifier': entry['specifier'],
            'extras': entry.get('extras', ''),
            'marker': entry.get('marker', ''),
            'status': status,
        })

    # Which declared distributions does the source actually import?
    used = set()
    for module in imported_modules:
        used.add(module.lower())
    # The import names are matched case-insensitively. The used module names
    # are lower-cased but the table above spells them "PIL", "PyPDF2" and
    # "PyQt6", so a case-sensitive comparison reported every one of them as
    # both unused and undeclared.
    import_map = {}
    for distribution, candidates in DISTRIBUTION_IMPORTS.items():
        import_map.setdefault(distribution.lower().replace('_', '-'), [])
        for candidate in candidates:
            import_map[distribution.lower().replace('_', '-')].append(candidate.lower())
    declared_used = []
    declared_unused = []
    for key, entry in sorted(declared.items()):
        candidates = import_map.get(key, [])
        hit = False
        for candidate in candidates:
            for module in used:
                if module == candidate or module.startswith(candidate + '.'):
                    hit = True
                    break
            if hit:
                break
        if hit:
            declared_used.append(entry['name'])
        else:
            declared_unused.append(entry['name'])

    # Third-party imports with no matching declared distribution.
    stdlib = stdlib_module_names()
    local = local_module_names(root)
    roots = set()
    for module in used:
        roots.add(module.split('.')[0])
    undeclared = []
    for name in sorted(roots):
        if name in stdlib or name in local:
            continue
        covered = False
        for distribution in declared:
            for candidate in import_map.get(distribution, []):
                if name == candidate or name.startswith(candidate + '.'):
                    covered = True
                    break
            if covered:
                break
        if covered:
            continue
        undeclared.append({
            'module': name,
            'installed': module_importable(name),
            'guarded': name.lower() in guarded_modules,
        })

    return {
        'rows': rows,
        'missing': missing,
        'unsatisfied': unsatisfied,
        'declared_used': declared_used,
        'declared_unused': declared_unused,
        'undeclared_imports': undeclared,
    }


# ── Report assembly ──────────────────────────────────────────────────────────

def build_report(root, include_generated=False, include_tests=False):
    """Run every check and assemble one report dictionary."""
    root = os.path.abspath(root)
    started = time.time()

    runtime = python_runtime_info()
    floor = setup_python_floor(root)
    venv = project_venv_info(root)
    permissions = check_permissions(root, include_generated)

    excluded = []
    entries = scan_tree(root, include_generated, include_tests, excluded)
    requirements = parse_requirements(os.path.join(root, 'requirements.txt'))

    python_files = []
    other_files = []
    metrics = []
    imported_modules = []
    guarded_names = set()
    syntax_errors = []
    incompatible = []
    below_project_floor = []
    project_minimum = floor.get('minimum') if floor else None
    all_functions = []
    all_definitions = []
    unused_imports = []
    star_imports = []
    mutable_defaults = []
    bare_excepts = []
    todo_total = 0

    for entry in entries:
        extension = entry['extension']
        if extension == '.py':
            python_files.append(entry)
            if entry['size'] > MAX_PARSE_BYTES:
                continue
            try:
                source = read_text(entry['path'])
            except OSError as exc:
                syntax_errors.append({'file': entry['relative'],
                                      'error': str(exc)})
                continue
            result = analyze_python_source(source, entry['relative'],
                                           project_minimum)
            metrics.append(result)
            if not result['syntax_ok']:
                syntax_errors.append({'file': entry['relative'],
                                      'error': result['error']})
            compat = result.get('compat') or {}
            if compat and not compat.get('compatible', True):
                incompatible.append({'file': entry['relative'],
                                     'problems': compat.get('problems', [])})
            project_compat = result.get('project_compat') or {}
            if project_compat and not project_compat.get('compatible', True):
                below_project_floor.append({
                    'file': entry['relative'],
                    'problems': project_compat.get('problems', []),
                })
            for item in result['imports']:
                imported_modules.append(item['module'].split('.')[0]
                                        if item.get('from_module') is None
                                        else item['module'])
                if item.get('from_module'):
                    imported_modules.append(item['from_module'])
                if item.get('guarded'):
                    guarded_names.add(item['module'].split('.')[0].lower())
                    if item.get('from_module'):
                        guarded_names.add(item['from_module'].split('.')[0].lower())
            for detail in result['function_details']:
                item = dict(detail)
                item['file'] = entry['relative']
                all_functions.append(item)
            for definition in result['definitions']:
                item = dict(definition)
                item['file'] = entry['relative']
                all_definitions.append(item)
            for item in result['unused_imports']:
                record = dict(item)
                record['file'] = entry['relative']
                unused_imports.append(record)
            if result['star_imports']:
                star_imports.append(entry['relative'])
            for item in result['mutable_defaults']:
                record = dict(item)
                record['file'] = entry['relative']
                mutable_defaults.append(record)
            for item in result['bare_excepts']:
                record = dict(item)
                record['file'] = entry['relative']
                bare_excepts.append(record)
            todo_total += result['todo_count']
        elif extension in CODE_EXTENSIONS:
            other_files.append(entry)
            if entry['size'] > MAX_PARSE_BYTES:
                continue
            try:
                source = read_text(entry['path'])
            except OSError:
                continue
            result = analyze_text_source(source, entry['relative'])
            result['relative'] = entry['relative']
            result['size'] = entry['size']
            metrics.append(result)

    dependencies = check_dependencies(root, requirements, imported_modules,
                                      guarded_names)

    directories = directory_map(root, include_generated, include_tests)

    # Definitions nobody references anywhere in the tree.
    referenced = set()
    for entry in entries:
        if entry['extension'] in CODE_EXTENSIONS and \
                entry['size'] <= MAX_PARSE_BYTES:
            try:
                source = read_text(entry['path'])
            except OSError:
                continue
            for match in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', source):
                referenced.add(match.group(1))
    unreferenced = []
    for definition in all_definitions:
        if definition['name'].startswith('__'):
            continue
        if definition['name'] in referenced:
            continue
        unreferenced.append(definition)

    structure = summarize_structure(root, entries, directories)
    language = summarize_languages(metrics, entries)

    findings = collect_findings(metrics, syntax_errors, incompatible,
                                below_project_floor, all_functions,
                                unused_imports, mutable_defaults,
                                bare_excepts, dependencies, permissions,
                                todo_total, project_minimum)

    scope = summarize_scope(root, entries, excluded, include_tests)

    report = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'root': root,
        'tool': 'tools/analyze_codebase.py',
        'runtime': runtime,
        'project_python_floor': floor,
        'project_venv': venv,
        'permissions': permissions,
        'scope': scope,
        'structure': structure,
        'language': language,
        'metrics': metrics,
        'dependencies': dependencies,
        'requirements': requirements,
        'findings': findings,
        'functions': all_functions,
        'definitions': all_definitions,
        'unreferenced_definitions': unreferenced,
        'syntax_errors': syntax_errors,
        'python_compatibility_issues': incompatible,
        'below_project_floor': below_project_floor,
        'unused_imports': unused_imports,
        'star_imports': star_imports,
        'mutable_defaults': mutable_defaults,
        'bare_excepts': bare_excepts,
        'todo_count': todo_total,
        'elapsed_seconds': round(time.time() - started, 2),
    }
    return report


def summarize_structure(root, entries, directories):
    """Top-level layout, file types and per-directory counts."""
    top_level = []
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if os.path.isdir(full):
            record = directories.get(full, {'files': 0, 'bytes': 0})
            top_level.append({
                'name': entry,
                'kind': 'directory',
                'files': record['files'],
                'bytes': record['bytes'],
            })
        else:
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            top_level.append({'name': entry, 'kind': 'file',
                              'files': 1, 'bytes': size})

    by_extension = {}
    for entry in entries:
        bucket = by_extension.setdefault(entry['extension'], {
            'files': 0, 'bytes': 0})
        bucket['files'] += 1
        bucket['bytes'] += entry['size']

    return {
        'top_level': top_level,
        'by_extension': by_extension,
        'total_files': len(entries),
        'total_bytes': sum(entry['size'] for entry in entries),
    }


def summarize_scope(root, entries, excluded, include_tests):
    """Describe exactly what was analysed and what was left out.

    The owner asked for the product code and not the regression suite, so the
    report states which test folders and test files were skipped.
    """
    included_test_paths = []
    for entry in entries:
        relative = entry['relative']
        parts = relative.split('/')
        if any(part in TEST_DIRECTORIES for part in parts[:-1]):
            included_test_paths.append(relative)
        elif is_test_file(parts[-1]):
            included_test_paths.append(relative)

    test_directories = []
    test_files = []
    directory_files = 0
    for item in excluded:
        if item['kind'] == 'test directory':
            test_directories.append(item['path'])
            directory_files += item.get('files', 0)
        else:
            test_files.append(item['path'])

    return {
        'include_tests': include_tests,
        'analysed_files': len(entries),
        'excluded_paths': len(excluded),
        'excluded_files': directory_files + len(test_files),
        'excluded_test_directories': sorted(test_directories),
        'excluded_test_files': sorted(test_files),
        'test_paths_in_scope': sorted(included_test_paths),
        'test_directories': sorted(TEST_DIRECTORIES),
    }


def verify_scope(root, report):
    """Run the scope and environment checks the owner asked to verify.

    Returns a list of checks, each with a name, a pass/fail verdict and the
    evidence behind it.
    """
    scope = report['scope']
    runtime = report['runtime']
    permissions = report['permissions']
    dependencies = report['dependencies']

    checks = []

    checks.append({
        'name': 'Project directory exists',
        'ok': os.path.isdir(root),
        'detail': root,
    })

    checks.append({
        'name': 'Tests directory excluded from the analysis scope',
        'ok': not scope['include_tests']
        and not scope['test_paths_in_scope'],
        'detail': '%d test path(s) excluded (%d file(s) inside them), '
                  '%d test path(s) still in scope'
                  % (scope['excluded_paths'], scope['excluded_files'],
                     len(scope['test_paths_in_scope'])),
    })

    checks.append({
        'name': 'Test files excluded from the analysis scope',
        'ok': not scope['test_paths_in_scope'],
        'detail': '%d test file(s) skipped by name'
                  % len(scope['excluded_test_files']),
    })

    checks.append({
        'name': 'Product code included in the analysis scope',
        'ok': scope['analysed_files'] > 0,
        'detail': '%d file(s) analysed' % scope['analysed_files'],
    })

    checks.append({
        'name': 'Python %s or newer available'
                 % runtime['minimum_required'],
        'ok': runtime['meets_minimum'],
        'detail': 'running %s (%s)'
                  % (runtime['version'], runtime['implementation']),
    })

    checks.append({
        'name': 'Every requirement installed in this interpreter',
        'ok': not dependencies['missing'],
        'detail': ('%d requirement(s), %d missing'
                   % (len(dependencies['rows']), len(dependencies['missing']))),
    })

    checks.append({
        'name': 'Installed versions match requirements.txt',
        'ok': not dependencies['unsatisfied'],
        'detail': '%d version mismatch(es)' % len(dependencies['unsatisfied']),
    })

    checks.append({
        'name': 'Project directory and subfolders readable',
        'ok': permissions['root_readable'] and not permissions['unreadable'],
        'detail': '%d directories read, %d unreadable'
                  % (permissions['directories'],
                     len(permissions['unreadable'])),
    })

    checks.append({
        'name': 'Every analysed Python file parses',
        'ok': not report['syntax_errors'],
        'detail': '%d syntax error(s)' % len(report['syntax_errors']),
    })

    return checks


def summarize_languages(metrics, entries):
    """Aggregated line metrics per language."""
    buckets = {}
    for item in metrics:
        name = item.get('filename', '')
        extension = os.path.splitext(name)[1].lower() or '.txt'
        bucket = buckets.setdefault(extension, {
            'files': 0, 'lines': 0, 'code': 0, 'comments': 0, 'blank': 0,
            'docstrings': 0, 'max_file_lines': 0})
        bucket['files'] += 1
        bucket['lines'] += item.get('total_lines', 0)
        bucket['code'] += item.get('code_lines', 0)
        bucket['comments'] += item.get('comment_lines', 0)
        bucket['blank'] += item.get('blank_lines', 0)
        bucket['docstrings'] += item.get('docstring_lines', 0)
        bucket['max_file_lines'] = max(bucket['max_file_lines'],
                                       item.get('total_lines', 0))

    python_metrics = [item for item in metrics
                      if item.get('filename', '').endswith('.py')]
    lengths = [item.get('total_lines', 0) for item in python_metrics]
    complexities = [detail['complexity']
                    for item in python_metrics
                    for detail in item.get('function_details', [])]

    return {
        'by_language': buckets,
        'python': {
            'files': len(python_metrics),
            'total_lines': sum(lengths),
            'code_lines': sum(item.get('code_lines', 0)
                              for item in python_metrics),
            'comment_lines': sum(item.get('comment_lines', 0)
                                 for item in python_metrics),
            'docstring_lines': sum(item.get('docstring_lines', 0)
                                   for item in python_metrics),
            'blank_lines': sum(item.get('blank_lines', 0)
                               for item in python_metrics),
            'classes': sum(item.get('classes', 0) for item in python_metrics),
            'functions': sum(item.get('functions', 0)
                             for item in python_metrics),
            'methods': sum(item.get('methods', 0) for item in python_metrics),
            'median_lines': median(lengths),
            'p90_lines': percentile(lengths, 0.90),
            'largest_file_lines': max(lengths) if lengths else 0,
            'max_complexity': max(complexities) if complexities else 0,
            'mean_complexity': (round(sum(complexities) / float(len(complexities)), 2)
                                if complexities else 0),
        },
    }


def collect_findings(metrics, syntax_errors, incompatible, below_project_floor,
                     functions, unused_imports, mutable_defaults,
                     bare_excepts, dependencies, permissions, todo_total,
                     project_minimum=None):
    """Everything that deserves a line in the report."""
    findings = []

    if syntax_errors:
        findings.append({
            'severity': 'high',
            'title': 'Files that do not parse',
            'detail': '%d Python file(s) failed to parse.' % len(syntax_errors),
            'items': [item['file'] + ' — ' + str(item['error'])
                      for item in syntax_errors[:20]],
        })

    if below_project_floor:
        floor_text = 'Python %d.%d' % project_minimum if project_minimum \
            else 'the project floor'
        findings.append({
            'severity': 'high',
            'title': 'Files that need a newer Python than the project floor',
            'detail': '%d file(s) use syntax newer than %s.'
                      % (len(below_project_floor), floor_text),
            'items': [item['file'] + ' — ' + '; '.join(item['problems'])
                      for item in below_project_floor[:20]],
        })

    if incompatible:
        findings.append({
            'severity': 'info',
            'title': 'Files that need a newer Python than 3.3',
            'detail': '%d file(s) use syntax newer than Python 3.3, which is '
                      'the floor this analyzer promises to run on. The '
                      'application has its own floor (see setup.py), so this '
                      'is context, not a defect.'
                      % len(incompatible),
            'items': [item['file'] + ' — ' + '; '.join(item['problems'])
                      for item in incompatible[:20]],
        })

    long_functions = [item for item in functions
                      if item['length'] > LONG_FUNCTION_LINES]
    if long_functions:
        long_functions.sort(key=lambda item: item['length'], reverse=True)
        findings.append({
            'severity': 'medium',
            'title': 'Functions longer than %d lines' % LONG_FUNCTION_LINES,
            'detail': '%d function(s) are longer than %d lines.'
                      % (len(long_functions), LONG_FUNCTION_LINES),
            'items': ['%s:%s %s() — %d lines'
                      % (item['file'], item['line'], item['name'], item['length'])
                      for item in long_functions[:20]],
        })

    complex_functions = [item for item in functions
                         if item['complexity'] > HIGH_COMPLEXITY]
    if complex_functions:
        complex_functions.sort(key=lambda item: item['complexity'],
                               reverse=True)
        findings.append({
            'severity': 'medium',
            'title': 'Functions with complexity above %d' % HIGH_COMPLEXITY,
            'detail': '%d function(s) branch more than %d times.'
                      % (len(complex_functions), HIGH_COMPLEXITY),
            'items': ['%s:%s %s() — complexity %d'
                      % (item['file'], item['line'], item['name'],
                         item['complexity'])
                      for item in complex_functions[:20]],
        })

    deep = [item for item in functions if item['nesting'] > DEEP_NESTING]
    if deep:
        deep.sort(key=lambda item: item['nesting'], reverse=True)
        findings.append({
            'severity': 'low',
            'title': 'Nesting deeper than %d levels' % DEEP_NESTING,
            'detail': '%d function(s) nest control flow deeply.' % len(deep),
            'items': ['%s:%s %s() — depth %d'
                      % (item['file'], item['line'], item['name'],
                         item['nesting'])
                      for item in deep[:20]],
        })

    if unused_imports:
        findings.append({
            'severity': 'low',
            'title': 'Imports that are never used in their file',
            'detail': '%d unused import(s) found.' % len(unused_imports),
            'items': ['%s:%s %s'
                      % (item['file'], item['line'], item['name'])
                      for item in unused_imports[:30]],
        })

    if bare_excepts:
        findings.append({
            'severity': 'low',
            'title': 'Bare except clauses',
            'detail': '%d bare except(s) swallow every error.' % len(bare_excepts),
            'items': ['%s:%s' % (item['file'], item['line'])
                      for item in bare_excepts[:20]],
        })

    if mutable_defaults:
        findings.append({
            'severity': 'low',
            'title': 'Mutable default arguments',
            'detail': '%d function(s) default to a mutable object.' % len(mutable_defaults),
            'items': ['%s:%s %s()' % (item['file'], item['line'], item.get('name', ''))
                      for item in mutable_defaults[:20]],
        })

    missing = dependencies.get('missing', [])
    if missing:
        findings.append({
            'severity': 'high',
            'title': 'Requirements not installed in this interpreter',
            'detail': '%d package(s) from requirements.txt are missing.' % len(missing),
            'items': list(missing),
        })

    unguarded = [item for item in dependencies.get('undeclared_imports', [])
                 if not item['installed'] and not item.get('guarded')]
    if unguarded:
        findings.append({
            'severity': 'high',
            'title': 'Imports that are neither declared nor installed',
            'detail': '%d module(s) are imported without a try/except and are '
                      'not installed in this interpreter, so importing the '
                      'module that needs them raises ImportError.'
                      % len(unguarded),
            'items': [item['module'] for item in unguarded],
        })

    unsatisfied = dependencies.get('unsatisfied', [])
    if unsatisfied:
        findings.append({
            'severity': 'medium',
            'title': 'Installed versions outside the declared range',
            'detail': '%d package(s) do not match requirements.txt.' % len(unsatisfied),
            'items': ['%s — installed %s, required %s'
                      % (item['name'], item['installed'], item['specifier'])
                      for item in unsatisfied],
        })

    unreadable = permissions.get('unreadable', [])
    if unreadable:
        findings.append({
            'severity': 'high',
            'title': 'Paths that could not be read',
            'detail': '%d path(s) are not readable.' % len(unreadable),
            'items': ['%s — %s' % (item['path'], item['reason'])
                      for item in unreadable[:20]],
        })

    if todo_total:
        findings.append({
            'severity': 'info',
            'title': 'TODO / FIXME markers',
            'detail': '%d marker(s) in the tree.' % todo_total,
            'items': [],
        })

    order = {'high': 0, 'medium': 1, 'low': 2, 'info': 3}
    findings.sort(key=lambda item: order.get(item['severity'], 9))
    return findings


# ── Rendering ────────────────────────────────────────────────────────────────

def _table(headers, rows):
    """Render a Markdown table."""
    lines = ['| ' + ' | '.join(headers) + ' |',
             '| ' + ' | '.join(['---'] * len(headers)) + ' |']
    for row in rows:
        lines.append('| ' + ' | '.join(str(cell) for cell in row) + ' |')
    return '\n'.join(lines)


def render_markdown(report):
    """Render the full report as Markdown."""
    runtime = report['runtime']
    permissions = report['permissions']
    structure = report['structure']
    language = report['language']
    dependencies = report['dependencies']
    python_metrics = language['python']

    out = []
    out.append('# Zaya codebase analysis')
    out.append('')
    out.append('Generated by `tools/analyze_codebase.py` on %s.'
               % report['generated_at'])
    out.append('')
    out.append('Root: `%s` — %d files, %s.'
               % (report['root'], structure['total_files'],
                  format_bytes(structure['total_bytes'])))
    out.append('')

    out.append('## 1. Method')
    out.append('')
    out.append('Every number below is measured with the CPython standard library:')
    out.append('')
    out.append('- `ast` builds a real syntax tree, so functions, classes, '
               'branches and nesting are counted, not guessed from text.')
    out.append('- `tokenize` supplies exact comment positions.')
    out.append('- `importlib.metadata` reports the version of every installed '
               'distribution in the interpreter that ran this report.')
    out.append('')
    out.append('Complexity is a documented approximation: a function starts at 1 '
               'and gains one point for each `if`, `if` expression, `for`, '
               '`while`, `except`, `with`, `assert`, each extra operand of a '
               'boolean operator, and each `if` inside a comprehension.')
    out.append('')

    scope = report['scope']
    out.append('### 1.1 Analysis scope')
    out.append('')
    if scope['include_tests']:
        out.append('Test folders and test files are **included** in this run '
                   '(`--include-tests` was passed).')
    else:
        out.append('Test folders and test files are **excluded** from this '
                   'run, as requested. The product code is what the numbers '
                   'below describe.')
    out.append('')
    out.append(_table(
        ['Scope item', 'Value'],
        [
            ['Files analysed', str(scope['analysed_files'])],
            ['Test paths excluded', str(scope['excluded_paths'])],
            ['Files inside the excluded test paths',
             str(scope['excluded_files'])],
            ['Test paths still in scope', str(len(scope['test_paths_in_scope']))],
            ['Test directories excluded',
             ', '.join(scope['excluded_test_directories']) or 'none'],
            ['Test files excluded by name',
             str(len(scope['excluded_test_files']))],
        ]))
    out.append('')
    if scope['excluded_test_files']:
        out.append('Test files skipped by name:')
        out.append('')
        for path in scope['excluded_test_files'][:20]:
            out.append('- `%s`' % path)
        if len(scope['excluded_test_files']) > 20:
            out.append('- ...and %d more.'
                       % (len(scope['excluded_test_files']) - 20))
        out.append('')

    out.append('## 2. Environment')
    out.append('')
    floor = report.get('project_python_floor') or {}
    floor_min = floor.get('minimum')
    floor_max = floor.get('maximum')
    floor_text = 'not found'
    if floor_min:
        floor_text = '%d.%d' % floor_min
        if floor_max:
            floor_text += ' (warns above %d.%d)' % floor_max
    out.append(_table(
        ['Check', 'Result'],
        [
            ['Interpreter', '`%s`' % runtime['executable']],
            ['Python', '%s (%s)' % (runtime['version'], runtime['implementation'])],
            ['Analyzer minimum', '%s — %s'
             % (runtime['minimum_required'],
                'satisfied' if runtime['meets_minimum'] else 'NOT satisfied')],
            ['App Python floor (setup.py)', floor_text],
            ['Platform', runtime['platform']],
            ['Project virtualenv',
             ('`%s`' % report['project_venv']['relative'])
             if report.get('project_venv') else 'none found'],
            ['Analysis time', '%.2f s' % report['elapsed_seconds']],
        ]))
    out.append('')
    if floor_min:
        running = tuple(runtime['version_info'][:2])
        verdict = 'satisfied' if running >= floor_min else 'NOT satisfied'
        out.append('The running interpreter is %s, the application floor is %d.%d '
                   '(%s).' % (runtime['version'], floor_min[0], floor_min[1], verdict))
        out.append('')

    out.append('## 3. Read permissions')
    out.append('')
    out.append(_table(
        ['Check', 'Result'],
        [
            ['Project root readable', 'yes' if permissions['root_readable'] else 'NO'],
            ['Project root traversable', 'yes' if permissions['root_executable'] else 'NO'],
            ['Directories walked', str(permissions['directories'])],
            ['Files seen', str(permissions['files'])],
            ['Unreadable paths', str(len(permissions['unreadable']))],
        ]))
    out.append('')
    if permissions.get('probe'):
        out.append('A real read of `%s` succeeded (`%s`).'
                   % (permissions['probe'],
                      'yes' if permissions.get('probe_ok') else 'no'))
        out.append('')
    if permissions['unreadable']:
        out.append('Unreadable paths:')
        out.append('')
        for item in permissions['unreadable']:
            out.append('- `%s` — %s' % (item['path'], item['reason']))
        out.append('')

    out.append('## 4. Dependencies')
    out.append('')
    rows = []
    for item in dependencies['rows']:
        rows.append([item['name'],
                     item['installed'],
                     item['specifier'] or '—',
                     item['status']])
    out.append(_table(['Requirement', 'Installed', 'Declared', 'Status'], rows))
    out.append('')
    out.append('Missing: %s.  Version mismatches: %s.'
               % (', '.join(dependencies['missing']) or 'none',
                  len(dependencies['unsatisfied'])))
    out.append('')
    if dependencies['declared_unused']:
        out.append('Declared but never imported anywhere in the tree: %s.'
                   % ', '.join(dependencies['declared_unused']))
        out.append('')
    undeclared = dependencies['undeclared_imports']
    if undeclared:
        rows = []
        for item in undeclared:
            if item['installed']:
                state = 'installed'
            elif item.get('guarded'):
                state = 'not installed (guarded by try/except — optional)'
            else:
                state = 'NOT INSTALLED (unguarded)'
            rows.append([item['module'], state])
        out.append('Imported but not declared in requirements.txt. A guarded '
                   'import sits inside a try/except, so it disables one '
                   'feature instead of breaking the app — the optional extras '
                   'the project documents this way. An unguarded import that '
                   'is not installed is a real risk.')
        out.append('')
        out.append(_table(['Module', 'State'], rows))
        out.append('')

    out.append('## 5. Structure')
    out.append('')
    rows = []
    for item in sorted(structure['top_level'],
                       key=lambda entry: (-entry['bytes'], entry['name'])):
        rows.append([item['name'], item['kind'], item['files'],
                     format_bytes(item['bytes'])])
    out.append(_table(['Entry', 'Kind', 'Files', 'Size'], rows))
    out.append('')
    rows = []
    for extension, bucket in sorted(structure['by_extension'].items(),
                                    key=lambda item: -item[1]['files']):
        rows.append([extension, bucket['files'], format_bytes(bucket['bytes'])])
    out.append(_table(['Extension', 'Files', 'Size'], rows))
    out.append('')

    out.append('## 6. Code metrics')
    out.append('')
    out.append(_table(
        ['Metric', 'Value'],
        [
            ['Python files', str(python_metrics['files'])],
            ['Total lines', str(python_metrics['total_lines'])],
            ['Code lines', str(python_metrics['code_lines'])],
            ['Comment lines', str(python_metrics['comment_lines'])],
            ['Docstring lines', str(python_metrics['docstring_lines'])],
            ['Blank lines', str(python_metrics['blank_lines'])],
            ['Classes', str(python_metrics['classes'])],
            ['Functions', str(python_metrics['functions'])],
            ['Methods', str(python_metrics['methods'])],
            ['Median file length', str(python_metrics['median_lines'])],
            ['90th percentile file length', str(python_metrics['p90_lines'])],
            ['Largest file', str(python_metrics['largest_file_lines'])],
            ['Mean function complexity', str(python_metrics['mean_complexity'])],
            ['Highest function complexity', str(python_metrics['max_complexity'])],
        ]))
    out.append('')

    rows = []
    for extension, bucket in sorted(language['by_language'].items(),
                                    key=lambda item: -item[1]['lines']):
        rows.append([extension, bucket['files'], bucket['lines'],
                     bucket['code'], bucket['comments'], bucket['docstrings']])
    out.append(_table(['Language', 'Files', 'Lines', 'Code', 'Comments',
                       'Docstrings'], rows))
    out.append('')

    python_items = [item for item in report['metrics']
                    if item.get('filename', '').endswith('.py')]
    python_items.sort(key=lambda item: item.get('total_lines', 0), reverse=True)
    rows = []
    for item in python_items[:20]:
        rows.append([item['filename'], item.get('total_lines', 0),
                     item.get('code_lines', 0), item.get('classes', 0),
                     item.get('functions', 0)])
    out.append('### 6.1 Largest Python files')
    out.append('')
    out.append(_table(['File', 'Lines', 'Code', 'Classes', 'Functions'], rows))
    out.append('')

    functions = sorted(report['functions'],
                       key=lambda item: item['length'], reverse=True)
    rows = []
    for item in functions[:20]:
        rows.append(['%s:%s' % (item['file'], item['line']), item['name'],
                     item['length'], item['complexity'], item['nesting']])
    out.append('### 6.2 Longest functions')
    out.append('')
    out.append(_table(['Location', 'Function', 'Lines', 'Complexity',
                       'Nesting'], rows))
    out.append('')

    functions = sorted(report['functions'],
                       key=lambda item: item['complexity'], reverse=True)
    rows = []
    for item in functions[:20]:
        rows.append(['%s:%s' % (item['file'], item['line']), item['name'],
                     item['complexity'], item['length'], item['nesting']])
    out.append('### 6.3 Most complex functions')
    out.append('')
    out.append(_table(['Location', 'Function', 'Complexity', 'Lines',
                       'Nesting'], rows))
    out.append('')

    out.append('## 7. Findings')
    out.append('')
    if not report['findings']:
        out.append('Nothing above the configured thresholds was found.')
        out.append('')
    for finding in report['findings']:
        out.append('### %s — %s' % (finding['severity'].upper(),
                                    finding['title']))
        out.append('')
        out.append(finding['detail'])
        out.append('')
        if finding['items']:
            for item in finding['items']:
                out.append('- %s' % item)
            out.append('')

    unreferenced = report['unreferenced_definitions']
    out.append('## 8. Definitions with no reference in the tree')
    out.append('')
    if not unreferenced:
        out.append('Every definition is referenced somewhere.')
        out.append('')
    else:
        out.append('Candidates only — a definition can be reached dynamically '
                   '(plugin discovery, `getattr`, an entry point), so check '
                   'before removing anything.')
        out.append('')
        rows = [[item['file'], item['line'], item['kind'], item['name']]
                for item in unreferenced[:40]]
        out.append(_table(['File', 'Line', 'Kind', 'Name'], rows))
        out.append('')

    out.append('## 9. Summary')
    out.append('')
    counts = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    for finding in report['findings']:
        counts[finding['severity']] = counts.get(finding['severity'], 0) + 1
    out.append('- %d files analysed, %s on disk.'
               % (structure['total_files'], format_bytes(structure['total_bytes'])))
    out.append('- %d Python files, %d lines of code, %d functions, %d classes.'
               % (python_metrics['files'], python_metrics['code_lines'],
                  python_metrics['functions'], python_metrics['classes']))
    out.append('- %d requirement(s) declared, %d missing, %d outside their range.'
               % (len(dependencies['rows']), len(dependencies['missing']),
                  len(dependencies['unsatisfied'])))
    out.append('- %d unreadable path(s).' % len(permissions['unreadable']))
    out.append('- Findings: %d high, %d medium, %d low, %d informational.'
               % (counts.get('high', 0), counts.get('medium', 0),
                  counts.get('low', 0), counts.get('info', 0)))
    out.append('')
    return '\n'.join(out)


def render_console(report):
    """Short summary for the terminal."""
    structure = report['structure']
    python_metrics = report['language']['python']
    dependencies = report['dependencies']
    permissions = report['permissions']
    scope = report['scope']

    lines = []
    lines.append('Zaya codebase analysis — %s' % report['generated_at'])
    lines.append('Root: %s' % report['root'])
    lines.append('')
    lines.append('Scope        : %d file(s) analysed, %d test path(s) excluded '
                 '(%d file(s) inside them)'
                 % (scope['analysed_files'], scope['excluded_paths'],
                    scope['excluded_files']))
    lines.append('Files        : %d (%s)'
                 % (structure['total_files'],
                    format_bytes(structure['total_bytes'])))
    lines.append('Python       : %d files, %d lines of code, %d functions, '
                 '%d classes'
                 % (python_metrics['files'], python_metrics['code_lines'],
                    python_metrics['functions'], python_metrics['classes']))
    lines.append('Largest file : %d lines'
                 % python_metrics['largest_file_lines'])
    lines.append('Dependencies : %d declared, %d missing'
                 % (len(dependencies['rows']), len(dependencies['missing'])))
    lines.append('Permissions  : %d directories read, %d unreadable'
                 % (permissions['directories'],
                    len(permissions['unreadable'])))
    lines.append('Findings     : %d' % len(report['findings']))
    for finding in report['findings']:
        lines.append('  [%-6s] %s — %s'
                     % (finding['severity'], finding['title'],
                        finding['detail']))
    return '\n'.join(lines)


def render_verification(checks):
    """Render the verification checklist for the terminal."""
    lines = ['Verification checklist']
    lines.append('')
    for check in checks:
        lines.append('[%s] %s — %s'
                     % ('PASS' if check['ok'] else 'FAIL',
                        check['name'], check['detail']))
    failed = [check for check in checks if not check['ok']]
    lines.append('')
    lines.append('%d/%d checks passed.'
                 % (len(checks) - len(failed), len(checks)))
    return '\n'.join(lines)


# ── Command line ─────────────────────────────────────────────────────────────

def parse_arguments(argv):
    """Build the argument parser and parse argv."""
    here = os.path.dirname(os.path.abspath(__file__))
    default_root = os.path.dirname(here)

    parser = argparse.ArgumentParser(
        description='Static analysis of the Zaya source tree (read-only).')
    parser.add_argument('--root', default=default_root,
                        help='Project directory to analyse (default: the '
                             'folder this script lives in).')
    parser.add_argument('--out', default=None,
                        help='Directory for the Markdown and JSON reports '
                             '(default: <root>/docs/generated).')
    parser.add_argument('--json-only', action='store_true',
                        help='Write only the JSON report.')
    parser.add_argument('--markdown-only', action='store_true',
                        help='Write only the Markdown report.')
    parser.add_argument('--no-write', action='store_true',
                        help='Print the console summary without writing files.')
    parser.add_argument('--include-generated', action='store_true',
                        help='Also walk build output, caches and virtualenvs.')
    parser.add_argument('--include-tests', action='store_true',
                        help='Also analyse the tests folder and test files. '
                             'They are excluded by default.')
    parser.add_argument('--verify', action='store_true',
                        help='Print the scope and environment verification '
                             'checklist.')
    parser.add_argument('--strict', action='store_true',
                        help='Exit non-zero when high severity findings exist.')
    parser.add_argument('--self-check', action='store_true',
                        help='Check this analyzer against the Python 3.3 '
                             'syntax floor and exit.')
    return parser.parse_args(argv)


def self_check():
    """Verify this file itself stays inside the Python 3.3 syntax floor."""
    path = os.path.abspath(__file__)
    source = read_text(path)
    result = check_python_compatibility(source, os.path.basename(path))
    print('Self-check: %s' % os.path.basename(path))
    print('  Python 3.3 syntax floor: %s'
          % ('satisfied' if result['compatible'] else 'VIOLATED'))
    for problem in result['problems']:
        print('  - %s' % problem)
    return 0 if result['compatible'] else 1


def main(argv=None):
    """Entry point."""
    arguments = parse_arguments(argv)

    if arguments.self_check:
        return self_check()

    root = os.path.abspath(arguments.root)
    if not os.path.isdir(root):
        print('Not a directory: %s' % root, file=sys.stderr)
        return 2

    report = build_report(root, arguments.include_generated,
                          arguments.include_tests)

    out_directory = arguments.out or os.path.join(root, 'docs', 'generated')
    markdown_path = os.path.join(out_directory, 'codebase_analysis.md')
    json_path = os.path.join(out_directory, 'codebase_analysis.json')

    if not arguments.no_write:
        if not os.path.isdir(out_directory):
            os.makedirs(out_directory)
        if not arguments.json_only:
            handle = io.open(markdown_path, 'w', encoding='utf-8')
            try:
                handle.write(render_markdown(report))
            finally:
                handle.close()
        if not arguments.markdown_only:
            handle = io.open(json_path, 'w', encoding='utf-8')
            try:
                json.dump(report, handle, indent=2, sort_keys=True,
                          default=str)
            finally:
                handle.close()

    print(render_console(report))
    if not arguments.no_write:
        if not arguments.json_only:
            print('')
            print('Markdown report: %s' % markdown_path)
        if not arguments.markdown_only:
            print('JSON report    : %s' % json_path)

    if arguments.verify:
        checks = verify_scope(root, report)
        print('')
        print(render_verification(checks))
        if not all(check['ok'] for check in checks):
            return 1

    if arguments.strict:
        for finding in report['findings']:
            if finding['severity'] == 'high':
                return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
