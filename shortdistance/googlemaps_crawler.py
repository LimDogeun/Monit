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
    """
    def __init__(self, headless: bool = True, output_dir: str = "."):
        super().__init__(start_url="")
        self.headless = headless
        self.output_dir = output_dir
        self.reviews_data: List[Dict[str, str]] = []
        self.wait: WebDriverWait

    def _make_search_url(self, name: str, addr: str) -> str:
        query = quote_plus(f"{name} {addr}")
        return f"https://www.google.com/maps/search/?api=1&query={query}"

    def start_browser(self) -> None:
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        else:
            options.add_experimental_option("detach", True)
            options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)

    def navigate_to_reviews(self, name: str, addr: str) -> None:
        url = self._make_search_url(name, addr)
        print(f"\n[DEBUG] 접속 URL: {url}")
        print(f"[DEBUG] 검색어: {name} {addr}")
        self.driver.get(url)
        time.sleep(5)  # 페이지 로딩 여유

        # 바로 Reviews 탭으로 이동
        try:
            reviews_tab = self.wait.until(
                EC.element_to_be_clickable((By.XPATH,
                    '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[3]/div/div/button[2]'
                ))
            )
            reviews_tab.click()
            print("[INFO] 리뷰 탭 클릭 완료 via XPath")
            time.sleep(2)
        except Exception as e:
            print(f"[ERROR] 리뷰 탭 클릭 실패 ({e})")
            return

        # 리뷰 패널 로드 대기
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.m6QErb.DxyBCb.kA9KIf.dS8AEf'))
            )
            time.sleep(1)
        except TimeoutException:
            print("[ERROR] 리뷰 패널 로드 실패")
            return


    def scrape_reviews(self) -> None:
        print("리뷰 데이터를 크롤링합니다...")
        try:
            panel = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.m6QErb.DxyBCb.kA9KIf.dS8AEf'))
            )
        except TimeoutException:
            print("리뷰 패널을 찾지 못했습니다. URL 또는 셀렉터를 확인하세요.")
            return

        last, tries = 0, 0
        while tries < 20:
            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", panel)
            time.sleep(1.5)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            count = len(soup.select('span.kvMYJc'))
            if count == last and tries > 5:
                break
            last, tries = count, tries + 1

        while True:
            mores = self.driver.find_elements(By.CSS_SELECTOR, 'button.w8nwRe.kyuRq')
            if not mores:
                break
            for btn in mores:
                try:
                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except Exception:
                    pass

        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        ratings = []
        for span in soup.select('span.kvMYJc'):
            label = span.get('aria-label', '')
            score = ''.join([s for s in label if s.isdigit() or s == '/'])
            if score:
                ratings.append(score.replace('별표 ', '').replace('개', '').strip())

        dates = [e.text.strip() for e in soup.select('span.rsqaWe')]
        texts = [e.text.strip() for e in soup.select('span.wiI7pd')]
        while len(texts) < len(ratings): texts.append("리뷰 없음")
        while len(dates) < len(ratings): dates.append("")

        seen = set()
        for i, (r, t, d) in enumerate(zip(ratings, texts, dates)):
            key = f"{r}|{t}|{d}|{i}"
            if key in seen: continue
            self.reviews_data.append({'별점': r, '리뷰': t, '날짜': d})
            seen.add(key)

        print(f"크롤링 완료, 총 리뷰 수: {len(self.reviews_data)}")

    def save_to_database(self, output_path: str = None) -> None:
        if not self.reviews_data:
            print("저장할 리뷰 데이터가 없습니다.")
            return
        df = pd.DataFrame(self.reviews_data)
        out_dir = self.output_dir
        os.makedirs(out_dir, exist_ok=True)
        path = output_path or os.path.join(out_dir, "reviews_googlemaps.csv")
        df.to_csv(path, index=False, encoding='utf-8-sig')
        print(f"CSV 저장 완료: {path}")
