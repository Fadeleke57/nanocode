#!/usr/bin/env python3
"""nanocode-dspy - minimal claude code alternative using DSPy ReAct"""

import os
import re
import glob as globlib
import subprocess
from modaic import PrecompiledProgram, PrecompiledConfig
import dspy
from dspy.utils.callback import BaseCallback


# --- ANSI colors ---

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"


# --- Display utilities ---


def separator():
    """Return a horizontal separator line that fits the terminal width."""
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def render_markdown(text):
    """Convert basic markdown bold syntax to ANSI bold."""
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


# --- File operations ---


def read_file(path: str, offset: int = 0, limit: int = None) -> str:
    """Read file contents with line numbers.

    Args:
        path: Path to the file to read
        offset: Line number to start from (0-indexed)
        limit: Maximum number of lines to read

    Returns:
        File contents with line numbers
    """
    lines = open(path).readlines()
    if limit is None:
        limit = len(lines)
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write_file(path: str, content: str) -> str:
    """Write content to a file.

    Args:
        path: Path to the file to write
        content: Content to write to the file

    Returns:
        'ok' on success
    """
    with open(path, "w") as f:
        f.write(content)
    return "ok"


def edit_file(path: str, old: str, new: str, replace_all: bool = False) -> str:
    """Replace text in a file.

    Args:
        path: Path to the file to edit
        old: Text to find and replace
        new: Replacement text
        replace_all: If True, replace all occurrences; otherwise old must be unique

    Returns:
        'ok' on success, error message on failure
    """
    text = open(path).read()
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not replace_all and count > 1:
        return f"error: old_string appears {count} times, must be unique (use replace_all=True)"
    replacement = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    with open(path, "w") as f:
        f.write(replacement)
    return "ok"


