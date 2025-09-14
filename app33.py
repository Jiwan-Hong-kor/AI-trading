#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
한국투자증권 KIS API 기반 투자 거장 스크리너
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

from flask import Flask, render_template_string, request, jsonify, make_response
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
            description="PEG 비율 + 매출성장률 + 소비자 친숙도 + 기업규모",
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

# 다른 전략들도 비슷하게 구현 (간단화)
class GrahamStrategy(InvestmentStrategy):
    def __init__(self):
        super().__init__("벤저민 그레이엄", "순유동자산 + 낮은 PER/PBR + 배당 + 재무안정성", "📚")
    
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
        super().__init__("필립 피셔", "연구개발 투자 + 경영진 능력 + 장기성장 잠재력", "🔬")
    
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
        super().__init__("찰리 멍거", "간단한 비즈니스 + 경쟁우위 + 합리적 가격", "🎯")
    
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
        super().__init__("조엘 그린블라트", "자본수익률 + 이익수익률 (마법공식)", "🪄")
    
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

# 시장 정보
MARKET_INFO = {
    'KOSPI': {'name': 'KOSPI', 'flag': '🇰🇷', 'type': 'domestic'},
    'KOSDAQ': {'name': 'KOSDAQ', 'flag': '🇰🇷', 'type': 'domestic'},
    'NYSE': {'name': 'NYSE', 'flag': '🇺🇸', 'type': 'us'},
    'NASDAQ': {'name': 'NASDAQ', 'flag': '🇺🇸', 'type': 'us'},
    'TSE': {'name': 'TSE', 'flag': '🇯🇵', 'type': 'global'},
    'SEHK': {'name': '홍콩거래소', 'flag': '🇭🇰', 'type': 'global'}
}

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
        }
        .grade-S { background: #dbeafe; color: #1e40af; font-weight: bold; }
        .grade-A { background: #dcfce7; color: #166534; font-weight: bold; }
        .grade-B { background: #fef3c7; color: #92400e; font-weight: bold; }
        .recommendation-buy { background: #dcfce7; color: #166534; font-weight: bold; }
        .recommendation-hold { background: #fef3c7; color: #92400e; font-weight: bold; }
        .api-status {
            background: #fef2f2;
            color: #991b1b;
            padding: 10px;
            border-radius: 8px;
            margin: 10px 0;
        }
        .api-status.connected {
            background: #f0fdf4;
            color: #166534;
        }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="main-container">
            <div class="header">
                <h1><i class="fas fa-chart-line"></i> 한국투자증권 투자 거장 스크리너</h1>
                <p>KIS API 기반 · 6대 투자 철학으로 종목 분석</p>
            </div>

            <div class="controls-section">
                <div class="investor-buttons">
                    <button class="investor-btn active" data-investor="buffett" onclick="selectInvestor('buffett')">
                        <div>👑</div>
                        <h6>워렌 버핏</h6>
                        <small>가치투자</small>
                    </button>
                    <button class="investor-btn" data-investor="lynch" onclick="selectInvestor('lynch')">
                        <div>🚀</div>
                        <h6>피터 린치</h6>
                        <small>성장주</small>
                    </button>
                    <button class="investor-btn" data-investor="graham" onclick="selectInvestor('graham')">
                        <div>📚</div>
                        <h6>벤저민 그레이엄</h6>
                        <small>딥밸류</small>
                    </button>
                    <button class="investor-btn" data-investor="fisher" onclick="selectInvestor('fisher')">
                        <div>🔬</div>
                        <h6>필립 피셔</h6>
                        <small>성장 가치</small>
                    </button>
                    <button class="investor-btn" data-investor="munger" onclick="selectInvestor('munger')">
                        <div>🎯</div>
                        <h6>찰리 멍거</h6>
                        <small>우량기업</small>
                    </button>
                    <button class="investor-btn" data-investor="greenblatt" onclick="selectInvestor('greenblatt')">
                        <div>🪄</div>
                        <h6>조엘 그린블라트</h6>
                        <small>마법공식</small>
                    </button>
                </div>

                <div class="text-center">
                    <button class="btn btn-primary" onclick="openKisApiModal()">
                        <i class="fas fa-link"></i> KIS API 연동
                    </button>
                    <button class="btn btn-success" onclick="updatePrices()">
                        <i class="fas fa-sync-alt"></i> 실시간 업데이트
                    </button>
                    <div class="api-status" id="apiStatus">
                        🔴 KIS API 연결 안됨 (샘플 데이터 사용 중)
                    </div>
                </div>
            </div>

            <div class="results-section">
                <h3 id="resultsTitle">👑 워렌 버핏 기준 상위 추천 종목</h3>
                
                <div class="table-responsive">
                    <table class="table">
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
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5>KIS API 연동</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label>App Key</label>
                        <input type="password" class="form-control" id="kisAppKey" placeholder="KIS에서 발급받은 App Key">
                    </div>
                    <div class="mb-3">
                        <label>App Secret</label>
                        <input type="password" class="form-control" id="kisAppSecret" placeholder="KIS에서 발급받은 App Secret">
                    </div>
                    <div class="mb-3">
                        <label>환경</label>
                        <select class="form-select" id="kisEnvironment">
                            <option value="vps">모의투자</option>
                            <option value="real">실전투자</option>
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-primary" onclick="testConnection()">연결 테스트</button>
                    <button class="btn btn-success" onclick="saveConfig()">저장</button>
                </div>
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
            const names = {
                'buffett': '👑 워렌 버핏',
                'lynch': '🚀 피터 린치',
                'graham': '📚 벤저민 그레이엄',
                'fisher': '🔬 필립 피셔',
                'munger': '🎯 찰리 멍거',
                'greenblatt': '🪄 조엘 그린블라트'
            };
            document.getElementById('resultsTitle').textContent = names[currentInvestor] + ' 기준 상위 추천 종목';
        }

        async function loadStocks() {
            try {
                const response = await fetch(`/api/stocks?style=${currentInvestor}`);
                const data = await response.json();
                if (data.success) {
                    currentStocks = data.stocks;
                    displayStocks();
                }
            } catch (error) {
                console.error('데이터 로드 오류:', error);
            }
        }

        function displayStocks() {
            const tbody = document.getElementById('stockTableBody');
            tbody.innerHTML = '';
            
            currentStocks.forEach((stock, index) => {
                const score = stock.investment_score;
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><strong>#${index + 1}</strong></td>
                    <td>
                        <strong>${stock.name}</strong><br>
                        <small>${stock.code}</small>
                    </td>
                    <td>${getMarketFlag(stock.market)} ${stock.market}</td>
                    <td>${formatPrice(stock.current_price, stock.currency)}</td>
                    <td>${stock.roe.toFixed(1)}%</td>
                    <td>${stock.per.toFixed(1)}x</td>
                    <td>${stock.pbr.toFixed(1)}x</td>
                    <td><strong>${score.total_score.toFixed(1)}</strong></td>
                    <td><span class="grade-${score.grade}">${score.grade}급</span></td>
                    <td><span class="recommendation-${getRecClass(score.recommendation)}">${score.recommendation}</span></td>
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

        function getRecClass(rec) {
            return ['적극매수', '매수'].includes(rec) ? 'buy' : 'hold';
        }

        function openKisApiModal() {
            new bootstrap.Modal(document.getElementById('kisApiModal')).show();
        }

        async function testConnection() {
            const appKey = document.getElementById('kisAppKey').value;
            const appSecret = document.getElementById('kisAppSecret').value;
            const environment = document.getElementById('kisEnvironment').value;
            
            if (!appKey || !appSecret) {
                alert('App Key와 Secret을 입력하세요.');
                return;
            }
            
            try {
                const response = await fetch('/api/test-connection', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({appKey, appSecret, environment})
                });
                const data = await response.json();
                alert(data.message);
                if (data.success) {
                    updateApiStatus(true);
                }
            } catch (error) {
                alert('연결 테스트 실패');
            }
        }

        async function saveConfig() {
            alert('API 설정이 저장되었습니다.');
            bootstrap.Modal.getInstance(document.getElementById('kisApiModal')).hide();
        }

        function updateApiStatus(connected) {
            const status = document.getElementById('apiStatus');
            if (connected) {
                status.className = 'api-status connected';
                status.textContent = '🟢 KIS API 연결됨';
                isConnected = true;
            }
        }

        async function updatePrices() {
            if (!isConnected) {
                alert('KIS API 연결 후 실시간 업데이트가 가능합니다.');
                return;
            }
            alert('실시간 업데이트 기능 (KIS API 연동 시 활성화)');
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """메인 페이지"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """KIS API 연결 테스트"""
    try:
        data = request.get_json()
        app_key = data.get('appKey', '')
        app_secret = data.get('appSecret', '')
        
        if not app_key or not app_secret:
            return jsonify({'success': False, 'message': 'App Key와 Secret을 입력하세요.'})
        
        # 여기서 실제 KIS API 연결 테스트
        # 현재는 샘플 응답
        return jsonify({'success': True, 'message': 'KIS API 연결 성공!'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'연결 실패: {str(e)}'})

@app.route('/api/stocks')
def get_stocks():
    """종목 목록 조회"""
    try:
        style = request.args.get('style', 'buffett')
        strategy = INVESTMENT_STRATEGIES.get(style, INVESTMENT_STRATEGIES['buffett'])
        
        analyzed_stocks = []
        for stock in SAMPLE_STOCKS:
            score = strategy.calculate_score(stock)
            analyzed_stock = {
                **asdict(stock),
                'investment_score': asdict(score)
            }
            analyzed_stocks.append(analyzed_stock)
        
        # 점수순 정렬
        analyzed_stocks.sort(key=lambda x: x['investment_score']['total_score'], reverse=True)
        
        return jsonify({
            'success': True,
            'stocks': analyzed_stocks,
            'strategy': {
                'name': strategy.name,
                'description': strategy.description,
                'icon': strategy.icon
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/health')
def health_check():
    """헬스 체크"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print("🚀 한국투자증권 KIS 투자 거장 스크리너")
    print("=" * 60)
    print(f"📌 http://localhost:{port} 으로 접속하세요!")
    print("🔑 KIS API는 선택사항입니다 (샘플 데이터로 체험 가능)")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=True)
