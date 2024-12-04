# Model Context Provider CLI
This repository contains a protocol-level CLI designed to interact with a Model Context Provider server. The client allows users to send commands, query data, and interact with various resources provided by the server.

## Features
- Protocol-level communication with the Model Context Provider.
- Dynamic tool and resource exploration.
- Support for multiple providers and models:
  - Providers: OpenAI, Ollama, Groq.
  - Default models: 
    - OpenAI: `gpt-4o-mini`
    - Ollama: `qwen2.5-coder`
    - Groq: `llama3-groq-70b-8192-tool-use-preview`

## Prerequisites
- Python 3.8 or higher.
- Required dependencies (see [Installation](#installation))

## Installation
1. Clone the repository:

```bash
git clone https://github.com/chrishayuk/mcp-cli
cd mcp-cli
```

2. Install UV:

```bash
pip install uv
```

3. Resynchronize dependencies:

```bash
uv sync --reinstall
```

## Usage
To start the client and interact with the SQLite server, run the following command:

```bash
uv run main.py --server sqlite
```

### Command-line Arguments
- `--server`: Specifies the server configuration to use. Required.
- `--config-file`: (Optional) Path to the JSON configuration file. Defaults to `server_config.json`.
- `--provider`: (Optional) Specifies the provider to use (`openai`, `ollama`, or `groq`). Defaults to `openai`.
- `--model`: (Optional) Specifies the model to use. Defaults depend on the provider:
  - OpenAI: `gpt-4o-mini`
  - Ollama: `qwen2.5-coder`
  - Groq: `llama3-groq-70b-8192-tool-use-preview`

### Examples
Run the client with the default OpenAI provider and model:

```bash
uv run main.py --server sqlite
```

Run the client with Ollama provider:

```bash
uv run main.py --server sqlite --provider ollama --model llama3.2
```

Run the client with Groq provider:

```bash
uv run main.py --server sqlite --provider groq
```

Or specify a different Groq model:

```bash
uv run main.py --server sqlite --provider groq --model llama3-groq-8b-8192-tool-use-preview
```

## Interactive Mode
The client supports interactive mode, allowing you to execute commands dynamically. Type `help` for a list of available commands or `quit` to exit the program.

## Supported Commands
- `ping`: Check if the server is responsive.
- `list-tools`: Display available tools.
- `list-resources`: Display available resources.
- `list-prompts`: Display available prompts.
- `chat`: Enter interactive chat mode.
- `clear`: Clear the terminal screen.
- `help`: Show a list of supported commands.
- `quit`/`exit`: Exit the client.

### Chat Mode
To enter chat mode and interact with the server:

uv run main.py --server sqlite

In chat mode, you can use tools and query the server interactively. The provider and model used are specified during startup and displayed as follows:

Entering chat mode using provider 'ollama' and model 'llama3.2'...

#### Using OpenAI Provider:
If you wish to use openai models, you should

- set the `OPENAI_API_KEY` environment variable before running the client, either in .env or as an environment variable.

#### Using Groq Provider:
If you wish to use Groq models, you should:

- Set the `GROQ_API_KEY` environment variable before running the client, either in .env or as an environment variable.
- Available models include:
  - `llama3-groq-70b-8192-tool-use-preview` (default)
  - `llama3-groq-8b-8192-tool-use-preview`
  - `llama-3.1-70b-versatile`
  - `llama-3.1-8b-instant`

## Contributing
Contributions are welcome! Please open an issue or submit a pull request with your proposed changes.

## License
This project is licensed under the [MIT License](license.md).
