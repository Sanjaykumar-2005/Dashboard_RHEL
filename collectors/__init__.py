"""Live metric collectors — every function returns a plain dict snapshot.

None of these persist anything; they read the system / endpoints on demand and
hand back the current values.  Each collector is defensive: if the underlying
source is missing (e.g. no GPU, vLLM down) it returns ``available=False`` rather
than raising, so the dashboard degrades gracefully.
"""
