# Global
gl_next = "▶️ Next"
gl_back = "◀️ Back"
gl_yes = "✅ Yes"
gl_yep = "✅ yep"
gl_no = "❌ No"
gl_cancel = "❌ Cancel"
gl_on = "🟢 Enabled"
gl_off = "🔴 Disabled"
gl_error = "⚠️ Error"
gl_try_again = "Try again"
gl_error_try_again = f"{gl_error}. {gl_try_again}."
gl_refresh = "🔄 Refresh"
gl_delete = "🗑️ Delete"
gl_edit = "✏️ Edit"
gl_configure = "⚙️ Configure"
gl_pcs = "pcs."
gl_last_update = "Last update"

# Main menu
mm_language = "🗣️ Language"
mm_global = "⚙️ Global switches"
mm_notifications = "🔔 Notification settings"
mm_autoresponse = "🤖 Autoresponse settings"
mm_blacklist = "🚫 Blacklist settings"
mm_templates = "📝 Answer templates"
mm_greetings = "👋 Greeting message"
mm_order_confirm = "✅ Order confirmation response"
mm_review_reply = "⭐ Response to reviews"
mm_new_msg_view = "✉️ Appearance of new msg. notification"
mm_plugins = "🧩 Plugins"
mm_configs = "📁 Configs"
mm_authorized_users = "👥 Authorized Users"
mm_proxy = "🌐 Proxy"

# Global switches
gs_autoresponse = "{} Autoresponse"
gs_old_msg_mode = "{} Old Message Receiving Mode"
gs_keep_sent_messages_unread = "{} Keep unread when sending"

# Notification settings
ns_new_msg = "{} New message"
ns_cmd = "{} Command received"
ns_new_order = "{} New order"
ns_order_confirmed = "{} Order confirmed"
ns_raise = "{} Lots raised"
ns_new_review = "{} New review"
ns_bot_start = "{} Bot start"
ns_other = "{} Other (plugins)"

# Autoresponse settings
ar_edit_commands = "✏️ Edit existing commands"
ar_add_command = "➕ Add command / set of commands"
ar_to_ar = "🤖 Back to autoresponse settings"
ar_to_mm = "📋 Back to main menu"
ar_edit_response = "✏️ Edit response"
ar_edit_notification = "✏️ Edit notification text"
ar_notification = "{}  notification"
ar_add_more = "➕ Add more"
ar_add_another = "➕ Add another"



fl_manual = "➕ Enter manually"


# Blacklist settings
bl_autoresponse = "{} Don't respond to commands"
bl_new_msg_notifications = "{} Don't notify about new messages"
bl_new_order_notifications = "{} Don't notify about new orders"
bl_command_notifications = "{} Don't notify about commands received"

# Answer templates
tmplt_add = "➕ Add template"
tmplt_add_more = "➕ Add more"
tmplt_add_another = "➕ Add another"

# Greeting settings
gr_greetings = "{} Greet users"
gr_ignore_sys_msgs = "{} Ignore system messages"
gr_only_new_chats = "{} Only in new chats"
gr_edit_message = "✏️ Change the text of the welcome message"
gr_edit_cooldown = "⏱️ Cooldown: {} days"

# Order confirmation response settings
oc_watermark = "{} Message watermark"
oc_send_reply = "{} Send message"
oc_edit_message = "✏️ Change the text of the message"

# Appearance of new msg. notification
mv_incl_my_msg = "{} Show my messages"
mv_incl_fp_msg = "{} Show FunPay messages"
mv_incl_bot_msg = "{} Show bot messages"
mv_only_my_msg = "{} Notify, if only my messages"
mv_only_fp_msg = "{} Notify, if only FunPay messages"
mv_only_bot_msg = "{} Notify, if only bot messages"
mv_show_image_name = "{} Show image names"

# Plugins
pl_add = "➕ Add plugin"
pl_activate = "Activate"
pl_deactivate = "Deactivate"
pl_commands = "⌨️ Commands"
pl_settings = "⚙️ Settings"

