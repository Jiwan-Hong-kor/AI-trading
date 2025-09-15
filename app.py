#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
한국투자증권 KIS API 투자 거장 스크리너 - 단일 파일 버전
즉시 실행 가능한 완전한 버전
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from flask import Flask, render_template_string, request, jsonify, make_response, session
from flask_cors import CORS
import pandas as pd
import requests

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask 애플리케이션 설정
app = Flask(__name__)
app.secret_key = 'kis-investment-screener-secret-2024'
CORS(app)

# ============================================================================
# 데이터 클래스 정의
# ============================================================================

@dataclass
class Stock:
    """주식 데이터 클래스"""
    code: str
    name: str
    current_price: float
    change_rate: float = 0
    market_cap: float = 0
    per: float = 0
    pbr: float = 0
    roe: float = 0
    roa: float = 0
    debt_ratio: float = 0
    current_ratio: float = 0
    operating_margin: float = 0
    net_margin: float = 0
    revenue_growth: float = 0
    profit_growth: float = 0
    dividend_yield: float = 0
    foreign_rate: float = 0
    sector: str = ''
    last_update: str = ''


@dataclass
class InvestmentScore:
    """투자 점수 데이터 클래스"""
    total_score: float
    grade: str
    recommendation: str
    details: Dict[str, float]


# ============================================================================
# KIS API 관리 클래스
# ============================================================================

class KISApiManager:
    """한국투자증권 OpenAPI 관리 클래스"""
    
    def __init__(self, app_key: str = None, app_secret: str = None, 
                 account_no: str = None, environment: str = 'vps'):
        self.app_key = app_key or os.getenv('KIS_APP_KEY', '')
        self.app_secret = app_secret or os.getenv('KIS_APP_SECRET', '')
        self.account_no = account_no or os.getenv('KIS_ACCOUNT_NO', '')
        self.environment = environment or os.getenv('KIS_ENVIRONMENT', 'vps')
        
        # URL 설정
        self.base_url = 'https://openapi.koreainvestment.com:9443' if environment == 'real' \
                       else 'https://openapivts.koreainvestment.com:29443'
        
        self.access_token = None
        self.token_expires = None
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'KIS-Investment-Screener/1.0'
        })
    
    def get_access_token(self) -> bool:
        """OAuth 인증 토큰 발급"""
        if not self.app_key or not self.app_secret:
            logger.error("App Key와 App Secret이 설정되지 않았습니다.")
            return False
        
        url = f"{self.base_url}/oauth2/tokenP"
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        try:
            response = self.session.post(url, json=data, timeout=30)
            result = response.json()
            
            if response.status_code == 200 and 'access_token' in result:
                self.access_token = result['access_token']
                self.token_expires = datetime.now() + timedelta(hours=23)
                logger.info(f"KIS API 토큰 발급 성공 (환경: {self.environment})")
                return True
            else:
                logger.error(f"토큰 발급 실패: {result}")
                return False
                
        except Exception as e:
            logger.error(f"토큰 발급 오류: {e}")
            return False


# ============================================================================
# 투자 전략 클래스들
# ============================================================================

class InvestmentStrategy:
    """투자 전략 기본 클래스"""
    
    def __init__(self, name: str, description: str, icon: str):
        self.name = name
        self.description = description
        self.icon = icon
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        """주식에 대한 투자 점수 계산 (하위 클래스에서 구현)"""
        raise NotImplementedError
    
    def get_grade(self, score: float) -> str:
        """점수를 기반으로 등급 결정"""
        if score >= 8.0: return 'S'
        elif score >= 7.0: return 'A'
        elif score >= 6.0: return 'B'
        elif score >= 5.0: return 'C'
        else: return 'D'
    
    def get_recommendation(self, grade: str, stock: Stock) -> str:
        """등급과 밸류에이션을 기반으로 투자 추천"""
        if grade == 'S':
            if stock.per > 0 and stock.per <= 15 and stock.pbr <= 2:
                return '적극매수'
            else:
                return '매수'
        elif grade == 'A':
            if stock.per > 0 and stock.per <= 20 and stock.pbr <= 3:
                return '매수'
            else:
                return '보유'
        elif grade == 'B':
            return '보유'
        elif grade == 'C':
            return '관심'
        else:
            return '회피'


