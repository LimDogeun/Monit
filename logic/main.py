import pandas as pd
from datetime import datetime
from data_prep import data_load, preprocess_station_data
from scoring import (
    filtering_first,
    filter_by_distance_vectorized,
    filter_by_user_input,
    score_stations
)

def run_recommendation(
    data_dir: str,
    center: tuple,
    max_distance_km: float,
    output_values: list,
    chger_types: list,
    kinds: list,
    busi_ids: list,
    k: int = 5,
    hours: int = 48
):
    # # Step 1: 데이터 불러오기
    # raw_df = data_load(data_dir)

    # # Step 2: 전처리 (충전기 단위 → 충전소 단위)
    # station_df = preprocess_station_data(raw_df)
    # station_df.to_csv(f"../Database/preprocessed/processed_station_data.csv", index=False)

    station_df = pd.read_csv(f"../Database/preprocessed/processed_station_data.csv")

    # Step 3: 1차 필터링 (작동 상태 + 최근 사용 여부)
    # filtered_df = filtering_first(station_df, hours=hours, now=pd.Timestamp(datetime(2025, 5, 16, 12, 0, 0)))
    filtered_df = station_df

    # Step 4: 거리 필터링
    nearby_df = filter_by_distance_vectorized(filtered_df, center, max_distance_km=max_distance_km)

    # Step 5: 사용자 입력 필터링
    # user_filtered_df = filter_by_user_input(
    #     nearby_df,
    #     output_values=output_values,
    #     chger_types=chger_types,
    #     kinds=kinds,
    #     busi_ids=busi_ids
    # )

    user_filtered_df = nearby_df

    # Step 6: 스코어링
    top_k_df = score_stations(user_filtered_df, k=k)

    # Step 7: 출력
    pd.set_option('display.max_columns', None)
    print("\n🚗 추천 충전소 Top {} 🚗\n".format(k))
    print(top_k_df[['statNm', 'addr', 'total_score', 'distance_km'] + 
                   [col for col in top_k_df.columns if col.endswith('_score')]])
    
    filename = f"../Database/result/recommendation_{center[0]:.4f}_{center[1]:.4f}.csv"
    top_k_df.to_csv(filename, index=False)

    return top_k_df

def run_recommendation_with_list(
    center_list: list,
    data_dir: str,
    max_distance_km: float,
    output_values: list,
    chger_types: list,
    kinds: list,
    busi_ids: list,
    k: int = 5,
    hours: int = 48
):
    results = []
    for center in center_list:
        top_k_df = run_recommendation(
            data_dir=data_dir,
            center=center,
            max_distance_km=max_distance_km,
            output_values=output_values,
            chger_types=chger_types,
            kinds=kinds,
            busi_ids=busi_ids,
            k=k,
            hours=hours
        )
        results.append(top_k_df)
    return results

def get_recommendations_from_inputs(
    center_list: list,
    data_dir: str,
    max_distance_km: float,
    output_values: list,
    chger_types: list,
    kinds: list,
    busi_ids: list,
    k: int = 5,
    hours: int = 48
):
    return run_recommendation_with_list(
        center_list=center_list,
        data_dir=data_dir,
        max_distance_km=max_distance_km,
        output_values=output_values,
        chger_types=chger_types,
        kinds=kinds,
        busi_ids=busi_ids,
        k=k,
        hours=hours
    )

# 🔽 경로별 추천 파일로부터 요약 파일 생성 함수
def save_summary_from_recommendation_files(center_list, result_dir="../Database/result", summary_filename="summary_route_recommendations.csv"):
    summary_rows = []
    for center in center_list:
        file_path = f"{result_dir}/recommendation_{center[0]:.4f}_{center[1]:.4f}.csv"
        try:
            df = pd.read_csv(file_path)
            if not df.empty:
                top = df.iloc[0]
                summary_rows.append({
                    "statNm": top["statNm"],
                    "위도": top["lat"],
                    "경도": top["lng"],
                    "경로상 위도": center[1],
                    "경로상 경도": center[0]
                })
        except Exception as e:
            print(f"⚠️ 파일 읽기 실패: {file_path} ({e})")

    summary_df = pd.DataFrame(summary_rows)
    summary_path = f"{result_dir}/{summary_filename}"
    summary_df.to_csv(summary_path, index=False)
    print(f"\n✅ 요약 파일 저장 완료: {summary_filename}")

