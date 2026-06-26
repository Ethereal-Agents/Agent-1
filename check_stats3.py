import pandas as pd
df = pd.read_csv("eval_results/swe-verified-50/instances.csv")
df["repo"] = df["instance_id"].apply(lambda x: x.split("__")[0])

for reason in ["recovered", "submitted"]:
    subset = df[df["exit_reason"] == reason]
    print(f"--- {reason.upper()} ---")
    print(subset["repo"].value_counts().to_string())
    print("\n")

