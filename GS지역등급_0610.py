# -*- coding: utf-8 -*-
"""
Created on Wed Jan 21 17:26:11 2026

@author: USER
"""

# 3 에서 '군위군' 해결

import pandas as pd
import numpy as np
import pymysql
import os
import math
pd.options.display.float_format = '{:.2f}'.format

os.chdir(r"C:\Users\USER\Desktop\jw\GS지역등급산출등\260506_산출시작")

'''데이터 불러오기1'''
gagu = pd.read_excel("거처의_종류별_거처__가구__가구원__시군구.xlsx",header=[0,1,2], dtype = str)
ingu = pd.read_excel("성__연령_및_세대구성별_인구__시군구.xlsx",header=[0,1], dtype = str)
soyu = pd.read_excel('거주지역_주택_소유물건수별_주택소유자수.xlsx', header = [0,1], dtype = str)
soduk = pd.read_excel('26.05 기준 연소득.xlsx', dtype = str)
jutaek= pd.read_excel('주택의_종류별_주택__읍면동_연도_끝자리_0__5___시군구_그_외_연도.xlsx', header = [0,1] ,dtype = str)
j_code = pd.read_excel("지역코드매핑.xlsx", dtype = str, names = ['지역코드1','jk_code'])

# 소득파일 전분기거 가져와서 지역코드 가져오고 형태 맞춰줌 - 다음 분기 작업때 바뀔수있음
soduk_past = pd.read_excel('GS지역등급 연소득 최신자료_2026년01월 기준.xlsx', dtype = str)
soduk = pd.concat([soduk_past.iloc[:,:5], soduk], axis = 1)
soduk.drop(columns = ['시도','시군구'], inplace = True)

# r114_gs_ds_grade_income 테이블 업로드용
soduk_r114_gs_ds_grade_income = soduk.copy()

# 소득 파일에 지역코드 붙여줌
jiyuk = pd.read_excel(r'C:\Users\USER\Downloads\지역코드정리.xlsx', dtype = str)


# gagu 군위군 변경
def fix_gunwi_to_daegu(gagu: pd.DataFrame) -> pd.DataFrame:
    # 1) key 컬럼 찾기 (멀티인덱스)
    if isinstance(gagu.columns, pd.MultiIndex):
        key_candidates = [c for c in gagu.columns if any('행정구역별(시군구)' in str(x) for x in c)]
        if not key_candidates:
            raise ValueError("멀티인덱스 컬럼에서 '행정구역별(시군구)'를 찾지 못했어요.")
        key_col = key_candidates[0]
    else:
        key_col = '행정구역별(시군구)'

    s = gagu[key_col].astype(str)

    # 2) 상위 시도(광역/도) 행 판별: "22 대구광역시", "37 경상북도" 같은 형태
    is_sido_row = s.str.match(r'^\s*\d{2}\s+.+')

    # sido 이름만 추출해서 forward-fill
    sido = pd.Series(np.nan, index=gagu.index, dtype=object)
    sido.loc[is_sido_row] = s.loc[is_sido_row].str.replace(r'^\s*\d{2}\s+', '', regex=True)
    gagu = gagu.copy()
    gagu[('시도', '', '')] = sido.ffill()  # 멀티인덱스 유지용으로 3레벨 튜플로 새 컬럼 추가

    # 3) 군위군(대구/경북) 행 찾기
    is_gunwi = s.str.contains('군위군', na=False)
    mask_daegu_gunwi = is_gunwi & (gagu[('시도', '', '')].astype(str) == '대구광역시')
    mask_gb_gunwi    = is_gunwi & (gagu[('시도', '', '')].astype(str) == '경상북도')

    value_cols = [c for c in gagu.columns if c not in [key_col, ('시도', '', '')]]

    # 숫자 변환 (X -> NaN 포함)
    gagu[value_cols] = (
        gagu[value_cols]
        .replace('X', np.nan)
        .apply(pd.to_numeric, errors='coerce')
    )

    # 4) 둘 다 존재하면: "대구 군위군을 기준"으로 "경북 군위군으로 NaN만 보충" 후 경북 군위군 삭제
    if mask_daegu_gunwi.any() and mask_gb_gunwi.any():
        idx_d = gagu.index[mask_daegu_gunwi][0]
        idx_g = gagu.index[mask_gb_gunwi][0]

        gagu.loc[idx_d, value_cols] = gagu.loc[idx_d, value_cols].combine_first(gagu.loc[idx_g, value_cols])
        gagu = gagu.drop(index=idx_g)

    # (옵션) 경북 군위군만 있고 대구 군위군이 없으면: 경북 군위군을 대구로 “이동”
    elif (not mask_daegu_gunwi.any()) and mask_gb_gunwi.any():
        idx_g = gagu.index[mask_gb_gunwi][0]
        gagu.loc[idx_g, ('시도', '', '')] = '대구광역시'

    return gagu.reset_index(drop=True)


gagu = fix_gunwi_to_daegu(gagu)

# 2.ingu 군위군 변경
def _find_col(df, contains: str):
    if isinstance(df.columns, pd.MultiIndex):
        cols = [c for c in df.columns if any(contains in str(x) for x in c)]
        if not cols:
            raise ValueError(f"멀티인덱스 컬럼에서 '{contains}' 포함 컬럼을 찾지 못했어요.")
        return cols[0]
    else:
        cols = [c for c in df.columns if contains in str(c)]
        if not cols:
            raise ValueError(f"컬럼에서 '{contains}' 포함 컬럼을 찾지 못했어요.")
        return cols[0]

def _make_mi_col(df, first_level_name: str):
    """df.columns가 MultiIndex면 nlevels에 맞는 튜플 컬럼키 생성, 아니면 문자열 반환"""
    if isinstance(df.columns, pd.MultiIndex):
        n = df.columns.nlevels
        return tuple([first_level_name] + [''] * (n - 1))
    return first_level_name

def fix_ingu_gunwi_to_daegu(ingu: pd.DataFrame) -> pd.DataFrame:
    ingu = ingu.copy()

    key_col = _find_col(ingu, '행정구역별(시군구)')
    sex_col = _find_col(ingu, '성별')
    age_col = _find_col(ingu, '연령별')

    s = ingu[key_col].astype(str)

    # 시도(광역/도) 행: "22 대구광역시", "37 경상북도" 같은 형태
    is_sido_row = s.str.match(r'^\s*\d{2}\s+.+')

    sido = pd.Series(np.nan, index=ingu.index, dtype=object)
    sido.loc[is_sido_row] = s.loc[is_sido_row].str.replace(r'^\s*\d{2}\s+', '', regex=True)

    sido_col = _make_mi_col(ingu, '시도')   # ✅ 여기서 레벨 수 자동 맞춤
    ingu[sido_col] = sido.ffill()

    is_gunwi = s.str.contains('군위군', na=False)
    mask_daegu = is_gunwi & (ingu[sido_col].astype(str) == '대구광역시')
    mask_gb    = is_gunwi & (ingu[sido_col].astype(str) == '경상북도')

    exclude = {key_col, sex_col, age_col, sido_col}
    value_cols = [c for c in ingu.columns if c not in exclude]

    # 숫자화 (빈칸/문자 -> NaN)
    ingu[value_cols] = (
        ingu[value_cols]
        .replace('X', np.nan)
        .apply(pd.to_numeric, errors='coerce')
    )

    gb_rows = ingu.loc[mask_gb, [sex_col, age_col] + value_cols].copy()

    for _, r in gb_rows.iterrows():
        sex = r[sex_col]
        age = r[age_col]

        tgt_mask = mask_daegu & (ingu[sex_col] == sex) & (ingu[age_col] == age)

        if tgt_mask.any():
            idx_t = ingu.index[tgt_mask][0]
            ingu.loc[idx_t, value_cols] = ingu.loc[idx_t, value_cols].combine_first(r[value_cols])
        else:
            # 대구 군위군에 해당 (성별,연령) 조합이 없으면 새 행 추가
            base = ingu.loc[mask_daegu, [key_col, sex_col, age_col, sido_col] + value_cols].head(1).copy()

            if base.empty:
                base = pd.DataFrame([{key_col: '　　　22520 군위군', sex_col: sex, age_col: age, sido_col: '대구광역시'}])
                for c in value_cols:
                    base[c] = np.nan

            base.iloc[0, base.columns.get_loc(sex_col)] = sex
            base.iloc[0, base.columns.get_loc(age_col)] = age
            base.iloc[0, base.columns.get_loc(sido_col)] = '대구광역시'
            for c in value_cols:
                base.iloc[0, base.columns.get_loc(c)] = r[c]

            ingu = pd.concat([ingu, base], ignore_index=True)

    # 경북 군위군 삭제
    ingu = ingu.loc[~mask_gb].reset_index(drop=True)
    return ingu

