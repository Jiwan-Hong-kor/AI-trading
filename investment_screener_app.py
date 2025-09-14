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

from flask import Flask, render_template_string, request, jsonify, session, make_response
from flask_cors import CORS
import pandas as pd

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask 애플리케이션 설정
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'investment-screener-secret-key-2024')
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

# HTML 템플릿 (인라인)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>한국투자증권 KIS 투자 거장 스크리너</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #1e40af;
            --secondary-color: #3b82f6;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
            --dark-color: #1f2937;
        }

        body {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
        }

        .main-container {
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
            margin: 20px auto;
            max-width: 1600px;
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, var(--primary-color) 0%, #1e3a8a 100%);
            color: white;
            padding: 30px;
            text-align: center;
            position: relative;
        }

        .kis-logo {
            position: absolute;
            left: 30px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 28px;
            font-weight: bold;
            color: #fbbf24;
        }

        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }

        .header p {
            opacity: 0.9;
            font-size: 1.1rem;
            margin: 0;
        }

        .controls-section {
            background: #f8fafc;
            padding: 25px;
            border-bottom: 2px solid #e2e8f0;
        }

        .market-selection {
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            border: 2px solid #93c5fd;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 25px;
        }

        .market-title {
            color: var(--primary-color);
            font-weight: 600;
            margin-bottom: 15px;
            text-align: center;
        }

        .market-buttons {
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
        }

        .market-btn {
            background: white;
            border: 2px solid #93c5fd;
            border-radius: 8px;
            padding: 10px 15px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 600;
            color: var(--primary-color);
            display: flex;
            align-items: center;
            gap: 5px;
            min-width: 120px;
            justify-content: center;
        }

        .market-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(59,130,246,0.3);
            border-color: var(--secondary-color);
        }

        .market-btn.active {
            background: var(--secondary-color);
            color: white;
            border-color: var(--secondary-color);
            box-shadow: 0 4px 12px rgba(59,130,246,0.4);
        }

        .investor-selection {
            background: #f8fafc;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 25px;
        }

        .investor-title {
            color: var(--dark-color);
            font-weight: 600;
            margin-bottom: 15px;
            text-align: center;
        }

        .investor-buttons {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            max-width: 1200px;
            margin: 0 auto;
        }

        .investor-btn {
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            text-align: center;
            min-height: 120px;
        }

        .investor-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            border-color: var(--secondary-color);
        }

        .investor-btn.active {
            background: linear-gradient(135deg, var(--secondary-color) 0%, var(--primary-color) 100%);
            color: white;
            border-color: var(--secondary-color);
            box-shadow: 0 8px 25px rgba(59,130,246,0.4);
        }

        .investor-icon {
            font-size: 2.5rem;
            margin-bottom: 8px;
        }

        .investor-name {
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 4px;
        }

        .investor-subtitle {
            font-size: 0.85rem;
            opacity: 0.8;
            font-weight: 500;
        }

        .control-buttons {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
            justify-content: center;
            margin-top: 20px;
        }

        .btn-custom {
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .btn-primary-custom {
            background: var(--primary-color);
            border: none;
            color: white;
        }

        .btn-primary-custom:hover {
            background: #1e3a8a;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(30,64,175,0.4);
        }

        .btn-success-custom {
            background: var(--success-color);
            border: none;
            color: white;
        }

        .btn-success-custom:hover {
            background: #059669;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(16,185,129,0.4);
        }

        .btn-warning-custom {
            background: var(--warning-color);
            border: none;
            color: white;
        }

        .btn-warning-custom:hover {
            background: #d97706;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(245,158,11,0.4);
        }

        .api-status {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 16px;
            border-radius: 8px;
            font-weight: 600;
            background: #fef2f2;
            color: #991b1b;
            border: 2px solid #fecaca;
        }

        .api-status.connected {
            background: #f0fdf4;
            color: #166534;
            border-color: #bbf7d0;
        }

        .summary-section {
            background: #f8fafc;
            padding: 25px;
            border-bottom: 1px solid #e2e8f0;
        }

        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            border-left: 4px solid var(--secondary-color);
            transition: transform 0.3s ease;
        }

        .summary-card:hover {
            transform: translateY(-2px);
        }

        .summary-card h6 {
            color: #6b7280;
            font-size: 0.875rem;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .summary-card .value {
            font-size: 1.875rem;
            font-weight: 700;
            color: var(--dark-color);
            margin: 0;
        }

        .results-section {
            padding: 30px;
        }

        .results-header {
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }

        .results-title {
            color: var(--dark-color);
            font-size: 1.5rem;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .results-subtitle {
            color: #6b7280;
            margin: 0;
        }

        .investor-description {
            background: #eff6ff;
            border: 1px solid #93c5fd;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
            color: var(--primary-color);
            font-weight: 500;
        }

        .table-responsive {
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }

        .table {
            margin: 0;
            background: white;
        }

        .table thead th {
            background: linear-gradient(135deg, #374151 0%, #4b5563 100%);
            color: white;
            border: none;
            padding: 15px 10px;
            font-weight: 600;
            font-size: 0.875rem;
            text-align: center;
            position: sticky;
            top: 0;
            z-index: 10;
        }

        .table thead th.group-header {
            background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
        }

        .table tbody td {
            padding: 12px 10px;
            border-color: #f3f4f6;
            text-align: center;
            font-size: 0.875rem;
            vertical-align: middle;
        }

        .table tbody tr:hover {
            background: #f9fafb;
        }

        .grade-S { 
            background: #dbeafe; 
            color: #1e40af; 
            font-weight: bold; 
            padding: 4px 8px; 
            border-radius: 4px;
        }

        .grade-A { 
            background: #dcfce7; 
            color: #166534; 
            font-weight: bold; 
            padding: 4px 8px; 
            border-radius: 4px;
        }

        .grade-B { 
            background: #fef3c7; 
            color: #92400e; 
            font-weight: bold; 
            padding: 4px 8px; 
            border-radius: 4px;
        }

        .grade-C { 
            background: #fce7f3; 
            color: #be185d; 
            padding: 4px 8px; 
            border-radius: 4px;
        }

        .grade-D { 
            background: #fee2e2; 
            color: #dc2626; 
            padding: 4px 8px; 
            border-radius: 4px;
        }

        .positive { color: var(--success-color); font-weight: 600; }
        .negative { color: var(--danger-color); font-weight: 600; }
        .neutral { color: #6b7280; }

        .recommendation-buy { 
            background: #dcfce7; 
            color: #166534; 
            font-weight: bold; 
            padding: 6px 12px; 
            border-radius: 6px; 
        }

        .recommendation-hold { 
            background: #fef3c7; 
            color: #92400e; 
            font-weight: bold; 
            padding: 6px 12px; 
            border-radius: 6px; 
        }

        .recommendation-sell { 
            background: #fee2e2; 
            color: #dc2626; 
            font-weight: bold; 
            padding: 6px 12px; 
            border-radius: 6px; 
        }

        .rank-badge {
            background: var(--secondary-color);
            color: white;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            margin-bottom: 4px;
            display: inline-block;
        }

        .loading-spinner {
            display: none;
            text-align: center;
            padding: 40px;
        }

        .modal-content {
            border-radius: 12px;
            border: none;
        }

        .modal-header {
            background: var(--primary-color);
            color: white;
            border-radius: 12px 12px 0 0;
        }

        .btn-close {
            filter: invert(1);
        }

        .search-section {
            background: white;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }

        @media (max-width: 768px) {
            .main-container {
                margin: 10px;
                border-radius: 10px;
            }
            
            .header {
                padding: 20px 15px;
            }
            
            .kis-logo {
                position: static;
                transform: none;
                margin-bottom: 10px;
            }
            
            .header h1 {
                font-size: 1.75rem;
            }
            
            .investor-buttons {
                grid-template-columns: repeat(2, 1fr);
                gap: 10px;
            }
            
            .investor-btn {
                min-height: 100px;
                padding: 15px 10px;
            }
            
            .investor-icon {
                font-size: 2rem;
            }
            
            .investor-name {
                font-size: 0.9rem;
            }
            
            .market-buttons {
                gap: 5px;
            }
            
            .market-btn {
                min-width: 100px;
                padding: 8px 12px;
                font-size: 0.875rem;
            }
            
            .control-buttons {
                flex-direction: column;
                align-items: stretch;
            }
            
            .btn-custom {
                justify-content: center;
            }
        }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="main-container">
            <!-- 헤더 -->
            <div class="header">
                <div class="kis-logo">KIS</div>
                <h1><i class="fas fa-chart-line"></i> 한국투자증권 투자 거장 스크리너</h1>
                <p>KIS Developers API 기반 · 워렌 버핏부터 조엘 그린블라트까지 6대 투자 철학으로 종목 분석</p>
            </div>

            <!-- 컨트롤 섹션 -->
            <div class="controls-section">
                <!-- 시장 선택 -->
                <div class="market-selection">
                    <h5 class="market-title">
                        <i class="fas fa-globe-americas"></i> 투자 시장 선택 (KIS Developers 지원)
                    </h5>
                    <p class="text-center text-muted mb-3">국내주식과 해외주식을 한국투자증권 API로 실시간 분석</p>
                    <div class="market-buttons">
                        <button class="market-btn active" data-market="all" onclick="selectMarket('all')">
                            <span>🌍</span> 전체 시장
                        </button>
                        <button class="market-btn" data-market="domestic" onclick="selectMarket('domestic')">
                            <span>🇰🇷</span> 국내주식
                        </button>
                        <button class="market-btn" data-market="us" onclick="selectMarket('us')">
                            <span>🇺🇸</span> 미국주식
                        </button>
                        <button class="market-btn" data-market="global" onclick="selectMarket('global')">
                            <span>🌏</span> 해외주식
                        </button>
                    </div>
                </div>

                <!-- 투자자 선택 -->
                <div class="investor-selection">
                    <h5 class="investor-title">
                        <i class="fas fa-users"></i> 투자 거장 선택
                    </h5>
                    <p class="text-center text-muted mb-3">클릭하여 해당 투자 철학 기준으로 종목을 분석하세요</p>
                    <div class="investor-buttons">
                        <button class="investor-btn active" data-investor="buffett" onclick="selectInvestor('buffett')">
                            <div class="investor-icon">👑</div>
                            <div class="investor-name">워렌 버핏</div>
                            <div class="investor-subtitle">가치투자</div>
                        </button>
                        <button class="investor-btn" data-investor="lynch" onclick="selectInvestor('lynch')">
                            <div class="investor-icon">🚀</div>
                            <div class="investor-name">피터 린치</div>
                            <div class="investor-subtitle">성장주</div>
                        </button>
                        <button class="investor-btn" data-investor="graham" onclick="selectInvestor('graham')">
                            <div class="investor-icon">📚</div>
                            <div class="investor-name">벤저민 그레이엄</div>
                            <div class="investor-subtitle">딥밸류</div>
                        </button>
                        <button class="investor-btn" data-investor="fisher" onclick="selectInvestor('fisher')">
                            <div class="investor-icon">🔬</div>
                            <div class="investor-name">필립 피셔</div>
                            <div class="investor-subtitle">성장 가치</div>
                        </button>
                        <button class="investor-btn" data-investor="munger" onclick="selectInvestor('munger')">
                            <div class="investor-icon">🎯</div>
                            <div class="investor-name">찰리 멍거</div>
                            <div class="investor-subtitle">우량기업</div>
                        </button>
                        <button class="investor-btn" data-investor="greenblatt" onclick="selectInvestor('greenblatt')">
                            <div class="investor-icon">🪄</div>
                            <div class="investor-name">조엘 그린블라트</div>
                            <div class="investor-subtitle">마법공식</div>
                        </button>
                    </div>
                </div>

                <!-- 컨트롤 버튼들 -->
                <div class="control-buttons">
                    <button class="btn btn-primary-custom" onclick="openKisApiModal()">
                        <i class="fas fa-link"></i> KIS API 연동
                    </button>
                    <button class="btn btn-success-custom" id="updateBtn" onclick="updateAllPrices()">
                        <i class="fas fa-sync-alt"></i> 실시간 업데이트
                    </button>
                    <button class="btn btn-warning-custom" onclick="showInvestmentCriteria()">
                        <i class="fas fa-book"></i> 투자 기준
                    </button>
                    <button class="btn btn-primary-custom" onclick="exportData()">
                        <i class="fas fa-download"></i> 데이터 내보내기
                    </button>
                    <div class="api-status" id="apiStatus">
                        <span class="status-icon">🔴</span>
                        <span>KIS API 연결 안됨</span>
                    </div>
                </div>
            </div>

            <!-- 요약 섹션 -->
            <div class="summary-section">
                <div class="search-section">
                    <div class="input-group" style="max-width: 300px;">
                        <input type="text" class="form-control" id="stockSearch" placeholder="종목명 또는 코드 검색...">
                        <button class="btn btn-outline-secondary" type="button" onclick="searchStocks()">
                            <i class="fas fa-search"></i>
                        </button>
                    </div>
                    <select class="form-select" style="max-width: 200px;" id="limitSelect" onchange="updateResults()">
                        <option value="10">상위 10개</option>
                        <option value="20">상위 20개</option>
                        <option value="50">상위 50개</option>
                        <option value="0">전체 보기</option>
                    </select>
                </div>

                <div class="summary-cards" id="summaryCards">
                    <div class="summary-card">
                        <h6>분석 종목 수</h6>
                        <div class="value" id="totalStocks">0</div>
                    </div>
                    <div class="summary-card">
                        <h6>표시 중인 종목</h6>
                        <div class="value" id="displayedStocks">0</div>
                    </div>
                    <div class="summary-card">
                        <h6>S급 종목</h6>
                        <div class="value" id="sGradeStocks">0</div>
                    </div>
                    <div class="summary-card">
                        <h6>매수 추천</h6>
                        <div class="value" id="buyRecommendations">0</div>
                    </div>
                    <div class="summary-card">
                        <h6>현재 시장</h6>
                        <div class="value" id="currentMarket">🌍 전체</div>
                    </div>
                    <div class="summary-card">
                        <h6>평균 종합점수</h6>
                        <div class="value" id="avgScore">0.0</div>
                    </div>
                </div>
            </div>

            <!-- 결과 섹션 -->
            <div class="results-section">
                <div class="results-header">
                    <h2 class="results-title" id="resultsTitle">
                        <span>👑</span> 워렌 버핏 기준 상위 10개 추천 종목
                    </h2>
                    <p class="results-subtitle" id="resultsSubtitle">종합점수 기준으로 선별된 최고의 투자 기회</p>
                    <div class="investor-description" id="investorDescription">
                        <strong>워렌 버핏 철학:</strong> 경제적 해자 + 뛰어난 경영진 + 재무건전성 + 합리적 가격
                    </div>
                </div>

                <div class="loading-spinner" id="loadingSpinner">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">로딩 중...</span>
                    </div>
                    <p class="mt-3">투자 분석 중입니다...</p>
                </div>

                <div class="table-responsive">
                    <table class="table">
                        <thead>
                            <tr>
                                <th rowspan="2">순위</th>
                                <th rowspan="2">종목명</th>
                                <th rowspan="2">시장</th>
                                <th rowspan="2">섹터</th>
                                <th rowspan="2">현재가</th>
                                <th class="group-header" colspan="4">재무건전성</th>
                                <th class="group-header" colspan="4">수익성지표</th>
                                <th class="group-header" colspan="3">성장성</th>
                                <th class="group-header" colspan="3">밸류에이션</th>
                                <th class="group-header" colspan="3">투자평가</th>
                                <th rowspan="2">액션</th>
                            </tr>
                            <tr>
                                <th>부채비율</th>
                                <th>유동비율</th>
                                <th>자기자본비율</th>
                                <th>신용등급</th>
                                <th>ROE</th>
                                <th>ROA</th>
                                <th>영업이익률</th>
                                <th>순이익률</th>
                                <th>매출성장률</th>
                                <th>순이익성장률</th>
                                <th>EPS성장률</th>
                                <th>PER</th>
                                <th>PBR</th>
                                <th>배당수익률</th>
                                <th>종합점수</th>
                                <th>등급</th>
                                <th>투자의견</th>
                            </tr>
                        </thead>
                        <tbody id="stockTableBody">
                            <!-- 데이터가 여기에 동적으로 삽입됩니다 -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- KIS API 설정 모달 -->
    <div class="modal fade" id="kisApiModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">
                        <i class="fas fa-link"></i> 한국투자증권 API 연동 설정
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="alert alert-info">
                        <h6><i class="fas fa-info-circle"></i> KIS Developers API 정보</h6>
                        <ul class="mb-0">
                            <li><strong>서비스 신청:</strong> <a href="https://apiportal.koreainvestment.com" target="_blank">apiportal.koreainvestment.com</a></li>
                            <li><strong>지원 기능:</strong> REST API, WebSocket 실시간 시세</li>
                            <li><strong>인증 방식:</strong> OAuth 2.0 (App Key + App Secret)</li>
                            <li><strong>지원 상품:</strong> 국내주식, 해외주식, 선물옵션</li>
                        </ul>
                    </div>

                    <form id="kisApiForm">
                        <div class="mb-3">
                            <label class="form-label">환경 선택</label>
                            <select class="form-select" id="kisEnvironment">
                                <option value="vps">모의투자 (VPS)</option>
                                <option value="real">실전투자 (REAL)</option>
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label">App Key *</label>
                            <input type="password" class="form-control" id="kisAppKey" 
                                   placeholder="KIS Developers에서 발급받은 App Key">
                        </div>

                        <div class="mb-3">
                            <label class="form-label">App Secret *</label>
                            <input type="password" class="form-control" id="kisAppSecret" 
                                   placeholder="KIS Developers에서 발급받은 App Secret">
                        </div>

                        <div class="mb-3">
                            <label class="form-label">계좌번호 (선택)</label>
                            <input type="text" class="form-control" id="kisAccountNo" 
                                   placeholder="종합계좌번호 8자리-상품코드 2자리 (예: 50000000-01)">
                        </div>

                        <div class="d-flex gap-2">
                            <button type="button" class="btn btn-primary" onclick="testKisConnection()">
                                <i class="fas fa-plug"></i> 연결 테스트
                            </button>
                            <button type="button" class="btn btn-success" onclick="saveKisConfig()">
                                <i class="fas fa-save"></i> 설정 저장
                            </button>
                            <a href="https://apiportal.koreainvestment.com" target="_blank" class="btn btn-outline-primary">
                                <i class="fas fa-external-link-alt"></i> KIS 포털
                            </a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <!-- 투자 기준 모달 -->
    <div class="modal fade" id="criteriaModal" tabindex="-1">
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">
                        <i class="fas fa-book"></i> 투자 거장별 분석 기준
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">
                    <div class="row">
                        <div class="col-md-6 mb-4">
                            <div class="card">
                                <div class="card-header">
                                    <h6>👑 워렌 버핏 - 가치투자의 황제</h6>
                                </div>
                                <div class="card-body">
                                    <p><strong>투자 철학:</strong> "훌륭한 기업을 합리적인 가격에 사서 영원히 보유하라"</p>
                                    <ul>
                                        <li>경제적 해자: ROE 15%↑, 지속적인 성장</li>
                                        <li>뛰어난 경영진: 높은 자기자본비율, 낮은 부채</li>
                                        <li>재무건전성: 유동비율 2.0↑, 안정적 현금흐름</li>
                                        <li>합리적 가격: PER 20배 이하, 안전마진</li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <div class="col-md-6 mb-4">
                            <div class="card">
                                <div class="card-header">
                                    <h6>🚀 피터 린치 - 성장주 투자의 대가</h6>
                                </div>
                                <div class="card-body">
                                    <p><strong>투자 철학:</strong> "당신이 이해하는 회사에 투자하고 PEG 비율을 활용하라"</p>
                                    <ul>
                                        <li>성장성: PEG 비율 1.0 이하, 매출성장률 15%↑</li>
                                        <li>소비자 친숙도: 일상에서 발견할 수 있는 기업</li>
                                        <li>적정 밸류에이션: PER 25배 이하</li>
                                        <li>품질: ROE 15%↑, 영업이익률 10%↑</li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <div class="col-md-6 mb-4">
                            <div class="card">
                                <div class="card-header">
                                    <h6>📚 벤저민 그레이엄 - 가치투자의 아버지</h6>
                                </div>
                                <div class="card-body">
                                    <p><strong>투자 철학:</strong> "안전마진을 확보하여 Mr. Market의 변덕을 이용하라"</p>
                                    <ul>
                                        <li>저평가: PER 15배 이하, PBR 2.5배 이하</li>
                                        <li>안전성: 유동비율 2.0↑, 부채비율 30% 이하</li>
                                        <li>배당: 배당수익률 2%↑, 안정적 배당</li>
                                        <li>안전마진: 내재가치 대비 30% 이상 할인</li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <div class="col-md-6 mb-4">
                            <div class="card">
                                <div class="card-header">
                                    <h6>🔬 필립 피셔 - 성장 가치 투자</h6>
                                </div>
                                <div class="card-body">
                                    <p><strong>투자 철학:</strong> "뛰어난 기업을 찾아 장기간 보유하며 성장 과실을 누려라"</p>
                                    <ul>
                                        <li>혁신성: 높은 마진율, R&D 투자</li>
                                        <li>성장성: 매출/순이익 성장률 15%↑</li>
                                        <li>경영진: ROE 20%↑, 뛰어난 경영 능력</li>
                                        <li>15개 포인트: 매출성장, 이익성장, 연구개발 등</li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <div class="col-md-6 mb-4">
                            <div class="card">
                                <div class="card-header">
                                    <h6>🎯 찰리 멍거 - 버핏의 동반자</h6>
                                </div>
                                <div class="card-body">
                                    <p><strong>투자 철학:</strong> "간단하고 이해하기 쉬운 비즈니스에 합리적 가격으로 투자하라"</p>
                                    <ul>
                                        <li>단순성: 이해하기 쉬운 비즈니스</li>
                                        <li>경쟁우위: ROE 20%↑, 강력한 브랜드</li>
                                        <li>합리적 가격: PER 18배 이하</li>
                                        <li>멘탈 모델: 다각도 분석, 역산적 사고</li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <div class="col-md-6 mb-4">
                            <div class="card">
                                <div class="card-header">
                                    <h6>🪄 조엘 그린블라트 - 마법공식의 창시자</h6>
                                </div>
                                <div class="card-body">
                                    <p><strong>투자 철학:</strong> "좋은 회사를 싼 가격에 사는 것이 수익의 핵심이다"</p>
                                    <ul>
                                        <li>자본수익률: ROA 15%↑</li>
                                        <li>이익수익률: 1/PER 10%↑ (PER 10배 이하)</li>
                                        <li>마법공식: ROA 순위 + 이익수익률 순위</li>
                                        <li>시스템적 투자: 감정 배제, 기계적 접근</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 알림 토스트 -->
    <div class="toast-container position-fixed top-0 end-0 p-3">
        <div id="alertToast" class="toast" role="alert">
            <div class="toast-header">
                <strong class="me-auto" id="toastTitle">알림</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body" id="toastMessage">
                메시지가 여기에 표시됩니다.
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // 전역 변수
        let currentInvestor = 'buffett';
        let currentMarket = 'all';
        let currentLimit = 10;
        let currentStocks = [];
        let isKisConnected = false;

        // 초기화
        document.addEventListener('DOMContentLoaded', function() {
            loadStocks();
            setupEventListeners();
        });

        function setupEventListeners() {
            // 검색 입력 이벤트
            document.getElementById('stockSearch').addEventListener('input', debounce(searchStocks, 500));
            
            // 엔터키 검색
            document.getElementById('stockSearch').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    searchStocks();
                }
            });

            // 키보드 단축키
            document.addEventListener('keydown', function(e) {
                // 숫자 키로 투자자 선택 (1-6)
                if (e.key >= '1' && e.key <= '6' && !e.ctrlKey && !e.altKey) {
                    const investors = ['buffett', 'lynch', 'graham', 'fisher', 'munger', 'greenblatt'];
                    selectInvestor(investors[parseInt(e.key) - 1]);
                }
                
                // Ctrl+U로 업데이트
                if (e.ctrlKey && e.key === 'u') {
                    e.preventDefault();
                    updateAllPrices();
                }
            });
        }

        function selectMarket(market) {
            // 버튼 상태 업데이트
            document.querySelectorAll('.market-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelector(`[data-market="${market}"]`).classList.add('active');
            
            currentMarket = market;
            loadStocks();
            showToast('시장 선택', `${getMarketText(market)} 시장으로 변경되었습니다.`, 'success');
        }

        function selectInvestor(investor) {
            // 버튼 상태 업데이트
            document.querySelectorAll('.investor-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelector(`[data-investor="${investor}"]`).classList.add('active');
            
            currentInvestor = investor;
            loadStocks();
            
            const investorNames = {
                'buffett': '워렌 버핏',
                'lynch': '피터 린치', 
                'graham': '벤저민 그레이엄',
                'fisher': '필립 피셔',
                'munger': '찰리 멍거',
                'greenblatt': '조엘 그린블라트'
            };
            
            showToast('투자자 선택', `${investorNames[investor]} 기준으로 분석을 시작합니다.`, 'success');
        }

        function updateResults() {
            currentLimit = parseInt(document.getElementById('limitSelect').value);
            loadStocks();
        }

        function searchStocks() {
            const searchTerm = document.getElementById('stockSearch').value.trim();
            if (searchTerm) {
                const filteredStocks = currentStocks.filter(stock => 
                    stock.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    stock.code.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    stock.sector.toLowerCase().includes(searchTerm.toLowerCase())
                );
                displayStocks(filteredStocks);
                updateSummary(filteredStocks);
            } else {
                const displayStocks = currentLimit > 0 ? currentStocks.slice(0, currentLimit) : currentStocks;
                displayStocks(displayStocks);
                updateSummary(displayStocks);
            }
        }

        async function loadStocks() {
            try {
                showLoading(true);
                
                const response = await fetch(`/api/stocks?style=${currentInvestor}&market=${currentMarket}&limit=${currentLimit}`);
                const data = await response.json();
                
                if (data.success) {
                    currentStocks = data.stocks;
                    displayStocks(currentStocks);
                    updateSummary(currentStocks, data.summary);
                    updateResultsHeader(data.strategy);
                } else {
                    showToast('오류', data.message || '데이터를 불러오는데 실패했습니다.', 'danger');
                }
            } catch (error) {
                console.error('Load stocks error:', error);
                showToast('오류', '서버 연결에 실패했습니다.', 'danger');
            } finally {
                showLoading(false);
            }
        }

        function displayStocks(stocks) {
            const tbody = document.getElementById('stockTableBody');
            
            if (!stocks || stocks.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="21" class="text-center py-5 text-muted">
                            <i class="fas fa-search fa-3x mb-3"></i>
                            <p>표시할 종목이 없습니다.</p>
                        </td>
                    </tr>
                `;
                return;
            }

            tbody.innerHTML = '';
            
            stocks.forEach((stock, index) => {
                const score = stock.investment_score;
                const marketInfo = getMarketInfo(stock.market);
                
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>
                        <div class="rank-badge">#${index + 1}</div>
                    </td>
                    <td>
                        <div class="d-flex align-items-center justify-content-center">
                            <span class="me-2">${marketInfo.flag}</span>
                            <div>
                                <strong>${stock.name}</strong><br>
                                <small class="text-muted">${stock.code}</small>
                            </div>
                        </div>
                    </td>
                    <td><small>${marketInfo.name}</small></td>
                    <td>${stock.sector}</td>
                    <td>${formatPrice(stock.current_price, stock.currency)}</td>
                    <td class="${getColorClass(stock.debt_ratio, 'debt')}">${stock.debt_ratio.toFixed(1)}%</td>
                    <td class="${getColorClass(stock.current_ratio, 'current')}">${stock.current_ratio.toFixed(1)}</td>
                    <td class="${getColorClass(stock.equity_ratio, 'equity')}">${stock.equity_ratio.toFixed(1)}%</td>
                    <td>${stock.credit_rating}</td>
                    <td class="${getColorClass(stock.roe, 'roe')}">${stock.roe.toFixed(1)}%</td>
                    <td class="${getColorClass(stock.roa, 'roa')}">${stock.roa.toFixed(1)}%</td>
                    <td>${stock.operating_margin.toFixed(1)}%</td>
                    <td>${stock.profit_margin.toFixed(1)}%</td>
                    <td class="${getColorClass(stock.revenue_growth, 'growth')}">${stock.revenue_growth.toFixed(1)}%</td>
                    <td class="${getColorClass(stock.profit_growth, 'growth')}">${stock.profit_growth.toFixed(1)}%</td>
                    <td>${stock.eps_growth.toFixed(1)}%</td>
                    <td class="${getColorClass(stock.per, 'per')}">${stock.per.toFixed(1)}x</td>
                    <td class="${getColorClass(stock.pbr, 'pbr')}">${stock.pbr.toFixed(1)}x</td>
                    <td>${stock.dividend_yield.toFixed(1)}%</td>
                    <td><strong>${score.total_score.toFixed(1)}</strong></td>
                    <td><span class="grade-${score.grade}">${score.grade}급</span></td>
                    <td><span class="recommendation-${getRecommendationClass(score.recommendation)}">${score.recommendation}</span></td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="updateSinglePrice('${stock.code}')">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        }

        function updateSummary(stocks, summaryData) {
            if (summaryData) {
                document.getElementById('totalStocks').textContent = summaryData.total_stocks;
                document.getElementById('displayedStocks').textContent = summaryData.displayed_stocks;
                document.getElementById('sGradeStocks').textContent = summaryData.s_grade_stocks;
                document.getElementById('buyRecommendations').textContent = summaryData.buy_recommendations;
                document.getElementById('currentMarket').textContent = summaryData.current_market;
                document.getElementById('avgScore').textContent = summaryData.avg_score;
            } else if (stocks) {
                const sGradeCount = stocks.filter(s => s.investment_score.grade === 'S').length;
                const buyCount = stocks.filter(s => ['적극매수', '매수'].includes(s.investment_score.recommendation)).length;
                const avgScore = stocks.length > 0 ? 
                    (stocks.reduce((sum, s) => sum + s.investment_score.total_score, 0) / stocks.length).toFixed(1) : 0;
                
                document.getElementById('totalStocks').textContent = currentStocks.length;
                document.getElementById('displayedStocks').textContent = stocks.length;
                document.getElementById('sGradeStocks').textContent = sGradeCount;
                document.getElementById('buyRecommendations').textContent = buyCount;
                document.getElementById('currentMarket').textContent = getMarketText(currentMarket);
                document.getElementById('avgScore').textContent = avgScore;
            }
        }

        function updateResultsHeader(strategy) {
            const limitText = currentLimit > 0 ? `상위 ${currentLimit}개` : '전체';
            const marketText = getMarketText(currentMarket);
            
            document.getElementById('resultsTitle').innerHTML = 
                `<span>${strategy.icon}</span> ${strategy.name} 기준 ${limitText} 추천 종목 ${marketText !== '🌍 전체' ? '(' + marketText + ')' : ''}`;
            
            document.getElementById('resultsSubtitle').textContent = 
                `${strategy.name} 투자 철학을 바탕으로 분석된 최고의 투자 기회`;
            
            document.getElementById('investorDescription').innerHTML = 
                `<strong>${strategy.icon} ${strategy.name} 철학:</strong> ${strategy.description}`;
        }

        // 유틸리티 함수들
        function getMarketInfo(market) {
            const marketMap = {
                'KOSPI': { name: 'KOSPI', flag: '🇰🇷' },
                'KOSDAQ': { name: 'KOSDAQ', flag: '🇰🇷' },
                'NYSE': { name: 'NYSE', flag: '🇺🇸' },
                'NASDAQ': { name: 'NASDAQ', flag: '🇺🇸' },
                'TSE': { name: 'TSE', flag: '🇯🇵' },
                'SEHK': { name: 'SEHK', flag: '🇭🇰' }
            };
            return marketMap[market] || { name: market, flag: '🏳️' };
        }

        function getMarketText(market) {
            const texts = {
                'all': '🌍 전체',
                'domestic': '🇰🇷 국내',
                'us': '🇺🇸 미국', 
                'global': '🌏 해외'
            };
            return texts[market] || '🌍 전체';
        }

        function formatPrice(price, currency) {
            const symbols = { 'KRW': '₩', 'USD': '$', 'JPY': '¥', 'HKD': 'HK$' };
            const symbol = symbols[currency] || '';
            return `${symbol}${price.toLocaleString()}`;
        }

        function getColorClass(value, type) {
            switch(type) {
                case 'debt':
                    return value <= 20 ? 'positive' : value <= 40 ? 'neutral' : 'negative';
                case 'current':
                    return value >= 2.0 ? 'positive' : value >= 1.5 ? 'neutral' : 'negative';
                case 'equity':
                    return value >= 70 ? 'positive' : value >= 60 ? 'neutral' : 'negative';
                case 'roe':
                case 'roa':
                    return value >= 15 ? 'positive' : value >= 10 ? 'neutral' : 'negative';
                case 'growth':
                    return value >= 10 ? 'positive' : value >= 5 ? 'neutral' : 'negative';
                case 'per':
                    return value <= 15 ? 'positive' : value <= 20 ? 'neutral' : 'negative';
                case 'pbr':
                    return value <= 2 ? 'positive' : value <= 3 ? 'neutral' : 'negative';
                default:
                    return 'neutral';
            }
        }

        function getRecommendationClass(recommendation) {
            if (['적극매수', '매수'].includes(recommendation)) return 'buy';
            if (['보유', '관심'].includes(recommendation)) return 'hold';
            return 'sell';
        }

        function showLoading(show) {
            document.getElementById('loadingSpinner').style.display = show ? 'block' : 'none';
        }

        function debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }

        function showToast(title, message, type = 'info') {
            const toastElement = document.getElementById('alertToast');
            const titleElement = document.getElementById('toastTitle');
            const messageElement = document.getElementById('toastMessage');
            
            titleElement.textContent = title;
            messageElement.textContent = message;
            
            // 타입에 따른 스타일 변경
            toastElement.className = `toast ${type === 'success' ? 'bg-success text-white' : type === 'danger' ? 'bg-danger text-white' : ''}`;
            
            const toast = new bootstrap.Toast(toastElement);
            toast.show();
        }

        // KIS API 관련 함수들
        function openKisApiModal() {
            const modal = new bootstrap.Modal(document.getElementById('kisApiModal'));
            modal.show();
        }

        async function testKisConnection() {
            const appKey = document.getElementById('kisAppKey').value.trim();
            const appSecret = document.getElementById('kisAppSecret').value.trim();
            const environment = document.getElementById('kisEnvironment').value;
            
            if (!appKey || !appSecret) {
                showToast('입력 오류', 'App Key와 App Secret을 모두 입력해주세요.', 'danger');
                return;
            }
            
            try {
                const response = await fetch('/api/test-connection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ appKey, appSecret, environment })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showToast('연결 성공', data.message, 'success');
                    isKisConnected = true;
                    updateApiStatus(true);
                } else {
                    showToast('연결 실패', data.message, 'danger');
                }
            } catch (error) {
                showToast('오류', '연결 테스트 중 오류가 발생했습니다.', 'danger');
            }
        }

        async function saveKisConfig() {
            const appKey = document.getElementById('kisAppKey').value.trim();
            const appSecret = document.getElementById('kisAppSecret').value.trim();
            const environment = document.getElementById('kisEnvironment').value;
            const accountNo = document.getElementById('kisAccountNo').value.trim();
            
            if (!appKey || !appSecret) {
                showToast('입력 오류', 'App Key와 App Secret을 모두 입력해주세요.', 'danger');
                return;
            }
            
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ appKey, appSecret, environment, accountNo })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showToast('설정 저장', data.message, 'success');
                    bootstrap.Modal.getInstance(document.getElementById('kisApiModal')).hide();
                } else {
                    showToast('저장 실패', data.message, 'danger');
                }
            } catch (error) {
                showToast('오류', '설정 저장 중 오류가 발생했습니다.', 'danger');
            }
        }

        function updateApiStatus(connected) {
            const statusElement = document.getElementById('apiStatus');
            if (connected) {
                statusElement.className = 'api-status connected';
                statusElement.innerHTML = '<span class="status-icon">🟢</span><span>KIS API 연결됨</span>';
            } else {
                statusElement.className = 'api-status';
                statusElement.innerHTML = '<span class="status-icon">🔴</span><span>KIS API 연결 안됨</span>';
            }
        }

        async function updateAllPrices() {
            if (!isKisConnected) {
                showToast('API 필요', 'KIS API 연결 후 실시간 업데이트가 가능합니다.', 'warning');
                return;
            }
            
            const updateBtn = document.getElementById('updateBtn');
            const originalText = updateBtn.innerHTML;
            updateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 업데이트 중...';
            updateBtn.disabled = true;
            
            try {
                const response = await fetch('/api/update-all-prices');
                const data = await response.json();
                
                if (data.success) {
                    showToast('업데이트 완료', data.message, 'success');
                    loadStocks(); // 데이터 새로고침
                } else {
                    showToast('업데이트 실패', data.message, 'danger');
                }
            } catch (error) {
                showToast('오류', '가격 업데이트 중 오류가 발생했습니다.', 'danger');
            } finally {
                updateBtn.innerHTML = originalText;
                updateBtn.disabled = false;
            }
        }

        async function updateSinglePrice(stockCode) {
            if (!isKisConnected) {
                showToast('API 필요', 'KIS API 연결 후 실시간 업데이트가 가능합니다.', 'warning');
                return;
            }
            
            try {
                const response = await fetch(`/api/update-price/${stockCode}`);
                const data = await response.json();
                
                if (data.success) {
                    showToast('가격 업데이트', data.message, 'success');
                    loadStocks(); // 데이터 새로고침
                } else {
                    showToast('업데이트 실패', data.message, 'danger');
                }
            } catch (error) {
                showToast('오류', '가격 업데이트 중 오류가 발생했습니다.', 'danger');
            }
        }

        function showInvestmentCriteria() {
            const modal = new bootstrap.Modal(document.getElementById('criteriaModal'));
            modal.show();
        }

        async function exportData() {
            try {
                const url = `/api/export-stocks?style=${currentInvestor}&market=${currentMarket}`;
                const response = await fetch(url);
                
                if (response.ok) {
                    const blob = await response.blob();
                    const downloadUrl = window.URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = downloadUrl;
                    link.download = `investment_screener_${currentInvestor}_${currentMarket}_${new Date().toISOString().slice(0,10)}.csv`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    window.URL.revokeObjectURL(downloadUrl);
                    
                    showToast('내보내기 완료', 'CSV 파일이 다운로드되었습니다.', 'success');
                } else {
                    showToast('내보내기 실패', '데이터 내보내기에 실패했습니다.', 'danger');
                }
            } catch (error) {
                showToast('오류', '데이터 내보내기 중 오류가 발생했습니다.', 'danger');
            }
        }

        // 초기 로드
        loadStocks();
    </script>
</body>
</html>
'''

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

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': '요청한 페이지를 찾을 수 없습니다.'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': '서버 내부 오류가 발생했습니다.'}), 500

@app.route('/')
def index():
    """메인 페이지"""
    return render_template_string(HTML_TEMPLATE)

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
        'global': '🌏 해외'
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
        # stocks API 호출해서 데이터 가져오기
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
        
        # DataFrame 생성
        df_data = []
        for i, stock in enumerate(analyzed_stocks):
            score = stock['investment_score']
            df_data.append({
                '순위': i + 1,
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