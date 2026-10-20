"""Local TF-IDF product evidence retriever."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import re

from sklearn.feature_extraction.text import TfidfVectorizer

from metso_agent.schemas import ProductEvidence
from metso_agent.retrieval.brochure_loader import load_brochures


@dataclass(frozen=True)
class SearchHit:
    evidence: ProductEvidence
    score: float


def expand_query(query: str) -> str:
    """
    Add retrieval vocabulary.

    Expanded terms only help searching.
    They are not evidence of a technical fact.
    """

    terms = [query]

    triggers = (
        (
            r"\b(filter|filtration|larox|press)\w*\b",
            "filter filtration pressure filter cycle",
        ),
        (
            r"\b(change|changes|changing|vary|varying|"
            r"variable|variation|fluctuat\w*|unstable|"
            r"drop\w*|declin\w*)\b",
            "variations adapt optimization automatic "
            "control changing conditions",
        ),
        (
            r"\b(performance|throughput|cycle|moisture)\b",
            "filtration efficiency performance "
            "setpoints throughput",
        ),
        (
            r"\b(cloth|cloths|fabric)\b",
            "filter cloth replacement washing",
        ),
    )

    for pattern, expansion in triggers:
        if re.search(pattern, query, re.IGNORECASE):
            terms.append(expansion)

    return " ".join(terms)


class ProductSearcher:

    def __init__(
        self,
        evidence: list[ProductEvidence],
    ):

        if not evidence:
            raise ValueError(
                "Cannot index an empty evidence collection"
            )

        self.evidence = evidence

        documents = [
            (
                f"{item.product_name} "
                f"{item.source.document_id.replace('-', ' ')} "
                f"{item.excerpt}"
            )
            for item in evidence
        ]

        self.word_vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )

        self.char_vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            sublinear_tf=True,
        )

        self.word_matrix = (
            self.word_vectorizer.fit_transform(documents)
        )

        self.char_matrix = (
            self.char_vectorizer.fit_transform(documents)
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        max_per_document: int = 2,
    ) -> list[SearchHit]:

        if not query.strip():
            raise ValueError(
                "Search query cannot be blank"
            )

        if top_k < 1 or max_per_document < 1:
            raise ValueError(
                "top_k and max_per_document must be positive"
            )

        expanded_query = expand_query(query)

        query_words = (
            self.word_vectorizer.transform(
                [expanded_query]
            )
        )

        query_chars = (
            self.char_vectorizer.transform(
                [expanded_query]
            )
        )

        word_scores = (
            self.word_matrix @ query_words.T
        ).toarray().ravel()

        char_scores = (
            self.char_matrix @ query_chars.T
        ).toarray().ravel()

        scores = (
            0.75 * word_scores
            + 0.25 * char_scores
        )

        order = sorted(
            range(len(scores)),
            key=lambda index: (
                -float(scores[index]),
                self.evidence[index].chunk_id,
            ),
        )

        results: list[SearchHit] = []

        counts: dict[str, int] = {}

        for index in order:

            score = float(scores[index])

            if score <= 0:
                continue

            evidence = self.evidence[index]

            document_id = (
                evidence.source.document_id
            )

            if counts.get(document_id, 0) >= max_per_document:
                continue

            results.append(
                SearchHit(
                    evidence=evidence,
                    score=score,
                )
            )

            counts[document_id] = (
                counts.get(document_id, 0) + 1
            )

            if len(results) >= top_k:
                break

        return results


def main() -> None:

    project_root = (
        Path(__file__).resolve().parents[3]
    )

    parser = argparse.ArgumentParser(
        description=(
            "Search local Metso brochure evidence"
        )
    )

    parser.add_argument(
        "query",
        help="Customer product question",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--brochures",
        type=Path,
        default=(
            project_root
            / "raw"
            / "data"
            / "brochures"
        ),
    )

    args = parser.parse_args()

    try:

        chunks = load_brochures(
            args.brochures
        )

        searcher = ProductSearcher(chunks)

        results = searcher.search(
            args.query,
            top_k=args.top_k,
        )

    except (FileNotFoundError, ValueError) as exc:

        parser.exit(
            2,
            f"Retrieval error: {exc}\n",
        )

    document_count = len({
        chunk.source.document_id
        for chunk in chunks
    })

    print(
        f"Indexed {len(chunks)} chunks "
        f"from {document_count} brochures"
    )

    if not results:

        print(
            "No lexical evidence found. "
            "Do not invent an answer."
        )

        return

    for rank, hit in enumerate(results, start=1):

        evidence = hit.evidence

        preview = " ".join(
            evidence.excerpt.split()
        )[:180]

        print(
            f"{rank}. "
            f"{evidence.source.document_id}.md "
            f"| page {evidence.source.page_number} "
            f"| score={hit.score:.3f}"
        )

        print(
            f"   chunk={evidence.chunk_id} "
            f"| excerpt={preview}..."
        )

    print(
        "Retrieval only: verify claims "
        "in the cited PDF and ask "
        "for missing context."
    )


if __name__ == "__main__":
    main()