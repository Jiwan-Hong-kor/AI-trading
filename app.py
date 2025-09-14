#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
한국투자증권 KIS API 기반 투자 거장 스크리너 - 완전 버전
"""

import os
import json
import requests
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from functools import wraps

from flask import Flask, render_template_string, request, jsonify, make_response, session
from flask_cors import CORS
import pandas as pd

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask 애플리케이션 설정
app = Flask(__name__)
app.secret_key = 'investment-screener-secret-key-2024'
CORS(app)

# KIS API 설정
KIS_CONFIG = {
    'base_url_real': 'https://openapi.koreainvestment.com:9443',
    'base_url_vps': 'https://openapivts.koreainvestment.com:29443',
    'app_key': '',
    'app_secret': '',
    'access_token': '',
    'environment': 'vps',
    'account_no': '',
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
                self.config['is_connected'] = False
                return None
                
        except requests.exceptions.Timeout:
            logger.error("토큰 발급 시간 초과")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("토큰 발급 연결 오류")
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

class InvestmentStrategy:
    """투자 전략 기본 클래스"""
    
    def __init__(self, name: str, description: str, icon: str):
        self.name = name
        self.description = description
        self.icon = icon
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        """주식에 대한 투자 점수 계산"""
        raise NotImplementedError
    
    def get_grade(self, score: float) -> str:
        """점수를 기반으로 등급 결정"""
        if score >= 4.0: return 'S'
        elif score >= 3.5: return 'A'
        elif score >= 3.0: return 'B'
        elif score >= 2.5: return 'C'
        else: return 'D'
    
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
        if stock.roe >= 15: moat_score += 1.5
        elif stock.roe >= 10: moat_score += 1.0
        elif stock.roe >= 8: moat_score += 0.5
        
        if stock.revenue_growth >= 10: moat_score += 1.0
        elif stock.revenue_growth >= 5: moat_score += 0.5
        
        if stock.profit_growth >= 10: moat_score += 1.0
        elif stock.profit_growth >= 5: moat_score += 0.5
        
        # 경영진 능력 (30%)
        management_score = 0
        if stock.roe >= 15 and stock.equity_ratio >= 70 and stock.debt_ratio <= 30:
            management_score = 2.0
        elif stock.roe >= 10 and stock.equity_ratio >= 60 and stock.debt_ratio <= 40:
            management_score = 1.5
        else:
            management_score = 1.0
        
        # 재무건전성 (30%)
        health_score = 0
        if stock.equity_ratio >= 80 and stock.debt_ratio <= 20 and stock.current_ratio >= 2.0:
            health_score = 2.0
        elif stock.equity_ratio >= 70 and stock.debt_ratio <= 30 and stock.current_ratio >= 1.5:
            health_score = 1.5
        else:
            health_score = 1.0
        
        total_score = moat_score + management_score + health_score
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=total_score,
            grade=grade,
            recommendation=recommendation,
            details={'moat': moat_score, 'management': management_score, 'health': health_score}
        )

class LynchStrategy(InvestmentStrategy):
    """피터 린치 성장투자 전략"""
    
    def __init__(self):
        super().__init__(
            name="피터 린치",
            description="PEG 비율 + 매출성장률 + 소비자 친숙도",
            icon="🚀"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        growth_score = 0
        peg_ratio = stock.per / max(stock.profit_growth, 1) if stock.per > 0 else 0
        if peg_ratio <= 0.5: growth_score += 2.0
        elif peg_ratio <= 1.0: growth_score += 1.5
        elif peg_ratio <= 1.5: growth_score += 1.0
        
        if stock.revenue_growth >= 20: growth_score += 1.5
        elif stock.revenue_growth >= 15: growth_score += 1.0
        elif stock.revenue_growth >= 10: growth_score += 0.5
        
        valuation_score = 0
        if stock.per <= 15 and stock.pbr <= 3: valuation_score = 1.5
        elif stock.per <= 25 and stock.pbr <= 5: valuation_score = 1.0
        elif stock.per <= 35: valuation_score = 0.5
        
        quality_score = 0
        if stock.roe >= 15 and stock.operating_margin >= 10: quality_score = 1.0
        elif stock.roe >= 10: quality_score = 0.7
        
        total_score = growth_score + valuation_score + quality_score
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=total_score,
            grade=grade,
            recommendation=recommendation,
            details={'growth': growth_score, 'valuation': valuation_score, 'quality': quality_score}
        )

class GrahamStrategy(InvestmentStrategy):
    def __init__(self):
        super().__init__("벤저민 그레이엄", "저평가 + 안전마진 + 배당", "📚")
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        value_score = 2.0 if stock.per <= 15 and stock.pbr <= 2.5 else 1.0
        safety_score = 2.0 if stock.current_ratio >= 2.0 and stock.debt_ratio <= 30 else 1.0
        dividend_score = 1.0 if stock.dividend_yield >= 2.0 else 0.5
        
        total_score = value_score + safety_score + dividend_score
        return InvestmentScore(
            total_score=total_score,
            grade=self.get_grade(total_score),
            recommendation=self.get_recommendation(self.get_grade(total_score), stock),
            details={'value': value_score, 'safety': safety_score, 'dividend': dividend_score}
        )

class FisherStrategy(InvestmentStrategy):
    def __init__(self):
        super().__init__("필립 피셔", "혁신 + 장기성장 + 경영진", "🔬")
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        innovation_score = 2.0 if stock.operating_margin >= 15 else 1.0
        growth_score = 2.0 if stock.profit_growth >= 15 else 1.0
        management_score = 1.0 if stock.roe >= 15 else 0.5
        
        total_score = innovation_score + growth_score + management_score
        return InvestmentScore(
            total_score=total_score,
            grade=self.get_grade(total_score),
            recommendation=self.get_recommendation(self.get_grade(total_score), stock),
            details={'innovation': innovation_score, 'growth': growth_score, 'management': management_score}
        )

class MungerStrategy(InvestmentStrategy):
    def __init__(self):
        super().__init__("찰리 멍거", "단순함 + 경쟁우위 + 합리적가격", "🎯")
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        simplicity_score = 2.0 if stock.roe >= 12 else 1.0
        competitive_score = 2.0 if stock.roe >= 20 and stock.operating_margin >= 20 else 1.0
        rational_score = 1.5 if stock.per <= 18 and stock.pbr <= 3.0 else 1.0
        
        total_score = simplicity_score + competitive_score + rational_score
        return InvestmentScore(
            total_score=total_score,
            grade=self.get_grade(total_score),
            recommendation=self.get_recommendation(self.get_grade(total_score), stock),
            details={'simplicity': simplicity_score, 'competitive': competitive_score, 'rational': rational_score}
        )

class GreenblattStrategy(InvestmentStrategy):
    def __init__(self):
        super().__init__("조엘 그린블라트", "마법공식 (ROA + 이익수익률)", "🪄")
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        roc_score = 2.5 if stock.roa >= 15 else 1.5 if stock.roa >= 10 else 1.0
        earnings_yield = (100 / stock.per) if stock.per > 0 else 0
        ey_score = 2.5 if earnings_yield >= 10 else 1.5 if earnings_yield >= 6.67 else 1.0
        
        total_score = roc_score + ey_score
        return InvestmentScore(
            total_score=total_score,
            grade=self.get_grade(total_score),
            recommendation=self.get_recommendation(self.get_grade(total_score), stock),
            details={'roc': roc_score, 'earnings_yield': ey_score}
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

# 샘플 데이터
SAMPLE_STOCKS = [
    Stock(1, '삼성전자', '005930', 'KOSPI', '반도체', 75000, 'KRW', 15.2, 2.1, 85.2, 'AA', 18.5, 12.3, 22.1, 15.2, 8.5, 12.3, 15.2, 12.5, 1.2, 2.8, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
    Stock(2, '네이버', '035420', 'KOSPI', 'IT서비스', 210000, 'KRW', 8.5, 2.8, 88.5, 'AA-', 22.5, 18.2, 28.5, 20.1, 15.2, 18.5, 22.1, 18.5, 2.1, 1.8, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
    Stock(3, 'SK하이닉스', '000660', 'KOSPI', '반도체', 115000, 'KRW', 22.1, 1.8, 72.5, 'A+', 16.2, 11.8, 18.5, 12.8, 12.5, 15.8, 18.2, 14.2, 1.8, 2.2, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
    Stock(4, 'Apple Inc.', 'AAPL', 'NASDAQ', '기술', 185.25, 'USD', 31.2, 1.0, 68.8, 'AA+', 28.5, 18.9, 29.8, 24.3, 11.2, 16.8, 19.5, 24.2, 5.8, 0.5, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
    Stock(5, 'Microsoft Corp.', 'MSFT', 'NASDAQ', '기술', 378.85, 'USD', 18.5, 1.9, 81.5, 'AAA', 35.2, 22.1, 41.5, 35.8, 18.5, 24.2, 28.5, 28.5, 8.2, 0.7, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
    Stock(6, 'Toyota Motor', '7203', 'TSE', '자동차', 2485, 'JPY', 55.2, 1.1, 44.8, 'AA-', 10.8, 4.5, 9.2, 7.8, 12.8, 18.5, 22.1, 11.5, 1.2, 2.8, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
    Stock(7, 'Alibaba Group', '9988', 'SEHK', 'IT서비스', 85.50, 'HKD', 22.5, 1.8, 77.5, 'A+', 12.8, 8.5, 18.5, 15.2, 9.2, 12.5, 15.8, 14.8, 2.1, 0.0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
]

# HTML 템플릿
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
        body {
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
            font-family: 'Segoe UI', sans-serif;
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
            background: linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }
        .controls-section {
            background: #f8fafc;
            padding: 25px;
        }
        .investor-buttons {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .investor-btn {
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: center;
        }
        .investor-btn:hover, .investor-btn.active {
            background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%);
            color: white;
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(59,130,246,0.4);
        }
        .control-buttons {
            display: flex;
            gap: 15px;
            justify-content: center;
            flex-wrap: wrap;
            margin: 20px 0;
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
        .results-section {
            padding: 30px;
        }
        .table-responsive {
            border-radius: 12px;
            overflow: hidden;
        }
        .table thead th {
            background: #374151;
            color: white;
            text-align: center;
            font-size: 0.875rem;
            padding: 15px 8px;
        }
        .table tbody td {
            text-align: center;
            vertical-align: middle;
            padding: 12px 8px;
        }
        .grade-S { background: #dbeafe; color: #1e40af; font-weight: bold; padding: 4px 8px; border-radius: 4px; }
        .grade-A { background: #dcfce7; color: #166534; font-weight: bold; padding: 4px 8px; border-radius: 4px; }
        .grade-B { background: #fef3c7; color: #92400e; font-weight: bold; padding: 4px 8px; border-radius: 4px; }
        .grade-C { background: #fce7f3; color: #be185d; padding: 4px 8px; border-radius: 4px; }
        .grade-D { background: #fee2e2; color: #dc2626; padding: 4px 8px; border-radius: 4px; }
        .recommendation-buy { background: #dcfce7; color: #166534; font-weight: bold; padding: 6px 12px; border-radius: 6px; }
        .recommendation-hold { background: #fef3c7; color: #92400e; font-weight: bold; padding: 6px 12px; border-radius: 6px; }
        .recommendation-sell { background: #fee2e2; color: #dc2626; font-weight: bold; padding: 6px 12px; border-radius: 6px; }
        .api-status {
            padding: 10px 16px;
            border-radius: 8px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .api-status.disconnected {
            background: #fef2f2;
            color: #991b1b;
            border: 2px solid #fecaca;
        }
        .api-status.connected {
            background: #f0fdf4;
            color: #166534;
            border: 2px solid #bbf7d0;
        }
        .toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
        }
        .toast {
            min-width: 300px;
        }
        .loading {
            opacity: 0.6;
            pointer-events: none;
        }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="main-container">
            <div class="header">
                <h1><i class="fas fa-chart-line"></i> 한국투자증권 투자 거장 스크리너</h1>
                <p>KIS Developers API 기반 · 6대 투자 철학으로 실시간 종목 분석</p>
            </div>

            <div class="controls-section">
                <div class="investor-buttons">
                    <button class="investor-btn active" data-investor="buffett" onclick="selectInvestor('buffett')">
                        <div style="font-size: 2rem; margin-bottom: 8px;">👑</div>
                        <h6>워렌 버핏</h6>
                        <small>가치투자</small>
                    </button>
                    <button class="investor-btn" data-investor="lynch" onclick="selectInvestor('lynch')">
                        <div style="font-size: 2rem; margin-bottom: 8px;">🚀</div>
                        <h6>피터 린치</h6>
                        <small>성장주</small>
                    </button>
                    <button class="investor-btn" data-investor="graham" onclick="selectInvestor('graham')">
                        <div style="font-size: 2rem; margin-bottom: 8px;">📚</div>
                        <h6>벤저민 그레이엄</h6>
                        <small>딥밸류</small>
                    </button>
                    <button class="investor-btn" data-investor="fisher" onclick="selectInvestor('fisher')">
                        <div style="font-size: 2rem; margin-bottom: 8px;">🔬</div>
                        <h6>필립 피셔</h6>
                        <small>성장 가치</small>
                    </button>
                    <button class="investor-btn" data-investor="munger" onclick="selectInvestor('munger')">
                        <div style="font-size: 2rem; margin-bottom: 8px;">🎯</div>
                        <h6>찰리 멍거</h6>
                        <small>우량기업</small>
                    </button>
                    <button class="investor-btn" data-investor="greenblatt" onclick="selectInvestor('greenblatt')">
                        <div style="font-size: 2rem; margin-bottom: 8px;">🪄</div>
                        <h6>조엘 그린블라트</h6>
                        <small>마법공식</small>
                    </button>
                </div>

                <div class="control-buttons">
                    <button class="btn btn-primary btn-custom" onclick="openKisApiModal()">
                        <i class="fas fa-link"></i> KIS API 연동
                    </button>
                    <button class="btn btn-success btn-custom" onclick="updatePrices()" id="updateBtn">
                        <i class="fas fa-sync-alt"></i> 실시간 업데이트
                    </button>
                    <button class="btn btn-info btn-custom" onclick="exportData()">
                        <i class="fas fa-download"></i> CSV 다운로드
                    </button>
                </div>

                <div class="text-center">
                    <div class="api-status disconnected" id="apiStatus">
                        <span>🔴</span>
                        <span>KIS API 연결 안됨 (샘플 데이터 사용 중)</span>
                    </div>
                </div>
            </div>

            <div class="results-section">
                <h3 id="resultsTitle">👑 워렌 버핏 기준 상위 추천 종목</h3>
                <p class="text-muted mb-4" id="resultsSubtitle">경제적 해자 + 뛰어난 경영진 + 재무건전성 + 합리적 가격</p>
                
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th>순위</th>
                                <th>종목명</th>
                                <th>시장</th>
                                <th>현재가</th>
                                <th>ROE</th>
                                <th>PER</th>
                                <th>PBR</th>
                                <th>점수</th>
                                <th>등급</th>
                                <th>추천</th>
                                <th>업데이트</th>
                            </tr>
                        </thead>
                        <tbody id="stockTableBody">
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- KIS API 모달 -->
    <div class="modal fade" id="kisApiModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">
                        <i class="fas fa-link"></i> 한국투자증권 KIS API 연동
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="alert alert-info">
                        <h6><i class="fas fa-info-circle"></i> KIS Developers 정보</h6>
                        <ul class="mb-0">
                            <li><strong>신청:</strong> <a href="https://apiportal.koreainvestment.com" target="_blank">apiportal.koreainvestment.com</a></li>
                            <li><strong>지원:</strong> 국내주식, 해외주식 실시간 시세</li>
                            <li><strong>인증:</strong> OAuth 2.0 (App Key + App Secret)</li>
                        </ul>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">환경 선택</label>
                        <select class="form-select" id="kisEnvironment">
                            <option value="vps">모의투자 (추천)</option>
                            <option value="real">실전투자</option>
                        </select>
                        <small class="form-text text-muted">처음 사용하시는 경우 모의투자 환경을 권장합니다.</small>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">App Key *</label>
                        <input type="password" class="form-control" id="kisAppKey" 
                               placeholder="KIS Developers에서 발급받은 App Key를 입력하세요">
                    </div>

                    <div class="mb-3">
                        <label class="form-label">App Secret *</label>
                        <input type="password" class="form-control" id="kisAppSecret" 
                               placeholder="KIS Developers에서 발급받은 App Secret을 입력하세요">
                    </div>

                    <div class="mb-3">
                        <label class="form-label">계좌번호 (선택)</label>
                        <input type="text" class="form-control" id="kisAccountNo" 
                               placeholder="8자리-2자리 형식 (예: 50000000-01)">
                    </div>

                    <div id="connectionResult" class="mt-3"></div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-primary" onclick="testConnection()" id="testBtn">
                        <i class="fas fa-plug"></i> 연결 테스트
                    </button>
                    <button class="btn btn-success" onclick="saveConfig()" id="saveBtn">
                        <i class="fas fa-save"></i> 설정 저장
                    </button>
                    <a href="https://apiportal.koreainvestment.com" target="_blank" class="btn btn-outline-primary">
                        <i class="fas fa-external-link-alt"></i> KIS 포털
                    </a>
                </div>
            </div>
        </div>
    </div>

    <!-- 토스트 알림 -->
    <div class="toast-container">
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
        let currentInvestor = 'buffett';
        let currentStocks = [];
        let isConnected = false;

        // 초기 로드
        document.addEventListener('DOMContentLoaded', loadStocks);

        function selectInvestor(investor) {
            document.querySelectorAll('.investor-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelector(`[data-investor="${investor}"]`).classList.add('active');
            currentInvestor = investor;
            loadStocks();
            updateTitle();
        }

        function updateTitle() {
            const strategies = {
                'buffett': {name: '👑 워렌 버핏', desc: '경제적 해자 + 뛰어난 경영진 + 재무건전성 + 합리적 가격'},
                'lynch': {name: '🚀 피터 린치', desc: 'PEG 비율 + 매출성장률 + 소비자 친숙도'},
                'graham': {name: '📚 벤저민 그레이엄', desc: '저평가 + 안전마진 + 배당'},
                'fisher': {name: '🔬 필립 피셔', desc: '혁신 + 장기성장 + 경영진'},
                'munger': {name: '🎯 찰리 멍거', desc: '단순함 + 경쟁우위 + 합리적가격'},
                'greenblatt': {name: '🪄 조엘 그린블라트', desc: '마법공식 (ROA + 이익수익률)'}
            };
            const strategy = strategies[currentInvestor];
            document.getElementById('resultsTitle').textContent = strategy.name + ' 기준 상위 추천 종목';
            document.getElementById('resultsSubtitle').textContent = strategy.desc;
        }

        async function loadStocks() {
            try {
                document.querySelector('.results-section').classList.add('loading');
                const response = await fetch(`/api/stocks?style=${currentInvestor}`);
                const data = await response.json();
                
                if (data.success) {
                    currentStocks = data.stocks;
                    displayStocks();
                } else {
                    showToast('오류', data.message || '데이터 로드 실패', 'danger');
                }
            } catch (error) {
                console.error('데이터 로드 오류:', error);
                showToast('오류', '서버 연결에 실패했습니다.', 'danger');
            } finally {
                document.querySelector('.results-section').classList.remove('loading');
            }
        }

        function displayStocks() {
            const tbody = document.getElementById('stockTableBody');
            tbody.innerHTML = '';
            
            currentStocks.forEach((stock, index) => {
                const score = stock.investment_score;
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><span class="badge bg-primary">#${index + 1}</span></td>
                    <td>
                        <strong>${stock.name}</strong><br>
                        <small class="text-muted">${stock.code}</small>
                    </td>
                    <td>${getMarketFlag(stock.market)} ${stock.market}</td>
                    <td>${formatPrice(stock.current_price, stock.currency)}</td>
                    <td class="${getValueColor(stock.roe, 15, 10)}">${stock.roe.toFixed(1)}%</td>
                    <td class="${getValueColor(stock.per, 20, 15, true)}">${stock.per.toFixed(1)}x</td>
                    <td class="${getValueColor(stock.pbr, 3, 2, true)}">${stock.pbr.toFixed(1)}x</td>
                    <td><strong>${score.total_score.toFixed(1)}</strong></td>
                    <td><span class="grade-${score.grade}">${score.grade}급</span></td>
                    <td><span class="recommendation-${getRecClass(score.recommendation)}">${score.recommendation}</span></td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="updateSingleStock('${stock.code}')" 
                                title="개별 업데이트">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        }

        function getMarketFlag(market) {
            const flags = {
                'KOSPI': '🇰🇷', 'KOSDAQ': '🇰🇷', 'NYSE': '🇺🇸', 'NASDAQ': '🇺🇸',
                'TSE': '🇯🇵', 'SEHK': '🇭🇰'
            };
            return flags[market] || '🏳️';
        }

        function formatPrice(price, currency) {
            const symbols = { 'KRW': '₩', 'USD': '$', 'JPY': '¥', 'HKD': 'HK$' };
            return `${symbols[currency] || ''}${price.toLocaleString()}`;
        }

        function getValueColor(value, good, medium, reverse = false) {
            if (reverse) {
                return value <= good ? 'text-success fw-bold' : value <= medium ? 'text-warning' : 'text-danger';
            } else {
                return value >= good ? 'text-success fw-bold' : value >= medium ? 'text-warning' : 'text-danger';
            }
        }

        function getRecClass(rec) {
            if (['적극매수', '매수'].includes(rec)) return 'buy';
            if (['보유', '관심'].includes(rec)) return 'hold';
            return 'sell';
        }

        function openKisApiModal() {
            new bootstrap.Modal(document.getElementById('kisApiModal')).show();
        }

        async function testConnection() {
            const appKey = document.getElementById('kisAppKey').value.trim();
            const appSecret = document.getElementById('kisAppSecret').value.trim();
            const environment = document.getElementById('kisEnvironment').value;
            
            if (!appKey || !appSecret) {
                showToast('입력 오류', 'App Key와 App Secret을 모두 입력해주세요.', 'warning');
                return;
            }

            const testBtn = document.getElementById('testBtn');
            const originalText = testBtn.innerHTML;
            testBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> 연결 중...';
            testBtn.disabled = true;

            const resultDiv = document.getElementById('connectionResult');
            resultDiv.innerHTML = '';
            
            try {
                const response = await fetch('/api/test-connection', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({appKey, appSecret, environment})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    resultDiv.innerHTML = `
                        <div class="alert alert-success">
                            <i class="fas fa-check-circle"></i> <strong>연결 성공!</strong><br>
                            ${data.message}<br>
                            <small>토큰: ${data.token || 'N/A'}</small>
                        </div>
                    `;
                    updateApiStatus(true);
                } else {
                    resultDiv.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-times-circle"></i> <strong>연결 실패</strong><br>
                            ${data.message}
                        </div>
                    `;
                }
            } catch (error) {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i> <strong>연결 오류</strong><br>
                        네트워크 오류가 발생했습니다.
                    </div>
                `;
            } finally {
                testBtn.innerHTML = originalText;
                testBtn.disabled = false;
            }
        }

        async function saveConfig() {
            const appKey = document.getElementById('kisAppKey').value.trim();
            const appSecret = document.getElementById('kisAppSecret').value.trim();
            const environment = document.getElementById('kisEnvironment').value;
            const accountNo = document.getElementById('kisAccountNo').value.trim();

            if (!appKey || !appSecret) {
                showToast('입력 오류', 'App Key와 App Secret을 모두 입력해주세요.', 'warning');
                return;
            }

            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({appKey, appSecret, environment, accountNo})
                });

                const data = await response.json();
                
                if (data.success) {
                    showToast('설정 저장', '설정이 저장되었습니다.', 'success');
                    bootstrap.Modal.getInstance(document.getElementById('kisApiModal')).hide();
                } else {
                    showToast('저장 실패', data.message, 'danger');
                }
            } catch (error) {
                showToast('오류', '설정 저장 중 오류가 발생했습니다.', 'danger');
            }
        }

        function updateApiStatus(connected) {
            const status = document.getElementById('apiStatus');
            if (connected) {
                status.className = 'api-status connected';
                status.innerHTML = '<span>🟢</span><span>KIS API 연결됨 (실시간 데이터 사용)</span>';
                isConnected = true;
            } else {
                status.className = 'api-status disconnected';
                status.innerHTML = '<span>🔴</span><span>KIS API 연결 안됨 (샘플 데이터 사용 중)</span>';
                isConnected = false;
            }
        }

        async function updatePrices() {
            if (!isConnected) {
                showToast('API 필요', 'KIS API 연결 후 실시간 업데이트가 가능합니다.', 'info');
                return;
            }

            const updateBtn = document.getElementById('updateBtn');
            const originalText = updateBtn.innerHTML;
            updateBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 업데이트 중...';
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

        async function updateSingleStock(stockCode) {
            if (!isConnected) {
                showToast('API 필요', 'KIS API 연결이 필요합니다.', 'info');
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

        async function exportData() {
            try {
                const url = `/api/export-stocks?style=${currentInvestor}`;
                const response = await fetch(url);
                
                if (response.ok) {
                    const blob = await response.blob();
                    const downloadUrl = window.URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = downloadUrl;
                    link.download = `investment_screener_${currentInvestor}_${new Date().toISOString().slice(0,10)}.csv`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    window.URL.revokeObjectURL(downloadUrl);
                    
                    showToast('다운로드 완료', 'CSV 파일이 다운로드되었습니다.', 'success');
                } else {
                    showToast('다운로드 실패', '데이터 내보내기에 실패했습니다.', 'danger');
                }
            } catch (error) {
                showToast('오류', '데이터 내보내기 중 오류가 발생했습니다.', 'danger');
            }
        }

        function showToast(title, message, type = 'info') {
            const toastEl = document.getElementById('alertToast');
            const titleEl = document.getElementById('toastTitle');
            const messageEl = document.getElementById('toastMessage');
            
            titleEl.textContent = title;
            messageEl.textContent = message;
            
            // 타입별 색상
            toastEl.className = `toast ${type === 'success' ? 'bg-success text-white' : 
                                       type === 'danger' ? 'bg-danger text-white' :
                                       type === 'warning' ? 'bg-warning text-dark' : ''}`;
            
            const toast = new bootstrap.Toast(toastEl, {delay: 4000});
            toast.show();
        }
    </script>
</body>
</html>
'''

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
        
        # 세션에 저장
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
        
        # 실제 토큰 발급 테스트
        logger.info(f"KIS API 연결 테스트 시작 - 환경: {KIS_CONFIG['environment']}")
        token = kis_api.get_access_token()
        
        if token:
            env_text = '실전투자' if KIS_CONFIG['environment'] == 'real' else '모의투자'
            return jsonify({
                'success': True,
                'message': f'KIS {env_text} API 연결 성공!',
                'token': token[:20] + '...' if len(token) > 20 else token,
                'environment': KIS_CONFIG['environment']
            })
        else:
            # 실패 시 원래 설정 복원
            KIS_CONFIG.update(old_config)
            return jsonify({
                'success': False, 
                'message': 'API 연결에 실패했습니다. App Key/Secret을 확인하거나 네트워크 연결을 확인해주세요.'
            }), 400
            
    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return jsonify({
            'success': False, 
            'message': f'연결 테스트 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/stocks')
def get_stocks():
    """종목 목록 조회"""
    try:
        style = request.args.get('style', 'buffett')
        market = request.args.get('market', 'all')
        limit = int(request.args.get('limit', 10))
        
        stocks = SAMPLE_STOCKS.copy()
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
        
        return jsonify({
            'success': True,
            'stocks': analyzed_stocks,
            'strategy': {
                'name': strategy.name,
                'description': strategy.description,
                'icon': strategy.icon
            },
            'total_analyzed': len(analyzed_stocks)
        })
        
    except Exception as e:
        logger.error(f"Get stocks error: {e}")
        return jsonify({
            'success': False,
            'message': f'종목 조회 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/update-price/<stock_code>')
def update_single_price(stock_code):
    """개별 종목 가격 업데이트"""
    try:
        if not KIS_CONFIG['is_connected']:
            return jsonify({
                'success': False, 
                'message': 'KIS API가 연결되지 않았습니다.'
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
            old_price = stock.current_price
            stock.current_price = new_price
            stock.last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            change = new_price - old_price
            change_percent = (change / old_price) * 100 if old_price > 0 else 0
            
            return jsonify({
                'success': True,
                'message': f"{stock.name} 가격이 업데이트되었습니다. ({change:+.0f}원, {change_percent:+.1f}%)",
                'stock': {
                    'code': stock.code,
                    'name': stock.name,
                    'old_price': old_price,
                    'new_price': new_price,
                    'change': change,
                    'change_percent': change_percent,
                    'last_update': stock.last_update
                }
            })
        else:
            return jsonify({
                'success': False, 
                'message': '가격 조회에 실패했습니다.'
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
                'message': 'KIS API가 연결되지 않았습니다.'
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
                    
                    change = new_price - old_price
                    change_percent = (change / old_price) * 100 if old_price > 0 else 0
                    
                    updated_stocks.append({
                        'name': stock.name,
                        'change': change,
                        'change_percent': change_percent
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

@app.route('/api/export-stocks')
def export_stocks():
    """종목 데이터 CSV 내보내기"""
    try:
        style = request.args.get('style', 'buffett')
        
        stocks = SAMPLE_STOCKS.copy()
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
        filename = f"investment_screener_{style}_{timestamp}.csv"
        
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

@app.route('/health')
def health_check():
    """헬스 체크"""
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'kis_api_connected': KIS_CONFIG['is_connected']
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print("🚀 한국투자증권 KIS API 투자 거장 스크리너")
    print("=" * 60)
    print(f"📌 http://localhost:{port} 으로 접속하세요!")
    print("🔑 KIS API 연동 시 실시간 데이터 사용 가능")
    print("💡 API 없이도 샘플 데이터로 체험 가능")
    print("🌐 KIS API 신청: https://apiportal.koreainvestment.com")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=True)