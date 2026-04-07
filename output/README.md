# Workflow Discovery and Clustering Pipeline

## Overview

This project is an **AI-powered workflow discovery system** designed to analyze contact center call transcripts and automatically identify, normalize, and cluster business workflows and task sequences. It uses Large Language Models (LLMs) and machine learning clustering techniques to extract meaningful operational patterns from customer service interactions.

### Primary Use Case
Analyzing contact center conversations to:
- Discover underlying business workflows
- Identify common task sequences
- Group similar workflows together
- Provide insights for process optimization and automation

---

## Key Features

1. **Workflow Extraction from Transcripts**: Uses LLMs (Claude 3.5 Sonnet via AWS Bedrock) to analyze call transcripts and extract structured workflows with task sequences
2. **Task Normalization**: Clusters similar task descriptions using semantic embeddings and hierarchical clustering
3. **Workflow Sequence Clustering**: Groups complete workflow sequences to identify common operational patterns
4. **Configurable Pipeline**: YAML-based configuration for easy customization
5. **Privacy-Aware**: Designed to exclude sensitive personal information from extracted workflows

---

## Project Structure

```
discovery/
├── entry_point.py                      # Main entry point - orchestrates the pipeline
├── config_manager.py                   # Configuration management (YAML loader)
├── extract_from_asr.py                 # Workflow extraction from ASR transcripts
├── normalize_task.py                   # Task normalization and clustering
├── cluster_task_sequences.py           # Workflow sequence clustering
├── discovery_utils.py                  # Utility functions for clustering and embeddings
├── invoke_models.py                    # AWS Bedrock model invocation wrapper
├── prompts.py                          # LLM prompt templates
├── create_workflow_type_title.py       # Workflow title generation (WIP)
└── resources/
    ├── config.yaml                     # Configuration file
    └── Output/                         # Generated results directory
```

---

## Architecture & Pipeline Flow

### High-Level Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                     WORKFLOW DISCOVERY PIPELINE                      │
└─────────────────────────────────────────────────────────────────────┘

  ┌────────────────────┐
  │   Input Data       │
  │  • ASR Transcripts │
  │  • Intent Metadata │
  └─────────┬──────────┘
            │
            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  PHASE 1: WORKFLOW EXTRACTION (extract_from_asr.py)         │
  ├─────────────────────────────────────────────────────────────┤
  │  • Load interaction data with intent classifications        │
  │  • Sample transcripts (stratified by intent)                │
  │  • Parse ASR files → Generate transcript strings            │
  │  • Invoke LLM to extract:                                   │
  │    - Workflow name                                          │
  │    - Task sequence                                          │
  │    - Analysis                                               │
  │  • Output: df_summary (DataFrame with workflows & tasks)    │
  └─────────────────────┬───────────────────────────────────────┘
                        │
                        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  PHASE 2: TASK NORMALIZATION (normalize_task.py)            │
  ├─────────────────────────────────────────────────────────────┤
  │  • Flatten all task descriptions                            │
  │  • Filter out verification/review tasks                     │
  │  • Generate embeddings (Sentence Transformers)              │
  │  • Hierarchical clustering (Agglomerative)                  │
  │  • Find representative task for each cluster                │
  │  • Create task lookup mapping                               │
  │  • Output: reverse_clusters (task → cluster mapping)        │
  └─────────────────────┬───────────────────────────────────────┘
                        │
                        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  PHASE 3: WORKFLOW SEQUENCE CLUSTERING                      │
  │             (cluster_task_sequences.py)                     │
  ├─────────────────────────────────────────────────────────────┤
  │  • Map tasks to normalized cluster names                    │
  │  • Create sequence strings (e.g., "Task A, Task B, Task C") │
  │  • Filter invalid workflows                                 │
  │  • Generate embeddings for sequences                        │
  │  • Hierarchical clustering on sequences                     │
  │  • Find representative workflow for each cluster            │
  │  • Output: JSON with workflow clusters                      │
  └─────────────────────┬───────────────────────────────────────┘
                        │
                        ▼
  ┌────────────────────────────────────┐
  │   Output Artifacts                 │
  ├────────────────────────────────────┤
  │  • Excel: Raw workflow detections  │
  │  • JSON: Task clusters             │
  │  • JSON: Workflow sequence clusters│
  │  • Pickle: Intermediate data       │
  └────────────────────────────────────┘
