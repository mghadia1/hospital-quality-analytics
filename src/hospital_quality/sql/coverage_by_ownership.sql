-- Among general acute care hospitals, does the chance of being rated at all
-- differ by owner? If it did, comparing rated hospitals alone would be biased.
SELECT
    ownership_group,
    count(*)                                  AS hospitals,
    count(stars)                              AS rated,
    round(100.0 * count(stars) / count(*), 1) AS rated_pct
FROM hospitals
WHERE hospital_type = 'Acute Care Hospitals'
GROUP BY ownership_group
ORDER BY hospitals DESC;
