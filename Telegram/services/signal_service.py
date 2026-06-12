import json
import time
import logging
import re
from google import genai

from Telegram.config import GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger("BOT")

_client = genai.Client(api_key=GEMINI_API_KEY)


# ─────────────────────────────
# 🧹 NOISE FILTER
# ─────────────────────────────
def is_noise_signal(text: str) -> bool:
    bad_keywords = [
        "join our", "vip group", "subscribe now", "whatsapp group",
        "profit guarantee", "free signal group", "earn money fast",
        "signal group", "limited offer", "click here", "register now"
    ]

    text_lower = text.lower()
    
    # Check if message has trading keywords (symbol + action)
    has_symbol = any(sym in text_lower for sym in ["xau", "eur", "gbp", "usd", "btc", "gold", "oil"])
    has_action = any(act in text_lower for act in ["buy", "sell"])
    
    # If it has trading keywords, it's likely a signal, not noise
    if has_symbol and has_action:
        return False
    
    # Otherwise check for noise keywords
    return any(word in text_lower for word in bad_keywords)


# ─────────────────────────────
# 🧠 MAIN PARSER
# ─────────────────────────────
def parse_signal(message: str, retries: int = 3, wait: int = 1) -> dict:

    # 🚫 FILTER NOISE EARLY
    if is_noise_signal(message):
        log.warning(f"❌ Signal rejected: NOISE DETECTED - Message contains promotional keywords without trading data")
        return {"valid": False, "reason": "noise_detected"}

    prompt = f"""
You are a PROFESSIONAL trading signal extraction system.

Extract ONLY valid trading signals.

If NOT a valid signal → return empty JSON: {{}}

────────────────────────
OUTPUT FORMAT (STRICT)
────────────────────────
{{
  "symbol": "XAUUSD",
  "action": "BUY",
  "entry": 0,
  "sl": 0,
  "tps": [0, 0, 0],
  "confidence": 0.0
}}

────────────────────────
RULES
────────────────────────
- symbol must be valid (XAUUSD, EURUSD, BTCUSD, etc.)
- action MUST be BUY or SELL
- entry can be 0 or null (if not specified or is a range like 4800/4796)
- sl must be logical
- tps must be list of numbers
- confidence MUST be 0.0 → 1.0
- IGNORE usernames like @username, INBOX, channel names
- Extract ONLY the trading data (symbol, action, prices)

────────────────────────
EXAMPLES:
────────────────────────
"XAUUSD GOLD BUY 4800/4796 TP 4804 TP 4808 SL 4825"
→ {{"symbol": "XAUUSD", "action": "BUY", "entry": 4798, "sl": 4825, "tps": [4804, 4808], "confidence": 0.9}}

"EURUSD SELL @ 1.0850 TP1: 1.0830 TP2: 1.0810 SL: 1.0870"
→ {{"symbol": "EURUSD", "action": "SELL", "entry": 1.0850, "sl": 1.0870, "tps": [1.0830, 1.0810], "confidence": 0.95}}

────────────────────────
FILTER OUT:
────────────────────────
- ads / promotions
- emoji-only messages
- missing direction (no BUY/SELL)
- no prices at all

────────────────────────
MESSAGE:
{message}
"""

    for attempt in range(retries):
        try:
            response = _client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )

            text = response.text.strip()

            start = text.find("{")
            end = text.rfind("}") + 1

            if start == -1 or end == 0:
                log.warning(f"❌ Signal rejected (attempt {attempt+1}): AI returned no JSON structure")
                raise ValueError("No JSON found")

            data = json.loads(text[start:end])

            if not data:
                log.warning(f"❌ Signal rejected: AI returned EMPTY RESPONSE - Message likely not a valid trading signal")
                # Don't return yet, let it retry
                if attempt < retries - 1:
                    time.sleep(wait)
                    continue
                else:
                    # AI failed, try fallback parser
                    log.warning(f"⚠️ AI Parser failed after {retries} attempts - Switching to FALLBACK PARSER")
                    return fallback_parse_signal(message)

            signal = normalize_signal(data)

            signal["valid"] = validate_signal(signal)

            if not signal["valid"]:
                reason = signal.get("reason", "unknown")
                log.warning(f"❌ Signal rejected: VALIDATION FAILED - {get_rejection_message(reason, signal)}")
                return signal

            log.info(f"✅ Signal accepted (AI Parser): {signal['symbol']} {signal['action']} | Confidence: {signal.get('confidence', 0):.2f}")
            return signal

        except json.JSONDecodeError as e:
            log.warning(f"❌ Signal rejected (attempt {attempt+1}): JSON PARSE ERROR - {str(e)}")
            time.sleep(wait)
        except Exception as e:
            log.warning(f"❌ Signal rejected (attempt {attempt+1}): {str(e)}")
            time.sleep(wait)

    # AI completely failed, use fallback parser
    log.warning(f"⚠️ AI Parser failed after {retries} attempts - Switching to FALLBACK PARSER")
    return fallback_parse_signal(message)


