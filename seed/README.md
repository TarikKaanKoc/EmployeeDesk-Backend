# seed/

All data here is synthetic and generated for this exercise. Nothing is taken from any real organisation.

## Source of truth: `Tarik_Employee_Services_Assistant_Synthetic_Data_Expanded.xlsx`

Loaded into Postgres by `pdm run seed` (`scripts/seed_data.py`, idempotent upsert on business keys).

| Sheet | Rows | Table | Notes |
|---|---|---|---|
| Employees | 80 | `employees` | 3 inactive (E1070, E1075, E1080) |
| Identity_Map | 80 | `identities` | sign-in subject -> employee, 1:1. `Expected_Result` is not stored; it follows from `employment_status` |
| Assistant_Test_Cases.Precondition | - | not stored | constant "Mapped synthetic identity" on all 100 rows |
| Leave_Balances | 160 | `leave_balances` | PK (employee_id, leave_type); `available_days` is a stored generated column (entitled - used - pending) |
| Leave_Requests | 120 | `leave_requests` | `days` is a stored generated column (end - start + 1); `Created_At` -> `created_at` (UTC midnight) |
| Policy_Knowledge | 60 | `policy_documents` (3, keyed by domain) + `policy_clauses` (60) | one clause = one retrieval chunk = one citation; `tsv` generated; `embedding` filled only when Azure OpenAI is configured |
| Untrusted_Documents | 50 | `untrusted_documents` | prompt-injection fixtures |
| Assistant_Test_Cases | 100 | `assistant_test_cases` | the evaluation set |
| Purchase_Requests | 100 | `erp.purchase_requests` | own schema, no FK to `public`, business dates only: modelled as the external ERP |

Workbook labels are mapped to lower-snake enum values (`Under Review` -> `under_review`, `Annual` -> `annual`). Excel serial dates are converted. Currency is QAR.

Known data quirk: `Leave_Balances.Pending_Days` does not equal the sum of that employee's `Pending` requests in `Leave_Requests` (114 of 160 rows differ). The balance sheet is treated as the authoritative snapshot; requests are history.
