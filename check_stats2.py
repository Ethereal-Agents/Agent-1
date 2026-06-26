import pandas as pd
df = pd.read_csv("eval_results/swe-verified-50/instances.csv")
for reason in ["recovered", "submitted"]:
    subset = df[df["exit_reason"] == reason]
    avg_steps = subset["steps"].mean()
    print(f"--- {reason.upper()} ---")
    print(f"Avg Steps: {avg_steps:.1f}")
    print("Tags:")
    print(subset["tag"].value_counts().to_string())
    print("\n")

