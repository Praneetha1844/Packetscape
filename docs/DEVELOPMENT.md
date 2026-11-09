# Development guide

## Setup

Python 3.10 or newer.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,plots]"
make check      # ruff, ruff format --check, mypy (strict), pytest with coverage
```

Tests are deterministic and need no network.

## Where things live

See the project layout in the [README](../README.md) and the component diagram in [ARCHITECTURE](ARCHITECTURE.md). Dependencies point downwards: `config` knows nothing about the simulation, `queues` and `congestion` know nothing about the scheduler, and `metrics` is a passive sink.

## Adding a congestion controller

1. Subclass `CongestionControl` in `congestion.py` and implement `on_ack`, `on_fast_retransmit` and `on_timeout`.
2. Register its name in `make_congestion_control` and in `CC_NAMES` in `config.py`.
3. Add unit tests that drive the controller directly, as in `tests/test_congestion.py`.
4. Document what it simplifies in [model-and-limits](model-and-limits.md).

## Adding a queue discipline

Implement `QueueDiscipline` (`enqueue`, `dequeue`, `__len__`), add the type to `QUEUE_TYPES` and `_parse_queue`, and construct it in `simulation.make_queue`.

## Determinism rules

- Take randomness only from a stream made by `child_rng(seed, name)`. Never use the global `random` module or `hash()`.
- Do not iterate over sets in a way that changes event order.
- Events at the same time run in insertion order; keep it that way.

## Conventions

- Typed code. `ruff` and strict `mypy` must be clean.
- Conventional commit prefixes (`feat`, `fix`, `docs`, `test`, `chore`, `ci`).
- Never publish numbers that were not produced by a run you can reproduce.
