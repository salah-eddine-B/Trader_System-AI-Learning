import logging
import mt5_client
from Telegram.config import RISK_PERCENT, LOT_SIZE

log = logging.getLogger("BOT")


# ─────────────────────────────
# 💰 CALCULATE SL DISTANCE
# ─────────────────────────────
def calculate_sl_distance(symbol: str) -> float:
    try:
        acc = mt5_client.get_account_info()
        if not acc:
            raise ValueError("No account info")

        sym_info = mt5_client.get_symbol_info(symbol)
        if not sym_info:
            raise ValueError("No symbol info")

        risk_amount = acc["balance"] * RISK_PERCENT

        tick_value = sym_info.trade_tick_value
        tick_size  = sym_info.trade_tick_size

        if tick_value <= 0 or tick_size <= 0:
            raise ValueError("Invalid tick data")

        sl_distance = (risk_amount / (tick_value * LOT_SIZE)) * tick_size

        log.info(f"SL distance calculated: {sl_distance}")
        return round(sl_distance, 2)

    except Exception as e:
        log.warning(f"SL calculation failed: {e}")
        return 15.0  # fallback


# ─────────────────────────────
# 🎯 CALCULATE SL PRICE
# ─────────────────────────────
def calculate_sl(symbol, action, entry_price, signal_sl=None):
    if signal_sl:
        return signal_sl

    distance = calculate_sl_distance(symbol)

    if action == "BUY":
        return round(entry_price - distance, 2)
    else:
        return round(entry_price + distance, 2)


# ─────────────────────────────
# 📊 VALIDATE TPS
# ─────────────────────────────
def validate_tps(action, entry_price, sl, tps):
    valid = []

    for tp in tps:
        if action == "BUY":
            if tp > entry_price and tp > sl:
                valid.append(tp)
        else:
            if tp < entry_price and tp < sl:
                valid.append(tp)

    return valid


# ─────────────────────────────
# 📦 LOT DISTRIBUTION
# ─────────────────────────────
def split_lot(symbol, total_lot, num_trades):
    sym_info = mt5_client.get_symbol_info(symbol)

    min_lot  = sym_info.volume_min if sym_info else 0.01
    step     = sym_info.volume_step if sym_info else 0.01

    per_trade = max(min_lot, round(total_lot / num_trades, 2))
    per_trade = round(round(per_trade / step) * step, 2)

    return per_trade


# ─────────────────────────────
# 🛡 FINAL PREPARATION
# ─────────────────────────────
def prepare_trade(signal: dict):
    try:
        symbol = mt5_client.resolve_symbol(signal["symbol"])
        if not symbol:
            log.error(f"Symbol not found: {signal['symbol']}")
            return None

        tick = mt5_client.get_tick(symbol)
        if not tick:
            return None

        action = signal["action"]
        entry  = signal["entry"] or (tick.ask if action == "BUY" else tick.bid)

        sl = calculate_sl(symbol, action, entry, signal.get("sl"))

        valid_tps = validate_tps(action, entry, sl, signal.get("tps", []))

        if not valid_tps:
            log.warning("No valid TP — fallback will be used")
            valid_tps = [entry + 10] if action == "BUY" else [entry - 10]

        lot = split_lot(symbol, LOT_SIZE, len(valid_tps))

        return {
            "symbol": symbol,
            "action": action,
            "entry": entry,
            "sl": sl,
            "tps": valid_tps,
            "lot": lot
        }

    except Exception as e:
        log.exception(f"Trade preparation failed: {e}")
        return None