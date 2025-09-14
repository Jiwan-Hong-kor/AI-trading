#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
한국투자증권 KIS API 기반 투자 거장 스크리너
Author: Investment Screener Team
Version: 1.0.0
Description: 6대 투자 철학을 기반으로 한 주식 스크리너 시스템
"""

import os
import json
import requests
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, flash, redirect, url_for
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge
import pandas as pd

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask 애플리케이션 설정
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
CORS(app)

# KIS API 설정
KIS_CONFIG = {
    'base_url_real': 'https://openapi.koreainvestment.com:9443',
    'base_url_vps': 'https://openapivts.koreainvestment.com:29443',
    'app_key': os.environ.get('KIS_API_KEY', ''),
    'app_secret': os.environ.get('KIS_SECRET_KEY', ''),
    'access_token': '',
    'environment': 'vps',  # 'real' 또는 'vps'
    'account_no': os.environ.get('KIS_ACCOUNT_NO', ''),
    'is_connected': False
}

@dataclass
class Stock:
    """주식 데이터 클래스"""
    id: int
    name: str
    code: str
    market: str
    sector: str
    current_price: float
    currency: str
    debt_ratio: float
    current_ratio: float
    equity_ratio: float
    credit_rating: str
    roe: float
    roa: float
    operating_margin: float
    profit_margin: float
    revenue_growth: float
    profit_growth: float
    eps_growth: float
    per: float
    pbr: float
    dividend_yield: float
    last_update: str

@dataclass
class InvestmentScore:
    """투자 점수 데이터 클래스"""
    total_score: float
    grade: str
    recommendation: str
    details: Dict[str, float]

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
        if score >= 4.0:
            return 'S'
        elif score >= 3.5:
            return 'A'
        elif score >= 3.0:
            return 'B'
        elif score >= 2.5:
            return 'C'
        else:
            return 'D'
    
    def get_recommendation(self, grade: str, stock: Stock) -> str:
        """등급과 밸류에이션을 기반으로 투자 추천"""
        if grade == 'S' and stock.per <= 20 and stock.pbr <= 3:
            return '적극매수'
        elif grade == 'A' and stock.per <= 25 and stock.pbr <= 4:
            return '매수'
        elif grade == 'B' and stock.per <= 30:
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
        # 경제적 해자 (40%)
        moat_score = 0
        if stock.roe >= 15:
            moat_score += 1.5
        elif stock.roe >= 10:
            moat_score += 1.0
        elif stock.roe >= 8:
            moat_score += 0.5
        
        if stock.revenue_growth >= 10:
            moat_score += 1.0
        elif stock.revenue_growth >= 5:
            moat_score += 0.5
        
        if stock.profit_growth >= 10:
            moat_score += 1.0
        elif stock.profit_growth >= 5:
            moat_score += 0.5
        
        # 경영진 능력 (30%)
        management_score = 0
        if stock.roe >= 15 and stock.equity_ratio >= 70 and stock.debt_ratio <= 30:
            management_score = 2.0
        elif stock.roe >= 10 and stock.equity_ratio >= 60 and stock.debt_ratio <= 40:
            management_score = 1.5
        elif stock.roe >= 8 and stock.equity_ratio >= 50:
            management_score = 1.0
        else:
            management_score = 0.5
        
        # 재무건전성 (30%)
        health_score = 0
        if stock.equity_ratio >= 80 and stock.debt_ratio <= 20 and stock.current_ratio >= 2.0:
            health_score = 2.0
        elif stock.equity_ratio >= 70 and stock.debt_ratio <= 30 and stock.current_ratio >= 1.5:
            health_score = 1.5
        elif stock.equity_ratio >= 60 and stock.debt_ratio <= 40 and stock.current_ratio >= 1.2:
            health_score = 1.0
        else:
            health_score = 0.5
        
        total_score = moat_score + management_score + health_score
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=total_score,
            grade=grade,
            recommendation=recommendation,
            details={
                'moat': moat_score,
                'management': management_score,
                'health': health_score
            }
        )

class LynchStrategy(InvestmentStrategy):
    """피터 린치 성장투자 전략"""
    
    def __init__(self):
        super().__init__(
            name="피터 린치",
            description="PEG 비율 + 매출성장률 + 소비자 친숙도 + 기업규모",
            icon="🚀"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        # 성장성 (50%)
        growth_score = 0
        peg_ratio = stock.per / max(stock.profit_growth, 1) if stock.per > 0 else 0
        if peg_ratio <= 0.5:
            growth_score += 2.0
        elif peg_ratio <= 1.0:
            growth_score += 1.5
        elif peg_ratio <= 1.5:
            growth_score += 1.0
        elif peg_ratio <= 2.0:
            growth_score += 0.5
        
        if stock.revenue_growth >= 20:
            growth_score += 1.5
        elif stock.revenue_growth >= 15:
            growth_score += 1.0
        elif stock.revenue_growth >= 10:
            growth_score += 0.5
        
        # 밸류에이션 (30%)
        valuation_score = 0
        if stock.per <= 15 and stock.pbr <= 3:
            valuation_score = 1.5
        elif stock.per <= 25 and stock.pbr <= 5:
            valuation_score = 1.0
        elif stock.per <= 35:
            valuation_score = 0.5
        
        # 품질 (20%)
        quality_score = 0
        if stock.roe >= 15 and stock.operating_margin >= 10:
            quality_score = 1.0
        elif stock.roe >= 10 and stock.operating_margin >= 5:
            quality_score = 0.7
        elif stock.roe >= 8:
            quality_score = 0.3
        
        total_score = growth_score + valuation_score + quality_score
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=total_score,
            grade=grade,
            recommendation=recommendation,
            details={
                'growth': growth_score,
                'valuation': valuation_score,
                'quality': quality_score
            }
        )

class GrahamStrategy(InvestmentStrategy):
    """벤저민 그레이엄 딥밸류 전략"""
    
    def __init__(self):
        super().__init__(
            name="벤저민 그레이엄",
            description="순유동자산 + 낮은 PER/PBR + 배당 + 재무안정성",
            icon="📚"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        # 가치 (40%)
        value_score = 0
        if stock.per <= 10 and stock.pbr <= 1.5:
            value_score += 2.0
        elif stock.per <= 15 and stock.pbr <= 2.0:
            value_score += 1.5
        elif stock.per <= 20 and stock.pbr <= 2.5:
            value_score += 1.0
        elif stock.per <= 25 and stock.pbr <= 3.0:
            value_score += 0.5
        
        # 안전성 (40%)
        safety_score = 0
        if stock.current_ratio >= 2.0 and stock.debt_ratio <= 30:
            safety_score += 1.5
        elif stock.current_ratio >= 1.5 and stock.debt_ratio <= 50:
            safety_score += 1.0
        elif stock.current_ratio >= 1.2:
            safety_score += 0.5
        
        if stock.roe >= 8 and stock.profit_growth >= 0:
            safety_score += 1.0
        elif stock.roe >= 5:
            safety_score += 0.5
        
        # 배당 (20%)
        dividend_score = 0
        if stock.dividend_yield >= 3.0:
            dividend_score = 1.0
        elif stock.dividend_yield >= 2.0:
            dividend_score = 0.7
        elif stock.dividend_yield >= 1.0:
            dividend_score = 0.3
        
        total_score = value_score + safety_score + dividend_score
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=total_score,
            grade=grade,
            recommendation=recommendation,
            details={
                'value': value_score,
                'safety': safety_score,
                'dividend': dividend_score
            }
        )

class FisherStrategy(InvestmentStrategy):
    """필립 피셔 성장 가치 전략"""
    
    def __init__(self):
        super().__init__(
            name="필립 피셔",
            description="연구개발 투자 + 경영진 능력 + 장기성장 잠재력 + 혁신",
            icon="🔬"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        # 혁신성 (40%)
        innovation_score = 0
        if stock.operating_margin >= 20 and stock.profit_margin >= 15:
            innovation_score += 1.5
        elif stock.operating_margin >= 15 and stock.profit_margin >= 10:
            innovation_score += 1.0
        elif stock.operating_margin >= 10:
            innovation_score += 0.5
        
        if stock.revenue_growth >= 15:
            innovation_score += 1.0
        elif stock.revenue_growth >= 10:
            innovation_score += 0.7
        elif stock.revenue_growth >= 5:
            innovation_score += 0.3
        
        # 성장 (35%)
        growth_score = 0
        if stock.profit_growth >= 20 and stock.eps_growth >= 15:
            growth_score += 1.5
        elif stock.profit_growth >= 15 and stock.eps_growth >= 10:
            growth_score += 1.2
        elif stock.profit_growth >= 10:
            growth_score += 0.8
        elif stock.profit_growth >= 5:
            growth_score += 0.4
        
        # 경영진 (25%)
        management_score = 0
        if stock.roe >= 20 and stock.roa >= 15:
            management_score = 1.2
        elif stock.roe >= 15 and stock.roa >= 10:
            management_score = 1.0
        elif stock.roe >= 12 and stock.roa >= 7:
            management_score = 0.7
        elif stock.roe >= 10:
            management_score = 0.3
        
        total_score = innovation_score + growth_score + management_score
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=total_score,
            grade=grade,
            recommendation=recommendation,
            details={
                'innovation': innovation_score,
                'growth': growth_score,
                'management': management_score
            }
        )

class MungerStrategy(InvestmentStrategy):
    """찰리 멍거 다학문적 투자 전략"""
    
    def __init__(self):
        super().__init__(
            name="찰리 멍거",
            description="간단한 비즈니스 + 경쟁우위 + 합리적 가격 + 장기관점",
            icon="🎯"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        # 단순성 (30%)
        simplicity_score = 0
        roe_trend = 1 if stock.roe >= 12 else 0
        margin_stability = 1 if stock.operating_margin >= 15 else 0
        simplicity_score = (roe_trend + margin_stability) * 1.0
        
        # 경쟁우위 (40%)
        competitive_score = 0
        if stock.roe >= 20 and stock.operating_margin >= 20:
            competitive_score += 1.5
        elif stock.roe >= 15 and stock.operating_margin >= 15:
            competitive_score += 1.2
        elif stock.roe >= 12 and stock.operating_margin >= 10:
            competitive_score += 0.8
        
        if stock.revenue_growth >= 8 and stock.profit_growth >= 8:
            competitive_score += 1.0
        elif stock.revenue_growth >= 5:
            competitive_score += 0.5
        
        # 합리적 가격 (30%)
        rational_score = 0
        if stock.per <= 12 and stock.pbr <= 2.0:
            rational_score = 1.5
        elif stock.per <= 18 and stock.pbr <= 3.0:
            rational_score = 1.0
        elif stock.per <= 25:
            rational_score = 0.5
        
        total_score = simplicity_score + competitive_score + rational_score
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=total_score,
            grade=grade,
            recommendation=recommendation,
            details={
                'simplicity': simplicity_score,
                'competitive': competitive_score,
                'rational': rational_score
            }
        )

class GreenblattStrategy(InvestmentStrategy):
    """조엘 그린블라트 마법공식 전략"""
    
    def __init__(self):
        super().__init__(
            name="조엘 그린블라트",
            description="자본수익률 + 이익수익률 (마법공식: ROC + EY)",
            icon="🪄"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        # 자본수익률 (50%)
        roc_score = 0
        if stock.roa >= 20:
            roc_score = 2.5
        elif stock.roa >= 15:
            roc_score = 2.0
        elif stock.roa >= 12:
            roc_score = 1.5
        elif stock.roa >= 10:
            roc_score = 1.0
        elif stock.roa >= 8:
            roc_score = 0.5
        
        # 이익수익률 (50%)
        earnings_yield_score = 0
        earnings_yield = (100 / stock.per) if stock.per > 0 else 0
        if earnings_yield >= 10:
            earnings_yield_score = 2.5
        elif earnings_yield >= 6.67:
            earnings_yield_score = 2.0
        elif earnings_yield >= 5:
            earnings_yield_score = 1.5
        elif earnings_yield >= 4:
            earnings_yield_score = 1.0
        elif earnings_yield >= 3.33:
            earnings_yield_score = 0.5
        
        total_score = roc_score + earnings_yield_score
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=total_score,
            grade=grade,
            recommendation=recommendation,
            details={
                'roc': roc_score,
                'earnings_yield': earnings_yield_score
            }
        )

# 투자 전략 인스턴스
INVESTMENT_STRATEGIES = {
    'buffett': BuffettStrategy(),
    'lynch': LynchStrategy(),
    'graham': GrahamStrategy(),
    'fisher': FisherStrategy(),
    'munger': MungerStrategy(),
    'greenblatt': GreenblattStrategy()
}

class KISApiManager:
    """한국투자증권 API 관리자"""
    
    def __init__(self, config: dict):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Investment-Screener/1.0'
        })
    
    def get_access_token(self) -> Optional[str]:
        """액세스 토큰 발급"""
        if not self.config['app_key'] or not self.config['app_secret']:
            return None
        
        base_url = self.config['base_url_real'] if self.config['environment'] == 'real' else self.config['base_url_vps']
        url = f"{base_url}/oauth2/tokenP"
        
        data = {
            "grant_type": "client_credentials",
            "appkey": self.config['app_key'],
            "appsecret": self.config['app_secret']
        }
        
        try:
            response = self.session.post(url, json=data, timeout=30)
            result = response.json()
            
            if response.status_code == 200 and 'access_token' in result:
                self.config['access_token'] = result['access_token']
                self.config['is_connected'] = True
                logger.info("KIS API 토큰 발급 성공")
                return result['access_token']
            else:
                logger.error(f"토큰 발급 실패: {result}")
                return None
                
        except Exception as e:
            logger.error(f"토큰 발급 오류: {e}")
            return None
    
    def get_stock_price(self, stock_code: str, market: str) -> Optional[float]:
        """주식 현재가 조회"""
        if not self.config['access_token']:
            if not self.get_access_token():
                return None
        
        base_url = self.config['base_url_real'] if self.config['environment'] == 'real' else self.config['base_url_vps']
        
        # 국내주식과 해외주식 구분
        is_domestic = market in ['KOSPI', 'KOSDAQ']
        
        if is_domestic:
            url = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
            headers = {
                "authorization": f"Bearer {self.config['access_token']}",
                "appkey": self.config['app_key'],
                "appsecret": self.config['app_secret'],
                "tr_id": "FHKST01010100"
            }
            params = {
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": stock_code
            }
        else:
            url = f"{base_url}/uapi/overseas-price/v1/quotations/price"
            headers = {
                "authorization": f"Bearer {self.config['access_token']}",
                "appkey": self.config['app_key'],
                "appsecret": self.config['app_secret'],
                "tr_id": "HHDFS00000300"
            }
            params = {
                "symb": stock_code,
                "excd": self._get_exchange_code(market)
            }
        
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=30)
            result = response.json()
            
            if response.status_code == 200 and result.get('rt_cd') == '0':
                if is_domestic:
                    return float(result['output']['stck_prpr'])
                else:
                    return float(result['output']['last'])
            else:
                logger.warning(f"주식가격 조회 실패 ({stock_code}): {result}")
                return None
                
        except Exception as e:
            logger.error(f"주식가격 조회 오류 ({stock_code}): {e}")
            return None
    
    def _get_exchange_code(self, market: str) -> str:
        """거래소 코드 매핑"""
        codes = {
            'NYSE': 'NYS',
            'NASDAQ': 'NAS',
            'TSE': 'TYO',
            'SEHK': 'HKG'
        }
        return codes.get(market, 'NYS')

# KIS API 매니저 인스턴스
kis_api = KISApiManager(KIS_CONFIG)

# 샘플 데이터
SAMPLE_STOCKS = [
    Stock(
        id=1, name='삼성전자', code='005930', market='KOSPI', sector='반도체',
        current_price=75000, currency='KRW', debt_ratio=15.2, current_ratio=2.1,
        equity_ratio=85.2, credit_rating='AA', roe=18.5, roa=12.3,
        operating_margin=22.1, profit_margin=15.2, revenue_growth=8.5,
        profit_growth=12.3, eps_growth=15.2, per=12.5, pbr=1.2,
        dividend_yield=2.8, last_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ),
    Stock(
        id=2, name='네이버', code='035420', market='KOSPI', sector='IT서비스',
        current_price=210000, currency='KRW', debt_ratio=8.5, current_ratio=2.8,
        equity_ratio=88.5, credit_rating='AA-', roe=22.5, roa=18.2,
        operating_margin=28.5, profit_margin=20.1, revenue_growth=15.2,
        profit_growth=18.5, eps_growth=22.1, per=18.5, pbr=2.1,
        dividend_yield=1.8, last_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ),
    Stock(
        id=3, name='SK하이닉스', code='000660', market='KOSPI', sector='반도체',
        current_price=115000, currency='KRW', debt_ratio=22.1, current_ratio=1.8,
        equity_ratio=72.5, credit_rating='A+', roe=16.2, roa=11.8,
        operating_margin=18.5, profit_margin=12.8, revenue_growth=12.5,
        profit_growth=15.8, eps_growth=18.2, per=14.2, pbr=1.8,
        dividend_yield=2.2, last_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ),
    Stock(
        id=4, name='Apple Inc.', code='AAPL', market='NASDAQ', sector='기술',
        current_price=185.25, currency='USD', debt_ratio=31.2, current_ratio=1.0,
        equity_ratio=68.8, credit_rating='AA+', roe=28.5, roa=18.9,
        operating_margin=29.8, profit_margin=24.3, revenue_growth=11.2,
        profit_growth=16.8, eps_growth=19.5, per=24.2, pbr=5.8,
        dividend_yield=0.5, last_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ),
    Stock(
        id=5, name='Microsoft Corp.', code='MSFT', market='NASDAQ', sector='기술',
        current_price=378.85, currency='USD', debt_ratio=18.5, current_ratio=1.9,
        equity_ratio=81.5, credit_rating='AAA', roe=35.2, roa=22.1,
        operating_margin=41.5, profit_margin=35.8, revenue_growth=18.5,
        profit_growth=24.2, eps_growth=28.5, per=28.5, pbr=8.2,
        dividend_yield=0.7, last_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ),
    Stock(
        id=6, name='Toyota Motor', code='7203', market='TSE', sector='자동차',
        current_price=2485, currency='JPY', debt_ratio=55.2, current_ratio=1.1,
        equity_ratio=44.8, credit_rating='AA-', roe=10.8, roa=4.5,
        operating_margin=9.2, profit_margin=7.8, revenue_growth=12.8,
        profit_growth=18.5, eps_growth=22.1, per=11.5, pbr=1.2,
        dividend_yield=2.8, last_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ),
    Stock(
        id=7, name='Alibaba Group', code='9988', market='SEHK', sector='IT서비스',
        current_price=85.50, currency='HKD', debt_ratio=22.5, current_ratio=1.8,
        equity_ratio=77.5, credit_rating='A+', roe=12.8, roa=8.5,
        operating_margin=18.5, profit_margin=15.2, revenue_growth=9.2,
        profit_growth=12.5, eps_growth=15.8, per=14.8, pbr=2.1,
        dividend_yield=0.0, last_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ),
]

# 시장 정보
MARKET_INFO = {
    'KOSPI': {'name': 'KOSPI', 'flag': '🇰🇷', 'currency': 'KRW', 'type': 'domestic'},
    'KOSDAQ': {'name': 'KOSDAQ', 'flag': '🇰🇷', 'currency': 'KRW', 'type': 'domestic'},
    'NYSE': {'name': 'NYSE', 'flag': '🇺🇸', 'currency': 'USD', 'type': 'us'},
    'NASDAQ': {'name': 'NASDAQ', 'flag': '🇺🇸', 'currency': 'USD', 'type': 'us'},
    'TSE': {'name': 'TSE', 'flag': '🇯🇵', 'currency': 'JPY', 'type': 'global'},
    'SEHK': {'name': '홍콩거래소', 'flag': '🇭🇰', 'currency': 'HKD', 'type': 'global'}
}

# 통화 심볼
CURRENCY_SYMBOLS = {
    'KRW': '₩',
    'USD': '$',
    'JPY': '¥',
    'CNY': '¥',
    'HKD': 'HK$'
}

def cache_response(timeout=300):
    """응답 캐싱 데코레이터"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 간단한 메모리 캐싱 (실제로는 Redis 등 사용 권장)
            cache_key = f"{f.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            
            if not hasattr(wrapper, 'cache'):
                wrapper.cache = {}
            
            now = time.time()
            if cache_key in wrapper.cache:
                data, timestamp = wrapper.cache[cache_key]
                if now - timestamp < timeout:
                    return data
            
            result = f(*args, **kwargs)
            wrapper.cache[cache_key] = (result, now)
            return result
        
        return wrapper
    return decorator

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    return jsonify({'error': '파일 크기가 너무 큽니다. 16MB 이하로 업로드해주세요.'}), 413

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return render_template('500.html'), 500

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html', 
                         strategies=INVESTMENT_STRATEGIES,
                         market_info=MARKET_INFO)

