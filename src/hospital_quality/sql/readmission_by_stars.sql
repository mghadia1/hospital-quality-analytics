-- Per hospital: mean excess readmission ratio across the conditions it reports,
-- joined to its star rating. Hospitals with fewer than 3 reportable conditions
-- are left out so one noisy condition cannot define a hospital.
WITH per_hospital AS (
    SELECT facility_id, avg(excess_ratio) AS mean_ratio, count(excess_ratio) AS conditions
    FROM readmissions
    WHERE excess_ratio IS NOT NULL
    GROUP BY facility_id
    HAVING count(excess_ratio) >= 3
)
SELECT h.facility_id, h.state, h.ownership_group, h.stars, p.mean_ratio, p.conditions
FROM rated_acute AS h
JOIN per_hospital AS p USING (facility_id)
ORDER BY h.facility_id;
