from pyrogram import enums, errors, filters, types

from LuffyxHancock import app, config, db, lang
from LuffyxHancock.helpers import buttons, utils


@app.on_message(filters.command(["help"]) & filters.private & ~app.bl_users)
@lang.language()
async def _help(_, m: types.Message):
    """Handle /help command in private chats - shows help menu with image."""
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass
    
    try:
        await m.reply_photo(
            photo=config.START_IMG,  # Use same image as start command
            caption=m.lang["help_menu"],
            reply_markup=buttons.help_markup(m.lang),
            quote=True,
        )
    except Exception:
        # Fallback to text if photo fails
        await m.reply_text(
            text=m.lang["help_menu"],
            reply_markup=buttons.help_markup(m.lang),
            quote=True,
        )


@app.on_message(filters.command(["start"]))
@lang.language()
async def start(_, message: types.Message):
    """
    Handle /start command - welcome message for users.

    - In private chat: Shows welcome message with inline buttons
    - In group chat: Shows short welcome message
    - Adds new users to database
    - Sends log to logger group for new users
    """
    # Auto-delete command message in group chats
    if message.chat.type != enums.ChatType.PRIVATE:
        try:
            await message.delete()
        except Exception:
            pass
    
    # Skip if message from channel or anonymous admin
    if not message.from_user:
        return

    # Check if user is blacklisted
    if message.from_user.id in app.bl_users and message.from_user.id not in db.notified:
        return await message.reply_text(message.lang["bl_user_notify"])

    # If /start help, show help menu
    if len(message.command) > 1 and message.command[1] == "help":
        return await _help(_, message)

    # Determine if chat is private or group
    private = message.chat.type == enums.ChatType.PRIVATE

    # Premium Emojis Configuration
    PREMIUM_EMOJI_1 = "6120465303177533732" 
    PREMIUM_EMOJI_2 = "6120591326107935086" 
    PREMIUM_EMOJI_3 = "6120398056874582504"
    PREMIUM_EMOJI_4 = "6205967094039709231"
    PREMIUM_EMOJI_5 = "6206217069726271155"
    PREMIUM_EMOJI_6 = "6204129896009042249"
    PREMIUM_EMOJI_7 = "6206275004540126842"
    PREMIUM_EMOJI_8 = "6205967094039709231"
    PREMIUM_EMOJI_9 = "6206217069726271155"
    PREMIUM_EMOJI_10 = "6204129896009042249"
    PREMIUM_EMOJI_11 = "6206275004540126842"

    # Choose appropriate welcome message
    if private:
        # Telegram HTML Format အတွက် <tg-emoji emoji-id="..."> ကို အသုံးပြုထားပါသည်။
        _text = f"""
<tg-emoji emoji-id="{PREMIUM_EMOJI_4}">☉</tg-emoji> ʜᴇʏ ʙᴀʙʏ : <a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a> <tg-emoji emoji-id="{PREMIUM_EMOJI_1}">☉</tg-emoji>
<tg-emoji emoji-id="{PREMIUM_EMOJI_5}">☉</tg-emoji> ɪ ᴀᴍ {app.mention}, ʜᴇʀᴇ ᴛᴏ ᴘʀᴏᴠɪᴅᴇ ʏᴏᴜ ᴡɪᴛʜ ᴀ ꜱᴍᴏᴏᴛʜ ᴍᴜꜱɪᴄ ꜱᴛʀᴇᴀᴍɪɴɢ ᴇxᴘᴇʀɪᴇɴᴄᴇ <tg-emoji emoji-id="{PREMIUM_EMOJI_2}">☉</tg-emoji>.

<tg-emoji emoji-id="{PREMIUM_EMOJI_6}">☉</tg-emoji> ғᴇᴀᴛᴜʀᴇs
<tg-emoji emoji-id="{PREMIUM_EMOJI_7}">☉</tg-emoji> ʜǫ ᴀᴜᴅɪᴏ : 320ᴋʙᴘs sᴛʀᴇᴀᴍɪɴɢ
<tg-emoji emoji-id="{PREMIUM_EMOJI_8}">☉</tg-emoji> sᴛʀᴇᴀᴍ sᴜᴘᴘᴏʀᴛ : ᴀᴜᴅɪᴏ-ᴠɪᴅᴇᴏ
<tg-emoji emoji-id="{PREMIUM_EMOJI_9}">☉</tg-emoji> 24-7 ᴜᴘᴛɪᴍᴇ : ᴇɴᴛᴇʀᴘʀɪsᴇ ʀᴇʟɪᴀʙɪʟɪᴛʏ
<tg-emoji emoji-id="{PREMIUM_EMOJI_10}">☉</tg-emoji> ᴘʟᴀʏ ᴄᴏᴍᴍᴇɴᴛꜱ : ᴘʟᴀʏ, ᴠᴘʟᴀʏ 
<tg-emoji emoji-id="{PREMIUM_EMOJI_11}">☉</tg-emoji> ʙᴀsᴇᴅ ᴏɴ : ʏᴏᴜᴛᴜʙᴇ ᴀᴘɪ"""
    else:
        _text = message.lang["start_gp"].format(app.name)

    key = buttons.start_key(message.lang, private)
    
    try:
        await message.reply_photo(
            photo=config.START_IMG,
            caption=_text,
            reply_markup=key,
            quote=not private,
            parse_mode=enums.ParseMode.HTML  # HTML format အသုံးပြုရန်
        )
    except errors.ChatSendPhotosForbidden:
        # If photos are not allowed, send text only
        await message.reply_text(
            text=_text,
            reply_markup=key,
            quote=not private,
            parse_mode=enums.ParseMode.HTML  # HTML format အသုံးပြုရန်
        )
    except Exception as e:
        # အခြား Error များတက်ခဲ့လျှင် Bot မှ Message ပြန်ပို့ပေးရန်
        await message.reply_text(
            text=f"⚠️ **Error Occurred:** `{e}`\n\n(သင်၏ `START_IMG` Link သို့မဟုတ် Premium Emoji Format မှားယွင်းနေနိုင်ပါသည်။)",
            quote=True
        )
        print(f"Start Command Error: {e}")

    # For private chats, add user to database if new
    if private:
        if await db.is_user(message.from_user.id):
            return  # User already exists, no need to add
        # Log new user to logger group
        await utils.send_log(message)
        # Add user to database
        return await db.add_user(message.from_user.id)


