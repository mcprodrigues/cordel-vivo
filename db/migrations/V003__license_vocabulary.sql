-- License vocabulary (open item P-1, resolved in #21). Conservative: an image is
-- allowed only when it is clearly safe; in doubt, an item gets metadata_only.
-- Kept equal to LICENSE_VOCABULARY in app/collection/manifest.py (checked by tests).

INSERT INTO license (code, description, allows_image) VALUES
    ('public_domain',
     'The author, or the engraver for the cover, died more than 70 years ago '
     '(Law 9.610/98, art. 41).',
     true),
    ('written_authorization',
     'Written authorization from the poet, the engraver or the holding institution '
     'to use the image.',
     true),
    ('metadata_only',
     'Protected, not authorized, or in doubt: only metadata and a link to the source.',
     false);

COMMENT ON TABLE license IS 'License vocabulary (P-1, resolved in #21).';

-- Every license is recorded with its source, like authorship: the death year and where
-- it came from, the authorization document, or the reason for metadata_only.
ALTER TABLE collection_item
    ADD COLUMN booklet_license_source text,
    ADD COLUMN cover_license_source   text,
    ADD CONSTRAINT ck_collection_item_booklet_license_has_source
        CHECK (booklet_license IS NULL OR booklet_license_source IS NOT NULL),
    ADD CONSTRAINT ck_collection_item_cover_license_has_source
        CHECK (cover_license IS NULL OR cover_license_source IS NOT NULL);