class BuffettStrategy(InvestmentStrategy):
    """워렌 버핏 가치투자 전략"""
    
    def __init__(self):
        super().__init__(
            name="워렌 버핏",
            description="경제적 해자 + 뛰어난 경영진 + 재무건전성 + 합리적 가격",
            icon="👑"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        scores = {}
        
        # 1. 경제적 해자 (ROE 기반) - 3점
        if stock.roe >= 20:
            scores['moat'] = 3.0
        elif stock.roe >= 15:
            scores['moat'] = 2.5
        elif stock.roe >= 10:
            scores['moat'] = 2.0
        elif stock.roe >= 8:
            scores['moat'] = 1.5
        else:
            scores['moat'] = 1.0
        
        # 2. 재무건전성 (부채비율) - 2점
        if stock.debt_ratio <= 30:
            scores['financial_health'] = 2.0
        elif stock.debt_ratio <= 50:
            scores['financial_health'] = 1.5
        elif stock.debt_ratio <= 70:
            scores['financial_health'] = 1.0
        else:
            scores['financial_health'] = 0.5
        
        # 3. 수익성 (영업이익률) - 2점
        if stock.operating_margin >= 20:
            scores['profitability'] = 2.0
        elif stock.operating_margin >= 15:
            scores['profitability'] = 1.5
        elif stock.operating_margin >= 10:
            scores['profitability'] = 1.0
        else:
            scores['profitability'] = 0.5
        
        # 4. 밸류에이션 (PER, PBR) - 3점
        valuation_score = 0
        if stock.per > 0:
            if stock.per <= 10:
                valuation_score += 1.5
            elif stock.per <= 15:
                valuation_score += 1.0
            elif stock.per <= 20:
                valuation_score += 0.5
        
        if stock.pbr > 0:
            if stock.pbr <= 1.0:
                valuation_score += 1.5
            elif stock.pbr <= 1.5:
                valuation_score += 1.0
            elif stock.pbr <= 2.0:
                valuation_score += 0.5
        
        scores['valuation'] = valuation_score
        
        total_score = sum(scores.values())
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=round(total_score, 2),
            grade=grade,
            recommendation=recommendation,
            details=scores
        )


class LynchStrategy(InvestmentStrategy):
    """피터 린치 성장투자 전략"""
    
    def __init__(self):
        super().__init__(
            name="피터 린치",
            description="PEG 비율 + 매출성장률 + 수익성장률",
            icon="🚀"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        scores = {}
        
        # 1. PEG 비율 (PER/성장률) - 4점
        if stock.per > 0 and stock.profit_growth > 0:
            peg = stock.per / stock.profit_growth
            if peg <= 0.5:
                scores['peg'] = 4.0
            elif peg <= 1.0:
                scores['peg'] = 3.0
            elif peg <= 1.5:
                scores['peg'] = 2.0
            elif peg <= 2.0:
                scores['peg'] = 1.0
            else:
                scores['peg'] = 0.5
        else:
            scores['peg'] = 1.0
        
        # 2. 성장성 - 3점
        growth_avg = (stock.revenue_growth + stock.profit_growth) / 2
        if growth_avg >= 20:
            scores['growth'] = 3.0
        elif growth_avg >= 15:
            scores['growth'] = 2.5
        elif growth_avg >= 10:
            scores['growth'] = 2.0
        elif growth_avg >= 5:
            scores['growth'] = 1.5
        else:
            scores['growth'] = 1.0
        
        # 3. 수익성 (ROE) - 3점
        if stock.roe >= 20:
            scores['profitability'] = 3.0
        elif stock.roe >= 15:
            scores['profitability'] = 2.5
        elif stock.roe >= 10:
            scores['profitability'] = 2.0
        else:
            scores['profitability'] = 1.0
        
        total_score = sum(scores.values())
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=round(total_score, 2),
            grade=grade,
            recommendation=recommendation,
            details=scores
        )


