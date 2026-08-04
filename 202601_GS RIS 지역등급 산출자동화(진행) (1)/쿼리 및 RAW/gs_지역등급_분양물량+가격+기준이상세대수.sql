/* ============================================================
   1) 분양물량(bp_qty): bun_dt 연도 기준 2023~2025만 (절대 변경/확장 없음)
   2) 분양가격(bp_price): q윈도우만 사용
      - q1: 202407~202506
      - q2: 202410~202509
      - q3: 202501~202512
   3) price_ref + mm/js 기준 qty합계(mq): 오직 bp_price의 price_ref만 사용
   ============================================================ */

-- =========================
-- L2
-- =========================
SELECT
  'L2' AS lvl,
  jk.jk_gb,
  jk.jk_code,
  jk.jk_nm,

  /* 분양물량: 2023~2025 (완전 고정) */
  COALESCE(q.qty_2023, 0) AS qty_2023,
  COALESCE(q.qty_2024, 0) AS qty_2024,
  COALESCE(q.qty_2025, 0) AS qty_2025,

  /* 분양가격: q윈도우 */
  p.price_q1,
  p.price_q2,
  p.price_q3,
  p.price_ref,

  /* mm/js 기준 qty 합계: price_ref(q윈도우) 기준 */
  COALESCE(mq.mm_qty_sum, 0) AS `mm기준_qty합계`,
  COALESCE(mq.js_qty_sum, 0) AS `js기준_qty합계`

FROM modueum.m_jk jk

/* -------------------------
   (A) 분양물량(2023~2025 고정)
   ------------------------- */
LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 2) AS code_prefix,
    SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN m.qty ELSE 0 END) AS qty_2023,
    SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN m.qty ELSE 0 END) AS qty_2024,
    SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN m.qty ELSE 0 END) AS qty_2025
  FROM modueum.m_apt_mast m
  WHERE LEFT(m.bun_dt,4) IN ('2023','2024','2025')
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 2)
) q
  ON q.code_prefix = jk.jk_code

/* -------------------------
   (B) 분양가격(q윈도우만)
   ------------------------- */
LEFT JOIN (
  SELECT
    code_prefix,
    price_q1, price_q2, price_q3,
    CASE
      WHEN price_q3 IS NOT NULL THEN price_q3
      WHEN price_q2 IS NOT NULL THEN price_q2 * 1.05
      WHEN price_q1 IS NOT NULL THEN price_q1 * 1.05 * 1.05
      ELSE NULL
    END AS price_ref
  FROM (
    SELECT
      LEFT(CAST(m.jk_code AS CHAR), 2) AS code_prefix,

      CASE
        WHEN SUM(CASE WHEN m.bun_dt BETWEEN '202407' AND '202506' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN m.bun_dt BETWEEN '202407' AND '202506' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN m.bun_dt BETWEEN '202407' AND '202506' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_q1,

      CASE
        WHEN SUM(CASE WHEN m.bun_dt BETWEEN '202410' AND '202509' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN m.bun_dt BETWEEN '202410' AND '202509' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN m.bun_dt BETWEEN '202410' AND '202509' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_q2,

      CASE
        WHEN SUM(CASE WHEN m.bun_dt BETWEEN '202501' AND '202512' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN m.bun_dt BETWEEN '202501' AND '202512' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN m.bun_dt BETWEEN '202501' AND '202512' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_q3

    FROM modueum.m_apt_mast m
    LEFT JOIN modueum.m_aptsub_mast s
      ON s.ap_code = m.ap_code
     AND s.bprice <> 0
    WHERE m.bun_dt BETWEEN '202407' AND '202512'
      AND m.ap_uh IN ('1','2','3','4','6','9')
    GROUP BY LEFT(CAST(m.jk_code AS CHAR), 2)
  ) t
) p
  ON p.code_prefix = jk.jk_code

/* -------------------------
   (C) mm/js 기준 qty 합계 (dt 조건 누적, ap_uh 유지)
       - 단, price_ref는 (B)에서 계산된 값만 사용
   ------------------------- */
LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 2) AS code_prefix,
    SUM(CASE WHEN sm.mm_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS mm_qty_sum,
    SUM(CASE WHEN sm.js_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS js_qty_sum
  FROM modueum.m_aptsub_mast sm
  JOIN modueum.m_apt_mast m
    ON m.ap_code = sm.ap_code
  JOIN (
    /* (B)와 동일한 price_ref(윈도우)만 산출 */
    SELECT
      code_prefix,
      CASE
        WHEN price_q3 IS NOT NULL THEN price_q3
        WHEN price_q2 IS NOT NULL THEN price_q2 * 1.05
        WHEN price_q1 IS NOT NULL THEN price_q1 * 1.05 * 1.05
        ELSE NULL
      END AS price_ref
    FROM (
      SELECT
        LEFT(CAST(m2.jk_code AS CHAR), 2) AS code_prefix,

        CASE
          WHEN SUM(CASE WHEN m2.bun_dt BETWEEN '202407' AND '202506' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN m2.bun_dt BETWEEN '202407' AND '202506' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN m2.bun_dt BETWEEN '202407' AND '202506' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_q1,

        CASE
          WHEN SUM(CASE WHEN m2.bun_dt BETWEEN '202410' AND '202509' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN m2.bun_dt BETWEEN '202410' AND '202509' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN m2.bun_dt BETWEEN '202410' AND '202509' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_q2,

        CASE
          WHEN SUM(CASE WHEN m2.bun_dt BETWEEN '202501' AND '202512' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN m2.bun_dt BETWEEN '202501' AND '202512' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN m2.bun_dt BETWEEN '202501' AND '202512' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_q3

      FROM modueum.m_apt_mast m2
      LEFT JOIN modueum.m_aptsub_mast s2
        ON s2.ap_code = m2.ap_code
       AND s2.bprice <> 0
      WHERE m2.bun_dt BETWEEN '202407' AND '202512'
        AND m2.ap_uh IN ('1','2','3','4','6','9')
      GROUP BY LEFT(CAST(m2.jk_code AS CHAR), 2)
    ) z
  ) pr
    ON pr.code_prefix = LEFT(CAST(m.jk_code AS CHAR), 2)

  WHERE sm.area <= 110
    AND pr.price_ref IS NOT NULL
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 2)
) mq
  ON mq.code_prefix = jk.jk_code

WHERE jk.jk_gb='A'
  AND LENGTH(CAST(jk.jk_code AS CHAR)) = 2


UNION ALL


-- =========================
-- L5
-- =========================
SELECT
  'L5' AS lvl,
  jk.jk_gb,
  jk.jk_code,
  jk.jk_nm,

  COALESCE(q.qty_2023, 0) AS qty_2023,
  COALESCE(q.qty_2024, 0) AS qty_2024,
  COALESCE(q.qty_2025, 0) AS qty_2025,

  p.price_q1,
  p.price_q2,
  p.price_q3,
  p.price_ref,

  COALESCE(mq.mm_qty_sum, 0) AS `mm기준_qty합계`,
  COALESCE(mq.js_qty_sum, 0) AS `js기준_qty합계`

FROM modueum.m_jk jk

LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 5) AS code_prefix,
    SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN m.qty ELSE 0 END) AS qty_2023,
    SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN m.qty ELSE 0 END) AS qty_2024,
    SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN m.qty ELSE 0 END) AS qty_2025
  FROM modueum.m_apt_mast m
  WHERE LEFT(m.bun_dt,4) IN ('2023','2024','2025')
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 5)
) q
  ON q.code_prefix = jk.jk_code

