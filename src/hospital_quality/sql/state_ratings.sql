-- Mean star rating per state among rated acute care hospitals, plus the
-- for-profit share, which matters for reading the ownership comparison.
SELECT
    state,
    count(*)                                                       AS hospitals,
    round(avg(stars), 3)                                           AS mean_stars,
    round(100.0 * avg((ownership_group = 'For-profit')::INTEGER), 1) AS for_profit_pct
FROM rated_acute
GROUP BY state
ORDER BY state;
