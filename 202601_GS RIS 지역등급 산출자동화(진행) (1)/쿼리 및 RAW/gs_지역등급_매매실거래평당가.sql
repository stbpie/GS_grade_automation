/* ============================================================
   목적: 계산 X
   - 조건에 해당하는 데이터에서 "최신 6개 td"만 가져오기
   - 출력: td, jk_code, mm_amcap, mm_qcap
   - jk_code 길이 <= 7
   ============================================================ */

SELECT
  left(a.td,6),
  a.jk_code,
  a.mm_amcap,
  a.mm_qcap,
  (a.mm_amcap * 100 / NULLIF(a.mm_qcap,0) * 3.3058) AS 매매평당가
FROM modueum.ms_aptqindex a
JOIN (
  SELECT td
  FROM (
    SELECT DISTINCT td
    FROM modueum.ms_aptqindex
    WHERE grp_code = '00'
      AND gb = '0'
      AND jk_gb = 'a'
      AND LENGTH(CAST(jk_code AS CHAR)) <= 7
    ORDER BY td DESC
    LIMIT 6
  ) t
) last6
  ON last6.td = a.td
WHERE a.grp_code = '00'
  AND a.gb = '0'
  AND a.jk_gb = 'a'
  AND LENGTH(CAST(a.jk_code AS CHAR)) <= 7
ORDER BY
  a.jk_code,
  a.td DESC;