# Configs
cfg_download_main = "⤵️ Download main config"
cfg_download_ar = "⤵️ Download autoresponse config"
cfg_upload_main = "⤴️ Upload main config"
cfg_upload_ar = "⤴️ Upload autoresponse config"

# Authorized users
tg_block_login = "{} Block logins by password"

# Proxy
prx_proxy_add = "➕ Add proxy"

# Links
lnk_github = "🛠️ Create your FunPay bot"
lnk_updates = "🔄 Updates"
lnk_chat = "💬 Chat"

# Announcements
an_an = "{} Announcements"
an_ad = "{} Advertisement"

# New order
ord_refund = "💸 Make a refund"
ord_open = "🌐 Open order page"
ord_answer = "📨 Answer"
ord_templates = "📝 Templates"

# New message
msg_reply = "📨 Reply"
msg_reply2 = "📨 Reply"
msg_templates = "📝 Templates"
msg_more = "➕ More"

# Messages texts
access_denied = "👋 Hi, <b><i>{}</i></b>!\n\n❌ You are an unauthorized user.\n\n" \
                "🔑 Send me the <u><b>secret key</b></u> you entered during the initial setup to " \
                "gain access to the control panel."

access_granted = "🔓 Access granted!\n\n" \
                 "🔕 Keep in mind that I <b><u>don't send any notifications to this chat</u></b>.\n\n" \
                 "🔔 You can set up notifications for <b><u>this chat</u></b> in the settings menu.\n\n" \
                 "⚙️ To open the <i>FunPay Cardinal</i> settings menu, send me /menu."

access_granted_notification = "<b>🚨 ATTENTION! 🚨\n\n\n</b>" * 3 + "\n\n\n🔐 \"<a href=\"\"> {0} </a>\" <b>(ID: {1}) has just accessed the  Control Panel! 🔓</b>"

param_disabled = "❌ This parameter is disabled globally and cannot be changed for this lot.\n\n" \
                 "❔ Switching global parameters is available in the global switch menu " \
                 "(/menu -> ⚙️ Global switches)."

old_mode_help = """<b>New Message Receiving Mode</b>
✅ <i>FPC</i> gets the full chat history and sees all data about all new messages.
✅ <i>FPC</i> can see images in chat and forward them to <i></i> chat.
✅ <i>FPC</i> can determine exactly who wrote, whether it was you, your interlocutor, or a 3rd party (arbitrator).
❌ Because <i>FPC</i> gets the full chat history to detect new messages, the chat becomes "read" (not lit orange).

<b>Old Message Receiving Mode</b>
✅ Chats that you have not personally read remain unread (lit orange).
✅ Works a little bit faster than the new mode.
❌ <i>FPC</i> doesn't get the full chat history, so it sees only the last message. If the user quickly writes several messages, <i>FPC</i> will see only the last one.
❌ <i>FPC</i> cannot see images in chat and forward them to <i></i> chat.
❌ <i>FPC</i> cannot determine exactly who wrote: you or the person you are chatting with. If the chat is not read, then the message is from the interlocutor, otherwise it is from you. However, if you are viewing the chat when you receive messages, this logic can sometimes fail. Also, <i>FPC</i> will not be able to determine if a 3rd party (arbitrator) wrote into the chat.

❗ If you click the <code>More</code> button in a new message notification, <i>FPC</i> will "read" the chat and show the last 15 messages, including images. <i>FPC</i> will also be able to determine who the author of the messages is."""

bot_started = """✅  bot is running!\n
✅ You can <b><u>customize configurations</u></b> and <b><u>make full use of the <i></i> bot's functionality.</u></b>.\n
❌ <i>FunPay Cardinal</i> is not initialized yet and none of its functions work.\n
🔃 As soon as <i>FunPay Cardinal</i> is initialized, this message will change.\n
📋 If <i>FPC</i> does not initialize for a long time, check the logs with /logs"""

