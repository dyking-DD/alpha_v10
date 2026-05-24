import asyncio, logging
from datetime import datetime
from sqlalchemy import select, delete
from db.models import PositionRecord, TradeIntent, ReconciliationAudit
from sqlalchemy import text

logger = logging.getLogger("engine.reconciliation")

class ReconciliationEngine:
    def __init__(self, exchange, session_maker):
        self.exchange = exchange
        self.Session = session_maker
        self.reconciling = False

    async def run_full_reconciliation(self):
        if self.reconciling:
            return
        self.reconciling = True
        try:
            async with self.Session() as session:
                await session.execute(text("BEGIN IMMEDIATE"))
                ep = await self._fetch_safe()
                if ep is None:
                    raise RuntimeError("交易所数据异常，终止对账")
                await self._align(session, ep)
                await self._resolve_pending(session)
                await session.commit()
                logger.info("对账完成")
        except Exception as e:
            logger.critical(f"对账失败: {e}")
            raise
        finally:
            self.reconciling = False

    async def _fetch_safe(self):
        for i in range(3):
            try:
                pos = await self.exchange.fetch_positions()
                r = {}
                for p in pos:
                    amt = float(p.get('contracts', 0))
                    if amt != 0:
                        r[p['symbol']] = {'amount': amt, 'entry': float(p.get('entryPrice', 0))}
                logger.info(f"交易所返回持仓数: {len(r)}")
                return r
            except Exception as e:
                logger.warning(f"获取失败 ({i+1}/3): {e}")
                await asyncio.sleep(1)
        return None

    async def _align(self, session, ep):
        result = await session.execute(select(PositionRecord))
        local = {r.symbol: r for r in result.scalars()}
        lc, ec = len(local), len(ep)
        allow_del = not (lc > 4 and ec < lc * 0.5)
        if not allow_del:
            logger.critical("安全阀触发，跳过删除操作")
        for sym, dat in ep.items():
            if sym not in local:
                logger.warning(f"补录持仓: {sym}")
                session.add(PositionRecord(symbol=sym, amount=dat['amount'], entry_price=dat['entry']))
        if allow_del:
            for sym, rec in local.items():
                if sym not in ep:
                    logger.warning(f"删除幽灵持仓: {sym}")
                    await session.execute(delete(PositionRecord).where(PositionRecord.symbol == sym))

    async def _resolve_pending(self, session):
        result = await session.execute(
            select(TradeIntent).where(TradeIntent.status.in_(["PENDING", "TIMEOUT"]))
        )
        for intent in result.scalars().all():
            logger.warning(f"未确认意图: {intent.id}")
            session.add(ReconciliationAudit(
                id=str(uuid.uuid4()),
                symbol=intent.symbol,
                field="intent_status",
                exchange_value=0, local_value_before=0,
                action_taken=f"pending_intent_{intent.id}_requires_manual_check"
            ))
