# PPT Expert Setup README (Agent-Driven)

## Scope
This document describes the current operating model for the PPT Expert agent and aligns with:
- .github/agents/ppt-expert.agent.md

## Operating Model: Two Parts
The workflow is split into two parts.

### Part A: README Validation and Generation
Part A includes:
- Phase 1: README validation
- Phase 2: README generation or refresh (only if needed)

Part A output:
- output/README.md

Part A rules:
- Jira or Atlassian MCP tools are not used in Part A.
- If a Jira key is present in the initial prompt, it is ignored until Part B.
- Part A must complete before any PPT work starts.

### Part B: PPT Creation
Part B includes:
- Phase 3: slide JSON and Mermaid source generation
- Phase 4: PPT build

Part B outputs:
- output/presentation_data.json
- output/architecture_system.mmd
- output/architecture_dataflow.mmd
- output/project_presentation.pptx

## Part A Completion Gate (Mandatory)
After output/README.md is ready:
1. Report Part A completion in chat.
2. Ask this exact question:
   README is ready. Do you want me to proceed with PPT creation (Part B)?
3. Start Part B only after explicit user approval.

Prompt mechanism:
- Preferred: interactive prompt via vscode_askQuestions with options:
  - Yes, proceed to Part B
  - No, stop after Part A
- Fallback: typed yes or no in chat if interactive options are not rendered in the current UI.

## ZIP Extraction Naming Convention (Mandatory)
When extracting an attached ZIP, use the ZIP filename (without .zip) as the extraction folder name.

Example:
- process-pdf-diagrams-with-readme.zip -> process-pdf-diagrams-with-readme

Rules:
- Do not use generic names such as extracted_project or zip_extracted.
- If the target folder already exists, overwrite or recreate that same deterministic folder.
- Use this extracted folder as the project root for README discovery and analysis.

## Part A Details

### Phase 1: README Validation
Goal:
- Decide whether an existing README is strong enough for downstream presentation generation.

README discovery order:
1. README inside attached repository or extracted ZIP contents
2. output/README.md in workspace
3. Any README discovered while analyzing repository structure

Validation checks (8):
1. Problem solved and business value
2. High-level system behavior
3. Target users and use cases
4. Major modules or architecture components
5. Inputs and outputs
6. Setup or execution guidance
7. Dependencies/config/models/cloud/runtime assumptions
8. Sufficient depth for limitations, risks, roadmap slides

Decision rule:
- PASS if at least 6/8 checks pass
- FAIL if fewer than 6/8 checks pass
- Immediate FAIL if critical areas are missing:
  - project purpose
  - end-to-end flow
  - major components/modules

Chat output required:
- README path evaluated
- Score out of 8
- Passed checks
- Failed checks
- Final decision: reference or regenerate

Branching:
- PASS: copy/reference to output/README.md and complete Part A
- FAIL/missing: run Phase 2 to generate output/README.md

### Phase 2: README Generation or Refresh
Goal:
- Produce output/README.md only when validation fails or no acceptable README exists.

Expected behavior:
- Fully analyze Python source files
- Document architecture, modules, setup, usage, configuration, outputs, and tech stack
- Write final content to output/README.md

## Part B Details

### Phase 3: Slide JSON and Mermaid Generation
Input source of truth:
- output/README.md

Outputs written in output/:
- output/presentation_data.json
- output/architecture_system.mmd
- output/architecture_dataflow.mmd

Optional Jira enrichment in Part B only:
- mcp_com_atlassian_getJiraIssue
- mcp_com_atlassian_searchJiraIssuesUsingJql
- mcp_com_atlassian_getAccessibleAtlassianResources

If Jira is unavailable, slide generation continues from README-only context.

### Phase 4: Build Presentation
Command:
- python .github/agents/ppt-expert/main.py

Build behavior:
1. Load output/presentation_data.json
2. Attempt Mermaid render (.mmd to .png)
3. Build PPT from slides and any rendered diagram images
4. Save output/project_presentation.pptx

Mermaid failure behavior (validated):
- If mmdc is missing or Mermaid render fails, PPT generation still proceeds.
- Result: deck is created without diagram image slides.

## Tools and Runtime Setup
Python dependencies used by implementation:
- python-pptx
- boto3 (only fallback diagram generation path)
- standard library modules such as json, os, subprocess, datetime

External tool:
- mermaid-cli (mmdc) for .mmd to .png rendering

Template assets:
- .github/agents/ppt-expert/template/nice_template.pptx

## Atlassian MCP Setup (Part B Only)
Use this only when user requests Jira-enriched slides.

Steps:
1. Install or use an available Atlassian MCP integration in VS Code/Copilot tools.
2. Authenticate through OAuth when prompted.
3. Verify access using mcp_com_atlassian_getAccessibleAtlassianResources.
4. Use returned cloud ID for Jira calls.

Primary Jira tools:
- mcp_com_atlassian_getJiraIssue
- mcp_com_atlassian_searchJiraIssuesUsingJql

If unavailable:
- Skip Jira enrichment and continue with README-only slide generation.

## Mermaid CLI (mmdc) Setup
Install on Windows PowerShell:
1. Install Node.js LTS.
2. Install Mermaid CLI globally:
   npm install -g @mermaid-js/mermaid-cli
3. Verify:
   mmdc --version

Troubleshooting commands:
- mmdc -i output/architecture_system.mmd -o output/architecture_system.png
- mmdc -i output/architecture_dataflow.mmd -o output/architecture_dataflow.png

Common issues:
- mmdc not found: restart terminal or add npm global bin to PATH
- timeout: retry and validate Mermaid syntax
- blank output: simplify graph labels and rerun

## Files Used in This Setup
Agent definition:
- .github/agents/ppt-expert.agent.md

Pipeline scripts:
- .github/agents/ppt-expert/main.py
- .github/agents/ppt-expert/generate_ppt.py
- .github/agents/ppt-expert/diagram_generator.py
- .github/agents/ppt-expert/config.py

Generated artifacts in output/:
- output/README.md
- output/presentation_data.json
- output/architecture_system.mmd
- output/architecture_dataflow.mmd
- output/architecture_system.png
- output/architecture_dataflow.png
- output/project_presentation.pptx

## Quick Execution
1. Complete Part A and produce output/README.md.
2. Confirm approval to start Part B.
3. Generate slide JSON and Mermaid files.
4. Run python .github/agents/ppt-expert/main.py.
5. Verify output/project_presentation.pptx.
