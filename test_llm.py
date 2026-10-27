"""Minimal llama.cpp sanity check for the agent's GGUF model.

Bypasses LangChain / deepagents entirely and calls llama_cpp directly so we can
tell whether garbage output comes from the model+runtime (GPU build, corrupt
GGUF) or from the agent pipeline.

Usage (PowerShell):
    # Default: GPU (all layers)
    python test_llm.py

    # Force CPU to rule out a bad CUDA build:
    python test_llm.py --n-gpu-layers 0

    # Point at a different file:
    python test_llm.py --model "C:\\Haris\\models\\some-model.gguf"

If the GPU run is garbage but `--n-gpu-layers 0` (CPU) is coherent, the problem
is the CUDA build of llama-cpp-python (reinstall a matching CUDA wheel or
upgrade). If BOTH are garbage, re-download the .gguf (likely corrupt).
"""

from __future__ import annotations

import argparse
import sys

# Reuse the agent's Windows CUDA DLL discovery so the import matches the app.
try:
    from agent.config import add_windows_llama_dll_dirs

    add_windows_llama_dll_dirs()
except Exception as exc:  # noqa: BLE001
    print(f"(warning) could not run add_windows_llama_dll_dirs(): {exc}")

DEFAULT_MODEL = r"C:\Haris\models\nvidia_Nemotron-Cascade-14B-Thinking-Q8_0.gguf"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--n-gpu-layers", type=int, default=-1,
                        help="-1 = all on GPU, 0 = CPU only")
    parser.add_argument("--n-ctx", type=int, default=8192)
    parser.add_argument("--prompt", default="In one short sentence, what is an EDFA in optical networks?")
    args = parser.parse_args()

    from llama_cpp import Llama

    print(f"Loading: {args.model}")
    print(f"n_gpu_layers={args.n_gpu_layers}  n_ctx={args.n_ctx}\n")

    llm = Llama(
        model_path=args.model,
        n_ctx=args.n_ctx,
        n_gpu_layers=args.n_gpu_layers,
        verbose=True,  # show the raw llama.cpp load logs (arch, template, etc.)
    )

    # Print the chat template / chat format llama.cpp picked, since a wrong
    # template is a classic cause of bad output.
    print("\nchat_format =", getattr(llm, "chat_format", None))
    md = getattr(llm, "metadata", {}) or {}
    tmpl = md.get("tokenizer.chat_template")
    if tmpl:
        print("chat_template (first 300 chars):\n", tmpl[:300], "\n")

    print("=" * 60)
    print("PROMPT:", args.prompt)
    print("=" * 60)

    out = llm.create_chat_completion(
        messages=[{"role": "user", "content": args.prompt}],
        max_tokens=200,
        temperature=0.1,
    )
    text = out["choices"][0]["message"]["content"]
    print("\nMODEL OUTPUT:\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
