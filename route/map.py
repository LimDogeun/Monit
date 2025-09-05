# -------------------------------------
# 지도 시각화
# -------------------------------------
def generate_map(route_coords, sampled_coords, stations=None): 
    print("-----generate_map함수------")
    print(f"route_coords 타입: {type(route_coords)}, 길이: {len(route_coords)}")
    print(f"sampled_coords 타입: {type(sampled_coords)}, 길이: {len(sampled_coords)}")

    # route_coords가 dict라서 경로 좌표로 파싱해줌
    if isinstance(route_coords, dict) and 'routes' in route_coords:
        extracted_coords = []
        for section in route_coords['routes'][0]['sections']:
            for road in section['roads']:
                vertexes = road['vertexes']
                for i in range(0, len(vertexes), 2):
                    lon = vertexes[i]
                    lat = vertexes[i + 1]
                    extracted_coords.append((lat, lon))
        route_coords = extracted_coords

    if not route_coords:
        raise ValueError("route_coords가 비어 있습니다.")
    
    center = route_coords[len(route_coords)//2]
    m = folium.Map(location=center, zoom_start=12)

    # 경로 선
    folium.PolyLine(route_coords, color="blue", weight=4, tooltip="경로").add_to(m)

    # 샘플 지점 마커
    for lon, lat in sampled_coords:
        folium.CircleMarker([lat, lon], radius=5, color="orange", fill=True, fill_opacity=0.7, popup="샘플 지점").add_to(m)

    # 충전소 마커
    if stations is not None and not stations.empty:
        for _, row in stations.iterrows():
            folium.Marker(
                location=[row["위도"], row["경도"]],
                popup=row["이름"],
                icon=folium.Icon(color="blue", icon="bolt", prefix="fa")
            ).add_to(m)
   
    return m