fpc_init = """✅ <b><u>FunPay Cardinal initialized!</u></b>\n
ℹ️ <b><i>Version:</i></b> <code>{}</code>
👑 <b><i>Account:</i></b>  <code>{}</code> | <code>{}</code>
💰 <b><i>Balance:</i></b> <code>{}₽, {}$, {}€</code>
📊 <b><i>Active orders:</i></b>  <code>{}</code>

💬 <b><i> chat:</i></b> @funpay_cardinal
🔄 <b><i>Updates:</i></b> @fpc_updates
🧩 <b><i>Plugins:</i></b> @fpc_plugins
👨‍💻 <b><i>Developer:</i></b> @woopertail, @sidor0912
🤑 <b><i>Donate:</i></b> @sidor_donate"""



about = """<b>🐦 FunPay Cardinal 🐦 v{}</b>\n
<i> chat:</i> @funpay_cardinal
<i>Updates:</i> @fpc_updates
<i>Plugins:</i> @fpc_plugins
<i>Developer:</i> @woopertail, @sidor0912
<i>Donate:</i> @sidor_donate"""

sys_info = """<b><u>Data summary</u></b>

<b>CPU:</b>
{}
    Used by <i>FPC</i>: <code>{}%</code>

<b>RAM:</b>
    Total:  <code>{} MB</code>
    Used:  <code>{} MB</code>
    Free:  <code>{} MB</code>
    Used by <i>FPC</i>:  <code>{} MB</code>

<b>Other:</b>
    Uptime:  <code>{}</code>
    Chat ID:  <code>{}</code>"""

act_blacklist = """Enter the username you want to add to the blacklist."""
already_blacklisted = "❌ <code>{}</code> is already on the blacklist."
user_blacklisted = "✅ <code>{}</code> is blacklisted."
act_unban = "Enter the username you want to remove from the blacklist."
not_blacklisted = "❌ <code>{}</code> is not blacklisted."
user_unbanned = "✅ <code>{}</code> is no longer blacklisted."
blacklist_empty = "❌ Blacklist is empty."

act_proxy = "Enter the proxy in the format <u>login:password@ip:port</u> or <u>ip:port</u>."
proxy_already_exists = "❌ The proxy <code>{}</code> already exists."
proxy_added = "✅ Proxy <u>{}</u> added successfully."
proxy_format = "❌ Proxies must be in the format <u>login:password@ip:port</u> or <u>ip:port</u>."
proxy_adding_error = "❌ There was an error while adding the proxy."
proxy_undeletable = "❌ This proxy cannot be deleted as it is currently in use."

act_edit_watermark = "Enter a new watermark text. For example:\n{}\n" \
                     "<code>𝓕𝓾𝓷𝓟𝓪𝔂 𝓒𝓪𝓻𝓭𝓲𝓷𝓪𝓵</code>\n" \
                     "<code>𝔽𝕦𝕟ℙ𝕒𝕪 ℂ𝕒𝕣𝕕𝕚𝕟𝕒𝕝</code>\n<code>ＦｕｎＰａｙ Ｃａｒｄｉｎａｌ</code>\n" \
                     "<code>ꜰᴜɴᴘᴀʏ ᴄᴀʀᴅɪɴᴀʟ</code>\n<code>🄵🅄🄽🄿🄰🅈 🄲🄰🅁🄳🄸🄽🄰🄻</code>\n" \
                     "<code>ⒻⓤⓝⓅⓐⓨ Ⓒⓐⓡⓓⓘⓝⓐⓛ</code>\n<code>𝐅𝐮𝐧𝐏𝐚𝐲 𝐂𝐚𝐫𝐝𝐢𝐧𝐚𝐥</code>\n" \
                     "<code>𝗙𝘂𝗻𝗣𝗮𝘆 𝗖𝗮𝗿𝗱𝗶𝗻𝗮𝗹</code>\n<code>𝘍𝘶𝘯𝘗𝘢𝘺 𝘊𝘢𝘳𝘥𝘪𝘯𝘢𝘭</code>\n" \
                     "<code>𝙁𝙪𝙣𝙋𝙖𝙮 𝘾𝙖𝙧𝙙𝙞𝙣𝙖𝙡</code>\n<code>𝙵𝚞𝚗𝙿𝚊𝚢 𝙲𝚊𝚛𝚍𝚒𝚗𝚊𝚕</code>\n" \
                     "<code>ᖴᑌᑎᑭᗩY ᑕᗩᖇᗪIᑎᗩᒪ</code>\n" \
                     "<code>FunPay Cardinal</code>\n<code>[FunPay / Cardinal]</code>\n" \
                     "<code>🤖</code>\n<code>🐦</code>\n\n" \
                     "You can tap on the examples to copy and edit them to your liking.\nNote that on FunPay, the emoji " \
                     "🐦 looks different than in ." \
                     "\n\nTo remove the watermark, send <code>-</code>."
