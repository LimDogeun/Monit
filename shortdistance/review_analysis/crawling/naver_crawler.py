from review_analysis.crawling.base_crawler import BaseCrawler
from bs4 import BeautifulSoup  # type: ignore

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import pandas as pd # type: ignore
import time
import os

from datetime import datetime
from typing import List, Optional
from review_analysis.utils.logger import setup_logger

# Logger 설정
logger = setup_logger(name=__name__, log_file="./crawler.log")

class NaverCrawler(BaseCrawler):
    def __init__(self, output_dir: str, headless: bool = True):
        super().__init__(headless)
        self.output_dir = output_dir
        self.base_url: str = 'https://map.naver.com/p/entry/place/21306384?c=15.00,0,0,0,dh&placePath=/review'
        self.reviews: List[pd.DataFrame] = []
        self.driver: Optional[webdriver.Chrome] = None
        logger.info("NaverCrawler initialized with output_dir: %s", output_dir)

    def start_browser(self) -> None:
        """
        Chrome WebDriver를 초기화하고 지정된 네이버 맵 리뷰 페이지를 엽니다.

        Raises:
            Exception: 브라우저 시작 중 오류가 발생한 경우
        """
        try:
            chrome_options = Options()
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.get(self.base_url)
            self.driver.implicitly_wait(20)
            logger.info('"파이홀" 네이버 리뷰 페이지 로딩 성공')
        except Exception as e:
            logger.error("Error starting browser: %s", str(e))
            raise

    def scrape_reviews(self) -> None:
        """
        네이버 맵 리뷰 페이지에서 리뷰를 크롤링하여 수집합니다.

        - iframe 내부로 전환 후 리뷰 데이터 추출
        - 중복된 리뷰 제거
        - 리뷰 텍스트, 날짜, 평점 추출
        - '더보기' 버튼을 통해 추가 리뷰 로딩

        Raises:
            RuntimeError: WebDriver가 초기화되지 않은 경우
            Exception: 크롤링 중 발생하는 다양한 예외 상황
        """
        if not self.driver:
            logger.error("Driver is not initialized. Call `start_browser()` first.")
            raise RuntimeError("Driver is not initialized. Call `start_browser()` first.")

        columns: List[str] = ['text', 'date', 'rating']
        values: List[List[str]] = []
        n: int = 0
        seen_reviews: set = set()
        previous_review_count: int = 0

        try:
            iframe = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, 'entryIframe'))
            )
            self.driver.switch_to.frame(iframe)
            logger.info("iframe 전환 성공")

            while True:
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.place_apply_pui.EjjAW'))
                    )
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    reviews = soup.select('li.place_apply_pui.EjjAW')

                    if len(reviews) <= previous_review_count:
                        logger.info(f"새로운 리뷰 없음. 현재 리뷰 수: {len(reviews)}, 이전 리뷰 수: {previous_review_count}")
                        break

                    for review in reviews[previous_review_count:]:
                        blank: List[str] = ["", "", ""]
                        try:
                            content_tag = review.select_one('a[data-pui-click-code="rvshowmore"]')
                            content = content_tag.text.strip() if content_tag else ""
                            content_key = content.lower().replace(" ", "") if content else ""

                            if content_key in seen_reviews:
                                continue

                            seen_reviews.add(content_key)
                            n += 1
                            blank[0] = content

                            time_tag = review.find('time')
                            if time_tag:
                                date_str = time_tag.text.strip()
                                if date_str and '.' in date_str:
                                    parts = date_str.split('.')
                                    if len(parts) == 3:
                                        month, day, _ = parts
                                        current_year = datetime.now().year
                                        clean_date = f"{current_year}-{int(month):02d}-{int(day):02d}"
                                        blank[1] = clean_date
                                    elif len(parts) == 4:
                                        year_str, month, day, _ = parts
                                        parsed_year: int = int(year_str) + 2000 if int(year_str) < 100 else int(year_str)
                                        clean_date = f"{parsed_year}-{int(month):02d}-{int(day):02d}"
                                        blank[1] = clean_date

                            star_tag = review.select_one('.pui__6abRMf')
                            if star_tag:
                                star_text = star_tag.get_text(strip=True)
                                star_number = ''.join(filter(str.isdigit, star_text))  # 숫자만 추출
                                blank[2] = star_number

                        except Exception as e:
                            logger.warning(f"Error parsing review #{n}: {str(e)}")

                        values.append(blank)

                    logger.info(f"현재까지 크롤링된 리뷰 수: {len(values)}")
                    previous_review_count = len(reviews)

                    try:
                        more_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, '//*[@id="app-root"]/div/div/div/div[6]/div[3]/div[3]/div[2]/div/a')
                            )
                        )
                        more_button.click()
                        time.sleep(5)  # 시간 증가
                    except Exception:
                        logger.info("더보기 버튼 없음 또는 클릭 실패.")
                        break
                except Exception as e:
                    logger.error(f"리뷰 크롤링 중 오류 발생: {str(e)}")
                    break

            if values:
                df = pd.DataFrame(values, columns=columns)
                self.reviews.append(df)
                logger.info("크롤링 완료")
            else:
                logger.warning("크롤링 데이터 없음")
            input("브라우저를 닫으려면 Enter를 누르세요...")

        except Exception as e:
            logger.error(f"iframe 전환 실패 또는 크롤링 오류 발생: {str(e)}")
    
    def save_to_database(self) -> None:
        """
        크롤링된 리뷰 데이터를 CSV 파일로 저장합니다.

        - 크롤링된 모든 리뷰를 단일 DataFrame으로 병합
        - 출력 디렉토리가 존재하지 않을 경우 생성
        - UTF-8-SIG 인코딩으로 CSV 파일 저장

        Raises:
            Exception: 데이터 저장 중 오류가 발생한 경우
        """
        if not self.reviews:
            logger.warning("저장할 리뷰 데이터가 없습니다. 크롤링 데이터를 확인하세요.")
            return

        try:
            final_df = pd.concat(self.reviews, ignore_index=True)

            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            output_path = os.path.join(self.output_dir, "reviews_naver.csv")

            final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            logger.info(f"리뷰 데이터가 성공적으로 저장되었습니다: {output_path}")
        except Exception as e:
            logger.error(f"데이터 저장 중 오류 발생: {str(e)}")