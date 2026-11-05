"""Deterministic documentation and Python source inspection."""
import argparse
import ast
import json
from pathlib import Path
import sys

from .phrases import PARAPHRASE, NOPARAPHRASE, GENERIC_NAMES

EXCLUDED = {'.git', '__pycache__', '.venv', 'venv', 'env', '.env'}


def match_phrases(text, phrases):
    """Return longest-first matches and text with matched spans blanked."""
    text = text.lower()
    matches = []
    for phrase in sorted(phrases, key=len, reverse=True):
        start = text.find(phrase)
        while start >= 0:
            matches.append(phrase)
            text = text[:start] + ' ' * len(phrase) + text[start + len(phrase):]
            start = text.find(phrase)
    return matches, text


def prose(text):
    lines = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith('```'):
            fenced = not fenced
        elif not fenced:
            lines.append(line.replace('`', ''))
    return '\n'.join(lines)


def has_evidence(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    aliases = {}
    shadowed = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                aliases[a.asname or a.name] = node.module + '.' + a.name

    def resolve(node):
        if isinstance(node, ast.Name):
            return '' if node.id in shadowed else aliases.get(node.id, '')
        if isinstance(node, ast.Attribute):
            base = resolve(node.value)
            return base + '.' + node.attr if base and node.attr not in shadowed else ''
        return ''

    def literal(node):
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else ''

    def kind(node):
        if not isinstance(node, ast.Call):
            return None
        name = resolve(node.func)
        if name in {'transformers.' + x + '.from_pretrained' for x in ('AutoModelForSeq2SeqLM', 'PegasusForConditionalGeneration', 'T5ForConditionalGeneration')}:
            if node.args and 'paraphrase' in literal(node.args[0]).lower():
                return 'model'
        if name == 'transformers.pipeline' and node.args and literal(node.args[0]) == 'text2text-generation':
            model = next((k.value for k in node.keywords if k.arg == 'model'), node.args[1] if len(node.args) > 1 else None)
            if 'paraphrase' in literal(model).lower():
                return 'pipeline'
        if name.startswith('nlpaug.') and name.endswith('.BackTranslationAug'):
            return 'augmenter'
        return None

    values = {}
    # Resolve simple assignments, including aliases of loaded values.
    for _ in range(len(list(ast.walk(tree))) + 1):
        changed = False
        for n in ast.walk(tree):
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                value = n.value
                k = kind(value) or (values.get(value.id) if isinstance(value, ast.Name) else None)
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for target in targets:
                    if k and isinstance(target, ast.Name) and values.get(target.id) != k:
                        values[target.id] = k
                        changed = True
        if not changed:
            break
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        name = resolve(n.func)
        if name.startswith('sentence_transformers.') and name.endswith('.paraphrase_mining'):
            return True
        if isinstance(n.func, ast.Attribute):
            attr = n.func.attr
            if attr in GENERIC_NAMES and attr not in shadowed and not (isinstance(n.func.value, ast.Name) and n.func.value.id in shadowed):
                return True
            base = n.func.value
            k = kind(base) or (values.get(base.id) if isinstance(base, ast.Name) else None)
            if (attr, k) in {('generate', 'model'), ('augment', 'augmenter')}:
                return True
        elif isinstance(n.func, ast.Name):
            if name and name.split('.')[-1] in GENERIC_NAMES:
                return True
            if values.get(n.func.id) == 'pipeline':
                return True
        elif isinstance(n.func, ast.Call) and kind(n.func) == 'pipeline':
            return True
    return False


def audit(repo='.', ignore=(), verbose=False):
    root = Path(repo)
    if not root.is_dir():
        raise OSError('Repository is not a directory: ' + str(root))
    sources = []
    documents = []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        if any(part in EXCLUDED for part in path.relative_to(root).parts) or any(rel.startswith(p) for p in ignore):
            if verbose:
                print('skip ' + rel, file=sys.stderr)
            continue
        if not path.is_file():
            continue
        is_test = 'tests' in path.relative_to(root).parts[:-1]
        if path.suffix == '.py':
            sources.append(path.read_text(encoding='utf-8'))
        if rel == 'README.md' or (rel.startswith('docs/') and path.suffix == '.md') or (is_test and path.suffix in {'.md', '.py', '.txt', '.rst'}):
            documents.append((rel, prose(path.read_text(encoding='utf-8')), is_test))
        if verbose:
            print('scan ' + rel, file=sys.stderr)
    evidence = any(has_evidence(s) for s in sources)
    findings = []
    for path, text, test in documents:
        denials, rest = match_phrases(text, NOPARAPHRASE)
        claims, _ = match_phrases(rest, PARAPHRASE)
        for phrase in claims if not evidence else []:
            findings.append(dict(verdict='documented-paraphrasing-claim-false', severity='MEDIUM' if test else 'HIGH', path=path, message='Unsupported documented claim: ' + phrase))
        for phrase in denials if evidence and not test else []:
            findings.append(dict(verdict='documented-no-paraphrasing-claim-false', severity='HIGH', path=path, message='Documented denial contradicted by source evidence: ' + phrase))
    return findings


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, 'error: ' + message + '\n')


def main(argv=None):
    parser = Parser(description='Audit documented sentence restatement claims.')
    parser.add_argument('--version', action='version', version='0.1.0')
    sub = parser.add_subparsers(dest='command', parser_class=Parser)
    cmd = sub.add_parser('audit')
    cmd.add_argument('repo', nargs='?', default='.')
    cmd.add_argument('--json', action='store_true')
    cmd.add_argument('--verbose', action='store_true')
    cmd.add_argument('--ignore', action='append', default=[])
    cmd.add_argument('--fail-on', choices=['high', 'medium'], default='high')
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.verbose:
            print('scope: README.md, docs/**/*.md, tests fixtures; Python evidence', file=sys.stderr)
        findings = audit(args.repo, args.ignore, args.verbose)
    except (OSError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(findings))
    elif findings:
        for f in findings:
            print('{severity} {verdict} {path}: {message}'.format(**f))
    else:
        print('PASS')
    return 2 if any(f['severity'] == 'HIGH' or args.fail_on == 'medium' for f in findings) else 0
