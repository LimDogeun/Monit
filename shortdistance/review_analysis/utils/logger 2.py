# review_analysis/utils/logger.py

import logging
import os

def setup_logger(
    name: str,
    log_file: str = None,
    level: int = logging.INFO
) -> logging.Logger:
    """
    로거를 생성하고 반환합니다.

    Args:
        name (str): 로거 이름 (보통 __name__ 을 전달합니다).
        log_file (str, optional): 로그를 저장할 파일 경로. 지정하지 않으면 파일 핸들러를 추가하지 않습니다.
        level (int, optional): 로깅 레벨 (DEBUG, INFO, WARNING 등). 기본은 INFO 레벨입니다.

    Returns:
        logging.Logger: 설정된 로거 객체
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 중복 핸들러 추가 방지
    if not logger.handlers:
        # 포맷터 정의
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 콘솔 핸들러
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    # 파일 핸들러 (log_file 경로가 주어졌을 때만)
    if log_file:
        # 디렉터리 자동 생성
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger
