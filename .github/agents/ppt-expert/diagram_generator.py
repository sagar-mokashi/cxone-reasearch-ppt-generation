import json
import subprocess
import os
import boto3
from config import MMDC_CMD, INFERENCE_PROFILE

# Paths to pre-generated Mermaid files (written by the Copilot agent in Phase 2)
_SYSTEM_MMD = 'architecture_system.mmd'
_DATAFLOW_MMD = 'architecture_dataflow.mmd'


def generate_architecture_diagram(business_summary):
    """
    Render architecture diagrams to PNG.

    Preferred path: use pre-generated .mmd files written by the Copilot agent.
    Fallback path:  call Bedrock LLM to generate Mermaid code (requires AWS).

    Returns list of rendered PNG file paths.
    """
    # ── Preferred: render existing .mmd files written by the Copilot agent ──
    pregenerated_mmds = {
        'system_architecture': _SYSTEM_MMD,
        'data_flow': _DATAFLOW_MMD,
    }
    if os.path.exists(_SYSTEM_MMD) or os.path.exists(_DATAFLOW_MMD):
        print("\n  → Using pre-generated Mermaid files from Copilot agent...")
        mermaid_code = {}
        for key, mmd_file in pregenerated_mmds.items():
            if os.path.exists(mmd_file):
                # Accept UTF-8 files with or without BOM from different generators.
                with open(mmd_file, 'r', encoding='utf-8-sig') as f:
                    mermaid_code[key] = f.read()
        return _render_diagrams(mermaid_code)

    # ── Fallback: generate via Bedrock (requires business_summary + AWS) ────
    if not business_summary:
        print("  ✗ No Mermaid files found and no business summary provided")
        return []

    print("\n  → Analyzing architecture from README (Bedrock fallback)...")
    mermaid_code = extract_architecture_with_llm(business_summary)
    if not mermaid_code:
        print("  ✗ Could not generate architecture diagram")
        return []
    return _render_diagrams(mermaid_code)


def _render_diagrams(mermaid_code):
    """Render a dict of Mermaid code strings to PNG files via mmdc."""
    # Save and render Mermaid diagrams to PNG
    diagram_files = []

    diagram_map = [
        ('system_architecture', 'architecture_system.mmd',    'architecture_system.png',    'system architecture'),
        ('data_flow',           'architecture_dataflow.mmd',  'architecture_dataflow.png',  'data flow'),
    ]

    for key, mermaid_file, png_file, label in diagram_map:
        code = mermaid_code.get(key)
        if not code:
            continue

        # Write .mmd only if it wasn't already provided by the agent
        if not os.path.exists(mermaid_file):
            with open(mermaid_file, 'w', encoding='utf-8') as f:
                f.write(code)

        print(f"  → Rendering {label} diagram...")
        if render_with_mmdc(mermaid_file, png_file):
            diagram_files.append(png_file)
            print(f"  ✓ Created {label}: {png_file}")
        else:
            print(f"  ✗ Failed to render {label}")

    return diagram_files


def render_with_mmdc(mermaid_file, png_file):
    """
    Render Mermaid diagram using mermaid-cli (mmdc) command line tool.
    Creates professional architectural diagrams.
    
    mmdc path is resolved dynamically from config (no hardcoded usernames).
    """
    try:
        # mmdc path resolved at import time from config.py (portable, cross-platform)
        mmdc_cmd = MMDC_CMD
        
        # Verify mmdc is available
        try:
            result = subprocess.run(
                [mmdc_cmd, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                print("  Error: mermaid-cli not found in PATH")
                return False
        except FileNotFoundError:
            print("  Error: mermaid-cli not available (mmdc not on PATH)")
            print("  Install with: npm install -g @mermaid-js/mermaid-cli")
            return False
        
        # Use mmdc to convert mermaid to PNG
        result = subprocess.run(
            [mmdc_cmd, '-i', mermaid_file, '-o', png_file],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and os.path.exists(png_file):
            return True
        else:
            if result.stderr:
                print(f"  mmdc error: {result.stderr[:100]}")
            return False
    except subprocess.TimeoutExpired:
        print("  Error: mermaid-cli timeout")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def extract_architecture_with_llm(business_summary):
    """
    Use LLM to extract architecture and generate Mermaid diagrams
    """
    prompt = f"""
You are an architecture diagram expert. Analyze the following project information and generate Mermaid diagrams.

Create TWO diagrams in Mermaid syntax:

1. SYSTEM ARCHITECTURE (graph TD - top down)
   - Show main components/modules/services
   - Show connections/dependencies between them
   - Keep it simple and business-focused (5-8 main components)

2. DATA FLOW (flowchart TD)
   - Show how data/requests flow through the system
   - Include main processes/steps
   - Show decision points if applicable

IMPORTANT RULES:
- Use valid Mermaid syntax only
- Keep diagrams clean and readable
- Use meaningful component names
- Maximum 8-10 nodes per diagram
- Focus on HIGH-LEVEL architecture, not implementation details

Return ONLY valid JSON (no other text) with this structure:

{{
  "system_architecture": "graph TD\\n    A[Component1] --> B[Component2]\\n    ...",
  "data_flow": "flowchart TD\\n    Start[Input] --> Process[Processing]\\n    ..."
}}

Project Information:
{business_summary}
"""

    try:
        client = boto3.client("bedrock-runtime", region_name="us-west-2")
        
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 20000,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
        })
        
        response = client.invoke_model(
            modelId=INFERENCE_PROFILE,
            body=body,
            contentType="application/json"
        )
        
        result = json.loads(response["body"].read())
        content = result.get("content", [{}])[0].get("text", "")
        
        if not content:
            return generate_fallback_diagrams()
        
        # Parse JSON response
        try:
            diagrams = json.loads(content)
            return diagrams
        except json.JSONDecodeError:
            # Try to extract JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return generate_fallback_diagrams()
    
    except Exception as e:
        print(f"  Warning: LLM error ({e}), using fallback diagrams")
        return generate_fallback_diagrams()


def generate_fallback_diagrams():
    """Generate basic fallback diagrams"""
    return {
        "system_architecture": """graph TD
    A[User Interface] --> B[Application Layer]
    B --> C[Business Logic]
    C --> D[Data Layer]
    D --> E[Database]
    B --> F[External APIs]
    C --> G[Processing Engine]""",
        
        "data_flow": """flowchart TD
    Start([User Input]) --> Validate{Valid?}
    Validate -->|Yes| Process[Process Request]
    Validate -->|No| Error[Return Error]
    Process --> Execute[Execute Logic]
    Execute --> Store[Store Results]
    Store --> Response([Return Response])"""
    }

