-- Title of the booklet and the engraver of its cover woodcut (AGENTS.md, "The cover has
-- its own license"). All nullable: an empty value means unknown or not confirmed.
-- The engraver, like authorship, is never recorded without its source.

ALTER TABLE collection_item
    ADD COLUMN title           text,
    ADD COLUMN engraver        text,
    ADD COLUMN engraver_source text,
    ADD CONSTRAINT ck_collection_item_engraver_has_source
        CHECK (engraver IS NULL OR engraver_source IS NOT NULL);
