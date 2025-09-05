
# main.py 
import os
import sys
import time
import pandas as pd
import json
import google.generativeai as genai
import streamlit as st
from streamlit_folium import st_folium
from dotenv import load_dotenv
import io
import re
import folium
from streamlit_searchbox import st_searchbox

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# utils에서 필요 함수 임포트
from utils.geocode import get_coordinates, get_route, kakao_keyword_search
from utils.map_utils import haversine, extract_variable_interval_points, visualize_map
from utils.ai_planner import build_prompt_content
from utils.charger_recomm import run_recommendation, filter_by_distance_vectorized


# API 키 및 기본 설정
load_dotenv()
KAKAO_API_KEY=""
GEMINI_API_KEY=""

# Streamlit secrets에서 키 로드 (배포용)
if not KAKAO_API_KEY and 'KAKAO_API_KEY' in st.secrets:
    KAKAO_API_KEY = st.secrets.get("KAKAO_API_KEY")
if not GEMINI_API_KEY and 'GEMINI_API_KEY' in st.secrets:
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

# Gemini API 설정
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-2.0-flash"

# 데이터 파일 경로 설정 
BASE_DIR = os.path.join(project_root, "streamlit", "data")
DATA_DIR_REVIEWS = os.path.join(BASE_DIR, "data")
CHARGER_DATA_PATH = os.path.join(BASE_DIR, "processed_station_data.csv")
ADDRESS_DIR = os.path.join(project_root, 'streamlit', "address") 
FOOD_REVIEW_PATH = os.path.join(BASE_DIR, "모범음식점_리뷰_통영.csv")
TOURIST_REVIEW_PATH = os.path.join(BASE_DIR, "관광지_리뷰_통영.csv")
BLUE_RIBBON_PATH = os.path.join(BASE_DIR, "블루리본_리뷰_통영.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# 세션 상태 초기화 
state_defaults = {
    'charger_filters': {"highway_km": 50, "road_km": 5, "outputs": [], "charger_types": [], "kinds": [], "busis": []},
    'route_data': None, 'origin_coord': None, 'destination_coord': None,
    'submitted': False, 'is_long_trip': False, 'show_planner': False,
    'messages': [], 'itinerary_json': None, 'chat': None,
    'priority': "RECOMMEND", 'waypoints_coords': [], 'waypoints': [""],
    'origin_address': "", 'destination_address': ""
}
for key, value in state_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# 행정구역 정리 및 좌표 HARDCORD

HARDCODED_COORDS = {
    "연화도 출렁다리": (34.638979, 128.371600)
}

METROPOLITAN_CITIES = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "제주"]
PROVINCES = ["경기도", "강원도", "충청도", "전라도", "경상도"]

KOREAN_ADMIN_DISTRICTS = {
    "경기도": ["수원시", "성남시", "의정부시", "안양시", "부천시", "광명시", "평택시", "동두천시", "안산시", "고양시", "과천시", "구리시", "남양주시", "오산시", "시흥시", "군포시", "의왕시", "하남시", "용인시", "파주시", "이천시", "안성시", "김포시", "화성시", "광주시", "양주시", "포천시", "여주시", "연천군", "가평군", "양평군"],
    "강원도": ["춘천시", "원주시", "강릉시", "동해시", "태백시", "속초시", "삼척시", "홍천군", "횡성군", "영월군", "평창군", "정선군", "철원군", "화천군", "양구군", "인제군", "고성군", "양양군"],
    "충청도": ["청주시", "충주시", "제천시", "보은군", "옥천군", "영동군", "진천군", "괴산군", "음성군", "단양군", "증평군", "천안시", "공주시", "보령시", "아산시", "서산시", "논산시", "계룡시", "당진시", "금산군", "부여군", "서천군", "청양군", "홍성군", "예산군", "태안군"],
    "전라도": ["전주시", "군산시", "익산시", "정읍시", "남원시", "김제시", "완주군", "진안군", "무주군", "장수군", "임실군", "순창군", "고창군", "부안군", "목포시", "여수시", "순천시", "나주시", "광양시", "담양군", "곡성군", "구례군", "고흥군", "보성군", "화순군", "장흥군", "강진군", "해남군", "영암군", "무안군", "함평군", "영광군", "장성군", "완도군", "진도군", "신안군"],
    "경상도": ["포항시", "경주시", "김천시", "안동시", "구미시", "영주시", "영천시", "상주시", "문경시", "경산시", "군위군", "의성군", "청송군", "영양군", "영덕군", "청도군", "고령군", "성주군", "칠곡군", "예천군", "봉화군", "울진군", "울릉군", "창원시", "진주시", "통영시", "사천시", "김해시", "밀양시", "거제시", "양산시", "의령군", "함안군", "창녕군", "고성군", "남해군", "하동군", "산청군", "함양군", "거창군", "합천군"]
}

