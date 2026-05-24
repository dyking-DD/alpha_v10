import uuid, asyncio, logging
from datetime import datetime
from sqlalchemy import select
from db.models import TradeIntent

logger = logging.getLogger("engine.oms")

class AtomicOMS:
    def __init__(self, exchange, session_maker):
        self.exchange = exchange
        self.Session = session_maker
        self._pending_symbols = set()

    async def execute(self, symbol, side, amount, audit_mode=False):
        if symbol in self._pending_symbols:
            logger.warning(f"跳过 {symbol}，正在执行中")
            return None
        self._pending_symbols.add(symbol)
        intent_id = str(uuid.uuid4())

        try:
            # 1. WAL 写入
            async with self.Session() as session:
                async with session.begin():
                    session.add(TradeIntent(id=intent_id, symbol=symbol, side=side,
                                            amount=amount, status="PENDING"))
            if audit_mode:
                logger.info(f"[审计] 模拟成交: {side} {amount} {symbol}")
                async with self.Session() as session:
                    async with session.begin():
                        stmt = select(TradeIntent).where(TradeIntent.id == intent_id).with_for_update()
                        result = await session.execute(stmt)
                        intent = result.scalars().first()
                        if intent: intent.status = "FILLED"
                return {"status": "audit", "intent_id": intent_id}

            # 2. 真实下单
            try:
                order = await asyncio.wait_for(
                    self.exchange.create_order(symbol, 'market', side, amount),
                    timeout=8.0
                )
                async with self.Session() as session:
                    async with session.begin():
                        stmt = select(TradeIntent).where(TradeIntent.id == intent_id).with_for_update()
                        result = await session.execute(stmt)
                        intent = result.scalars().first()
                        if intent: intent.status = "FILLED"
                logger.info(f"成交: {symbol} {side} {amount}")
                return order
            except asyncio.TimeoutError:
                logger.critical(f"超时: {symbol}，标记为 TIMEOUT")
                async with self.Session() as session:
                    async with session.begin():
                        stmt = select(TradeIntent).where(TradeIntent.id == intent_id).with_for_update()
                        result = await session.execute(stmt)
                        intent = result.scalars().first()
                        if intent: intent.status = "TIMEOUT"
                return None
            except Exception as e:
                logger.error(f"订单失败: {e}")
                async with self.Session() as session:
                    async with session.begin():
                        stmt = select(TradeIntent).where(TradeIntent.id == intent_id).with_for_update()
                        result = await session.execute(stmt)
                        intent = result.scalars().first()
                        if intent: intent.status = "FAILED"
                return None
        finally:
            self._pending_symbols.discard(symbol)
