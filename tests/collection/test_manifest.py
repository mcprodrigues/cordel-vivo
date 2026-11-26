"""Manifest and image license rules (AGENTS.md, "Business rules" and principle 4).

Rule tests use fixture codes ("test_open", "test_closed") so that they hold whatever the
vocabulary says; the real vocabulary (P-1, resolved in #21) has tests of its own below.
"""

import random
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.collection.manifest import (
    LICENSE_VOCABULARY,
    MANIFEST_COLUMNS,
    ImagePart,
    ItemNotInManifestError,
    ManifestFormatError,
    ManifestItem,
    UnknownLicenseError,
    may_store_image,
    parse_manifest,
)

HEADER = ",".join(MANIFEST_COLUMNS)
VOCABULARY = {"test_open": True, "test_closed": False}


def row(
    item_id: UUID,
    *,
    origin: str = "FCRB",
    origin_url: str = "https://example.org/item",
    title: str = "",
    declared: str = "",
    declared_source: str = "",
    attributed: str = "",
    attributed_source: str = "",
    engraver: str = "",
    engraver_source: str = "",
    booklet_license: str = "",
    booklet_license_source: str = "",
    cover_license: str = "",
    cover_license_source: str = "",
) -> str:
    return ",".join(
        [
            str(item_id),
            origin,
            origin_url,
            title,
            declared,
            declared_source,
            attributed,
            attributed_source,
            engraver,
            engraver_source,
            booklet_license,
            booklet_license_source,
            cover_license,
            cover_license_source,
        ]
    )


def manifest_text(*rows: str) -> str:
    return "\n".join([HEADER, *rows]) + "\n"


def item(booklet_license: str | None = None, cover_license: str | None = None) -> ManifestItem:
    """An item with the given licenses, each recorded with a test source."""
    return ManifestItem(
        id=uuid4(),
        origin="FCRB",
        booklet_license=booklet_license,
        booklet_license_source="test source" if booklet_license else None,
        cover_license=cover_license,
        cover_license_source="test source" if cover_license else None,
    )


def test_item_in_manifest_is_found() -> None:
    item_id = uuid4()
    manifest = parse_manifest(manifest_text(row(item_id)))

    assert manifest.require(item_id).origin == "FCRB"


def test_item_without_manifest_row_is_rejected() -> None:
    manifest = parse_manifest(manifest_text(row(uuid4())))

    with pytest.raises(ItemNotInManifestError):
        manifest.require(uuid4())


def test_empty_cells_mean_unknown_or_not_confirmed() -> None:
    item_id = uuid4()
    parsed = parse_manifest(manifest_text(row(item_id, origin_url=""))).require(item_id)

    assert parsed.origin_url is None
    assert parsed.booklet_license is None
    assert parsed.cover_license is None


def test_cover_license_is_independent_of_booklet_license() -> None:
    entry = item(booklet_license="test_open")

    assert may_store_image(entry, "booklet", VOCABULARY) is True
    assert may_store_image(entry, "cover", VOCABULARY) is False


def test_cover_may_be_allowed_when_booklet_is_not() -> None:
    entry = item(booklet_license="test_closed", cover_license="test_open")

    assert may_store_image(entry, "booklet", VOCABULARY) is False
    assert may_store_image(entry, "cover", VOCABULARY) is True


@pytest.mark.parametrize("part", ["booklet", "cover"])
def test_unconfirmed_license_never_allows_image(part: ImagePart) -> None:
    # Holds whatever the vocabulary says.
    entry = item()

    assert may_store_image(entry, part) is False
    assert may_store_image(entry, part, {"anything": True}) is False


def test_license_that_forbids_images_is_respected() -> None:
    assert may_store_image(item(booklet_license="test_closed"), "booklet", VOCABULARY) is False


@pytest.mark.parametrize("part", ["booklet", "cover"])
@pytest.mark.parametrize("code", ["public_domain", "written_authorization"])
def test_public_domain_and_written_authorization_allow_image(code: str, part: ImagePart) -> None:
    entry = item(**{f"{part}_license": code})

    assert may_store_image(entry, part) is True


