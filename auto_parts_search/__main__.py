"""CLI entry point for auto parts search pipeline.

Usage:
    python3 -m auto_parts_search scrape     # Run all scrapers
    python3 -m auto_parts_search pairs      # Generate training pairs (research + catalog)
    python3 -m auto_parts_search benchmark  # Generate evaluation benchmark
    python3 -m auto_parts_search all        # Run everything
    python3 -m auto_parts_search stats      # Show stats for existing data
"""
import logging
import sys
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auto_parts_search.config import RAW_DIR, TRAINING_DIR, KNOWLEDGE_GRAPH_DIR


def cmd_scrape():
    """Run all scrapers."""
    print("=" * 60)
    print("SCRAPING: Shopify platforms")
    print("=" * 60)
    try:
        from scrapers.shopify_scraper import scrape_all_shopify, save_products
        products = scrape_all_shopify()
        if products:
            output = RAW_DIR / "shopify_products.jsonl"
            save_products(products, output)
        else:
            print("No products scraped from Shopify platforms.")
    except Exception as e:
        print(f"Shopify scraping failed: {e}")

    print("\n" + "=" * 60)
    print("SCRAPING: Playwright platforms (Boodmo, Autozilla)")
    print("=" * 60)
    try:
        import asyncio
        from scrapers.playwright_scraper import scrape_all_playwright, save_products as pw_save
        products = asyncio.run(scrape_all_playwright())
        if products:
            output = RAW_DIR / "playwright_products.jsonl"
            pw_save(products, output)
        else:
            print("No products scraped from Playwright platforms.")
    except Exception as e:
        print(f"Playwright scraping failed: {e}")


def cmd_pairs():
    """Generate all training pairs."""
    all_pairs = []

    # 1. Research-based vocabulary pairs
    print("=" * 60)
    print("PAIRS: Research-based vocabulary pairs")
    print("=" * 60)
    try:
        from training.vocabulary_pairs import generate_vocabulary_pairs, save_pairs
        vocab_pairs = generate_vocabulary_pairs()
        output = TRAINING_DIR / "vocabulary_pairs.jsonl"
        save_pairs(vocab_pairs, output)
        all_pairs.extend(vocab_pairs)
        print(f"Generated {len(vocab_pairs)} vocabulary pairs")
    except Exception as e:
        print(f"Vocabulary pair generation failed: {e}")
        import traceback
        traceback.print_exc()

    # 2. Catalog-based pairs (requires scraped data)
    print("\n" + "=" * 60)
    print("PAIRS: Catalog-based pairs")
    print("=" * 60)
    try:
        from training.catalog_pairs import generate_from_all_sources, save_pairs as cat_save
        catalog_pairs = generate_from_all_sources()
        if catalog_pairs:
            output = TRAINING_DIR / "catalog_pairs.jsonl"
            cat_save(catalog_pairs, output)
            all_pairs.extend(catalog_pairs)
            print(f"Generated {len(catalog_pairs)} catalog pairs")
        else:
            print("No catalog pairs (scrape data first)")
    except Exception as e:
        print(f"Catalog pair generation failed: {e}")

    # 3. Combined output
    if all_pairs:
        combined_output = TRAINING_DIR / "all_pairs.jsonl"
        with open(combined_output, "w", encoding="utf-8") as f:
            for pair in all_pairs:
                f.write(json.dumps(pair.to_dict(), ensure_ascii=False) + "\n")
        print(f"\nCombined: {len(all_pairs)} total pairs → {combined_output}")

        # Stats
        from collections import Counter
        type_counts = Counter(p.pair_type for p in all_pairs)
        label_counts = Counter(p.label for p in all_pairs)
        print("\nBy type:")
        for t, c in type_counts.most_common():
            print(f"  {t}: {c}")
        print(f"\nPositive: {label_counts.get(1.0, 0)}, Negative: {label_counts.get(0.0, 0)}")


def cmd_benchmark():
    """Generate evaluation benchmark."""
    print("=" * 60)
    print("BENCHMARK: Generating 200-query evaluation set")
    print("=" * 60)
    try:
        from training.benchmark import generate_benchmark, save_benchmark, print_benchmark_stats
        queries = generate_benchmark()
        output = TRAINING_DIR / "benchmark.json"
        save_benchmark(queries, output)
        print_benchmark_stats(queries)
    except Exception as e:
        print(f"Benchmark generation failed: {e}")
        import traceback
        traceback.print_exc()


def cmd_graph():
    """Build knowledge graph from Phase 2 data sources."""
    print("=" * 60)
    print("GRAPH: Building knowledge graph")
    print("=" * 60)
    try:
        from auto_parts_search.build_graph import build_knowledge_graph, save_graph
        graph = build_knowledge_graph()
        output = KNOWLEDGE_GRAPH_DIR / "graph.json"
        save_graph(graph, output)
    except Exception as e:
        print(f"Knowledge graph build failed: {e}")
        import traceback
        traceback.print_exc()


def cmd_build_graph_db():
    """Materialize the knowledge graph to SQLite (ADR 007)."""
    print("=" * 60)
    print("GRAPH-DB: Materializing to SQLite")
    print("=" * 60)
    from auto_parts_search.build_graph import build_knowledge_graph
    from auto_parts_search.graph_db import GraphDB
    from auto_parts_search.config import GRAPH_DB

    graph = build_knowledge_graph()
    if GRAPH_DB.exists():
        GRAPH_DB.unlink()
    with GraphDB(GRAPH_DB) as db:
        db.init_schema()
        db.load_from_graph_dict(graph)
        counts = db.counts()

    print(f"\nNodes: {counts['nodes_total']}")
    for t, c in sorted(counts["nodes_by_type"].items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
    print(f"Edges: {counts['edges_total']}")
    for t, c in sorted(counts["edges_by_type"].items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
    print(f"\nWrote {GRAPH_DB} ({GRAPH_DB.stat().st_size / 1024:.1f} KB)")


def cmd_stats():
    """Show stats for existing data."""
    print("=" * 60)
    print("DATA STATS")
    print("=" * 60)

    # Raw data
    print("\n--- Raw Data ---")
    raw_files = list(RAW_DIR.glob("*.jsonl"))
    if raw_files:
        for f in raw_files:
            count = sum(1 for _ in open(f))
            print(f"  {f.name}: {count} products")
    else:
        print("  No raw data files. Run: python3 -m auto_parts_search scrape")

    # Training pairs
    print("\n--- Training Pairs ---")
    pair_files = list(TRAINING_DIR.glob("*.jsonl"))
    if pair_files:
        for f in pair_files:
            count = sum(1 for _ in open(f))
            print(f"  {f.name}: {count} pairs")
    else:
        print("  No training pair files. Run: python3 -m auto_parts_search pairs")

    # Benchmark
    print("\n--- Benchmark ---")
    benchmark_file = TRAINING_DIR / "benchmark.json"
    if benchmark_file.exists():
        with open(benchmark_file) as f:
            data = json.load(f)
        print(f"  benchmark.json: {len(data)} queries")
    else:
        print("  No benchmark. Run: python3 -m auto_parts_search benchmark")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "scrape":
        cmd_scrape()
    elif command == "pairs":
        cmd_pairs()
    elif command == "benchmark":
        cmd_benchmark()
    elif command == "graph":
        cmd_graph()
    elif command in ("build-graph-db", "graph-db"):
        cmd_build_graph_db()
    elif command == "stats":
        cmd_stats()
    elif command == "all":
        cmd_scrape()
        print("\n")
        cmd_pairs()
        print("\n")
        cmd_benchmark()
        print("\n")
        cmd_stats()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
