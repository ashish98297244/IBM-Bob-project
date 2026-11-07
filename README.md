# AI-Powered LaTeX Diagram Generator

> **Problem Statement #26** — An intelligent agent that automatically converts natural language descriptions into professional **TikZ/LaTeX** diagrams using **IBM Watson Studio** and **IBM Granite Models**.

---

## Table of Contents
1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Setup](#setup)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Architecture](#architecture)
7. [Diagram Types Supported](#diagram-types-supported)
8. [Refinement Commands](#refinement-commands)

---

## Overview

This agent accepts plain-English diagram descriptions and produces publication-ready **TikZ** code for LaTeX documents. It supports:

- **Natural-language generation** — describe any diagram in plain English
- **Iterative refinement** — modify diagrams with conversational commands (e.g. *"make the arrows blue"*, *"add a legend"*)
- **Auto diagram-type detection** — the agent infers flowchart, neural network, state machine, etc.
- **Granite-powered validation** — the model self-reviews generated code for syntax errors
- **Session history** — every iteration is saved; all versions are preserved

---

## Project Structure

```
AI-agent/
├── main.py                          # Interactive CLI entry point
├── env.example                      # Template for environment variables
├── requirements.txt
├── outputs/                         # Generated .tex files land here
└── latex_diagram_agent/
    ├── config.py                    # Centralised config loader
    ├── core/
    │   ├── diagram_agent.py         # Orchestrator (generate / refine loop)
    │   ├── granite_client.py        # IBM WatsonX / Granite API wrapper
    │   └── prompt_builder.py        # All prompt engineering
    ├── generators/
    │   └── tikz_generator.py        # TikZ post-processing, templates, type detection
    └── utils/
        ├── nlp_utils.py             # Intent classification, command parsing
        └── file_utils.py            # Save / load / PDF compilation helpers
```

---

## Setup

### 1. Clone / download the project

```bash
cd AI-agent
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure credentials

```bash
# Copy the template
copy env.example .env        # Windows
# cp env.example .env        # macOS/Linux

# Edit .env and fill in:
# WATSONX_API_KEY=<your IBM Cloud API key>
# WATSONX_PROJECT_ID=<your WatsonX project ID>
```

### 4. Run the agent

```bash
python main.py
```

---

## Configuration

All settings live in **`.env`** (copy from `env.example`).

| Variable | Default | Description |
|---|---|---|
| `WATSONX_API_KEY` | *(required)* | IBM Cloud API key |
| `WATSONX_PROJECT_ID` | *(required)* | WatsonX project ID |
| `WATSONX_URL` | `https://us-south.ml.cloud.ibm.com` | WatsonX endpoint |
| `GRANITE_MODEL_ID` | `ibm/granite-13b-instruct-v2` | Granite model to use |
| `GRANITE_MAX_NEW_TOKENS` | `2048` | Max tokens per response |
| `GRANITE_TEMPERATURE` | `0.2` | Sampling temperature (lower = more deterministic) |
| `OUTPUT_DIR` | `outputs` | Where `.tex` files are saved |
| `MAX_REFINEMENT_ITERATIONS` | `10` | Hard cap on refinement rounds |
| `ENABLE_LATEX_VALIDATION` | `true` | Let Granite validate its own output |
| `ENABLE_LOCAL_COMPILATION` | `false` | Compile to PDF if `pdflatex` is on PATH |

---

## Usage

### Interactive CLI

```
diagram> /generate A three-layer neural network with 3 input nodes, 4 hidden nodes, and 2 output nodes

diagram> /refine Make the connections between layers grey and thinner

diagram> /refine Add labels "Input", "Hidden", "Output" above each layer

diagram> /show

diagram> /save neural_net_figure1

diagram> /history
```

### Slash commands

| Command | Description |
|---|---|
| `/generate <desc>` | Generate a new diagram |
| `/refine <instr>` | Refine current diagram with plain English |
| `/show` | Print the current TikZ code |
| `/save [filename]` | Save to `outputs/<filename>.tex` |
| `/history` | List all iterations in this session |
| `/template <type>` | Print a starter template |
| `/help` | Show help |
| `/quit` | Exit |

### Python API

```python
from latex_diagram_agent.config import get_config
from latex_diagram_agent.core.diagram_agent import DiagramAgent

config = get_config()
agent  = DiagramAgent(config)

# Generate
result = agent.generate(
    description="A flowchart showing the steps of gradient descent",
    diagram_type="flowchart",
)
print(result.tikz_code)

# Refine
result2 = agent.refine("Add a red border around the decision diamond")
print(result2.tikz_code)
```

---

## Architecture

```
User Input (plain English)
        │
        ▼
┌───────────────────┐
│  nlp_utils.py     │  — intent classification, command parsing
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  diagram_agent.py │  — session management, orchestration
└────────┬──────────┘
         │
         ▼
┌───────────────────┐       ┌────────────────────────┐
│  prompt_builder.py│──────▶│  granite_client.py     │
│  (prompt crafting)│       │  (IBM WatsonX API call) │
└───────────────────┘       └────────────┬───────────┘
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  tikz_generator.py    │
                             │  (extract, validate,  │
                             │   post-process code)  │
                             └───────────┬───────────┘
                                         │
                                         ▼
                                  outputs/<name>.tex
```

---

## Diagram Types Supported

| Type | Auto-detected keywords |
|---|---|
| `flowchart` | flow, process, pipeline, workflow, decision |
| `neural_network` | neural, deep learning, CNN, layer, neuron |
| `graph` | graph, node, edge, vertex, network |
| `tree` | tree, hierarchy, binary tree, parent, child |
| `state_machine` | state, automaton, FSM, transition |
| `sequence_diagram` | sequence, UML, lifeline, actor |
| `plot` | plot, function, axis, curve, histogram |
| `block_diagram` | block, module, system, architecture |
| `venn` | venn, intersection, union, set |
| `timeline` | timeline, chronology, milestone |

---

## Refinement Commands (Examples)

```
"Make the arrows blue"
"Add a legend in the bottom-right corner"
"Increase the node spacing to 2cm"
"Label the edges with transition probabilities"
"Use dashed lines for optional paths"
"Add a title 'Algorithm Overview' at the top"
"Make all rectangles have rounded corners"
"Remove the self-loop on state q1"
```

---

## IBM Technology Stack

| Component | Technology |
|---|---|
| AI / LLM | IBM Granite (`ibm/granite-13b-instruct-v2`) |
| Platform | IBM Watson Studio / WatsonX |
| SDK | `ibm-watsonx-ai` Python SDK |
| Output format | TikZ / LaTeX (`.tex`) |
| Optional PDF | `pdflatex` / `xelatex` (local) |