def main():
    data_dir = '../Database/opendata'
    center_list = [(126.99999918905259, 37.544330897558446), (127.01816252061731, 37.503701771404366), (127.03916340731878, 37.46412878936889), (127.08323872172886, 37.41686653952456), (127.10218291010248, 37.38855599473638), (127.10326507302938, 37.34603323713007), (127.10348832047815, 37.30160236014302), (127.10376463116029, 37.25357617946718), (127.09591345005207, 37.213444601945305), (127.09147320922787, 37.16653511530046), (127.10729497264947, 37.11944601386889), (127.12613270303927, 37.08413625579521), (127.13681331133334, 37.04484421718685), (127.15318788027434, 36.99666138308551), (127.18089508481894, 36.956610748341035), (127.18886351584455, 36.923097631296756), (127.18758152253208, 36.873579387175766), (127.17435035208358, 36.83458507307928), (127.16996922806496, 36.79180320019847), (127.20584728999698, 36.765688796041175), (127.25979541905103, 36.732593779914495), (127.29723950925994, 36.73091925426243), (127.34809555207215, 36.714554651921105), (127.37370325491938, 36.67632819574277), (127.38054646193147, 36.63352981278262), (127.41426864490518, 36.602815898899166), (127.43236337133125, 36.55877087843907), (127.42972855553347, 36.517491311221555), (127.42831691713269, 36.4725853109792), (127.41721011743243, 36.429849083900386), (127.42453580432317, 36.38773352223601), (127.45647321322572, 36.35696125391817), (127.47572753180641, 36.325305094603635), (127.45604663842981, 36.28689562187796), (127.47412965083566, 36.25141257648903), (127.49080037076924, 36.20990902276432), (127.48535970573185, 36.16607462385846), (127.50949707562387, 36.12936744386378), (127.53445573921167, 36.087016180702236), (127.55752446947929, 36.050339584532495), (127.58529272756245, 36.00823970294122), (127.6279639147095, 35.99014609638006), (127.66294248970559, 35.95645909121501), (127.6652488599688, 35.9142746327323), (127.64976677933461, 35.87229165905615), (127.6470279140314, 35.82812724494894), (127.62148653608045, 35.79009408798755), (127.59499446495771, 35.75242169191561), (127.6189920832849, 35.712335851861326), (127.66005477070357, 35.68515669528077), (127.694284827227, 35.65254700583248), (127.73468262931318, 35.62582703840504), (127.77252933059785, 35.598006910506584), (127.7577082166886, 35.55753315766802), (127.78464751081125, 35.51949173656511), (127.8157882840265, 35.488391233103904), (127.84944454071987, 35.45428400194215), (127.86538836179369, 35.41286536543613), (127.90656483173409, 35.38807045144247), (127.9306177069142, 35.34791970217836), (127.94141947649501, 35.30537843788127), (127.97518981574096, 35.26762937590774), (127.99543758392063, 35.234206785791514), (128.02521191917845, 35.19948995711302), (128.06276533205406, 35.16407673580105), (128.09725830197277, 35.138317697963984), (128.1403652262473, 35.11371096917442), (128.182754729526, 35.08884653395729), (128.23011415085492, 35.07041231590636), (128.27903643266274, 35.043960080906), (128.32077788905212, 35.02186132379919), (128.36144008569877, 34.993621464635154), (128.39822874674073, 34.96044968423919), (128.40873854739863, 34.92029037892846), (128.41358907213925, 34.877039217340155), (128.42997046460718, 34.861350749596035)]
    max_distance_km = 300
    output_values = ['50', '100', '200']
    chger_types = ['04', '05']
    kinds = ['A001', 'B001']
    busi_ids = ['ME', 'HI']
    k = 5

    results = get_recommendations_from_inputs(
        center_list=center_list,
        data_dir=data_dir,
        max_distance_km=max_distance_km,
        output_values=output_values,
        chger_types=chger_types,
        kinds=kinds,
        busi_ids=busi_ids,
        k=k
    )

    print("\n🚗 추천 충전소 최종결과 🚗\n")
    print(results)
    print("\n📁 추천 결과가 각 위치별로 CSV 파일로 저장되었습니다.")

    # 🔄 경로 요약 결과 통합 저장
    save_summary_from_recommendation_files(center_list)



if __name__ == '__main__':
    main()


