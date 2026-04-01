import ast
import os
import re
from dataclasses import dataclass, field
from collections import deque


# ─────────────────────────────────────────────
# Files / folders that are never "useful" for
# a business README description
# ─────────────────────────────────────────────
EXCLUDED_FILENAMES = {
    "setup.py", "setup.cfg", "conftest.py", "pytest.ini",
    "pyproject.toml", "tox.ini", "Makefile", ".env",
}

EXCLUDED_EXTENSIONS = {
    ".lock", ".cfg", ".ini", ".env", ".txt", ".json",
    ".yaml", ".yml", ".toml", ".md", ".rst", ".csv",
    ".log", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".pdf", ".zip", ".tar", ".gz",
}

EXCLUDED_DIR_PATTERNS = {
    "__pycache__", ".git", ".github", ".venv", "venv",
    "env", ".env", "node_modules", ".tox", "dist",
    "build", "egg-info", ".pytest_cache", ".mypy_cache",
    "migrations", "static", "templates", "assets",
}

# Filename score bonuses for entry-point detection
ENTRY_FILENAME_SCORES = {
    "main.py": 10,
    "app.py": 10,
    "entry_point.py": 10,
    "entrypoint.py": 10,
    "run.py": 8,
    "start.py": 8,
    "cli.py": 7,
    "server.py": 7,
    "pipeline.py": 5,
    "workflow.py": 5,
    "execute.py": 5,
    "launch.py": 5,
}


# ─────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────
@dataclass
class FunctionInfo:
    name: str
    docstring: str
    args: list[str]


@dataclass
class FileMetadata:
    rel_path: str          # path relative to repo root, e.g. "utils/aws/bedrock.py"
    abs_path: str
    module_docstring: str
    functions: list[FunctionInfo]
    classes: list[str]
    imports: list[str]     # raw project-local module names this file imports
    external_imports: list[str]   # imports not resolved inside repo (likely external/local-path deps)
    sys_path_hints: list[str]     # folder hints detected from sys.path.insert(...)
    model_ids: list[str]    # model IDs / ARNs detected in this file
    has_main_block: bool   # has `if __name__ == "__main__"`
    has_argparse: bool     # uses argparse / click / typer
    uses_sys_argv: bool    # reads sys.argv directly
    uses_input_prompt: bool  # uses input() prompts for runtime values
    entry_score: int       # computed entry-point score


@dataclass
class RepoAnalysis:
    repo_root: str
    primary_entry_point: FileMetadata | None
    entry_points: list[FileMetadata]          # highest-scoring files
    reachable_files: list[FileMetadata]       # files reachable from entry points
    unreachable_files: list[FileMetadata]     # excluded / unused files
    file_tree: str                            # printable tree of reachable files
    all_metadata: dict[str, FileMetadata]     # rel_path → metadata (all py files)
    detected_models: list[str]                # all model identifiers discovered (repo + external hints)
    external_models_by_hint: dict[str, list[str]]   # hint folder -> detected model IDs


# ─────────────────────────────────────────────
# Step 1 – Walk & filter files
# ─────────────────────────────────────────────
def walk_python_files(repo_root: str) -> list[str]:
    """
    Recursively walk repo_root and return absolute paths of .py files
    that are not inside excluded directories.
    """
    result = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Prune excluded directories in-place so os.walk doesn't descend into them
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDED_DIR_PATTERNS and not d.startswith(".")
        ]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            if fname in EXCLUDED_FILENAMES:
                continue
            result.append(os.path.join(dirpath, fname))
    return result


# ─────────────────────────────────────────────
# Step 2 – Parse individual file
# ─────────────────────────────────────────────
def _safe_read(path: str) -> str | None:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return None


def _get_docstring(node) -> str:
    """Extract docstring from a function/class/module AST node."""
    try:
        val = ast.get_docstring(node)
        return (val or "").strip()[:300]   # cap length
    except Exception:
        return ""


