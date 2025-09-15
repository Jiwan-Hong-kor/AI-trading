#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
한국투자증권 KIS API 기반 투자 거장 스크리너 - 실행 스크립트
Author: Investment Screener Team
Version: 1.0.0
"""

import os
import sys
import logging
from dotenv import load_dotenv

def setup_environment():
    """환경 설정"""
    # .env 파일 로드
    load_dotenv()
    
    # 필수 디렉토리 생성
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # 로깅 설정
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    log_file = os.getenv('LOG_FILE', 'logs/app.log')
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def check_dependencies():
    """의존성 확인"""
    try:
        import flask
        import requests
        import pandas
        print("✅ 모든 필수 패키지가 설치되어 있습니다.")
        return True
    except ImportError as e:
        print(f"❌ 필수 패키지가 누락되었습니다: {e}")
        print("다음 명령어로 설치하세요: pip install -r requirements.txt")
        return False

def print_startup_info():
    """시작 정보 출력"""
    port = os.getenv('PORT', '5000')
    host = os.getenv('HOST', '0.0.0.0')
    environment = os.getenv('KIS_ENVIRONMENT', 'vps')
    
    print("=" * 70)
    print("🚀 한국투자증권 KIS API 기반 투자 거장 스크리너")
    print("=" * 70)
    print(f"📌 서버 주소: http://localhost:{port}")
    print(f"🏠 네트워크: http://{host}:{port}")
    print(f"🔧 KIS 환경: {environment.upper()} ({'모의투자' if environment == 'vps' else '실전투자'})")
    print("🔑 KIS API Key가 설정되지 않은 경우 샘플 데이터로 실행됩니다.")
    print("🌐 API 신청: https://apiportal.koreainvestment.com")
    print("")
    print("💡 주요 기능:")
    print("   • 6대 투자 철학 기반 주식 스크리너")
    print("   • 워렌 버핏, 피터 린치, 벤저민 그레이엄 등")
    print("   • 국내주식 (KOSPI/KOSDAQ) 및 해외주식 지원")
    print("   • 실시간 KIS API 연동")
    print("   • CSV 데이터 내보내기")
    print("")
    print("🎯 사용 방법:")
    print("   1. 브라우저에서 위 주소로 접속")
    print("   2. 투자 거장 선택 (기본: 워렌 버핏)")
    print("   3. 시장 선택 (전체/국내/미국/해외)")
    print("   4. KIS API 연동 (선택사항)")
    print("   5. 투자 분석 결과 확인")
    print("=" * 70)
    print("")

def main():
    """메인 실행 함수"""
    try:
        # 환경 설정
        setup_environment()
        
        # 의존성 확인
        if not check_dependencies():
            sys.exit(1)
        
        # 시작 정보 출력
        print_startup_info()
        
        # Flask 앱 임포트 및 실행
        from app import app
        
        # 환경변수에서 설정 읽기
        port = int(os.getenv('PORT', 5000))
        host = os.getenv('HOST', '0.0.0.0')
        debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
        
        # 서버 시작
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True,
            use_reloader=False  # 중복 실행 방지
        )
        
    except KeyboardInterrupt:
        print("\n🛑 서버가 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"❌ 서버 시작 중 오류가 발생했습니다: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()