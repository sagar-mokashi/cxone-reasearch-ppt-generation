# Workflow Inference from Process PDF Diagrams

## 1. Project Overview

This project enables automated extraction of customer journey and business process workflows from PDF documents containing process diagrams (SVG format). Using advanced AI vision capabilities, the system analyzes diagram images to identify workflow stages, decision points, and process flows—converting visual diagrams into structured, machine-readable JSON representations. This is critical for organizations that need to digitize manual process documentation, analyze process improvements, and feed workflow data into business process management systems. The solution targets data scientists and process engineers who work with BPMN (Business Process Model and Notation) diagrams and need to convert them to actionable workflow metadata without manual transcription.

**High-level system function:** Ingest PDF files containing workflow diagrams, automatically extract the diagram images, analyze them with AI vision models, identify all workflow nodes and connections (including decision gates), and output structured JSON workflow metadata with support for complex decision logic and branching.

**Target users:** Data Scientists, Business Process Engineers, Enterprise Architects, AI/Copilot development teams (specifically Orch AI team).

**Primary inputs and outputs:** 
- **Input:** PDF files containing BPMN or process flow diagrams in SVG format (e.g., "AR Workflow - Future State.pdf")
- **Output:** Structured JSON workflow definitions with node metadata, decision gates, and connection descriptions (e.g., "workflow_json/AR_Workflow_workflow.json")

**AI Services:** AWS Bedrock with Claude Sonnet 4.5 or Claude Opus 4.5 vision models for diagram analysis and Mermaid code generation.

**Differentiation:** Unlike naive image-to-text OCR or simple diagram extraction, this solution implements a two-stage extraction pipeline that separates vision-based arrow/node detection from code generation, reducing hallucination and improving accuracy on complex BPMN diagrams with decision gates and loop-backs.

## 2. Key Features & Capabilities

- **Multi-page PDF Processing:** Automatically detects and processes only workflow diagram pages, skipping text-heavy content pages without manual configuration.
- **BPMN Diagram Support:** Recognizes BPMN-compliant shapes (rectangles for tasks, diamonds for gateways with inner symbols, circles for events) and correctly classifies decision nodes regardless of inner icons.
- **Two-Stage Extraction Pipeline:** Stage 1 extracts natural language descriptions of nodes and arrows (vision task); Stage 2 converts descriptions to Mermaid flowchart code (code generation task), significantly reducing AI hallucination compared to single-stage approaches.
- **Mermaid Code Generation:** Automatically generates valid Mermaid flowchart syntax from diagram images, enabling visualization and downstream automation.
- **Decision Gate Logic:** Identifies and preserves decision points with conditional branches (e.g., Yes/No paths, success/failure flows).
- **Loop-Back Detection:** Traces curved and backward-pointing arrows to capture iterative processes and loops within workflows.
- **Image Enhancement for Vision Models:** Applies minimal contrast and sharpness optimization to preserve shape clarity while reducing noise.
- **PDF Image Extraction:** Renders PDF pages at 300 DPI for high-quality diagram analysis, supporting large multi-page documents.
- **Workflow JSON Output:** Converts extracted diagrams to structured JSON format with node metadata, descriptions, and hierarchical workflow structure.
- **Error Handling & Validation:** Validates that pages contain actual workflows before processing, skips invalid diagrams, and provides detailed processing logs.
- **Configurable DPI & Image Resizing:** Handles large images by automatically resizing while preserving aspect ratio and limiting dimensions to prevent API failures.

## 3. Pipeline Architecture

The system follows a five-stage processing pipeline:

**Stage 1: PDF Ingestion & Validation** – The entry point loads a PDF file and iterates through pages. For each page, a validation check (using drawings density analysis and image detection) determines whether the page contains a workflow diagram or text content. Invalid pages are skipped.