watermark_changed = "✅ The message watermark has been changed."
watermark_deleted = "✅ The message watermark has been deleted."
watermark_error = "❌ Invalid watermark."

logfile_not_found = "❌ Log file not found."
logfile_sending = "Sending log file (it may take some time)..."
logfile_error = "❌ Failed to send log file."
logfile_deleted = "🗑️ Deleted {} logfile(s)."

update_no_tags = "❌ Failed to get the version list. Try again later."
update_lasted = "✅ You have the latest version FunPayCardinal {}"
update_get_error = "❌ Failed to get new version information. Try again later."
update_available = "<b><u>New version available!</u></b>\n\n\n{}\n\n{}"
update_update = "To update, enter the command /update"
update_backup = "✅ Backup of configs, storage and plugins <code>backup.zip</code>.\n\n" \
                "⚠️ DO NOT SEND this archive to ANYONE. It contains ABSOLUTELY ALL content and settings of the bot (including golden_key and product files)."
update_backup_error = "❌ Failed to back up configs, storage and plugins."
update_backup_not_found = "❌ Backup not found."
update_downloaded = "✅ The update {} is downloaded (skipped {} items). Installing..."
update_download_error = "❌ An error occurred while downloading the update."
update_done = "✅ The update is installed! Restart the FPC with the /restart command."
update_done_exe = "✅ The update is installed! New <code>FPC.exe</code> is in <code>update</code> folder. " \
                  "Turn off <i>FPC</i>, replace old <code>FPC.exe</code> with new one and run <code>Start.bat</code>. "
update_install_error = "❌ An error occurred while installing the update."

send_backup = "Send me the backup.\n\n<b>⚠️ WARNING! Uploading backups from untrusted sources may lead to serious consequences.</b>"

restarting = "Restarting..."
power_off_0 = """<b><u>Are you sure you want to turn me off?</u></b>\n
You <b><u>wont be able</u></b> to turn me on via <i></i>!"""
power_off_1 = "I'll ask again, just in case.\n\n<b><u>Are you sure about this?</u></b>"
power_off_2 = """Just for the record:
you have to go to the server or go to your computer (or wherever you have me) and run me manually!"""
power_off_3 = "Not that I'm imposing, but if you want to apply changes to the main config, " \
              "you can just restart me with the /restart command."
power_off_4 = "Do you even read my messages? Let's put you to the test: yes = no, no = yes." \
              "I'm sure you don't even read my messages, but I write important info here."
power_off_5 = "Hell yeah?.."
power_off_6 = "Okay, okay, I'm off..."
power_off_cancelled = "The shutdown has been cancelled."
power_off_error = "❌ This button does not belong to this session.\nCall this menu again."

enter_msg_text = "Enter message text."
msg_sent = "✅ Message sent to <a href=\"https://funpay.com/chat/?node={}\">{}</a> chat."
msg_sent_short = "✅ Message sent."
msg_sending_error = "❌ Failed to send a message to <a href=\"https://funpay.com/chat/?node={}\">{}</a> chat."
msg_sending_error_short = "❌ Failed to send a message to chat."
send_img = "Send me an image."

greeting_changed = "✅ The greeting text has been changed."
greeting_cooldown_changed = "✅ Greeting message cooldown changed: {} days."
order_confirm_changed = "✅ The text of the order confirmation reply has been changed!"
review_reply_changed = "✅ The text of {} review reply has been changed!"
review_reply_empty = "❌ {} review reply text not set."
review_reply_text = "{} review reply text:\n<code>{}</code>"

