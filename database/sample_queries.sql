-- 1. Match journal: filter by account and date, then show the latest 50 matches.
SELECT m.id, m.played_at, m.map_name, m.placement, m.rp
FROM "match" AS m
WHERE m.user_id = (SELECT id FROM "user" WHERE username = :username)
  AND m.played_at BETWEEN :date_from AND :date_to
ORDER BY m.played_at DESC, m.id DESC
LIMIT 50;

-- 2. Daily RP totals: one row per day, ready for the cumulative RP chart.
SELECT m.played_at, COUNT(*) AS match_count, SUM(m.rp) AS daily_rp
FROM "match" AS m
WHERE m.user_id = (SELECT id FROM "user" WHERE username = :username)
  AND m.played_at BETWEEN :date_from AND :date_to
GROUP BY m.played_at
ORDER BY m.played_at;

-- 3. Weapon usage: each match counts once per weapon, even across two slots.
WITH match_weapons AS (
    SELECT DISTINCT match_id, weapon_id FROM match_weapon
)
SELECT w.name, COUNT(*) AS match_count, ROUND(AVG(m.rp), 1) AS avg_rp
FROM "match" AS m
JOIN match_weapons AS mw ON mw.match_id = m.id
JOIN weapon AS w ON w.id = mw.weapon_id
WHERE m.user_id = (SELECT id FROM "user" WHERE username = :username)
  AND m.played_at BETWEEN :date_from AND :date_to
GROUP BY w.id, w.name
ORDER BY match_count DESC, w.name;

-- 4. Map performance: filter grouped results by minimum match count.
SELECT m.map_name, COUNT(*) AS match_count,
       ROUND(AVG(m.rp), 1) AS avg_rp, ROUND(AVG(m.damage), 1) AS avg_damage
FROM "match" AS m
WHERE m.user_id = (SELECT id FROM "user" WHERE username = :username)
  AND m.played_at BETWEEN :date_from AND :date_to
GROUP BY m.map_name
HAVING COUNT(*) >= :min_matches
ORDER BY AVG(m.rp) DESC, m.map_name;
