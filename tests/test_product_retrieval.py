from pathlib import Path

import pytest

from metso_agent.retrieval.brochure_loader import (
    load_brochures,
)

from metso_agent.retrieval.product_search import (
    ProductSearcher,
)


def make_pair(
    folder: Path,
    stem: str,
    pages: list[str],
) -> None:

    (folder / f"{stem}.pdf").write_bytes(
        b"%PDF TEST FIXTURE ONLY"
    )

    text = (
        f"# {stem}\n"
        "Source: synthetic.pdf\n\n"
    )

    text += "\n\n".join(
        f"## Page {number}\n\n{page}"
        for number, page in enumerate(
            pages,
            start=1,
        )
    )

    (folder / f"{stem}.md").write_text(
        text,
        encoding="utf-8",
    )


def test_page_provenance(tmp_path):

    make_pair(
        tmp_path,
        "demo-filter",
        [
            "A filter demonstration.",
            "Another filter demonstration.",
        ],
    )

    chunks = load_brochures(tmp_path)

    assert [
        chunk.source.page_number
        for chunk in chunks
    ] == [1, 2]

    assert all(
        chunk.source.document_id == "demo-filter"
        for chunk in chunks
    )


def test_missing_pdf_pair_fails(tmp_path):

    (tmp_path / "demo.md").write_text(
        "## Page 1\nValid content",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="pairing mismatch",
    ):
        load_brochures(tmp_path)


def test_missing_page_marker_fails(tmp_path):

    (tmp_path / "demo.pdf").write_bytes(
        b"fixture"
    )

    (tmp_path / "demo.md").write_text(
        "No page heading",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="page markers",
    ):
        load_brochures(tmp_path)


def test_nonconsecutive_pages_fail(tmp_path):

    (tmp_path / "demo.pdf").write_bytes(
        b"fixture"
    )

    (tmp_path / "demo.md").write_text(
        "## Page 1\nHello\n"
        "## Page 3\nWorld",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="pages",
    ):
        load_brochures(tmp_path)


def test_search_finds_relevant_product(tmp_path):

    make_pair(
        tmp_path,
        "filter-optimizer",
        [
            "Automatic cycle by cycle optimization "
            "adapts filtration setpoints to "
            "changing feed conditions."
        ],
    )

    make_pair(
        tmp_path,
        "slurry-pump",
        [
            "Centrifugal pumps transport "
            "abrasive slurries in pipelines."
        ],
    )

    searcher = ProductSearcher(
        load_brochures(tmp_path)
    )

    results = searcher.search(
        "Our filtration performance varies "
        "with changing feed",
        top_k=2,
    )

    assert (
        results[0].evidence.source.document_id
        == "filter-optimizer"
    )


def test_empty_query_rejected(tmp_path):

    make_pair(
        tmp_path,
        "filter-optimizer",
        ["Filter performance optimization."],
    )

    searcher = ProductSearcher(
        load_brochures(tmp_path)
    )

    with pytest.raises(
        ValueError,
        match="blank",
    ):
        searcher.search("   ")


def test_chunks_never_cross_pages(tmp_path):

    make_pair(
        tmp_path,
        "demo-filter",
        [
            "alpha " * 70,
            "beta " * 70,
        ],
    )

    chunks = load_brochures(
        tmp_path,
        window_words=25,
        overlap_words=5,
    )

    assert len(chunks) > 2

    for chunk in chunks:
        assert (
            ("alpha" in chunk.excerpt)
            != ("beta" in chunk.excerpt)
        )