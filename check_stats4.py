import pandas as pd

df = pd.read_csv("eval_results/swe-verified-50/instances.csv")
df["repo"] = df["instance_id"].apply(lambda x: x.split("__")[0])

repos = df["repo"].unique()
for repo in repos:
    subset = df[df["repo"] == repo]
    passed = subset[subset["tag"] == "resolved"].shape[0]
    total = subset.shape[0]
    print(f"{repo}: {passed}/{total} ({(passed / total) * 100:.1f}%)")
