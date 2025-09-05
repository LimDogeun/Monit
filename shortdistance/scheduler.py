import os
import time
import pandas as pd
import json
import google.generativeai as genai

# ─── Gemini API 설정 ──────────────────────────────────────────────────────────
API_KEY    = ""  # 실제 키로 교체
MODEL_NAME = "gemini-2.0-flash"

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(MODEL_NAME)
# ────────────────────────────────────────────────────────────────────────────────

# ─── CSV 경로 ──────────────────────────────────────────────────────────────────
FOOD_REVIEW_PATH    = "C:/Users/lgsc0/Desktop/Monit/모범음식점_리뷰_통영.csv"
TOURIST_REVIEW_PATH = "C:/Users/lgsc0/Desktop/Monit/관광지_리뷰_통영.csv"
BLUE_RIBBON_PATH    = "C:/Users/lgsc0/Desktop/Monit/블루리본_리뷰_통영.csv"
OUTPUT_DIR          = "C:/Users/lgsc0/Desktop/Monit"
os.makedirs(OUTPUT_DIR, exist_ok=True)
# ────────────────────────────────────────────────────────────────────────────────

def build_prompt_content(prefs, df_food, df_tourist, df_blue):
    def top5(df, key_col):
        score_col = next((c for c in df.columns if "Score" in c), None)
        top = df.sort_values(score_col, ascending=False).head(5)
        return [f"{r[key_col]} (점수: {r[score_col]})" for _, r in top.iterrows()]

    place_col = "Place" if "Place" in df_tourist.columns else "관광명소"
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
        "\n위 정보를 참고하여, 날짜·시간대별 방문 순서, 추천 이유, 전기차 이동 경로 및 예상 소요 시간을 포함한 JSON 형식의 상세 일정표를 작성해주세요.",
        "JSON 형식 예시: " +
        '[{"index": 숫자, "출발지": "장소명", "출발 시간": "HH:MM", "도착지": "장소명", "도착 시간": "HH:MM", "예상 이동 시간": "X분", "추천 이유": "…"}, …]'
    ]
    return "\n".join(parts)

def scheduler_flow(prefs):
    # 1) 데이터 로드
    df_food    = pd.read_csv(FOOD_REVIEW_PATH)
    df_tourist = pd.read_csv(TOURIST_REVIEW_PATH)
    df_blue    = pd.read_csv(BLUE_RIBBON_PATH)

    # 2) 채팅 세션 시작
    chat = model.start_chat()

    # ─── 1단계: 일정 생성 ─────────────────────────────────────────────────────────
    prompt_itin = build_prompt_content(prefs, df_food, df_tourist, df_blue)
    resp1 = chat.send_message(prompt_itin)

    # JSON 파싱 전처리 (```json … ``` 제거)
    raw = resp1.text
    if raw.startswith("```"):
        raw = raw.split("\n",1)[1]
    if raw.rstrip().endswith("```"):
        raw = raw.rstrip()[:raw.rstrip().rfind("```")]
    itinerary_json = None
    try:
        itinerary_json = json.loads(raw.strip())
        # JSON 파일 저장
        fn_j = f"여행_일정_{time.strftime('%Y%m%d_%H%M%S')}.json"
        fp_j = os.path.join(OUTPUT_DIR, fn_j)
        with open(fp_j, 'w', encoding='utf-8') as f:
            json.dump(itinerary_json, f, ensure_ascii=False, indent=4)
        print(f"✅ JSON 일정 파일 생성: {fp_j}")
    except Exception as e:
        print("⚠️ 일정 JSON 파싱 실패:", e)
        itinerary_json = None

    # 텍스트 일정 저장
    fn_t = f"여행_일정_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    fp_t = os.path.join(OUTPUT_DIR, fn_t)
    with open(fp_t, 'w', encoding='utf-8') as f:
        f.write(resp1.text)
    print(f"✅ 텍스트 일정 파일 생성: {fp_t}")

    # ─── 2단계: 예상 경비 계산 ──────────────────────────────────────────────────────
    if itinerary_json:
        # JSON 문자열로 채팅에 올려주기
        itin_str = json.dumps(itinerary_json, ensure_ascii=False, indent=4)
        chat.send_message(f"아래는 생성된 여행 일정(JSON)입니다:\n{itin_str}")

        # 렌트 비용 제외한 경비 요청
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
        resp2 = chat.send_message(cost_prompt)
        print("\n=== 예상 경비 ===")
        print(resp2.text)
    else:
        print("⚠️ 일정 데이터가 없어서 경비 계산을 생략합니다.")

    # ─── 3단계: 사용자가 '종료' 입력할 때까지 편집 지원 ─────────────────────────────
    print("\n💬 여행 일정 편집을 시작합니다. 수정/보완할 부분을 말씀해주세요.")
    print("   (편집이 완료되면, 입력창에 '종료'를 입력하세요.)")
    while True:
        user_input = input("▶ 사용자: ")
        if user_input.strip() == '종료':
            break
        resp = chat.send_message(user_input)
        print(f"▶ Gemini: {resp.text}")

    # ─── 4단계: 최종 JSON 받아서 저장 ───────────────────────────────────────────────
    final_prompt = "수정된 최종 일정 JSON만 ```json … ``` 형태로 다시 출력해주세요."
    final_resp = chat.send_message(final_prompt)
    raw2 = final_resp.text
    if raw2.startswith("```"):
        raw2 = raw2.split("\n",1)[1]
    if raw2.rstrip().endswith("```"):
        raw2 = raw2.rstrip()[:raw2.rstrip().rfind("```")]
    try:
        final_json = json.loads(raw2.strip())
        fn2 = f"최종_여행_일정_{time.strftime('%Y%m%d_%H%M%S')}.json"
        fp2 = os.path.join(OUTPUT_DIR, fn2)
        with open(fp2, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, ensure_ascii=False, indent=4)
        print(f"✅ 최종 JSON 일정 파일 생성: {fp2}")

        # .txt에도 마지막 JSON 형태 또는 사람이 읽기 좋은 형태로 저장
        fn2t = f"최종_여행_일정_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        fp2t = os.path.join(OUTPUT_DIR, fn2t)
        with open(fp2t, 'w', encoding='utf-8') as f:
            f.write(json.dumps(final_json, ensure_ascii=False, indent=4))
        print(f"✅ 최종 TXT 일정 파일 생성: {fp2t}")

    except Exception as e:
        print("⚠️ 최종 일정 JSON 파싱/저장 실패:", e)
        print("원본 응답:\n", raw2)


if __name__ == "__main__":
    duration   = int(input("▶ 여행 기간(일): "))
    interests  = input("▶ 관심사 (콤마 구분): ")
    budget     = input("▶ 예산 (낮/중/높): ")
    elderly    = input("▶ 노인 편의 필요? (y/n): ").lower() == 'y'
    wheelchair = input("▶ 휠체어 접근 필요? (y/n): ").lower() == 'y'

    prefs = {
        "duration_days": duration,
        "interest":       [s.strip() for s in interests.split(',') if s.strip()],
        "budget":         budget,
        "mobility_needs": {"elderly": elderly, "wheelchair": wheelchair}
    }

    scheduler_flow(prefs)