# ─────────────────────────────
# 🔧 FALLBACK PARSER (Regex-based)
# ─────────────────────────────
def fallback_parse_signal(message: str) -> dict:
    """
    Smart regex-based parser as fallback when AI fails
    Handles various message formats
    """
    try:
        log.info(f"🔧 Fallback Parser activated for message: {message[:100]}...")
        
        message_upper = message.upper()
        
        # ── STEP 1: EXTRACT SYMBOL ──
        symbol = extract_symbol(message_upper)
        if not symbol:
            log.warning("❌ Fallback Parser: No valid symbol found")
            return {"valid": False, "reason": "no_symbol_found"}
        
        # ── STEP 2: EXTRACT ACTION (BUY/SELL) ──
        action = extract_action(message_upper)
        if not action:
            log.warning("❌ Fallback Parser: No BUY/SELL action found")
            return {"valid": False, "reason": "no_action_found"}
        
        # ── STEP 3: EXTRACT PRICES ──
        prices = extract_prices(message)
        
        # ── STEP 4: IDENTIFY ENTRY, SL, TPs ──
        entry = extract_entry(message, prices)
        sl = extract_sl(message, prices)
        tps = extract_tps(message, prices)
        
        if not tps:
            log.warning("❌ Fallback Parser: No TP levels found")
            return {"valid": False, "reason": "no_tps_found"}
        
        # Build signal
        signal = {
            "symbol": symbol,
            "action": action,
            "entry": entry,
            "sl": sl,
            "tps": tps,
            "confidence": 0.75  # Fallback parser gets 0.75 confidence
        }
        
        log.info(f"📊 Fallback Parser extracted: {symbol} {action} | Entry: {entry} | SL: {sl} | TPs: {len(tps)}")
        
        # Normalize and validate
        signal = normalize_signal(signal)
        signal["valid"] = validate_signal(signal)
        
        if signal["valid"]:
            log.info(f"✅ Signal accepted (Fallback Parser): {signal['symbol']} {signal['action']}")
        else:
            reason = signal.get("reason", "unknown")
            log.warning(f"❌ Fallback Parser validation failed: {reason}")
        
        return signal
        
    except Exception as e:
        log.error(f"❌ Fallback Parser error: {str(e)}")
        return {"valid": False, "reason": "fallback_parser_error"}


# ─────────────────────────────
# 🔍 SYMBOL EXTRACTION
# ─────────────────────────────
def extract_symbol(text: str) -> str:
    """Extract trading symbol from text"""
    
    # Symbol mappings
    symbol_map = {
        "GOLD": "XAUUSD",
        "XAUUSD": "XAUUSD",
        "XAU": "XAUUSD",
        "EURUSD": "EURUSD",
        "EUR/USD": "EURUSD",
        "GBPUSD": "GBPUSD",
        "GBP/USD": "GBPUSD",
        "USDJPY": "USDJPY",
        "USD/JPY": "USDJPY",
        "BTCUSD": "BTCUSD",
        "BTC": "BTCUSD",
        "ETHUSD": "ETHUSD",
        "ETH": "ETHUSD",
        "OIL": "USOIL",
        "USOIL": "USOIL",
        "WTI": "USOIL",
        "NAS100": "NAS100",
        "NASDAQ": "NAS100",
        "US30": "US30",
        "DOW": "US30"
    }
    
    for key, value in symbol_map.items():
        if key in text:
            return value
    
    # Try to find common forex pairs
    forex_pattern = r'\b([A-Z]{6})\b'
    match = re.search(forex_pattern, text)
    if match:
        return match.group(1)
    
    return None


