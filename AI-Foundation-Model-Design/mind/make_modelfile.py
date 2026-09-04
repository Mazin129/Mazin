"""
make_modelfile  —  write a correct Ollama Modelfile for a fine-tuned Qwen2.5 GGUF.

A bare `FROM model.gguf` gives Ollama no chat template, so Qwen's <|im_start|>
formatting is missing and role labels like "system" leak into the answer as
garbage. This writes a Modelfile with the proper ChatML template so the model
answers cleanly. Special characters ({{ }}, <|im_end|>, quotes) are impossible
to type safely in cmd/PowerShell — let Python write the file instead.

Usage (run it in the folder that holds your .gguf):
    python make_modelfile.py                 # auto-finds the .gguf here
    python make_modelfile.py C:\\path\\model.gguf
Then:
    ollama create vio-net -f Modelfile
"""
import sys, glob, os

g = sys.argv[1] if len(sys.argv) > 1 else None
if not g:
    hits = sorted(glob.glob("*.gguf"))
    if not hits:
        print("No .gguf found in this folder. Either run this where your model is, "
              "or pass the path:\n    python make_modelfile.py C:\\path\\to\\model.gguf")
        sys.exit(1)
    g = hits[0]
if not os.path.exists(g):
    print(f"File not found: {g}")
    sys.exit(1)

fname = os.path.basename(g)
modelfile = (
    f"FROM ./{fname}\n\n"
    'TEMPLATE """{{ if .System }}<|im_start|>system\n'
    "{{ .System }}<|im_end|>\n"
    "{{ end }}{{ if .Prompt }}<|im_start|>user\n"
    "{{ .Prompt }}<|im_end|>\n"
    "{{ end }}<|im_start|>assistant\n"
    '{{ .Response }}<|im_end|>"""\n\n'
    'PARAMETER stop "<|im_end|>"\n'
    'PARAMETER stop "<|im_start|>"\n'
)
with open("Modelfile", "w", encoding="utf-8") as fh:
    fh.write(modelfile)

print(f"Wrote Modelfile  ->  FROM ./{fname}")
print("Next:")
print("    ollama rm vio-net        (if you made a broken one earlier)")
print("    ollama create vio-net -f Modelfile")
