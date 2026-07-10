
# 미분양
SELECT
    jk_code,
    left(td,4) AS td,
    tot
FROM modueum.d_mibun
WHERE RIGHT(td,2) ='12'
GROUP BY jk_code, td
ORDER BY jk_code, td;
