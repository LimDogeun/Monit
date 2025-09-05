# kakao_api.py

import os
import requests
from dotenv import load_dotenv
from geopy.distance import geodesic

# .env에서 API 키 로드
load_dotenv()
REST_API_KEY = os.getenv("KAKAO_API_KEY")

if REST_API_KEY is None:
    raise ValueError("KAKAO_API_KEY가 .env에 설정되어 있지 않습니다.")

# -----------------------------
# 1. 주소 → 위경도 변환 함수
# -----------------------------
def get_coordinates(address):
    """주소를 위도, 경도로 변환 (결과는 경도, 위도 순서로 반환됨)"""

    print("-----get_coordinates함수------")
    url = 'https://dapi.kakao.com/v2/local/search/address.json'
    headers = {'Authorization': f'KakaoAK {REST_API_KEY}'}
    params = {'query': address}

    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    if data['documents']:
        x = float(data['documents'][0]['x'])  # 경도
        y = float(data['documents'][0]['y'])  # 위도
        print(f"get_coordinates 위경도 : {x}, {y}")
        return float(x), float(y)
    else:
        raise ValueError(f"주소 '{address}'를 찾을 수 없습니다.")

# -----------------------------
# 2. 출발지-도착지 경로 얻기
# -----------------------------
def get_route(origin, destination, waypoints=None):
    """
        자동차 길찾기 API
        waypoints : 경유지, 리스트로 5개까지 넣을 수 있음!
    """

    print("-----get_route함수------")

    url = 'https://apis-navi.kakaomobility.com/v1/directions'
    headers = {'Authorization': f'KakaoAK {REST_API_KEY}'}
    params = {
        'origin': f'{origin[0]},{origin[1]}',
        'destination': f'{destination[0]},{destination[1]}',
        'priority': "RECOMMEND",
        # 'road_details' : 'true',
    }

    if waypoints:
        # 경유지를 "x,y" 형식의 문자열 리스트로 변환 
        waypoints_str = [f"{wp[0]},{wp[1]}" for wp in waypoints]
        params['waypoints'] = waypoints_str
        
    response = requests.get(url, headers=headers, params=params)
    result = response.json()
    
    return result

# def get_route(origin_coord, dest_coord, waypoints=None):
#     """
#     Kakao 자동차 길찾기 API를 이용해 경로 좌표 반환
#     origin_coord, dest_coord: (lat, lon)
#     반환: [(lat1, lon1), (lat2, lon2), ...]
#     """

#     print("-----get_route함수------")
#     url = 'https://apis-navi.kakaomobility.com/v1/directions'
#     headers = {'Authorization': f'KakaoAK {REST_API_KEY}'}

#     params = {
#         'origin': f'{origin_coord[1]},{origin_coord[0]}',  # x,y = lon,lat
#         'destination': f'{dest_coord[1]},{dest_coord[0]}',
#         'priority': 'RECOMMEND'
#     }

#     if waypoints:
#         waypoints_str = [f"{wp[1]},{wp[0]}" for wp in waypoints]
#         params['waypoints'] = '|'.join(waypoints_str)

#     response = requests.get(url, headers=headers, params=params)
#     data = response.json()

#     if 'routes' not in data:
#         raise ValueError("경로 데이터를 가져오는 데 실패했습니다.")

#     # 좌표 추출
#     coords = []
#     for section in data['routes'][0]['sections']:
#         for road in section['roads']:
#             for vertex in road['vertexes']:
#                 # vertexes: [lon1, lat1, lon2, lat2, ...]
#                 for i in range(0, len(road['vertexes']), 2):
#                     lon = road['vertexes'][i]
#                     lat = road['vertexes'][i + 1]
#                     coords.append((lat, lon))

#     return coords

from geopy.distance import geodesic

# -----------------------------
# 3. Nkm마다 경로 샘플링 함수
# -----------------------------
from math import radians, cos, sin, asin, sqrt
def haversine(coord1, coord2):
    """두 위경도 좌표 사이 거리 (단위: km)"""
    lon1, lat1, lon2, lat2 = map(radians, [coord1[0], coord1[1], coord2[0], coord2[1]])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c

def sample_route_points(route_data, interval_km=5):
    """경로 데이터에서 5km마다 좌표 추출"""

    print("------sample_route_points함수------")
    coords = []
    for section in route_data['routes'][0]['sections']:
        for road in section['roads']:
            vertexes = road['vertexes']
            for i in range(0, len(vertexes) - 2, 2):
                x1, y1 = vertexes[i], vertexes[i+1]
                x2, y2 = vertexes[i+2], vertexes[i+3]
                coords.append(((x1, y1), (x2, y2)))

    full_path = [coords[0][0]]
    for segment in coords:
        full_path.append(segment[1])

    extracted = []
    accumulated = 0
    next_target = interval_km

    for i in range(1, len(full_path)):
        d = haversine(full_path[i-1], full_path[i])
        accumulated += d

        if accumulated >= next_target:
            extracted.append(full_path[i])
            next_target += interval_km

    print(extracted)
    return extracted

def get_route_info(origin, destination, waypoints=None):
    """
    자동차 길찾기 API를 통해 경로 정보를 가져옵니다.
    
    Args:
        origin (tuple): 출발지 (위도, 경도)
        destination (tuple): 도착지 (위도, 경도)
        waypoints (list, optional): 경유지 리스트 [(위도1, 경도1), (위도2, 경도2), ...]
    
    Returns:
        dict: {
            'total_distance': float,  # 총 거리 (km)
            'total_duration': int,    # 총 소요시간 (분)
            'route_coords': list,     # 경로 좌표 리스트 [(위도1, 경도1), (위도2, 경도2), ...]
            'road_details': list      # 도로별 상세 정보 리스트
        }
    """
    print("-----get_route_info함수------")
    
    url = 'https://apis-navi.kakaomobility.com/v1/directions'
    headers = {'Authorization': f'KakaoAK {REST_API_KEY}'}
    params = {
        'origin': f'{origin[0]},{origin[1]}',
        'destination': f'{destination[0]},{destination[1]}',
        'priority': "RECOMMEND",
    }

    if waypoints:
        waypoints_str = [f"{wp[1]},{wp[0]}" for wp in waypoints]
        params['waypoints'] = waypoints_str
        
    response = requests.get(url, headers=headers, params=params)
    result = response.json()
    
    if 'routes' not in result or not result['routes']:
        raise ValueError("경로를 찾을 수 없습니다.")
    
    route = result['routes'][0]
    summary = route['summary']
    
    # 총 거리와 소요시간
    total_distance = summary['distance'] / 1000  # m -> km 변환
    total_duration = summary['duration'] // 60   # 초 -> 분 변환
    
    # 경로 좌표 추출
    route_coords = []
    road_details = []
    
    for section in route['sections']:
        for road in section['roads']:
            # 도로별 상세 정보
            road_info = {
                'name': road['name'],
                'distance': road['distance'] / 1000,  # m -> km
                'duration': road['duration'] // 60,    # 초 -> 분
                'traffic_speed': road.get('traffic_speed', 0),
                'traffic_state': road.get('traffic_state', 0)
            }
            road_details.append(road_info)
            
            # 좌표 추출
            vertexes = road['vertexes']
            for i in range(0, len(vertexes), 2):
                lon = vertexes[i]
                lat = vertexes[i + 1]
                route_coords.append((lat, lon))
    
    return {
        'total_distance': total_distance,
        'total_duration': total_duration,
        'route_coords': route_coords,
        'road_details': road_details
    }
