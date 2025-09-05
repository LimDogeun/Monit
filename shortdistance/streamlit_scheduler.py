import streamlit as st
import os
import time
import pandas as pd
import json
import google.generativeai as genai
from io import StringIO
import base64
import re

# ─── 페이지 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="통영 여행 일정 생성기",
    page_icon="🏖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS 스타일링 ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1e3a8a;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 2rem;
    }
    .section-header {
        color: #1e40af;
        font-size: 1.3rem;
        font-weight: bold;
        margin-top: 2rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 0.5rem;
    }
    .success-box {
        background-color: #d1fae5;
        border: 1px solid #10b981;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #fef3c7;
        border: 1px solid #f59e0b;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #dbeafe;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ─── 세션 상태 초기화 ────────────────────────────────────────────────────────────
if 'chat_session' not in st.session_state:
    st.session_state.chat_session = None
if 'itinerary_generated' not in st.session_state:
    st.session_state.itinerary_generated = False
if 'current_itinerary' not in st.session_state:
    st.session_state.current_itinerary = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# ─── 헤더 ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🏖️ 통영 여행 일정 생성기</div>', unsafe_allow_html=True)

# ─── 사이드바 설정 ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-header">⚙️ API 설정</div>', unsafe_allow_html=True)
    
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value="AIzaSyCLXeTOs_V8MhOl7ND09gP8uo5Q_t_fYyw",  # 기본값 (실제 사용시 제거 권장)
        help="Google AI Studio에서 발급받은 API 키를 입력하세요"
    )
    
    model_name = st.selectbox(
        "모델 선택",
        ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        index=0
    )
    
    st.markdown('<div class="section-header">📁 CSV 파일 업로드</div>', unsafe_allow_html=True)
    
    food_file = st.file_uploader("모범음식점 리뷰 CSV", type=['csv'], key="food")
    tourist_file = st.file_uploader("관광지 리뷰 CSV", type=['csv'], key="tourist")
    blue_file = st.file_uploader("블루리본 리뷰 CSV", type=['csv'], key="blue")

# ─── 메인 함수들 ────────────────────────────────────────────────────────────────
@st.cache_data
def load_csv_data(uploaded_file):
    """업로드된 CSV 파일을 로드합니다."""
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    return None

