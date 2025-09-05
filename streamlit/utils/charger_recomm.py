# utils/charger_recomm.py
# 충전소 추천 함수
import os
import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st

def stat_filtering(df):
    '''
    1개 이상 사용 가능(stat = 2 or 3)한 충전소만 필터링하는 함수
    input: 전처리를 마친 dataframe
    output: working_ratio(전체 충전기 중 stat = 2 or 3인 충전기의 비율)가 0보다 큰 충전소들의 dataframe
    '''
    return df[df['working_ratio'] > 0]

def recent_filtering(df, hours=48, now=None):
    '''
    현재 시점 기준 48시간 이내에 사용 기록이 있는지 여부 기반 필터링 함수
    input: 
        df: dataframe, 
        hours: 기준 시간(default 48시간), 
        now: 현재 시점을 임의로 부여 / 부여하지 않을 경우 현재 시간 불러와서 처리
    output: 현재 시점 기준 hours 이내에 사용 기록이 있는 충전소 dataframe
    '''
    if now is None:
        now = pd.Timestamp.now()

    # 두 컬럼을 datetime 타입으로 변환 (오류 발생 시 NaT로 처리)
    df['lastTsdt'] = pd.to_datetime(df['lastTsdt'], errors='coerce')
    df['lastTedt'] = pd.to_datetime(df['lastTedt'], errors='coerce')

    # 최근 충전 '시작' 시간과 최근 충전 '종료' 시간 중 더 최근 시간을 기준으로 계산
    max_time = df[['lastTsdt', 'lastTedt']].max(axis=1)

    # 기준 시각에서 `hours` 이전보다 더 늦은 것만 남기기
    return df[max_time >= (now - pd.Timedelta(hours=hours))].copy()


def filtering_first(df, hours=48, now=None):
    '''
    stat, 시간 기준의 1차 필터링 함수
    input: dataframe, hours, now
    output: 1차 필터링을 거친 데이터프레임
    '''
    temp_df = stat_filtering(df)
    result_df = recent_filtering(temp_df, hours, now)
    return result_df

def filter_by_distance_vectorized(df, center, max_distance_km=5):
    '''
    거리 기반 m km 이내의 충전소만 필터링하는 함수
    input: 
        df: dataframe
        centor: (위도, 경도)
        max_distance_km: m km, default = 5 km
    '''
    R = 6371  # 지구 반지름 (단위: km)
    lon1, lat1 = np.radians(center)

    lat2 = np.radians(df['lat'].values)
    lon2 = np.radians(df['lng'].values)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    distances = R * c

    df = df.copy()
    df['distance_km'] = distances  

    return df.loc[distances <= max_distance_km]

def filter_by_user_input(df, 
                         output_values=None, 
                         chger_types=None, 
                         kinds=None, 
                         busi_ids=None):
    '''
    2차 필터링: 사용자 입력 변수 기반 필터링
    input:
        output: 충전 용량(3, 7, 50, 100, 200)
        chgertype: 충전기 커넥터 유형(01:DC차데모,02: AC완속,03: DC차데모+AC3상,04: DC콤보,05: DC차데모+DC콤보, 06: DC차데모+AC3상+DC콤보, 07: AC3상, 08: DC콤보(완속), 09: NACS, 10: DC콤보+NACS)
        kind: 관련 시설 종류(공공시설, 주차시설 등)
        busid: 충전 사업자(GS 칼텍스, 현대자동차 등)
    output:
        2차 필터링이 적용된 데이터프레임 
    '''
    filtered = df.copy()

    if output_values is not None:
        filtered = filtered[filtered['output'].isin(output_values)]
    
    if chger_types is not None:
        filtered = filtered[filtered['chgerType'].astype(str).isin(chger_types)]

    if kinds is not None:
        filtered = filtered[filtered['kind'].isin(kinds)]
    
    if busi_ids is not None:
        filtered = filtered[filtered['busiId'].isin(busi_ids)]

    return filtered

