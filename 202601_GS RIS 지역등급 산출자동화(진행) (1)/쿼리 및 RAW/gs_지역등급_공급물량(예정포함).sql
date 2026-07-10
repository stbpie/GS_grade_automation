
# 여러연도 입주물량
-- L2: M_JK 코드 길이 2만
SELECT
  'L2' AS lvl,
  jk.JK_GB,
  jk.JK_CODE,
  jk.JK_NM,
  COALESCE(a.qty_2024, 0) AS qty_2024,
  COALESCE(a.qty_2025, 0) AS qty_2025,
  COALESCE(a.qty_2026, 0) AS qty_2026,
  (COALESCE(a.qty_2024,0) + COALESCE(a.qty_2025,0) + COALESCE(a.qty_2026,0)) / 3 AS qty_avg_3y
FROM modueum.M_JK jk
LEFT JOIN (
  SELECT
    LEFT(CAST(jk_code AS CHAR), 2) AS code_prefix,
    SUM(CASE WHEN LEFT(ibju_dt, 4) = '2024' THEN qty ELSE 0 END) AS qty_2024,
    SUM(CASE WHEN LEFT(ibju_dt, 4) = '2025' THEN qty ELSE 0 END) AS qty_2025,
    SUM(CASE WHEN LEFT(ibju_dt, 4) = '2026' THEN qty ELSE 0 END) AS qty_2026
  FROM modueum.m_apt_mast
  WHERE LEFT(ibju_dt, 4) IN ('2024','2025','2026')
    AND ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(jk_code AS CHAR), 2)
) a
  ON a.code_prefix = jk.JK_CODE
WHERE jk.jk_gb = 'A'
  AND LENGTH(CAST(jk.JK_CODE AS CHAR)) = 2

UNION ALL

-- L5: M_JK 코드 길이 5만
SELECT
  'L5' AS lvl,
  jk.JK_GB,
  jk.JK_CODE,
  jk.JK_NM,
  COALESCE(a.qty_2024, 0) AS qty_2024,
  COALESCE(a.qty_2025, 0) AS qty_2025,
  COALESCE(a.qty_2026, 0) AS qty_2026,
  (COALESCE(a.qty_2024,0) + COALESCE(a.qty_2025,0) + COALESCE(a.qty_2026,0)) / 3 AS qty_avg_3y
FROM modueum.M_JK jk
LEFT JOIN (
  SELECT
    LEFT(CAST(jk_code AS CHAR), 5) AS code_prefix,
    SUM(CASE WHEN LEFT(ibju_dt, 4) = '2024' THEN qty ELSE 0 END) AS qty_2024,
    SUM(CASE WHEN LEFT(ibju_dt, 4) = '2025' THEN qty ELSE 0 END) AS qty_2025,
    SUM(CASE WHEN LEFT(ibju_dt, 4) = '2026' THEN qty ELSE 0 END) AS qty_2026
  FROM modueum.m_apt_mast
  WHERE LEFT(ibju_dt, 4) IN ('2024','2025','2026')
    AND ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(jk_code AS CHAR), 5)
) a
  ON a.code_prefix = jk.JK_CODE
WHERE jk.jk_gb = 'A'
  AND LENGTH(CAST(jk.JK_CODE AS CHAR)) = 5

UNION ALL

-- L7: M_JK 코드 길이 7만
SELECT
  'L7' AS lvl,
  jk.JK_GB,
  jk.JK_CODE,
  jk.JK_NM,
  COALESCE(a.qty_2024, 0) AS qty_2024,
  COALESCE(a.qty_2025, 0) AS qty_2025,
  COALESCE(a.qty_2026, 0) AS qty_2026,
  (COALESCE(a.qty_2024,0) + COALESCE(a.qty_2025,0) + COALESCE(a.qty_2026,0)) / 3 AS qty_avg_3y
FROM modueum.M_JK jk
LEFT JOIN (
  SELECT
    LEFT(CAST(jk_code AS CHAR), 7) AS code_prefix,
    SUM(CASE WHEN LEFT(ibju_dt, 4) = '2024' THEN qty ELSE 0 END) AS qty_2024,
    SUM(CASE WHEN LEFT(ibju_dt, 4) = '2025' THEN qty ELSE 0 END) AS qty_2025,
    SUM(CASE WHEN LEFT(ibju_dt, 4) = '2026' THEN qty ELSE 0 END) AS qty_2026
  FROM modueum.m_apt_mast
  WHERE LEFT(ibju_dt, 4) IN ('2024','2025','2026')
    AND ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(jk_code AS CHAR), 7)
) a
  ON a.code_prefix = jk.JK_CODE
WHERE jk.jk_gb = 'A'
  AND LENGTH(CAST(jk.JK_CODE AS CHAR)) = 7
;



