import os
import sys
import json
from generate_ppt import create_ppt
from read_zip import extract_repo
from readme_parser import find_readme, parse_readme, create_business_summary
from diagram_generator import generate_architecture_diagram
from config import TEMPLATE_FILE, OUTPUT_FILE

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_AGENT_DIR, "..", "..", ".."))
PRESENTATION_DATA_FILE = os.path.join(_WORKSPACE_ROOT, "presentation_data.json")
LEGACY_PRESENTATION_DATA_FILE = os.path.join(_AGENT_DIR, "presentation_data.json")


def _get_presentation_data_path():
    """Prefer workspace-root slide data, but keep the legacy path readable."""
    if os.path.exists(PRESENTATION_DATA_FILE):
        return PRESENTATION_DATA_FILE
    if os.path.exists(LEGACY_PRESENTATION_DATA_FILE):
        return LEGACY_PRESENTATION_DATA_FILE
    return PRESENTATION_DATA_FILE


def _load_pregenerated_slides():
    """Load pre-generated slide JSON written by the Copilot agent (Phase 2)."""
    presentation_data_path = _get_presentation_data_path()
    if not os.path.exists(presentation_data_path):
        return None
    try:
        # Use utf-8-sig so both BOM and non-BOM UTF-8 JSON files parse cleanly.
        with open(presentation_data_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if data.get("slides"):
            print(f"✓ Loaded pre-generated slides from: {presentation_data_path}")
            return data
    except Exception as e:
        print(f"⚠ Could not read {presentation_data_path}: {e}")
    return None


def run_agent(zip_path=None, template_path=TEMPLATE_FILE):
    """
    Main function to generate a business-focused presentation.

    Preferred pipeline (Copilot-native, no Bedrock):
      Agent Phase 1 → README.md
      Agent Phase 2 → presentation_data.json + architecture_*.mmd
      This script  → renders diagrams + builds .pptx

    Fallback pipeline (legacy, requires AWS Bedrock):
      Extract ZIP → find/generate README → call LLM for slides + diagrams → build .pptx
    """
    # ── Fast path: pre-generated data from Copilot agent ────────────────────
    pregenerated = _load_pregenerated_slides()
    if pregenerated:
        slides = pregenerated.get("slides", [])
        project_title = pregenerated.get("project_title", "Project Presentation")
        print(f"\n[1/3] Using pre-generated slides ({len(slides)} slides, title: '{project_title}')")

        print("\n[2/3] Rendering architecture diagrams...")
        # Pass None as business_summary — diagram_generator will use existing .mmd files
        diagram_files = generate_architecture_diagram(None)
        if diagram_files:
            print(f"✓ Rendered {len(diagram_files)} diagram(s)")
        else:
            print("⚠ No diagrams rendered")

        print("\n[3/3] Creating PowerPoint presentation...")
        success = create_ppt(slides, diagram_files, output_file=OUTPUT_FILE,
                             template_file=template_path, project_title=project_title)
        if success:
            print("\n" + "="*50)
            print("✓ SUCCESS! Presentation created")
            print(f"  Output: {OUTPUT_FILE}")
            print("="*50)
        else:
            print("\n✗ Failed to create presentation")
        return success

    # ── Fallback path: legacy Bedrock pipeline ───────────────────────────────
    if not zip_path:
        print("✗ No presentation_data.json found and no ZIP path provided.")
        print("  Run the Copilot agent phases first, or supply a ZIP path.")
        return False

    from call_ppt_llm import generate_slides
    from repo_analyzer import analyze_repo
    from readme_generator import generate_readme, save_readme

    print(f"Processing (legacy Bedrock path): {zip_path}")
    if template_path:
        print(f"Using template: {template_path}")

    print("\n[1/6] Extracting repository...")
    repo_path = extract_repo(zip_path)
    print(f"✓ Extracted to: {repo_path}")

    print("\n[2/6] Looking for README file...")
    readme_path = find_readme(repo_path)
    if not readme_path:
        print("⚠ README.md not found — generating one via Bedrock...")
        analysis = analyze_repo(repo_path)
        readme_content = generate_readme(analysis)
        generated_readme_path = os.path.join(repo_path, "README.md")
        save_readme(readme_content, generated_readme_path)
        readme_path = generated_readme_path
        print(f"✓ Generated README saved to: {readme_path}")
    print(f"✓ Found: {readme_path}")

    print("\n[3/6] Analyzing README for business insights...")
    sections = parse_readme(readme_path)
    business_summary = create_business_summary(sections)
    print(f"✓ Extracted {len([s for s in sections.values() if s])} key sections")

    print("\n[4/6] Generating presentation slides via Bedrock...")
    result = generate_slides(business_summary)
    if not result or not result.get("slides"):
        print("✗ Failed to generate slides")
        return False
    slides = result.get("slides", [])
    project_title = result.get("project_title", "Project Presentation")
    print(f"✓ Generated {len(slides)} slides — '{project_title}'")

    print("\n[5/6] Generating architecture diagrams via Bedrock...")
    diagram_files = generate_architecture_diagram(business_summary)
    if diagram_files:
        print(f"✓ Generated {len(diagram_files)} diagram(s)")
    else:
        print("⚠ No diagrams generated")

    print("\n[6/6] Creating PowerPoint presentation...")
    success = create_ppt(slides, diagram_files, output_file=OUTPUT_FILE,
                         template_file=template_path, project_title=project_title)
    if success:
        print("\n" + "="*50)
        print("✓ SUCCESS! Presentation created with diagrams")
        print("="*50)
    else:
        print("\n✗ Failed to create presentation")
    return success


# Run the agent
if __name__ == "__main__":
    # Preferred: let the agent pre-generate presentation_data.json (no ZIP needed)
    # Fallback:  pass the ZIP path for the legacy Bedrock pipeline
    run_agent()