get_chat_error = "❌ Failed to get chat data."
viewing = "Viewing"
you = "You"
support = "support"
photo = "Photo"

refund_attempt = "❌ Failed to refund order <code>#{}</code>.\n<code>{}</code> attempts left."
refund_error = "❌ Failed to refund order <code>#{}</code>."
refund_complete = "✅ The #{} order has been refunded."

updating_profile = "Updating account statistics (this may take some time)..."
profile_updating_error = "❌ Failed to update account statistics."

act_change_golden_key = "Enter golden_key"
cookie_changed = "✅ golden_key successfully changed{}.\n"
cookie_changed2 = "Restart the bot with the /restart command."
cookie_incorrect_format = "❌ Incorrect format of golden_key. Please try again."
cookie_error = "❌ Authorization failed. The golden_key might be incorrect?"

copy_lot_name = "Send the name of the lot exactly as on FunPay."


ar_cmd_not_found_err = "❌ Command with index <code>{}</code> not found."
ar_subcmd_duplicate_err = "❌ The command <code>{}</code> is duplicated in the command net."
ar_cmd_already_exists_err = "❌ The command <code>{}</code> already exists."
ar_enter_new_cmd = "Enter a new command (or several commands via <code>|</code>)."
ar_cmd_added = "Added a new command <code>{}</code>."
ar_response_text = "Response text"
ar_notification_text = "Notification text"
ar_response_text_changed = "✅ The response text of the command <code>{}</code> has been changed to <code>{}</code>."
ar_notification_text_changed = "✅ The notification text of the command <code>{}</code> has been changed to <code>{}</code>"

cfg_main = "Main config.\n\n⚠️ DO NOT SEND this file to ANYONE."
cfg_ar = "Autoresponse config."
cfg_not_found_err = "❌ Config {} not found."
cfg_empty_err = "❌ Config {} is empty."

tmplt_not_found_err = "❌ Answer template with index <code>{}</code> not found."
tmplt_already_exists_err = "❌ Such a template already exists."
tmplt_added = "✅ Template added."
tmplt_msg_sent = "✅ Message sent to <a href=\"https://funpay.com/chat/?node={}\">{}</a> chat.\n\n<code>{}</code>"

pl_not_found_err = "❌ Plugin with UUID <code>{}</code> not found."
pl_file_not_found_err = "❌  File <code>{}</code> not found.\nRestart <i>FPC</i> with command /restart."
pl_commands_list = "<b><i>{}</i></b> plugin commands list."
pl_author = "Dev"
pl_new = "Send me a plugin.\n\n<b>⚠️ ATTENTION! Downloading plugins from questionable sources may lead to unfortunate consequences.\n" \
         "@fpc_plugins solves most potential issues.</b>"

au_user_settings = "Settings for user {}"
adv_fpc = "😎 FunPay Cardinal - the best bot for FunPay"
adv_description = """🐦 FunPay Cardinal v{}🐦

🚀 Auto-raise of lots
💬 Auto-reply to prepared commands
🔝 Permanent online presence
📲 Notifications in 
🕹️ Full control panel in 
🧩 Plugins
🌟 And much more...

🛠️ Create your own bot: github.com/sidor0912/FunPayCardinal
🔄 Updates: @fpc_updates
🧩 Plugins: @fpc_plugins
💬 Chat: @funpay_cardinal"""

# - Menus desc
desc_main = "Select a settings category."
desc_lang = desc_main
desc_gs = "Here you can turn the basic <i>FPC</i> functions on and off."
desc_ns = """Here you can configure notifications.\n
<b><u>Settings are separate for each <i></i> chat!</u></b>\n
Current chat ID: <code>{}</code>"""
desc_bl = "Here you can set restrictions for blacklisted users."
desc_ar = "Here you can add commands or edit existing ones."
desc_ar_list = "Chose a command / commands set you are interested in."


