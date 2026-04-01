import os
import json
from generate_ppt import create_ppt
from diagram_generator import generate_architecture_diagram
from config import TEMPLATE_FILE, OUTPUT_FILE

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_AGENT_DIR, "..", "..", ".."))
PRESENTATION_DATA_FILE = os.path.join(_WORKSPACE_ROOT, "presentation_data.json")
LEGACY_PRESENTATION_DATA_FILE = os.path.join(_AGENT_DIR, "presentation_data.json")


def _get_presentation_data_path():
    """Prefer workspace-root slide data, fall back to agent directory."""
    if os.path.exists(PRESENTATION_DATA_FILE):
        return PRESENTATION_DATA_FILE
    if os.path.exists(LEGACY_PRESENTATION_DATA_FILE):
        return LEGACY_PRESENTATION_DATA_FILE
    return PRESENTATION_DATA_FILE


def _load_pregenerated_slides():
    """Load pre-generated slide JSON written by the Copilot agent."""
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


def run_agent(template_path=TEMPLATE_FILE):
    """
    Build a PowerPoint presentation from agent-generated artifacts.

    Pipeline:
      Agent Phase 1 → validates / writes README.md
      Agent Phase 2 → writes presentation_data.json + architecture_*.mmd
      This script   → renders .mmd → PNG, then builds .pptx
    """
    pregenerated = _load_pregenerated_slides()
    if not pregenerated:
        print("✗ presentation_data.json not found.")
        print("  Run the Copilot agent phases first to generate the required artifacts.")
        return False

    slides = pregenerated.get("slides", [])
    project_title = pregenerated.get("project_title", "Project Presentation")
    print(f"\n[1/3] Using pre-generated slides ({len(slides)} slides, title: '{project_title}')")

    print("\n[2/3] Rendering architecture diagrams...")
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


# Run the agent
if __name__ == "__main__":
    run_agent()