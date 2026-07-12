

/* ============================================================
   멸실(p_apt_멸실) → m_jk의 jk_code 기준(L2/L5/L7)으로 집계
   - 조인키:
     p.도시 = jk.jk_nm1
     CONCAT(p.구시군, p.`구`) = jk.jk_nm2   (공백없이 결합)
   - 기간: (YEAR(CURDATE())-5) ~ (YEAR(CURDATE())-1)
   ============================================================ */

-- =========================
-- L2 (시도 단위: 도시만)
-- =========================
SELECT
  'L2' AS lvl,
  jk.jk_gb,
  jk.jk_code,
  jk.jk_nm,

  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-5 THEN p.총세대수 ELSE 0 END) AS `y-5`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-4 THEN p.총세대수 ELSE 0 END) AS `y-4`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-3 THEN p.총세대수 ELSE 0 END) AS `y-3`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-2 THEN p.총세대수 ELSE 0 END) AS `y-2`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-1 THEN p.총세대수 ELSE 0 END) AS `y-1`,

  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) BETWEEN YEAR(CURDATE())-5 AND YEAR(CURDATE())-1
           THEN p.총세대수 ELSE 0 END) / 5 AS `5년평균`

FROM modueum.m_jk jk
LEFT JOIN modueum.p_apt_멸실 p
  ON p.도시 = jk.jk_nm1

 AND p.멸실시점 IS NOT NULL
 AND p.총세대수 > 0
 AND CAST(LEFT(p.멸실시점,4) AS UNSIGNED) BETWEEN YEAR(CURDATE())-5 AND YEAR(CURDATE())-1
 AND p.아파트유형구분 IN ('1','2','3','4','6','9')

WHERE jk.jk_gb = 'A'
  AND LENGTH(CAST(jk.jk_code AS CHAR)) = 2

GROUP BY jk.jk_gb, jk.jk_code, jk.jk_nm


UNION ALL


-- =========================
-- L5 (시군구 단위: 도시 + (구시군+구))
-- =========================
SELECT
  'L5' AS lvl,
  jk.jk_gb,
  jk.jk_code,
  jk.jk_nm,

  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-5 THEN p.총세대수 ELSE 0 END) AS `y-5`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-4 THEN p.총세대수 ELSE 0 END) AS `y-4`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-3 THEN p.총세대수 ELSE 0 END) AS `y-3`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-2 THEN p.총세대수 ELSE 0 END) AS `y-2`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-1 THEN p.총세대수 ELSE 0 END) AS `y-1`,

  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) BETWEEN YEAR(CURDATE())-5 AND YEAR(CURDATE())-1
           THEN p.총세대수 ELSE 0 END) / 5 AS `5년평균`

FROM modueum.m_jk jk
LEFT JOIN modueum.p_apt_멸실 p
  ON p.도시 = jk.jk_nm1
 AND CONCAT(p.구시군, p.`구`) = jk.jk_nm2

 AND p.멸실시점 IS NOT NULL
 AND p.총세대수 > 0
 AND CAST(LEFT(p.멸실시점,4) AS UNSIGNED) BETWEEN YEAR(CURDATE())-5 AND YEAR(CURDATE())-1
 AND p.아파트유형구분 IN ('1','2','3','4','6','9')

WHERE jk.jk_gb = 'A'
  AND LENGTH(CAST(jk.jk_code AS CHAR)) = 5

GROUP BY jk.jk_gb, jk.jk_code, jk.jk_nm


UNION ALL


-- =========================
-- L7 (더 상세 단위: jk_nm2 매칭 동일, 코드 길이만 7)
-- (※ 멸실 테이블이 '구'까지만 있으면 L5와 결과가 거의 동일할 수 있음)
-- =========================
SELECT
  'L7' AS lvl,
  jk.jk_gb,
  jk.jk_code,
  jk.jk_nm,

  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-5 THEN p.총세대수 ELSE 0 END) AS `y-5`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-4 THEN p.총세대수 ELSE 0 END) AS `y-4`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-3 THEN p.총세대수 ELSE 0 END) AS `y-3`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-2 THEN p.총세대수 ELSE 0 END) AS `y-2`,
  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) = YEAR(CURDATE())-1 THEN p.총세대수 ELSE 0 END) AS `y-1`,

  SUM(CASE WHEN CAST(LEFT(p.멸실시점,4) AS UNSIGNED) BETWEEN YEAR(CURDATE())-5 AND YEAR(CURDATE())-1
           THEN p.총세대수 ELSE 0 END) / 5 AS `5년평균`

FROM modueum.m_jk jk
LEFT JOIN modueum.p_apt_멸실 p
  ON p.도시 = jk.jk_nm1
 AND CONCAT(p.구시군, p.`구`) = jk.jk_nm2

 AND p.멸실시점 IS NOT NULL
 AND p.총세대수 > 0
 AND CAST(LEFT(p.멸실시점,4) AS UNSIGNED) BETWEEN YEAR(CURDATE())-5 AND YEAR(CURDATE())-1
 AND p.아파트유형구분 IN ('1','2','3','4','6','9')

WHERE jk.jk_gb = 'A'
  AND LENGTH(CAST(jk.jk_code AS CHAR)) = 7

GROUP BY jk.jk_gb, jk.jk_code, jk.jk_nm
;

