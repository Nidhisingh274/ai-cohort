# Coverage Database SQL Queries

## 1. What's the deductible on the Gold PPO plan?
**SQL:**
`SELECT annual_deductible FROM plans WHERE plan_name = 'Gold PPO';`
**Output:** 
2000

## 2. How many claims are pending for member M1001?
**SQL:**
`SELECT COUNT(*) FROM claims WHERE member_id = 'M1001' AND status = 'Pending';`
**Output:** 
1

## 3. Which plans have a monthly premium under $400?
**SQL:**
`SELECT plan_name, monthly_premium FROM plans WHERE monthly_premium < 400;`
**Output:** 
- Silver HMO (300)
- Bronze HMO (150)

## 4. A JOIN between claims and plans
**Question:** What are the claim amounts and associated plan names?
**SQL:**
`SELECT claims.claim_id, plans.plan_name, claims.claim_amount FROM claims JOIN plans ON claims.plan_id = plans.plan_id;`
**Output:**
- C1001 | Gold PPO | 250
- C1002 | Gold PPO | 1200
- C1003 | Silver HMO | 150
- C1004 | Silver HMO | 900
- C1005 | Bronze HMO | 50

## 5. A top-N query (most claimed procedures)
**Question:** What are the top procedures by claim count?
**SQL:**
`SELECT procedure, COUNT(*) as claim_count FROM claims GROUP BY procedure ORDER BY claim_count DESC LIMIT 2;`
**Output:**
- X-ray | 3
- Surgery | 2