@pytest.mark.parametrize("part", ["booklet", "cover"])
def test_metadata_only_never_allows_image(part: ImagePart) -> None:
    assert may_store_image(item(**{f"{part}_license": "metadata_only"}), part) is False


def test_license_vocabulary_is_the_approved_one() -> None:
    assert dict(LICENSE_VOCABULARY) == {
        "public_domain": True,
        "written_authorization": True,
        "metadata_only": False,
    }


def test_license_vocabulary_cannot_be_changed_at_runtime() -> None:
    with pytest.raises(TypeError):
        LICENSE_VOCABULARY["metadata_only"] = True  # type: ignore[index]


def test_unknown_license_is_rejected_by_the_real_vocabulary() -> None:
    with pytest.raises(UnknownLicenseError):
        may_store_image(item(booklet_license="cc_by"), "booklet")


def test_unknown_license_is_rejected() -> None:
    with pytest.raises(UnknownLicenseError):
        may_store_image(item(cover_license="not_listed"), "cover", VOCABULARY)


def test_changing_the_vocabulary_changes_the_decision() -> None:
    entry = item(booklet_license="test_open")

    assert may_store_image(entry, "booklet", {"test_open": True}) is True
    assert may_store_image(entry, "booklet", {"test_open": False}) is False


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("declared_authorship", "Leandro"),
        ("attributed_authorship", "Leandro"),
        ("engraver", "Leandro"),
        ("booklet_license", "public_domain"),
        ("cover_license", "public_domain"),
    ],
)
def test_claims_are_recorded_only_with_their_source(claim: str, value: str) -> None:
    with pytest.raises(ValidationError, match=f"{claim} needs {claim}_source"):
        ManifestItem.model_validate({"id": str(uuid4()), "origin": "FCRB", claim: value})


def test_declared_and_attributed_authorship_are_kept_apart() -> None:
    entry = ManifestItem(
        id=uuid4(),
        origin="FCRB",
        declared_authorship="João Martins de Athayde",
        declared_authorship_source="printed on the booklet",
        attributed_authorship="Leandro Gomes de Barros",
        attributed_authorship_source="test source",
    )

    assert entry.declared_authorship != entry.attributed_authorship


def test_engraver_is_recorded_apart_from_authorship() -> None:
    item_id = uuid4()
    text = manifest_text(
        row(
            item_id,
            title="test title",
            declared="test author",
            declared_source="printed on the booklet",
            engraver="test engraver",
            engraver_source="test source",
        )
    )
    entry = parse_manifest(text).require(item_id)

    assert entry.title == "test title"
    assert entry.engraver == "test engraver"
    assert entry.declared_authorship == "test author"


@pytest.mark.parametrize(
    "fields",
    [
        {"origin": " "},
        {"origin_url": "ftp://example.org"},
        {"origin_url": "javascript:alert(1)"},
        {"booklet_license": "Public Domain"},
    ],
    ids=["blank-origin", "ftp-url", "script-url", "license-not-a-code"],
)
def test_invalid_manifest_values_are_rejected(fields: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        ManifestItem.model_validate({"id": str(uuid4()), "origin": "FCRB", **fields})


def test_unknown_manifest_column_is_rejected() -> None:
    with pytest.raises(ManifestFormatError):
        parse_manifest(HEADER + ",extra\n")


def test_missing_manifest_column_is_rejected() -> None:
    with pytest.raises(ManifestFormatError):
        parse_manifest(",".join(MANIFEST_COLUMNS[:-1]) + "\n")


def test_repeated_item_id_is_rejected() -> None:
    item_id = uuid4()
    with pytest.raises(ManifestFormatError, match="more than once"):
        parse_manifest(manifest_text(row(item_id), row(item_id)))


def test_manifest_does_not_depend_on_row_order() -> None:
    rows = [
        row(uuid4(), booklet_license="test_open", booklet_license_source="test source")
        for _ in range(20)
    ]
    shuffled = rows.copy()
    random.Random(7).shuffle(shuffled)

    assert parse_manifest(manifest_text(*rows)) == parse_manifest(manifest_text(*shuffled))


def test_parsing_is_deterministic() -> None:
    text = manifest_text(*(row(uuid4()) for _ in range(5)))

    assert parse_manifest(text) == parse_manifest(text)
