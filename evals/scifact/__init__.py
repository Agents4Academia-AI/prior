"""SciFact eval harness for Prior's Navigator (forward mode).

SciFact gives claims labelled SUPPORT / CONTRADICT / NOINFO against a corpus of
abstracts — a near-direct mirror of Prior's forward output (supporting /
contradicting / abstain). We retrieve candidate abstracts per claim, run
Navigator over a small atlas built from them, and map its verdict to a label.

Credit thrift is built in: see `harness.run_eval` (caching, limit, injectable
ask_fn) and `run.py --mock` (zero API calls).
"""
