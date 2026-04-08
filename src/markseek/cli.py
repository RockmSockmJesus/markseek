"""
markseek.cli -- Command-line interface for markseek.

Commands:
    markseek "your query"               Search semantically
    markseek --status                   Show index status
    markseek --rebuild                  Force full reindex and search
    markseek --watch                    Start the auto-indexing watcher
    markseek --index                    Build/update index without searching
    markseek --index --rebuild          Force full reindex
    markseek --configure                Interactive config wizard
"""

import argparse
import sys
import logging
import textwrap


def setup_logging(level: str = "INFO"):
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(message)s",
        stream=sys.stdout,
    )


def cmd_search(cfg, args):
    from markseek.core import Index

    index = Index(cfg)
    if not cfg.vault_exists():
        print(f"Error: vault not found at {cfg.vault_path}")
        print(f"Run 'markseek --configure' to set up your vault path.")
        sys.exit(1)

    # Ensure index exists and is current
    if args.rebuild:
        index.rebuild()
    else:
        index.index_all()

    if not args.query:
        print("Usage: markseek \"your query\"\n")
        return

    results = index.search(args.query, top_k=args.top)
    if not results:
        print("No results found.")
        return

    print(f"\nSearch results for: \"{args.query}\"\n")
    for i, r in enumerate(results, 1):
        display = r["text"]
        if len(display) > 400:
            display = display[:397] + "..."
        print(f"--- Result {i} (relevance: {r['score']:.2f}) ---")
        print(f"File: {r['file']}")
        print(f"Snippet:\n{display}\n")


def cmd_status(cfg, args):
    from markseek.core import Index

    index = Index(cfg)
    try:
        status = index.status()
        print(f"\nVault:    {status['vault_path']}")
        print(f"Index:    {status['index_path']}")
        print(f"Model:    {status['model']}")
        print(f"Files:    {status['indexed_files']}")
        print(f"Chunks:   {status['total_chunks']}")
    except Exception:
        print("Index not yet created. Run 'markseek --index' or search to create it.")


def cmd_index(cfg, args):
    from markseek.core import Index

    index = Index(cfg)
    if not cfg.vault_exists():
        print(f"Error: vault not found at {cfg.vault_path}")
        sys.exit(1)

    if args.rebuild:
        print("Rebuilding index from scratch...")
        index.rebuild()
    else:
        print("Updating index...")
        index.index_all()
    print("Done.")


def cmd_watch(cfg, args):
    from markseek.watcher import VaultWatcher

    if not cfg.vault_exists():
        print(f"Error: vault not found at {cfg.vault_path}")
        sys.exit(1)

    print(f"Watching vault: {cfg.vault_path}")
    print(f"Debounce: {cfg.debounce_seconds}s")
    print(f"Extensions: {', '.join(cfg.extensions)}")
    print("Press Ctrl-C to stop\n")
    watcher = VaultWatcher(cfg)
    watcher.start()


def cmd_configure(cfg, args):
    import os
    from pathlib import Path

    print("markseek configuration")
    print("=" * 40)

    # Vault path
    current = cfg.vault_path or "(not set)"
    prompt = f"\nVault path [{current}]: "
    vault_input = input(prompt).strip()
    if vault_input:
        cfg.vault_path = os.path.expanduser(vault_input)

    # Model
    current_model = cfg.model_name
    prompt = f"Embedding model [{current_model}]: "
    model_input = input(prompt).strip()
    if model_input:
        cfg.model_name = model_input

    # Verify vault exists
    if cfg.vault_exists():
        md_count = len(list(Path(cfg.vault_path).rglob("*.md")))
        print(f"\nFound {md_count} markdown files in vault.")
    else:
        print(f"\nWarning: vault path not found: {cfg.vault_path}")
        print("You can still configure it now, fix the path later.")

    cfg.save()
    print(f"\nConfig saved to: ~/.config/markseek/config.yaml")
    print("You can edit it directly anytime.")


def main():
    parser = argparse.ArgumentParser(
        prog="markseek",
        description="Semantic search over your markdown vault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              markseek "what does Frankl say about meaning"
              markseek -n 10 "existential vacuum"
              markseek --watch
              markseek --index --rebuild
              markseek --status
              markseek --configure
        """),
    )
    parser.add_argument("query", nargs="?", default=None, help="Search query")
    parser.add_argument("-n", "--top", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--configure", action="store_true", help="Interactive configuration wizard")
    parser.add_argument("--status", action="store_true", help="Show index status")
    parser.add_argument("--rebuild", action="store_true", help="Force full reindex")
    parser.add_argument("--watch", action="store_true", help="Start the auto-indexing watcher")
    parser.add_argument("--index", action="store_true", help="Build or update the index (use with --rebuild)")

    args = parser.parse_args()

    from markseek.config import Config
    cfg = Config.load()
    setup_logging(cfg.log_level)

    if args.configure:
        cmd_configure(cfg, args)
    elif args.status:
        cmd_status(cfg, args)
    elif args.watch:
        cmd_watch(cfg, args)
    elif args.index:
        cmd_index(cfg, args)
    elif args.query:
        cmd_search(cfg, args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
