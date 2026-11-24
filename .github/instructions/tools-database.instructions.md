---
applyTo: "tools/database/**"
---

# Code rules for tools/database

- A backend readiness probe must establish that the database can run its required initialization or, if none is needed, serve the workload. A successful connection or command exit status does not establish readiness if the backend returned an error.