desc_mv = "Here you can configure the appearance of new message notifications."
desc_gr = "Here you can configure the welcome message for new users.\n\n<b>Greeting text:</b>\n<code>{}</code>"
desc_oc = "Here you can configure an order confirmation message.\n\n<b>Message text:</b>\n<code>{}</code>"
desc_or = "Here you can configure your response to feedback."
desc_an = "Here you can configure notifications about announcements."
desc_cfg = "Hare you can download and upload configs."
desc_tmplt = "Here you can add and delete answer templates."
desc_pl = "Here you can get information about the plugins, as well as configure them.\n\n" \
          "⚠️ <b><u>After activating / deactivating / adding / removing a plugin, you must restart the bot!</u></b>" \
          " (/restart)"
desc_au = "Here you can configure authorization in the  control panel."
desc_proxy = "Here you can set up the proxy."

# - Commands desc
cmd_menu = "open settings"
cmd_language = "change language"
cmd_profile = "account statistics"
cmd_golden_key = "change golden_key"
cmd_upload_chat_img = "(chat) upload an image to FunPay"
cmd_upload_offer_img = "(lot) upload an image to FunPay"
cmd_upload_plugin = "upload a plugin"
cmd_ban = "add user to the blacklist"
cmd_unban = "delete user from blacklist"
cmd_black_list = "blacklist"
cmd_watermark = "change message watermark"
cmd_logs = "download current log-file"
cmd_del_logs = "delete old log-files"
cmd_about = "about current version"
cmd_check_updates = "check for updates"
cmd_update = "upgrade to the next version"
cmd_sys = "system load information"
cmd_create_backup = "create backup"
cmd_get_backup = "get backup"
cmd_upload_backup = "upload backup"
cmd_restart = "restart FPC"
cmd_power_off = "shutdown FPC"

# - Variables desc
v_edit_greeting_text = "Enter the text of the welcome message."
v_edit_greeting_cooldown = "Enter the greeting message cooldown (in days)."
v_edit_order_confirm_text = "Enter the text of the order confirmation response."
v_edit_review_reply_text = "Enter the {} review response text."
v_edit_response_text = "Enter a new response text."
v_edit_notification_text = "Enter a new  notification text."
V_new_template = "Enter a text of the new answer template."
v_list = "Variables list"
v_date = "<code>$date</code> - current date in <i>DD.MM.YYYY</i> format."
v_date_text = "<code>$date_text</code> - current date in <i>January 1</i> format."
v_full_date_text = "<code>$full_date_text</code> - current date in <i>January 1, 2020</i> format."
v_time = "<code>$time</code> - current time in <i>HH:MM</i> format."
v_full_time = "<code>$full_time</code> - current time in <i>HH:MM:SS</i> format."
v_photo = "<code>$photo=[PHOTO ID]</code> - photo. Instead of <code>[PHOTO ID]</code>, " \
          "type the photo ID obtained with the /upload_chat_img command."
v_sleep = "<code>$sleep=[TIME]</code> - delay. Replace <code>[TIME]</code> " \
          "with the delay time in seconds."
v_order_id = "<code>$order_id</code> - order ID (without #)"
v_order_link = "<code>$order_link</code> - link to the order"
v_order_title = "<code>$order_title</code> - order title."
v_order_params = "<code>$order_params</code> - order parameters."
v_order_desc_and_params = "<code>$order_desc_and_params</code> - order name and/or parameters."
v_order_desc_or_params = "<code>$order_desc_or_params</code> - order name or parameters."
v_game = "<code>$game</code> - name of the game."
v_category = "<code>$category</code> - name of the subcategory."
v_category_fullname = "<code>$category_fullname</code> - full name of the subcategory (name of the subcategory + name of the game)."
v_chat_id = "<code>$chat_id</code> - chat ID."
v_chat_name = "<code>$chat_name</code> - chat name."
v_message_text = "<code>$message_text</code> - interlocutors message text."
v_username = "<code>$username</code> - interlocutors username."

# Exception texts
exc_param_not_found = "The option \"{}\" not found."
exc_param_cant_be_empty = "The value of the option \"{}\" cannot be empty."
exc_param_value_invalid = "Invalid value of the option \"{}\". Possible values: {}. Current value: \"{}\"."
exc_no_section = "Section does not exists."
exc_section_duplicate = "Section duplicate found."
exc_cmd_duplicate = "The command or the subcommand \"{}\" already exists."
exc_cfg_parse_err = "Error in {} config, in the [{}] section: {}"
exc_plugin_field_not_found = "Failed to load the plugin \"{}\": required field \"{}\" does not exists."

