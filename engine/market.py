import logging, pandas as pd, numpy as np
logger = logging.getLogger("engine.market")

class MarketEngine:
    async def get_score(self, exchange):
        try:
            ohlcv = await exchange.fetch_ohlcv('BTC/USDT:USDT', '1d', limit=30)
            if not ohlcv or len(ohlcv) < 20: return 50.0
            df = pd.DataFrame(ohlcv, columns=['ts','o','h','l','c','v'])
            price, ma20 = df['c'].iloc[-1], df['c'].rolling(20).mean().iloc[-1]
            trend = min(max((price / ma20 - 0.95) * 200, 0), 40)
            vol = df['c'].pct_change().dropna().std() * np.sqrt(365)
            vol_score = 20 if 0.3 < vol < 0.8 else (10 if vol <= 0.3 else 5)
            try:
                fr = (await exchange.fetch_funding_rate('BTC/USDT:USDT')).get('fundingRate', 0) if isinstance(await exchange.fetch_funding_rate('BTC/USDT:USDT'), dict) else 0
                fr_score = 20 if fr > 0.001 else (10 if fr > -0.005 else 0)
            except: fr_score = 10
            total = trend + vol_score + fr_score
            logger.info(f"市场评分: {total:.1f}")
            return total
        except Exception as e:
            logger.error(f"评分异常: {e}")
            return 50.0