# 통영 주소 데이터
@st.cache_data
def load_charger_data(charger_data_path):
    if not os.path.exists(CHARGER_DATA_PATH):
        st.error(f"충전소 데이터 파일을 찾을 수 없습니다: {CHARGER_DATA_PATH}")
        return pd.DataFrame()
    return pd.read_csv(CHARGER_DATA_PATH)

def load_address_files():
    address_files = ["관광지_통영.csv", "모범음식점_통영.csv", "블루리본_통영.csv", "숙박업소_통영.csv", "호텔.csv"]
    all_address_df = []
    for f in address_files:
        path = os.path.join(ADDRESS_DIR, f)
        if os.path.exists(path):
            all_address_df.append(pd.read_csv(path))
    return all_address_df

def find_address_in_local_files(place_name, address_dfs):
    for df in address_dfs:
        if len(df.columns) >= 2:
            name_col = df.columns[0]     
            address_col = df.columns[1]
            match = df[df[name_col].astype(str).str.contains(place_name.strip(), na=False, case=False)]
            
            if not match.empty:
                return match.iloc[0][address_col]
    return None

# 통영 리뷰데이터 로드 함수
@st.cache_data
def load_review_data():
    try:
        return pd.read_csv(FOOD_REVIEW_PATH), pd.read_csv(TOURIST_REVIEW_PATH), pd.read_csv(BLUE_RIBBON_PATH)
    except FileNotFoundError as e:
        st.error(f"리뷰 데이터 로드 실패: {e}. 'data' 폴더 및 하위 파일들을 확인하세요.")
        return None, None, None

# Streamlit 앱 UI
st.set_page_config(page_title="AI 전기차 충전소 추천 & 여행 플래너", layout="wide")
st.title("🚗EV Monit [AI 전기차 충전소 추천 & 여행 플래너]🚗")

# 1단계: 경로 분석 UI 
st.header("1. 경로 탐색")
st.info("아래에 출발지와 도착지를 입력해주세요!")

def search_address_callback(query: str) -> list[str]:
    """st_searchbox를 위한 주소 검색 콜백 함수"""
    if len(query) < 2: return []
    results = kakao_keyword_search(query, KAKAO_API_KEY)
    return [f"{item['place_name']} ({item['address_name']})" for item in results]

def parse_address(selected_value: str) -> str:
    """'(주소)' 형식의 문자열에서 주소 부분만 추출하는 함수"""
    if selected_value and '(' in selected_value:
        return selected_value.split('(')[-1].rstrip(')')
    return selected_value # 괄호가 없는 경우 원본 반환

# # 출발지 자동완성 (폼 바깥)
def search_origin_address(query):
    if len(query) < 2:
        return []
    results = kakao_keyword_search(query,KAKAO_API_KEY)
    return [f"{item['place_name']} ({item['address_name']})" for item in results]

origin_address = st_searchbox(
    search_origin_address,
    key="origin_searchbox",
    placeholder="출발지 주소를 입력하세요"
)

if origin_address:
    origin_address = origin_address.split('(')[-1].rstrip(')')
print(origin_address)

# 도착지 자동완성 (폼 바깥)
def search_dest_address(query):
    if len(query) < 2:
        return []
    results = kakao_keyword_search(query, KAKAO_API_KEY)
    return [f"{item['place_name']} ({item['address_name']})" for item in results]

destination_address = st_searchbox(
    search_dest_address,
    key="dest_searchbox",
    placeholder="도착지 주소를 입력하세요"
)
if destination_address:  
    destination_address = destination_address.split('(')[-1].rstrip(')')
print(destination_address)

cols = st.columns([2.5, 1, 1]) # 너비 비율 조정
with cols[0]:
    st.markdown('<div style="margin-top: 30px;">경유지 추가/삭제:</div>', unsafe_allow_html=True)