```

---

## Detailed Component Description

### 1. Configuration Management (`config_manager.py`)

**Purpose**: Centralized configuration management using YAML

**Key Components**:
- `ConfigurationManager`: Singleton class that loads and provides access to configuration
- Properties for paths (ASR directory, output directory, embedder model)
- Data parameters (distance thresholds, top-n values)

**Configuration Example**:
```yaml
paths:
  asr_dir_path: "/path/to/asr/files"
  output_dir_path: "/path/to/output"
  input_intents_file: "/path/to/intents.csv"
  embedder_path: "/path/to/embedding/model"
```

---

### 2. Workflow Extraction (`extract_from_asr.py`)

**Purpose**: Extract structured workflows from raw call transcripts using LLMs

**Algorithm**:
1. **Load Intent Data**: Reads CSV with interaction IDs and intent classifications (level1, level2, level3)
2. **Sample Selection**: 
   - Groups by level3 intent
   - Takes highest rank interaction per ID
   - Random samples 20 (configurable) per intent group
3. **Transcript Parsing**:
   - Reads ASR CSV files (tab-separated)
   - Combines phrases by speaker channel (Agent/Customer)
   - Generates conversation transcript
4. **LLM Workflow Extraction**:
   - Uses Claude 3.5 Sonnet via AWS Bedrock
   - Prompt includes transcript + intent metadata
   - Extracts JSON with:
     - `workflow`: 2-3 word workflow name
     - `tasks`: Ordered list of task descriptions (3-4 words each)
     - `analysis`: Detailed explanation
5. **Output**: Excel file + DataFrame with all extracted workflows

**Key Constraints** (from prompt):
- Only actual performed actions (not explanations)
- No verification/confirmation tasks
- Privacy-aware: No sensitive information in output
- Rejects inquiry-only workflows

---

### 3. Task Normalization (`normalize_task.py`)

**Purpose**: Group similar task descriptions into semantic clusters

**Algorithm**:
1. **Task Collection**:
   - Flatten all task arrays from workflows
   - Filter out invalid/unknown tasks
   - Remove verification/review tasks (prefixes: verify, locate, review)

2. **Embedding Generation**:
   - Use Sentence Transformer model (bge-base-en-v1.5)
   - Convert tasks to normalized embeddings

3. **Hierarchical Clustering**:
   - Algorithm: Agglomerative Clustering
   - Linkage: Complete
   - Metric: Cosine similarity
   - Distance threshold: 0.2 (configurable)

4. **Cluster Naming**:
   - For each cluster, find centroid in embedding space
   - Select task closest to centroid as representative

5. **Quality Scoring**:
   - Use DBCV (Density-Based Cluster Validation) metric
   - Scores cluster quality based on density and separation

6. **Output**: 
   - JSON with cluster mappings: `{cluster_name: [task1, task2, ...]}`
   - Reverse mapping: `{task: cluster_name}`

---

### 4. Workflow Sequence Clustering (`cluster_task_sequences.py`)

**Purpose**: Group complete workflow sequences to find common operational patterns

**Algorithm**:
1. **Task Sequence Normalization**:
   - Replace individual tasks with their normalized cluster names
   - Create sequence strings: "Normalized Task A, Normalized Task B, ..."

2. **Filtering**:
   - Remove workflows with "No identifiable workflow"
   - Remove empty or Unknown-only sequences

3. **Embedding & Clustering**:
   - Encode sequences using Sentence Transformer
   - Agglomerative clustering with cosine similarity
   - Distance threshold: 0.15 (configurable)

4. **Representative Selection**:
   - Find centroid of each workflow cluster
   - Select sequence closest to centroid as representative

5. **Output**:
   - JSON with workflow clusters and frequency counts
   - Format: `{representative_workflow: {workflow1: count1, workflow2: count2, ...}}`

---

### 5. Utility Functions (`discovery_utils.py`)

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `filter_tasks()` | Remove verification/review tasks |
| `cluster_and_score()` | Perform hierarchical clustering + DBCV scoring |
| `find_cluster_name()` | Find representative element for each cluster |
| `create_cluster_mappings()` | Create bidirectional cluster mappings |
| `pickle_data()` / `unpickle_data()` | Serialize intermediate results |
| `cosine_distance_matrix()` | Compute pairwise cosine distances |

---

### 6. LLM Invocation (`invoke_models.py`)

**Purpose**: Wrapper for AWS Bedrock model invocation

**Supported Models**:
- Claude 3.5 Sonnet (us.anthropic.claude-3-5-sonnet-20241022-v2:0)
- Claude 3 Haiku
- Claude Sonnet 3.7 & 4
- Amazon Nova Lite & Micro

**Features**:
- Handles authentication via boto3
- Temperature: 0.0 (deterministic)
- Error handling (throttling, access denied, validation)
- Latency tracking
- Token usage monitoring

---

## Algorithm Details

### Hierarchical Clustering Strategy

**Why Agglomerative Clustering?**
- **Advantage**: No need to predefine number of clusters
- **Distance Threshold**: Controls granularity automatically
- **Linkage Method**: Complete linkage ensures compact clusters
- **Metric**: Cosine similarity captures semantic meaning

**Tuning Parameters**:
| Parameter | Task Normalization | Workflow Clustering |
|-----------|-------------------|---------------------|
| Distance Threshold | 0.2 | 0.15 |
| Linkage | Complete | Complete |
| Metric | Cosine | Cosine |

### Embedding Model

**Model**: `bge-base-en-v1.5` (BGE - BAAI General Embedding)
- **Dimensions**: 768
- **Normalization**: L2 normalized embeddings
- **Advantages**: 
  - Strong semantic understanding
  - Optimized for sentence-level embeddings
  - Good performance on similarity tasks

### Quality Metrics

**DBCV (Density-Based Cluster Validation)**:
- Measures both cluster density and separation
- Range: [-1, 1], higher is better
- Score < 0 indicates poor clustering
- Used to evaluate clustering quality automatically

---

## Prompt Engineering

The system uses carefully designed prompts (in `prompts.py`) for workflow extraction:

**Key Prompt Components**:
1. **Context**: Domain explanation (contact center, travel technology)
2. **Constraints**:
   - Execution Rule: Only performed actions
   - Task Relevance: No verification/confirmation tasks
   - Privacy: Exclude all sensitive information
3. **Output Format**: Strict JSON schema
4. **Examples**: Few-shot learning with good/bad examples

**Prompt Versions**:
- `WorkflowDetectionIntent`: Main prompt with intent metadata
- `WorkflowDetectionNoAnalysis`: Lightweight version without analysis
- `WorkflowDetectionMultiTranscripts`: Batch processing variant

---

## Installation & Setup

### Prerequisites
```bash
# Python 3.8+
pip install pandas
pip install scikit-learn
pip install sentence-transformers
pip install torch
pip install boto3
pip install pyyaml
pip install tqdm
pip install kDBCV
```

### AWS Configuration
Ensure AWS credentials are configured:
```bash
aws configure
# Provide your AWS Access Key ID, Secret Access Key, and region
```

### Configuration
Edit `resources/config.yaml`:
```yaml
paths:
  asr_dir_path: "/path/to/your/asr/files"
  output_dir_path: "/path/to/output"
  input_intents_file: "/path/to/intents.csv"
  embedder_path: "/path/to/embedding/model"
