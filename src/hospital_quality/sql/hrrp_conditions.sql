-- For each HRRP condition: how many hospitals have a reportable excess
-- readmission ratio (ERR), and what share are above 1.0 (more readmissions than
-- CMS's risk model expected; an ERR above 1 is what drives the payment penalty).
SELECT
    condition,
    count(*)                                              AS hospital_rows,
    count(excess_ratio)                                   AS with_ratio,
    round(100.0 * count(excess_ratio) / count(*), 1)      AS reported_pct,
    round(median(excess_ratio), 4)                        AS median_ratio,
    round(100.0 * avg((excess_ratio > 1)::INTEGER), 1)    AS pct_above_1
FROM readmissions
GROUP BY condition
ORDER BY condition;
