
SELECT *
FROM modueum.R114_KHI_미분양관리지역
WHERE 기준년월 = (
    SELECT MAX(기준년월)
    FROM modueum.R114_KHI_미분양관리지역
);