ALTER TABLE match_history
ADD COLUMN norad_code TEXT;

ALTER TABLE match_history
DROP COLUMN satellite_name;
