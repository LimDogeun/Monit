import math, folium
from math import radians, sin, cos, asin, sqrt
import streamlit as st

# --- 위경도 좌표 사이 거리 ──────────────────────────────
def haversine(coord1, coord2):
    """두 위경도 좌표 사이 거리 (단위: km)"""
    # 사용자의 코드에 맞춰 (lat, lon) 순서의 입력을 처리하도록 수정
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c


# --- 경로설정 -> 고속도로인경우 50km마다 위경도 뽑기 , 국도인 경우 5km마다 뽑기 ──────────────────────────────
@st.cache_data
def extract_variable_interval_points(route_data, road_km=5, highway_km=30):
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
    if not route_data or not route_data.get('routes'): return []
    
    all_roads = []
    for section in route_data['routes'][0].get('sections', []):
        all_roads.extend(section.get('roads', []))
    if not all_roads: return []
    
    extracted, accumulated, prev_point, prev_is_highway = [], 0, None, False

    # 시작점 설정
    first_road_vertexes = all_roads[0].get('vertexes', [])
    if len(first_road_vertexes) >= 2:
        y1, x1 = first_road_vertexes[1], first_road_vertexes[0]
        # haversine 함수 입력 형식에 맞게 (lat, lon) 저장
        prev_point = (y1, x1) 
        extracted.append({'name': all_roads[0].get('name', ''), 'road_type':'start', 'inout':'no', 'lat':y1,'lon': x1})

    for road in all_roads:
        name = road.get('name', '')
        is_highway = "고속도로" in name
        vertexes = road.get('vertexes', [])
        
        current_interval = highway_km if is_highway else road_km

        for i in range(0, len(vertexes), 2):
            lon, lat = vertexes[i], vertexes[i + 1]
            if prev_point is None:
                prev_point = (lat, lon)
                continue

            # 도로의 시작점을 진/출입 지점으로 판단 (루프 안으로 이동하여 각 도로 시작점마다 체크)
            if i == 0:
                 if is_highway and not prev_is_highway:
                    extracted.append({'name':name, 'road_type':'highway', 'inout':'in', 'lat':lat,'lon': lon})
                    accumulated = 0
                 elif not is_highway and prev_is_highway:
                    extracted.append({'name':name, 'road_type':'road', 'inout':'out', 'lat':lat,'lon': lon})
                    accumulated = 0
            
            accumulated += haversine(prev_point, (lat, lon))
            
            if accumulated >= current_interval:
                road_type_str = 'highway' if is_highway else 'road'
                extracted.append({'name':name, 'road_type':road_type_str, 'inout':'no', 'lat':lat,'lon': lon}) 
                accumulated = 0
            
            prev_point = (lat, lon)
        prev_is_highway = is_highway
            
    last_road_vertexes = all_roads[-1].get('vertexes', [])
    if len(last_road_vertexes) >= 2:
        y_end, x_end = last_road_vertexes[-1], last_road_vertexes[-2]
        extracted.append({'name': '도착지', 'road_type': 'end', 'inout': 'no', 'lat': y_end, 'lon': x_end})
    return extracted


# --- 지도 시각화 ──────────────────────────────
def visualize_map(origin_coord, destination_coord, waypoints_coords, route_data, interval_points=None, recommended_stations=None):
    """
    Folium 지도 위에 경로 + 간격 및 출발/도착지 마커 시각화 
    • 출발지(녹색깃발), 도착지(빨강깃발)
    • 경유지(주황 깃발)
    • 고속도로 출입(빨강점)
    • 고속도로 출구(파랑점)
    • 기타 Nkm간격 지점 (보라점)
    • 전체 경로(파랑 선)
    - input : (출발지위경도, 도착지위경도, route데이터)
    - output : folium 지도
    """
    map_center = [origin_coord[0], origin_coord[1]]
    m = folium.Map(location=map_center, zoom_start=13)

    # 출발, 도착지 마커
    folium.Marker(origin_coord, tooltip="출발지", icon=folium.Icon(color='green', icon='play')).add_to(m)
    folium.Marker(destination_coord, tooltip="도착지", icon=folium.Icon(color='red', icon='stop')).add_to(m)
    
    # 경유지 마커
    if waypoints_coords:
        for i, wp_coord in enumerate(waypoints_coords):
            folium.Marker(
                wp_coord,
                tooltip=f"경유지 {i+1}",
                icon=folium.Icon(color='orange', icon='star')
            ).add_to(m)

    if route_data and route_data.get('routes'):
        for section in route_data['routes'][0].get('sections', []):
            for road in section.get('roads', []):
                coords = road.get('vertexes', [])
                points = [(coords[i+1], coords[i]) for i in range(0, len(coords), 2)]
                folium.PolyLine(points, color='blue', weight=5, opacity=0.7).add_to(m)

    if interval_points:
        for pt in interval_points:
            lat, lon, name, inout = pt.get('lat'), pt.get('lon'), pt.get('name', ''), pt.get('inout')
            color, radius, tooltip_text = 'purple', 5, f"{name}"
            if inout == 'in': color, radius, tooltip_text = 'red', 7, f"[고속도로 진입] {name}"
            elif inout == 'out': color, radius, tooltip_text = 'blue', 7, f"[고속도로 출구] {name}"
            
            if pt.get('road_type') not in ['start', 'end']:
                folium.CircleMarker(location=[lat, lon], radius=radius, color=color, fill=True, fill_color=color, fill_opacity=0.8, tooltip=tooltip_text).add_to(m)

    # --- 최종 추천 충전소 마커 ---
    if recommended_stations is not None and not recommended_stations.empty:
        for _, station in recommended_stations.iterrows():
            # 툴팁에 표시할 정보들을 HTML 형식으로 예쁘게 구성
            parking_info = "무료" if station.get('parkingFree') == 'Y' else "유료/정보없음"
            limit_info = station.get('limitDetail', '정보없음') if station.get('limitYn') == 'Y' else "없음"
            
            tooltip_html = f"""
            <b>{station.get('statNm', '이름 정보 없음')}</b><br>
            --------------------<br>
            주소: {station.get('addr', '')}<br>
            운영: {station.get('busiNm', '')} ({station.get('busiCall', '')})<br>
            타입: {station.get('chgerType', '')}<br>
            용량(kW): {station.get('output', '')}<br>
            이용 시간: {station.get('useTime', '24시간')}<br>
            주차비: {parking_info}<br>
            이용 제한: {limit_info}
            """
            
            folium.CircleMarker(
                location=[station['lat'], station['lng']],
                radius=7,
                color='deeppink',
                fill=True,
                fill_color='pink',
                fill_opacity=0.8,
                tooltip=tooltip_html
            ).add_to(m)
    return m