# 사용
ingu = fix_ingu_gunwi_to_daegu(ingu)

# 3. soyu 군위군 변경
def _find_col(df, contains: str):
    if isinstance(df.columns, pd.MultiIndex):
        cols = [c for c in df.columns if any(contains in str(x) for x in c)]
        if not cols:
            raise ValueError(f"멀티인덱스 컬럼에서 '{contains}' 포함 컬럼을 찾지 못했어요.")
        return cols[0]
    else:
        cols = [c for c in df.columns if contains in str(c)]
        if not cols:
            raise ValueError(f"컬럼에서 '{contains}' 포함 컬럼을 찾지 못했어요.")
        return cols[0]

def move_gunwi_soyu_to_daegu(soyu: pd.DataFrame) -> pd.DataFrame:
    soyu = soyu.copy()

    col_sido = _find_col(soyu, '거주지역별(1)')   # "SGG 거주지역별(1)"
    col_sgg  = _find_col(soyu, '거주지역별(2)')   # "SGG 거주지역별(2)"

    s_sido = soyu[col_sido].astype(str)
    s_sgg  = soyu[col_sgg].astype(str)

    # 타겟/소스 마스크
    mask_src = s_sido.str.contains('경상북도', na=False) & s_sgg.str.contains('군위군', na=False)
    mask_tgt = s_sido.str.contains('대구광역시', na=False) & s_sgg.str.contains('군위군', na=False)

    # 값 컬럼(연도/항목)만 추출: 위 두 키 컬럼 제외 전부
    value_cols = [c for c in soyu.columns if c not in {col_sido, col_sgg}]

    # 숫자형 변환(빈칸/문자 -> NaN)
    soyu[value_cols] = (
        soyu[value_cols]
        .replace('', np.nan)
        .apply(pd.to_numeric, errors='coerce')
    )

    # 소스가 없으면 그대로 반환
    if not mask_src.any():
        return soyu

    src_row = soyu.loc[mask_src, value_cols].sum(numeric_only=True)  # 혹시 중복행 있으면 합산
    # 타겟행이 있으면 "비어있는 곳만" 채우기 / 없으면 새로 만들기
    if mask_tgt.any():
        idx = soyu.index[mask_tgt][0]
        soyu.loc[idx, value_cols] = soyu.loc[idx, value_cols].combine_first(src_row)
    else:
        # 새 행 만들기: 키 컬럼 + value 컬럼 세팅
        new = {col_sido: '22 대구광역시', col_sgg: '22520 군위군'}
        for c in value_cols:
            new[c] = src_row[c]
        soyu = pd.concat([soyu, pd.DataFrame([new])], ignore_index=True)

    # 경북 군위군 행 삭제
    soyu = soyu.loc[~mask_src].reset_index(drop=True)
    return soyu

# 실행
soyu = move_gunwi_soyu_to_daegu(soyu)

# 4. jutaek 군위군 변경
def _find_col(df, contains: str):
    if isinstance(df.columns, pd.MultiIndex):
        cols = [c for c in df.columns if any(contains in str(x) for x in c)]
        if not cols:
            raise ValueError(f"멀티인덱스 컬럼에서 '{contains}' 포함 컬럼을 찾지 못했어요.")
        return cols[0]
    else:
        cols = [c for c in df.columns if contains in str(c)]
        if not cols:
            raise ValueError(f"컬럼에서 '{contains}' 포함 컬럼을 찾지 못했어요.")
        return cols[0]

def move_gunwi_jutaek_to_daegu(jutaek: pd.DataFrame) -> pd.DataFrame:
    jutaek = jutaek.copy()

    col_region = _find_col(jutaek, '행정구역별(읍면동)')  # "A 행정구역별(읍면동)"
    s = jutaek[col_region].astype(str)

    # ✅ 군위군을 "정확히" 잡기: 코드 우선, 없으면 텍스트 포함으로 보조
    mask_src = (s.str.contains(r'\b37510\b', na=False) & s.str.contains('군위군', na=False)) | \
               (s.str.contains('경상북도', na=False) & s.str.contains('군위군', na=False))

    mask_tgt = (s.str.contains(r'\b22520\b', na=False) & s.str.contains('군위군', na=False)) | \
               (s.str.contains('대구광역시', na=False) & s.str.contains('군위군', na=False))

    # 값 컬럼 = 지역 컬럼 제외 전부
    value_cols = [c for c in jutaek.columns if c != col_region]

    # 숫자형 변환
    jutaek[value_cols] = (
        jutaek[value_cols]
        .replace('', np.nan)
        .apply(pd.to_numeric, errors='coerce')
    )

    if not mask_src.any():
        return jutaek

    src_row = jutaek.loc[mask_src, value_cols].sum(numeric_only=True)

    if mask_tgt.any():
        idx = jutaek.index[mask_tgt][0]
        # 타겟이 비어있는 곳만 채우기(기존 값 보존)
        jutaek.loc[idx, value_cols] = jutaek.loc[idx, value_cols].combine_first(src_row)
    else:
        # 타겟 행 신규 생성
        new = {col_region: '　　　22520 군위군'}  # 대구광역시 블록 내부 포맷 유지(들여쓰기)
        for c in value_cols:
            new[c] = src_row[c]
        jutaek = pd.concat([jutaek, pd.DataFrame([new])], ignore_index=True)

    # 소스(경북 군위군) 행 삭제
    jutaek = jutaek.loc[~mask_src].reset_index(drop=True)
    return jutaek

# 실행
jutaek = move_gunwi_jutaek_to_daegu(jutaek)

#%%
'''데이터 불러오기2'''
# 1. gs_지역등급_멸실추출.sql
query = '''SELECT
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
;'''

conn = pymysql.connect(
    host="218.237.65.225",
    port=3306,
    user="wjd2165_dev",
    password="K5jqKGWFZAg2RvT",
    database="modueum",
    charset="utf8mb4",
    autocommit=True
)

try:
    with conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        meoylsil = pd.DataFrame.from_records(rows, columns=columns)
finally:
    conn.close()

# 2. gs_지역등급_내지인거래비율.spl
query = '''SELECT
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
'''

conn = pymysql.connect(
    host="218.237.65.225",
    port=3306,
    user="wjd2165_dev",
    password="K5jqKGWFZAg2RvT",
    database="modueum",
    charset="utf8mb4",
    autocommit=True
)

try:
    with conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        naejiin = pd.DataFrame.from_records(rows, columns=columns)
finally:
    conn.close()


# 3. gs_지역등급_매매실거래평당가.spl
query = '''SELECT
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
'''

conn = pymysql.connect(
    host="218.237.65.225",
    port=3306,
    user="wjd2165_dev",
    password="K5jqKGWFZAg2RvT",
    database="modueum",
    charset="utf8mb4",
    autocommit=True
)

try:
    with conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        silgeorae = pd.DataFrame.from_records(rows, columns=columns)
finally:
    conn.close()



# 4. gs_지역등급_분양물량+가격+기준이상세대수.sql
query = '''SELECT
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
'''

conn = pymysql.connect(
    host="218.237.65.225",
    port=3306,
    user="wjd2165_dev",
    password="K5jqKGWFZAg2RvT",
    database="modueum",
    charset="utf8mb4",
    autocommit=True
)

try:
    with conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        tripple = pd.DataFrame.from_records(rows, columns=columns)
finally:
    conn.close()


# 5. gs_지역등급_미분양.sql
query = '''SELECT
    jk_code,
    LEFT(td, 4) AS td,
    tot
FROM modueum.d_mibun
WHERE RIGHT(td, 2) = '12'
  AND LEFT(td, 4) BETWEEN '2022' AND '2025'
GROUP BY jk_code, td
ORDER BY jk_code, td;
'''

conn = pymysql.connect(
    host="218.237.65.225",
    port=3306,
    user="wjd2165_dev",
    password="K5jqKGWFZAg2RvT",
    database="modueum",
    charset="utf8mb4",
    autocommit=True
)

try:
    with conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        mibunyang = pd.DataFrame.from_records(rows, columns=columns)
finally:
    conn.close()






#%%
'''시트 만들기 시작'''
### 1. 일반가구수(통계청 주택총조사_일반,외국인가구)  <C ~ H열>
region = gagu.iloc[:, 0] # 지역
result_CH = gagu.xs(('T210 일반가구','00 계'), level = [1,2], axis = 1) # 일반가구수 00계
result_CH.columns = [f'general_hh_y{i}' for i in range(1, len(result_CH.columns) + 1)] # 가구수 칼럼명

result = pd.concat([region, result_CH], axis = 1) # 지역 + 가구


result.iloc[:,1:] = round(result.iloc[:,1:] ,2)
result = result.fillna(0)
result.isnull().sum()

