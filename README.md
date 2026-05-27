# CyCode: Your AI-Powered Coding Assistant

```
   ██████╗██╗   ██╗ ██████╗ ██████╗ ██████╗ ███████╗
  ██╔════╝╚██╗ ██╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝
  ██║      ╚████╔╝ ██║     ██║   ██║██║  ██║█████╗
  ██║       ╚██╔╝  ██║     ██║   ██║██║  ██║██╔══╝
  ╚██████╗   ██║   ╚██████╗╚██████╔╝██████╔╝███████╗
   ╚═════╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
```

CyCode is an advanced, AI-powered coding harness designed to enhance the productivity of professional software engineers. Built with a focus on reliability, speed, and precision, CyCode integrates seamlessly into your development workflow, providing intelligent assistance for various coding tasks.

## Vision

Our vision for CyCode is to empower developers with cutting-edge AI capabilities, enabling them to write better code, faster. CyCode aims to be a reliable partner in the software development lifecycle, from initial design to deployment and maintenance.

## Features

*   **Intelligent File Handling**: CyCode can read and understand project files, providing context-aware assistance.
*   **Interactive Code Editing**: Propose and apply code modifications with interactive diffs, allowing you to accept or reject changes.
*   **Context Management**: Automatically manages conversation context, ensuring the AI always has the most relevant information without overwhelming token limits.
*   **Multi-Model Support**: Leverage various AI models for different tasks, optimizing for speed or complexity.
*   **Plugin Ecosystem**: Extend CyCode's capabilities with powerful plugins for web search, GitHub integration, and more.
*   **Skill-Based Assistance**: Utilize predefined skills for code review, refactoring, test generation, documentation, and commit message creation.
*   **Sandbox Execution**: Safely execute code snippets in an isolated environment.
*   **Image Generation**: Generate images directly from prompts using CyVision SDXL.

## Quickstart

To get started with CyCode, follow these steps:

1.  **Installation**:
    ```bash
    # Assuming you have Python 3.9+ installed
    pip install -e .
    ```

2.  **Launch CyCode REPL**:
    ```bash
    cycode
    ```

3.  **Initialize Project Context**:
    Run the `/init` command to scan your project and create a `CYGNISAI.md` file, which helps CyCode understand your project structure and guidelines.
    ```
    /init
    ```

4.  **Basic Commands**:
    *   `/help`: Display available commands.
    *   `/file <path>`: Inject a specific file's content into the AI's context.
    *   `/exec <cmd>`: Run a shell command locally.
    *   `/sandbox <code>`: Execute Python/Bash code via CygnisAI sandbox.
    *   `/image <prompt>`: Generate an image via CyVision SDXL.
    *   `/plugins`: Manage available plugins (e.g., Google Search, GitHub).
    *   `/skills`: Access predefined AI skills (e.g., code_review, refactor).

## Repository Layout

```text
.
├── src/                                # Main Python source code
│   ├── cli/                            # Command Line Interface components
│   ├── services/                       # API client and service integrations
│   ├── state/                          # Session and configuration management
│   ├── utils/                          # Utility functions
│   ├── cycode_repl.py                  # Main REPL logic
│   ├── query_engine.py                 # Query processing and routing
│   └── ...                             # Other core modules
├── tests/                              # Unit and integration tests
├── rust/                               # Rust crates for performance-critical components
└── README.md
```



## Ownership / Affiliation Disclaimer

- This repository does **not** claim ownership of the original Claude Code source material.
- This repository is **not affiliated with, endorsed by, or maintained by Anthropic**.- CyCode is an independent project.