# ─────────────────────────────
# 🔍 ACTION EXTRACTION
# ─────────────────────────────
def extract_action(text: str) -> str:
    """Extract BUY or SELL action"""
    
    if "BUY" in text:
        return "BUY"
    elif "SELL" in text:
        return "SELL"
    
    return None


# ─────────────────────────────
# 🔍 PRICE EXTRACTION
# ─────────────────────────────
def extract_prices(text: str) -> list:
    """Extract all numeric prices from text"""
    
    # Match numbers with optional decimals (e.g., 4800, 4800.50, 1.0850)
    price_pattern = r'\b\d+\.?\d*\b'
    prices = re.findall(price_pattern, text)
    
    # Convert to float and filter valid prices
    valid_prices = []
    for price in prices:
        try:
            p = float(price)
            if p > 0:
                valid_prices.append(p)
        except:
            continue
    
    return valid_prices


# ─────────────────────────────
# 🔍 ENTRY EXTRACTION
# ─────────────────────────────
def extract_entry(text: str, prices: list) -> float:
    """Extract entry price"""
    
    text_upper = text.upper()
    
    # Look for explicit entry markers
    entry_patterns = [
        r'ENTRY[:\s@]*(\d+\.?\d*)',
        r'ENTER[:\s@]*(\d+\.?\d*)',
        r'@\s*(\d+\.?\d*)',
        r'PRICE[:\s]*(\d+\.?\d*)'
    ]
    
    for pattern in entry_patterns:
        match = re.search(pattern, text_upper)
        if match:
            try:
                return float(match.group(1))
            except:
                continue
    
    # Look for range format like "4800/4796"
    range_pattern = r'(\d+\.?\d*)/(\d+\.?\d*)'
    match = re.search(range_pattern, text)
    if match:
        try:
            price1 = float(match.group(1))
            price2 = float(match.group(2))
            # Return average of range
            return round((price1 + price2) / 2, 2)
        except:
            pass
    
    # If no explicit entry, return None (will use market price)
    return None


# ─────────────────────────────
# 🔍 STOP LOSS EXTRACTION
# ─────────────────────────────
def extract_sl(text: str, prices: list) -> float:
    """Extract stop loss price"""
    
    text_upper = text.upper()
    
    # Look for SL markers
    sl_patterns = [
        r'SL[:\s]*(\d+\.?\d*)',
        r'STOP\s*LOSS[:\s]*(\d+\.?\d*)',
        r'STOPLOSS[:\s]*(\d+\.?\d*)',
        r'STOP[:\s]*(\d+\.?\d*)'
    ]
    
    for pattern in sl_patterns:
        match = re.search(pattern, text_upper)
        if match:
            try:
                return float(match.group(1))
            except:
                continue
    
    return None


# ─────────────────────────────
# 🔍 TAKE PROFIT EXTRACTION
# ─────────────────────────────
def extract_tps(text: str, prices: list) -> list:
    """Extract take profit levels"""
    
    text_upper = text.upper()
    tps = []
    
    # Look for TP markers with numbers
    tp_patterns = [
        r'TP\s*\d*[:\s]*(\d+\.?\d*)',
        r'TAKE\s*PROFIT\s*\d*[:\s]*(\d+\.?\d*)',
        r'TARGET\s*\d*[:\s]*(\d+\.?\d*)',
        r'T\d+[:\s]*(\d+\.?\d*)'
    ]
    
    for pattern in tp_patterns:
        matches = re.finditer(pattern, text_upper)
        for match in matches:
            try:
                tp = float(match.group(1))
                if tp > 0 and tp not in tps:
                    tps.append(tp)
            except:
                continue
    
    # If we found TPs, return them sorted
    if tps:
        return sorted(tps)
    
    # Fallback: try to identify TPs from all prices
    # Exclude entry and SL, remaining are likely TPs
    entry = extract_entry(text, prices)
    sl = extract_sl(text, prices)
    
    for price in prices:
        if price != entry and price != sl and price not in tps:
            tps.append(price)
    
    return sorted(tps) if tps else []


