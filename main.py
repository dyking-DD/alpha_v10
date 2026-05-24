import asyncio, os, sys, logging, ccxt.async_support as ccxt
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from db.models import Base
from engine.oms import AtomicOMS
from engine.reconciliation import ReconciliationEngine
from engine.risk import RiskEngine
from engine.market import MarketEngine

DB_URL = "sqlite+aiosqlite:////root/alpha_v10/alpha_v10.db"
LOG_FILE = "/root/alpha_v10/system.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
logger = logging.getLogger("main")

class AlphaV10_6:
    def __init__(self, audit_mode=True):
        self.audit = audit_mode
        self.engine = create_async_engine(DB_URL)
        self.Session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.exchange = None
        self.oms = None
        self.recon = None
        self.risk = RiskEngine()
        self.market = MarketEngine()
        self.peak_equity = 0
        self.current_equity = 0

    async def init(self):
        logger.info("Alpha V10.6 启动")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        api_key = os.getenv("OKX_API_KEY")
        if not api_key:
            logger.warning("未设置API密钥，仅审计模式可用")
            self.exchange = None
        else:
            self.exchange = ccxt.okx({
                'apiKey': api_key,
                'secret': os.getenv("OKX_SECRET_KEY"),
                'password': os.getenv("OKX_PASSPHRASE"),
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'}
            })
            logger.info("交易所连接成功")

        self.oms = AtomicOMS(self.exchange, self.Session)
        self.recon = ReconciliationEngine(self.exchange, self.Session)

        # 启动对账
        await self.recon.run_full_reconciliation()

        if self.exchange:
            try:
                bal = await self.exchange.fetch_balance()
                self.current_equity = float(bal.get('USDT', {}).get('total', 0))
                self.peak_equity = self.current_equity
                logger.info(f"账户权益: {self.current_equity:.2f} USDT")
            except: pass
        logger.info("初始化完成")

    async def run(self):
        await self.init()
        while True:
            try:
                if self.exchange:
                    score = await self.market.get_score(self.exchange)
                    try:
                        bal = await self.exchange.fetch_balance()
                        self.current_equity = float(bal.get('USDT', {}).get('total', 0))
                        self.peak_equity = max(self.peak_equity, self.current_equity)
                    except: pass
                    if self.risk.check_meltdown(self.current_equity, self.peak_equity):
                        logger.critical("熔断状态中，禁止开仓")
                    rp = self.risk.report(self.current_equity, [], self.peak_equity)
                    logger.info(f"权益={rp['equity']} 回撤={rp['drawdown_pct']}% 熔断={rp['meltdown']}")
                # 定时对账
                if datetime.now().hour % 6 == 0:
                    await self.recon.run_full_reconciliation()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"主循环异常: {e}")
                await asyncio.sleep(30)

if __name__ == "__main__":
    audit = "--live" not in sys.argv  # 默认审计模式，加 --live 切实盘
    asyncio.run(AlphaV10_6(audit_mode=audit).run())