**Stage 2: Image Extraction & Enhancement** – Valid workflow pages are rendered as PNG images at 300 DPI (high quality). Minimal image enhancement (contrast boost, light sharpening) is applied to improve clarity for vision models while preserving shape integrity. Images are resized if they exceed 8,000×8,000 pixels to comply with API limits.

**Stage 3: Vision-Based Diagram Analysis (Stage 1 LLM Call)** – Each enhanced image is sent to AWS Bedrock (Claude Sonnet/Opus) with a specialized prompt. The AI analyzes the diagram's visual structure and outputs natural language descriptions of all nodes (type, label, position) and arrows (source, target, labels/conditions). This stage separates visual perception from code generation.

**Stage 4: Mermaid Code Generation (Stage 2 LLM Call)** – The natural language descriptions from Stage 3 are converted to valid Mermaid flowchart syntax. The LLM reconstructs the complete flow, ensures all loop-backs and decision branches are included, and outputs compilable Mermaid code.

**Stage 5: Workflow JSON Conversion & Output** – The Mermaid code is parsed alongside the original image Base64 encoding to extract workflow metadata. Nodes are identified, decision gates are marked, and the entire workflow is serialized to JSON format with descriptions, node types, and connections. Multiple workflows (multi-page PDFs) are saved with page-specific filenames.

```
PDF Input
   ↓
Page Iteration & Validation
   ├─→ [Valid Page] → Image Extraction @ 300 DPI
   │   ├─→ Image Enhancement (Contrast, Sharpness)
   │   ├─→ Resize if > 8000x8000px
   │   ├─→ Base64 Encode for API
   │   ↓
   │   AWS Bedrock (Claude Sonnet/Opus - Vision)
   │   ├─→ Stage 1: Extract Nodes & Arrows (Natural Language)
   │   │   └─→ Output: NODE_1: RECTANGLE "Start Process"
   │   │       Output: NODE_1 → NODE_2 |condition|
   │   ↓
   │   Generate Mermaid Code (Stage 2)
   │   ├─→ Parse Natural Language Descriptions
   │   ├─→ Trace Connections & Loop-Backs
   │   └─→ Output: flowchart TD
   │           A[Start] → B{Decision?}
   │           B -->|Yes| C[Process]
   │           B -->|No| A
   │
   └─→ [Invalid Page] → Skip, Log
   
   ↓
Extract Workflow Metadata
├─→ Parse Mermaid for Node Structure
├─→ Identify Decision Gates
├─→ Extract Node Labels & Descriptions
↓
Serialize to JSON Workflow Format
├─→ workflow_name, description, nodes[], connections[]
├─→ Handle Multiple Workflows (Page N → File N)
↓
JSON Output Files
└─→ workflow_json/Filename_page_X_workflow.json
```

**Stage 1: PDF Validation** – Analyzes page structure (drawing density, shape count, embedded images) to determine if page is a workflow diagram.

**Stage 2: Image Rendering** – Extracts pages at 300 DPI and returns PNG file paths for valid diagrams.

**Stage 3: Image Enhancement** – Applies minimal contrast and sharpness boost to improve diagram clarity without distorting connections.

**Stage 4: Base64 Encoding** – Converts image to Base64 for AWS Bedrock API payload, with automatic resizing for oversized images.

**Stage 5: Vision Analysis (Two Stages)** – AWS Bedrock Claude model analyzes image and outputs natural language node/arrow descriptions, then generates Mermaid code.

**Stage 6: Workflow JSON Conversion** – Parses Mermaid code and image analysis to extract metadata, decision nodes, and connections into structured JSON format.

**Stage 7: File Output** – Saves each workflow to a separate JSON file with automatic page numbering for multi-page PDFs.

## 4. Prerequisites & Setup

**Python Version:** Python 3.8 or higher

**AWS Configuration:**
- AWS Account with Bedrock access (us-west-2 region)
- Bedrock inference profile for Claude Sonnet (`arn:aws:bedrock:us-west-2:<account-id>:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0`) or Claude Opus
- AWS credentials configured via environment variables or AWS configuration file (`~/.aws/credentials`)

