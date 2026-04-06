import os
import subprocess
import shutil

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_AGENT_DIR, "..", "..", ".."))
OUTPUT_DIR = os.path.join(_WORKSPACE_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Default PowerPoint template (.pptx)
TEMPLATE_FILE = os.path.join(_AGENT_DIR, "template", "nice_template.pptx")

# Output file path for the generated presentation
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "project_presentation.pptx")

# ─────────────────────────────────────────────
# Diagram Generation (mmdc)
# ─────────────────────────────────────────────
def find_mmdc():
    """
    Find mermaid-cli (mmdc) command in system PATH.
    
    Detection order (portable, no hardcoded usernames):
    1. Check system PATH for 'mmdc' command
    2. Check npm global directory on Windows (dynamically)
    3. Fallback: return 'mmdc' and let subprocess try PATH
    
    Returns: path to mmdc executable or 'mmdc' (if PATH-resident)
    """
    # First, try to find in system PATH
    mmdc_path = shutil.which('mmdc')
    if mmdc_path:
        return mmdc_path
    
    # Windows-specific: check npm global directory dynamically
    if os.name == 'nt':  # Windows
        try:
            # Get npm prefix dynamically (no hardcoded username)
            result = subprocess.run(
                ['npm', 'config', 'get', 'prefix'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                npm_prefix = result.stdout.strip()
                # Try both .cmd and bare executable
                for cmd_variant in ['.cmd', '']:
                    mmdc_candidate = os.path.join(npm_prefix, 'mmdc' + cmd_variant)
                    if os.path.exists(mmdc_candidate):
                        return mmdc_candidate
        except Exception:
            pass
    
    # Fallback: return 'mmdc' and rely on PATH lookup
    return 'mmdc'

# Cached mmdc executable path (resolved at import time)
MMDC_CMD = find_mmdc()

# ─────────────────────────────────────────────
# LLM / Bedrock
# ─────────────────────────────────────────────
AWS_REGION = "us-west-2"
INFERENCE_PROFILE = (
    "arn:aws:bedrock:us-west-2:934137132601:inference-profile/"
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)
LLM_MAX_TOKENS = 20000
LLM_TEMPERATURE = 0.2
