import json
import logging
from datetime import datetime
import mt5_client
from Telegram.config import LOT_SIZE

log = logging.getLogger("BOT")

TRADES_FILE = "storage/trades.json"


# ─────────────────────────────
# 💾 LOG TRADE
# ─────────────────────────────
def log_trade(trade, ticket, tp):
    try:
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": trade["symbol"],
            "action": trade["action"],
            "entry": trade["entry"],
            "sl": trade["sl"],
            "tp": tp,
            "lot": trade["lot"],
            "ticket": ticket
        }

        try:
            with open(TRADES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = []

        data.append(record)

        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        log.info(f"Trade logged: {ticket}")

    except Exception as e:
        log.exception(f"Trade logging failed: {e}")


# ─────────────────────────────
# 🚀 EXECUTE TRADE
# ─────────────────────────────
def execute_trade(prepared_trade: dict):
    try:
        symbol = prepared_trade["symbol"]
        action = prepared_trade["action"]
        entry  = prepared_trade["entry"]
        sl     = prepared_trade["sl"]
        tps    = prepared_trade["tps"]
        lot    = prepared_trade["lot"]

        log.info(f"Executing trade: {symbol} {action}")

        results = []

        for i, tp in enumerate(tps):
            result = mt5_client.send_order(
                symbol=symbol,
                action=action,
                volume=lot,
                price=entry,
                sl=sl,
                tp=tp,
                comment=f"TP{i+1}"
            )

            if result:
                log.info(f"TP{i+1} success | ticket={result.order}")
                log_trade(prepared_trade, result.order, tp)
                results.append(result)
            else:
                log.error(f"TP{i+1} failed")

        return results

    except Exception as e:
        log.exception(f"Execution failed: {e}")
        return []