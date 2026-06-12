import MetaTrader5 as mt5
import logging

log = logging.getLogger("BOT")

# ─────────────────────────────
# 🚀 INIT / SHUTDOWN
# ─────────────────────────────
def initialize() -> bool:
    if not mt5.initialize():
        log.critical(f"MT5 initialization failed: {mt5.last_error()}")
        return False
    log.info("MT5 initialized successfully")
    return True


def shutdown():
    mt5.shutdown()
    log.info("MT5 shutdown complete")


# ─────────────────────────────
# 📊 ACCOUNT
# ─────────────────────────────
def get_account_info() -> dict | None:
    info = mt5.account_info()
    if not info:
        log.warning(f"Failed to get account info: {mt5.last_error()}")
        return None

    return {
        "balance": info.balance,
        "equity": info.equity,
        "free_margin": info.margin_free,
        "profit": info.profit,
        "currency": info.currency,
        "leverage": info.leverage,
        "login": info.login,
    }


# ─────────────────────────────
# 🔍 SYMBOL RESOLUTION
# ─────────────────────────────
def resolve_symbol(symbol: str) -> str | None:
    """
    Checks if a symbol exists in MT5.
    Tries common broker suffixes if the base symbol is not found.
    """
    symbol = symbol.upper()

    # Try as-is first
    info = mt5.symbol_info(symbol)
    if info is not None:
        if not info.visible:
            mt5.symbol_select(symbol, True)
        return symbol

    # Try with common broker suffixes
    for suffix in [".r", ".m", "m", "pro", ".pro", ".ecn"]:
        candidate = symbol + suffix
        info = mt5.symbol_info(candidate)
        if info is not None:
            if not info.visible:
                mt5.symbol_select(candidate, True)
            log.info(f"Symbol resolved: {symbol} → {candidate}")
            return candidate

    log.warning(f"Symbol not found in MT5: {symbol}")
    return None


# ─────────────────────────────
# 📈 SYMBOL INFO
# ─────────────────────────────
def get_symbol_info(symbol: str):
    """Returns MT5 SymbolInfo object or None."""
    info = mt5.symbol_info(symbol)
    if not info:
        log.warning(f"No symbol info for: {symbol}")
    return info


# ─────────────────────────────
# 💹 TICK
# ─────────────────────────────
def get_tick(symbol: str):
    """Returns the latest tick for a symbol."""
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        log.warning(f"No tick data for: {symbol} — {mt5.last_error()}")
    return tick


# ─────────────────────────────
# 📂 OPEN POSITIONS
# ─────────────────────────────
def get_positions(symbol: str = None) -> list:
    """Returns a list of open positions. Optionally filtered by symbol."""
    if symbol:
        positions = mt5.positions_get(symbol=symbol)
    else:
        positions = mt5.positions_get()

    if positions is None:
        return []
    return list(positions)


# ─────────────────────────────
# 📤 SEND ORDER
# ─────────────────────────────
def send_order(
    symbol: str,
    action: str,        # "BUY" or "SELL"
    volume: float,
    price: float | None = None,
    sl: float = 0.0,
    tp: float = 0.0,
    comment: str = "",
    magic: int = 999999,
    deviation: int = 20,
):
    """
    Sends a market order.
    - BUY  → ORDER_TYPE_BUY  at ask price
    - SELL → ORDER_TYPE_SELL at bid price
    Returns the OrderSendResult or None on failure.
    """
    tick = get_tick(symbol)
    if not tick:
        log.error(f"Cannot send order — no tick for {symbol}")
        return None

    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
    exec_price  = price or (tick.ask if action == "BUY" else tick.bid)

    request = {
        "action":    mt5.TRADE_ACTION_DEAL,
        "symbol":    symbol,
        "volume":    float(volume),
        "type":      order_type,
        "price":     exec_price,
        "sl":        float(sl) if sl else 0.0,
        "tp":        float(tp) if tp else 0.0,
        "deviation": deviation,
        "magic":     magic,
        "comment":   comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        retcode = result.retcode if result else "None"
        log.error(f"Order failed: {symbol} {action} | retcode={retcode} | {mt5.last_error()}")
        return None

    log.info(f"Order placed: {symbol} {action} | ticket={result.order} | lot={volume} | tp={tp} | sl={sl}")
    return result