**Installation:**
```bash
pip install boto3 botocore PyMuPDF Pillow opencv-python numpy uuid img2pdf
```

**Directory Structure Required:**
```
project/
├── pdf_images/              # Place input PDF files here
├── extracted_images/        # Auto-generated: PNG renderings of workflow pages
├── workflow_json/           # Auto-generated: JSON output files
├── entry_point.py           # Main orchestrator script
├── handle_process_doc_pdf_with_image.py
├── pdf_image_conversion.py
├── create_mermaid_from_image.py
├── two_stage_mermaid_extraction.py
└── requirements.txt
```

**Environment Variables:**
- `AWS_ACCESS_KEY_ID` – AWS access key
- `AWS_SECRET_ACCESS_KEY` – AWS secret key
- Ensure region is set to `us-west-2` in boto3 client initialization

## 5. Project Structure

```
workflow-inference-process-pdf-diagrams/
├── entry_point.py                       — Main orchestrator; manages PDF processing pipeline, validation, and file output coordination
├── handle_process_doc_pdf_with_image.py — PDF extraction, text/image recovery, AWS Bedrock client setup, image resizing; provides image_base64_encoder and PDF analysis utilities
├── pdf_image_conversion.py              — PDF-to-image rendering at 300 DPI; page-level workflow diagram detection; image enhancement (contrast, sharpness)
├── create_mermaid_from_image.py         — Bedrock integration for Mermaid code generation; uses Claude Vision to extract flowchart syntax from diagram images
├── two_stage_mermaid_extraction.py      — Two-stage extraction pipeline: Stage 1 (natural language node/arrow extraction) and Stage 2 (Mermaid code generation); BPMN shape classification
├── count_tokens_for_pdf.py              — Utility for estimating token cost of diagram processing
├── image_to_pdf.py                      — Optional utility for converting extracted images back to PDF (not used in main pipeline)
├── requirements.txt                     — Python dependencies and AWS SDK requirements
├── pdf_images/                          — Input directory for source PDF files containing workflow diagrams
├── extracted_images/                    — Auto-generated directory for 300 DPI PNG renderings of workflow pages
├── workflow_json/                       — Auto-generated directory for output JSON workflow definitions
├── old_code/                            — Legacy implementation code (not used; kept for reference)
└── __pycache__/                         — Python bytecode cache
```

## 6. Module Descriptions

### entry_point.py
**Purpose:** Main orchestrator for the entire workflow extraction pipeline. Coordinates all processing stages: PDF loading, page iteration, validation, image extraction, LLM calls, and JSON output.

**Key Functions:**
- `main()` – Master orchestration loop that processes each page, calls validation, enhancement, and LLM extraction functions, and saves output JSON files.

**Dependencies:** Imports all utility modules (`pdf_image_conversion`, `handle_process_doc_pdf_with_image`, `create_mermaid_from_image`, `two_stage_mermaid_extraction`).

**Pipeline Role:** Entry point called by user; invokes entire processing chain from PDF ingestion through JSON output.

**Notable Implementation Details:**
- Configurable PDF filename in code (e.g., `pdf_name = "AR Workflow - Future State.pdf"`)
- Output filenames automatically include page numbers for multi-workflow PDFs
- Tracks valid workflow pages and provides success/failure summary at end

### handle_process_doc_pdf_with_image.py
**Purpose:** Provides low-level PDF extraction utilities and AWS Bedrock client initialization. Handles image encoding, PDF text extraction, embedded image recovery, and image resizing.

**Key Functions:**
- `image_base64_encoder(image_path)` – Converts image file to Base64 and detects format (PNG/JPEG); applies adaptive resizing for large images (max 8,000×8,000 px).
- `extract_text_from_pdf(pdf_path)` – Extracts all text from PDF using PyMuPDF.
- `extract_images_from_pdf(pdf_path, output_dir)` – Extracts embedded images from PDF (if they exist).
- `check_pdf_has_images(pdf_path)` – Detects presence and count of embedded images.
- `resize_image_if_needed(img, max_dim)` – Resizes PIL Image to meet API dimension limits while preserving aspect ratio.
- `bedrock_client` – Boto3 client initialized for AWS Bedrock API in us-west-2 region.