@app.route('/api/config', methods=['POST'])
def save_config():
    """KIS API 설정 저장"""
    try:
        data = request.get_json()
        
        KIS_CONFIG['app_key'] = data.get('appKey', '')
        KIS_CONFIG['app_secret'] = data.get('appSecret', '')
        KIS_CONFIG['environment'] = data.get('environment', 'vps')
        KIS_CONFIG['account_no'] = data.get('accountNo', '')
        
        # 세션에 설정 저장
        session['kis_config'] = {
            'environment': KIS_CONFIG['environment'],
            'account_no': KIS_CONFIG['account_no']
        }
        
        return jsonify({
            'success': True, 
            'message': 'KIS API 설정이 저장되었습니다.'
        })
        
    except Exception as e:
        logger.error(f"Config save error: {e}")
        return jsonify({
            'success': False, 
            'message': f'설정 저장 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """KIS API 연결 테스트"""
    try:
        data = request.get_json()
        
        # 임시로 설정 업데이트
        old_config = KIS_CONFIG.copy()
        KIS_CONFIG['app_key'] = data.get('appKey', '')
        KIS_CONFIG['app_secret'] = data.get('appSecret', '')
        KIS_CONFIG['environment'] = data.get('environment', 'vps')
        
        if not KIS_CONFIG['app_key'] or not KIS_CONFIG['app_secret']:
            return jsonify({
                'success': False, 
                'message': 'App Key와 App Secret을 입력해주세요.'
            }), 400
        
        # 토큰 발급 테스트
        token = kis_api.get_access_token()
        
        if token:
            env_text = '실전투자' if KIS_CONFIG['environment'] == 'real' else '모의투자'
            return jsonify({
                'success': True,
                'message': f'KIS {env_text} API 연결 성공!',
                'token': token[:20] + '...',
                'environment': KIS_CONFIG['environment']
            })
        else:
            # 실패 시 원래 설정 복원
            KIS_CONFIG.update(old_config)
            return jsonify({
                'success': False, 
                'message': 'API 연결에 실패했습니다. App Key/Secret을 확인해주세요.'
            }), 400
            
    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return jsonify({
            'success': False, 
            'message': f'연결 테스트 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/stocks')
@cache_response(timeout=60)
def get_stocks():
    """종목 목록 조회"""
    try:
        style = request.args.get('style', 'buffett')
        market = request.args.get('market', 'all')
        limit = int(request.args.get('limit', 10))
        
        stocks = SAMPLE_STOCKS.copy()
        
        # 시장 필터링
        if market != 'all':
            if market == 'domestic':
                stocks = [s for s in stocks if MARKET_INFO[s.market]['type'] == 'domestic']
            elif market == 'us':
                stocks = [s for s in stocks if MARKET_INFO[s.market]['type'] == 'us']
            elif market == 'global':
                stocks = [s for s in stocks if MARKET_INFO[s.market]['type'] == 'global']
        
        # 투자 점수 계산
        strategy = INVESTMENT_STRATEGIES.get(style, INVESTMENT_STRATEGIES['buffett'])
        analyzed_stocks = []
        
        for stock in stocks:
            try:
                score = strategy.calculate_score(stock)
                analyzed_stock = {
                    **asdict(stock),
                    'investment_score': asdict(score)
                }
                analyzed_stocks.append(analyzed_stock)
            except Exception as e:
                logger.warning(f"Score calculation failed for {stock.name}: {e}")
                continue
        
        # 점수순 정렬
        analyzed_stocks.sort(key=lambda x: x['investment_score']['total_score'], reverse=True)
        
        # 제한된 수만 반환
        if limit > 0:
            analyzed_stocks = analyzed_stocks[:limit]
        
        # 요약 통계 계산
        summary = calculate_summary(analyzed_stocks, market)
        
        return jsonify({
            'success': True,
            'stocks': analyzed_stocks,
            'summary': summary,
            'strategy': {
                'name': strategy.name,
                'description': strategy.description,
                'icon': strategy.icon
            },
            'market_filter': market,
            'total_analyzed': len(analyzed_stocks)
        })
        
    except Exception as e:
        logger.error(f"Get stocks error: {e}")
        return jsonify({
            'success': False,
            'message': f'종목 조회 중 오류가 발생했습니다: {str(e)}'
        }), 500

def calculate_summary(stocks: List[dict], market_filter: str) -> dict:
    """요약 통계 계산"""
    if not stocks:
        return {
            'total_stocks': 0,
            'displayed_stocks': 0,
            's_grade_stocks': 0,
            'buy_recommendations': 0,
            'current_market': get_market_text(market_filter),
            'avg_score': 0.0
        }
    
    s_grade_count = sum(1 for s in stocks if s['investment_score']['grade'] == 'S')
    buy_count = sum(1 for s in stocks if s['investment_score']['recommendation'] in ['적극매수', '매수'])
    avg_score = sum(s['investment_score']['total_score'] for s in stocks) / len(stocks)
    
    return {
        'total_stocks': len(stocks),
        'displayed_stocks': len(stocks),
        's_grade_stocks': s_grade_count,
        'buy_recommendations': buy_count,
        'current_market': get_market_text(market_filter),
        'avg_score': round(avg_score, 1)
    }

def get_market_text(market_filter: str) -> str:
    """시장 필터 텍스트 반환"""
    market_texts = {
        'all': '🌍 전체',
        'domestic': '🇰🇷 국내',
        'us': '🇺🇸 미국',
        'global': '🌍 해외'
    }
    return market_texts.get(market_filter, '🌍 전체')

@app.route('/api/update-price/<stock_code>')
def update_single_price(stock_code):
    """개별 종목 가격 업데이트"""
    try:
        if not KIS_CONFIG['is_connected']:
            return jsonify({
                'success': False, 
                'message': 'KIS API가 연결되지 않았습니다. 먼저 API 설정을 완료해주세요.'
            }), 400
        
        # 해당 종목 찾기
        stock = None
        for s in SAMPLE_STOCKS:
            if s.code == stock_code:
                stock = s
                break
        
        if not stock:
            return jsonify({
                'success': False, 
                'message': '종목을 찾을 수 없습니다.'
            }), 404
        
        # KIS API로 가격 조회
        new_price = kis_api.get_stock_price(stock_code, stock.market)
        
        if new_price:
            stock.current_price = new_price
            stock.last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return jsonify({
                'success': True,
                'message': f"{stock.name} 가격이 업데이트되었습니다.",
                'stock': {
                    'code': stock.code,
                    'name': stock.name,
                    'new_price': new_price,
                    'currency': stock.currency,
                    'last_update': stock.last_update
                }
            })
        else:
            return jsonify({
                'success': False, 
                'message': '가격 조회에 실패했습니다. API 연결 상태를 확인해주세요.'
            }), 500
            
    except Exception as e:
        logger.error(f"Update price error for {stock_code}: {e}")
        return jsonify({
            'success': False, 
            'message': f'가격 업데이트 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/update-all-prices')
def update_all_prices():
    """전체 종목 가격 업데이트"""
    try:
        if not KIS_CONFIG['is_connected']:
            return jsonify({
                'success': False, 
                'message': 'KIS API가 연결되지 않았습니다. 먼저 API 설정을 완료해주세요.'
            }), 400
        
        success_count = 0
        fail_count = 0
        updated_stocks = []
        
        for stock in SAMPLE_STOCKS:
            try:
                new_price = kis_api.get_stock_price(stock.code, stock.market)
                if new_price:
                    old_price = stock.current_price
                    stock.current_price = new_price
                    stock.last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    success_count += 1
                    
                    updated_stocks.append({
                        'code': stock.code,
                        'name': stock.name,
                        'old_price': old_price,
                        'new_price': new_price,
                        'change': new_price - old_price,
                        'change_percent': ((new_price - old_price) / old_price) * 100 if old_price > 0 else 0
                    })
                else:
                    fail_count += 1
                
                # API 호출 제한을 위한 딜레이
                time.sleep(0.2)
                
            except Exception as e:
                logger.warning(f"Failed to update price for {stock.name}: {e}")
                fail_count += 1
        
        return jsonify({
            'success': True,
            'message': f'업데이트 완료: 성공 {success_count}개, 실패 {fail_count}개',
            'success_count': success_count,
            'fail_count': fail_count,
            'updated_stocks': updated_stocks
        })
        
    except Exception as e:
        logger.error(f"Update all prices error: {e}")
        return jsonify({
            'success': False, 
            'message': f'전체 가격 업데이트 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/add-stock', methods=['POST'])
def add_stock():
    """새 종목 추가"""
    try:
        data = request.get_json()
        
        # 필수 필드 검증
        required_fields = ['name', 'code', 'market', 'sector']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'{field} 필드는 필수입니다.'
                }), 400
        
        # 중복 종목 코드 확인
        if any(s.code == data['code'] for s in SAMPLE_STOCKS):
            return jsonify({
                'success': False,
                'message': '이미 존재하는 종목 코드입니다.'
            }), 400
        
        # 새 종목 생성
        new_stock = Stock(
            id=max([s.id for s in SAMPLE_STOCKS], default=0) + 1,
            name=data['name'],
            code=data['code'],
            market=data['market'],
            sector=data['sector'],
            current_price=float(data.get('current_price', 100000)),
            currency=data.get('currency', 'KRW'),
            debt_ratio=float(data.get('debt_ratio', 20)),
            current_ratio=float(data.get('current_ratio', 2.0)),
            equity_ratio=100 - float(data.get('debt_ratio', 20)),
            credit_rating='A',
            roe=float(data.get('roe', 15)),
            roa=float(data.get('roa', 10)),
            operating_margin=20,
            profit_margin=15,
            revenue_growth=10,
            profit_growth=12,
            eps_growth=15,
            per=float(data.get('per', 15)),
            pbr=float(data.get('pbr', 2.0)),
            dividend_yield=2.5,
            last_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        SAMPLE_STOCKS.append(new_stock)
        
        return jsonify({
            'success': True,
            'message': f"{new_stock.name}이(가) 성공적으로 추가되었습니다.",
            'stock': asdict(new_stock)
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': f'잘못된 숫자 형식입니다: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Add stock error: {e}")
        return jsonify({
            'success': False,
            'message': f'종목 추가 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/export-stocks')
def export_stocks():
    """종목 데이터 CSV 내보내기"""
    try:
        style = request.args.get('style', 'buffett')
        market = request.args.get('market', 'all')
        
        # 종목 데이터 가져오기
        response_data = get_stocks()
        if isinstance(response_data, tuple):  # 에러 응답인 경우
            return response_data
        
        stocks_data = response_data.get_json()['stocks']
        
        # DataFrame 생성
        df_data = []
        for stock in stocks_data:
            score = stock['investment_score']
            df_data.append({
                '순위': stocks_data.index(stock) + 1,
                '종목명': stock['name'],
                '종목코드': stock['code'],
                '시장': stock['market'],
                '섹터': stock['sector'],
                '현재가': stock['current_price'],
                '통화': stock['currency'],
                'ROE(%)': stock['roe'],
                'ROA(%)': stock['roa'],
                'PER': stock['per'],
                'PBR': stock['pbr'],
                '부채비율(%)': stock['debt_ratio'],
                '유동비율': stock['current_ratio'],
                '매출성장률(%)': stock['revenue_growth'],
                '순이익성장률(%)': stock['profit_growth'],
                '배당수익률(%)': stock['dividend_yield'],
                '종합점수': score['total_score'],
                '등급': score['grade'],
                '투자의견': score['recommendation'],
                '업데이트': stock['last_update']
            })
        
        df = pd.DataFrame(df_data)
        
        # CSV 파일로 변환
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"investment_screener_{style}_{market}_{timestamp}.csv"
        
        # 한글 인코딩 처리
        csv_data = df.to_csv(index=False, encoding='utf-8-sig')
        
        from flask import make_response
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({
            'success': False,
            'message': f'데이터 내보내기 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/strategies')
def get_strategies():
    """투자 전략 목록 조회"""
    strategies_info = {}
    for key, strategy in INVESTMENT_STRATEGIES.items():
        strategies_info[key] = {
            'name': strategy.name,
            'description': strategy.description,
            'icon': strategy.icon
        }
    
    return jsonify({
        'success': True,
        'strategies': strategies_info
    })

@app.route('/health')
def health_check():
    """헬스 체크 엔드포인트"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'kis_api_connected': KIS_CONFIG['is_connected']
    })

if __name__ == '__main__':
    # 개발 모드 실행
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print("=" * 60)
    print("🚀 한국투자증권 KIS API 투자 거장 스크리너")
    print("=" * 60)
    print(f"📌 브라우저에서 http://localhost:{port} 으로 접속하세요!")
    print("🔑 KIS Developers에서 App Key/Secret 발급 후 사용 가능")
    print("🌐 API 신청: https://apiportal.koreainvestment.com")
    print("💡 샘플 데이터 모드로 먼저 테스트해보세요!")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=debug)