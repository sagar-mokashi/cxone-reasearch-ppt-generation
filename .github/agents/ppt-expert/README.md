# PPT Expert Setup README (Agent-Driven)

## Scope
This README is generated from the agent contract defined in:
- .github/agents/ppt-expert.agent.md

It documents how the setup is expected to run, phase by phase, and which files are used.

## Agent MD Reference
Primary specification source:
- .github/agents/ppt-expert.agent.md

Supporting implementation files:
- .github/agents/ppt-expert/main.py
- .github/agents/ppt-expert/generate_ppt.py
- .github/agents/ppt-expert/diagram_generator.py
- .github/agents/ppt-expert/config.py

## End-to-End Phases
The agent contract defines 4 phases.

### Phase 1: README Validation
Goal:
- Decide whether an existing README is strong enough to support PPT generation.

Discovery order:
1. README inside attached repository or extracted ZIP
2. Workspace root README
3. Any README discovered while analyzing repository structure

Validation checks (exactly 8):
1. Problem solved and why it matters
2. High-level system behavior
3. Target users or use cases
4. Major modules, workflow stages, or architecture components
5. Primary inputs and outputs
6. Setup or execution guidance
7. Dependencies, configuration, models, cloud/runtime assumptions
8. Enough detail for limitations, risks, and roadmap slides

Decision rules:
- PASS if score is at least 6 out of 8
- FAIL if score is below 6 out of 8
- FAIL immediately if any critical area is missing:
  - project purpose
  - end-to-end flow
  - major components/modules

Required validation output in chat:
- README path evaluated
- Score out of 8
- Passed checks
- Failed checks
- Final decision: reference or regenerate

Branching behavior:
- If PASS: use that README as reference and proceed to phase 3
- If FAIL or missing: run phase 2 to generate root README

### Phase 2: README Generation or Refresh
Goal:
- Produce root README.md only if phase 1 fails or no valid README exists.

Expected behavior:
- Analyze Python source files fully
- Document architecture, modules, setup, usage, configuration, outputs, stack
- Save as workspace root README.md

### Phase 3: Slide JSON and Mermaid Generation
Input source of truth:
- Workspace root README.md

Outputs written at workspace root:
- presentation_data.json
- architecture_system.mmd
- architecture_dataflow.mmd

Slide structure target:
- 9 business-facing slides from project overview through roadmap

### Phase 4: Build Presentation
Command:
- python .github/agents/ppt-expert/main.py

Build behavior:
1. Load presentation_data.json
2. Render Mermaid to PNG via mmdc
3. Build PPT using template
4. Save project_presentation.pptx

## Tools and Runtime Setup
Python dependencies used by implementation:
- python-pptx
- boto3 (diagram fallback path)
- standard library modules such as json, os, subprocess, datetime

External tool:
- mermaid-cli (mmdc) for .mmd to .png rendering

MCP integrations:
- Atlassian MCP tools (used for optional Jira enrichment in phase 3)

Template assets:
- .github/agents/ppt-expert/template/nice_template.pptx
- .github/agents/ppt-expert/template/thank_you.pptx

## Atlassian MCP Setup
This setup supports optional Jira enrichment in phase 3 through Atlassian MCP tools referenced in the agent contract.

Tools expected by the flow:
- mcp_com_atlassian_getJiraIssue
- mcp_com_atlassian_searchJiraIssuesUsingJql
- mcp_com_atlassian_getAccessibleAtlassianResources

**Installation (recommended via VS Code Marketplace):**
1. Install the Atlassian MCP extension from VS Code Extensions Marketplace: **@mcp atlassian**
2. The extension auto-registers with OAuth 2.1 authentication (no manual mcp.json entry needed)
3. Reload VS Code when prompted to activate the extension
4. First call to an Atlassian MCP tool will trigger OAuth browser sign-in
5. Verify access by calling `mcp_com_atlassian_getAccessibleAtlassianResources` from Copilot chat

**Alternative (manual mcp.json configuration):**
If you prefer explicit config, use the command palette: **MCP: Open Workspace Configuration**

Example manual config (if needed):
```json
{
  "servers": {
    "pptx": {
      "command": "python",
      "args": ["-m", "pptx_mcp.server"]
    },
    "atlassian": {
      "command": "npx",
      "args": ["-y", "@atlassian/mcp-server"]
    }
  }
}
```

**Validation checklist:**
- mcp_com_atlassian_getAccessibleAtlassianResources returns ≥1 Jira/Confluence cloud instances
- mcp_com_atlassian_getJiraIssue succeeds for a known issue key (e.g., CEAR-6084)
- mcp_com_atlassian_searchJiraIssuesUsingJql returns child stories or linked issues

**If Atlassian MCP is unavailable or JIRA ticket is missing:**
- Phase 3 still runs from README-only content
- Jira enrichment is skipped gracefully (as defined in agent contract)
- Presentation generation completes without Jira context

## Mermaid CLI (mmdc) Setup
This setup requires mermaid-cli to render architecture_system.mmd and architecture_dataflow.mmd into PNG files.

Install on Windows (PowerShell):
1. Install Node.js LTS if not installed.
2. Install Mermaid CLI globally:
   npm install -g @mermaid-js/mermaid-cli
3. Verify installation:
   mmdc --version

Optional fallback check (path used by this workspace code):
- C:\Users\sagarm\AppData\Roaming\npm\mmdc.cmd --version

Manual render commands for troubleshooting:
- mmdc -i architecture_system.mmd -o architecture_system.png
- mmdc -i architecture_dataflow.mmd -o architecture_dataflow.png

Expected outputs:
- architecture_system.png
- architecture_dataflow.png

Common mmdc issues and fixes:
- "mermaid-cli not found": restart terminal or add npm global bin to PATH
- timeout during render: retry command and validate Mermaid syntax in .mmd file
- blank image: simplify graph labels and re-run mmdc

## Files Used in This Setup
Agent definition:
- .github/agents/ppt-expert.agent.md

Pipeline scripts:
- .github/agents/ppt-expert/main.py
- .github/agents/ppt-expert/generate_ppt.py
- .github/agents/ppt-expert/diagram_generator.py
- .github/agents/ppt-expert/config.py

Generated artifacts in workspace root:
- README.md
- presentation_data.json
- architecture_system.mmd
- architecture_dataflow.mmd
- architecture_system.png
- architecture_dataflow.png
- project_presentation.pptx

## Phase 1 Validation Record (Current Run)
Validation performed against:
- .github/agents/ppt-expert/cxone-cxmo-orchestrator-discovery-ai-engine-extracted/README.md

Recorded result:
- Score: 8 out of 8
- Decision: reference
- Critical areas present: yes

Why this matters:
- Confirms that README validation details are explicitly captured in setup documentation.
- Provides traceability to the exact file and decision rule from the agent contract.

## Execution Quick Steps
1. Ensure presentation_data.json and architecture_*.mmd exist at workspace root.
2. Run: python .github/agents/ppt-expert/main.py
3. Verify output: project_presentation.pptx

## Sample Agent Input
Example Copilot or Agent prompt:
```
Create ppt for #file:cxone-customer-journey-data-generation.zip and use context from jira epic CEAR-6084 to generate the slides
```

This will:
1. Extract and analyze the ZIP file
2. Validate or generate a README documenting the project
3. Fetch Jira epic CEAR-6084 for business context enrichment
4. Generate 9 business-facing slides with architecture diagrams
5. Create project_presentation.pptx with embedded diagrams