def score_stations(df, k=3):
    '''
    스코어링 함수, top k개 반환
    input: N km 지점마다의 point로부터 m km 이내의 충전소 데이터프레임
    output: 스코어 기반 top k개 dataframe
    '''
    df = df.copy()

    # 미리 전처리된 변수들 기준으로 스코어링에 필요한 이진 변수 생성
    df['is_free_parking'] = df['parkingFree'].apply(lambda x: 1 if x == 'Y' else 0)
    df['has_convenience'] = df['trafficYn'].apply(lambda x: 1 if x == 'Y' else 0)

    # 급속 여부: output 문자열을 쉼표로 구분된 값 중 하나라도 50 이상이면 1
    def is_fast_output(output_str):
        try:
            outputs = [float(o) for o in output_str.split(',') if o.strip().isdigit()]
            return int(any(o >= 50 for o in outputs))
        except:
            return 0

    df['is_fast'] = df['output'].apply(is_fast_output)

    # avg_cost 컬럼이 없으므로 가정
    df['avg_cost'] = 300
    df['inv_cost'] = 1 / (df['avg_cost'] + 1e-6)

    # 가중치 설정
    weights = {
        # 'is_open': 1.0,  # 제외됨
        'is_free_parking': 0.5,
        'working_ratio': 1.0,
        'congestion_ratio': -0.8,
        'inv_cost': 0.8,
        'has_convenience': 0.4,
        'is_fast': 0.4,
        'distance_km': -1.5
    }

    for feature, weight in weights.items():
        if weight >= 0:
            df[feature + '_score'] = df[feature] * weight
        else:
            # 혼잡도나 거리처럼 작을수록 좋은 경우는 (1 - x) * -w
            df[feature + '_score'] = (1 - df[feature]) * (-weight) if 'ratio' in feature else df[feature] * weight

    # 총합 스코어 계산
    score_cols = [col for col in df.columns if col.endswith('_score')]
    df['total_score'] = df[score_cols].sum(axis=1)

    return df.sort_values('total_score', ascending=False).head(k)


def score_highway(df, k=3):
    '''
    스코어링 함수, top k개 반환
    input: N km 지점마다의 point로부터 m km 이내의 충전소 데이터프레임
    output: 스코어 기반 top k개 dataframe
    '''
    df = df.copy()

    # 미리 전처리된 변수들 기준으로 스코어링에 필요한 이진 변수 생성
    df['is_free_parking'] = df['parkingFree'].apply(lambda x: 1 if x == 'Y' else 0)
    df['has_convenience'] = df['trafficYn'].apply(lambda x: 1 if x == 'Y' else 0)

    # 급속 여부: output 문자열을 쉼표로 구분된 값 중 하나라도 50 이상이면 1
    def is_fast_output(output_str):
        try:
            outputs = [float(o) for o in output_str.split(',') if o.strip().isdigit()]
            return int(any(o >= 50 for o in outputs))
        except:
            return 0

    df['is_fast'] = df['output'].apply(is_fast_output)

    # avg_cost 컬럼이 없으므로 가정
    df['avg_cost'] = 300
    df['inv_cost'] = 1 / (df['avg_cost'] + 1e-6)

    # 가중치 설정
    weights = {
        # 'is_open': 1.0,  # 제외됨
        'is_free_parking': 0.5,
        'working_ratio': 1.0,
        'congestion_ratio': -0.8,
        'inv_cost': 0.8,
        'has_convenience': 0.4,
        'is_fast': 0.4,
        'distance_km': -1.5
    }

    for feature, weight in weights.items():
        if weight >= 0:
            df[feature + '_score'] = df[feature] * weight
        else:
            # 혼잡도나 거리처럼 작을수록 좋은 경우는 (1 - x) * -w
            df[feature + '_score'] = (1 - df[feature]) * (-weight) if 'ratio' in feature else df[feature] * weight

    # 총합 스코어 계산
    score_cols = [col for col in df.columns if col.endswith('_score')]
    df['total_score'] = df[score_cols].sum(axis=1)

    return df.sort_values('total_score', ascending=False).head(k)