### 2. 1인가구수(인구총조사_1인가구) <N ~ S열>
result_NS = ingu.xs(('T50 1인가구'), level = 1, axis = 1) # 1인가구수
result_NS.columns = [f'single_hh_y{i}' for i in range(1, len(result_NS.columns) + 1)] # 인구수 칼럼명

result = pd.concat([result, result_NS], axis = 1) # 결과파일에 인구수 추가 완료

# 칼럼이름 변경
result.rename(columns = {('A 행정구역별(시군구)', 'A 행정구역별(시군구)', 'A 행정구역별(시군구)'):'행정구역별(시군구)'}, inplace = True)


result['시군구'] = result['행정구역별(시군구)'].str.split(' ').str[1] # 시군구 칼럼 만들어줌
result.insert(1,'시군구', result.pop('시군구')) # 위치변경

result['지역코드1'] = result['행정구역별(시군구)'].str.split(' ').str[0] # 지역코드 칼럼 만들어줌
result.insert(1,'지역코드1', result.pop('지역코드1')) # 위치변경

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)
result = result.fillna(0)
result.isnull().sum()

### 3. 1인가구증가 <T ~ X열>
for i in range(1, 7):
    result[f'single_hh_y{i}'] = pd.to_numeric(result[f'single_hh_y{i}'], errors='coerce') # 타입 숫자로 변경

for i in range(1, 7):
    result[f'general_hh_y{i}'] = pd.to_numeric(result[f'general_hh_y{i}'], errors='coerce') # 타입 숫자로 변경

for i in range(1, 6):
    result[f'single_hh_inc_y{i}'] = result[f'single_hh_y{i + 1}'] - result[f'single_hh_y{i}'] # 가구수 하나씩 빼며 계산

result = round(result,2)

### 4. 일반가구증가(1인가구 外 전년대비 증감수) <I ~ M 열>
for i in range(1,6):
    result[f'general_hh_inc_y{i}'] = result[f'general_hh_y{i + 1}'] - result[f'general_hh_y{i}'] - result[f'single_hh_inc_y{i}']

# 칼럼 순서 바꿔줌 I ~M 열에  일반가구증가 넣음
result.insert(9, 'general_hh_inc_y1', result.pop('general_hh_inc_y1'))
result.insert(10, 'general_hh_inc_y2', result.pop('general_hh_inc_y2'))
result.insert(11, 'general_hh_inc_y3', result.pop('general_hh_inc_y3'))
result.insert(12, 'general_hh_inc_y4', result.pop('general_hh_inc_y4'))
result.insert(13, 'general_hh_inc_y5', result.pop('general_hh_inc_y5'))

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)
result.isnull().sum()

### 5. 일반가구아파트비율 <Y ~ AC열> 특이사항 : 기존은 5년치, 이번꺼는 6년치 집계됨 <Y ~ AC 열>
result_YAC1 = gagu.xs(('T210 일반가구','102 주택_아파트'), level = [1,2] ,axis = 1) # 일반가구 아파트 가져옴
result_YAC1 = result_YAC1.astype('float64')

result_YAC2 = gagu.xs(('T210 일반가구','00 계'), level = [1,2] ,axis = 1)# 일반가구 계 가져옴
result_YAC2 = result_YAC2.astype('float64')

result_YAC = (result_YAC1 / result_YAC2) # 아파트 / 계 비율 계산
# result_YAC = result_YAC.astype(str) + '%' # % 붙여줌

result_YAC = result_YAC.iloc[:,1:] # 19년도는 안가져오기위해 커팅함
result_YAC.columns = [f'general_hh_ratio_y{i}' for i in range(1, len(result_YAC.columns) + 1)] # 칼럼이름 변경


for col in result_YAC.columns:
    result_YAC[col] = round(result_YAC[col],2)
    

result = pd.concat([result , result_YAC], axis = 1) # result에 비율정보 추가
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)
result = result.fillna(0)
result.isnull().sum()

### 6. 일반아파트가구증가(1인가구 外_최근5년평균 <AD ~ AI 열>
for i in range(1 , 6):
    result[f'general_hh_apt_inc_y{i}'] = result[f'general_hh_inc_y{i}'] * result[f'general_hh_ratio_y{i}']

# 일반아파트가구증가 - 5년 평균 넣어주기
result['general_hh_apt_inc_AVG'] = result.iloc[:,-5:].mean(axis = 1) # 맨 마지막 5개 열로 계산함

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)
result.isnull().sum()

### 7. 1인아파트가구증가_최근5년평균 <AJ ~ AO 열>
for i in range(1 , 6):
    result[f'single_hh_apt_inc_y{i}'] = result[f'single_hh_inc_y{i}'] * result[f'general_hh_ratio_y{i}']

# 1인아파트가구증가 - 5년 평균 넣어주기
result['single_hh_apt_inc_AVG'] = result.iloc[:,-5:].mean(axis = 1) # 맨 마지막 5개 열로 계산

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)


### 8. 소계(a) <AP ~ AT열>
for i in range(1, 6):
    result[f'general_hh_apt_demand_y{i}'] = result[f'general_hh_apt_inc_y{i}'] + result[f'single_hh_apt_inc_y{i}']

# 소계(a) - 5년 평균 넣어주기 <AU 열>
result['general_hh_apt_inc'] = result.iloc[:,-5:].mean(axis = 1) # 맨 마지막 5개 열로 계산

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 9. 외국인가구수(주택총조사_일반,외국인가구) <AV ~ BA 열>
result_AVBA = gagu.xs(('T230 외국인가구','00 계'),level = [1,2], axis = 1)

result_AVBA.columns = [f'foreign_hh_y{i}' for i in range(1,len(result_AVBA.columns) + 1)] # 칼럼이름 변경

result_AVBA = result_AVBA.astype('float64')

# result에 외국인가구수 추가
result = pd.concat([result, result_AVBA], axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)
result = result.fillna(0)
result.isnull().sum()

### 10. 외국인가구증가 <BB ~ BF 열>
for i in range(1, 6) :
    result[f'foreign_hh_inc_y{i}'] = result[f'foreign_hh_y{i+1}'] - result[f'foreign_hh_y{i}']

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 11. 외국인가구아파트비율 <BG ~ BK 열>
result_BGGK1 = gagu.xs(('T230 외국인가구','00 계'),level = [1,2], axis = 1).astype('float64').iloc[:,1:] # 외국인가구 계 가져옴
result_BGGK2 = gagu.xs(('T230 외국인가구','102 주택_아파트'), level = [1,2], axis = 1).iloc[:,1:] # 외국인가구 주택_아파트 가져옴

# result_BGGK2 에 문자 X 발견하여 결측치로 처리
result_BGGK2 = result_BGGK2.replace('X',np.nan)

result_BGGK2 = result_BGGK2.astype('float64')
result_BGGK = result_BGGK2 / result_BGGK1 # 두개 나누어줌

result_BGGK.columns = [f'foreign_hh_ratio_y{i}' for i in range(1,len(result_BGGK.columns) + 1)] # 칼럼 이름 변경