**Dependencies:** PyMuPDF (fitz), Pillow (PIL), boto3.

**Pipeline Role:** Called by all other modules for image encoding, AWS client, and PDF utilities; central hub for AWS integration.

**Notable Implementation Details:**
- AWS region hardcoded to us-west-2
- Image resizing uses LANCZOS filter for quality preservation
- Bedrock client uses inference profile ARN for Claude model selection

### pdf_image_conversion.py
**Purpose:** Converts PDF pages to high-resolution PNG images and detects which pages contain workflow diagrams vs. text content. Applies minimal enhancement for vision model optimization.

**Key Functions:**
- `extract_pages_as_images(pdf_path, output_dir, dpi)` – Renders each page to PNG at specified DPI (default 300); returns list of file paths.
- `is_workflow_diagram_page(page)` – Analyzes PyMuPDF page object to detect workflow diagrams using drawing density, shape count, and image embedding heuristics.
- `enhance_workflow_image(image_path)` – Applies minimal enhancement (contrast +20%, sharpness +10%) to improve clarity without distortion.

**Dependencies:** PyMuPDF (fitz), Pillow (PIL).

**Pipeline Role:** Called by entry_point after initial validation; produces enhanced PNG files for LLM vision analysis.

**Notable Implementation Details:**
- Uses 300 DPI zoom factor (zoom = 300/72)
- Drawing density threshold for diagram detection: > 0.5 or > 10 objects
- Preserves color information in images (does not convert to binary)
- Minimal enhancement settings to preserve original diagram structure

### create_mermaid_from_image.py
**Purpose:** Uses AWS Bedrock Claude vision models to analyze workflow diagram images and generate Mermaid flowchart code. Implements detailed extraction prompts to minimize AI hallucination.

**Key Functions:**
- `generate_mermaid_from_image(file_type, image_base64)` – Sends Base64-encoded image to Claude with specialized prompt; returns Mermaid flowchart code.
- `extract_workflow_from_mermaid_and_image(mermaid_code, file_type, image_base64)` – Parses Mermaid output and image to extract structured workflow items (nodes, connections).
- `convert_items_to_workflow_json_with_decisions(items, workflow_name, mermaid_code)` – Converts extracted items to final JSON workflow format with decision node support.
- `extract_workflow_name_from_stage1(stage1_output)` – Parses Stage 1 natural language output to extract workflow name and description.

**Dependencies:** boto3, PyMuPDF (fitz), Pillow (PIL), handle_process_doc_pdf_with_image.

**Pipeline Role:** Called by entry_point after image enhancement; performs LLM inference for Mermaid extraction.

**Notable Implementation Details:**
- Uses Claude Sonnet 4.5 inference profile (default) with option to swap for Opus
- Temperature set to 0.0 for deterministic extraction
- Max tokens set to 10,000 for detailed output
- Includes anti-hallucination rules in prompt (no inference, no guessing connections)

### two_stage_mermaid_extraction.py
**Purpose:** Implements two-stage extraction pipeline to separate vision-based node/arrow detection (Stage 1) from code generation (Stage 2). Reduces hallucination by avoiding single-stage LLM overload.

**Key Functions:**
- `stage1_extract_arrows(file_type, image_base64)` – First LLM call: analyzes image and outputs natural language descriptions of all nodes (type, label) and arrows (source, target, labels).
- `stage2_generate_mermaid(stage1_output)` – Second LLM call: converts Stage 1 descriptions to valid Mermaid flowchart code; ensures all loop-backs and branches are included.
- `is_valid_workflow_page(image_path)` – Validates whether a page image contains a workflow diagram (alternative to pdf_image_conversion version).
- `extract_mermaid_two_stage(image_path)` – Orchestrates both stages and returns both outputs (mermaid_code, stage1_output).

