"""Deterministic delivery checks for explicitly requested document artifacts."""
from pathlib import Path
import re
import time
import zipfile


_FORMATS = [('pptx', r'\bpptx\b|\bpowerpoint\b|\bpresentation\b|\bslide deck\b'),
            ('xlsx', r'\bxlsx\b|\bexcel\b'), ('docx', r'\bdocx\b|\bword document\b'),
            ('pdf', r'\bpdf\b'), ('html', r'\bhtml\b')]
_OUTPUT_VERB = re.compile(r'\b(create|make|build|generate|prepare|deliver|export|save|write|convert)(?:s|d)?\b')


def requested_formats(goal):
    """Conservatively recognize deliverables, not input types or topic nouns."""
    text = str(goal).lower()
    if 'owner follow-up:' in text:
        followup = text.rsplit('owner follow-up:', 1)[-1]
        if (re.search(r'\b(wanted|meant|said|instead|actually|should be)\b', followup)
                and any(re.search(pattern, followup) for _, pattern in _FORMATS)):
            # An explicit format correction supersedes the earlier format.
            text = 'Create ' + followup
            text = text.lower()
    formats = []
    for extension, pattern in _FORMATS:
        for match in re.finditer(pattern, text):
            prefix = text[:match.start()]
            # New clauses require their own output instruction. Comma-separated
            # formats still share the last explicit output verb.
            clause = re.split(r'[;\n!?]', prefix)[-1]
            if re.search(r'(?:not|no|instead of|rather than)\s+(?:an?\s+)?$', clause):
                continue
            verbs = list(_OUTPUT_VERB.finditer(clause))
            if not verbs:
                continue
            verb = verbs[-1]
            lead = clause[:verb.start()]
            between = clause[verb.end():]
            if re.search(r'(?:not|never|don.t)\s*$', lead):
                continue
            if re.search(r'\b(about|regarding|discussing|explaining)\b', between):
                continue
            if re.search(r'\b(read|reads|reading|parse|parses|parsing|load|loads|import|imports|open|opens|input|source|from)\b', between):
                # A later output marker explicitly changes the direction.
                tail = re.split(r'\b(?:read|reads|reading|parse|parses|parsing|load|loads|import|imports|open|opens|input|source|from)\b', between)[-1]
                if not re.search(r'\b(?:to|into|as|output)\b', tail):
                    continue
            if re.match(r'\s+(?:parser|reader|viewer|processor|converter)\b', text[match.end():]):
                continue
            if re.search(r'\b(script|app|application|tool|program|parser|converter|tutorial)\b', between) and not re.search(r'\b(to|into|as|export|output)\b', between):
                continue
            if verb.group(1) == 'convert' and not re.search(r'\b(to|into|as)\b', between):
                continue
            if re.match(r'\s+(?:to|into|as)\b', text[match.end():]) and verb.group(1) in {'save', 'convert'}:
                continue
            formats.append(extension)
            break
    return formats


def _valid_artifact(path, extension):
    if path.stat().st_size > 32 * 1024 * 1024:
        return False
    if extension in {'pptx', 'docx', 'xlsx'}:
        with zipfile.ZipFile(path) as package:
            entries = package.infolist()
            if len(entries) > 10000 or sum(entry.file_size for entry in entries) > 100 * 1024 * 1024:
                return False
            if package.testzip() is not None:
                return False
        if extension == 'pptx':
            from pptx import Presentation
            presentation = Presentation(str(path))
            return len(presentation.slides) > 0
        if extension == 'xlsx':
            from openpyxl import load_workbook
            workbook = load_workbook(path, read_only=True, keep_links=False)
            try:
                if not workbook.worksheets:
                    return False
                for sheet in workbook.worksheets:
                    next(sheet.iter_rows(), None)
                return True
            finally:
                workbook.close()
        from docx import Document
        document = Document(str(path))
        return document.element.body is not None
    if extension == 'pdf':
        from pypdf import PdfReader
        with path.open('rb') as stream:
            reader = PdfReader(stream, strict=True)
            return not reader.is_encrypted and len(reader.pages) > 0
    if extension == 'html':
        from html.parser import HTMLParser
        class DocumentParser(HTMLParser):
            document = False
            def handle_starttag(self, tag, attrs):
                if tag == 'html':
                    self.document = True
        parser = DocumentParser()
        parser.feed(path.read_text(encoding='utf-8', errors='replace'))
        return parser.document
    return False


def verify_artifacts(project, formats, since):
    root = Path(project).resolve()
    found = set()
    inspected = 0
    deadline = time.monotonic() + 3
    for path in root.rglob('*'):
        inspected += 1
        if inspected > 10000 or time.monotonic() > deadline:
            break
        if path.is_symlink() or any(part in {'.git', '.venv', 'node_modules'} for part in path.relative_to(root).parts):
            continue
        ext = path.suffix.lower().lstrip('.')
        if ext not in formats or not path.is_file():
            continue
        try:
            if not path.resolve().is_relative_to(root) or path.stat().st_mtime < since - 2 or path.stat().st_size == 0:
                continue
            if not _valid_artifact(path, ext):
                continue
            found.add(ext)
        except Exception:
            # Document parsers have provider-specific format exceptions. An
            # unreadable artifact remains missing; it can never authorize work.
            continue
    return sorted(set(formats) - found)
