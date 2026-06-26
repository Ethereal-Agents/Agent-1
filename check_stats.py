import pandas as pd
df = pd.read_csv("eval_results/swe-verified-50/instances.csv")
for reason in df["exit_reason"].unique():
    subset = df[df["exit_reason"] == reason]
    passed = subset[subset["tag"] == "resolved"].shape[0]
    total = subset.shape[0]
    print(f"{reason}: {passed}/{total} ({(passed/total)*100:.1f}%)")