# Logs
log_tg_initialized = "$MAGENTA bot initialized."
log_tg_started = "$CYAN bot $YELLOW@{}$CYAN started."
log_tg_handler_error = "An error occurred while executing the  bot handler."
log_tg_update_error = "An error ({}) occurred while getting  updates (probably an invalid token?)."
log_tg_notification_error = "An error occurred while sending a notification to chat $YELLOW{}$RESET."
log_access_attempt = "$MAGENTA@{} (ID: {})$RESET tried to access the control panel. I'm holding him back as best I can!"
log_click_attempt = "$MAGENTA@{} (ID: {})$RESET presses the control panel buttons in $MAGENTA@{} (ID: {})$RESET. He won't make it!"
log_access_granted = "$MAGENTA@{} (ID: {})$RESET gained access to the control panel."
log_user_blacklisted = "$MAGENTA@{} (ID: {})$RESET has blacklisted $YELLOW{}$RESET."
log_user_unbanned = "$MAGENTA@{} (ID: {})$RESET has removed $YELLOW{}$RESET from the blacklist."
log_watermark_changed = "$MAGENTA@{} (ID: {})$RESET changed the message watermark to $YELLOW{}$RESET."
log_watermark_deleted = "$MAGENTA@{} (ID: {})$RESET deleted the message watermark."
log_greeting_changed = "$MAGENTA@{} (ID: {})$RESET changed the greeting text to $YELLOW{}$RESET."
log_greeting_cooldown_changed = "$MAGENTA@{} (ID: {})$RESET changed the cooldown of the welcome message to $YELLOW{}$RESET days."
log_order_confirm_changed = "$MAGENTA@{} (ID: {})$RESET changed the text of order confirmation reply to $YELLOW{}$RESET."
log_review_reply_changed = "$MAGENTA@{} (ID: {})$RESET changed the text of {}-star(s) review reply to $YELLOW{}$RESET."
log_param_changed = "$MAGENTA@{} (ID: {})$RESET changed value of $CYAN{}$RESET in $YELLOW[{}]$RESET section to $YELLOW{}$RESET."
log_notification_switched = "$MAGENTA@{} (ID: {})$RESET switched notifications $YELLOW{}$RESET for chat $YELLOW{}$RESET to $CYAN{}$RESET."
log_ar_added = "$MAGENTA@{} (ID: {})$RESET added new command $YELLOW{}$RESET."
log_ar_response_text_changed = "$MAGENTA@{} (ID: {})$RESET response text of command $YELLOW{}$RESET to $YELLOW\"{}\"$RESET."
log_ar_notification_text_changed = "$MAGENTA@{} (ID: {})$RESET notification text of command $YELLOW{}$RESET to $YELLOW\"{}\"$RESET."
log_ar_cmd_deleted = "$MAGENTA@{} (ID: {})$RESET deleted the command $YELLOW{}$RESET."
log_cfg_downloaded = "$MAGENTA@{} (ID: {})$RESET requested config $YELLOW{}$RESET."
log_tmplt_added = "$MAGENTA@{} (ID: {})$RESET added the answer template $YELLOW\"{}\"$RESET."
log_tmplt_deleted = "$MAGENTA@{} (ID: {})$RESET deleted the answer template $YELLOW\"{}\"$RESET."
log_pl_activated = "$MAGENTA@{} (ID: {})$RESET activated the plugin $YELLOW\"{}\"$RESET."
log_pl_deactivated = "$MAGENTA@{} (ID: {})$RESET deactivated the plugin $YELLOW\"{}\"$RESET."
log_pl_deleted = "$MAGENTA@{} (ID: {})$RESET deleted the plugin $YELLOW\"{}\"$RESET."
log_pl_delete_handler_err = "An error occurred when executing the $YELLOW\"{}\"$RESET plugin removal handler."

