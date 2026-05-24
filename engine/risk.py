import logging
logger = logging.getLogger("engine.risk")

class RiskEngine:
    def __init__(self):
        self.base_risk = 0.005
        self.max_daily_loss = 0.05
        self.max_position_ratio = 0.30
        self.meltdown = False

    def position_size(self, equity, price, natr):
        if not natr or natr <= 0: natr = 0.02
        risk_amt = equity * self.base_risk
        size = risk_amt / (price * natr * 2.0)
        max_size = (equity * self.max_position_ratio) / price
        return min(size, max_size)

    def check_meltdown(self, current, peak):
        if peak <= 0: return False
        if (peak - current) / peak >= self.max_daily_loss:
            if not self.meltdown:
                logger.critical(f"熔断触发！回撤: {(peak - current) / peak:.2%}")
                self.meltdown = True
            return True
        return False

    def report(self, equity, positions, peak):
        dd = (peak - equity) / peak if peak > 0 else 0
        return {
            "equity": round(equity, 2),
            "drawdown_pct": round(dd * 100, 2),
            "meltdown": self.meltdown,
            "positions": len(positions) if positions else 0
        }
