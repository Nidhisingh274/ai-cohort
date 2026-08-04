import pandas as pd

# Load the CSVs
plans = pd.read_csv("data/plans.csv")
claims = pd.read_csv("data/claims.csv")

# Inspect the data
print("=== Plans Info ===")
print(plans.info())
print(plans.head())

print("\n=== Claims Info ===")
print(claims.info())
print(claims.head())

# Clean: drop duplicates
plans = plans.drop_duplicates()
claims = claims.drop_duplicates()

# Clean: handle nulls (fill numeric nulls with 0, or drop rows with critical missing data)
plans = plans.fillna(0)
claims = claims.dropna(subset=["claim_id", "member_id", "plan_id"])

# Clean: convert date_filed to actual datetime type
claims["date_filed"] = pd.to_datetime(claims["date_filed"])

print("\n=== Cleaned Claims dtypes ===")
print(claims.dtypes)

import sqlite3

# Connect (creates coverage.db if it doesn't exist)
conn = sqlite3.connect("coverage.db")

# Load DataFrames into SQL tables
plans.to_sql("plans", conn, if_exists="replace", index=False)
claims.to_sql("claims", conn, if_exists="replace", index=False)

conn.close()
print("\nDatabase created: coverage.db")