```

---

## Usage

### Running the Full Pipeline

```bash
python entry_point.py
```

**Pipeline Execution**:
1. Generates workflows from ASR transcripts
2. Pickles intermediate results
3. Loads data and embedding model
4. Normalizes tasks into clusters
5. Clusters workflow sequences
6. Saves all results to output directory

### Output Files

| File | Description |
|------|-------------|
| `Refactored_Orcherstrator_WorkflowDetector_results.xlsx` | Raw workflow extractions with tasks |
| `orcherstrator_norm_clusters_0.2.json` | Task normalization clusters |
| `orcherstrator_task_seq_clusters_0.15.json` | Workflow sequence clusters |
| `pickle_wf_discover.dat` | Intermediate data for resumption |

---

## Data Flow Example

### Input
```csv
interaction_id,rank,level1,level2,level3,distance
12345,5,Service,Modification,Name Change,0.23
```

### Phase 1 Output (Workflow Extraction)
```json
{
  "workflow": "Name Correction",
  "tasks": [
    "Customer requested name correction",
    "Verify customer identity",
    "Update name in system",
    "Send confirmation email"
  ],
  "analysis": "..."
}
```

### Phase 2 Output (Task Normalization)
```json
{
  "Update customer information": [
    "Update name in system",
    "Update customer details",
    "Modify customer record"
  ]
}
```

### Phase 3 Output (Workflow Clustering)
```json
{
  "Customer requested name correction, Update customer information, Send confirmation": {
    "Customer requested name correction, Update name in system, Send confirmation email": 15,
    "Customer requested profile update, Update customer information, Send notification": 8
  }
}
```

---

## Customization

### Adjusting Clustering Thresholds
In `normalize_task.py`:
```python
distance_threshold = 0.2  # Lower = more clusters, Higher = fewer clusters
```

In `cluster_task_sequences.py`:
```python
distance_thresholds = [0.15]  # Can test multiple values
```

### Filtering Task Types
In `discovery_utils.py`:
```python
def filter_tasks(task_list):
    prefixes = ['verify', 'locate', 'review', 'Verify', 'Locate', 'Review']
    # Add more prefixes to filter
    return [task for task in task_list if not any(task.startswith(prefix) for prefix in prefixes)]