def score_start(df, k=3):
    '''
    출발(도착) 지점 근처의 스코어링 함수, top k개 반환
    input: N km 지점마다의 point로부터 m km 이내의 충전소 데이터프레임
    output: 스코어 기반 top k개 dataframe
    '''
    df = df.copy()

    # 미리 전처리된 변수들 기준으로 스코어링에 필요한 이진 변수 생성
    df['is_free_parking'] = df['parkingFree'].apply(lambda x: 1 if x == 'Y' else 0)
    df['has_convenience'] = df['trafficYn'].apply(lambda x: 1 if x == 'Y' else 0)

    # 급속 여부: output 문자열을 쉼표로 구분된 값 중 하나라도 50 이상이면 1
    def is_fast_output(output_str):
        try:
            outputs = [float(o) for o in output_str.split(',') if o.strip().isdigit()]
            return int(any(o >= 50 for o in outputs))
        except:
            return 0

    df['is_fast'] = df['output'].apply(is_fast_output)

    # avg_cost 컬럼이 없으므로 가정
    df['avg_cost'] = 300
    df['inv_cost'] = 1 / (df['avg_cost'] + 1e-6)

    # 가중치 설정
    weights = {
        # 'is_open': 1.0,  # 제외됨
        'is_free_parking': 0.5,
        'working_ratio': 1.0,
        'congestion_ratio': -0.8,
        'inv_cost': 0.8,
        'has_convenience': 0.4,
        'is_fast': 0.4,
        'distance_km': -1.5
    }

    for feature, weight in weights.items():
        if weight >= 0:
            df[feature + '_score'] = df[feature] * weight
        else:
            # 혼잡도나 거리처럼 작을수록 좋은 경우는 (1 - x) * -w
            df[feature + '_score'] = (1 - df[feature]) * (-weight) if 'ratio' in feature else df[feature] * weight

    # 총합 스코어 계산
    score_cols = [col for col in df.columns if col.endswith('_score')]
    df['total_score'] = df[score_cols].sum(axis=1)

    return df.sort_values('total_score', ascending=False).head(k) 

def score_inout(df, k=3):
    '''
    고속도로 진출입로 근처의 스코어링 함수, top k개 반환
    input: N km 지점마다의 point로부터 m km 이내의 충전소 데이터프레임
    output: 스코어 기반 top k개 dataframe
    '''
    df = df.copy()

    # 미리 전처리된 변수들 기준으로 스코어링에 필요한 이진 변수 생성
    df['is_free_parking'] = df['parkingFree'].apply(lambda x: 1 if x == 'Y' else 0)
    df['has_convenience'] = df['trafficYn'].apply(lambda x: 1 if x == 'Y' else 0)

    # 급속 여부: output 문자열을 쉼표로 구분된 값 중 하나라도 50 이상이면 1
    def is_fast_output(output_str):
        try:
            outputs = [float(o) for o in output_str.split(',') if o.strip().isdigit()]
            return int(any(o >= 50 for o in outputs))
        except:
            return 0

    df['is_fast'] = df['output'].apply(is_fast_output)

    # avg_cost 컬럼이 없으므로 가정
    df['avg_cost'] = 300
    df['inv_cost'] = 1 / (df['avg_cost'] + 1e-6)

    # 가중치 설정
    weights = {
        # 'is_open': 1.0,  # 제외됨
        'is_free_parking': 0.5,
        'working_ratio': 1.0,
        'congestion_ratio': -0.8,
        'inv_cost': 0.8,
        'has_convenience': 0.4,
        'is_fast': 0.4,
        'distance_km': -10
    }

    for feature, weight in weights.items():
        if weight >= 0:
            df[feature + '_score'] = df[feature] * weight
        else:
            # 혼잡도나 거리처럼 작을수록 좋은 경우는 (1 - x) * -w
            df[feature + '_score'] = (1 - df[feature]) * (-weight) if 'ratio' in feature else df[feature] * weight

    # 총합 스코어 계산
    score_cols = [col for col in df.columns if col.endswith('_score')]
    df['total_score'] = df[score_cols].sum(axis=1)

    return df.sort_values('total_score', ascending=False).head(k)