with cols[1]:
    if st.button("＋ 추가", key="add_wp_btn", help="새 경유지 입력란 추가", use_container_width=True):
        if len(st.session_state.waypoints) < 3: # 최대 3개로 제한
            st.session_state.waypoints.append("")
        else:
            st.warning("경유지는 최대 3개까지 추가할 수 있습니다.")
        st.rerun()
with cols[2]:
    if st.button("－ 삭제", key="del_wp_btn", help="마지막 경유지 입력란 삭제", use_container_width=True):
        if st.session_state.waypoints:
            st.session_state.waypoints.pop()
        st.rerun()


#     submitted = st.form_submit_button("경로 탐색")
def search_waypoint_address(query: str) -> list[str]:
    """kakao_keyword_search를 호출하여 경유지 목록을 반환하는 콜백 함수"""
    if len(query) < 2:
        return []
    results = kakao_keyword_search(query, KAKAO_API_KEY)
    return [f"{item['place_name']} ({item['address_name']})" for item in results]

# 2) st.form 안: 출발지·경유지 텍스트박스·도착지·라디오·제출 버튼
with st.form("route_form"):

    for i in range(len(st.session_state.waypoints)):
        # 각 경유지마다 고유한 key를 부여합니다 (예: "waypoint_searchbox_0")
        selected_waypoint = st_searchbox(
            search_waypoint_address,
            key=f"waypoint_searchbox_{i}",
            placeholder=f"경유지 {i+1} 주소를 입력하세요",
            default=st.session_state.waypoints[i]  # 이전에 입력한 값 유지
        )
        
        # 사용자가 목록에서 항목을 선택하면, 해당 주소로 값을 업데이트
        if selected_waypoint:
            # "장소명 (주소)" 형식에서 주소 부분만 추출
            address = selected_waypoint.split('(')[-1].rstrip(')')
            st.session_state.waypoints[i] = address

    # 경로 우선순위 및 제출 버튼 (기존과 동일)
    priority = st.radio(
        "경로 탐색 시 우선순위를 설정해주세요!",
        ["추천경로","최단시간","최단경로"],
        horizontal=True
    )
    priority_mapping = {
        "추천경로": "RECOMMEND",
        "최단시간": "FASTEST",
        "최단경로": "SHORTEST"
    }
    submitted = st.form_submit_button("경로 탐색")


if submitted:
    st.session_state.submitted = True
    keys_to_clear = ['route_data', 'origin_coord', 'destination_coord', 'is_long_trip', 'show_planner', 'messages', 'itinerary_json', 'chat', 'priority']
    for key in keys_to_clear:
        if key in st.session_state: del st.session_state[key]
            
    if not origin_address or not destination_address:
        st.warning("출발지와 도착지 주소를 모두 입력해주세요.")
    else:
        with st.spinner("경로를 분석 중입니다..."):
            origin_coord = get_coordinates(origin_address, KAKAO_API_KEY)
            destination_coord = get_coordinates(destination_address, KAKAO_API_KEY)

            # 경유지 처리
            waypoints_coords = []
            for wp_address in st.session_state.waypoints:
                wp_coord = get_coordinates(wp_address, KAKAO_API_KEY)
                if wp_coord:
                    waypoints_coords.append(wp_coord)
                else:
                    st.error(f"경유지 '{wp_address}'의 좌표를 찾을 수 없습니다.")
            st.session_state.waypoints_coords = waypoints_coords
            
            
            if origin_coord and destination_coord:
                st.session_state.origin_coord = origin_coord
                st.session_state.destination_coord = destination_coord
                st.session_state.priority = priority_mapping[priority]
                route_data = get_route(origin_coord, destination_coord, KAKAO_API_KEY, priority=st.session_state.priority,waypoints=st.session_state.waypoints_coords)
                if route_data:
                    st.session_state.route_data = route_data
                    distance_km = route_data['routes'][0]['summary']['distance'] / 1000
                    has_highway = any("고속도로" in r.get('name', '') for s in route_data['routes'][0].get('sections', []) for r in s.get('roads', []))
                    st.session_state.is_long_trip = distance_km > 30 and has_highway
                    print(f"장거리 여부 : {st.session_state.is_long_trip}")

