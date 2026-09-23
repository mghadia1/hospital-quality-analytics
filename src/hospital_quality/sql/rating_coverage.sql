-- Who gets a star rating at all, by hospital type, with the main reason for a
-- missing rating in CMS's own words.
WITH by_type AS (
    SELECT
        hospital_type,
        count(*)                                 AS hospitals,
        count(stars)                             AS rated,
        round(100.0 * count(stars) / count(*), 1) AS rated_pct
    FROM hospitals
    GROUP BY hospital_type
),
reasons AS (
    SELECT hospital_type, rating_footnote, count(*) AS n,
           row_number() OVER (PARTITION BY hospital_type ORDER BY count(*) DESC, rating_footnote) AS rk
    FROM hospitals
    WHERE stars IS NULL
    GROUP BY hospital_type, rating_footnote
)
SELECT
    b.*,
    r.rating_footnote AS main_missing_footnote,
    r.n               AS main_missing_count,
    f.footnote_text   AS main_missing_reason
FROM by_type AS b
LEFT JOIN reasons AS r ON r.hospital_type = b.hospital_type AND r.rk = 1
LEFT JOIN footnotes AS f ON f.footnote = r.rating_footnote
ORDER BY b.hospitals DESC;
