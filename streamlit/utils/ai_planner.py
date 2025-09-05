
import json
import google.generativeai as genai
import pandas as pd 
import base64


def build_prompt_content(prefs, df_food, df_tourist, df_blue):
    """프롬프트 내용을 생성합니다."""
    def top5(df, key_col):
        if df is None or df.empty:
            return ["- (데이터 없음)"]
        # 'Score' 컬럼이 없거나, 리뷰 기반 정렬이 아닌 경우를 대비
        if "Score" not in df.columns:
            top = df.head(5)
            return [f"- {row[key_col]}" for _, row in top.iterrows()]

        top = df.sort_values("Score", ascending=False).head(5)
        return [f"- {row[key_col]} (점수: {row['Score']:.2f})" for _, row in top.iterrows()]

    duration = prefs.get('duration_days', 1)
    origin_address = prefs.get('origin_address', '통영시내') # main.py에서 전달받은 출발지

    place_col = "Place" if df_tourist is not None and "Place" in df_tourist.columns else "관광명소"
    
    parts = [
        f"당신은 유능한 통영 여행 플래너입니다. 아래 정보를 바탕으로 사용자의 요구사항을 완벽하게 충족하는 **{duration}일**짜리 여행 일정을 JSON 형식으로 생성해주세요.",
        "\n### 사용자 요구사항",
        f"- 최초 출발지 및 최종 도착지: '{origin_address}'",
        f"- 희망 여행 기간: {duration}일",
        f"- 관심사: {', '.join(prefs.get('interest', []))}",
        f"- 이동 편의성 요구: 노인 편의({prefs.get('mobility_needs', {}).get('elderly', False)}), 휠체어 접근({prefs.get('mobility_needs', {}).get('wheelchair', False)})",
        "- 이동 수단: 전기차",

        "\n### 참고 데이터 (통영)",
        "#### 최신 리뷰 기반 상위 5개 음식점:",
    ] + top5(df_food, "Restaurant") + [
        "#### 최신 리뷰 기반 상위 5개 관광지:",
    ] + top5(df_tourist, place_col) + [
        "#### 최신 리뷰 기반 상위 5개 블루리본 맛집:",
    ] + top5(df_blue, "Restaurant") + [
        "\n### 일정 생성 시 필수 규칙",
        f"1. **연속성:** 각 일정의 '출발지'는 이전 일정의 '도착지'와 동일해야 합니다.",
        "2. **식사 시간:** 점심은 11:30~14:00, 저녁은 18:00~19:30 사이에 정확히 한 번씩만 포함해주세요.",
        "3. **일차(day) 명시:** 생성되는 모든 일정 항목에는 'day' 필드를 반드시 포함하고, 1부터 시작하여 날짜에 맞는 숫자를 정확히 기입해야 합니다.",
        f"4. **기간 준수:** 반드시 총 **{duration}일** 분량의 일정을 모두 생성해야 합니다.",

        "\n### JSON 출력 형식 (이 형식을 반드시 엄격하게 준수해주세요)",
        "전체 결과는 다른 설명 없이 JSON 리스트( [...] ) 형식으로만 출력해야 합니다.",
        'JSON 예시: [{"day": 1, "time": "09:00-10:30", "place": "이순신공원", "activity": "공원 산책"}, {"day": 1, "time": "11:00-12:00", "place": "동피랑 벽화마을", "activity": "벽화 구경"}, ... , {"day": 2, ...}]'
    ]
    return "\n".join(parts)