# result에 외국인가구아파트비율 추가
result = pd.concat([result, result_BGGK], axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

result = result.fillna(0)
result.isnull().sum()


### 12. 외국인아파트가구증가 <BL ~ BQ 열>
for i in range(1, 6):
    result[f'foreign_hh_apt_inc_y{i}'] = result[f'foreign_hh_inc_y{i}'] * result[f'foreign_hh_ratio_y{i}']

# 외국인아파트가구증가 - 5년 평균 넣어주기
result['foreign_hh_apt_inc'] = result.iloc[:,-5:].mean(axis = 1)

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 13. 시도 멸실 아파트 <BR ~ BV 열>
result['지역코드1'] = result['지역코드1'].str.strip()
result = result.merge(j_code, on = '지역코드1', how = 'left') # 새로운 지역코드 붙임
result.insert(2, 'jk_code', result.pop('jk_code')) # 칼럼순서변경

# jk_code 앞자리 2인것들에 대해 앞에 0을 붙여줌
result.loc[result['jk_code'].str[:1] == '2', 'jk_code'] = '0' + result.loc[result['jk_code'].str[:1] == '2', 'jk_code']

# result jk_code 안붙은 곳들에 대해서 지역코드1에 -200 한다음 다시 지역코드 붙이기
list_200 = result[(result['지역코드1'].str.len() == 5) & (result['jk_code'].isnull())].index

result.loc[list_200, '지역코드1'] = result.loc[list_200, '지역코드1'].astype(int) - 200 # 안붙은 지역들에 대해서 -200

# 새로 매핑할 딕셔너리
code_map = j_code.set_index('지역코드1')['jk_code']

# 다시 붙이기
result.loc[list_200, 'jk_code'] = (
    result.loc[list_200, '지역코드1']
    .astype(str)
    .str.strip()
    .map(code_map)
)


# 멸실에서 칼럼 필터링
meoylsil_ext = meoylsil[['jk_code','y-5', 'y-4', 'y-3', 'y-2', 'y-1']] # 멸실 데이터 추출
meoylsil_ext.columns = ['jk_code','demolished_apt_y1','demolished_apt_y2','demolished_apt_y3','demolished_apt_y4','demolished_apt_y5']

# result에 시군구멸실아파트 추가
result = result.merge(meoylsil_ext, on = 'jk_code', how = 'left') # 

# 시군구별멸실아파트 5년 평균 구해주기 <BW열>
result['demolished_apt_inc'] = result.iloc[:,-5:].mean(axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)


### 14. a+b+c 구하기 <BX열>
result['natural_demand'] = result['general_hh_apt_inc'] + result['foreign_hh_apt_inc'] + result['demolished_apt_inc']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 15. 다주택자 <BY ~ CB열> - 지역코드 기준으로 다시 붙이기
result_BYCB_code1 = soyu.xs(('SGG 거주지역별(1)'), level = 1, axis = 1) # 소유에서 거주지역별1 가져옴
result_BYCB_code2 = soyu.xs(('SGG 거주지역별(2)'), level = 1, axis = 1) # 소유에서 거주지역별1 가져옴

result_BYCB_code = pd.concat([result_BYCB_code1,result_BYCB_code2], axis = 1) # 거주지역별 정보 합침

# 거주지역별 2 비어있는곳 1로 채워주기
result_BYCB_code.loc[result_BYCB_code['SGG 거주지역별(2)'] == '소계', 'SGG 거주지역별(2)'] = result_BYCB_code['SGG 거주지역별(1)']

# SGG 거주지역별(2) 에서 지역코드 떼어내기
result_BYCB_code['지역코드1'] = result_BYCB_code['SGG 거주지역별(2)'].str.split(' ').str[0]

result_BYCB1 = soyu.xs(('000 총계'),level = 1, axis = 1) # 소유에서 총계만 가져옴
result_BYCB2 = soyu.xs(('010 1건'),level = 1, axis = 1) # 소유에서 1건만 가져옴

result_BYCB1 = result_BYCB1.astype("Int64") # 정수로 변환
result_BYCB2 = result_BYCB2.astype("Int64")
result_BYCB = result_BYCB1 - result_BYCB2 # 빼서 다주택자를 계산

result_BYCB.columns = [f'multi_homeowner_y{i}' for i in range(1, len(result_BYCB.columns) + 1)] # 칼럼이름 변경

result_BYCB = pd.concat([result_BYCB_code['지역코드1'], result_BYCB], axis = 1) # 지역코드와 다주택자 합침

# 지역코드 형태에 따라 안붙는거 생김 -> 안붙는거는 int로 바꿔서 다시 매핑
result_BYCB['지역코드2'] = result_BYCB['지역코드1'].astype(int) # 

# result 에 다주택자 추가 1
result = result.merge(result_BYCB, on = '지역코드1', how = 'left')
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

# 1) 안 붙은 행만 마스크
mask = result['multi_homeowner_y1'].isna()
mh_cols = [c for c in result.columns if c.startswith('multi_homeowner_y')]

map2 = result_BYCB.drop(columns=['지역코드1'], errors='ignore') \
                 .drop_duplicates(subset=['지역코드2'])

fill = (
    result.loc[mask, ['지역코드1']]
    .merge(map2, left_on='지역코드1', right_on='지역코드2', how='left')
    .set_index(result.loc[mask].index)   # 인덱스 맞추기
)

# 빈 값만 채우기
result.loc[mask, mh_cols] = result.loc[mask, mh_cols].combine_first(fill[mh_cols])

result.drop('지역코드2', axis = 1, inplace = True)

### 16. 다주택자증가(전년대비) <CC ~ CE열>
for i in range(1, 4):
    result[f'multi_homeowner_inc_y{i}'] = result[f'multi_homeowner_y{i + 1}'] - result[f'multi_homeowner_y{i}']

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 17. 내지인거래비율 <CF ~ CH 열>
result_CFCH = naejiin.copy() # 내지인 거래비율 가져옴

# 내지인거래, 거래합계 타입 변경
for col in ['내지인거래_y1','내지인거래_y2','내지인거래_y3','거래합계_y1','거래합계_y2','거래합계_y3'] :
    result_CFCH[col] = result_CFCH[col].astype('Int64')


# 직접 빼서 local_buyer_ratio 계산
result_CFCH['local_buyer_ratio_y1'] = result_CFCH['내지인거래_y3'] / result_CFCH['거래합계_y3']
result_CFCH['local_buyer_ratio_y2'] = result_CFCH['내지인거래_y2'] / result_CFCH['거래합계_y2']
result_CFCH['local_buyer_ratio_y3'] = result_CFCH['내지인거래_y1'] / result_CFCH['거래합계_y1']

#for i in [1,2,3]:
#    result_CFCH[f'local_buyer_ratio_y{i}'] = result_CFCH[f'local_buyer_ratio_y{i}'].astype(int)

# result 에 내지인거래비율 추가
# result = pd.concat([result, result_CFCH.iloc[:,-3:]], axis = 1)
result = result.merge(result_CFCH[['jk_code','local_buyer_ratio_y1','local_buyer_ratio_y2','local_buyer_ratio_y3']], on = 'jk_code', how = 'left')
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

result = result.fillna(0)

### 18. 매매평균실거래 <CI ~ CK열>
result_CICK = silgeorae.copy() # 실거래데이터 가져옴

# 날짜에 Q1 ~ Q6 순서대로 부여
vals = sorted(result_CICK['left(a.td,6)'].unique())
mapping = {v: f"Q{i+1}" for i, v in enumerate(vals)}
result_CICK['Q_label'] = result_CICK['left(a.td,6)'].map(mapping)

# 지역코드별 - 쿼터별 매매평당가 구함
result_CICK2 = result_CICK.pivot_table(index = 'jk_code', columns = 'Q_label', values = '매매평당가').reset_index()
result_CICK2['avg_trade_price_y3'] = result_CICK2[['Q3', 'Q4', 'Q5', 'Q6']].mean(axis=1)
result_CICK2['avg_trade_price_y2'] = result_CICK2[['Q2', 'Q3', 'Q4', 'Q5']].mean(axis=1)
result_CICK2['avg_trade_price_y1'] = result_CICK2[['Q1', 'Q2', 'Q3', 'Q4']].mean(axis=1)

# result에 매매평균실거래 추가
# result = pd.concat([result, result_CICK2.iloc[:,-3:]], axis = 1)
result = result.merge(result_CICK2[['jk_code','avg_trade_price_y1','avg_trade_price_y2','avg_trade_price_y3']], on = 'jk_code', how = 'left')
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

result = result.fillna(0)
result.isnull().sum()


### 19. 평균분양가 <CL ~ CN열>
result_CLCN = tripple[['jk_code','price_q1','price_q2','price_q3','price_ref']].copy()
# 타입 변환
result_CLCN['price_q1'] = result_CLCN['price_q1'].astype('float64')
result_CLCN['price_q2'] = result_CLCN['price_q2'].astype('float64')
result_CLCN['price_q3'] = result_CLCN['price_q3'].astype('float64')

# 1. price_q3 결측 = price_q2 * 1.05
mask = result_CLCN['price_q3'].isna() & result_CLCN['price_q2'].notna()
result_CLCN.loc[mask, 'price_q3'] = result_CLCN.loc[mask, 'price_q2'] * 1.05

# 2. price_q1 결측 = price_q2 * 0.95
mask = result_CLCN['price_q1'].isna() & result_CLCN['price_q2'].notna()
result_CLCN.loc[mask, 'price_q1'] = result_CLCN.loc[mask, 'price_q2'] * 0.95

# 3-1. price_q2 결측 & price_q1 존재 → price_q1 * 1.05
mask = result_CLCN['price_q2'].isna() & result_CLCN['price_q1'].notna()
result_CLCN.loc[mask, 'price_q2'] = result_CLCN.loc[mask, 'price_q1'] * 1.05

# 3-2. price_q2 결측 & price_q1도 결측 & price_q3 존재 → price_q3 * 0.95
mask = result_CLCN['price_q2'].isna() & result_CLCN['price_q1'].isna() & result_CLCN['price_q3'].notna()
result_CLCN.loc[mask, 'price_q2'] = result_CLCN.loc[mask, 'price_q3'] * 0.95

# q3 결측 = q2 * 1.05  (다시)
mask = result_CLCN['price_q3'].isna() & result_CLCN['price_q2'].notna()
result_CLCN.loc[mask, 'price_q3'] = result_CLCN.loc[mask, 'price_q2'] * 1.05

# q1 결측 = q2 * 0.95  (다시)
mask = result_CLCN['price_q1'].isna() & result_CLCN['price_q2'].notna()
result_CLCN.loc[mask, 'price_q1'] = result_CLCN.loc[mask, 'price_q2'] * 0.95

result_CLCN.rename(columns = {"price_q1":"py_bprice_y1","price_q2":"py_bprice_y2","price_q3":"py_bprice_y3"}, inplace = True)

# result에 평균분양가 추가
result = result.merge(result_CLCN.iloc[:,:4], on = 'jk_code', how = 'left')
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

result.isnull().sum()

### 20. 가격보정(실거래/분양가) <CO ~ CQ열>
for i in range(1,4) :
    result[f'adj_price_y{i}'] = result[f'avg_trade_price_y{i}'] / result[f'py_bprice_y{i}']
    result[f'adj_price_y{i}'] = result[f'adj_price_y{i}'].astype('float64')

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)


