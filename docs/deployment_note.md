# API Deployment Note

- Build image: `docker build -t electronic-consultant-api .`
- Container startup runs canonical schema upgrade automatically when `CANONICAL_DB_AUTO_UPGRADE=1`.
- Health endpoint is `GET /health` and reports DB reachability plus current migration revision.
- Set `CANONICAL_DB_DSN` and storage-related paths through environment variables; the image does not hardcode deployment credentials.
- For production PostgreSQL deployments, provide a PostgreSQL DSN and install the required DB driver in the target runtime image variant.
