import os
import csv
import pandas as pd
import openai

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Directory containing review CSV files
reviews_dir = "C:/Users/lgsc0/Desktop/Monit/모범음식점"

# Prompt template for ChatGPT analysis
PROMPT_TEMPLATE = """
다음 CSV 리뷰 데이터를 기반으로 아래 형식으로 분석해주세요.

1) 노인 방문 적합도 (0~5점) 및 평가 사유
2) 장애인 방문 적합도 (0~5점) 및 평가 사유
3) 유아 방문 적합도 (0~5점) 및 평가 사유
4) 가격대 대비 음식 만족도 (0~5점) 및 평가 사유
5) 주차 문제 유무 (Yes/No) 및 이유
6) 핵심 키워드 5개 (세미콜론(;)으로 구분)

결과는 반드시 CSV 헤더에 맞춘 단일 행 형태로 반환해 주세요.
CSV 헤더:
Restaurant,Elderly_Score,Elderly_Notes,Disabled_Score,Disabled_Notes,Infant_Score,Infant_Notes,Price_Satisfaction_Score,Price_Satisfaction_Notes,Parking_Issue,Parking_Notes,Keywords

리뷰 데이터:
{review_csv}
"""

def embed_text(text):
    """Generate embedding for the given text."""
    response = openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

def analyze_reviews(file_path):
    """Read reviews from CSV, embed, call ChatGPT for analysis, and return parsed CSV row."""
    df = pd.read_csv(file_path)
    # Combine all reviews into one text blob for context
    reviews_blob = "\n".join(df['리뷰'].astype(str).tolist())
    
    # Step 1: Embed the reviews blob (optional, for storing or similarity tasks)
    embedding = embed_text(reviews_blob)
    
    # Step 2: Call ChatGPT for analysis
    prompt = PROMPT_TEMPLATE.format(review_csv=reviews_blob)
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are a review analysis assistant."},
                  {"role": "user", "content": prompt}],
        temperature=0.2
    )
    csv_line = response.choices[0].message.content.strip()
    # Parse CSV line into a list of values
    reader = csv.reader([csv_line])
    return next(reader)

def main():
    # Collect results
    aggregated_rows = []
    header = ["Restaurant","Elderly_Score","Elderly_Notes","Disabled_Score","Disabled_Notes",
              "Infant_Score","Infant_Notes","Price_Satisfaction_Score","Price_Satisfaction_Notes",
              "Parking_Issue","Parking_Notes","Keywords"]
    
    # Iterate review files
    for filename in os.listdir(reviews_dir):
        if filename.endswith(".csv"):
            file_path = os.path.join(reviews_dir, filename)
            restaurant_name = os.path.splitext(filename)[0]
            row = analyze_reviews(file_path)
            row[0] = restaurant_name  # Ensure Restaurant column matches filename
            aggregated_rows.append(row)
    
    # Save all results to a single CSV
    out_df = pd.DataFrame(aggregated_rows, columns=header)
    out_df.to_csv("모범음식점_리뷰_통영.csv", index=False, encoding="utf-8-sig")
    print("Saved aggregated analysis to 모범음식점_리뷰_통영.csv")

if __name__ == "__main__":
    main()