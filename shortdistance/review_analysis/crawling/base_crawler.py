class BaseCrawler:
    """
    모든 크롤러의 공통 기능을 정의하는 베이스 클래스.
    서브클래스에서 crawl(), parse() 등을 구현하세요.
    """
    def __init__(self, start_url: str):
        self.start_url = start_url

    def crawl(self):
        """
        실제 크롤링 로직을 이 메서드에 구현합니다.
        서브클래스에서 반드시 오버라이드하세요.
        """
        raise NotImplementedError("서브클래스에서 crawl()을 구현해야 합니다.")