### 21. 3년 가중치 <CR ~ CT열>
result['internal_invest_demand_3yr_wgt_y1'] = 0.2
result['internal_invest_demand_3yr_wgt_y2'] = 0.3
result['internal_invest_demand_3yr_wgt_y3'] = 0.5

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 22. 투자수요(내부) 소계_a <CU ~ CW열>
for i in range(1,4):
    result[f'internal_invest_demand_y{i}'] = result[f'multi_homeowner_inc_y{i}'] * result[f'local_buyer_ratio_y{i}'] * result[f'adj_price_y{i}'] * result[f'internal_invest_demand_3yr_wgt_y{i}']

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 23. 평균(결과) <CX열>
result['internal_invest_demand'] = result[['internal_invest_demand_y1','internal_invest_demand_y2','internal_invest_demand_y3']].mean(axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)



### 24. 분양물량 <CY ~ DA열>
result_CYDA = tripple[['jk_code','qty_2023','qty_2024','qty_2025']].copy() # tripple에서 가져옴
result_CYDA.rename(columns = {'qty_2023':'bqty_y1','qty_2024':'bqty_y2','qty_2025':'bqty_y3'}, inplace = True)

# result에 분양물량 추가
result = result.merge(result_CYDA, on = 'jk_code', how = 'left')

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)


### 25. 연말 기준 미분양물량 <DB ~ DE열>
# result에 미분양물량 추가
pivoted = mibunyang.pivot_table(
    index='jk_code',
    columns='td',
    values='tot',
    aggfunc='first'
).reset_index()

result = result.merge(pivoted, on='jk_code', how='left')

result.columns = list(result.columns[:-4]) + ['mibun_y1', 'mibun_y2', 'mibun_y3', 'mibun_y4'] # 마지막 4개 칼럼 이름변경

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)
result.iloc[:,-4:] = result.iloc[:,-4:].fillna(0)

### 26. 분양물량+전년미분양 <DF ~ DH열>
# result에 분양물량 + 전년미분양 추가
for i in range(1,4):
    result[f'b_p_mi_y{i}'] = result[f'bqty_y{i}'] + result[f'mibun_y{i}']
result = round(result,2)

### 27. 소화물량 <DI ~ DK>
for i in range(1,4):
    result[f'absorbed_supply_y{i}'] = result[f'b_p_mi_y{i}'] - result[f'mibun_y{i + 1}']
    result[f'absorbed_supply_y{i}'] = result[f'absorbed_supply_y{i}'].astype('Int64')

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)
result.iloc[:,-3:] = result.iloc[:,-3:].fillna(0)


### 28. 매매평균실거래, 평균분양가, 가격보정 <DL ~ DT> 는 스킵함 - 앞에거와 중복이기 때문

### 29. 외지인거래비율 <DU ~ DV열>
for i in range(1,4):
    result[f'nonlocal_buyer_ratio_y{i}'] = 1 - result[f'local_buyer_ratio_y{i}']
    
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 30. 3년 가중치 <DX ~ DZ 열>
result['external_invest_demand_3yr_wgt_y1'] = 0.2
result['external_invest_demand_3yr_wgt_y2'] = 0.3
result['external_invest_demand_3yr_wgt_y3'] = 0.5

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 31. 투자수요(외부) 소계_b <EA ~ EC열>
for i in range(1,4) :
    result[f'external_invest_demand_y{i}'] = result[f'absorbed_supply_y{i}'] * result[f'adj_price_y{i}'] * result[f'nonlocal_buyer_ratio_y{i}'] * result[f'external_invest_demand_3yr_wgt_y{i}']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 32. 평균(결과) <ED 열>
result['external_invest_demand'] = result[['external_invest_demand_y1','external_invest_demand_y2','external_invest_demand_y3']].mean(axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 33. a + b <EE열>
result['total_invest_demand'] = result['internal_invest_demand'] + result['external_invest_demand']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 34. 자연발생수요+투자수요 <EF열>
result['new_demand_volume'] = result['natural_demand'] + result['total_invest_demand']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 35. 직전년 평균평단가 <EG열>
result_EG = silgeorae.copy()
result_EG['year'] = result_EG['left(a.td,6)'].str[:4] #  년도 생성

# 년도별 매매평당가 조회
result_EG = result_EG.groupby(['jk_code','year'])['매매평당가'].mean().unstack().reset_index()[['jk_code','2025']]

# result에 직전년 평균평단가 추가
result = result.merge(result_EG, on = 'jk_code', how = 'left')
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

result.iloc[:,-1:] = result.iloc[:,-1:].fillna(0)

### 36. 직전년 평균분양가 <EH ~ EI열>
result['py_bprice_y3_34py'] = round(result['py_bprice_y3'] * 34, -2)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 37. 분양가기준가격비율 <EJ열>
result['bprice_threshold_ratio'] = 0.55
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 38. 기준가격 이상 apt 세대수(매매가) <EK열>
result = result.merge(tripple[['jk_code','mm기준_qty합계']], on = 'jk_code', how = 'left') # result에 세대수 데이터 추가
result.rename(columns = {'mm기준_qty합계':'apt_hh_over_threshold_mm'}, inplace = True)
result['apt_hh_over_threshold_mm'] = result['apt_hh_over_threshold_mm'].astype('Int64')
result['apt_hh_over_threshold_mm'] = result['apt_hh_over_threshold_mm'].fillna(0)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 39. 소득분위 <EL열>
soduk['상환기간(연)'] = soduk['상환기간(연)'].astype(int)
soduk['금리'] = soduk['금리'].astype('float64')
soduk['LTV'] = soduk['LTV'].astype('float64')
soduk['DTI'] = soduk['DTI'].astype('float64')

for col in soduk.columns[-9:]:
    soduk[col] = pd.to_numeric(soduk[col], errors='coerce').astype(float)

soduk.loc[soduk['jk_code'].str[:1] == '2', 'jk_code'] = '0' + soduk.loc[soduk['jk_code'].str[:1] == '2', 'jk_code']
soduk = soduk.merge(result[['jk_code','py_bprice_y3']], on = 'jk_code', how = 'left') # 소득분위데이터에 평균분양가 병합

soduk.insert(5, 'py_bprice_y3', soduk.pop('py_bprice_y3')) # 칼럼 위치 변경

# 평균분양가 34평기준 만들기<FL열>
# soduk['py_bprice_y34'] = round(soduk['py_bprice_y3'] * 34, -3)



# 1. 금융 계산 함수
def pmt(rate, nper, pv):
    if abs(rate) < 1e-15:
        return -pv / nper
    return -(pv * rate) / (1 - (1 + rate) ** -nper)

def round_half_away_from_zero(x, digits):
    factor = 10 ** (-digits)
    y = x / factor
    return np.sign(y) * np.floor(abs(y) + 0.5) * factor

# 2. 소득구간 정의 (만원)
BANDS = [
    (1500, 2000),
    (2000, 2500),
    (2500, 3000),
    (3000, 4000),
    (4000, 5000),
    (5000, 6000),
    (6000, 7000),
    (7000, 10000),
    (10000, None)   # 1억 이상
]

# 3. 3. 단일 row 계산
def calc_income_quantile(row):
    # ── 기본 파라미터 (순서 기반)
    rate = row.iloc[1]
    years = int(row.iloc[2])
    ltv = row.iloc[3]
    dti = row.iloc[4]
    price = row.iloc[5]
    
    if pd.isna(price):
        return np.nan

    counts = row.iloc[6:15].astype(float).fillna(0).values
    total = counts.sum()

    # ── 금융 계산
    loan = price * 34 * ltv
    G = pmt(rate / 12, years * 12, loan)          # 월상환(음수)
    H_raw = -(G / dti) * 12                        # 연소득(만원)
    H = round_half_away_from_zero(H_raw, -2)      # 100단위 반올림

    # ── 1500 미만 → 0%
    if H < 1500 or total == 0:
        return 0.0

    # ── 소득구간 탐색 + 선형보간
    for i, (lo, hi) in enumerate(BANDS):
        if hi is None or (lo <= H < hi):
            # 상위구간 합
            higher = counts[i+1:].sum()
            # 현재구간 비율
            if hi is None:
                share = 1.0
            else:
                share = 1 - (H - lo) / (hi - lo)
                share = max(0, min(1, share))
            tail = counts[i] * share + higher
            return tail / total

    return 0.0


# 4. 소득분위 계산
soduk["소득분위"] = soduk.apply(calc_income_quantile, axis=1)
soduk.rename(columns = {'소득분위':'income_quintile'}, inplace = True)

soduk['income_quintile'] = soduk['income_quintile'].fillna(0)

# result에 소득분위 추가 <EL열>
result = result.merge(soduk[['jk_code','income_quintile']], on = 'jk_code', how = 'left')
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)
result.iloc[:,-1:] = result.iloc[:,-1:].fillna(0)
result.isnull().sum()

