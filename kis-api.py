#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
한국투자증권 KIS API 관리 모듈
실시간 코스피 데이터 수집 및 관리
"""

import os
import json
import requests
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KISApiManager:
    """한국투자증권 OpenAPI 관리 클래스"""
    
    def __init__(self, app_key: str = None, app_secret: str = None, 
                 account_no: str = None, environment: str = 'vps'):
        """
        초기화
        
        Args:
            app_key: KIS API App Key
            app_secret: KIS API App Secret
            account_no: 계좌번호 (8자리-2자리)
            environment: 'vps' (모의투자) 또는 'real' (실전투자)
        """
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
        
    def _ensure_token(self) -> bool:
        """토큰 유효성 확인 및 갱신"""
        if self.access_token and self.token_expires:
            if datetime.now() < self.token_expires:
                return True
        
        return self.get_access_token()
    
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
                # 토큰 만료시간 설정 (23시간)
                self.token_expires = datetime.now() + timedelta(hours=23)
                logger.info(f"KIS API 토큰 발급 성공 (환경: {self.environment})")
                return True
            else:
                logger.error(f"토큰 발급 실패: {result}")
                return False
                
        except Exception as e:
            logger.error(f"토큰 발급 오류: {e}")
            return False
    
    def _get_hashkey(self, data: dict) -> str:
        """거래 API용 해시키 생성"""
        url = f"{self.base_url}/uapi/hashkey"
        headers = {
            'content-Type': 'application/json',
            'appKey': self.app_key,
            'appSecret': self.app_secret
        }
        
        try:
            response = self.session.post(url, headers=headers, json=data, timeout=10)
            if response.status_code == 200:
                return response.json().get('HASH', '')
        except Exception as e:
            logger.error(f"해시키 생성 오류: {e}")
        
        return ''
    
    def get_kospi_stock_list(self) -> List[Dict]:
        """코스피 전종목 기본 정보 조회"""
        if not self._ensure_token():
            return []
        
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-member"
        headers = {
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100"  # 주식 현재가 시세
        }
        
        stocks = []
        try:
            # 코스피 주요 종목 리스트 (실제로는 더 많은 종목 추가 필요)
            major_stocks = [
                '005930',  # 삼성전자
                '000660',  # SK하이닉스
                '035420',  # 네이버
                '005490',  # POSCO홀딩스
                '035720',  # 카카오
                '051910',  # LG화학
                '006400',  # 삼성SDI
                '005380',  # 현대차
                '000270',  # 기아
                '068270',  # 셀트리온
                '207940',  # 삼성바이오로직스
                '096770',  # SK이노베이션
                '028260',  # 삼성물산
                '012330',  # 현대모비스
                '066570',  # LG전자
                '003550',  # LG
                '015760',  # 한국전력
                '009150',  # 삼성전기
                '010950',  # S-Oil
                '017670',  # SK텔레콤
                '030200',  # KT
                '033780',  # KT&G
                '018260',  # 삼성에스디에스
                '032830',  # 삼성생명
                '003490',  # 대한항공
                '011200',  # HMM
                '090430',  # 아모레퍼시픽
                '010130',  # 고려아연
                '024110',  # 기업은행
                '086790',  # 하나금융지주
                '055550',  # 신한지주
                '105560',  # KB금융
                '316140',  # 우리금융지주
                '001570',  # 금양
                '047050',  # 포스코인터내셔널
                '009830',  # 한화솔루션
                '034730',  # SK
                '011170',  # 롯데케미칼
                '001040',  # CJ
                '004020',  # 현대제철
            ]
            
            for stock_code in major_stocks:
                stock_info = self.get_stock_price(stock_code)
                if stock_info:
                    stocks.append(stock_info)
                time.sleep(0.1)  # API 호출 제한
            
            logger.info(f"코스피 종목 {len(stocks)}개 조회 완료")
            return stocks
            
        except Exception as e:
            logger.error(f"코스피 종목 조회 오류: {e}")
            return []
    
    def get_stock_price(self, stock_code: str) -> Optional[Dict]:
        """주식 현재가 및 기본 정보 조회"""
        if not self._ensure_token():
            return None
        
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = {
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100"
        }
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code
        }
        
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            result = response.json()
            
            if response.status_code == 200 and result.get('rt_cd') == '0':
                output = result.get('output', {})
                
                # 데이터 변환
                stock_data = {
                    'code': stock_code,
                    'name': output.get('stck_shrn_iscd_name', ''),
                    'current_price': float(output.get('stck_prpr', 0)),
                    'change_rate': float(output.get('prdy_ctrt', 0)),
                    'volume': int(output.get('acml_vol', 0)),
                    'trading_value': float(output.get('acml_tr_pbmn', 0)),
                    'market_cap': float(output.get('stck_mxpr', 0)) * int(output.get('lstn_stcn', 1)),
                    'per': float(output.get('per', 0)),
                    'pbr': float(output.get('pbr', 0)),
                    'eps': float(output.get('eps', 0)),
                    'bps': float(output.get('bps', 0)),
                    'high_52w': float(output.get('w52_hgpr', 0)),
                    'low_52w': float(output.get('w52_lwpr', 0)),
                    'foreign_rate': float(output.get('frgn_hldn_pvrg', 0)),
                    'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                return stock_data
            else:
                logger.warning(f"주식가격 조회 실패 ({stock_code}): {result.get('msg1', '')}")
                return None
                
        except Exception as e:
            logger.error(f"주식가격 조회 오류 ({stock_code}): {e}")
            return None
    
    def get_stock_fundamental(self, stock_code: str) -> Optional[Dict]:
        """주식 재무제표 정보 조회"""
        if not self._ensure_token():
            return None
        
        url = f"{self.base_url}/uapi/domestic-stock/v1/finance/income-statement"
        headers = {
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST66430200"  # 재무제표 조회
        }
        params = {
            "fid_div_cls_code": "0",  # 0: 연결, 1: 별도
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code
        }
        
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            result = response.json()
            
            if response.status_code == 200 and result.get('rt_cd') == '0':
                output = result.get('output', [])
                if output and len(output) > 0:
                    latest = output[0]  # 최신 재무제표
                    
                    fundamental_data = {
                        'revenue': float(latest.get('sale_account', 0)),
                        'operating_profit': float(latest.get('sale_cost', 0)),
                        'net_profit': float(latest.get('thtr_ntin', 0)),
                        'total_assets': float(latest.get('total_aset', 0)),
                        'total_equity': float(latest.get('total_cptl', 0)),
                        'total_debt': float(latest.get('total_debt', 0)),
                        'roe': self._calculate_roe(latest),
                        'roa': self._calculate_roa(latest),
                        'debt_ratio': self._calculate_debt_ratio(latest),
                        'current_ratio': float(latest.get('current_ratio', 100)),
                        'operating_margin': self._calculate_operating_margin(latest),
                        'net_margin': self._calculate_net_margin(latest)
                    }
                    
                    return fundamental_data
            
            return None
            
        except Exception as e:
            logger.error(f"재무제표 조회 오류 ({stock_code}): {e}")
            return None
    
    def _calculate_roe(self, data: dict) -> float:
        """ROE 계산"""
        try:
            net_profit = float(data.get('thtr_ntin', 0))
            equity = float(data.get('total_cptl', 1))
            return (net_profit / equity) * 100 if equity > 0 else 0
        except:
            return 0
    
    def _calculate_roa(self, data: dict) -> float:
        """ROA 계산"""
        try:
            net_profit = float(data.get('thtr_ntin', 0))
            assets = float(data.get('total_aset', 1))
            return (net_profit / assets) * 100 if assets > 0 else 0
        except:
            return 0
    
    def _calculate_debt_ratio(self, data: dict) -> float:
        """부채비율 계산"""
        try:
            debt = float(data.get('total_debt', 0))
            equity = float(data.get('total_cptl', 1))
            return (debt / equity) * 100 if equity > 0 else 0
        except:
            return 100
    
    def _calculate_operating_margin(self, data: dict) -> float:
        """영업이익률 계산"""
        try:
            operating_profit = float(data.get('sale_cost', 0))
            revenue = float(data.get('sale_account', 1))
            return (operating_profit / revenue) * 100 if revenue > 0 else 0
        except:
            return 0
    
    def _calculate_net_margin(self, data: dict) -> float:
        """순이익률 계산"""
        try:
            net_profit = float(data.get('thtr_ntin', 0))
            revenue = float(data.get('sale_account', 1))
            return (net_profit / revenue) * 100 if revenue > 0 else 0
        except:
            return 0
    
    def get_stock_full_data(self, stock_code: str) -> Optional[Dict]:
        """종목의 전체 데이터 조회 (가격 + 재무)"""
        price_data = self.get_stock_price(stock_code)
        if not price_data:
            return None
        
        # 재무 데이터 조회 (선택적)
        fundamental_data = self.get_stock_fundamental(stock_code)
        
        # 데이터 병합
        if fundamental_data:
            price_data.update(fundamental_data)
        else:
            # 재무 데이터가 없는 경우 기본값 설정
            price_data.update({
                'roe': 10.0,
                'roa': 5.0,
                'debt_ratio': 50.0,
                'current_ratio': 150.0,
                'operating_margin': 10.0,
                'net_margin': 5.0,
                'revenue_growth': 5.0,
                'profit_growth': 5.0
            })
        
        return price_data