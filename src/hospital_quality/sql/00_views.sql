-- Typed views over the raw CMS files. Inputs: raw_hospitals, raw_hrrp, raw_footnotes,
-- each read with every column as VARCHAR so that "Not Available", "N/A" and
-- "Too Few to Report" arrive as text and are converted here, in one place.

CREATE OR REPLACE VIEW hospitals AS
SELECT
    "Facility ID"                              AS facility_id,
    "Facility Name"                            AS facility_name,
    "City/Town"                                AS city,
    "State"                                    AS state,
    "Hospital Type"                            AS hospital_type,
    "Hospital Ownership"                       AS ownership,
    CASE
        WHEN "Hospital Ownership" LIKE 'Voluntary non-profit%' THEN 'Non-profit'
        WHEN "Hospital Ownership" = 'Proprietary'              THEN 'For-profit'
        WHEN "Hospital Ownership" = 'Physician'                THEN 'Physician-owned'
        ELSE 'Government'  -- federal, state, local, district, tribal, VA, DoD
    END                                        AS ownership_group,
    "Emergency Services" = 'Yes'               AS has_emergency,
    TRY_CAST("Hospital overall rating" AS INTEGER) AS stars,
    -- a hospital can carry several footnotes ("16, 23"); keep the first as the reason
    NULLIF(trim(split_part("Hospital overall rating footnote", ',', 1)), '') AS rating_footnote
FROM raw_hospitals;

-- One row per hospital per condition. CMS writes "N/A" and "Too Few to Report"
-- where a value is suppressed; TRY_CAST turns those into NULL.
CREATE OR REPLACE VIEW readmissions AS
SELECT
    "Facility ID"                                                AS facility_id,
    regexp_extract("Measure Name", 'READM-30-(.*)-HRRP', 1)      AS condition,
    TRY_CAST("Number of Discharges" AS INTEGER)                  AS discharges,
    TRY_CAST("Excess Readmission Ratio" AS DOUBLE)               AS excess_ratio,
    TRY_CAST("Predicted Readmission Rate" AS DOUBLE)             AS predicted_rate,
    TRY_CAST("Expected Readmission Rate" AS DOUBLE)              AS expected_rate,
    NULLIF(trim("Footnote"), '')                                 AS footnote
FROM raw_hrrp;

CREATE OR REPLACE VIEW footnotes AS
SELECT trim("Footnote") AS footnote, "Footnote Text" AS footnote_text FROM raw_footnotes;

-- The comparison population for rating analyses: general acute care hospitals
-- that received a rating. Critical access, VA, psychiatric and children's
-- hospitals differ in mission and are mostly unrated; mixing them in would
-- compare hospital types, not owners.
CREATE OR REPLACE VIEW rated_acute AS
SELECT * FROM hospitals
WHERE hospital_type = 'Acute Care Hospitals' AND stars IS NOT NULL;