```

### Changing LLM Model
In `extract_from_asr.py`:
```python
modelId = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"  # Change to desired model
```

---

## Performance Considerations

### Scalability
- **LLM Calls**: Rate limited by AWS Bedrock (throttling)
- **Embedding Generation**: Batched for efficiency
- **Clustering**: O(n²) for distance matrix computation

### Optimization Tips
1. **Caching**: Use pickle files to avoid re-running phases
2. **Sampling**: Reduce sample size in `extract_from_asr.py`
3. **Batch Processing**: Process transcripts in batches
4. **Model Selection**: Use faster models (Nova Micro) for initial testing

---

## Error Handling

### Common Issues

1. **AWS Throttling**: Implement exponential backoff
2. **Invalid JSON from LLM**: Retry with cleaned prompt
3. **Empty Clusters**: Adjust distance thresholds
4. **Memory Issues**: Process data in chunks

### Debugging
Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Future Enhancements

1. **Workflow Title Generation**: Complete `create_workflow_type_title.py`
2. **Interactive UI**: Slider for distance threshold adjustment
3. **Task Category Filtering**: Enable filtering by task categories
4. **Multi-language Support**: Extend to non-English transcripts
5. **Real-time Processing**: Stream processing for live calls
6. **Quality Metrics Dashboard**: Visualize clustering quality

---

## Dependencies

```txt
pandas>=1.3.0
scikit-learn>=0.24.0
sentence-transformers>=2.0.0
torch>=1.9.0
boto3>=1.18.0
pyyaml>=5.4.0
tqdm>=4.60.0
kDBCV>=0.1.0
botocore>=1.21.0
```

---

## License

[Specify your license here]

---

## Contact & Support

[Add contact information or support channels]

---

## Acknowledgments

- **Embedding Model**: BGE (BAAI General Embedding)
- **LLM Provider**: AWS Bedrock (Anthropic Claude)
- **Clustering**: scikit-learn
- **Validation**: kDBCV library

---

## Changelog

### Version 1.0 (Current)
- Initial implementation
- Three-phase pipeline
- Claude 3.5 Sonnet integration
- Hierarchical clustering
- Task normalization
- Workflow sequence clustering

