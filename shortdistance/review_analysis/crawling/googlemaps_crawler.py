from review_analysis.crawling.base_crawler import BaseCrawler
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import pandas as pd
import time
import os
from typing import List, Dict
from urllib.parse import quote_plus

class GoogleMapsCrawler(BaseCrawler):
    """
    Google Maps에서 관광지명+주소로 검색하여 첫 번째 결과의 리뷰 섹션을 크롤링하고 CSV로 저장하는 클래스
    리뷰는 각 장소당 최대 20개만 수집합니다.
    """
    def __init__(self, headless: bool = True, output_dir: str = "."):
        # BaseCrawler의 start_url은 사용하지 않으므로 빈 문자열 전달
        super().__init__(start_url="")
        self.headless = headless
        self.output_dir = output_dir
        self.reviews_data: List[Dict[str, str]] = []
        self.wait: WebDriverWait

    def _make_search_url(self, name: str, addr: str) -> str:
        """관광지명(name)과 주소(addr)를 합쳐 구글맵 검색 URL 생성"""
        query = quote_plus(f"{name} {addr}")
        return f"https://www.google.com/maps/search/?api=1&query={query}"

    def start_browser(self) -> None:
        """Chrome WebDriver를 설정하고 띄우기"""
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        else:
            options.add_experimental_option("detach", True)
            options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)

    def navigate_to_reviews(self, name: str, addr: str) -> None:
        """
        1) 검색 결과 페이지 접속
        2) 첫 번째 장소 클릭 → 상세 페이지 이동
        3) 리뷰(tab) 클릭 → 리뷰 패널 로드
        """
        # 검색 결과 페이지
        url = self._make_search_url(name, addr)
        self.driver.get(url)
        time.sleep(2)

        # 첫 번째 결과 클릭
        first = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[role="article"] a[href*="/place/"]'))
        )
        first.click()
        time.sleep(2)

        # 리뷰 탭 클릭
        review_btn = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-value="reviews"]'))
        )
        review_btn.click()
        # 리뷰 패널 로드 대기
        self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.m6QErb.DxyBCb.kA9KIf.dS8AEf'))
        )
        time.sleep(1)

    def scrape_reviews(self) -> None:
        """스크롤과 '더보기' 클릭으로 최대 20개의 리뷰를 로딩 후 파싱"""
        print("리뷰 데이터를 크롤링합니다...")
        try:
            panel = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.m6QErb.DxyBCb.kA9KIf.dS8AEf'))
            )
        except TimeoutException:
            print("리뷰 패널을 찾지 못했습니다. URL 또는 셀렉터를 확인하세요.")
            return

        # 무한 스크롤: 최소 5회, 최대 20회
        last, tries = 0, 0
        while tries < 20:
            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", panel)
            time.sleep(1.5)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            count = len(soup.select('span.kvMYJc[role="img"]'))
            if count == last and tries >= 5:
                break
            last, tries = count, tries + 1

        # '더보기' 버튼 클릭
        while True:
            mores = self.driver.find_elements(By.CSS_SELECTOR, 'button.w8nwRe.kyuRq')
            if not mores:
                break
            for btn in mores:
                try:
                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except:
                    pass

        # 최종 파싱
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        ratings = [e['aria-label'] for e in soup.select('span.kvMYJc[role="img"]')]
        texts   = [e.text.strip() or "리뷰 없음" for e in soup.select('span.wiI7pd')]
        dates   = [e.text.strip() for e in soup.select('span.rsqaWe')]

        # 개수 보정
        while len(texts) < len(ratings): texts.append("리뷰 없음")
        while len(dates) < len(ratings): dates.append("")

        # 최대 20개까지만 수집
        seen = set()
        for i, (r, t, d) in enumerate(zip(ratings, texts, dates)):
            if len(self.reviews_data) >= 20:
                break
            key = f"{r}|{t}|{d}|{i}"
            if key in seen:
                continue
            self.reviews_data.append({'별점': r, '리뷰': t, '날짜': d})
            seen.add(key)

        print(f"크롤링 완료, 수집된 리뷰 수: {len(self.reviews_data)}")

    def save_to_database(self, output_path: str = None) -> None:
        """수집된 리뷰를 CSV로 저장"""
        if not self.reviews_data:
            print("저장할 리뷰 데이터가 없습니다.")
            return
        df = pd.DataFrame(self.reviews_data)
        os.makedirs(self.output_dir, exist_ok=True)
        path = output_path or os.path.join(self.output_dir, "reviews_googlemaps.csv")
        df.to_csv(path, index=False, encoding='utf-8-sig')
        print(f"CSV 저장 완료: {path}")