# --- 2단계: 경로 분석 결과 및 공통 기능 표시 ---
if st.session_state.get('route_data'):
    st.header("2. 경로 지도 및 충전소 추천")
    # 변수 초기화
    interval_points = None
    final_recommendations_df = pd.DataFrame()  # 최종 추천 결과 담은 데이터프레임 (NameError방지 위해 여기서 초기화)
    
    # 충전소 추천 기능
    show_recommendations = st.toggle("경로 내 추천 충전소 보기")

    if show_recommendations:
        st.info("충전소 추천을 원하는 간격을 설정해주세요!")
        col1, col2 = st.columns(2)
        with col1:
            highway_km = st.slider("고속도로 간격 (km)", min_value=10, max_value=100, value=50, step=5)
        with col2:
            road_km = st.slider("국도/일반도로 간격 (km)", min_value=1, max_value=20, value=5, step=1)

        st.session_state.charger_filters['highway_km'] = highway_km
        st.session_state.charger_filters['road_km'] = road_km
        
        # --- 충전소 상세 필터 옵션 UI ---
        st.markdown("---")
        st.write("⚙️ 충전소 상세 필터 (선택 사항)")

        # 필터 옵션 정의
        output_options = [3, 7, 50, 100, 200]
        charger_type_mapping = {
            '01': "DC차데모", '02': "AC완속", '03': "DC차데모+AC3상", '04': "DC콤보",
            '05': "DC차데모+DC콤보", '06': "DC차데모+AC3상+DC콤보", '07': "AC3상",
            '08': "DC콤보(완속)", '09': "NACS", '10': "DC콤보+NACS"
        }
        kind_options = ["공공시설", "주차시설", "상업시설", "관광시설", "휴게소", "기타"]
        busi_options = ["환경부", "GS칼텍스", "현대자동차", "기아자동차", "대영채비", "에버온", "차지비", "한국전력"]

        # 2x2 레이아웃으로 필터 배치
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            selected_outputs = st.multiselect(
                "충전 용량 (kW) 선택",
                options=output_options,
                help="원하는 충전 용량을 모두 선택하세요 (예: 50kW, 100kW)."
            )
            selected_kinds = st.multiselect(
                "시설 종류 선택",
                options=kind_options,
                help="충전소가 위치한 시설의 종류를 선택하세요."
            )
        with filter_col2:
            selected_charger_types = st.multiselect(
                "충전기 커넥터 타입 선택",
                options=list(charger_type_mapping.values()),
                help="사용 가능한 충전기 커넥터 타입을 선택하세요."
            )
            selected_busis = st.multiselect(
                "충전 사업자 선택",
                options=busi_options,
                help="선호하는 충전기 운영 사업자를 선택하세요."
            )
        
        # 3단계 : 충전소 추천!! 실행!!!
        with st.spinner('경로상 추천 지점 계산 및 충전소 탐색 중...'):
            interval_points = extract_variable_interval_points(
                st.session_state.route_data, 
                road_km=road_km, 
                highway_km=highway_km
            )

            if interval_points:
                recommended_list = []
                for point in interval_points:
                    if point['road_type'] not in ['start', 'end']: #출발, 도착지 제외 
                        recommended_df = run_recommendation(
                            data_dir=BASE_DIR,
                            meta=point,
                            output_values=selected_outputs,
                            chger_types=selected_charger_types,
                            kinds=selected_kinds,
                            busi_ids=selected_busis,
                            k=3
                        )
                        recommended_list.append(recommended_df)
                if recommended_list:
                    final_recommendations_df = pd.concat(recommended_list, ignore_index=True)
                    print(f"최종추천 : {final_recommendations_df}")
                    
    # 지도 시각화
    final_map = visualize_map(
        st.session_state.origin_coord,
        st.session_state.destination_coord,
        st.session_state.get('waypoints_coords'),
        st.session_state.route_data,
        interval_points,
        recommended_stations=final_recommendations_df
    )
    st_folium(final_map, width='100%', height=600)

    if show_recommendations and interval_points:
        st.write("추천 충전소 목록")
        st.dataframe(pd.DataFrame(final_recommendations_df))
        st.write("추천 지점 목록(추후 충전소팀 코드병합 위해 임시로 출력)")
        st.dataframe(pd.DataFrame(interval_points))
        # print(interval_points)


