"""Command-line interface: ``packetscape run|validate``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from packetscape import __version__
from packetscape.config import ConfigError, load_config
from packetscape.reporting import format_table, write_cwnd_csv, write_flows_csv
from packetscape.simulation import Simulation
from packetscape.topology import NoRouteError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="packetscape", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a scenario")
    run.add_argument("config", type=Path, help="path to a YAML scenario file")
    run.add_argument("--out", type=Path, default=None, help="directory for CSV output")
    run.add_argument("--plots", action="store_true", help="also write PNG plots (needs matplotlib)")
    run.add_argument("--seed", type=int, default=None, help="override the scenario seed")

    validate = sub.add_parser("validate", help="validate a scenario file without running it")
    validate.add_argument("config", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "validate":
            Simulation(config)  # builds routes, so unreachable flows are reported too
            print(f"{args.config}: OK")
            return 0
        if args.seed is not None:
            config = replace(config, seed=args.seed)
        result = Simulation(config).run()
    except (ConfigError, NoRouteError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(format_table(result))
    if args.out is not None:
        write_flows_csv(result, args.out / "flows.csv")
        write_cwnd_csv(result, args.out / "cwnd.csv")
        print(f"wrote {args.out / 'flows.csv'} and {args.out / 'cwnd.csv'}")
        if args.plots:
            from packetscape.plots import plot_results

            try:
                for path in plot_results(result, args.out):
                    print(f"wrote {path}")
            except RuntimeError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
    elif args.plots:
        print("error: --plots requires --out", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
