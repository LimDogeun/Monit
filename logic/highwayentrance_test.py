import os
import requests
from dotenv import load_dotenv
# from geopy.distance import geodesic
import math
import folium


# .env에서 API 키 로드
load_dotenv()
REST_API_KEY = os.getenv("KAKAO_API_KEY")

if REST_API_KEY is None:
    raise ValueError("KAKAO_API_KEY가 .env에 설정되어 있지 않습니다.")

# -----------------------------
# 아래는 함수 사용 위해 필요한 함수들 
# -----------------------------
# 주소 -> 위경도 변환
def get_coordinates(address):
    """주소를 위도, 경도로 변환 (결과는 경도, 위도 순서로 반환됨)"""
    url = 'https://dapi.kakao.com/v2/local/search/address.json'
    headers = {'Authorization': f'KakaoAK {REST_API_KEY}'}
    params = {'query': address}

    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    if data['documents']:
        x = float(data['documents'][0]['x'])  # 경도
        y = float(data['documents'][0]['y'])  # 위도
        return float(y), float(x)
    else:
        raise ValueError(f"주소 '{address}'를 찾을 수 없습니다.")
    
# 출발지-도착지 경로 얻기 (kakao API)
def get_route(origin, destination, waypoints=None):
    """
        자동차 길찾기 API
        input : 출발지와 도착지의 (위도, 경도)
        waypoints : 경유지, 리스트로 5개까지 넣을 수 있음!
    """

    url = 'https://apis-navi.kakaomobility.com/v1/directions'
    headers = {'Authorization': f'KakaoAK {REST_API_KEY}'}
    params = {
        'origin': f'{origin[1]},{origin[0]}',
        'destination': f'{destination[1]},{destination[0]}',
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


def haversine(coord1, coord2):
    """두 위경도 좌표 사이 거리 (단위: km)"""
    lon1, lat1, lon2, lat2 = map(math.radians, [coord1[0], coord1[1], coord2[0], coord2[1]])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c  # 지구 반지름 (km)


# -----------------------------
# 함수들
# -----------------------------

# 1. 출발지+도착지 (주소) -> 해당 경로 내 도로들
def roadnames_in_route(origin_address, destination_address):
    '''
    iput: 출발지도로명주소, 도착지도로명주소
    output: 해당 경로 내 도로들 
    '''

    # 주소 -> 위경도 반환 
    origin = get_coordinates(origin_address)
    destination = get_coordinates(destination_address)
    
    # 루트 내의 이름들 모두 반환
    roads = get_route(origin, destination)['routes'][0]['sections'][0]['roads']
    result = set()
    
    for road in roads:
        name = road.get('name', '')
        result.add(name)
    
    return list(result)


# 2. 위경도 -> 고속도로인지 아닌지
# 먼저 위경도로 도로명주소 가져와서 도로명만 추출. 근데 많은 위경도가 도로명주소가 없어서 None값이 반환됨
# 도로명 없는 경우, 주변 6m 지점 뽑아서 거기까지 경로 추출해서 도로 추출 
def is_highway(lat, lon):
    '''
    위경도 -> 해당 위치가 고속도로인지 반환 
    input: (위도, 경도)
    output: Bool (True/False)
    '''
    url = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
    headers = {"Authorization": f"KakaoAK {REST_API_KEY}"}
    params = {"x": lon, "y": lat}

    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    try:
        docs = data.get('documents', [])
        if docs:
            road_address = docs[0].get('road_address')
            # 도로명 있는 경우 
            if road_address:
                name = road_address.get('road_name', '')
                print(f'도로명:{name}')
                if name.endswith('고속도로'): # 고속도로로 끝나면 true
                    return True 
                else: return False

            # 도로명 없는 경우 : 해당 위경도에서 동쪽 6m의 위경도 추출해 길찾기 -> 도로 추출 
            print("도로명 X -> 길찾기 사용해 도로 추출")
            # input 위경도에서 동쪽 6m 위경도 추출
            R = 6378137  # 지구 반지름 (m)
            bearing_rad = math.radians(90)

            new_lat = lat + (6 * math.cos(bearing_rad)) / R * (180 / math.pi)
            new_lon = lon + (6 * math.sin(bearing_rad)) / (R * math.cos(math.radians(lat))) * (180 / math.pi)

            # 길찾기 후 도로명 추출 
            road_name = get_route((lat,lon), (new_lat,new_lon))['routes'][0]['sections'][0]['roads'][0]['name']
            print(f'도로명2:{road_name}')
            
            if road_name.endswith('고속도로'):
                return True
            else: return False
        else: # docs가 비어있는 경우 
            print("도로명 추출 시 에러! : 길찾기 사용")
            # input 위경도에서 동쪽 6m 위경도 추출
            R = 6378137  # 지구 반지름 (m)
            bearing_rad = math.radians(90)

            new_lat = lat + (6 * math.cos(bearing_rad)) / R * (180 / math.pi)
            new_lon = lon + (6 * math.sin(bearing_rad)) / (R * math.cos(math.radians(lat))) * (180 / math.pi)

            # 길찾기 후 도로명 추출 
            road_name = get_route((lat,lon), (new_lat,new_lon))['routes'][0]['sections'][0]['roads'][0]['name']
            print(f'도로명2:{road_name}')
            
            if road_name.endswith('고속도로'):
                return True
            else: return False

    except (KeyError, IndexError) as e:
        print("오류 발생: ", e)
        
        


# 3. 출발지+도착지 -> 고속도로 in, out 지점 (위경도)
def get_highway_inout_points(origin_address, destination_address):
    '''
    출발지+도착지 주소 -> 고속도로 in, out 지점의 위경도
    
    - input: (origin_address, destination_address)
    - output:
        {
        'in': [
            {'도로명': '경부고속도로', 'lat': 37.123, 'lon': 127.456},
            ...
        ],
        'out': [
            {'도로명': '서초대로', 'lat': 37.234, 'lon': 127.567},
            ...
        ]
        }
    '''
    # 위경도 뽑기 
    origin = get_coordinates(origin_address)
    destination = get_coordinates(destination_address)

    # 경로 뽑기 
    route = get_route(origin, destination)
    roads = route['routes'][0]['sections'][0]['roads']

    # 도로명 뽑고 고속도로 진입점 뽑기 
    points = {'in':[], 'out': []}
    prev_is_highway = False 

    for road in roads:
        name = road.get('name', '') # 도로명 뽑기
        vertexes = road.get('vertexes', []) # 여기가 위경도 부분임
        is_highway = name.endswith("고속도로") # 고속도로로 끝나면 고속도로
        
        if len(vertexes)<2:
             continue
        lat,lon = vertexes[1], vertexes[0] # 바뀌는 첫 지점을 진입 지점으로 

        # 고속도로 in
        if is_highway and not prev_is_highway:
            points['in'].append({'도로명':name, 'lat':lat, 'lon':lon})

        if not is_highway and prev_is_highway:
            points['out'].append({'도로명':name, 'lat':lat, 'lon':lon})
        
        # print(name, is_highway, (vertexes[1], vertexes[0]))

        prev_is_highway = is_highway

    return points 


# 4. 경로설정 -> 고속도로인경우 50km마다 위경도 뽑기 , 국도인 경우 5km마다 뽑기 
def extract_variable_interval_points(route_data, road_km=5, highway_km=50):
    """
    경로에서 도로 유형에 따라 5km 또는 50km 간격으로 위경도 좌표 추출
    - input : route데이터(카카오API결과), 도로에서의 간격, 고속도로에서의 간격
    - output : 
        [
            {
                'name': '강남대로',
                'road_type': 'road', # 도로 타입 표시 : road는 일반도로, highway는 고속도로 
                'inout': 'no', # in/out지점 표시 : 둘다 해당 X시 'no' 
                'lat': 37.495438039450185,
                'lon': 127.02893499568054
            }, 
            ...

        ]
    """
    roads = route_data['routes'][0]['sections'][0]['roads']
    extracted = [] # 추출한 죄표 리스트
    accumulated = 0 # 현재까지 누적 거리 km
    next_target = 0 # 다음 추출 대상 거리 
    current_interval = road_km  # 현재 간격 (일반도로로 시작 가정)
    prev_point = None # 직전 좌표
    prev_is_highway = False # 직전 도로가 고속도로였는지 여부

    for road in roads:
        name = road.get('name', '')
        is_highway = True if name.endswith("고속도로") else False
        vertexes = road.get('vertexes', [])

        for i in range(0, len(vertexes) - 2, 2):
            x1, y1 = vertexes[i], vertexes[i + 1]
            x2, y2 = vertexes[i + 2], vertexes[i + 3]
            pt1, pt2 = (x1, y1), (x2, y2)

            # 초기지점 설정 : 첫 좌표에서는 누적거리 계산 안하고 시작점만 결정
            if prev_point is None:
                prev_point = pt1
                next_target = current_interval
                extracted.append({'name':name, 'road_type':'road', 'inout':'no', 'lat':y1,'lon': x1})
                continue
            
            # 거리 누적 및 간격 판별 
            d = haversine(prev_point, pt2) 
            accumulated += d # pt2까지 거리 누적

            # 고속도로 진입지점
            if is_highway and not prev_is_highway:
                extracted.append({'name':name, 'road_type':'highway', 'inout':'in', 'lat':y1,'lon': x1})
                current_interval = highway_km
                next_target = current_interval
                accumulated = 0
            
            # 고속도로 출입지점
            if prev_is_highway and not is_highway:
                extracted.append({'name':name, 'road_type':'road', 'inout':'out', 'lat':y1,'lon': x1})
                current_interval = road_km
                next_target = current_interval
                accumulated = 0

            # 간격마다 추가
            if accumulated >= next_target:
                if is_highway:
                    extracted.append({'name':name, 'road_type':'highway', 'inout':'no', 'lat':pt2[1],'lon': pt2[0]}) 
                else:
                    extracted.append({'name':name, 'road_type':'road', 'inout':'no', 'lat':pt2[1],'lon': pt2[0]}) 
                next_target += current_interval

            prev_point = pt2
            prev_is_highway = is_highway

    return extracted


# -----------------------------
# 아래는 시각화 함수
# -----------------------------
def visualize_route_with_5km(origin, destination, route_data, waypoints=None):
    """
    Folium 지도 위에 경로 + 간격 및 출발/도착지 마커 시각화 : 고속도로 출입은 red, 출구는 blue, 나머지는 purple 
    - input : (출발지위경도, 도착지위경도, route데이터)
    - output : folium 지도
    """
    m = folium.Map(location=[origin[0], origin[1]], zoom_start=14)

    # 출발지, 도착지 마커
    folium.Marker([origin[0], origin[1]], tooltip="출발지", icon=folium.Icon(color='green')).add_to(m)
    folium.Marker([destination[0], destination[1]], tooltip="도착지", icon=folium.Icon(color='red')).add_to(m)

    # 경유지 마커 
    if waypoints:
        for idx, wp in enumerate(waypoints):
            folium.Marker([wp[0], wp[1]], tooltip=f"경유지 {idx+1}", icon=folium.Icon(color='blue')).add_to(m)
    
    # 경로 폴리라인
    sections = route_data['routes'][0]['sections']
    for section in sections:
        for road in section['roads']:
            coords = road['vertexes']
            points = [(coords[i+1], coords[i]) for i in range(0, len(coords), 2)]
            folium.PolyLine(points, color='black', weight=3).add_to(m)

    # Nkm마다 마커
    interval_points = extract_variable_interval_points(route_data)
    # for point in points:
    #     interval_points.append((point.get('lat'), point.get('lon')))

    for i, pt in enumerate(interval_points):
        folium.CircleMarker(
            location=[pt.get('lat'), pt.get('lon')],
            radius=4,  # 점 크기
            color='red' if pt.get('inout') == 'in' else 'blue' if pt.get('inout') == 'out' else 'purple',
            fill=True,
            fill_color='purple',
            fill_opacity=1,
            tooltip=f"{'[진입지점!] 'if pt.get('inout')=='in' else '[출구지점!] 'if pt.get('inout')=='out' else ''} {pt.get('name')}"
        ).add_to(m)
    return m




# -----------------------------
# test
# -----------------------------
def main():
    print("-------test(kakaoAPI는 notion > 개인별조사결과 > 민서에 있음! .env파일 만들어주세용)--------")
    print("1. 출발/도착지 주소, 위경도 정의")

    origin_address = "서울특별시 강남구 역삼동 826-21"
    destination_address = "경남 통영시 충렬로 33"

    origin = get_coordinates(origin_address)
    destination = get_coordinates(destination_address)

    print(f"출발지 주소 : {origin_address}, 위경도: {origin}")
    print(f"도착지 주소 : {destination_address}, 위경도: {destination}")

    print("\n2. 출발지+도착지 (주소) -> 해당 경로 내 도로들 (roadnames_in_route 함수)")
    print(roadnames_in_route(origin_address, destination_address))

    print("\n3. 위경도 -> 고속도로인지 아닌지 (is_highway 함수)")
    print(is_highway(origin[0], origin[1]))

    print("\n4. 출발지+도착지 -> 고속도로 in, out 지점 위경도 (get_highway_inout_points 함수)")
    print(get_highway_inout_points(origin_address, destination_address))
    
    print("\n5. 경로설정 -> 고속도로인경우 50km마다 위경도 뽑기 , 국도인 경우 5km마다 뽑기 (extract_variable_interval_points 함수)")
    route = get_route(origin, destination)
    highway_km = 50
    road_km = 5
    print(extract_variable_interval_points(route,road_km, highway_km))

    print("\n6. 시각화 (visualize_route_with_5km 함수)")
    print("map.html 파일 확인 or ipynb로 확인")
    # 지도 생성
    m = visualize_route_with_5km(origin, destination, route)

    # HTML로 저장
    m.save("map.html")
    



if __name__ == '__main__':
    main()