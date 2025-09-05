# utils/geocode.py

import os, requests
from functools import lru_cache
from dotenv import load_dotenv

# --- 키워드 기반 장소 자동완성 함수 ──────────────────────────────
def kakao_keyword_search(query, KAKAO_API_KEY, size=10):
    """카카오 키워드 장소 검색 API로 자동완성 추천 리스트 반환"""
    url = 'https://dapi.kakao.com/v2/local/search/keyword.json'
    headers = {'Authorization': f'KakaoAK {KAKAO_API_KEY}'}
    params = {'query': query, 'size': size}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json().get('documents', [])
    else:
        return []
    
# --- 주소 -> 위경도 변환 ──────────────────────────────
def get_coordinates(address, KAKAO_API_KEY):
    """주소를 위도, 경도로 변환"""
    if not KAKAO_API_KEY: return None
    url = 'https://dapi.kakao.com/v2/local/search/address.json'
    headers = {'Authorization': f'KakaoAK {KAKAO_API_KEY}'}
    params = {'query': address}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('documents'):
            return float(data['documents'][0]['y']), float(data['documents'][0]['x']) # 위도 경도순
    except Exception: return None
    return None


# --- 출발지-도착지 경로 얻기 (kakao API) ──────────────────────────────
def get_route(origin, destination, KAKAO_API_KEY, priority="RECOMMEND", waypoints=None):
    """
        자동차 길찾기 API
        input : 출발지와 도착지의 (위도, 경도)
        waypoints : 경유지, 리스트로 5개까지 넣을 수 있음!
    """
    print(priority)
    if not KAKAO_API_KEY: return None
    url = 'https://apis-navi.kakaomobility.com/v1/directions'
    headers = {'Authorization': f'KakaoAK {KAKAO_API_KEY}'}
    params = {
        'origin': f'{origin[1]},{origin[0]}', 
        'destination': f'{destination[1]},{destination[0]}', 
        'priority': priority,
        'avoid': 'ferries' # 페리항로는 경로에서 제외디도록 함
        }
    
    # 경유지 설정 
    if waypoints:
        # 경유지를 "x,y" 형식의 문자열 리스트로 변환 후 '|'로 join
        waypoints_str = '|'.join([f"{wp[1]},{wp[0]}" for wp in waypoints])
        params['waypoints'] = waypoints_str
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        result = response.json()
        if "routes" not in result or not result.get("routes"): return None
        return result
    except Exception: return None