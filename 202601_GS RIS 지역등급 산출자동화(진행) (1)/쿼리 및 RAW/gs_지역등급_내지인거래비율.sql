SELECT
  LEFT(CAST(jk_code AS CHAR), 7) AS jk_code,

  /* m100 (전체) */
  SUM(CASE WHEN uh = 'm100' AND CAST(LEFT(td,4) AS UNSIGNED) = YEAR(CURDATE())-1 THEN qty ELSE 0 END) AS 거래합계_y1,
  SUM(CASE WHEN uh = 'm100' AND CAST(LEFT(td,4) AS UNSIGNED) = YEAR(CURDATE())-2 THEN qty ELSE 0 END) AS 거래합계_y2,
  SUM(CASE WHEN uh = 'm100' AND CAST(LEFT(td,4) AS UNSIGNED) = YEAR(CURDATE())-3 THEN qty ELSE 0 END) AS 거래합계_y3,

  /* m110 (내지인: 해당 시군구) */
  SUM(CASE WHEN uh = 'm110' AND CAST(LEFT(td,4) AS UNSIGNED) = YEAR(CURDATE())-1 THEN qty ELSE 0 END) AS 내지인거래_y1,
  SUM(CASE WHEN uh = 'm110' AND CAST(LEFT(td,4) AS UNSIGNED) = YEAR(CURDATE())-2 THEN qty ELSE 0 END) AS 내지인거래_y2,
  SUM(CASE WHEN uh = 'm110' AND CAST(LEFT(td,4) AS UNSIGNED) = YEAR(CURDATE())-3 THEN qty ELSE 0 END) AS 내지인거래_y3

FROM modueum.d_aptdeal_maemae_m
WHERE jk_gb = 'b'
  AND uh IN ('m100','m110')
  AND CAST(LEFT(td,4) AS UNSIGNED) BETWEEN YEAR(CURDATE())-4 AND YEAR(CURDATE())-1

GROUP BY
  jk_gb,
  LEFT(CAST(jk_code AS CHAR), 7)

ORDER BY
  jk_code;