def initialize_gemini(api_key, model_name):
    """Gemini API를 초기화합니다."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        return model
    except Exception as e:
        st.error(f"Gemini API 초기화 실패: {e}")
        return None

def build_prompt_content(prefs, df_food, df_tourist, df_blue):
    """프롬프트 내용을 생성합니다."""
    def top5(df, key_col):
        if df is None or df.empty:
            return ["데이터 없음"]
        score_col = next((c for c in df.columns if "Score" in c), None)
        if score_col is None:
            return [f"{r[key_col]}" for _, r in df.head(5).iterrows()]
        top = df.sort_values(score_col, ascending=False).head(5)
        return [f"{r[key_col]} (점수: {r[score_col]})" for _, r in top.iterrows()]

    place_col = "Place" if df_tourist is not None and "Place" in df_tourist.columns else "관광명소"
    
    parts = [
        f"여행 기간: {prefs['duration_days']}일",
        f"관심사: {', '.join(prefs['interest'])}",
        f"예산 수준: {prefs['budget']}",
        f"모빌리티 요구 - 노인 편의: {prefs['mobility_needs']['elderly']}, 휠체어 접근: {prefs['mobility_needs']['wheelchair']}",
        "이동 수단: 전기차",
        "\n[최신 리뷰 상위 5개]\n- 음식점:"
    ] + top5(df_food, "Restaurant") + [
        "\n- 관광지:"
    ] + top5(df_tourist, place_col) + [
        "\n- 블루리본:"
    ] + top5(df_blue, "Restaurant") + [
        "\n일정 작성 시 유의사항:",
        "- 점심 식사는 11:30~14:00 사이에 배치",
        "- 저녁 식사는 18:00~19:30 사이에 배치",
        "\n위 정보를 참고하여, 날짜·시간대별 방문 순서, 추천 이유, 전기차 이동 경로 및 예상 소요 시간을 포함한 JSON 형식의 상세 일정표를 작성해주세요.",
        "JSON 형식 예시: " +
        '[{"index": 숫자, "출발지": "장소명", "출발 시간": "HH:MM", "도착지": "장소명", "도착 시간": "HH:MM", "예상 이동 시간": "X분", "추천 이유": "…"}, …]'
    ]
    return "\n".join(parts)

def create_download_link(content, filename, label):
    """다운로드 링크를 생성합니다."""
    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href

# 주소 매핑 함수 추가
@st.cache_data
def load_address_dict():
    address_dict = {}
    for fname in ["관광지_통영.csv", "모범음식점_통영.csv", "블루리본_통영.csv"]:
        if os.path.exists(fname):
            df = pd.read_csv(fname)
            for _, row in df.iterrows():
                address_dict[str(row["관광지명"]).strip()] = str(row["주소"]).strip()
    return address_dict

# ─── 메인 애플리케이션 ──────────────────────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown('<div class="section-header">🎯 여행 선호사항 입력</div>', unsafe_allow_html=True)
    
    # 여행 선호사항 입력 폼
    with st.form("travel_preferences"):
        col_a, col_b = st.columns(2)
        
        with col_a:
            duration = st.number_input("여행 기간 (일)", min_value=1, max_value=7, value=2)
            budget = st.selectbox("예산 수준", ["낮음", "중간", "높음"], index=1)
        
        with col_b:
            elderly = st.checkbox("노인 편의 시설 필요")
            wheelchair = st.checkbox("휠체어 접근성 필요")
        
        interests = st.text_input(
            "관심사 (콤마로 구분)",
            value="맛집, 관광, 문화체험",
            help="예: 맛집, 관광, 문화체험, 자연경관"
        )
        
        submitted = st.form_submit_button("✈️ 여행 일정 생성", use_container_width=True)

with col2:
    st.markdown('<div class="section-header">📊 업로드 상태</div>', unsafe_allow_html=True)
    
    # 파일 업로드 상태 표시
    files_status = {
        "모범음식점": food_file is not None,
        "관광지": tourist_file is not None,
        "블루리본": blue_file is not None
    }
    
    for name, status in files_status.items():
        if status:
            st.success(f"✅ {name} CSV 업로드됨")
        else:
            st.error(f"❌ {name} CSV 필요")

# ─── 일정 생성 로직 ─────────────────────────────────────────────────────────────
if submitted and api_key:
    if not all(files_status.values()):
        st.error("⚠️ 모든 CSV 파일을 업로드해주세요!")
    else:
        # 사용자 선호사항 저장
        prefs = {
            "duration_days": duration,
            "interest": [s.strip() for s in interests.split(',') if s.strip()],
            "budget": budget,
            "mobility_needs": {"elderly": elderly, "wheelchair": wheelchair}
        }
        
        # 데이터 로드
        df_food = load_csv_data(food_file)
        df_tourist = load_csv_data(tourist_file)
        df_blue = load_csv_data(blue_file)
        
        # Gemini 초기화
        model = initialize_gemini(api_key, model_name)
        
        if model:
            with st.spinner("🤖 AI가 여행 일정을 생성 중입니다..."):
                try:
                    # 채팅 세션 시작
                    chat = model.start_chat()
                    st.session_state.chat_session = chat
                    
                    # 1단계: 일정 생성
                    prompt_itin = build_prompt_content(prefs, df_food, df_tourist, df_blue)
                    resp1 = chat.send_message(prompt_itin)
                    
                    # JSON 파싱
                    raw = resp1.text
                    if raw.startswith("```"):
                        raw = raw.split("\n", 1)[1]
                    if raw.rstrip().endswith("```"):
                        raw = raw.rstrip()[:raw.rstrip().rfind("```")]
                    
                    try:
                        itinerary_json = json.loads(raw.strip())
                        st.session_state.current_itinerary = itinerary_json
                        st.session_state.itinerary_generated = True
                        
                        # 2단계: 예상 경비 계산
                        if itinerary_json:
                            itin_str = json.dumps(itinerary_json, ensure_ascii=False, indent=4)
                            chat.send_message(f"아래는 생성된 여행 일정(JSON)입니다:\n{itin_str}")
                            
                            cost_prompt = (
                                "위 일정 기준으로 2인 여행의 예상 경비를 계산해주세요:\n"
                                "- 인원: 어르신 1명, 보호자 1명(총 2인)\n"
                                "- 숙소: 1박당 60,000원(2박)\n"
                                "- 식사: 점심·저녁 1인당 10,000원(아침 조식 무료)\n"
                                "- 충전비: km당 200원, 총 주행 100km\n"
                                "- 입장료: 통영옻칠박물관 3,000원/인\n"
                                "- 기타 간식·기념품: 예시로 20,000원\n\n"
                                "각 항목별 합산 후 최종 총액을 알려주세요."
                            )
                            cost_resp = chat.send_message(cost_prompt)
                            st.session_state.cost_estimate = cost_resp.text
                        
                        st.success("✅ 여행 일정이 성공적으로 생성되었습니다!")
                        
                    except json.JSONDecodeError:
                        st.warning("⚠️ JSON 파싱에 실패했지만, 텍스트 일정은 생성되었습니다.")
                        st.session_state.raw_itinerary = raw
                        st.session_state.itinerary_generated = True
                        
                except Exception as e:
                    st.error(f"❌ 일정 생성 중 오류가 발생했습니다: {e}")

# ─── 생성된 일정 표시 ───────────────────────────────────────────────────────────
if st.session_state.itinerary_generated:
    st.markdown('<div class="section-header">📅 생성된 여행 일정</div>', unsafe_allow_html=True)

    # 주소 dict 준비
    address_dict = load_address_dict()

    # 탭으로 구분
    tab1, tab2, tab3 = st.tabs(["📋 일정표", "💰 예상 경비", "💬 일정 수정"])

    with tab1:
        if st.session_state.current_itinerary:
            df_schedule = pd.DataFrame(st.session_state.current_itinerary)

            # 추천 이유 컬럼 제거
            if "추천 이유" in df_schedule.columns:
                df_schedule = df_schedule.drop(columns=["추천 이유"])

            # 출발지/도착지에 주소 붙이기
            def add_addr(name):
                name = str(name)
                addr = address_dict.get(name, "")
                return f"{name} ({addr})" if addr else name
            df_schedule["출발지"] = df_schedule["출발지"].apply(add_addr)
            df_schedule["도착지"] = df_schedule["도착지"].apply(add_addr)

            # 시간 흐름에 따라 일차 분리
            def extract_hour_min(time_str):
                match = re.search(r"(\d{1,2}):(\d{2})", str(time_str))
                if match:
                    return int(match.group(1)), int(match.group(2))
                return None, None
            day_list = []
            current_day = 1
            prev_hour, prev_min = None, None
            for i, row in df_schedule.iterrows():
                hour, minute = extract_hour_min(row["출발 시간"])
                if prev_hour is not None and hour is not None:
                    if (hour, minute) < (prev_hour, prev_min):
                        current_day += 1
                day_list.append(current_day)
                if hour is not None:
                    prev_hour, prev_min = hour, minute
            df_schedule["일차"] = day_list

            # 일자별로 표 출력
            for day in sorted(df_schedule["일차"].unique()):
                st.markdown(f"#### {day}일차 일정")
                st.dataframe(df_schedule[df_schedule["일차"]==day].drop(columns=["일차"]).reset_index(drop=True), use_container_width=True)

            # 다운로드 버튼 (전체 일정)
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                json_str = json.dumps(st.session_state.current_itinerary, ensure_ascii=False, indent=4)
                st.download_button(
                    "📄 JSON 파일 다운로드",
                    json_str,
                    f"여행일정_{time.strftime('%Y%m%d_%H%M%S')}.json",
                    "application/json"
                )
            with col_dl2:
                csv_str = df_schedule.drop(columns=["일차"]).to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    "📊 CSV 파일 다운로드",
                    csv_str,
                    f"여행일정_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv"
                )
        elif hasattr(st.session_state, 'raw_itinerary'):
            st.text_area("생성된 일정 (텍스트)", st.session_state.raw_itinerary, height=400)
    
    with tab2:
        if hasattr(st.session_state, 'cost_estimate'):
            st.markdown('<div class="info-box">', unsafe_allow_html=True)
            st.write(st.session_state.cost_estimate)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("예상 경비 정보가 없습니다.")
    
    with tab3:
        st.markdown("💡 **일정 수정 방법**: 아래에 수정하고 싶은 내용을 입력하세요.")
        st.markdown("예: '첫째 날 점심을 다른 음식점으로 바꿔주세요', '관광지 방문 시간을 늘려주세요' 등")
        
        # 채팅 히스토리 표시
        for message in st.session_state.chat_history:
            if message['role'] == 'user':
                st.markdown(f"**👤 사용자**: {message['content']}")
            else:
                st.markdown(f"**🤖 AI**: {message['content']}")
        
        # 새로운 메시지 입력
        user_message = st.text_input("수정 요청사항을 입력하세요:", key="edit_message")
        
        col_send, col_finish = st.columns([1, 1])
        
        with col_send:
            if st.button("💬 전송", use_container_width=True) and user_message:
                if st.session_state.chat_session:
                    try:
                        response = st.session_state.chat_session.send_message(user_message)
                        
                        # 채팅 히스토리에 추가
                        st.session_state.chat_history.append({
                            'role': 'user',
                            'content': user_message
                        })
                        st.session_state.chat_history.append({
                            'role': 'assistant',
                            'content': response.text
                        })
                        
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"메시지 전송 실패: {e}")
        
        with col_finish:
            if st.button("✅ 수정 완료", use_container_width=True):
                if st.session_state.chat_session:
                    try:
                        final_prompt = "수정된 최종 일정 JSON만 ```json … ``` 형태로 다시 출력해주세요."
                        final_resp = st.session_state.chat_session.send_message(final_prompt)
                        
                        # JSON 파싱
                        raw2 = final_resp.text
                        if raw2.startswith("```"):
                            raw2 = raw2.split("\n", 1)[1]
                        if raw2.rstrip().endswith("```"):
                            raw2 = raw2.rstrip()[:raw2.rstrip().rfind("```")]
                        
                        try:
                            final_json = json.loads(raw2.strip())
                            st.session_state.current_itinerary = final_json
                            st.success("✅ 일정이 업데이트되었습니다!")
                            st.rerun()
                        except json.JSONDecodeError:
                            st.error("최종 일정 파싱에 실패했습니다.")
                            
                    except Exception as e:
                        st.error(f"최종 일정 생성 실패: {e}")

# ─── 푸터 ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #6b7280; font-size: 0.9rem;'>
        🏖️ 통영 여행 일정 생성기 | Powered by Google Gemini AI
    </div>
    """,
    unsafe_allow_html=True
)