LEFT JOIN (
  SELECT
    code_prefix,
    price_q1, price_q2, price_q3,
    CASE
      WHEN price_q3 IS NOT NULL THEN price_q3
      WHEN price_q2 IS NOT NULL THEN price_q2 * 1.05
      WHEN price_q1 IS NOT NULL THEN price_q1 * 1.05 * 1.05
      ELSE NULL
    END AS price_ref
  FROM (
    SELECT
      LEFT(CAST(m.jk_code AS CHAR), 5) AS code_prefix,

      CASE
        WHEN SUM(CASE WHEN m.bun_dt BETWEEN '202407' AND '202506' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN m.bun_dt BETWEEN '202407' AND '202506' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN m.bun_dt BETWEEN '202407' AND '202506' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_q1,

      CASE
        WHEN SUM(CASE WHEN m.bun_dt BETWEEN '202410' AND '202509' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN m.bun_dt BETWEEN '202410' AND '202509' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN m.bun_dt BETWEEN '202410' AND '202509' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_q2,

      CASE
        WHEN SUM(CASE WHEN m.bun_dt BETWEEN '202501' AND '202512' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN m.bun_dt BETWEEN '202501' AND '202512' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN m.bun_dt BETWEEN '202501' AND '202512' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_q3

    FROM modueum.m_apt_mast m
    LEFT JOIN modueum.m_aptsub_mast s
      ON s.ap_code = m.ap_code
     AND s.bprice <> 0
    WHERE m.bun_dt BETWEEN '202407' AND '202512'
      AND m.ap_uh IN ('1','2','3','4','6','9')
    GROUP BY LEFT(CAST(m.jk_code AS CHAR), 5)
  ) t
) p
  ON p.code_prefix = jk.jk_code

LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 5) AS code_prefix,
    SUM(CASE WHEN sm.mm_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS mm_qty_sum,
    SUM(CASE WHEN sm.js_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS js_qty_sum
  FROM modueum.m_aptsub_mast sm
  JOIN modueum.m_apt_mast m
    ON m.ap_code = sm.ap_code
  JOIN (
    SELECT
      code_prefix,
      CASE
        WHEN price_q3 IS NOT NULL THEN price_q3
        WHEN price_q2 IS NOT NULL THEN price_q2 * 1.05
        WHEN price_q1 IS NOT NULL THEN price_q1 * 1.05 * 1.05
        ELSE NULL
      END AS price_ref
    FROM (
      SELECT
        LEFT(CAST(m2.jk_code AS CHAR), 5) AS code_prefix,

        CASE
          WHEN SUM(CASE WHEN m2.bun_dt BETWEEN '202407' AND '202506' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN m2.bun_dt BETWEEN '202407' AND '202506' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN m2.bun_dt BETWEEN '202407' AND '202506' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_q1,

        CASE
          WHEN SUM(CASE WHEN m2.bun_dt BETWEEN '202410' AND '202509' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN m2.bun_dt BETWEEN '202410' AND '202509' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN m2.bun_dt BETWEEN '202410' AND '202509' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_q2,

        CASE
          WHEN SUM(CASE WHEN m2.bun_dt BETWEEN '202501' AND '202512' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN m2.bun_dt BETWEEN '202501' AND '202512' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN m2.bun_dt BETWEEN '202501' AND '202512' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_q3

      FROM modueum.m_apt_mast m2
      LEFT JOIN modueum.m_aptsub_mast s2
        ON s2.ap_code = m2.ap_code
       AND s2.bprice <> 0
      WHERE m2.bun_dt BETWEEN '202407' AND '202512'
        AND m2.ap_uh IN ('1','2','3','4','6','9')
      GROUP BY LEFT(CAST(m2.jk_code AS CHAR), 5)
    ) z
  ) pr
    ON pr.code_prefix = LEFT(CAST(m.jk_code AS CHAR), 5)

  WHERE sm.area <= 110
    AND pr.price_ref IS NOT NULL
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 5)
) mq
  ON mq.code_prefix = jk.jk_code

WHERE jk.jk_gb='A'
  AND LENGTH(CAST(jk.jk_code AS CHAR)) = 5


UNION ALL


-- =========================
-- L7
-- =========================
SELECT
  'L7' AS lvl,
  jk.jk_gb,
  jk.jk_code,
  jk.jk_nm,

  COALESCE(q.qty_2023, 0) AS qty_2023,
  COALESCE(q.qty_2024, 0) AS qty_2024,
  COALESCE(q.qty_2025, 0) AS qty_2025,

  p.price_q1,
  p.price_q2,
  p.price_q3,
  p.price_ref,

  COALESCE(mq.mm_qty_sum, 0) AS `mm기준_qty합계`,
  COALESCE(mq.js_qty_sum, 0) AS `js기준_qty합계`

FROM modueum.m_jk jk

LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 7) AS code_prefix,
    SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN m.qty ELSE 0 END) AS qty_2023,
    SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN m.qty ELSE 0 END) AS qty_2024,
    SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN m.qty ELSE 0 END) AS qty_2025
  FROM modueum.m_apt_mast m
  WHERE LEFT(m.bun_dt,4) IN ('2023','2024','2025')
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 7)
) q
  ON q.code_prefix = jk.jk_code