def glob_files(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern, sorted by modification time.

    Args:
        pattern: Glob pattern to match (e.g., '**/*.py')
        path: Base directory to search in

    Returns:
        Newline-separated list of matching files
    """
    full_pattern = (path + "/" + pattern).replace("//", "/")
    files = globlib.glob(full_pattern, recursive=True)
    files = sorted(
        files,
        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
        reverse=True,
    )
    return "\n".join(files) or "no files found"


def grep_files(pattern: str, path: str = ".") -> str:
    """Search files for a regex pattern.

    Args:
        pattern: Regular expression pattern to search for
        path: Base directory to search in

    Returns:
        Matching lines in format 'filepath:line_num:content'
    """
    regex = re.compile(pattern)
    hits = []
    for filepath in globlib.glob(path + "/**", recursive=True):
        try:
            for line_num, line in enumerate(open(filepath), 1):
                if regex.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except Exception:
            pass
    return "\n".join(hits[:50]) or "no matches found"


# --- Shell operations ---


def run_bash(cmd: str) -> str:
    """Run a shell command and return output.

    Args:
        cmd: Shell command to execute

    Returns:
        Command output (stdout and stderr combined)
    """
    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    output_lines = []
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 30s)")
    return "".join(output_lines).strip() or "(empty output)"


# --- Model selection ---

AVAILABLE_MODELS = {
    "1": ("Claude 3.5 Sonnet", "anthropic/claude-3.5-sonnet"),
    "2": ("Claude 3.5 Haiku", "anthropic/claude-3.5-haiku"),
    "3": ("GPT-4o", "openai/gpt-4o"),
    "4": ("GPT-4o mini", "openai/gpt-4o-mini"),
    "5": ("Gemini Pro 1.5", "google/gemini-pro-1.5"),
    "6": ("Llama 3.1 405B", "meta-llama/llama-3.1-405b-instruct"),
    "7": ("DeepSeek V3", "deepseek/deepseek-chat"),
    "8": ("Qwen 2.5 72B", "qwen/qwen-2.5-72b-instruct"),
}


def select_model():
    """Interactive model selection or use environment variable."""
    model_env = os.getenv("MODEL")
    if model_env:
        print(f"{GREEN}⏺ Using model from environment: {model_env}{RESET}")
        return model_env

    print(f"\n{BOLD}Select a model:{RESET}")
    for key, (name, model_id) in AVAILABLE_MODELS.items():
        print(f"  {BLUE}{key}{RESET}. {name} ({DIM}{model_id}{RESET})")
    print(f"  {BLUE}c{RESET}. Custom model (enter manually)")

    while True:
        try:
            choice = (
                input(f"\n{BOLD}{BLUE}❯{RESET} Enter choice (1-8 or c): ")
                .strip()
                .lower()
            )

            if choice in AVAILABLE_MODELS:
                name, model_id = AVAILABLE_MODELS[choice]
                print(f"{GREEN}⏺ Selected: {name}{RESET}")
                return model_id
            elif choice == "c":
                custom_model = input(
                    f"{BOLD}{BLUE}❯{RESET} Enter model ID (e.g., openai/gpt-4): "
                ).strip()
                if custom_model:
                    print(f"{GREEN}⏺ Selected custom model: {custom_model}{RESET}")
                    return custom_model
                else:
                    print(f"{RED}⏺ Invalid model ID{RESET}")
            else:
                print(f"{RED}⏺ Invalid choice. Please enter 1-8 or c{RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{RED}⏺ Model selection cancelled{RESET}")
            exit(1)


# --- DSPy Signature ---


class CodingAssistant(dspy.Signature):
    """You are a concise coding assistant. Help the user with their coding task by using the available tools to read, write, edit files, search the codebase, and run commands."""

    task: str = dspy.InputField(desc="The user's coding task or question")
    answer: str = dspy.OutputField(
        desc="Your response to the user after completing the task"
    )
    affected_files: list[str] = dspy.OutputField(
        desc="List of files that were written or modified during the task"
    )


# ReAct agent with tools

tools = [read_file, write_file, edit_file, glob_files, grep_files, run_bash]


class ToolLoggingCallback(BaseCallback):
    """Callback that logs tool calls as they happen."""

    def on_tool_start(self, call_id, instance, inputs):
        """Log when a tool starts executing."""
        tool_name = instance.name if hasattr(instance, "name") else str(instance)
        # Format args nicely
        args_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in inputs.items())
        print(f"  {MAGENTA}⏺ {tool_name}({args_str}){RESET}", flush=True)

    def on_tool_end(self, call_id, outputs, exception):
        """Log when a tool finishes executing."""
        if exception:
            print(f"    {RED}Error: {exception}{RESET}", flush=True)

    def on_module_end(self, call_id, outputs, exception):
        """Log when the finish tool is called (ReAct completion)."""
        # Check if this is a ReAct prediction with tool_calls
        if outputs and "tool_calls" in outputs:
            for call in outputs["tool_calls"]:
                args_str = ", ".join(
                    f"{k}={repr(v)[:50]}" for k, v in call.args.items()
                )
                if call.name == "finish":
                    print(f"  {GREEN}⏺ finish{RESET}", flush=True)
                else:
                    print(f"  {MAGENTA}⏺ {call.name}({args_str}){RESET}", flush=True)


class AgentConfig(PrecompiledConfig):
    max_iters: int = 15
    lm: str = "openrouter/anthropic/claude-3.5-sonnet"  # Default fallback
    api_base: str = "https://openrouter.ai/api/v1"
    max_tokens: int = 16000


class AgentProgram(PrecompiledProgram):
    config: AgentConfig

    def __init__(self, config: AgentConfig, **kwargs):
        self.config = config
        super().__init__(config, **kwargs)

        # Configure logging callback globally
        dspy.settings.configure(callbacks=[ToolLoggingCallback()])

        agent = dspy.ReAct(
            CodingAssistant, tools=tools, max_iters=self.config.max_iters
        )
        lm = dspy.LM(
            self.config.lm,
            api_base=self.config.api_base,
            max_tokens=self.config.max_tokens,
        )
        agent.set_lm(lm)
        self.agent = agent

    def forward(self, task: str) -> str:
        assert task, "Task cannot be empty"
        return self.agent(task=task)


# --- Main ---


def main():
    """Create AgentConfig with selected model."""
    model = os.getenv("MODEL")
    if model is None:
        model = select_model()

    # Add openrouter/ prefix if not already present
    if not model.startswith("openrouter/"):
        model = f"openrouter/{model}"

    config = AgentConfig()
    config.lm = model

    agent = AgentProgram(config)
    print(
        f"{BOLD}nanocode-dspy{RESET} | {DIM}{agent.config.lm} | {os.getcwd()}{RESET}\n"
    )

    # Conversation history for context
    history = []

    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())

            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                history = []
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue

            # Build context from history
            context = f"Working directory: {os.getcwd()}\n"
            if history:
                context += "\nPrevious conversation:\n"
                for h in history[-5:]:  # Keep last 5 exchanges
                    context += f"User: {h['user']}\nAssistant: {h['assistant']}\n\n"

            task = f"{context}\nCurrent task: {user_input}"

            print(f"\n{CYAN}⏺{RESET} Thinking...", flush=True)

            # Run the ReAct agent
            result = agent(task=task)

            # Display the answer
            print(f"\n{CYAN}⏺{RESET} {render_markdown(result.answer)}")

            # Save to history
            history.append({"user": user_input, "assistant": result.answer})

            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            import traceback

            traceback.print_exc()
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    #agent = AgentProgram(AgentConfig(lm="openai/gpt-5.2-codex"))
    #agent.push_to_hub("farouk1/nanocode")
    main()