# ─────────────────────────────
# 📝 REJECTION MESSAGE HELPER
# ─────────────────────────────
def get_rejection_message(reason: str, signal: dict) -> str:
    """Generate detailed rejection message"""
    messages = {
        "low_confidence": f"Low confidence score ({signal.get('confidence', 0):.2f} < 0.5)",
        "invalid_sl": f"Invalid Stop Loss (too close to entry: {signal.get('entry')} vs {signal.get('sl')})",
        "no_tps": "No Take Profit levels found",
        "invalid_tp": "Invalid Take Profit values (must be > 0)",
        "normalize_error": "Failed to normalize signal data",
        "validation_error": "Validation error occurred",
        "empty_response": "AI could not extract trading signal from message",
        "noise_detected": "Message contains promotional content"
    }
    
    default_msg = f"Unknown reason: {reason}"
    detailed = messages.get(reason, default_msg)
    
    # Add signal data for debugging
    if signal.get("symbol"):
        detailed += f" | Symbol: {signal.get('symbol')}, Action: {signal.get('action')}"
    
    return detailed


# ─────────────────────────────
# 🔧 NORMALIZATION
# ─────────────────────────────
def normalize_signal(data: dict) -> dict:
    try:
        symbol = str(data.get("symbol", "")).upper()
        action = str(data.get("action", "")).upper()

        entry = data.get("entry")
        sl = data.get("sl")
        confidence = float(data.get("confidence", 0))

        # clean numbers
        entry = float(entry) if entry else None
        sl = float(sl) if sl else None

        # clean TP list
        tps = []
        for tp in data.get("tps", []):
            try:
                val = float(tp)
                if val > 0:
                    tps.append(val)
            except:
                continue

        result = {
            "symbol": symbol,
            "action": action,
            "entry": entry,
            "sl": sl,
            "tps": tps,
            "confidence": confidence
        }
        
        log.info(f"📊 Normalized signal: {symbol} {action} | Entry: {entry} | SL: {sl} | TPs: {len(tps)} | Confidence: {confidence:.2f}")
        
        return result

    except Exception as e:
        log.error(f"❌ Normalization failed: {str(e)}")
        return {"valid": False, "reason": "normalize_error"}


# ─────────────────────────────
# 🛡 VALIDATION ENGINE
# ─────────────────────────────
def validate_signal(signal: dict) -> bool:
    try:
        # Check symbol
        if not signal.get("symbol"):
            signal["reason"] = "missing_symbol"
            return False

        # Check action
        if signal.get("action") not in ["BUY", "SELL"]:
            signal["reason"] = "invalid_action"
            return False

        # confidence filter - LOWERED to 0.5 for better acceptance
        confidence = signal.get("confidence", 0)
        if confidence < 0.5:
            signal["reason"] = "low_confidence"
            return False

        entry = signal.get("entry")
        sl = signal.get("sl")

        # SL sanity check
        if entry and sl:
            if abs(entry - sl) < 0.0001:
                signal["reason"] = "invalid_sl"
                return False

        # must have at least 1 TP
        tps = signal.get("tps", [])
        if not tps:
            signal["reason"] = "no_tps"
            return False

        # validate TP values
        for tp in tps:
            if tp <= 0:
                signal["reason"] = "invalid_tp"
                return False

        return True

    except Exception as e:
        log.error(f"❌ Validation error: {str(e)}")
        signal["reason"] = "validation_error"
        return False


# ─────────────────────────────
# 📊 OPTIONAL: SORT TPS (helper)
# ─────────────────────────────
def sort_tps(action, tps):
    if action == "BUY":
        return sorted(tps)
    return sorted(tps, reverse=True)