LEFT JOIN (
  SELECT
    code_prefix,
    price_q1, price_q2, price_q3,
    CASE
      WHEN price_q3 IS NOT NULL THEN price_q3
      WHEN price_q2 IS NOT NULL THEN price_q2 * 1.05
      WHEN price_q1 IS NOT NULL THEN price_q1 * 1.05 * 1.05
      ELSE NULL
    END AS price_ref
  FROM (
    SELECT
      LEFT(CAST(m.jk_code AS CHAR), 7) AS code_prefix,

      CASE
        WHEN SUM(CASE WHEN m.bun_dt BETWEEN '202407' AND '202506' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN m.bun_dt BETWEEN '202407' AND '202506' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN m.bun_dt BETWEEN '202407' AND '202506' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_q1,

      CASE
        WHEN SUM(CASE WHEN m.bun_dt BETWEEN '202410' AND '202509' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN m.bun_dt BETWEEN '202410' AND '202509' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN m.bun_dt BETWEEN '202410' AND '202509' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_q2,

      CASE
        WHEN SUM(CASE WHEN m.bun_dt BETWEEN '202501' AND '202512' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN m.bun_dt BETWEEN '202501' AND '202512' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN m.bun_dt BETWEEN '202501' AND '202512' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_q3

    FROM modueum.m_apt_mast m
    LEFT JOIN modueum.m_aptsub_mast s
      ON s.ap_code = m.ap_code
     AND s.bprice <> 0
    WHERE m.bun_dt BETWEEN '202407' AND '202512'
      AND m.ap_uh IN ('1','2','3','4','6','9')
    GROUP BY LEFT(CAST(m.jk_code AS CHAR), 7)
  ) t
) p
  ON p.code_prefix = jk.jk_code

LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 7) AS code_prefix,
    SUM(CASE WHEN sm.mm_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS mm_qty_sum,
    SUM(CASE WHEN sm.js_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS js_qty_sum
  FROM modueum.m_aptsub_mast sm
  JOIN modueum.m_apt_mast m
    ON m.ap_code = sm.ap_code
  JOIN (
    SELECT
      code_prefix,
      CASE
        WHEN price_q3 IS NOT NULL THEN price_q3
        WHEN price_q2 IS NOT NULL THEN price_q2 * 1.05
        WHEN price_q1 IS NOT NULL THEN price_q1 * 1.05 * 1.05
        ELSE NULL
      END AS price_ref
    FROM (
      SELECT
        LEFT(CAST(m2.jk_code AS CHAR), 7) AS code_prefix,

        CASE
          WHEN SUM(CASE WHEN m2.bun_dt BETWEEN '202407' AND '202506' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN m2.bun_dt BETWEEN '202407' AND '202506' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN m2.bun_dt BETWEEN '202407' AND '202506' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_q1,

        CASE
          WHEN SUM(CASE WHEN m2.bun_dt BETWEEN '202410' AND '202509' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN m2.bun_dt BETWEEN '202410' AND '202509' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN m2.bun_dt BETWEEN '202410' AND '202509' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_q2,

        CASE
          WHEN SUM(CASE WHEN m2.bun_dt BETWEEN '202501' AND '202512' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN m2.bun_dt BETWEEN '202501' AND '202512' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN m2.bun_dt BETWEEN '202501' AND '202512' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_q3

      FROM modueum.m_apt_mast m2
      LEFT JOIN modueum.m_aptsub_mast s2
        ON s2.ap_code = m2.ap_code
       AND s2.bprice <> 0
      WHERE m2.bun_dt BETWEEN '202407' AND '202512'
        AND m2.ap_uh IN ('1','2','3','4','6','9')
      GROUP BY LEFT(CAST(m2.jk_code AS CHAR), 7)
    ) z
  ) pr
    ON pr.code_prefix = LEFT(CAST(m.jk_code AS CHAR), 7)

  WHERE sm.area <= 110
    AND pr.price_ref IS NOT NULL
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 7)
) mq
  ON mq.code_prefix = jk.jk_code

WHERE jk.jk_gb='A'
  AND LENGTH(CAST(jk.jk_code AS CHAR)) = 7
;


#현재는 price_q1/q2/q3가 모두 채워지지 않았는데, 코딩할때는 모두 채워지고 마지막 값이 ref가 나오는 형태로 구축해야함



/* ============================================================
   (1) 분양물량/분양가격/price_ref : bun_dt(2023~2025) + ap_uh 조건으로 "확정"
   (2) mm/js 기준 qty 합계       : bun_dt 조건은 제거(누적), ap_uh는 유지
       - sm.area <= 110
       - sm.mm_price >= (price_ref * 34 * 0.55)
       - sm.js_price >= (price_ref * 34 * 0.55)

   ※ 분양가격/price_ref는 "평당" ( * 3.3058 적용)
   ============================================================ 

-- =========================
-- L2
-- =========================
SELECT
  'L2' AS lvl,
  jk.jk_gb,
  jk.jk_code,
  jk.jk_nm,

  COALESCE(bp.qty_2023, 0) AS qty_2023,
  COALESCE(bp.qty_2024, 0) AS qty_2024,
  COALESCE(bp.qty_2025, 0) AS qty_2025,

  bp.price_2023,
  bp.price_2024,
  bp.price_2025,
  bp.price_ref,

  COALESCE(mq.mm_qty_sum, 0) AS `mm기준_qty합계`,
  COALESCE(mq.js_qty_sum, 0) AS `js기준_qty합계`

FROM modueum.m_jk jk

LEFT JOIN (
  /* bun_dt(2023~2025) + ap_uh 조건으로 분양물량/분양가격/price_ref 확정 */
 /* SELECT
    code_prefix,
    qty_2023, qty_2024, qty_2025,
    price_2023, price_2024, price_2025,
    CASE
      WHEN price_2025 IS NOT NULL THEN price_2025
      WHEN price_2024 IS NOT NULL THEN price_2024 * 1.05
      WHEN price_2023 IS NOT NULL THEN price_2023 * 1.05 * 1.05
      ELSE NULL
    END AS price_ref
  FROM (
    SELECT
      LEFT(CAST(m.jk_code AS CHAR), 2) AS code_prefix,

      SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN m.qty ELSE 0 END) AS qty_2023,
      SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN m.qty ELSE 0 END) AS qty_2024,
      SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN m.qty ELSE 0 END) AS qty_2025,

      CASE
        WHEN SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_2023,

      CASE
        WHEN SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_2024,

      CASE
        WHEN SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_2025

    FROM modueum.m_apt_mast m
    LEFT JOIN modueum.m_aptsub_mast s
      ON s.ap_code = m.ap_code
     AND s.bprice <> 0
    WHERE LEFT(m.bun_dt,4) IN ('2023','2024','2025')
      AND m.ap_uh IN ('1','2','3','4','6','9')
    GROUP BY LEFT(CAST(m.jk_code AS CHAR), 2)
  ) t
) bp
  ON bp.code_prefix = jk.jk_code

LEFT JOIN (
  /* dt 조건 제거(누적), ap_uh는 유지한 mm/js qty 합계 
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 2) AS code_prefix,
    SUM(CASE WHEN sm.mm_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS mm_qty_sum,
    SUM(CASE WHEN sm.js_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS js_qty_sum
  FROM modueum.m_aptsub_mast sm
  JOIN modueum.m_apt_mast m
    ON m.ap_code = sm.ap_code
  JOIN (
    /* prefix별 price_ref 확정(=분양가격 기반) */
    /*SELECT
      code_prefix,
      CASE
        WHEN price_2025 IS NOT NULL THEN price_2025
        WHEN price_2024 IS NOT NULL THEN price_2024 * 1.05
        WHEN price_2023 IS NOT NULL THEN price_2023 * 1.05 * 1.05
        ELSE NULL
      END AS price_ref
    FROM (
      SELECT
        LEFT(CAST(m2.jk_code AS CHAR), 2) AS code_prefix,
        CASE
          WHEN SUM(CASE WHEN LEFT(m2.bun_dt,4)='2023' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN LEFT(m2.bun_dt,4)='2023' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN LEFT(m2.bun_dt,4)='2023' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_2023,
        CASE
          WHEN SUM(CASE WHEN LEFT(m2.bun_dt,4)='2024' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN LEFT(m2.bun_dt,4)='2024' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN LEFT(m2.bun_dt,4)='2024' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_2024,
        CASE
          WHEN SUM(CASE WHEN LEFT(m2.bun_dt,4)='2025' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN LEFT(m2.bun_dt,4)='2025' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN LEFT(m2.bun_dt,4)='2025' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_2025
      FROM modueum.m_apt_mast m2
      LEFT JOIN modueum.m_aptsub_mast s2
        ON s2.ap_code = m2.ap_code
       AND s2.bprice <> 0
      WHERE LEFT(m2.bun_dt,4) IN ('2023','2024','2025')
        AND m2.ap_uh IN ('1','2','3','4','6','9')
      GROUP BY LEFT(CAST(m2.jk_code AS CHAR), 2)
    ) z
  ) pr
    ON pr.code_prefix = LEFT(CAST(m.jk_code AS CHAR), 2)
  WHERE sm.area <= 110
    AND pr.price_ref IS NOT NULL
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 2)
) mq
  ON mq.code_prefix = jk.jk_code

WHERE jk.jk_gb='A'
  AND LENGTH(CAST(jk.jk_code AS CHAR)) = 2


UNION ALL


-- =========================
-- L5
-- =========================
SELECT
  'L5' AS lvl,
  jk.jk_gb,
  jk.jk_code,
  jk.jk_nm,

  COALESCE(bp.qty_2023, 0) AS qty_2023,
  COALESCE(bp.qty_2024, 0) AS qty_2024,
  COALESCE(bp.qty_2025, 0) AS qty_2025,

  bp.price_2023,
  bp.price_2024,
  bp.price_2025,
  bp.price_ref,

  COALESCE(mq.mm_qty_sum, 0) AS `mm기준_qty합계`,
  COALESCE(mq.js_qty_sum, 0) AS `js기준_qty합계`

FROM modueum.m_jk jk

LEFT JOIN (
  SELECT
    code_prefix,
    qty_2023, qty_2024, qty_2025,
    price_2023, price_2024, price_2025,
    CASE
      WHEN price_2025 IS NOT NULL THEN price_2025
      WHEN price_2024 IS NOT NULL THEN price_2024 * 1.05
      WHEN price_2023 IS NOT NULL THEN price_2023 * 1.05 * 1.05
      ELSE NULL
    END AS price_ref
  FROM (
    SELECT
      LEFT(CAST(m.jk_code AS CHAR), 5) AS code_prefix,

      SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN m.qty ELSE 0 END) AS qty_2023,
      SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN m.qty ELSE 0 END) AS qty_2024,
      SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN m.qty ELSE 0 END) AS qty_2025,

      CASE
        WHEN SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_2023,

      CASE
        WHEN SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_2024,

      CASE
        WHEN SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_2025

    FROM modueum.m_apt_mast m
    LEFT JOIN modueum.m_aptsub_mast s
      ON s.ap_code = m.ap_code
     AND s.bprice <> 0
    WHERE LEFT(m.bun_dt,4) IN ('2023','2024','2025')
      AND m.ap_uh IN ('1','2','3','4','6','9')
    GROUP BY LEFT(CAST(m.jk_code AS CHAR), 5)
  ) t
) bp
  ON bp.code_prefix = jk.jk_code

LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 5) AS code_prefix,
    SUM(CASE WHEN sm.mm_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS mm_qty_sum,
    SUM(CASE WHEN sm.js_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS js_qty_sum
  FROM modueum.m_aptsub_mast sm
  JOIN modueum.m_apt_mast m
    ON m.ap_code = sm.ap_code
  JOIN (
    SELECT
      code_prefix,
      CASE
        WHEN price_2025 IS NOT NULL THEN price_2025
        WHEN price_2024 IS NOT NULL THEN price_2024 * 1.05
        WHEN price_2023 IS NOT NULL THEN price_2023 * 1.05 * 1.05
        ELSE NULL
      END AS price_ref
    FROM (
      SELECT
        LEFT(CAST(m2.jk_code AS CHAR), 5) AS code_prefix,
        CASE
          WHEN SUM(CASE WHEN LEFT(m2.bun_dt,4)='2023' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN LEFT(m2.bun_dt,4)='2023' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN LEFT(m2.bun_dt,4)='2023' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_2023,
        CASE
          WHEN SUM(CASE WHEN LEFT(m2.bun_dt,4)='2024' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN LEFT(m2.bun_dt,4)='2024' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN LEFT(m2.bun_dt,4)='2024' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_2024,
        CASE
          WHEN SUM(CASE WHEN LEFT(m2.bun_dt,4)='2025' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN LEFT(m2.bun_dt,4)='2025' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN LEFT(m2.bun_dt,4)='2025' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_2025
      FROM modueum.m_apt_mast m2
      LEFT JOIN modueum.m_aptsub_mast s2
        ON s2.ap_code = m2.ap_code
       AND s2.bprice <> 0
      WHERE LEFT(m2.bun_dt,4) IN ('2023','2024','2025')
        AND m2.ap_uh IN ('1','2','3','4','6','9')
      GROUP BY LEFT(CAST(m2.jk_code AS CHAR), 5)
    ) z
  ) pr
    ON pr.code_prefix = LEFT(CAST(m.jk_code AS CHAR), 5)
  WHERE sm.area <= 110
    AND pr.price_ref IS NOT NULL
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 5)
) mq
  ON mq.code_prefix = jk.jk_code

WHERE jk.jk_gb='A'
  AND LENGTH(CAST(jk.jk_code AS CHAR)) = 5


UNION ALL


-- =========================
-- L7
-- =========================
SELECT
  'L7' AS lvl,
  jk.jk_gb,
  jk.jk_code,
  jk.jk_nm,

  COALESCE(bp.qty_2023, 0) AS qty_2023,
  COALESCE(bp.qty_2024, 0) AS qty_2024,
  COALESCE(bp.qty_2025, 0) AS qty_2025,

  bp.price_2023,
  bp.price_2024,
  bp.price_2025,
  bp.price_ref,

  COALESCE(mq.mm_qty_sum, 0) AS `mm기준_qty합계`,
  COALESCE(mq.js_qty_sum, 0) AS `js기준_qty합계`

FROM modueum.m_jk jk

LEFT JOIN (
  SELECT
    code_prefix,
    qty_2023, qty_2024, qty_2025,
    price_2023, price_2024, price_2025,
    CASE
      WHEN price_2025 IS NOT NULL THEN price_2025
      WHEN price_2024 IS NOT NULL THEN price_2024 * 1.05
      WHEN price_2023 IS NOT NULL THEN price_2023 * 1.05 * 1.05
      ELSE NULL
    END AS price_ref
  FROM (
    SELECT
      LEFT(CAST(m.jk_code AS CHAR), 7) AS code_prefix,

      SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN m.qty ELSE 0 END) AS qty_2023,
      SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN m.qty ELSE 0 END) AS qty_2024,
      SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN m.qty ELSE 0 END) AS qty_2025,

      CASE
        WHEN SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN LEFT(m.bun_dt,4)='2023' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_2023,

      CASE
        WHEN SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN LEFT(m.bun_dt,4)='2024' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_2024,

      CASE
        WHEN SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN s.barea*s.bqty ELSE 0 END) > 0
        THEN ( SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN s.bprice*s.bqty ELSE 0 END)
             / SUM(CASE WHEN LEFT(m.bun_dt,4)='2025' THEN s.barea*s.bqty ELSE 0 END) ) * 3.3058
      END AS price_2025

    FROM modueum.m_apt_mast m
    LEFT JOIN modueum.m_aptsub_mast s
      ON s.ap_code = m.ap_code
     AND s.bprice <> 0
    WHERE LEFT(m.bun_dt,4) IN ('2023','2024','2025')
      AND m.ap_uh IN ('1','2','3','4','6','9')
    GROUP BY LEFT(CAST(m.jk_code AS CHAR), 7)
  ) t
) bp
  ON bp.code_prefix = jk.jk_code

LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 7) AS code_prefix,
    SUM(CASE WHEN sm.mm_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS mm_qty_sum,
    SUM(CASE WHEN sm.js_price >= (pr.price_ref * 34 * 0.55) THEN sm.qty ELSE 0 END) AS js_qty_sum
  FROM modueum.m_aptsub_mast sm
  JOIN modueum.m_apt_mast m
    ON m.ap_code = sm.ap_code
  JOIN (
    SELECT
      code_prefix,
      CASE
        WHEN price_2025 IS NOT NULL THEN price_2025
        WHEN price_2024 IS NOT NULL THEN price_2024 * 1.05
        WHEN price_2023 IS NOT NULL THEN price_2023 * 1.05 * 1.05
        ELSE NULL
      END AS price_ref
    FROM (
      SELECT
        LEFT(CAST(m2.jk_code AS CHAR), 7) AS code_prefix,
        CASE
          WHEN SUM(CASE WHEN LEFT(m2.bun_dt,4)='2023' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN LEFT(m2.bun_dt,4)='2023' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN LEFT(m2.bun_dt,4)='2023' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_2023,
        CASE
          WHEN SUM(CASE WHEN LEFT(m2.bun_dt,4)='2024' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN LEFT(m2.bun_dt,4)='2024' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN LEFT(m2.bun_dt,4)='2024' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_2024,
        CASE
          WHEN SUM(CASE WHEN LEFT(m2.bun_dt,4)='2025' THEN s2.barea*s2.bqty ELSE 0 END) > 0
          THEN ( SUM(CASE WHEN LEFT(m2.bun_dt,4)='2025' THEN s2.bprice*s2.bqty ELSE 0 END)
               / SUM(CASE WHEN LEFT(m2.bun_dt,4)='2025' THEN s2.barea*s2.bqty ELSE 0 END) ) * 3.3058
        END AS price_2025
      FROM modueum.m_apt_mast m2
      LEFT JOIN modueum.m_aptsub_mast s2
        ON s2.ap_code = m2.ap_code
       AND s2.bprice <> 0
      WHERE LEFT(m2.bun_dt,4) IN ('2023','2024','2025')
        AND m2.ap_uh IN ('1','2','3','4','6','9')
      GROUP BY LEFT(CAST(m2.jk_code AS CHAR), 7)
    ) z
  ) pr
    ON pr.code_prefix = LEFT(CAST(m.jk_code AS CHAR), 7)
  WHERE sm.area <= 110
    AND pr.price_ref IS NOT NULL
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 7)
) mq
  ON mq.code_prefix = jk.jk_code

WHERE jk.jk_gb='A'
  AND LENGTH(CAST(jk.jk_code AS CHAR)) = 7
;

*/







/* =========================
   분양가격만 (2023/2024/2025) + price_ref
   ========================= 

-- L2
SELECT
  'L2' AS lvl,
  jk.JK_GB,
  jk.JK_CODE,
  jk.JK_NM,

  CASE WHEN p.den_2023 > 0 THEN p.num_2023 / p.den_2023 END AS price_2023,
  CASE WHEN p.den_2024 > 0 THEN p.num_2024 / p.den_2024 END AS price_2024,
  CASE WHEN p.den_2025 > 0 THEN p.num_2025 / p.den_2025 END AS price_2025,

  CASE
    WHEN (p.den_2025 > 0) THEN (p.num_2025 / p.den_2025)
    WHEN (p.den_2024 > 0) THEN (p.num_2024 / p.den_2024) * 1.05
    WHEN (p.den_2023 > 0) THEN (p.num_2023 / p.den_2023) * 1.05 * 1.05
    ELSE NULL
  END AS price_ref

FROM modueum.M_JK jk
LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 2) AS code_prefix,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2023' THEN s.bprice * s.bqty ELSE 0 END) AS num_2023,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2023' THEN s.barea  * s.bqty ELSE 0 END) AS den_2023,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2024' THEN s.bprice * s.bqty ELSE 0 END) AS num_2024,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2024' THEN s.barea  * s.bqty ELSE 0 END) AS den_2024,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2025' THEN s.bprice * s.bqty ELSE 0 END) AS num_2025,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2025' THEN s.barea  * s.bqty ELSE 0 END) AS den_2025
  FROM modueum.m_apt_mast m
  JOIN modueum.M_APTSUB_MAST s
    ON s.ap_code = m.ap_code
   AND s.bprice <> 0
  WHERE LEFT(m.bun_dt, 4) IN ('2023','2024','2025')
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 2)
) p
  ON p.code_prefix = jk.JK_CODE
WHERE jk.jk_gb = 'A'
  AND LENGTH(CAST(jk.JK_CODE AS CHAR)) = 2

UNION ALL

-- L5
SELECT
  'L5' AS lvl,
  jk.JK_GB,
  jk.JK_CODE,
  jk.JK_NM,

  CASE WHEN p.den_2023 > 0 THEN p.num_2023 / p.den_2023 END AS price_2023,
  CASE WHEN p.den_2024 > 0 THEN p.num_2024 / p.den_2024 END AS price_2024,
  CASE WHEN p.den_2025 > 0 THEN p.num_2025 / p.den_2025 END AS price_2025,

  CASE
    WHEN (p.den_2025 > 0) THEN (p.num_2025 / p.den_2025)
    WHEN (p.den_2024 > 0) THEN (p.num_2024 / p.den_2024) * 1.05
    WHEN (p.den_2023 > 0) THEN (p.num_2023 / p.den_2023) * 1.05 * 1.05
    ELSE NULL
  END AS price_ref

FROM modueum.M_JK jk
LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 5) AS code_prefix,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2023' THEN s.bprice * s.bqty ELSE 0 END) AS num_2023,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2023' THEN s.barea  * s.bqty ELSE 0 END) AS den_2023,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2024' THEN s.bprice * s.bqty ELSE 0 END) AS num_2024,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2024' THEN s.barea  * s.bqty ELSE 0 END) AS den_2024,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2025' THEN s.bprice * s.bqty ELSE 0 END) AS num_2025,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2025' THEN s.barea  * s.bqty ELSE 0 END) AS den_2025
  FROM modueum.m_apt_mast m
  JOIN modueum.M_APTSUB_MAST s
    ON s.ap_code = m.ap_code
   AND s.bprice <> 0
  WHERE LEFT(m.bun_dt, 4) IN ('2023','2024','2025')
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 5)
) p
  ON p.code_prefix = jk.JK_CODE
WHERE jk.jk_gb = 'A'
  AND LENGTH(CAST(jk.JK_CODE AS CHAR)) = 5

UNION ALL

-- L7
SELECT
  'L7' AS lvl,
  jk.JK_GB,
  jk.JK_CODE,
  jk.JK_NM,

  CASE WHEN p.den_2023 > 0 THEN p.num_2023 / p.den_2023 END AS price_2023,
  CASE WHEN p.den_2024 > 0 THEN p.num_2024 / p.den_2024 END AS price_2024,
  CASE WHEN p.den_2025 > 0 THEN p.num_2025 / p.den_2025 END AS price_2025,

  CASE
    WHEN (p.den_2025 > 0) THEN (p.num_2025 / p.den_2025)
    WHEN (p.den_2024 > 0) THEN (p.num_2024 / p.den_2024) * 1.05
    WHEN (p.den_2023 > 0) THEN (p.num_2023 / p.den_2023) * 1.05 * 1.05
    ELSE NULL
  END AS price_ref

FROM modueum.M_JK jk
LEFT JOIN (
  SELECT
    LEFT(CAST(m.jk_code AS CHAR), 7) AS code_prefix,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2023' THEN s.bprice * s.bqty ELSE 0 END) AS num_2023,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2023' THEN s.barea  * s.bqty ELSE 0 END) AS den_2023,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2024' THEN s.bprice * s.bqty ELSE 0 END) AS num_2024,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2024' THEN s.barea  * s.bqty ELSE 0 END) AS den_2024,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2025' THEN s.bprice * s.bqty ELSE 0 END) AS num_2025,
    SUM(CASE WHEN LEFT(m.bun_dt, 4)='2025' THEN s.barea  * s.bqty ELSE 0 END) AS den_2025
  FROM modueum.m_apt_mast m
  JOIN modueum.M_APTSUB_MAST s
    ON s.ap_code = m.ap_code
   AND s.bprice <> 0
  WHERE LEFT(m.bun_dt, 4) IN ('2023','2024','2025')
    AND m.ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(m.jk_code AS CHAR), 7)
) p
  ON p.code_prefix = jk.JK_CODE
WHERE jk.jk_gb = 'A'
  AND LENGTH(CAST(jk.JK_CODE AS CHAR)) = 7
;
*/


/*
-- L2: M_JK 코드 길이 2만
SELECT
  'L2' AS lvl,
  jk.JK_GB,
  jk.JK_CODE,
  jk.JK_NM,
  COALESCE(a.qty_2023, 0) AS qty_2023,
  COALESCE(a.qty_2024, 0) AS qty_2024,
  COALESCE(a.qty_2025, 0) AS qty_2025
FROM modueum.M_JK jk
LEFT JOIN (
  SELECT
    LEFT(CAST(jk_code AS CHAR), 2) AS code_prefix,
    SUM(CASE WHEN LEFT(bun_dt, 4) = '2023' THEN qty ELSE 0 END) AS qty_2023,
    SUM(CASE WHEN LEFT(bun_dt, 4) = '2024' THEN qty ELSE 0 END) AS qty_2024,
    SUM(CASE WHEN LEFT(bun_dt, 4) = '2025' THEN qty ELSE 0 END) AS qty_2025
  FROM modueum.m_apt_mast
  WHERE LEFT(bun_dt, 4) IN ('2023','2024','2025')
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
  COALESCE(a.qty_2023, 0) AS qty_2023,
  COALESCE(a.qty_2024, 0) AS qty_2024,
  COALESCE(a.qty_2025, 0) AS qty_2025
FROM modueum.M_JK jk
LEFT JOIN (
  SELECT
    LEFT(CAST(jk_code AS CHAR), 5) AS code_prefix,
    SUM(CASE WHEN LEFT(bun_dt, 4) = '2023' THEN qty ELSE 0 END) AS qty_2023,
    SUM(CASE WHEN LEFT(bun_dt, 4) = '2024' THEN qty ELSE 0 END) AS qty_2024,
    SUM(CASE WHEN LEFT(bun_dt, 4) = '2025' THEN qty ELSE 0 END) AS qty_2025
  FROM modueum.m_apt_mast
  WHERE LEFT(bun_dt, 4) IN ('2023','2024','2025')
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
  COALESCE(a.qty_2023, 0) AS qty_2023,
  COALESCE(a.qty_2024, 0) AS qty_2024,
  COALESCE(a.qty_2025, 0) AS qty_2025
FROM modueum.M_JK jk
LEFT JOIN (
  SELECT
    LEFT(CAST(jk_code AS CHAR), 7) AS code_prefix,
    SUM(CASE WHEN LEFT(bun_dt, 4) = '2023' THEN qty ELSE 0 END) AS qty_2023,
    SUM(CASE WHEN LEFT(bun_dt, 4) = '2024' THEN qty ELSE 0 END) AS qty_2024,
    SUM(CASE WHEN LEFT(bun_dt, 4) = '2025' THEN qty ELSE 0 END) AS qty_2025
  FROM modueum.m_apt_mast
  WHERE LEFT(bun_dt, 4) IN ('2023','2024','2025')
    AND ap_uh IN ('1','2','3','4','6','9')
  GROUP BY LEFT(CAST(jk_code AS CHAR), 7)
) a
  ON a.code_prefix = jk.JK_CODE
WHERE jk.jk_gb = 'A'
  AND LENGTH(CAST(jk.JK_CODE AS CHAR)) = 7
;

*/

