from retrieval_engine import retrieve

# Test citation retrieval
result1 = retrieve("Is physical therapy covered under the Silver plan?")
print("=== Physical Therapy Question ===")
print("Classification:", result1["classification"])
print("Vector results count:", len(result1.get("vector_results", [])))
print("Vector results:", result1.get("vector_results", []))

print("\n=== Claim Question ===")
result2 = retrieve("Status of claim C1001")
print("Classification:", result2["classification"])
print("SQL results:", result2.get("sql_results", []))