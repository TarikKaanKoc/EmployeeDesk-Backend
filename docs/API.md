# API

Base path `/api`. Every route except health and sign-in needs a bearer token or the session cookie; every route is rate limited. All reads are scoped to the signed-in employee.

| Area | Method | Path | What it does |
|---|---|---|---|
| Health | GET | `/health/` · `/health/live` · `/health/ready` | process up · liveness · Postgres and Redis answer |
| Auth | POST | `/auth/login` | email + password → access and refresh tokens |
| Auth | POST | `/auth/refresh` | rotate the refresh token |
| Auth | POST | `/auth/logout` | revoke the session |
| Auth | GET | `/auth/me` | the signed-in employee |
| Employees | GET | `/employees/me` | profile |
| Leave | GET | `/leave/balances` | annual and sick balances |
| Leave | GET | `/leave/requests` · `/leave/requests/{id}` | own requests |
| Leave | POST | `/leave/requests` | submit a request |
| Procurement | GET | `/procurement/requests` · `/procurement/requests/{pr}` | own purchase requests from the ERP; others' are 404 |
| Policies | GET | `/policies` | policy clauses |
| Policies | POST | `/policies/search` | hybrid search, `{ "query", "language" }` |
| Assistant | POST | `/assistant/chat` | one turn, JSON |
| Assistant | POST | `/assistant/chat/stream` | one turn, SSE: `meta` · `tool_start` · `tool_call` · `token` · `done` |
| Assistant | POST | `/assistant/confirm/{actionId}` | `{ "decision": "confirm" \| "reject" }` for a parked draft |
| Assistant | GET | `/assistant/conversations` · `/assistant/conversations/{id}` | history |
| Assistant | POST | `/assistant/conversations/{id}/title` | regenerate the title |
| Assistant | DELETE | `/assistant/conversations/{id}` | delete a conversation |
| Audit | GET | `/audit/me` | own activity trail, `limit` and `before` paging |

Interactive docs: `/docs` (OpenAPI).