### 40. 자가거주비율, 이사계획 유 <EM ~ EN 열>
result['own_hh_ratio'] = 0.74
result['own_move_plan_yn'] = 0.05
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 41. 자가가구apt이전수요 <EO열>
result['income_quintile'] = result['income_quintile'].fillna(0)

result["own_hh_apt_move_demand"] = result.iloc[:, -4:].prod(axis=1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 42. 평균분양가(34평) <ER열>
result['py_bprice_y3_34py2'] = round(result['py_bprice_y3'] * 34, -2)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 43. 직전년 평균분양가의 55% <ES열>
result['py_bprice_y3_34py2_55'] = result.iloc[:,-1:] * 0.55
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 44. 기준가격 이상 apt 세대수(전세가) <ET열>
result = result.merge(tripple[['jk_code','js기준_qty합계']], on = 'jk_code', how = 'left') # result에 세대수 데이터 추가
result.rename(columns = {'js기준_qty합계':'apt_hh_over_threshold_js'}, inplace = True)
result['apt_hh_over_threshold_js'] = result['apt_hh_over_threshold_js'].astype('Int64')
result['apt_hh_over_threshold_js'] = result['apt_hh_over_threshold_js'].fillna(0)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 45. 임차비율 <EV열>
result['rent_hh_ratio'] = 0.26
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 46.이사계획 有 <EW열>
result['rent_move_plan_yn'] = 0.2
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 47. 임차가구apt 이주 수요 <EX열>
result['rent_hh_apt_move_demand'] = result[['apt_hh_over_threshold_js', 'income_quintile', 'rent_hh_ratio', 'rent_move_plan_yn']].prod(axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 48. 아파트 가구 비율 <EY열>
# list_200 지역코드 다시 + 200
result['지역코드1'].dtype
result.loc[list_200, '지역코드1'] = result.loc[list_200, '지역코드1'].astype(int) + 200

# 1. 주택에서 주택코드 분리
jutaek['지역코드1'] = jutaek['A 행정구역별(읍면동)', 'A 행정구역별(읍면동)'].str.split(' ').str[0]

# 2. 년도별 아파트 / 주택 평균 계산
result_EY = pd.concat([jutaek['지역코드1'] ,(jutaek.xs(('T30 아파트'), level = 1, axis = 1).astype('Int64') / jutaek.xs(('T10 주택'), level = 1, axis = 1).astype('Int64')).mean(axis = 1)], axis = 1)
result_EY.columns = ['지역코드1','apt_hh_ratio']

# 지역코드 빈칸 제거
result_EY['지역코드1'] = result_EY['지역코드1'].astype(str).str.replace(r'\s+', '', regex=True)
result['지역코드1'] = result['지역코드1'].astype(str).str.replace(r'\s+', '', regex=True)

# result에 아파트가구비율 추가
result = result.merge(result_EY, on = '지역코드1', how = 'left')




### 49. 단독가구비율 <EZ 열>
# 1. 년도별 단독주택 - 계 / 주택 계산
result_EZ = pd.concat([jutaek['지역코드1'] ,(jutaek.xs(('T20 단독주택-계'), level = 1, axis = 1).astype('Int64') / jutaek.xs(('T10 주택'), level = 1, axis = 1).astype('Int64')).mean(axis = 1)], axis = 1)
result_EZ.columns = ['지역코드1','sp_hh_ratio']

# 지역코드 빈칸 제거
result_EZ['지역코드1'] = result_EZ['지역코드1'].astype(str).str.replace(r'\s+', '', regex=True)

# result에 단독가구비율 추가
result = result.merge(result_EZ, on = '지역코드1', how = 'left')




### 50. 연립다세대가구비율 <FA 열>
# 1. 년도별 단독주택 - 계 / 주택 계산
jutaek = jutaek.replace('X',np.nan) # T40 연립주택에 문자열 X 발견함.

result_FA = pd.concat([jutaek['지역코드1'] ,((jutaek.xs(('T40 연립주택'), level = 1, axis = 1).astype('Int64') + jutaek.xs(('T50 다세대주택'), level = 1, axis = 1).astype('Int64')) /
                                         jutaek.xs(('T10 주택'), level = 1, axis = 1).astype('Int64')).mean(axis = 1)], axis = 1)

# 지역코드 빈칸 제거
result_FA['지역코드1'] = result_FA['지역코드1'].astype(str).str.replace(r'\s+', '', regex=True)

result_FA.columns = ['지역코드1','mf_hh_ratio']

# result에 연립다세대가구비율 추가
result = result.merge(result_FA, on = '지역코드1', how = 'left')


### 51. (단독+다세대/아파트)가구 비율 <FB 열>
result['nonapt_hh_ratio'] = result[['sp_hh_ratio', 'mf_hh_ratio']].sum(axis = 1) / result['apt_hh_ratio']


### 52. 모수 보정 <FC 열>
result['nonapt_adj'] = result[['own_hh_apt_move_demand','rent_hh_apt_move_demand']].sum(axis = 1) * result['nonapt_hh_ratio']


### 53. 이사계획 보정 <FD 열>
result['nonapt_move_plan_yn'] = 0.4

### 54. 가격 보정 <FE 열>
result['nonapt_price_adj'] = 0.6

### 55. 비apt 이주 수요 <FF 열>
result['nonapt_move_demand'] = result.iloc[:,-3:].prod(axis = 1) # 맨 마지막 3개 열을 곱했음

### 56. 이주수요 계 <FG 열>
result['total_move_demand'] = result[['own_hh_apt_move_demand', 'rent_hh_apt_move_demand', 'nonapt_move_demand']].sum(axis = 1)

### 57. 소득분위 soduk 붙이기
soduk2 = soduk.copy()

# 1. 평균 분양가(34평 기준, 직전년 평균 분양가*34) <FL 열>
soduk2['평균분양가'] = round(soduk2['py_bprice_y3'] * 34 , -3)

# 2. 대출 수준 <FM 열>
soduk2['대출수준'] = round(soduk2['py_bprice_y3'] * 34 * soduk2['LTV'], -2)

# 3. 월상환금액<FN 열>
def pmt_vec(rate, nper, pv):
    rate = np.asarray(rate)
    nper = np.asarray(nper)
    pv = np.asarray(pv)

    return np.where(
        np.abs(rate) < 1e-15,
        -pv / nper,
        -(pv * rate) / (1 - (1 + rate) ** -nper)
    )

soduk2['월상환금액(만원)'] = pmt_vec(soduk2['금리'] / 12 , soduk2['상환기간(연)'] * 12, soduk2['대출수준'])

# 4. 연소득금액(만원) <FO 열>
soduk2['연소득금액'] =  - round((soduk2['월상환금액(만원)'] / soduk2['DTI']) , -1) * 12

# 위치 변경
soduk2.insert(5, '평균분양가', soduk2.pop('평균분양가'))
soduk2.insert(6, '대출수준', soduk2.pop('대출수준'))
soduk2.insert(7, '월상환금액(만원)', soduk2.pop('월상환금액(만원)'))
soduk2.insert(8, '연소득금액', soduk2.pop('연소득금액'))

# 5. 계 만들기
soduk2['계'] = soduk2.iloc[:,-10:-1].sum(axis = 1)

# 6. 소득분위 이름 변경, 위치변경
soduk2.rename(columns = {'income_quintile':'소득분위'}, inplace = True) # 이름 변경
soduk2['소득분위'] = soduk2.pop('소득분위') # 소득분위 맨뒤로

# 7. py_bprice 지운다음 result에 붙이기
soduk2 = soduk2.drop(columns = 'py_bprice_y3')

# 8. soduk2 에서 첫째자리 2인거 앞에 0 붙여주기
soduk2.loc[soduk2['jk_code'].str[:1] == '2', 'jk_code'] = '0' + soduk2.loc[soduk2['jk_code'].str[:1] == '2', 'jk_code']

# result에 soduk2 추가 <FH ~ FZ열>
result = result.merge(soduk2, on = 'jk_code', how = 'left')


### 58. 1인&외국인가구 증가분 <GA 열>
result['single_and_foreign_hh_inc'] = result[['single_hh_apt_inc_AVG','foreign_hh_apt_inc']].sum(axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 59. 자가점유율 <GB 열>
result['single_foreign_own_occ_ratio'] = 0.3
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 60. 소득분위 <GC 열>
result['소득분위2'] = result['소득분위']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 61. 결과 <GD 열>
result['single_and_foreign_demand'] = result.iloc[:,-3:].prod(axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 62. 1인 外&멸실가구 증가분 <GE 열>
result['multi_hh_and_demolished_hh_inc'] = result[['general_hh_apt_inc_AVG','demolished_apt_inc']].sum(axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 63. 자가점유율 <GF 열>
result['multi_demolished_own_occ_ratio'] = 0.7
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 64. 소득분위 <GG 열>
result['소득분위3'] = result['소득분위']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 65. 결과 <GH 열>
result['multi_and_demolished_demand'] = result.iloc[:,-3:].prod(axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 66. 결과 <GI 열>
result['hh_increase_demand'] = result[['single_and_foreign_demand', 'multi_and_demolished_demand']].sum(axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 67. 투자수요내부 <GJ 열>
result['internal_invest_demand2'] = result['internal_invest_demand']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 68. 투자수요외부 <GK열>
result['external_invest_demand2'] = result['external_invest_demand']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)
result.isnull().sum()

result['internal_invest_demand'].isnull().sum()

### 69. 지역 제고 아파트수(아파트+연립+다세대) <GL 열>
result_GL = pd.concat([jutaek.xs(('지역코드1'), level = 0 , axis = 1), jutaek.xs(('Y2024 2024','T30 아파트'), level = [0,1] , axis = 1),
          jutaek.xs(('Y2024 2024','T40 연립주택'), level = [0,1] , axis = 1), jutaek.xs(('Y2024 2024','T50 다세대주택'), level = [0,1] , axis = 1)], axis = 1)

# 칼럼 타입 변경
for col in result_GL.columns.values[1:]:
    result_GL[col] = result_GL[col].astype('Int64')

result_GL['house_qty'] = result_GL.iloc[:,-3:].sum(axis = 1) # 합산
result_GL.columns.values[0] = '지역코드1' # 칼럼이름 지역코드로 변경

result_GL = result_GL[['지역코드1','house_qty']]

# 지역코드 빈칸 제거
result_GL['지역코드1'] = result_GL['지역코드1'].astype(str).str.replace(r'\s+', '', regex=True)

# result에 지역 제고 아파트수 추가
result = result.merge(result_GL, on = '지역코드1', how = 'left')
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 70. 미분양 <GM 열>
result['mibun_y4_2'] = result['mibun_y4']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 71. 미분양 수준 <GN 열>
result['unsold_level_ratio'] = np.nan
mask = result['house_qty'] != 0

result.loc[mask, 'unsold_level_ratio'] = (
    result.loc[mask, 'mibun_y4_2'] / result.loc[mask, 'house_qty']
)

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 72. 미분양 비율 보정률<GO 열>
result['unsold_level_adj_ratio'] = np.where(
    result['unsold_level_ratio'] < 0.005, 1.0,
    np.where(
        result['unsold_level_ratio'] < 0.01, 0.8,
        np.where(
            result['unsold_level_ratio'] < 0.015, 0.6,
            0.4
        )
    )
)

# 미분양 관리지역이면 20%로 덮어쓰기
result.loc[result['unsold_level_ratio'].isnull(), 'unsold_level_adj_ratio'] = 0.2

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 73. 투자수요(유효수요) <GP열>
result['total_invest_demand_eff'] = (result['internal_invest_demand'] + result['external_invest_demand']) * result['unsold_level_adj_ratio']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)


### 74. 유효수요 <GQ 열>
result['effective_demand'] = result[['total_move_demand','hh_increase_demand','total_invest_demand_eff']].sum(axis = 1)
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)


### 75. 공급물량(예정포함) <GR 열>
result_GR = tripple.iloc[:,2:7] # 2 ~ 6번째 열 가져옴
result_GR['supply_volume_3y'] = (result_GR.iloc[:,-3:].sum(axis = 1)) / 3 # 마지막 3개 열만 더한다음 나누기
result_GR = result_GR[['jk_code','supply_volume_3y']] # 필요한 칼럼만 남김

# result에 공급물량 추가
result = result.merge(result_GR, on = 'jk_code', how = 'left')
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)


### 76. 공급물량 대비 유효수요 <GS 열>
# 칼럼 타입 변경
result['supply_volume_3y'] = result['supply_volume_3y'].astype(float)
result['effective_demand'] = result['effective_demand'].astype(float)

# result에 공급물량 대비 유효수요 추가
result['effective_demand_to_supply'] = result['supply_volume_3y'] / result['effective_demand']
result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 77. 수급등급 <GT 열>
result['demand_supply_grade'] = np.where(
    result['effective_demand_to_supply'] <= 0.5, 'S',
    np.where(
        result['effective_demand_to_supply'] <= 1.0, 'A',
        np.where(
            result['effective_demand_to_supply'] <= 1.5, 'B',
            'C'
        )
    )
)

result.iloc[:,3:] = round(result.iloc[:,3:] ,2)

### 78. 기준일자 <GU 열>
result['today'] = pd.Timestamp.today().strftime("%Y%m")

# 중복제거
result = result.drop_duplicates()

# effective_demand_to_supply inf 해결
result.loc[result['effective_demand_to_supply'] == np.inf, 'effective_demand_to_supply'] = np.nan

result = result.replace(np.inf, np.nan)
result = result.replace(-np.inf, np.nan)


# 저장 - 1차적으로 완료
today = pd.Timestamp.today().strftime("%Y%m%d")
result.to_excel('GS지역등급_{a}.xlsx'.format(a = today), index = False) # 완료

aa = pd.read_excel(r"C:\Users\USER\Desktop\jw\GS지역등급산출등\202601_GS RIS 지역등급 산출자동화(진행) (1)\gs_지역등급_자동화관련.xlsx", sheet_name = '세부로직')
mapping_dict = aa.set_index('변수명')['구분'].to_dict()

result22 = result.rename(columns=mapping_dict)

result22.to_excel('결과원본_260610.xlsx', index = False)

result22 = pd.read_excel('결과원본_260610.xlsx')

#%%


# 업로드 테이블에 맞게 양식 정리
today = pd.Timestamp.today().strftime("%Y%m%d")
result = pd.read_excel('GS지역등급_{a}.xlsx'.format(a = today), dtype = {'jk_code':'str'})
# result = pd.read_excel('GS지역등급_20260212.xlsx'.format(a = today), dtype = {'jk_code':'str'})

mapping_result = pd.read_excel('매핑.xlsx', dtype = str)
gs_grade = pd.read_csv("GS_ds_grade.csv", dtype = str)


result['jk_code'] = result['jk_code'].astype(str)

# 코드만 가져옴
mapping_result = mapping_result[['jk_code','법정동코드']]
mapping_result.loc[mapping_result['jk_code'].str[:1] == '2','jk_code'] = '0' + mapping_result.loc[mapping_result['jk_code'].str[:1] == '2','jk_code']

# 

# 법정동코드 매핑
result = result.merge(mapping_result, on = 'jk_code', how = 'left')

# 법정동코드 결측값 제거
result = result[result['법정동코드'].notnull()]

# 법정동코드 맨 앞으로
result.insert(0, '법정동코드', result.pop('법정동코드'))

# 법정동코드 5자리 잘라내기
result['법정동코드'] = result['법정동코드'].str[:5]
result_original = result.copy() # 쓰고 지울거임

# 칼럼 이름 변경
result.rename(columns = {'법정동코드':'loc_code', 'demand_supply_grade':'supply_demand_grade' ,'today':'base_date'}, inplace = True)

# 최종파일 result2
result2 = result[['loc_code','general_hh_apt_inc','foreign_hh_apt_inc','demolished_apt_inc','natural_demand','internal_invest_demand','avg_trade_price_y3','multi_homeowner_inc_y3','local_buyer_ratio_y3','internal_invest_demand_3yr_wgt_y3','internal_invest_demand_y1','internal_invest_demand_y2','external_invest_demand','absorbed_supply_y3','nonlocal_buyer_ratio_y3','external_invest_demand_3yr_wgt_y3','external_invest_demand_y1','external_invest_demand_y2','total_invest_demand','new_demand_volume','own_hh_apt_move_demand','py_bprice_y3','bprice_threshold_ratio','income_quintile','own_hh_ratio','own_move_plan_yn','rent_hh_apt_move_demand','rent_hh_ratio','rent_move_plan_yn','nonapt_move_demand','nonapt_hh_ratio','nonapt_move_plan_yn','nonapt_price_adj','total_move_demand','single_and_foreign_hh_inc','single_foreign_own_occ_ratio','multi_hh_and_demolished_hh_inc','multi_demolished_own_occ_ratio','hh_increase_demand','unsold_level_ratio','unsold_level_adj_ratio','total_invest_demand_eff','effective_demand','supply_volume_3y','effective_demand_to_supply','supply_demand_grade','base_date']]
result2 = result2[result2['loc_code'].isin(gs_grade['loc_code'])]
result2.index = range(0, len(result2))

# 칼럼 타입 변경
schema = {
    'loc_code': ('char', 5),
    'general_hh_apt_inc': ('int', None),
    'foreign_hh_apt_inc': ('int', None),
    'demolished_apt_inc': ('int', None),
    'natural_demand': ('int', None),
    'internal_invest_demand': ('int', None),
    'avg_trade_price_y3': ('int', None),
    'multi_homeowner_inc_y3': ('int', None),
    'local_buyer_ratio_y3': ('decimal', 2),
    'internal_invest_demand_3yr_wgt_y3': ('decimal', 2),
    'internal_invest_demand_y1': ('int', None),
    'internal_invest_demand_y2': ('int', None),
    'external_invest_demand': ('int', None),
    'absorbed_supply_y3': ('int', None),
    'nonlocal_buyer_ratio_y3': ('decimal', 2),
    'external_invest_demand_3yr_wgt_y3': ('decimal', 2),
    'external_invest_demand_y1': ('int', None),
    'external_invest_demand_y2': ('int', None),
    'total_invest_demand': ('int', None),
    'new_demand_volume': ('int', None),
    'own_hh_apt_move_demand': ('int', None),
    'py_bprice_y3': ('int', None),
    'bprice_threshold_ratio': ('decimal', 2),
    'income_quintile': ('decimal', 2),
    'own_hh_ratio': ('decimal', 2),
    'own_move_plan_yn': ('decimal', 2),
    'rent_hh_apt_move_demand': ('int', None),
    'rent_hh_ratio': ('decimal', 2),
    'rent_move_plan_yn': ('decimal', 2),
    'nonapt_move_demand': ('int', None),
    'nonapt_hh_ratio': ('decimal', 2),
    'nonapt_move_plan_yn': ('decimal', 2),
    'nonapt_price_adj': ('decimal', 2),
    'total_move_demand': ('int', None),
    'single_and_foreign_hh_inc': ('int', None),
    'single_foreign_own_occ_ratio': ('decimal', 2),
    'multi_hh_and_demolished_hh_inc': ('int', None),
    'multi_demolished_own_occ_ratio': ('decimal', 2),
    'hh_increase_demand': ('int', None),
    'unsold_level_ratio': ('decimal', 2),
    'unsold_level_adj_ratio': ('decimal', 2),
    'total_invest_demand_eff': ('int', None),
    'effective_demand': ('int', None),
    'supply_volume_3y': ('int', None),
    'effective_demand_to_supply': ('decimal', 2),
    'supply_demand_grade': ('char', 1),
    'base_date': ('char', 6),
}

def to_nullable_int(s: pd.Series) -> pd.Series:
    # 숫자 변환 → 소수 있으면 반올림 → NaN 유지 → Int64(Nullable)
    x = pd.to_numeric(s, errors='coerce')
    x = x.round(0)
    return x.astype('Int64')

def to_decimal_2(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors='coerce')
    return x.round(2)

def to_char(s: pd.Series, length: int, zfill: bool = True) -> pd.Series:
    # NaN은 NaN 유지
    x = s.copy()
    mask = x.notna()
    x = x.astype('object')
    x.loc[mask] = x.loc[mask].astype(str).str.strip()
    if zfill:
        x.loc[mask] = x.loc[mask].str.zfill(length)
    x.loc[mask] = x.loc[mask].str[:length]
    return x

for col, (typ, opt) in schema.items():
    if col not in result2.columns:
        # 컬럼이 없다면 스킵(원하면 여기서 에러로 바꿔도 됨)
        continue

    if typ == 'int':
        result2[col] = to_nullable_int(result2[col])

    elif typ == 'decimal':
        result2[col] = to_decimal_2(result2[col])

    elif typ == 'char':
        length = int(opt)
        # loc_code/base_date는 보통 0 padding 필요해서 zfill=True
        # supply_demand_grade는 굳이 zfill 필요 없지만 length=1이니 무해
        zfill = col in ['loc_code', 'base_date']
        result2[col] = to_char(result2[col], length=length, zfill=zfill)


if 'supply_demand_grade' in result2.columns:
    m = result2['supply_demand_grade'].notna()
    result2.loc[m, 'supply_demand_grade'] = (
        result2.loc[m, 'supply_demand_grade'].astype(str).str.strip().str[:1]
    )


# 최종 업로드 파일
result2.to_excel('GS지역등급_업로드_{a}.xlsx'.format(a = today), index = False) # 완료
result2.to_csv('GS지역등급_업로드_{a}.csv'.format(a = today), index = False) # 완료

###########################################
'''r114_gs_ds_grade_income 업로드용 만들어서 upload_r114_gs_ds_grade_income 에 업로드 해야한다.'''
# jk_code 2로 시작하는거 앞에 0 붙여줘야한다
z_idx = soduk_r114_gs_ds_grade_income[soduk_r114_gs_ds_grade_income['jk_code'].str[:1] == '2'].index

# 0 붙여줌
soduk_r114_gs_ds_grade_income.loc[z_idx,'jk_code'] = '0' + soduk_r114_gs_ds_grade_income.loc[z_idx,'jk_code']

# loc_code 붙여줌
soduk_r114_gs_ds_grade_income2 = soduk_r114_gs_ds_grade_income.merge(jiyuk[['jk_code','loc_code']], on = 'jk_code', how = 'left')

# loc_code 안붙은거 제거 - 총 277건이어야함
soduk_r114_gs_ds_grade_income2 = soduk_r114_gs_ds_grade_income2[soduk_r114_gs_ds_grade_income2['loc_code'].notnull()]

# 필요없는 칼럼 drop
soduk_r114_gs_ds_grade_income2.drop(columns = 'jk_code', inplace = True)

# base_date 생성
soduk_r114_gs_ds_grade_income2['base_date'] = '202505'

# 칼럼 순서 조정
soduk_r114_gs_ds_grade_income2.insert(0, 'base_date', soduk_r114_gs_ds_grade_income2.pop('base_date'))
soduk_r114_gs_ds_grade_income2.insert(1, 'loc_code', soduk_r114_gs_ds_grade_income2.pop('loc_code'))


soduk_r114_gs_ds_grade_income2.columns = ['base_date', 'loc_code', 'rate', 'loan_term', 'ltv', 'dti', 'income_15_20m', 'income_20_25m', 'income_25_30m', 'income_30_40m', 'income_40_50m', 'income_50_60m',	'income_60_70m',	'income_70_100m'	,'income_100m_over']

income_cols = [
    'income_15_20m', 'income_20_25m', 'income_25_30m',
    'income_30_40m', 'income_40_50m', 'income_50_60m',
    'income_60_70m', 'income_70_100m', 'income_100m_over'
]

soduk_r114_gs_ds_grade_income2[income_cols] = (
    soduk_r114_gs_ds_grade_income2[income_cols]
    .apply(pd.to_numeric, errors='coerce')
    .astype('Int64')
)

soduk_r114_gs_ds_grade_income2.to_excel('soduk_r114_gs_ds_grade_income2_202605.xlsx', index = False)


##############
##############
##############
import pandas as pd

aa = pd.read_excel(r"C:\Users\USER\Desktop\jw\GS지역등급산출등\202601_GS RIS 지역등급 산출자동화(진행) (1)\gs_지역등급_자동화관련.xlsx", sheet_name = '세부로직')
data1 = pd.read_excel(r"C:\Users\USER\Downloads\결과원본_26051222.xlsx", sheet_name = 0)
data2 = pd.read_excel(r"C:\Users\USER\Downloads\결과원본_26051222.xlsx", sheet_name = 1)

mapping_dict = aa.set_index('변수명')['구분'].to_dict()


data22 = data2.rename(columns=mapping_dict)









