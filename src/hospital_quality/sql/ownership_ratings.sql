-- Star-rating distribution by ownership group among rated acute care hospitals.
SELECT
    ownership_group,
    count(*)                                            AS hospitals,
    round(avg(stars), 3)                                AS mean_stars,
    median(stars)                                       AS median_stars,
    round(100.0 * avg((stars >= 4)::INTEGER), 1)        AS pct_4_or_5,
    round(100.0 * avg((stars <= 2)::INTEGER), 1)        AS pct_1_or_2,
    count(*) FILTER (WHERE stars = 1)                   AS stars_1,
    count(*) FILTER (WHERE stars = 2)                   AS stars_2,
    count(*) FILTER (WHERE stars = 3)                   AS stars_3,
    count(*) FILTER (WHERE stars = 4)                   AS stars_4,
    count(*) FILTER (WHERE stars = 5)                   AS stars_5
FROM rated_acute
GROUP BY ownership_group
ORDER BY hospitals DESC;
