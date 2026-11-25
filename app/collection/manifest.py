"""The collection manifest and the license rule for images (AGENTS.md, "Business rules").

Rules enforced here:
- an item that has no row in the manifest does not enter the collection;
- the booklet and its cover have independent licenses;
- an image is stored or indexed only when its license is confirmed and allows it.

This module is pure: it parses manifest text and decides, it never reads files.
"""

import csv
import io
from collections.abc import Mapping
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.errors import UnresolvedPendingError

MANIFEST_COLUMNS = (
    "id",
    "origin",
    "origin_url",
    "declared_authorship",
    "declared_authorship_source",
    "attributed_authorship",
    "attributed_authorship_source",
    "booklet_license",
    "cover_license",
)

# TODO(P-1): license vocabulary, mapping each license code to whether it allows storing
# and indexing the image. Until it is defined, any confirmed license fails loudly.
LICENSE_VOCABULARY: Mapping[str, bool] | None = None

LicenseCode = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+$")]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
HttpUrl = Annotated[str, StringConstraints(pattern=r"^https?://\S+$")]
ImagePart = Literal["booklet", "cover"]


class ItemNotInManifestError(LookupError):
    """The item has no row in the manifest, so it does not enter the collection."""


class UnknownLicenseError(ValueError):
    """The manifest uses a license code that is not in the vocabulary."""


class ManifestFormatError(ValueError):
    """The manifest text does not have the expected columns or has repeated ids."""


class ManifestItem(BaseModel):
    """One row of the manifest. Empty cells mean "unknown" or "not confirmed"."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    origin: NonBlank
    origin_url: HttpUrl | None = None
    declared_authorship: NonBlank | None = None
    declared_authorship_source: NonBlank | None = None
    attributed_authorship: NonBlank | None = None
    attributed_authorship_source: NonBlank | None = None
    booklet_license: LicenseCode | None = None
    cover_license: LicenseCode | None = None

    @model_validator(mode="after")
    def _authorship_has_source(self) -> "ManifestItem":
        if self.declared_authorship and not self.declared_authorship_source:
            raise ValueError("declared_authorship needs declared_authorship_source")
        if self.attributed_authorship and not self.attributed_authorship_source:
            raise ValueError("attributed_authorship needs attributed_authorship_source")
        return self

    def license_of(self, part: ImagePart) -> str | None:
        return self.booklet_license if part == "booklet" else self.cover_license


class Manifest(BaseModel):
    """All manifest rows, by id."""

    model_config = ConfigDict(frozen=True)

    items: Mapping[UUID, ManifestItem] = Field(default_factory=dict)

    def require(self, item_id: UUID) -> ManifestItem:
        try:
            return self.items[item_id]
        except KeyError:
            raise ItemNotInManifestError(f"item {item_id} has no row in the manifest") from None


def parse_manifest(text: str) -> Manifest:
    """Parse manifest CSV text. The header must list exactly MANIFEST_COLUMNS, in order."""
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != MANIFEST_COLUMNS:
        raise ManifestFormatError(
            f"manifest header must be {','.join(MANIFEST_COLUMNS)}, got {reader.fieldnames}"
        )
    items: dict[UUID, ManifestItem] = {}
    for line, row in enumerate(reader, start=2):
        cells = {key: (value if value and value.strip() else None) for key, value in row.items()}
        item = ManifestItem.model_validate(cells)
        if item.id in items:
            raise ManifestFormatError(f"line {line}: id {item.id} appears more than once")
        items[item.id] = item
    return Manifest(items=items)


def may_store_image(
    item: ManifestItem,
    part: ImagePart,
    vocabulary: Mapping[str, bool] | None = LICENSE_VOCABULARY,
) -> bool:
    """Whether the image of this part of the item may be downloaded, stored or indexed.

    An unconfirmed license (empty cell) never allows it, whatever the vocabulary says.
    """
    code = item.license_of(part)
    if code is None:
        return False
    if vocabulary is None:
        raise UnresolvedPendingError("P-1", "the license vocabulary is not defined")
    if code not in vocabulary:
        raise UnknownLicenseError(f"license {code!r} of item {item.id} is not in the vocabulary")
    return vocabulary[code]
