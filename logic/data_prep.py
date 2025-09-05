import pandas as pd
import numpy as np
import os
from datetime import datetime

def data_load(folder_path='../Database/opendata'):
    '''
    csv 형태로 Database 폴더에 저장된 공공데이터들을 불러오는 함수
    input: 폴더 위치 (기본값은 ../Database/opendata)
    output: 통합된 데이터프레임
    '''

    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"[data_load] 폴더 경로가 존재하지 않습니다: {folder_path}")

    file_list = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
    if not file_list:
        raise ValueError(f"[data_load] 해당 폴더에 CSV 파일이 없습니다: {folder_path}")

    df_list = []

    for file in file_list:
        file_path = os.path.join(folder_path, file)
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig') 
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='euc-kr')  
        if df.empty:
            print(f"[data_load] 경고: {file} 파일이 비어있습니다.")
        else:
            df_list.append(df)

    all_data = pd.concat(df_list, ignore_index=True)
    print(f"[data_load] 총 {len(df_list)}개 파일에서 {len(all_data)}개 행 로드 완료.")
    return all_data

def process_station(group):
    '''
    groupby 할 때 각각의 column별로 어떻게 처리할지를 정의해주는 기준 함수
    input, output은 고려하지 않아도 됨. 다음에 정의된 함수에 포함되어 자동으로 사용됨.
    '''
    result = {}

    # 기본 정보
    result['statNm'] = group['statNm'].iloc[0]
    result['statId'] = group['statId'].iloc[0]
    result['addr'] = group['addr'].iloc[0]
    result['addrDetail'] = group['addrDetail'].iloc[0]
    result['location'] = group['location'].iloc[0]
    result['useTime'] = group['useTime'].iloc[0]
    result['lat'] = group['lat'].iloc[0]
    result['lng'] = group['lng'].iloc[0]
    result['busiId'] = group['busiId'].iloc[0]
    result['bnm'] = group['bnm'].iloc[0]
    result['busiNm'] = group['busiNm'].iloc[0]
    result['busiCall'] = group['busiCall'].iloc[0]

    # 중복 제거한 집합
    result['chgerType'] = ','.join(sorted(group['chgerType'].dropna().astype(str).unique()))
    result['output'] = ','.join(sorted(group['output'].dropna().astype(str).unique()))
    result['method'] = ','.join(sorted(group['method'].dropna().astype(str).unique()))

    # 사용 가능한 충전기 수 (stat == 2)
    result['available_chargers'] = (group['stat'] == 2).sum()
    result['num_chargers'] = len(group)
    result['congestion_ratio'] = 1 - (result['available_chargers'] / result['num_chargers']) \
        if result['num_chargers'] > 0 else np.nan

    # stat → 작동률 (stat in [2, 3])
    num_total = len(group)
    num_working = group['stat'].isin([2, 3]).sum()
    result['working_ratio'] = num_working / num_total if num_total > 0 else np.nan

    # 시간 정보: 가장 최근 시점 (max)
    for col in ['statUpdDt', 'lastTsdt', 'lastTedt', 'nowTsdt']:
        result[col] = pd.to_datetime(group[col], errors='coerce').max()

    # 그대로 유지
    for col in ['zcode', 'zscode', 'kind', 'kindDetail', 'parkingFree',
                'note', 'limitYn', 'limitDetail', 'delYn', 'delDetail',
                'trafficYn', 'year', 'regionName']:
        result[col] = group[col].iloc[0]

    return pd.Series(result)

def preprocess_station_data(
    raw_df,
    remove_deleted=True,
    filter_accessible=True,
    filter_24h=True,
    time_columns=('statUpdDt', 'lastTsdt', 'lastTedt', 'nowTsdt')
):
    '''
    충전기 단위로 나와있는 공공데이터 원본 DataFrame을 받아 충전소 단위로 전처리 및 집계하는 함수

    input:
        raw_df (DataFrame): 원본 데이터
        remove_deleted (bool): 삭제된 충전소 제거 여부
        filter_accessible (bool): 접근 불가 충전소 제거 여부
        filter_24h (bool): 24시간 운영 충전소만 남길지 여부
        time_columns (tuple): datetime으로 변환할 컬럼들

    output: 충전소 단위로 집계된 결과 데이터프레임
    '''

    df = raw_df.copy()

    if remove_deleted:
        df = df[df['delYn'] == 'N']

    if filter_accessible:
        inaccessible_codes = [
    "F001", "F002",                     # 정비소, 서비스센터 (내부 고객 전용 가능성)
    "G001", "G005", "G006",             # 군부대, 오피스텔, 단독주택
    "H001", "H002", "H003", "H004",     # 아파트, 빌라, 사옥, 기숙사
    "H005",                             # 연립주택
    "I007",                             # 수련원
    "J001", "J002"                      # 학교, 교육원
]
        df = df[~df['kindDetail'].isin(inaccessible_codes)]

    if filter_24h:
        df = df[df['useTime'].str.contains('24시간', na=False)]

    for col in time_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format='%Y%m%d%H%M%S', errors='coerce')

    station_df = df.groupby('statId').apply(process_station).reset_index(drop=True)
    return station_df

