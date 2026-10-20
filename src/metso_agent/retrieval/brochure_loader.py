"""Load authorized Markdown brochures as page-traceable evidence."""

from pathlib import Path
import re

from metso_agent.schemas import ProductEvidence, SourceRef


PAGE_PATTERN = re.compile(
    r"(?m)^[ \t]{0,3}#{1,8}[ \t]+Page[ \t]+(?P<page>\d+)\b[^\n]*$"
)

WORD_PATTERN = re.compile(r"\S+")


def load_brochures(
    brochure_dir: Path,
    window_words: int = 300,
    overlap_words: int = 45,
) -> list[ProductEvidence]:
    """
    Read Markdown brochures and produce page-grounded chunks.

    Every Markdown brochure must have a matching PDF.
    Page numbers are read from explicit source markers.
    Missing or inconsistent page markers raise errors.
    """

    if window_words < 20 or not 0 <= overlap_words < window_words:
        raise ValueError("Invalid chunk window or overlap")

    brochure_dir = Path(brochure_dir)

    if not brochure_dir.is_dir():
        raise FileNotFoundError(
            f"Brochure folder not found: {brochure_dir}"
        )

    md_files = sorted(brochure_dir.glob("*.md"))

    pdf_stems = {
        path.stem
        for path in brochure_dir.glob("*.pdf")
    }

    md_stems = {
        path.stem
        for path in md_files
    }

    if not md_files:
        raise ValueError("No Markdown brochures found")

    if md_stems != pdf_stems:
        raise ValueError(
            "Brochure pairing mismatch: "
            f"missing PDFs={sorted(md_stems - pdf_stems)}, "
            f"missing Markdown={sorted(pdf_stems - md_stems)}"
        )

    chunks: list[ProductEvidence] = []

    for path in md_files:

        text = path.read_text(encoding="utf-8-sig")

        matches = list(PAGE_PATTERN.finditer(text))

        if not matches:
            raise ValueError(
                f"No explicit page markers: {path.name}"
            )

        page_numbers = [
            int(match.group("page"))
            for match in matches
        ]

        expected_pages = list(
            range(1, len(page_numbers) + 1)
        )

        if page_numbers != expected_pages:
            raise ValueError(
                "Missing, duplicated, or unordered pages: "
                f"{path.name}"
            )

        for page_index, marker in enumerate(matches):

            page_number = page_numbers[page_index]

            page_start = marker.end()

            if page_index + 1 < len(matches):
                page_end = matches[page_index + 1].start()
            else:
                page_end = len(text)

            page_text = text[
                page_start:page_end
            ].strip()

            words = list(
                WORD_PATTERN.finditer(page_text)
            )

            if not words:
                raise ValueError(
                    "Empty source page: "
                    f"{path.name}, page {page_number}"
                )

            step = window_words - overlap_words

            for chunk_number, start in enumerate(
                range(0, len(words), step),
                start=1,
            ):

                stop = min(
                    start + window_words,
                    len(words),
                )

                char_start = words[start].start()
                char_end = words[stop - 1].end()

                excerpt = page_text[
                    char_start:char_end
                ]

                evidence = ProductEvidence(
                    product_name=(
                        path.stem.replace("-", " ").title()
                    ),
                    chunk_id=(
                        f"{path.stem}:"
                        f"p{page_number}:"
                        f"c{chunk_number:02d}"
                    ),
                    excerpt=excerpt,
                    source=SourceRef(
                        source_kind="brochure",
                        document_id=path.stem,
                        page_number=page_number,
                        location=(
                            f"page_char:"
                            f"{char_start}-{char_end}"
                        ),
                    ),
                )

                chunks.append(evidence)

                if stop == len(words):
                    break

    return chunks