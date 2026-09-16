"""Command-line entry point for the documentary renderer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from exceptions import DocumentaryRendererError
from logger import setup_logging
from project_menu import choose_project_manifest
from renderer import DocumentaryRenderer


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    parser = argparse.ArgumentParser(description="Render a documentary from a V1 storyboard or V2 manifest JSON.")
    parser.add_argument(
        "input_json",
        nargs="?",
        default=None,
        help="Path to a storyboard JSON file or V2 manifest. Omit it to choose from projects/.",
    )
    parser.add_argument("--v2", action="store_true", help="Render a V2 MASTER_MANIFEST/manifest JSON.")
    parser.add_argument("--ignore-qc", action="store_true", help="Render a V2 manifest even when QC reports errors.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""

    args = build_parser().parse_args(argv)
    logger = setup_logging(args.verbose)

    try:
        renderer = DocumentaryRenderer(logger=logger)
        if args.input_json is None:
            manifest_path = choose_project_manifest("projects")
            output = renderer.render_manifest(manifest_path, ignore_qc=args.ignore_qc)
        elif args.v2:
            manifest_path = Path(args.input_json)
            if args.ignore_qc:
                output = renderer.render_manifest(manifest_path, ignore_qc=True)
            else:
                output = renderer.render_manifest(manifest_path)
        else:
            output = renderer.render(Path(args.input_json))
    except DocumentaryRendererError as exc:
        logger.error("Render failed: %s", exc)
        return 1

    logger.info("Output: %s", output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
