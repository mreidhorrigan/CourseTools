# WSGI and ASGI server decision

## Decision

Run the existing Flask WSGI application with pinned Waitress. Do not migrate it
to ASGI at this time.

Flask's built-in server is a development server. Waitress is a maintained,
pure-Python production WSGI server, runs on macOS, Windows, and Unix, and accepts
the application without an adapter or framework rewrite. The launcher, loopback
binding, single-course allowlist, in-memory token lifecycle, health endpoint,
and shutdown command remain the public contract.

## ASGI feasibility and value

ASGI is feasible through a WSGI-to-ASGI adapter or a rewrite to an ASGI-native
framework. It is not presently desirable. This tool has one local operator;
most request time is spent waiting on the remote Canvas API or Canvas migration
jobs; and its `requests` client and Flask handlers are synchronous. Placing that
code behind ASGI does not make those operations asynchronous. A genuine speedup
would require an async HTTP client, concurrency/rate-limit design, cancellation,
and broader tests. That complexity would weaken transferability for little
measurable benefit.

Reconsider ASGI only if profiling shows concurrent local clients saturating the
four Waitress threads or a future streaming/websocket requirement appears.

Authoritative references:

- https://flask.palletsprojects.com/en/stable/deploying/
- https://flask.palletsprojects.com/en/stable/deploying/waitress/
- https://docs.pylonsproject.org/projects/waitress/en/stable/
- https://flask.palletsprojects.com/en/stable/deploying/asgi/