def _extract_function_info(node: ast.FunctionDef) -> FunctionInfo:
    args = []
    for arg in node.args.args:
        if arg.arg not in ("self", "cls"):
            args.append(arg.arg)
    return FunctionInfo(
        name=node.name,
        docstring=_get_docstring(node),
        args=args,
    )


def _has_main_block(tree: ast.AST) -> bool:
    """Check for `if __name__ == '__main__':` pattern."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if isinstance(test, ast.Compare):
            left = test.left
            ops = test.ops
            comparators = test.comparators
            if (
                isinstance(left, ast.Name) and left.id == "__name__"
                and len(ops) == 1 and isinstance(ops[0], ast.Eq)
                and len(comparators) == 1
                and isinstance(comparators[0], ast.Constant)
                and comparators[0].value == "__main__"
            ):
                return True
    return False


def _has_argparse(tree: ast.AST, source: str) -> bool:
    """Check for argparse / click / typer usage."""
    keywords = ("argparse", "click", "typer", "ArgumentParser")
    return any(kw in source for kw in keywords)


def _uses_sys_argv(source: str) -> bool:
    return "sys.argv" in source


def _uses_input_prompt(tree: ast.AST, source: str) -> bool:
    if "input(" in source:
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "input":
            return True
    return False


def _extract_sys_path_hints(source: str) -> list[str]:
    """
    Extract folder hints from lines like:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'workflow_inference_process_pdf_diagrams'))
    """
    hints = set()
    for line in source.splitlines():
        if "sys.path.insert" not in line:
            continue
        parts = re.findall(r"['\"]([^'\"]+)['\"]", line)
        for part in parts:
            normalized = part.strip().replace("\\", "/")
            if normalized in {"", ".", "..", "__file__"}:
                continue
            if normalized.startswith("."):
                continue
            hints.add(normalized)
    return sorted(hints)


def _extract_model_ids(source: str) -> list[str]:
    """
    Extract model identifiers / ARNs referenced in source code.
    Captures Bedrock model IDs, inference profiles, and foundation-model ARNs.
    """
    patterns = [
        r"arn:aws:bedrock:[^\"'\s]+",  # full Bedrock ARN
        r"(?:us|eu|ap|sa|ca|me|af)\.[a-z0-9\-]+\.[a-z0-9\-]+(?::\d+)?",  # e.g. us.amazon.nova-lite-v1:0
        r"amazon\.titan\-[a-z0-9\-]+(?::\d+)?",  # e.g. amazon.titan-embed-text-v2:0
        r"us\.anthropic\.[a-z0-9\-]+(?::\d+)?",  # e.g. us.anthropic.claude-sonnet-4-5-...:0
    ]

    found = set()
    for pattern in patterns:
        for match in re.findall(pattern, source, flags=re.IGNORECASE):
            found.add(match.strip())

    return sorted(found)


def _resolve_candidate_to_rel_paths(cand: str, all_rel_paths: set[str]) -> list[str]:
    """
    Resolve an import candidate (path-like or dotted) to repo-relative .py files.
    Supports exact path, suffix path, and basename fallback.
    """
    normalized = cand.replace("\\", "/").strip("/")
    if not normalized:
        return []

    path_like = normalized.replace(".", "/")
    expected = f"{path_like}.py"
    basename = os.path.basename(path_like) + ".py"

    matches = set()

    if expected in all_rel_paths:
        matches.add(expected)

    for rel in all_rel_paths:
        if rel == expected or rel.endswith("/" + expected):
            matches.add(rel)
        elif rel.endswith("/" + basename) or rel == basename:
            matches.add(rel)

    return sorted(matches)


def _extract_local_imports(tree: ast.AST, all_rel_paths: set[str], repo_root: str, file_abs: str) -> tuple[list[str], list[str]]:
    """
    Parse import statements and return module names that correspond to
    files that exist inside the repo (i.e. project-local imports).
    """
    local_imports = []
    unresolved_imports = []
    file_dir = os.path.dirname(file_abs)

    for node in ast.walk(tree):
        candidates = []

        if isinstance(node, ast.Import):
            for alias in node.names:
                candidates.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_path = node.module
                candidates.append(mod_path)
                for alias in node.names:
                    if alias.name != "*":
                        candidates.append(f"{mod_path}.{alias.name}")
                # also try relative resolution
                if node.level and node.level > 0:
                    rel_dir = file_dir
                    for _ in range(node.level - 1):
                        rel_dir = os.path.dirname(rel_dir)
                    rel_cand = os.path.join(rel_dir, mod_path.replace(".", os.sep))
                    candidates.append(rel_cand)

        any_match_for_node = False
        for cand in candidates:
            resolved = _resolve_candidate_to_rel_paths(cand, all_rel_paths)
            if resolved:
                local_imports.extend(resolved)
                any_match_for_node = True
                continue

            # Try relative path fallback for odd imports
            abs_candidate2 = os.path.join(file_dir, cand.replace(".", os.sep) + ".py")
            if os.path.exists(abs_candidate2):
                rel = os.path.relpath(abs_candidate2, repo_root).replace("\\", "/")
                local_imports.append(rel)
                any_match_for_node = True

        if not any_match_for_node:
            for cand in candidates:
                unresolved_imports.append(cand.split(".")[0])

    return sorted(set(local_imports)), sorted(set(unresolved_imports))


def parse_file(abs_path: str, repo_root: str, all_rel_paths: set[str]) -> FileMetadata | None:
    """Parse a single .py file and return its FileMetadata."""
    source = _safe_read(abs_path)
    if source is None:
        return None

    rel_path = os.path.relpath(abs_path, repo_root).replace("\\", "/")

    try:
        tree = ast.parse(source, filename=abs_path)
    except SyntaxError:
        return None

    functions = []
    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            # only top-level + class-level (skip nested helpers)
            functions.append(_extract_function_info(node))
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)

    has_main = _has_main_block(tree)
    has_arg = _has_argparse(tree, source)
    uses_argv = _uses_sys_argv(source)
    uses_input = _uses_input_prompt(tree, source)
    local_imports, unresolved_imports = _extract_local_imports(tree, all_rel_paths, repo_root, abs_path)
    sys_path_hints = _extract_sys_path_hints(source)
    model_ids = _extract_model_ids(source)

    return FileMetadata(
        rel_path=rel_path,
        abs_path=abs_path,
        module_docstring=_get_docstring(tree),
        functions=functions,
        classes=classes,
        imports=local_imports,
        external_imports=unresolved_imports,
        sys_path_hints=sys_path_hints,
        model_ids=model_ids,
        has_main_block=has_main,
        has_argparse=has_arg,
        uses_sys_argv=uses_argv,
        uses_input_prompt=uses_input,
        entry_score=0,  # filled later
    )


def _find_dirs_named(search_root: str, target_name: str) -> list[str]:
    """Recursively find directories whose basename matches target_name."""
    matches = []
    if not os.path.isdir(search_root):
        return matches

    for dirpath, dirnames, _ in os.walk(search_root):
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDED_DIR_PATTERNS and not d.startswith(".")
        ]
        for d in dirnames:
            if d == target_name:
                matches.append(os.path.join(dirpath, d))
    return matches


def _scan_models_in_dir(path: str) -> list[str]:
    """Scan all Python files under a directory and extract model IDs."""
    found = set()
    if not os.path.isdir(path):
        return []

    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDED_DIR_PATTERNS and not d.startswith(".")
        ]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            source = _safe_read(os.path.join(dirpath, fname))
            if not source:
                continue
            found.update(_extract_model_ids(source))

    return sorted(found)


def _collect_external_models(repo_root: str, hints: set[str]) -> dict[str, list[str]]:
    """
    For each sys.path hint folder name, try to locate matching directory candidates
    near repo_root and scan them for model identifiers.
    """
    models_by_hint: dict[str, list[str]] = {}
    if not hints:
        return models_by_hint

    # Search from parent of analyzed repo so sibling and nested project folders are covered.
    search_root = os.path.dirname(repo_root)

    for hint in sorted(hints):
        all_models = set()

        # direct sibling candidate
        sibling_candidate = os.path.normpath(os.path.join(repo_root, "..", hint))
        if os.path.isdir(sibling_candidate):
            all_models.update(_scan_models_in_dir(sibling_candidate))

        # recursive name match candidates
        for candidate in _find_dirs_named(search_root, hint):
            all_models.update(_scan_models_in_dir(candidate))

        models_by_hint[hint] = sorted(all_models)

    return models_by_hint


# ─────────────────────────────────────────────
# Step 3 – Score entry points
# ─────────────────────────────────────────────
def score_entry_points(
    metadata_map: dict[str, FileMetadata]
) -> list[FileMetadata]:
    """
    Score every file for likelihood of being an entry point.
    Returns files sorted by score descending.
    """
    # Build reverse import map: who_is_imported_by[X] = set of files that import X
    imported_by: dict[str, set[str]] = {k: set() for k in metadata_map}
    for rel, meta in metadata_map.items():
        for imp in meta.imports:
            if imp in imported_by:
                imported_by[imp].add(rel)

    scored = []
    for rel, meta in metadata_map.items():
        score = 0
        fname = os.path.basename(rel).lower()

        # Layer 1: __main__ block
        if meta.has_main_block:
            score += 5

        # Layer 2: filename convention
        score += ENTRY_FILENAME_SCORES.get(fname, 0)

        # Layer 3: not imported by anyone else (top of dependency tree)
        if not imported_by[rel]:
            score += 5

        # Layer 4: uses argparse / click / typer
        if meta.has_argparse:
            score += 4

        # Layer 5: imports many other project files (orchestrator)
        score += min(len(meta.imports), 5)  # cap at 5 points

        # Penalty: test files
        if "test" in rel.lower() or fname.startswith("test_") or fname.endswith("_test.py"):
            score -= 20

        # Penalty: __init__ with no real content
        if fname == "__init__.py" and len(meta.functions) == 0:
            score -= 10

        meta.entry_score = score
        scored.append(meta)

    scored.sort(key=lambda m: m.entry_score, reverse=True)
    return scored


# ─────────────────────────────────────────────
# Step 4 – Reachability via BFS
# ─────────────────────────────────────────────
def find_reachable_files(
    entry_points: list[FileMetadata],
    metadata_map: dict[str, FileMetadata],
) -> list[FileMetadata]:
    """
    BFS from entry points through the import graph.
    Returns all reachable FileMetadata objects.
    """
    visited: set[str] = set()
    queue: deque[str] = deque()

    for ep in entry_points:
        queue.append(ep.rel_path)
        visited.add(ep.rel_path)

    while queue:
        current = queue.popleft()
        meta = metadata_map.get(current)
        if not meta:
            continue
        for imp in meta.imports:
            if imp not in visited and imp in metadata_map:
                visited.add(imp)
                queue.append(imp)

    return [metadata_map[r] for r in visited]


# ─────────────────────────────────────────────
# Step 5 – File tree
# ─────────────────────────────────────────────
def build_file_tree(reachable_files: list[FileMetadata], repo_root: str) -> str:
    """
    Build a printable directory tree from the list of reachable files.
    """
    # Group by directory
    tree: dict[str, list[str]] = {}
    for meta in reachable_files:
        parts = meta.rel_path.split("/")
        if len(parts) == 1:
            tree.setdefault(".", []).append(parts[0])
        else:
            folder = "/".join(parts[:-1])
            tree.setdefault(folder, []).append(parts[-1])

    lines = []
    repo_name = os.path.basename(repo_root)
    lines.append(f"{repo_name}/")

    for folder in sorted(tree.keys()):
        if folder != ".":
            lines.append(f"├── {folder}/")
            indent = "│   "
        else:
            indent = ""

        files = sorted(tree[folder])
        for i, fname in enumerate(files):
            connector = "└── " if i == len(files) - 1 else "├── "
            lines.append(f"{indent}{connector}{fname}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Step 6 – Detect entry point threshold
# ─────────────────────────────────────────────
def _select_entry_points(scored: list[FileMetadata]) -> list[FileMetadata]:
    """
    From the sorted-by-score list, pick all files whose score is
    within 4 points of the top score (handles ties / multiple entry points).
    Always return at least 1.
    """
    if not scored:
        return []
    top_score = scored[0].entry_score
    # Must have a positive score to be considered a real entry point
    if top_score <= 0:
        return [scored[0]]
    return [m for m in scored if m.entry_score >= max(top_score - 4, 1)]


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────
def analyze_repo(repo_root: str) -> RepoAnalysis:
    """
    Full pipeline:
      1. Walk & collect .py files
      2. Parse each file
      3. Score entry points
      4. BFS reachability from entry points
      5. Build file tree
    Returns a RepoAnalysis object ready for README generation.
    """
    print("  [analyzer] Walking repository files...")
    abs_paths = walk_python_files(repo_root)

    if not abs_paths:
        print("  [analyzer] No Python files found.")
        return RepoAnalysis(
            repo_root=repo_root,
            primary_entry_point=None,
            entry_points=[],
            reachable_files=[],
            unreachable_files=[],
            file_tree="(empty)",
            all_metadata={},
            detected_models=[],
            external_models_by_hint={},
        )

    all_rel_paths = {
        os.path.relpath(p, repo_root).replace("\\", "/") for p in abs_paths
    }

    print(f"  [analyzer] Parsing {len(abs_paths)} Python files...")
    metadata_map: dict[str, FileMetadata] = {}
    for ap in abs_paths:
        meta = parse_file(ap, repo_root, all_rel_paths)
        if meta:
            metadata_map[meta.rel_path] = meta

    print("  [analyzer] Scoring entry points...")
    scored = score_entry_points(metadata_map)

    # Debug: print top scores
    for m in scored[:5]:
        print(f"    score={m.entry_score:3d}  {m.rel_path}")

    entry_points = _select_entry_points(scored)
    primary_entry_point = scored[0] if scored else None
    print(f"  [analyzer] Entry point(s): {[e.rel_path for e in entry_points]}")

    print("  [analyzer] Computing reachable files via BFS (primary entry point only)...")
    bfs_roots = [primary_entry_point] if primary_entry_point else entry_points
    reachable = find_reachable_files(bfs_roots, metadata_map)
    reachable_set = {m.rel_path for m in reachable}
    unreachable = [m for m in metadata_map.values() if m.rel_path not in reachable_set]

    print(f"  [analyzer] Reachable: {len(reachable)} | Unreachable/unused: {len(unreachable)}")

    file_tree = build_file_tree(reachable, repo_root)

    repo_models = sorted({m for meta in reachable for m in meta.model_ids})
    hint_set = {hint for meta in reachable for hint in meta.sys_path_hints}
    external_models_by_hint = _collect_external_models(repo_root, hint_set)
    external_models = sorted({m for models in external_models_by_hint.values() for m in models})
    detected_models = sorted(set(repo_models + external_models))

    return RepoAnalysis(
        repo_root=repo_root,
        primary_entry_point=primary_entry_point,
        entry_points=entry_points,
        reachable_files=reachable,
        unreachable_files=unreachable,
        file_tree=file_tree,
        all_metadata=metadata_map,
        detected_models=detected_models,
        external_models_by_hint=external_models_by_hint,
    )
