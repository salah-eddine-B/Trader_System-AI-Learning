from telethon import events
import logging

from Telegram.config import CHANNEL_IDS
from Telegram.services.signal_service import parse_signal
from Telegram.services.risk_service import prepare_trade
from Telegram.services.trade_service import execute_trade

log = logging.getLogger("BOT")

# prevent duplicate messages
_last_messages = set()


def register_handlers(client):
    @client.on(events.NewMessage(chats=CHANNEL_IDS))
    async def handle_signal(event):
        try:
            msg = event.message.message

            if not msg or not msg.strip():
                return

            # prevent duplicates
            if msg in _last_messages:
                log.warning("Duplicate message skipped")
                return

            _last_messages.add(msg)

            log.info(f"New signal message:\n{msg}")

            # ── STEP 1: PARSE ──
            signal = parse_signal(msg)
            log.info(f"Parsed signal: {signal}")

            if not signal.get("valid"):
                log.warning("Invalid signal — skipped")
                return

            # ── STEP 2: PREPARE (RISK) ──
            trade = prepare_trade(signal)

            if not trade:
                log.warning("Trade preparation failed")
                return

            log.info(f"Prepared trade: {trade}")

            # ── STEP 3: EXECUTE ──
            results = execute_trade(trade)

            if results:
                log.info(f"{len(results)} trades executed successfully")
            else:
                log.error("Trade execution failed")

        except Exception as e:
            log.exception(f"Handler error: {e}")