**Dependencies:** boto3, handle_process_doc_pdf_with_image.

**Pipeline Role:** Called by entry_point as alternative or replacement for single-stage extraction; provides two LLM calls instead of one.

**Notable Implementation Details:**
- Stage 1 focuses on BPMN shape classification: rectangles (tasks), diamonds (gateways with inner symbols), circles (events)
- Stage 2 ensures all visible arrows are included and no connections are invented
- Both stages use temperature 0.0 for deterministic output
- Supports loop-back detection with explicit backward arrow validation

## 7. How to Run

**Basic Execution:**
```bash
cd workflow-inference-process-pdf-diagrams
python entry_point.py
```

**Step-by-Step Setup from Clean Environment:**
1. **Clone/Extract Project:** Extract the workflow-inference-process-pdf-diagrams.zip file to a local directory.
2. **Install Dependencies:** Run `pip install -r requirements.txt` (Python 3.8+).
3. **Configure AWS Credentials:** Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables or configure `~/.aws/credentials`.
4. **Prepare Input PDF:** Place your workflow PDF in the `pdf_images/` directory (e.g., `pdf_images/AR_Workflow.pdf`).
5. **Update entry_point.py:** Change the `pdf_name` variable to match your input file:
   ```python
   pdf_name = "AR Workflow - Future State.pdf"  # Change this to your file
   ```
6. **Run:** Execute `python entry_point.py`.
7. **View Output:** Check `workflow_json/` directory for JSON files and `extracted_images/` for page renderings.

**Realistic Usage Examples:**

**Example 1: Basic AR Workflow Processing**
```bash
# Input: pdf_images/AR_Workflow - Future State.pdf (3 pages, 2 workflow diagrams)
python entry_point.py
# Output: 
#   - extracted_images/page_1_workflow.png
#   - extracted_images/page_2_workflow.png
#   - workflow_json/AR_Workflow_page1_workflow.json
#   - workflow_json/AR_Workflow_page2_workflow.json
```

**Example 2: Multi-Page Service Request Workflow**
```bash
# Input: pdf_images/Service_Request_Workflow.pdf (5 pages, 4 workflows)
pdf_name = "Service_Request_Workflow.pdf"
python entry_point.py
# Output: 4 separate JSON files, one per workflow detected across pages
```

**Example 3: Complex BPMN Diagram with Decision Gates**
```bash
# Input: pdf_images/Complex_Process.pdf (1 page with BPMN diagram)
pdf_name = "Complex_Process.pdf"
python entry_point.py
# Output: workflow_json/Complex_Process_workflow.json with full decision logic
# Example JSON: {"nodes": [{"id": "gateway_1", "type": "decision", "label": "Is Valid?"}], 
#              "connections": [{"source": "gateway_1", "target": "process_a", "condition": "Yes"}]}
```

**Expected Console Output (Successful Run):**
```
================================================================================
Processing: extracted_images/page_1_workflow.png (Page 1)
================================================================================

 Validating page content...
Generated Mermaid:
flowchart TD
A[Start] --> B{Decision?}
B -->|Yes| C[Process]
B -->|No| D[Cancel]
C --> E[End]

================================================================================

Workflow Name: AR Process Workflow
Workflow Description: Handles approval requests with decision gates
Items extracted: 5

================================================================================

[OK] Workflow JSON saved to workflow_json/AR_Workflow_page1_workflow.json

[SUCCESS] Processing complete - 1 workflow(s) extracted from pages: [1]
```

**Expected Runtime:** 15–45 seconds per page (depends on diagram complexity and AWS latency). A 3-page PDF with 2 workflows typically completes in 30–60 seconds.

