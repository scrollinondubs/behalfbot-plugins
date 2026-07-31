# Image generation

**One prompt, two backends, one CLI.** Generate an image locally through
ComfyUI + FLUX.1, or through a hosted image API, and switch between them with a
flag.

## What it does

`generate-image.sh` takes a text prompt and writes a PNG.

- **Local (ComfyUI + FLUX.1):** free after the hardware, nothing leaves the machine, roughly 11 minutes per image on consumer silicon. The script injects your prompt and a random seed into the shipped workflow graph, submits it to ComfyUI's HTTP API, polls the history endpoint, and copies the finished render out.
- **Hosted:** seconds per image, billed per call, markedly better at rendering readable text inside the image.

## Which backend

| | Local ComfyUI | Hosted |
|---|---|---|
| Speed | minutes | seconds |
| Cost | free | per image |
| Privacy | prompt and output stay on the machine | both transit a third party |
| Text in images | unreliable | good |
| Best for | background and batch work | iteration, urgency, text overlays |

## Install

Chassis installs: enable the module and re-bootstrap.

```yaml
# chassis.config.yaml
modules:
  image-generation:
    enabled: true
    comfyui_output_dir: /path/to/ComfyUI/output   # required for the local backend
```

Off by default, deliberately. The local backend needs a ComfyUI install with
several GB of model weights, and the hosted backend spends money on every call.

`setup.sh` installs neither backend. It checks `curl` and `jq`, reports whether
ComfyUI is reachable and whether a hosted credential is in the environment, and
tells you what is missing. Installing 20GB of model weights is an operator
decision, not something a bootstrap script should do quietly.

## Configuration

| Key | Default | What it controls |
|---|---|---|
| `enabled` | `false` | Master switch |
| `default_backend` | `comfyui` | Used when the caller passes no flag |
| `output_dir` | `${CHASSIS_HOME}/temp` | Where generated PNGs land |
| `comfyui_url` | `http://localhost:8188` | ComfyUI HTTP API base |
| `comfyui_output_dir` | *(none)* | **Required for the local backend.** ComfyUI's own output directory, readable from the chassis. No default - it depends where ComfyUI was installed, and guessing would fail confusingly instead of loudly. |
| `comfyui_workflow_path` | shipped FLUX.1 graph | API-format workflow JSON |
| `comfyui_prompt_node` | `6` | Node whose `inputs.text` gets the prompt |
| `comfyui_seed_node` | `25` | Node whose `inputs.noise_seed` gets the seed |
| `comfyui_output_node` | `9` | SaveImage node read back for the filename |
| `comfyui_timeout_seconds` | `900` | Poll ceiling. FLUX.1 Q6_K runs to about 11 minutes. |
| `openai_model` | `gpt-image-1` | Hosted model id |
| `openai_size` | `1024x1024` | Requested dimensions |
| `openai_quality` | `high` | Quality tier. Higher costs more. |
| `openai_base_url` | `https://api.openai.com/v1` | Override to route through a compatible gateway |

Credentials come from the process environment (`OPENAI_API_KEY`), supplied by
the chassis secret store. **The script never sources a `.env` and never reads a
secret off disk.** A plugin that quietly opens a credential file it did not
declare is the thing the manifest contract exists to prevent.

## Usage

```bash
bash scripts/generate-image.sh "a lighthouse in fog, cinematic, wide angle"
bash scripts/generate-image.sh --openai "a lighthouse in fog" out.png
bash scripts/generate-image.sh --comfyui "a lighthouse in fog"
```

The output path goes to stdout and progress to stderr, so
`IMG=$(bash scripts/generate-image.sh "...")` captures just the path.

## Swapping the workflow graph

The shipped graph is FLUX.1 Dev Q6_K in ComfyUI API format. To use your own,
point `comfyui_workflow_path` at it and set the three node ids to match. Those
ids are the whole contract between script and graph: prompt in, seed in,
filename out. `validate.sh` checks all three exist in whatever graph is
configured, so a mismatched swap fails at validation rather than eleven minutes
into a render.

## Layout

- `openclaw.plugin.json` - manifest (config schema, env contract)
- `.claude-plugin/plugin.json` - Claude Code compatibility shim
- `setup.sh` / `validate.sh` - dependency checks + smoke check
- `config/comfyui-flux-workflow.json` - the FLUX.1 API-format graph
- `skills/image-generation/SKILL.md` - the agent-facing skill
- `scripts/generate-image.sh` - the generator
