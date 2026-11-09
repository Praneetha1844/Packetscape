# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [Unreleased]

### Fixed
- Two links between the same pair of nodes are now reported as a scenario error instead of raising an unhandled exception.
- `cc` and `window` on a non-TCP flow, and `window` without `cc: fixed`, are rejected instead of being silently ignored.
- `packetscape run --out` reports an unwritable output directory with exit code 2 instead of a traceback.

### Added
- Documentation: index, scenario reference, command-line reference, development guide, glossary, `SECURITY.md`, and notes on loss recovery, RTT sampling and queue capacity in the model limits.
- Regression tests for config validation, CLI output errors and the receiver's cumulative ACKs.
- Project URLs in package metadata.

## [0.1.0] - 2026-11-09

### Added
- Deterministic discrete-event scheduler with stable ordering of simultaneous events.
- Link model with serialization delay, propagation delay, random loss and per-direction queues.
- Queue disciplines: drop-tail FIFO and RED.
- Congestion controllers: fixed window, AIMD (Reno-like) and a simplified CUBIC-style controller.
- Packet-granular TCP-like transport with cumulative ACKs, fast retransmit and RFC 6298 style RTO.
- Open-loop traffic sources: constant bit rate and Poisson.
- Metrics: throughput, loss ratio, one-way delay percentiles and Jain's fairness index.
- Strict YAML scenario loader with path-qualified validation errors.
- `packetscape run` and `packetscape validate` commands, CSV export and optional plots.
- Example scenarios, architecture documentation and decision records.
