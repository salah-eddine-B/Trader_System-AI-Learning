import asyncio
import logging
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import mt5_client

log = logging.getLogger("BOT")

POLL_INTERVAL = 10


# ─────────────────────────────
# 🔍 POSITION MONITOR
# ─────────────────────────────
async def start_monitor(event_callback=None):
    """
    Monitors positions and emits events
    event_callback(event_type, data)
    """

    known = {p.ticket for p in mt5_client.get_positions()}
    log.info(f"Monitor started — tracking {len(known)} positions")

    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL)

            current_positions = mt5_client.get_positions()
            current = {p.ticket: p for p in current_positions}
            current_ids = set(current.keys())

            # ── NEW POSITIONS ──
            for ticket in current_ids - known:
                pos = current[ticket]

                log.info(f"New position detected: {ticket}")

                if event_callback:
                    await event_callback("POSITION_OPENED", pos)

            # ── CLOSED POSITIONS ──
            for ticket in known - current_ids:
                log.info(f"Position closed: {ticket}")

                deal = _get_last_deal(ticket)

                if event_callback:
                    await event_callback("POSITION_CLOSED", deal)

            known = current_ids

        except Exception as e:
            log.exception(f"Monitor error: {e}")


# ─────────────────────────────
# 📊 DEAL HISTORY
# ─────────────────────────────
def _get_last_deal(ticket):
    try:
        now = datetime.now()
        from_dt = now - timedelta(hours=24)

        history = mt5.history_deals_get(
            int(from_dt.timestamp()),
            int(now.timestamp())
        )

        if not history:
            return None

        matches = [d for d in history if d.position_id == ticket]
        return matches[-1] if matches else None

    except Exception as e:
        log.warning(f"Deal fetch failed: {e}")
        return None