**Common Failure Modes:**
- **"No valid workflow diagrams found"** – PDF contains only text pages or no diagrams; add actual workflow diagram pages.
- **AWS Authentication Error** – `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` not set; configure credentials.
- **Image Size Error** – Diagram image exceeds API limits; code auto-resizes but verify image is not > 50MB before encoding.
- **Bedrock Model Unavailable** – Inference profile ARN incorrect or region not us-west-2; verify Bedrock access in correct region.
- **Mermaid Parsing Error** – LLM output is not valid Mermaid syntax; check Claude model is Sonnet/Opus with vision support.

## 8. Configuration & Customization

**High-Impact Parameters:**

| Parameter | Location | Default | Effect |
|-----------|----------|---------|--------|
| `pdf_name` | entry_point.py, line ~12 | "AR Workflow - Future State.pdf" | Input PDF filename; must match file in pdf_images/ directory |
| `dpi` | pdf_image_conversion.py, extract_pages_as_images() | 300 | PDF rendering resolution; higher = more detail but slower processing and larger files |
| `region_name` | handle_process_doc_pdf_with_image.py, line ~19 | "us-west-2" | AWS region for Bedrock; must be region where models are available |
| `INFERENCE_PROFILE` | create_mermaid_from_image.py, line ~53 | Claude Sonnet 4.5 | LLM model selection; options: Claude Sonnet 4.5, Claude Opus 4.5, Claude Haiku 4.5 |
| `temperature` | create_mermaid_from_image.py, two_stage_mermaid_extraction.py | 0.0 | LLM creativity; 0.0 = deterministic (recommended), higher = more creative/risky |
| `max_tokens` | create_mermaid_from_image.py | 10,000 | Max output length for LLM; increase if truncated outputs occur |
| `max_dim` | handle_process_doc_pdf_with_image.py, resize_image_if_needed() | 8,000 | Maximum image dimension before resizing; API limit is typically 8,000×8,000 px |

**Customization Examples:**

**Use a Different AI Model:**
```python
# In create_mermaid_from_image.py, line ~53:
# Current:
INFERENCE_PROFILE = f"arn:aws:bedrock:us-west-2:934137132601:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Change to Claude Opus (more powerful, more expensive):
INFERENCE_PROFILE = f"arn:aws:bedrock:us-west-2:934137132601:inference-profile/us.anthropic.claude-opus-4-5-20251101-v1:0"

# Or Claude Haiku (faster, cheaper, less accurate):
INFERENCE_PROFILE = f"arn:aws:bedrock:us-west-2:934137132601:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0"
```

**Process PDFs Containing Only Text (No Diagrams):**
```python
# In pdf_image_conversion.py, is_workflow_diagram_page():
# Reduce threshold to accept more pages:
has_many_shapes = rect_count > 3  # Lower from 5
has_connecting_lines = line_count > 1  # Lower from 3
```

**Process Diagrams from a Different Document Format:**
To support other formats (e.g., images, Office documents):
1. Create a new file extraction function (e.g., `extract_from_image_folder()` for pre-converted PNGs).
2. Insert outputs directly into the two-stage extraction pipeline.
3. Skip PDF-specific processing stages.

**Change Output Directory:**
```python
# In entry_point.py, line ~50:
output_file = f"custom_output_folder/{filename}_page{page_num}_workflow.json"  # Change from "workflow_json/"
```

## 9. Output & Results

**Output File Types & Locations:**

| File Type | Path Pattern | Purpose |
|-----------|-------------|---------|
| Enhanced Diagram Images | extracted_images/page_N_workflow.png | 300 DPI PNG renderings of valid workflow pages; used for documentation or visual reference |
| Workflow JSON | workflow_json/Filename_page_N_workflow.json | Structured workflow metadata; primary deliverable |
| Processing Logs | Console output | Diagnostic info: validation results, LLM outputs, file paths, success/failure status |

