from datasets import load_dataset

ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
for row in ds:
    if row["instance_id"] == "matplotlib__matplotlib-26466":
        print(row["patch"])
        break
