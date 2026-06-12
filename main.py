import asyncio
import logging
import MetaTrader5 as mt5

from mt5_client import initialize, shutdown
from Telegram.core.telegram_client import start_telegram
from Telegram.handlers.telegram_handlers import register_handlers
from Telegram.services.monitor_service import start_monitor


# ─────────────────────────────
# 📋 LOGGING SETUP
# ─────────────────────────────
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("trader_system.log", encoding="utf-8"),
        ]
    )

log = logging.getLogger("BOT")


# ─────────────────────────────
# 📡 MONITOR EVENT HANDLER
# ─────────────────────────────
async def on_position_event(event_type: str, data):
    if event_type == "POSITION_OPENED":
        log.info(f"📬 Position opened: ticket={data.ticket} | {data.symbol}")
    elif event_type == "POSITION_CLOSED":
        if data:
            profit = getattr(data, "profit", "?")
            log.info(f"📭 Position closed: ticket={data.position_id} | P&L={profit}")
        else:
            log.info("📭 A position was closed (no deal data found)")


# ─────────────────────────────
# 🚀 MAIN
# ─────────────────────────────
async def main():
    client = None
    monitor_task = None

    try:
        # ── INIT LOGGING ──
        setup_logging()
        log.info("=" * 50)
        log.info("🚀 Trader System starting...")
        log.info("=" * 50)

        # ── INIT MT5 ──
        if not initialize():
            log.critical("MT5 initialization failed — exiting")
            return

        # ── START TELEGRAM ──
        client = await start_telegram()
        if not client:
            log.critical("Telegram client failed to start — exiting")
            return

        # ── REGISTER SIGNAL HANDLERS ──
        register_handlers(client)
        log.info("✅ Signal handlers registered")

        # ── START POSITION MONITOR (background task) ──
        monitor_task = asyncio.create_task(
            start_monitor(event_callback=on_position_event),
            name="position_monitor"
        )
        log.info("✅ Position monitor started")

        log.info("=" * 50)
        log.info("✅ Trader System running — listening for signals...")
        log.info("   Press Ctrl+C to stop")
        log.info("=" * 50)

        # Keep alive until Ctrl+C or Telegram disconnects
        await client.run_until_disconnected()

    except asyncio.CancelledError:
        pass  # Clean shutdown — not an error

    except Exception as e:
        log.exception(f"Fatal error: {e}")

    finally:
        log.info("Shutting down...")

        # Cancel monitor task
        if monitor_task and not monitor_task.done():
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        # Disconnect Telegram
        if client and client.is_connected():
            await client.disconnect()
            log.info("Telegram disconnected")

        # Shutdown MT5
        shutdown()

        log.info("Trader System stopped.")


# ─────────────────────────────
# ▶️ ENTRY POINT
# ─────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Suppress Ctrl+C traceback
