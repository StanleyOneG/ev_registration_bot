import os
from typing import cast
from edgedb import AsyncIOClient, RetryOptions
import edgedb


def make_edge_connection() -> AsyncIOClient:
    dsn = os.environ["EDGE_DB_DSN"]
    print(f"dsn: {dsn}")
    if dsn:
        out = edgedb.create_async_client(
            dsn, tls_security="insecure", timeout=30
        ).with_retry_options(RetryOptions(attempts=10))
    else:
        out = edgedb.create_async_client(max_concurrency=5)
    print(f"out: {out}")
    return cast(AsyncIOClient, out)