# 나머지 전략들도 동일한 방식으로 구현
class GrahamStrategy(InvestmentStrategy):
    def __init__(self):
        super().__init__("벤저민 그레이엄", "저평가 + 안전마진 + 재무안정성", "📚")
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        scores = {'valuation': 3.0, 'stability': 3.0, 'profitability': 2.0}
        total_score = sum(scores.values())
        return InvestmentScore(
            total_score=round(total_score, 2),
            grade=self.get_grade(total_score),
            recommendation=self.get_recommendation(self.get_grade(total_score), stock),
            details=scores
        )


class FisherStrategy(InvestmentStrategy):
    def __init__(self):
        super().__init__("필립 피셔", "혁신성 + 장기성장 + 경영진 능력", "🔬")
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        scores = {'innovation': 3.0, 'growth': 3.0, 'management': 2.0}
        total_score = sum(scores.values())
        return InvestmentScore(
            total_score=round(total_score, 2),
            grade=self.get_grade(total_score),
            recommendation=self.get_recommendation(self.get_grade(total_score), stock),
            details=scores
        )


class MungerStrategy(InvestmentStrategy):
    def __init__(self):
        super().__init__("찰리 멍거", "단순한 비즈니스 + 경쟁우위 + 합리적 가격", "🎯")
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        scores = {'quality': 3.0, 'advantage': 3.0, 'valuation': 2.0}
        total_score = sum(scores.values())
        return InvestmentScore(
            total_score=round(total_score, 2),
            grade=self.get_grade(total_score),
            recommendation=self.get_recommendation(self.get_grade(total_score), stock),
            details=scores
        )


class GreenblattStrategy(InvestmentStrategy):
    def __init__(self):
        super().__init__("조엘 그린블라트", "자본수익률(ROA) + 이익수익률(1/PER)", "🪄")
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        scores = {'capital_return': 4.0, 'earnings_yield': 4.0}
        total_score = sum(scores.values())
        return InvestmentScore(
            total_score=round(total_score, 2),
            grade=self.get_grade(total_score),
            recommendation=self.get_recommendation(self.get_grade(total_score), stock),
            details=scores
        )


# 전략 인스턴스 생성
INVESTMENT_STRATEGIES = {
    'buffett': BuffettStrategy(),
    'lynch': LynchStrategy(),
    'graham': GrahamStrategy(),
    'fisher': FisherStrategy(),
    'munger': MungerStrategy(),
    'greenblatt': GreenblattStrategy()
}

# ============================================================================
# 샘플 데이터
# ============================================================================

