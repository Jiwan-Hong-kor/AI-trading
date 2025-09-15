#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
투자 거장 전략 모듈
6대 투자 철학 기반 종목 평가 시스템
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Stock:
    """주식 데이터 클래스"""
    code: str
    name: str
    current_price: float
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


class GrahamStrategy(InvestmentStrategy):
    """벤저민 그레이엄 딥밸류 전략"""
    
    def __init__(self):
        super().__init__(
            name="벤저민 그레이엄",
            description="저평가 + 안전마진 + 재무안정성",
            icon="📚"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        scores = {}
        
        # 1. 저평가 (PER, PBR) - 4점
        valuation_score = 0
        if stock.per > 0:
            if stock.per <= 10:
                valuation_score += 2.0
            elif stock.per <= 15:
                valuation_score += 1.5
            elif stock.per <= 20:
                valuation_score += 1.0
            else:
                valuation_score += 0.5
        
        if stock.pbr > 0:
            if stock.pbr <= 1.0:
                valuation_score += 2.0
            elif stock.pbr <= 1.5:
                valuation_score += 1.5
            elif stock.pbr <= 2.0:
                valuation_score += 1.0
            else:
                valuation_score += 0.5
        
        scores['valuation'] = valuation_score
        
        # 2. 재무안정성 - 3점
        if stock.current_ratio >= 200:
            scores['financial_stability'] = 3.0
        elif stock.current_ratio >= 150:
            scores['financial_stability'] = 2.5
        elif stock.current_ratio >= 100:
            scores['financial_stability'] = 2.0
        else:
            scores['financial_stability'] = 1.0
        
        # 3. 수익성 - 3점
        if stock.roe >= 10 and stock.net_margin >= 5:
            scores['profitability'] = 3.0
        elif stock.roe >= 8 and stock.net_margin >= 3:
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


class FisherStrategy(InvestmentStrategy):
    """필립 피셔 성장가치 전략"""
    
    def __init__(self):
        super().__init__(
            name="필립 피셔",
            description="혁신성 + 장기성장 + 경영진 능력",
            icon="🔬"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        scores = {}
        
        # 1. 혁신성 (영업이익률) - 3점
        if stock.operating_margin >= 25:
            scores['innovation'] = 3.0
        elif stock.operating_margin >= 20:
            scores['innovation'] = 2.5
        elif stock.operating_margin >= 15:
            scores['innovation'] = 2.0
        else:
            scores['innovation'] = 1.0
        
        # 2. 성장 잠재력 - 4점
        growth_score = 0
        if stock.revenue_growth >= 15:
            growth_score += 2.0
        elif stock.revenue_growth >= 10:
            growth_score += 1.5
        else:
            growth_score += 1.0
        
        if stock.profit_growth >= 15:
            growth_score += 2.0
        elif stock.profit_growth >= 10:
            growth_score += 1.5
        else:
            growth_score += 1.0
        
        scores['growth'] = growth_score
        
        # 3. 경영진 능력 (ROE) - 3점
        if stock.roe >= 20:
            scores['management'] = 3.0
        elif stock.roe >= 15:
            scores['management'] = 2.5
        elif stock.roe >= 12:
            scores['management'] = 2.0
        else:
            scores['management'] = 1.0
        
        total_score = sum(scores.values())
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=round(total_score, 2),
            grade=grade,
            recommendation=recommendation,
            details=scores
        )


class MungerStrategy(InvestmentStrategy):
    """찰리 멍거 우량기업 전략"""
    
    def __init__(self):
        super().__init__(
            name="찰리 멍거",
            description="단순한 비즈니스 + 경쟁우위 + 합리적 가격",
            icon="🎯"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        scores = {}
        
        # 1. 비즈니스 품질 (ROE, 마진) - 4점
        quality_score = 0
        if stock.roe >= 15:
            quality_score += 2.0
        elif stock.roe >= 12:
            quality_score += 1.5
        else:
            quality_score += 1.0
        
        if stock.operating_margin >= 15:
            quality_score += 2.0
        elif stock.operating_margin >= 10:
            quality_score += 1.5
        else:
            quality_score += 1.0
        
        scores['business_quality'] = quality_score
        
        # 2. 경쟁우위 (시장지배력) - 3점
        if stock.market_cap >= 10000000:  # 10조원 이상
            scores['competitive_advantage'] = 3.0
        elif stock.market_cap >= 5000000:  # 5조원 이상
            scores['competitive_advantage'] = 2.5
        elif stock.market_cap >= 1000000:  # 1조원 이상
            scores['competitive_advantage'] = 2.0
        else:
            scores['competitive_advantage'] = 1.0
        
        # 3. 합리적 가격 - 3점
        if stock.per > 0 and stock.per <= 15 and stock.pbr <= 2:
            scores['valuation'] = 3.0
        elif stock.per > 0 and stock.per <= 20 and stock.pbr <= 3:
            scores['valuation'] = 2.0
        else:
            scores['valuation'] = 1.0
        
        total_score = sum(scores.values())
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=round(total_score, 2),
            grade=grade,
            recommendation=recommendation,
            details=scores
        )


class GreenblattStrategy(InvestmentStrategy):
    """조엘 그린블라트 마법공식 전략"""
    
    def __init__(self):
        super().__init__(
            name="조엘 그린블라트",
            description="자본수익률(ROA) + 이익수익률(1/PER)",
            icon="🪄"
        )
    
    def calculate_score(self, stock: Stock) -> InvestmentScore:
        scores = {}
        
        # 1. 자본수익률 (ROA) - 5점
        if stock.roa >= 20:
            scores['capital_return'] = 5.0
        elif stock.roa >= 15:
            scores['capital_return'] = 4.0
        elif stock.roa >= 10:
            scores['capital_return'] = 3.0
        elif stock.roa >= 7:
            scores['capital_return'] = 2.0
        else:
            scores['capital_return'] = 1.0
        
        # 2. 이익수익률 (1/PER) - 5점
        if stock.per > 0:
            earnings_yield = 100 / stock.per
            if earnings_yield >= 15:  # PER 6.67 이하
                scores['earnings_yield'] = 5.0
            elif earnings_yield >= 10:  # PER 10 이하
                scores['earnings_yield'] = 4.0
            elif earnings_yield >= 7:  # PER 14.3 이하
                scores['earnings_yield'] = 3.0
            elif earnings_yield >= 5:  # PER 20 이하
                scores['earnings_yield'] = 2.0
            else:
                scores['earnings_yield'] = 1.0
        else:
            scores['earnings_yield'] = 1.0
        
        total_score = sum(scores.values())
        grade = self.get_grade(total_score)
        recommendation = self.get_recommendation(grade, stock)
        
        return InvestmentScore(
            total_score=round(total_score, 2),
            grade=grade,
            recommendation=recommendation,
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