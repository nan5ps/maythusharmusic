import sys
import traceback
from functools import wraps
from datetime import datetime

import aiofiles
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden
from maythusharmusic import app
from config import LOGGER_ID
from maythusharmusic.logging import LOGGER
from maythusharmusic.utils.pastebin import HottyBin


def split_limits(text):
    if len(text) < 2048:
        return [text]

    lines = text.splitlines(True)
    small_msg = ""
    result = []
    for line in lines:
        if len(small_msg) + len(line) < 2048:
            small_msg += line
        else:
            result.append(small_msg)
            small_msg = line

    result.append(small_msg)

    return result

async def send_large_error(text: str, caption: str, filename: str):
    try:
        paste_url = await HottyBin(text)
        if paste_url:
            await app.send_message(LOGGER_ID, f"{caption}\n\n🔗 Paste: {paste_url}")
            return
    except Exception:
        pass

    path = f"{filename}.txt"
    async with aiofiles.open(path, "w") as f:
        await f.write(text)
    await app.send_document(LOGGER_ID, path, caption="❌ Error Log (Fallback)")
    os.remove(path)



def capture_err(func):
    @wraps(func)
    async def capture(client, message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except ChatWriteForbidden:
            await app.leave_chat(message.chat.id)
            return
        except Exception as err:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            errors = traceback.format_exception(
                etype=exc_type,
                value=exc_obj,
                tb=exc_tb,
            )
            error_feedback = split_limits(
                "**ERROR** | `{}` | `{}`\n\n```{}```\n\n```{}```\n".format(
                    0 if not message.from_user else message.from_user.id,
                    0 if not message.chat else message.chat.id,
                    message.text or message.caption,
                    "".join(errors),
                ),
            )
            for x in error_feedback:
                await app.send_message(LOGGER, x)
            raise err

    return capture


def capture_callback_err(func):
    """
    Handles errors in callback query handlers.
    Logs only unignored errors.
    """
    @wraps(func)
    async def wrapper(client, callback_query, *args, **kwargs):
        try:
            return await func(client, callback_query, *args, **kwargs)
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            extras = {
                "User": callback_query.from_user.mention if callback_query.from_user else "N/A",
                "Chat ID": callback_query.message.chat.id
            }
            filename = f"cb_error_log_{callback_query.message.chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Callback Error", filename, extras)
            raise err
    return wrapper

def capture_internal_err(func):
    """
    Handles errors in background/internal async bot functions.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            extras = {"Function": func.__name__}
            filename = f"internal_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Internal Error", filename, extras)
            raise err
    return wrapper
