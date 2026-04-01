"""
readme_generator.py

Takes a RepoAnalysis object (from repo_analyzer.py) and generates a
structured README.md using an LLM.

Adaptive token management:
- Small repos (<120K tokens): Full source code included
- Large repos (>120K tokens): Priority-based selection (important files get full code)
All structural information (file tree, entry points, imports) comes
from static analysis — so the README is always accurate.
"""

import json
import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError
from repo_analyzer import RepoAnalysis, FileMetadata
from config import AWS_REGION, INFERENCE_PROFILE, LLM_MAX_TOKENS, LLM_TEMPERATURE

# AWS Bedrock Configuration
MODEL_ID = INFERENCE_PROFILE
REGION = AWS_REGION

# Token budget settings
MAX_SAFE_TOKENS = 120000  # Leave room for response (200K window - 80K response buffer)
TOKENS_PER_CHAR = 0.25    # Approximate: 1 token ≈ 4 characters


# ─────────────────────────────────────────────
# Token estimation and priority scoring
# ─────────────────────────────────────────────
def _estimate_file_tokens(meta: FileMetadata) -> int:
    """Estimate token count for a file."""
    try:
        with open(meta.abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Rough estimate: 1 token ≈ 4 characters
            return int(len(content) * TOKENS_PER_CHAR) + 100  # +100 for metadata
    except Exception:
        return 1000  # Default estimate


def _calculate_priority_score(meta: FileMetadata, analysis: RepoAnalysis) -> int:
    """Calculate importance score for prioritizing files."""
    score = 0
    
    # Entry point detection
    if meta.has_main_block:
        score += 20
    if meta in analysis.entry_points:
        score += 30
    if meta == analysis.primary_entry_point:
        score += 40
    
    # CLI/interactive indicators
    if meta.has_argparse:
        score += 10
    if meta.uses_input_prompt or meta.uses_sys_argv:
        score += 8
    
    # Complexity indicators
    if len(meta.functions) > 10:
        score += 5
    if len(meta.functions) > 20:
        score += 10
    if len(meta.classes) > 3:
        score += 5
    
    # Integration points
    if meta.external_imports:
        score += 3
    if meta.sys_path_hints:
        score += 5
    if meta.model_ids:
        score += 7
    
    # Avoid test files
    if 'test' in meta.rel_path.lower():
        score -= 15
    
    return max(0, score)


# ─────────────────────────────────────────────
# Build file summaries with different detail levels
# ─────────────────────────────────────────────
def _file_summary_full(meta: FileMetadata) -> str:
    """Include FULL source code for maximum context."""
    lines = [f"\n{'='*70}"]
    lines.append(f"FILE: {meta.rel_path} [FULL SOURCE]")
    lines.append('='*70)
    
    if meta.module_docstring:
        lines.append(f"Module docstring: {meta.module_docstring}\n")
    
    try:
        with open(meta.abs_path, 'r', encoding='utf-8') as f:
            lines.append(f.read())
    except Exception as e:
        lines.append(f"[Could not read source: {e}]")
    
    lines.append('='*70 + "\n")
    return "\n".join(lines)


def _file_summary_truncated(meta: FileMetadata) -> str:
    """Include truncated source code (~80 lines)."""
    lines = [f"\nFILE: {meta.rel_path} [TRUNCATED]"]
    lines.append("-"*60)

    if meta.module_docstring:
        lines.append(f"Module docstring: {meta.module_docstring}")

    if meta.classes:
        lines.append(f"Classes: {', '.join(meta.classes)}")

    if meta.functions:
        for fn in meta.functions[:15]:
            sig = f"def {fn.name}({', '.join(fn.args)})"
            if fn.docstring:
                sig += f"  →  {fn.docstring[:120]}"
            lines.append(sig)

    lines.append("\nSOURCE CODE (first ~80 lines):")
    try:
        with open(meta.abs_path, 'r', encoding='utf-8') as f:
            source_lines = f.readlines()
            truncated_lines = []
            char_count = 0
            max_lines = 80
            max_chars = 3000
            
            for i, line in enumerate(source_lines[:max_lines]):
                if char_count + len(line) > max_chars:
                    truncated_lines.append("... [truncated for length] ...")
                    break
                truncated_lines.append(line.rstrip())
                char_count += len(line)
            else:
                if len(source_lines) > max_lines:
                    truncated_lines.append(f"... [truncated: {len(source_lines) - max_lines} more lines] ...")
            
            lines.extend(truncated_lines)
    except Exception as e:
        lines.append(f"[Could not read source: {e}]")

    return "\n".join(lines)


def _file_summary_metadata_only(meta: FileMetadata) -> str:
    """Include only metadata (no source code)."""
    lines = [f"\nFILE: {meta.rel_path} [METADATA ONLY]"]

    if meta.module_docstring:
        lines.append(f"Module docstring: {meta.module_docstring}")

    if meta.classes:
        lines.append(f"Classes: {', '.join(meta.classes)}")

    if meta.functions:
        for fn in meta.functions[:10]:
            sig = f"def {fn.name}({', '.join(fn.args)})"
            if fn.docstring:
                sig += f" → {fn.docstring[:100]}"
            lines.append(sig)

    if meta.imports:
        lines.append(f"Imports from project: {', '.join(meta.imports)}")

    if meta.external_imports:
        lines.append(f"External imports: {', '.join(meta.external_imports)}")

    if meta.has_main_block:
        lines.append("✓ Contains __main__ block")

    if meta.has_argparse:
        lines.append("✓ Uses argparse/click/typer")

    return "\n".join(lines)


def _build_llm_context(analysis: RepoAnalysis) -> str:
    """
    Build the full context string to give the LLM.
    Adaptive strategy: uses full source for small repos, priority-based for large repos.
    """
    # First, estimate total tokens needed
    file_token_estimates = [(meta, _estimate_file_tokens(meta)) 
                            for meta in analysis.reachable_files]
    total_estimated_tokens = sum(tokens for _, tokens in file_token_estimates)
    
    print(f"  [readme_gen] Estimated total tokens: {total_estimated_tokens:,}")
    
    # Decide strategy based on size
    if total_estimated_tokens < MAX_SAFE_TOKENS:
        print(f"  [readme_gen] Repo is small - using FULL source code for all files")
        return _build_full_context(analysis)
    else:
        print(f"  [readme_gen] Repo is large - using PRIORITY-BASED selection")
        return _build_priority_context(analysis, file_token_estimates)


def _build_full_context(analysis: RepoAnalysis) -> str:
    """Build context with FULL source code for all files (small repos)."""
    repo_name = os.path.basename(analysis.repo_root)
    sections = []

    sections.append(f"REPOSITORY NAME: {repo_name}")
    if analysis.primary_entry_point:
        sections.append(f"\nPRIMARY ENTRY POINT: {analysis.primary_entry_point.rel_path}")
        sections.append(
            f"RUN STYLE: argparse={analysis.primary_entry_point.has_argparse}, "
            f"sys_argv={analysis.primary_entry_point.uses_sys_argv}, "
            f"input_prompts={analysis.primary_entry_point.uses_input_prompt}"
        )
    sections.append(f"\nENTRY POINT(S): {', '.join(e.rel_path for e in analysis.entry_points)}")
    sections.append(f"\nPROJECT FILE TREE:\n{analysis.file_tree}")

    _add_external_dependency_section(sections, analysis)
    _add_model_detection_section(sections, analysis)

    sections.append("\nFILE DETAILS WITH FULL SOURCE CODE:")
    
    # Sort: entry points first, then alphabetical
    entry_paths = {e.rel_path for e in analysis.entry_points}
    ordered = sorted(
        analysis.reachable_files,
        key=lambda m: (0 if m.rel_path in entry_paths else 1, m.rel_path)
    )
    
    for meta in ordered:
        sections.append(_file_summary_full(meta))

    return "\n".join(sections)


def _build_priority_context(analysis: RepoAnalysis, file_token_estimates: list) -> str:
    """Build context with priority-based file inclusion (large repos)."""
    repo_name = os.path.basename(analysis.repo_root)
    sections = []

    sections.append(f"REPOSITORY NAME: {repo_name}")
    if analysis.primary_entry_point:
        sections.append(f"\nPRIMARY ENTRY POINT: {analysis.primary_entry_point.rel_path}")
        sections.append(
            f"RUN STYLE: argparse={analysis.primary_entry_point.has_argparse}, "
            f"sys_argv={analysis.primary_entry_point.uses_sys_argv}, "
            f"input_prompts={analysis.primary_entry_point.uses_input_prompt}"
        )
    sections.append(f"\nENTRY POINT(S): {', '.join(e.rel_path for e in analysis.entry_points)}")
    sections.append(f"\nPROJECT FILE TREE:\n{analysis.file_tree}")

    _add_external_dependency_section(sections, analysis)
    _add_model_detection_section(sections, analysis)

    # Calculate priorities
    files_with_priority = []
    for meta, token_count in file_token_estimates:
        score = _calculate_priority_score(meta, analysis)
        files_with_priority.append((score, token_count, meta))
    
    # Sort by priority (highest first)
    files_with_priority.sort(reverse=True, key=lambda x: x[0])
    
    # Allocate tokens to files based on priority
    used_tokens = 5000  # Reserve for header/footer
    file_inclusions = []
    
    for score, token_count, meta in files_with_priority:
        if used_tokens + token_count < MAX_SAFE_TOKENS:
            # Include full source
            file_inclusions.append((meta, 'full', score))
            used_tokens += token_count
        elif used_tokens + (token_count // 4) < MAX_SAFE_TOKENS:
            # Include truncated
            file_inclusions.append((meta, 'truncated', score))
            used_tokens += (token_count // 4)
        else:
            # Metadata only
            file_inclusions.append((meta, 'metadata', score))
            used_tokens += 200
    
    # Log the allocation
    full_count = sum(1 for _, mode, _ in file_inclusions if mode == 'full')
    trunc_count = sum(1 for _, mode, _ in file_inclusions if mode == 'truncated')
    meta_count = sum(1 for _, mode, _ in file_inclusions if mode == 'metadata')
    print(f"  [readme_gen] Allocation: {full_count} full, {trunc_count} truncated, {meta_count} metadata-only")
    
    sections.append("\nFILE DETAILS (PRIORITY-BASED INCLUSION):")
    sections.append(f"Note: {full_count} files with full source, {trunc_count} truncated, {meta_count} metadata-only\n")
    
    for meta, mode, score in file_inclusions:
        if mode == 'full':
            sections.append(_file_summary_full(meta))
        elif mode == 'truncated':
            sections.append(_file_summary_truncated(meta))
        else:
            sections.append(_file_summary_metadata_only(meta))

    return "\n".join(sections)


def _add_external_dependency_section(sections: list, analysis: RepoAnalysis):
    """Helper to add external dependency information."""
    external_paths = sorted({hint for m in analysis.reachable_files for hint in m.sys_path_hints})
    external_imports = sorted({imp for m in analysis.reachable_files for imp in m.external_imports})

    if external_paths or external_imports:
        sections.append("\nEXTERNAL DEPENDENCY HINTS:")
        if external_paths:
            sections.append(f"- sys.path folders: {', '.join(external_paths)}")
        if external_imports:
            sections.append(f"- external modules: {', '.join(external_imports)}")


def _add_model_detection_section(sections: list, analysis: RepoAnalysis):
    """Helper to add model detection information."""
    if analysis.detected_models:
        sections.append("\nDETECTED MODEL IDENTIFIERS:")
        for model in analysis.detected_models:
            sections.append(f"- {model}")

    if analysis.external_models_by_hint:
        sections.append("\nEXTERNAL-HINT MODEL MAP:")
        for hint, models in sorted(analysis.external_models_by_hint.items()):
            if models:
                sections.append(f"- {hint}: {', '.join(models)}")


# ─────────────────────────────────────────────
# LLM call
# ─────────────────────────────────────────────
def _call_llm(prompt: str) -> str:
    """Call Claude via Bedrock and return the text response."""
    # Configure boto3 client with timeout and retry settings
    config = Config(
        read_timeout=300,
        retries={'max_attempts': 3, 'mode': 'adaptive'}
    )
    
    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=REGION,
            config=config,
            verify=False
        )
    except Exception as e:
        print(f"  [readme_gen] ✗ Failed to create Bedrock client: {e}")
        raise

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": LLM_MAX_TOKENS,
        "temperature": LLM_TEMPERATURE,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }
        ]
    })

    try:
        response = client.invoke_model(
            modelId=MODEL_ID,
            body=body,
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        return result.get("content", [{}])[0].get("text", "")
    except ClientError as e:
        print(f"  [readme_gen] ✗ AWS ClientError: {e.response['Error']['Message']}")
        raise
    except ReadTimeoutError as e:
        print(f"  [readme_gen] ✗ Request timeout: {e}")
        raise
    except Exception as e:
        print(f"  [readme_gen] ✗ Unexpected error during model invocation: {e}")
        raise


# ─────────────────────────────────────────────
# Prompt template
# ─────────────────────────────────────────────
README_PROMPT = """You are a senior technical architect writing comprehensive documentation for a Python project. Your goal is to create a README that serves both developers implementing the solution and stakeholders understanding its value.

You will be given:
- Repository name and structure
- Entry point file(s) with execution metadata
- Complete file tree of source files
- Detailed metadata: module docstrings, class names, function signatures, docstrings, and import relationships
- Source code for files (full source for important files, truncated for others based on priority)
- Detection of external dependencies, models, and configuration patterns

NOTE: Files are marked as [FULL SOURCE], [TRUNCATED], or [METADATA ONLY] based on their importance.
Priority files (entry points, complex modules) get full source code for maximum accuracy.

Your task is to generate a complete, well-structured README.md with EXACTLY these 10 sections, in this order:

## 1. **Project Overview**
Write a compelling 3-5 sentence overview that answers:
- What problem does this solve? (Business value)
- What does the system do? (Core functionality)
- Who is this for? (Target users/use cases)
- What makes it unique/valuable? (Key differentiator)

## 2. **Key Features & Capabilities**
List 4-8 bullet points highlighting:
- Primary features and functionality
- What makes this solution powerful/effective
- Key technical capabilities (based on detected functions/classes)
- Integration capabilities (based on external imports)

## 3. **Pipeline Architecture**
Provide a comprehensive architectural overview:
- High-level end-to-end flow (use ASCII diagram to visualize major stages)
- Key components and their interactions
- Data flow and transformations
- External dependencies and integration points
- If RUN STYLE shows argparse/CLI: describe command-line workflow
- If RUN STYLE shows input_prompts: describe interactive workflow
- If EXTERNAL DEPENDENCY HINTS exist: explicitly show where they integrate

Example ASCII diagram style:
```
[Input] → [Preprocessing] → [Core Processing] → [Post-processing] → [Output]
              ↓                    ↓                    ↓
         [Validation]      [External Service]    [Storage/Export]
```

## 4. **Prerequisites & Setup**
List all requirements for running this project:
- **Python Version:** (infer from syntax/features if possible)
- **Required Dependencies:** List key external imports with brief purpose
- **AWS/Cloud Services:** If boto3 or cloud SDKs detected, specify services needed
- **AI Models:** List detected model identifiers with usage context
- **Environment Setup:** Any sys.path adjustments or virtual environment needs
- **Access Requirements:** API keys, credentials, permissions (based on detected services)

## 5. **Project Structure**
Insert the file tree, then provide:
- One-line description for each top-level folder
- Purpose of key modules/files
- Organizational logic (why files are grouped this way)

## 6. **Module Descriptions**
For EACH file in the project, provide:
- **Purpose:** What role does this file serve? (1-2 sentences)
- **Key Functions/Classes:** List main functions with brief description of what they do (not just repeat name)
- **Dependencies:** What it imports from the project
- **Pipeline Role:** How it fits in the end-to-end flow
- **Notable Features:** Argparse, main blocks, configuration, error handling

Group by logical component/layer if applicable (e.g., "Data Processing Layer", "Integration Layer").

## 7. **How to Run**

### Basic Execution
Show the primary execution command based on PRIMARY ENTRY POINT with actual filename.

### Execution Modes
Based on RUN STYLE metadata:
- If argparse detected: Show command-line argument examples with explanations
- If sys.argv detected: Explain positional arguments
- If input_prompts=True: Explain interactive prompts user will see
- Otherwise: Note that configuration is in-file

### Example Usage
Provide 2-3 realistic usage examples with actual entry point filename and realistic arguments.

### Expected Runtime
Mention if processing is batch/streaming, estimated execution time if inferable.

## 8. **Configuration & Customization**
Document all configuration options found in code:

### Configuration Parameters
List constants, environment variables, or config objects:
- **Parameter Name:** Purpose and valid values
- **Location:** Which file contains it
- **Default Value:** If apparent from code
- **Impact:** What changing it affects

### Environment Variables
If boto3, os.getenv, or config patterns detected:
- Required vs. optional variables
- Format and examples

### Model Configuration
If AI models detected:
- Model identifiers and where they're referenced
- How to change/update models
- Performance implications

## 9. **Output & Results**
Describe what the system produces:
- **Output Files:** Paths, formats, contents (infer from save/write functions)
- **Output Structure:** Organization of results
- **Success Indicators:** How to verify successful execution
- **Storage Location:** Where outputs are saved (local, S3, database, etc.)
- **Output Format Examples:** If CSV, JSON, images, etc. are generated

## 10. **Technology Stack**

### Core Technologies
- **Language:** Python (with version if detectable)
- **Key Libraries:** List major third-party imports with purpose
  - Example: `boto3` - AWS SDK for cloud integration
  - Example: `pandas` - Data manipulation and analysis

### Cloud Services
If AWS/cloud SDKs detected:
- Specific services used (Bedrock, S3, Lambda, etc.)
- Why each service is used

### AI/ML Models
- Model identifiers detected
- Model providers (Anthropic, OpenAI, etc.)
- Use cases for each model

### External Dependencies
If EXTERNAL DEPENDENCY HINTS provided:
- Local module dependencies
- Sibling folder requirements
- External service integrations

---

CRITICAL REQUIREMENTS:
✓ Base ALL content on provided metadata - DO NOT invent features
✓ DO NOT include files not in the provided list
✓ USE THE SOURCE CODE to understand implementation details, configuration values, constants, data flows, and algorithms
✓ If EXTERNAL DEPENDENCY HINTS provided, integrate them prominently in Architecture and Prerequisites
✓ Use clear, professional language suitable for both technical and business audiences
✓ Use proper Markdown formatting throughout (##, ###, `, ```, bullet lists)
✓ Make descriptions actionable - focus on "what it does" and "why it matters"
✓ For commands, always use concrete examples (no placeholders like <file>)
✓ Extract configuration constants directly from source code when documenting Configuration section
✓ Identify actual output file paths, formats, and variable names from the source code
✓ Prioritize clarity and usability over brevity

---

REPOSITORY INFORMATION:

{context}

---

Generate the complete README.md following the 10-section structure above:
"""


def _append_external_dependency_notes(content: str, analysis: RepoAnalysis) -> str:
    """
    Ensure critical external/local-path dependencies are explicitly visible
    in the generated README even if the LLM underemphasizes them.
    """
    external_paths = sorted({hint for m in analysis.reachable_files for hint in m.sys_path_hints})
    external_imports = sorted({imp for m in analysis.reachable_files for imp in m.external_imports})

    if not external_paths and not external_imports:
        return content

    lines = [
        "",
        "### External Local Module Dependencies",
        "",
        "The codebase uses path-based imports that may come from sibling/local folders outside the extracted repo tree.",
    ]

    if external_paths:
        lines.append("")
        lines.append("**Detected `sys.path` target folders:**")
        for path in external_paths:
            lines.append(f"- `{path}`")

    if external_imports:
        lines.append("")
        lines.append("**Imported modules not present in extracted repo:**")
        for module in external_imports:
            lines.append(f"- `{module}`")

    lines.append("")
    lines.append("These modules are often required for diagram-level extraction; ensure they are available on `PYTHONPATH` or in the expected sibling directory.")

    return content.rstrip() + "\n" + "\n".join(lines) + "\n"


def _build_external_dependency_module_block(analysis: RepoAnalysis) -> str:
    """
    Build a detailed markdown block for external local dependencies so they can
    appear inside `## Module Descriptions` like first-class modules.
    """
    path_to_consumers: dict[str, set[str]] = {}
    path_to_modules: dict[str, set[str]] = {}

    for meta in analysis.reachable_files:
        if not meta.sys_path_hints:
            continue

        # Prefer likely local module names and avoid noisy stdlib/3rd-party names.
        likely_local_modules = {imp for imp in meta.external_imports if "_" in imp}

        for hint in meta.sys_path_hints:
            path_to_consumers.setdefault(hint, set()).add(meta.rel_path)
            path_to_modules.setdefault(hint, set()).update(likely_local_modules)

    if not path_to_consumers:
        return ""

    lines = [
        "",
        "### External Local Dependencies",
        "",
        "These dependencies are loaded via dynamic `sys.path.insert(...)` and are required by diagram extraction code paths.",
        "",
    ]

    for hint in sorted(path_to_consumers.keys()):
        consumers = sorted(path_to_consumers[hint])
        modules = sorted(path_to_modules.get(hint, set()))

        lines.append(f"#### `{hint}`")
        lines.append("- **Purpose:** Local sibling module set used by diagram-level workflow extraction.")
        if modules:
            lines.append(f"- **Key modules used:** {', '.join(f'`{m}`' for m in modules)}")
        else:
            lines.append("- **Key modules used:** Detected via runtime path injection; concrete module names not fully resolved from extracted repo.")
        lines.append(f"- **Used by files:** {', '.join(f'`{p}`' for p in consumers)}")
        lines.append("- **Pipeline impact:** Provides image-to-workflow validation/extraction helpers used in Phase 2 diagram processing.")
        lines.append("")

    return "\n".join(lines).rstrip()


def _is_local_like_module_name(name: str) -> bool:
    if not name:
        return False
    if "_" in name:
        return True
    return name.startswith(("create", "extract", "validate", "deduplicate", "parse", "workflow", "pdf", "mermaid"))


def _guess_external_module_purpose(module_name: str) -> str:
    lowered = module_name.lower()
    if "mermaid" in lowered:
        return "Converts/validates workflow diagrams into Mermaid flowchart structure."
    if "pdf" in lowered or "image" in lowered:
        return "Performs PDF/image preprocessing or diagram page analysis."
    if "workflow" in lowered:
        return "Provides workflow-specific extraction/validation helpers."
    return "Provides helper functionality imported dynamically via extended PYTHONPATH."


def _build_external_module_descriptions_block(analysis: RepoAnalysis) -> str:
    """
    Create file-like module descriptions for unresolved external imports
    so critical modules (e.g. two_stage_mermaid_extraction) are documented
    under Module Descriptions.
    """
    consumers_by_module: dict[str, set[str]] = {}
    hints_by_module: dict[str, set[str]] = {}

    for meta in analysis.reachable_files:
        for module_name in [m for m in meta.external_imports if _is_local_like_module_name(m)]:
            consumers_by_module.setdefault(module_name, set()).add(meta.rel_path)
            for hint in meta.sys_path_hints:
                hints_by_module.setdefault(module_name, set()).add(hint)

    if not consumers_by_module:
        return ""

    lines = ["", "### External Imported Modules"]
    for module_name in sorted(consumers_by_module.keys()):
        consumers = sorted(consumers_by_module[module_name])
        hints = sorted(hints_by_module.get(module_name, set()))
        lines.append("")
        lines.append(f"#### `{module_name}`")
        lines.append(f"- **Purpose:** {_guess_external_module_purpose(module_name)}")
        if hints:
            lines.append(f"- **Expected location:** {', '.join(f'`{h}`' for h in hints)}")
        lines.append(f"- **Imported by:** {', '.join(f'`{c}`' for c in consumers)}")
        lines.append("- **Pipeline role:** Transitive dependency from the primary entry-point execution path.")

    return "\n".join(lines).rstrip()


def _inject_external_dependency_block(content: str, analysis: RepoAnalysis) -> str:
    """
    Insert external dependency module descriptions under
    `## Module Descriptions`.
    """
    block = _build_external_dependency_module_block(analysis)
    block2 = _build_external_module_descriptions_block(analysis)
    if block2:
        block = (block + "\n\n" + block2).strip()
    if not block:
        return content

    marker = "## Module Descriptions"
    idx = content.find(marker)
    if idx == -1:
        return content.rstrip() + "\n\n" + block + "\n"

    insert_at = content.find("\n", idx)
    if insert_at == -1:
        return content.rstrip() + "\n\n" + block + "\n"

    return content[:insert_at + 1] + block + "\n" + content[insert_at + 1:]


def _inject_model_inventory_block(content: str, analysis: RepoAnalysis) -> str:
    """
    Ensure all detected model identifiers are explicitly listed in README.
    Inserts under `## Technology Stack` when present.
    """
    if not analysis.detected_models:
        return content

    lines = [
        "",
        "### Model Inventory (Auto-Detected)",
        "",
        "The following model identifiers were detected across reachable source files and external hinted folders:",
        "",
    ]
    for model in analysis.detected_models:
        lines.append(f"- `{model}`")

    if analysis.external_models_by_hint:
        lines.append("")
        lines.append("**Models detected in external hinted folders:**")
        for hint, models in sorted(analysis.external_models_by_hint.items()):
            if not models:
                continue
            lines.append(f"- `{hint}`: {', '.join(f'`{m}`' for m in models)}")

    block = "\n".join(lines).rstrip() + "\n"

    marker = "## Technology Stack"
    idx = content.find(marker)
    if idx == -1:
        return content.rstrip() + "\n\n" + block

    insert_at = content.find("\n", idx)
    if insert_at == -1:
        return content.rstrip() + "\n\n" + block

    return content[:insert_at + 1] + block + "\n" + content[insert_at + 1:]


# ─────────────────────────────────────────────
# Fallback: generate README without LLM
# ─────────────────────────────────────────────
def _generate_static_readme(analysis: RepoAnalysis) -> str:
    """
    Generate a basic README purely from static analysis output,
    used when the LLM call fails.
    """
    repo_name = os.path.basename(analysis.repo_root)
    entry_name = analysis.primary_entry_point.rel_path if analysis.primary_entry_point else "unknown"

    lines = [
        f"# {repo_name}",
        "",
        "## Project Overview",
        "*(Auto-generated README — no README found in repository)*",
        "",
        "## Pipeline Architecture",
        "*(Could not generate — LLM unavailable)*",
        "",
        "## Project Structure",
        "",
        "```",
        analysis.file_tree,
        "```",
        "",
        "## Module Descriptions",
        "",
    ]

    for meta in analysis.reachable_files:
        lines.append(f"### `{meta.rel_path}`")
        if meta.module_docstring:
            lines.append(meta.module_docstring)
        if meta.functions:
            lines.append("")
            lines.append("**Key functions:**")
            for fn in meta.functions[:8]:
                doc = f" — {fn.docstring}" if fn.docstring else ""
                lines.append(f"- `{fn.name}({', '.join(fn.args)})`{doc}")
        lines.append("")

    lines += [
        "## How to Run",
        "",
        f"```bash",
        f"python {entry_name}",
        "```",
        "",
    ]

    if analysis.primary_entry_point and analysis.primary_entry_point.uses_input_prompt:
        lines += [
            "This entry script reads values via interactive `input()` prompts.",
            "",
        ]
    elif analysis.primary_entry_point and (analysis.primary_entry_point.has_argparse or analysis.primary_entry_point.uses_sys_argv):
        lines += [
            "This entry script accepts CLI arguments (detected via argparse/sys.argv).",
            "",
        ]
    else:
        lines += [
            "This entry script runs with in-file configuration constants (no CLI args detected).",
            "",
        ]

    lines += [
        "## Configuration",
        "*(See source files for configurable constants)*",
        "",
        "## Output Files",
        "*(See source files for output paths)*",
        "",
        "## Technology Stack",
        "*(See import statements in source files)*",
    ]

    content = "\n".join(lines)
    content = _inject_external_dependency_block(content, analysis)
    content = _inject_model_inventory_block(content, analysis)
    return _append_external_dependency_notes(content, analysis)


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────
def generate_readme(analysis: RepoAnalysis) -> str:
    """
    Generate a complete README.md string from a RepoAnalysis object.

    1. Builds a compact LLM context from static analysis
    2. Calls LLM to write natural-language descriptions
    3. Falls back to static README if LLM fails

    Returns: full README.md content as a string
    """
    print("  [readme_gen] Building LLM context from analysis...")
    context = _build_llm_context(analysis)

    prompt = README_PROMPT.format(context=context)

    print("  [readme_gen] Calling LLM to generate README...")
    try:
        readme_content = _call_llm(prompt)
        if not readme_content.strip():
            raise ValueError("Empty response from LLM")
        print("  [readme_gen] ✓ README generated successfully")
        readme_content = _inject_external_dependency_block(readme_content, analysis)
        readme_content = _inject_model_inventory_block(readme_content, analysis)
        return _append_external_dependency_notes(readme_content, analysis)
    except Exception as e:
        print(f"  [readme_gen] ✗ LLM failed ({e}), using static fallback...")
        return _generate_static_readme(analysis)


def save_readme(content: str, output_path: str) -> str:
    """
    Save the generated README to disk.
    Returns the path it was saved to.
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [readme_gen] ✓ Saved to: {output_path}")
    return output_path
