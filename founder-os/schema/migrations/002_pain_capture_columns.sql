-- Safari capture columns on pains (VCL vibecodelisboa migration 0084).
-- A VCL student saves quotes from the web with a browser extension; each
-- capture is a pains row that also keeps the page title, the student's typed
-- note, a screenshot URL and where the row came from. All nullable, so rows
-- written before this migration, and rows from add_pain without them, stay
-- valid. source is one of extension, card or api when set.

ALTER TABLE pains ADD COLUMN page_title TEXT;
ALTER TABLE pains ADD COLUMN note TEXT;
ALTER TABLE pains ADD COLUMN screenshot_url TEXT;
ALTER TABLE pains ADD COLUMN source TEXT CHECK (source IS NULL OR source IN ('extension', 'card', 'api'));