**JSON Output Schema Example:**
```json
{
  "workflow_name": "AR Approval Request Workflow",
  "description": "Handles approval routing with escalation for high-value requests",
  "nodes": [
    {
      "id": "start_1",
      "type": "start",
      "label": "Start",
      "position": "top"
    },
    {
      "id": "process_1",
      "type": "process",
      "label": "Validate Request",
      "position": "middle"
    },
    {
      "id": "decision_1",
      "type": "decision",
      "label": "Amount > $5000?",
      "position": "middle"
    },
    {
      "id": "end_1",
      "type": "end",
      "label": "Approved",
      "position": "bottom"
    }
  ],
  "connections": [
    {
      "source": "start_1",
      "target": "process_1",
      "label": null,
      "type": "forward"
    },
    {
      "source": "process_1",
      "target": "decision_1",
      "label": null,
      "type": "forward"
    },
    {
      "source": "decision_1",
      "target": "end_1",
      "label": "Yes",
      "type": "conditional"
    },
    {
      "source": "decision_1",
      "target": "process_1",
      "label": "No",
      "type": "loop-back"
    }
  ]
}
```

**JSON Field Descriptions:**
- `workflow_name` – Human-readable name extracted from diagram or title
- `description` – Brief narrative of workflow purpose
- `nodes[]` – Array of workflow stages/tasks/decisions; each has `id`, `type` (start/process/decision/end), `label`, position
- `connections[]` – Array of arrows between nodes; `source` and `target` are node IDs, `label` is condition (e.g., "Yes", "No"), `type` indicates flow direction
- Relationship: A node is a stage in the workflow; a connection is a directed arrow between two stages

**Intermediate Files (Safe to Delete):**
- **extracted_images/page_*.png** – Can be deleted after JSON generation is complete; only needed for LLM processing and visual reference
- **__pycache__/** – Python cache; auto-regenerated if deleted

**How to Interpret Output:**
Each JSON file represents one complete workflow. The `nodes` array lists all stages (from start to end). The `connections` array shows the order and conditions under which stages execute. Decision nodes have multiple outgoing connections with different labels (Yes/No/Approve/Reject); the `type: "conditional"` indicates branching logic. Loop-back connections (with `type: "loop-back"`) indicate iterative processes that return to previous stages.

Example interpretation: A workflow with 5 nodes and 6 connections represents a process with a decision gate that either moves forward or loops back to an earlier step.

## 10. Technology Stack

| Technology | Version/Provider | Purpose in Project | Dependency Type |
|------------|------------------|-------------------|-----------------|
| Python | 3.8+ | Core runtime language; all scripts are Python-based | Hard dependency |
| AWS Bedrock | Latest (inference profiles) | Cloud AI service providing Claude Vision models for diagram analysis | Hard dependency |
| Claude (Sonnet/Opus) | 4.5 series | Vision and code generation models; analyzes PDF diagrams and generates Mermaid | Hard dependency |
| boto3 | 1.26+ | AWS SDK; handles Bedrock API calls and authentication | Hard dependency |
| PyMuPDF (fitz) | 1.20+ | PDF parsing and page rendering; extracts pages as high-resolution images | Hard dependency |
| Pillow (PIL) | 9.0+ | Image processing; enhancement, resizing, encoding (JPEG/PNG) | Hard dependency |
| OpenCV (cv2) | 4.5+ | Advanced image analysis; edge detection, morphology operations (used in validation) | Hard dependency |
| NumPy | 1.20+ | Numerical operations; image matrix operations, density calculations | Hard dependency |
| uuid | Built-in | Generates unique identifiers for workflow elements | Optional (built-in) |
| img2pdf | 1.4+ | Converts extracted images back to PDF (not used in primary flow) | Optional |

**Specific Roles in Pipeline:**
- **boto3 + Bedrock + Claude:** Core AI extraction engine; processes diagram images and generates Mermaid code
- **PyMuPDF + Pillow:** PDF and image handling; enables rendering and encoding for LLM input
- **OpenCV + NumPy:** Page validation; analyzes drawing density to detect workflow diagrams
- **uuid:** Generates unique node IDs in JSON output (if needed for enterprise integration)
