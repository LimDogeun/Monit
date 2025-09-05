from argparse import ArgumentParser
from typing import Dict, Type
from review_analysis.utils.logger import setup_logger
from review_analysis.crawling.base_crawler import BaseCrawler
from review_analysis.crawling.naver_crawler import NaverCrawler
from review_analysis.crawling.googlemaps_crawler import GoogleMapsCrawler

import pandas as pd
import time
import os

# 모든 크롤링 클래스를 예시 형식으로 적어주세요.
CRAWLER_CLASSES: Dict[str, Type[BaseCrawler]] = {
    "Naver": NaverCrawler,
    "googlemaps": GoogleMapsCrawler,
}


def create_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument('-o', '--output_dir', type=str, required=True,
                        help="Output file directory. Example: ../../database")
    parser.add_argument('-c', '--crawler', type=str, required=False, choices=CRAWLER_CLASSES.keys(),
                         help=f"Which crawler to use. Choices: {', '.join(CRAWLER_CLASSES.keys())}")
    parser.add_argument('--input_csv', type=str, default="통합 문서1.csv",
                        help="(googlemaps 전용) 관광지명·주소가 담긴 CSV 파일 경로")
    parser.add_argument('-a', '--all', action='store_true',
                        help="Run all crawlers. Default to False.")
    return parser


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()

    if args.all:
        for crawler_name in CRAWLER_CLASSES.keys():
            Crawler_class = CRAWLER_CLASSES[crawler_name]
            crawler = Crawler_class(args.output_dir)
            crawler.start_browser()
            crawler.scrape_reviews()
            crawler.save_to_database()

    elif args.crawler == "googlemaps":
        df = pd.read_csv(args.input_csv, encoding="utf-8-sig")

        for _, row in df.iterrows():
            # 1) 크롤러 생성 & 브라우저 실행
            crawler = GoogleMapsCrawler(headless=False, output_dir=args.output_dir)
            crawler.start_browser()

            # 2) 검색 → 첫 결과 클릭 → 리뷰 탭 자동 이동
            crawler.navigate_to_reviews(
                name=row["관광지명"],
                addr=row["주소"]
            )
            time.sleep(2)  # 페이지 로딩 여유

            # 3) 리뷰 스크래핑
            crawler.scrape_reviews()

            # 4) 저장 (관광지명으로 파일명 지정)
            os.makedirs(args.output_dir, exist_ok=True)
            filename = f"{row['관광지명']}.csv"
            crawler.save_to_database(output_path=os.path.join(args.output_dir, filename))

    else:
        # Naver 등 다른 크롤러 분기
        Crawler_class = CRAWLER_CLASSES[args.crawler]
        crawler = Crawler_class(args.output_dir)
        crawler.start_browser()
        crawler.scrape_reviews()
        crawler.save_to_database()