@app.on_message(filters.command(["playmode", "settings"]) & filters.group & ~app.bl_users)
@lang.language()
async def settings(_, message: types.Message):
    """
    Handle /playmode or /settings command - show group settings.

    Displays:
    - Play mode (everyone or admin only)
    - Current language
    - Options to change settings
    """
    # Auto-delete command message
    try:
        await message.delete()
    except Exception:
        pass
    
    admin_only = await db.get_play_mode(message.chat.id)  # Get play mode setting
    _language = "en"
    await utils.safe_text(
        message,
        message.lang["start_settings"].format(message.chat.title),
        reply_markup=buttons.settings_markup(
            message.lang, admin_only, _language, message.chat.id
        ),
        quote=True,
    )


@app.on_message(filters.new_chat_members, group=7)
@lang.language()
async def _new_member(_, message: types.Message):
    """
    Handle new member events - detect when bot is added to groups.

    - Leaves non-supergroup chats
    - Adds new groups to database
    """
    # Only work in supergroups (not basic groups)
    if message.chat.type != enums.ChatType.SUPERGROUP:
        return await message.chat.leave()

    # Check each new member
    for member in message.new_chat_members:
        if member.id == app.id:  # Bot itself was added
            if await db.is_chat(message.chat.id):
                return  # Chat already in database
            # Add chat to database (log is sent from new_chat.py with photo)
            await db.add_chat(message.chat.id)