# handlers.py logs
log_new_msg = "$MAGENTA┌──$RESET New message in chat with $YELLOW{} (CID: {}):"
log_sending_greetings = "User $YELLOW{} (CID: {})$RESET wrote for the first time! Sending greetings..."
log_new_cmd = "Received the command $YELLOW{}$RESET in the chat with the user $YELLOW{} (CID: {})$RESET."
ntfc_new_order = "💰 <b>New order:</b> <code>{}</code>\n\n<b><i>🙍‍♂️ Buyer:</i></b>  <code>{}</code>\n" \
                 "<b><i>💵 Order amount:</i></b>  <code>{}</code>\n<b><i>📇 ID:</i></b> <code>#{}</code>\n\n<i>{}</i>"
ntfc_new_review = "🔮 You received {} for the order <code>{}</code>!\n\n💬<b>Review:</b>\n<code>{}</code>{}"
ntfc_review_reply_text = "\n\n🗨️<b>Reply:</b> \n<code>{}</code>"

# cardinal.py logs
crd_proxy_detected = "Proxy detected."
crd_checking_proxy = "Running proxy checks..."
crd_proxy_err = "Failed to connect to the proxy. Make sure that the data is entered correctly."
crd_proxy_success = "Proxy verified successfully! IP address: $YELLOW{}$RESET."
crd_acc_get_timeout_err = "Failed to load account data: Timeout exceeded."
crd_acc_get_unexpected_err = "An unexpected error occurred while retrieving account information."
crd_try_again_in_n_secs = "The next attempt is in {} seconds(-s)..."
crd_getting_profile_data = "Getting lots and categories data..."
crd_profile_get_timeout_err = "Failed to load account lots data: timeout exceeded."
crd_profile_get_unexpected_err = "An unexpected error occurred while retrieving data about the account's lots."
crd_profile_get_too_many_attempts_err = "An error occurred while getting data about the lots of the account: the number of attempts ({}) was exceeded."
crd_profile_updated = "Updated the information about profile lots $YELLOW({})$RESET and categories $YELLOW({})$RESET."
crd_tg_profile_updated = "Updated the information about profile lots $YELLOW({})$RESET and categories $YELLOW({})$RESET ( Control Panel)."
crd_raise_time_err = "The $CYAN\"{}\"$RESET category lots could not be raised. FunPay says: \"{}\". Next attempt in {}."
crd_raise_unexpected_err = "An unexpected error occurred while trying to raise $CYAN\"{}\"$RESET catgory lots. Pause for 10 seconds."
crd_raise_status_code_err = "Error {} when raising lots of the $CYAN\"{}\"$RESET category. Pause for 1 minute..."
crd_lots_raised = "All lots in the $CYAN\"{}\"$RESET category are raised!"
crd_raise_wait_3600 = "Next attempt in {}."
crd_msg_send_err = "An error occurred when sending a message to chat $YELLOW{}$RESET."
crd_msg_attempts_left = "Attempts left: $YELLOW{}$RESET."
crd_msg_no_more_attempts_err = "Failed to send a message to chat $YELLOW{}$RESET: the number of attempts exceeded."
crd_msg_sent = "Sent a message to the chat $YELLOW{}."
crd_session_timeout_err = "Failed to refresh session: timeout exceeded."
crd_session_unexpected_err = "An unexpected error occurred while refreshing the session."
crd_session_no_more_attempts_err = "Failed to refresh session: the number of attempts was exceeded."
crd_session_updated = "Session updated."
crd_session_loop_started = "$CYANThe session refresh loop is running."
crd_no_plugins_folder = "The plugins folder is not detected."
crd_no_plugins = "No plugins detected."
crd_plugin_load_err = "Failed to load plugin {}."
crd_invalid_uuid = "Failed to load plugin {}: invalid UUID."
crd_uuid_already_registered = "UUID {} ({}) is already registered."
crd_handlers_registered = "The handlers from $YELLOW{}.py$RESET are registered."
crd_handler_err = "An error occurred in the handler's execution."
crd_tg_au_err = "Failed to update the message with user information: {}. I will try without a link."