@st.cache_data
def run_recommendation(
    meta: dict, # dict 추천 중심지점 데이터 
    output_values: list, # 충전용량 (사용자에게받음)
    chger_types: list, # 충전기 커넥터 유형 (사용자에게받음)
    kinds: list, # 관련 시설 종류 (사용자에게받음)
    busi_ids: list, # 충전 사업자 (사용자에게받음)
    data_dir: str,
    max_distance_km: float = 1.0,
    k: int = 5,
    hours: int = 48
):
    print(f"run_recommendation함수! {meta}")
    center = (meta["lon"], meta["lat"])

    file_path = os.path.join(data_dir, "processed_station_data.csv")
    station_df = pd.read_csv(file_path)
    print(f"----------------------station_df: {len(station_df)}----------------------")

    # Step 3: 1차 필터링 (작동 상태 + 최근 사용 여부)
    # filtered_df = filtering_first(station_df, hours=hours, now=pd.Timestamp.now())
    filtered_df = station_df
    print(f"----------------------filtered_df: {len(filtered_df)}----------------------")


    # Step 4: 거리 필터링
    nearby_df = filter_by_distance_vectorized(filtered_df, center, max_distance_km=max_distance_km)
    print(f"----------------------nearby_df: {len(nearby_df)}----------------------")

    user_filtered_df = nearby_df
    print(f"----------------------user_filtered_df: {len(user_filtered_df)}----------------------")


    # user_filtered_df = nearby_df
    # Step 6: 스코어링    
    if meta.get("road_type") == 'highway':
        top_k_df = score_highway(user_filtered_df, k=k)
    elif meta.get("inout") == "in" or meta.get("inout") == "out":
        top_k_df = score_inout(user_filtered_df, k=k)
    else:
        top_k_df = score_stations(user_filtered_df, k=k)

    return top_k_df


@st.cache_data
def load_charger_data(charger_data_path):
    """전체 충전소 데이터를 로드하고 캐싱하는 함수."""
    if not os.path.exists(charger_data_path):
        st.error(f"충전소 데이터 파일을 찾을 수 없습니다: {charger_data_path}")
        return pd.DataFrame()
    return pd.read_csv(charger_data_path)

def find_chargers_in_radius(center_points: list, charger_df: pd.DataFrame, radius: int = 500):
    """
    주어진 경로 좌표 리스트(center_points) 주변 반경(radius) 내의 모든 충전소를 찾습니다.
    
    Args:
        center_points (list): (위도, 경도) 튜플의 리스트.
        charger_df (pd.DataFrame): 미리 로드된 전체 충전소 데이터.
        radius (int): 검색할 반경 (미터 단위).

    Returns:
        pd.DataFrame: 검색된 충전소들의 데이터프레임.
    """
    if charger_df.empty or not center_points:
        return pd.DataFrame()

    radius_km = radius / 1000.0
    
    # 각 경로 지점 주변의 충전소를 찾아서 모두 합칩니다.
    nearby_chargers_list = []
    for center_point in center_points:
        # center_point가 (경도, 위도) 순서일 수 있으므로 (위도, 경도)로 맞춥니다.
        lat, lng = center_point[0], center_point[1]
        nearby_df = filter_by_distance_vectorized(charger_df, center=(lat, lng), max_distance_km=radius_km)
        if not nearby_df.empty:
            nearby_chargers_list.append(nearby_df)
    
    if not nearby_chargers_list:
        return pd.DataFrame()
        
    # 모든 지점에서 찾은 충전소들을 하나로 합치고, 중복을 제거합니다.
    final_df = pd.concat(nearby_chargers_list).drop_duplicates(subset=['statId']).reset_index(drop=True)
    return final_df