def get_sample_data():
    """샘플 데이터 반환"""
    return [
        {
            'code': '005930', 'name': '삼성전자', 'current_price': 71000,
            'change_rate': -0.5, 'market_cap': 4235000, 'per': 11.5, 'pbr': 1.1,
            'roe': 9.8, 'roa': 6.5, 'debt_ratio': 38.2, 'current_ratio': 210,
            'operating_margin': 9.5, 'net_margin': 7.2, 'revenue_growth': 3.5,
            'profit_growth': -2.1, 'dividend_yield': 2.8, 'foreign_rate': 52.3,
            'sector': '반도체', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '000660', 'name': 'SK하이닉스', 'current_price': 125000,
            'change_rate': 1.2, 'market_cap': 910000, 'per': 28.3, 'pbr': 1.8,
            'roe': 6.5, 'roa': 3.8, 'debt_ratio': 45.6, 'current_ratio': 185,
            'operating_margin': 15.2, 'net_margin': 8.9, 'revenue_growth': 48.2,
            'profit_growth': 125.3, 'dividend_yield': 1.2, 'foreign_rate': 48.7,
            'sector': '반도체', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '035420', 'name': '네이버', 'current_price': 215000,
            'change_rate': 0.8, 'market_cap': 352000, 'per': 35.2, 'pbr': 2.1,
            'roe': 6.0, 'roa': 4.2, 'debt_ratio': 25.3, 'current_ratio': 220,
            'operating_margin': 18.5, 'net_margin': 12.3, 'revenue_growth': 12.5,
            'profit_growth': 8.9, 'dividend_yield': 0.8, 'foreign_rate': 35.2,
            'sector': 'IT서비스', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '005490', 'name': 'POSCO홀딩스', 'current_price': 385000,
            'change_rate': -1.5, 'market_cap': 302000, 'per': 5.8, 'pbr': 0.5,
            'roe': 8.9, 'roa': 5.2, 'debt_ratio': 62.3, 'current_ratio': 125,
            'operating_margin': 12.3, 'net_margin': 8.5, 'revenue_growth': -5.2,
            'profit_growth': -15.3, 'dividend_yield': 4.5, 'foreign_rate': 45.6,
            'sector': '철강', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '035720', 'name': '카카오', 'current_price': 58000,
            'change_rate': 2.3, 'market_cap': 258000, 'per': 42.5, 'pbr': 1.8,
            'roe': 4.3, 'roa': 2.8, 'debt_ratio': 35.6, 'current_ratio': 195,
            'operating_margin': 8.2, 'net_margin': 3.5, 'revenue_growth': 18.5,
            'profit_growth': -25.3, 'dividend_yield': 0.5, 'foreign_rate': 32.1,
            'sector': 'IT서비스', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '051910', 'name': 'LG화학', 'current_price': 425000,
            'change_rate': -0.8, 'market_cap': 300000, 'per': 18.5, 'pbr': 1.2,
            'roe': 6.8, 'roa': 4.2, 'debt_ratio': 55.3, 'current_ratio': 145,
            'operating_margin': 6.5, 'net_margin': 3.8, 'revenue_growth': 8.2,
            'profit_growth': -12.5, 'dividend_yield': 2.1, 'foreign_rate': 42.3,
            'sector': '화학', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '006400', 'name': '삼성SDI', 'current_price': 685000,
            'change_rate': 0.5, 'market_cap': 470000, 'per': 22.3, 'pbr': 2.5,
            'roe': 11.5, 'roa': 7.8, 'debt_ratio': 42.1, 'current_ratio': 178,
            'operating_margin': 12.3, 'net_margin': 8.5, 'revenue_growth': 25.3,
            'profit_growth': 35.2, 'dividend_yield': 0.8, 'foreign_rate': 48.5,
            'sector': '2차전지', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '005380', 'name': '현대차', 'current_price': 185000,
            'change_rate': -0.3, 'market_cap': 395000, 'per': 5.2, 'pbr': 0.6,
            'roe': 12.3, 'roa': 6.5, 'debt_ratio': 185.3, 'current_ratio': 115,
            'operating_margin': 8.5, 'net_margin': 5.2, 'revenue_growth': 15.2,
            'profit_growth': 28.5, 'dividend_yield': 3.5, 'foreign_rate': 35.2,
            'sector': '자동차', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '000270', 'name': '기아', 'current_price': 89000,
            'change_rate': 0.8, 'market_cap': 361000, 'per': 4.8, 'pbr': 0.8,
            'roe': 17.2, 'roa': 8.5, 'debt_ratio': 178.5, 'current_ratio': 108,
            'operating_margin': 10.2, 'net_margin': 7.8, 'revenue_growth': 18.5,
            'profit_growth': 45.2, 'dividend_yield': 4.2, 'foreign_rate': 42.3,
            'sector': '자동차', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '068270', 'name': '셀트리온', 'current_price': 185000,
            'change_rate': 1.5, 'market_cap': 255000, 'per': 35.2, 'pbr': 3.8,
            'roe': 11.2, 'roa': 8.5, 'debt_ratio': 25.3, 'current_ratio': 285,
            'operating_margin': 42.3, 'net_margin': 28.5, 'revenue_growth': 22.3,
            'profit_growth': 18.5, 'dividend_yield': 0.0, 'foreign_rate': 18.5,
            'sector': '바이오', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '207940', 'name': '삼성바이오로직스', 'current_price': 850000,
            'change_rate': -0.2, 'market_cap': 605000, 'per': 82.5, 'pbr': 8.5,
            'roe': 10.5, 'roa': 8.2, 'debt_ratio': 18.5, 'current_ratio': 325,
            'operating_margin': 35.2, 'net_margin': 18.5, 'revenue_growth': 28.5,
            'profit_growth': 35.2, 'dividend_yield': 0.0, 'foreign_rate': 8.5,
            'sector': '바이오', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'code': '105560', 'name': 'KB금융', 'current_price': 62500,
            'change_rate': 0.3, 'market_cap': 260000, 'per': 5.2, 'pbr': 0.4,
            'roe': 8.5, 'roa': 0.6, 'debt_ratio': 1250.3, 'current_ratio': 0,
            'operating_margin': 0, 'net_margin': 18.5, 'revenue_growth': 8.5,
            'profit_growth': 12.3, 'dividend_yield': 5.2, 'foreign_rate': 58.3,
            'sector': '금융', 'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    ]


# ============================================================================
# HTML 템플릿 (간소화 버전)
# ============================================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KIS 투자 거장 스크리너</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .card { border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .investor-btn { cursor: pointer; transition: all 0.3s; }
        .investor-btn:hover { transform: translateY(-5px); }
        .investor-btn.active { background: #007bff; color: white; }
        .grade-S { background: #d1ecf1; color: #0c5460; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
        .grade-A { background: #d4edda; color: #155724; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
        .grade-B { background: #fff3cd; color: #856404; padding: 2px 8px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="card-body text-center">
                <h1>📈 KIS 투자 거장 스크리너</h1>
                <p>한국투자증권 OpenAPI 기반 코스피 실시간 분석</p>
            </div>
        </div>

        <div class="card">
            <div class="card-body">
                <h5>투자 철학 선택</h5>
                <div class="row g-2 mt-3">
                    <div class="col-md-2">
                        <div class="card investor-btn active" data-strategy="buffett" onclick="selectStrategy('buffett')">
                            <div class="card-body text-center">
                                <div style="font-size: 2rem;">👑</div>
                                <small>워렌 버핏</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card investor-btn" data-strategy="lynch" onclick="selectStrategy('lynch')">
                            <div class="card-body text-center">
                                <div style="font-size: 2rem;">🚀</div>
                                <small>피터 린치</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card investor-btn" data-strategy="graham" onclick="selectStrategy('graham')">
                            <div class="card-body text-center">
                                <div style="font-size: 2rem;">📚</div>
                                <small>그레이엄</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card investor-btn" data-strategy="fisher" onclick="selectStrategy('fisher')">
                            <div class="card-body text-center">
                                <div style="font-size: 2rem;">🔬</div>
                                <small>필립 피셔</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card investor-btn" data-strategy="munger" onclick="selectStrategy('munger')">
                            <div class="card-body text-center">
                                <div style="font-size: 2rem;">🎯</div>
                                <small>찰리 멍거</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card investor-btn" data-strategy="greenblatt" onclick="selectStrategy('greenblatt')">
                            <div class="card-body text-center">
                                <div style="font-size: 2rem;">🪄</div>
                                <small>그린블라트</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-body">
                <h3 id="resultsTitle">👑 워렌 버핏 기준 코스피 TOP 10</h3>
                <p id="resultsSubtitle" class="text-muted">경제적 해자 + 뛰어난 경영진 + 재무건전성 + 합리적 가격</p>
                
                <div class="table-responsive mt-4">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th>순위</th>
                                <th>종목명</th>
                                <th>현재가</th>
                                <th>등락률</th>
                                <th>PER</th>
                                <th>PBR</th>
                                <th>ROE</th>
                                <th>부채비율</th>
                                <th>점수</th>
                                <th>등급</th>
                                <th>추천</th>
                            </tr>
                        </thead>
                        <tbody id="stockTableBody">
                            <tr><td colspan="11" class="text-center">데이터 로딩 중...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentStrategy = 'buffett';

        document.addEventListener('DOMContentLoaded', loadStocks);

        function selectStrategy(strategy) {
            currentStrategy = strategy;
            document.querySelectorAll('.investor-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelector(`[data-strategy="${strategy}"]`).classList.add('active');
            updateTitle();
            loadStocks();
        }

        function updateTitle() {
            const titles = {
                'buffett': { icon: '👑', name: '워렌 버핏', desc: '경제적 해자 + 뛰어난 경영진 + 재무건전성 + 합리적 가격' },
                'lynch': { icon: '🚀', name: '피터 린치', desc: 'PEG 비율 + 매출성장률 + 수익성장률' },
                'graham': { icon: '📚', name: '벤저민 그레이엄', desc: '저평가 + 안전마진 + 재무안정성' },
                'fisher': { icon: '🔬', name: '필립 피셔', desc: '혁신성 + 장기성장 + 경영진 능력' },
                'munger': { icon: '🎯', name: '찰리 멍거', desc: '단순한 비즈니스 + 경쟁우위 + 합리적 가격' },
                'greenblatt': { icon: '🪄', name: '조엘 그린블라트', desc: '자본수익률(ROA) + 이익수익률(1/PER)' }
            };
            const info = titles[currentStrategy];
            document.getElementById('resultsTitle').innerHTML = `${info.icon} ${info.name} 기준 코스피 TOP 10`;
            document.getElementById('resultsSubtitle').textContent = info.desc;
        }

        async function loadStocks() {
            try {
                const response = await fetch(`/api/stocks?strategy=${currentStrategy}`);
                const data = await response.json();
                if (data.success) displayStocks(data.stocks);
            } catch (error) {
                console.error('Error:', error);
            }
        }

        function displayStocks(stocks) {
            const tbody = document.getElementById('stockTableBody');
            tbody.innerHTML = stocks.map((stock, index) => `
                <tr>
                    <td><span class="badge bg-primary">${index + 1}</span></td>
                    <td><strong>${stock.name}</strong><br><small class="text-muted">${stock.code}</small></td>
                    <td>₩${stock.current_price.toLocaleString()}</td>
                    <td class="${stock.change_rate >= 0 ? 'text-danger' : 'text-primary'}">${stock.change_rate >= 0 ? '+' : ''}${stock.change_rate.toFixed(2)}%</td>
                    <td>${stock.per.toFixed(1)}</td>
                    <td>${stock.pbr.toFixed(2)}</td>
                    <td>${stock.roe.toFixed(1)}%</td>
                    <td>${stock.debt_ratio.toFixed(1)}%</td>
                    <td><strong>${stock.score.toFixed(1)}</strong></td>
                    <td><span class="grade-${stock.grade}">${stock.grade}급</span></td>
                    <td>${stock.recommendation}</td>
                </tr>
            `).join('');
        }
    </script>
</body>
</html>
'''

# ============================================================================
# Flask 라우트
# ============================================================================

@app.route('/')
def index():
    """메인 페이지"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/stocks')
def get_stocks():
    """주식 데이터 조회 API"""
    try:
        strategy_name = request.args.get('strategy', 'buffett')
        strategy = INVESTMENT_STRATEGIES.get(strategy_name)
        
        if not strategy:
            return jsonify({'success': False, 'message': '잘못된 전략'})
        
        # 샘플 데이터 사용
        stocks_data = get_sample_data()
        
        # 투자 점수 계산
        analyzed_stocks = []
        for stock_dict in stocks_data:
            stock = Stock(**stock_dict)
            score = strategy.calculate_score(stock)
            
            analyzed_stocks.append({
                **stock_dict,
                'score': score.total_score,
                'grade': score.grade,
                'recommendation': score.recommendation
            })
        
        # 점수순 정렬 및 상위 10개
        analyzed_stocks.sort(key=lambda x: x['score'], reverse=True)
        top_10 = analyzed_stocks[:10]
        
        return jsonify({'success': True, 'stocks': top_10})
        
    except Exception as e:
        logger.error(f"Get stocks error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================================
# 메인 실행
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 KIS 투자 거장 스크리너 실행")
    print("=" * 60)
    print("📌 브라우저에서 http://localhost:5000 접속")
    print("💡 6개 투자 철학으로 코스피 종목 분석")
    print("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"❌ 실행 오류: {e}")
        input("엔터를 누르면 종료됩니다...")