elif st.session_state.get('submitted'):
    st.error("경로 탐색에 실패했거나 결과가 없습니다. 주소를 다시 확인해주세요.")


# ---───────────────────────────────────────────────────
# 4단계: 장거리 여행 시 AI 플래너 제안 (추가 기능)
# ---───────────────────────────────────────────────────
if st.session_state.get('is_long_trip', False):
    # print("장거리 맞아서 3단계 발동")
    st.header("3. 여행 일정 생성")
    if st.button("🤖AI 여행 플래너 사용하기🤖"):
        st.session_state.show_planner = True
        st.rerun()

# --- AI 여행 플래너 UI -----
if st.session_state.get('show_planner', False):
    with st.form("planner_form"):
        st.write("여행 세부 정보를 입력해주세요.")
        col_a, col_b = st.columns(2)
        col_c, col_d = st.columns(2)

        with col_c:
            province_metro_list = METROPOLITAN_CITIES + PROVINCES
            selected_province_metro = st.selectbox(
                "여행지 (시, 도)",
                province_metro_list,
                index=province_metro_list.index("경상도") # 기본값을 '경상도'로 설정
            )

        with col_d:
            is_metro = selected_province_metro in METROPOLITAN_CITIES
            
            if is_metro:
                # 광역시/특별자치시 선택 시, 시/군 드롭다운 비활성화
                selected_city_county = st.selectbox(
                    "여행지 (시, 군)",
                    [selected_province_metro], # 자기 자신만 옵션으로 표시
                    disabled=True
                )
                dest_city = selected_province_metro
            else:
                # '도' 선택 시, 해당 도에 속한 시/군 목록으로 드롭다운 활성화
                city_county_options = KOREAN_ADMIN_DISTRICTS.get(selected_province_metro, [])
                selected_city_county = st.selectbox(
                    "여행지 (시, 군)",
                    city_county_options,
                    index=city_county_options.index("통영시") if "통영시" in city_county_options else 0 # 기본값을 '통영시'로 설정
                )
                dest_city = selected_city_county

        with col_a: # 첫번째 열 : 여행기간, 예산수준 
            duration = st.number_input("여행 기간(일)", 1, 7, 2)
            
        with col_b: # 두번째 열 : 편의시설 여부 
            elderly = st.checkbox("노인 편의 시설 필요")
            wheelchair = st.checkbox("휠체어 접근성 필요")

        interests = st.multiselect("관심사", ["맛집탐방", "자연경관", "역사/문화", "액티비티", "휴양"], default=["맛집탐방", "자연경관"])
        submitted_planner = st.form_submit_button("✈️ 나만의 여행 일정 생성")

    # 여행정보 제출!!
    if submitted_planner:
            df_food, df_tourist, df_blue = load_review_data()
            with st.spinner("AI가 여행 일정을 생성 중입니다..."):

                st.info(f"선택된 여행지: {dest_city} (현재 일정 생성은 통영 기준으로만 동작합니다.)")
                prefs = {
                    "duration_days": duration, 
                    "interest": interests, 
                    "mobility_needs" : {"elderly": elderly, "wheelchair": wheelchair}
                }

                # 모델 초기화 및 채팅 시작 
                model = genai.GenerativeModel(MODEL_NAME)
                if model: 
                        st.session_state.chat = model.start_chat()
                # 1. 일정 생성 요청 
                prompt = build_prompt_content(prefs, df_food, df_tourist, df_blue)
                response = st.session_state.chat.send_message(prompt)

                try: # 일정 JSON 파싱 
                    json_str = response.text[response.text.find('['):response.text.rfind(']')+1]
                    st.session_state.itinerary_json = json.loads(json_str)

                    # 채팅 기록 초기화 
                    st.session_state.messages = [{"role": "assistant", "content": "여행 일정이 생성되었습니다! 채팅으로 일정을 수정해보세요."}]
                
                except Exception as e:
                    st.error(f"AI 응답에서 일정(JSON) 추출 실패: {e}")
                    st.text_area("Gemini 원본 응답", response.text)

    # (2) 생성된 일정 표시 
    if st.session_state.get('itinerary_json'):
        st.subheader("🗓️ 생성된 여행 일정")
        address_dfs = load_address_files()
        charger_df = load_charger_data(CHARGER_DATA_PATH)

        charger_df = load_charger_data(CHARGER_DATA_PATH)
        tongyeong_chargers = pd.DataFrame() # 빈 데이터프레임으로 초기화
        if charger_df is not None and not charger_df.empty:
        # 'addr' 컬럼이 있는 경우에만 필터링 수행
            if 'addr' in charger_df.columns:
                tongyeong_chargers = charger_df[charger_df['addr'].str.contains("통영시", na=False)].copy()
            else:
                st.warning("'processed_station_data.csv' 파일에 'addr' 컬럼이 없어 충전소 위치를 표시할 수 없습니다.")
    
        tab1, tab2 = st.tabs(["**상세 일정표**", "**일차별 경로 및 주변 충전소**"])
    

        df_schedule = pd.DataFrame(st.session_state.itinerary_json)
        df_display = df_schedule.copy()

        if "time" in df_display.columns and "place" in df_display.columns:  
            planner_origin_full = st.session_state.get('planner_home_address', '알 수 없는 출발지')
            planner_origin = parse_address(planner_origin_full)
            if not df_display.empty:
                df_display.loc[df_display.index[0], '출발지'] = planner_origin
            df_display['출발지'] = df_display['place'].shift(1)
            df_display['도착지'] = df_display['place']
            df_display['출발 시간'] = df_display['time'].apply(lambda x: x.split('-')[0] if isinstance(x, str) and '-' in x else None)
            df_display['도착 시간'] = df_display['time'].apply(lambda x: x.split('-')[1] if isinstance(x, str) and '-' in x else None)
    
        if "출발 시간" in df_display.columns:
            def extract_hour_min(time_str):
                match = re.search(r"(\d{1,2}):(\d{2})", str(time_str))
                return (int(match.group(1)), int(match.group(2))) if match else (None, None)
        
            day_list, current_day, (prev_hour, prev_min) = [], 1, (None, None)
            for _, row in df_display.iterrows():
                hour, minute = extract_hour_min(row["출발 시간"])
                if prev_hour is not None and hour is not None and (hour, minute) < (prev_hour, prev_min):
                    current_day += 1
                day_list.append(current_day)
                if hour is not None: prev_hour, prev_min = hour, minute
            df_display["일차"] = day_list
        elif "day" in df_display.columns:
            df_display["일차"] = df_display["day"]
    
    # --- Tab 1: 생성된 여행 일정 (기존 표) ---
        with tab1:
            for day in sorted(df_display["일차"].unique()):
                st.markdown(f"#### DAY {day}")
                day_df = df_display[df_display["일차"] == day].drop(columns=["일차", "day"], errors='ignore')
                st.dataframe(day_df, use_container_width=True, hide_index=True)
        
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_schedule.to_excel(writer, index=False, sheet_name='여행일정')
                writer.sheets['여행일정'].autofit()
        

    # --- Tab 2: 일정별 경로 (새로운 지도) ---
        with tab2:
            st.markdown("#### 🗺️ 일차별 경로 지도")
        
        # 일차별로 그룹화하여 지도 생성
            for day, day_df in df_display.groupby("일차"):
                st.markdown(f"**DAY {day} 경로**")
            
            # 경로 좌표 리스트 생성
                places_in_order = pd.concat([day_df['출발지'].head(1), day_df['도착지']]).dropna().unique()
                stopover_coords = []
                places_with_coords = []

                with st.spinner(f"{day}일차 경로 좌표를 조회 중..."):
                    for place in places_in_order:
                        place_stripped = place.strip()
                        coord = None
                    
                        if place_stripped in HARDCODED_COORDS:
                            coord = HARDCODED_COORDS[place_stripped]
                        else:
                            # 2. 로컬 파일에서 주소 검색
                            local_address = find_address_in_local_files(place_stripped, address_dfs)
                        # 3. 로컬 주소 또는 장소 이름으로 API 검색 (Fallback)
                            search_query = local_address if local_address else place_stripped
                            coord = get_coordinates(search_query, KAKAO_API_KEY)
                    
                        if coord:
                            stopover_coords.append(coord)
                            places_with_coords.append(place)

                if len(stopover_coords) > 1:
                    # --- ✨✨✨ [수정] 실제 도로 경로 조회 로직 추가 ✨✨✨ ---
                    full_route_path = []
                    with st.spinner(f"{day}일차 실제 도로 경로를 조회하는 중..."):
                        for i in range(len(stopover_coords) - 1):
                            start_node = stopover_coords[i]
                            end_node = stopover_coords[i+1]
                        
                        # 각 경유지 사이의 길찾기 경로 API 호출
                            route_segment_data = get_route(start_node, end_node, KAKAO_API_KEY)
                        
                            if route_segment_data and route_segment_data.get('routes'):
                            # 경로 결과에서 좌표 목록(vertexes) 추출
                                for section in route_segment_data['routes'][0].get('sections', []):
                                    for road in section.get('roads', []):
                                        vertexes = road.get('vertexes', [])
                                        for j in range(0, len(vertexes), 2):
                                            full_route_path.append((vertexes[j+1], vertexes[j]))
                    
                    chargers_nearby_df = pd.DataFrame()
                
                if not charger_df.empty:
                    with st.spinner(f"{day}일차 경유지 주변 충전소를 탐색 중..."):
                        nearby_chargers_list = []
                        for coord in stopover_coords:
                            # 각 경유지(stopover) 반경 500m 내 충전소 검색
                            nearby_df = filter_by_distance_vectorized(charger_df, center=coord, max_distance_km=0.5)
                            if not nearby_df.empty:
                                nearby_chargers_list.append(nearby_df)
                        
                        if nearby_chargers_list:
                            # 검색된 모든 충전소를 합치고 중복 제거
                            chargers_nearby_df = pd.concat(nearby_chargers_list).drop_duplicates(subset=['statId']).reset_index(drop=True)

                # 지도 생성
                    center_coord = stopover_coords[len(stopover_coords) // 2]
                    m = folium.Map(location=center_coord, zoom_start=12)

                    if not tongyeong_chargers.empty:
                        for _, charger in tongyeong_chargers.iterrows():
                            folium.CircleMarker(
                                location=[charger['lat'], charger['lng']],
                                radius=3,
                                color='red',
                                fill=True,
                                fill_color='red',
                                fill_opacity=0.6,
                                popup=charger['statNm'],
                                tooltip="통영시 충전소"
                            ).add_to(m)


                # 각 경유지에 마커 추가 (기존과 동일)
                    for i, (place, coord) in enumerate(zip(places_with_coords, stopover_coords)):
                        folium.Marker(location=coord, popup=f"{i+1}. {place}", tooltip=place).add_to(m)

                # [수정] 직선 대신 실제 도로 경로선 추가
                    if full_route_path:
                        folium.PolyLine(locations=full_route_path, color='blue', weight=5, opacity=0.8).add_to(m)
                
                    st_folium(m, width='100%', height=500, key=f"map_{day}")
                else:
                    st.info(f"{day}일차의 경로를 표시하기에 장소 정보가 충분하지 않습니다.")

                    if not chargers_nearby_df.empty:
                        for _, charger in chargers_nearby_df.iterrows():
                            folium.Marker(
                                location=[charger['lat'], charger['lng']],
                                popup=f"**{charger['statNm']}**\n- 주소: {charger['addr']}",
                                tooltip=charger['statNm'],
                                icon=folium.Icon(color='red', icon='bolt', prefix='fa') # 빨간색 번개 아이콘
                            ).add_to(m)
                
                    st_folium(m, width='100%', height=500, key=f"map_{day}")
            else:
                st.info(f"{day}일차의 경로를 표시하기에 장소 정보가 충분하지 않습니다.")

        # --- (4) 채팅 UI ---
        st.subheader("💬 GEMINI와 함께 일정 수정하기")
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
    
        if user_prompt := st.chat_input("예: '첫째 날 점심을 다른 음식점으로 바꿔주세요' 등"):
        # ... (기존 채팅 로gic)
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"): st.markdown(user_prompt)
        
            with st.chat_message("assistant"):
                with st.spinner("답변 생성 중..."):
                    response = st.session_state.chat.send_message(user_prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    try:
                        if "[" in response.text and "]" in response.text:
                            json_str = response.text[response.text.find('['):response.text.rfind(']')+1]
                            new_itinerary = json.loads(json_str)
                            st.session_state.itinerary_json = new_itinerary
                            st.rerun()
                    except Exception as e:
                        st.warning(f"채팅 응답에서 일정 추출 실패: {e}")