import json
import logging
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import threading
from flask import Flask, render_template, jsonify
from flask_cors import CORS

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID", "-1002760567924")

# File paths for data storage
USERS_FILE = "users.json"
HISTORY_FILE = "user_history.json"
BROADCAST_FILE = "broadcast.json"
BANLIST_FILE = "banlist.json"
MAPPINGS_FILE = "message_mappings.json"

# Arabic messages
CONFIRMATION_MESSAGE = "✅ تم إرسال رسالتك، سيتم الرد عليك في أقرب وقت ممكن ."
WELCOME_MESSAGE = """مرحبا بك . في بوت تواصل الأقسام

البوت مخصص لـ :
-• تفعيل الموقع من خلال إرسال دليل الإشتراك
-• إرسال ما ورد لكم في الاختبار
-• إرسال الملاحظات والاقتراحات

ارسل رسالتك و سيتم الرد عليك في أقرب وقت 🫡"""
BAN_MESSAGE = "لقد تم حظرك من استخدام البوت❌"
UNBAN_MESSAGE = "! لقد تم رفع الحظر نرجو عدم تكرار الأخطاء السابقة"

def load_json_file(filename):
    """Load data from JSON file, create empty if doesn't exist"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json_file(filename, data):
    """Save data to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving to {filename}: {e}")

def get_user_info(user):
    """Extract user information"""
    return {
        'id': user.id,
        'username': user.username or "No username",
        'first_name': user.first_name or "",
        'last_name': user.last_name or "",
        'display_name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"User_{user.id}"
    }

def add_user(user_id, user_info):
    """Add user to users database"""
    users = load_json_file(USERS_FILE)
    users[str(user_id)] = {
        **user_info,
        'join_date': datetime.now().isoformat()
    }
    save_json_file(USERS_FILE, users)

def add_to_history(user_id, message_text, message_type="user_message"):
    """Add message to user history"""
    history = load_json_file(HISTORY_FILE)
    user_id_str = str(user_id)
    
    if user_id_str not in history:
        history[user_id_str] = []
    
    history[user_id_str].append({
        'message': message_text,
        'type': message_type,
        'timestamp': datetime.now().isoformat()
    })
    
    save_json_file(HISTORY_FILE, history)

def is_user_banned(user_id):
    """Check if user is banned"""
    banlist = load_json_file(BANLIST_FILE)
    return str(user_id) in banlist

def ban_user(user_id, reason="No reason provided"):
    """Ban a user"""
    banlist = load_json_file(BANLIST_FILE)
    users = load_json_file(USERS_FILE)
    
    user_info = users.get(str(user_id), {})
    banlist[str(user_id)] = {
        'username': user_info.get('username', 'Unknown'),
        'display_name': user_info.get('display_name', 'Unknown'),
        'reason': reason,
        'ban_date': datetime.now().isoformat()
    }
    
    save_json_file(BANLIST_FILE, banlist)

def unban_user(user_id):
    """Unban a user"""
    banlist = load_json_file(BANLIST_FILE)
    if str(user_id) in banlist:
        del banlist[str(user_id)]
        save_json_file(BANLIST_FILE, banlist)
        return True
    return False

def save_message_mapping(forwarded_msg_id, user_id):
    """Save message mapping for replies"""
    mappings = load_json_file(MAPPINGS_FILE)
    mappings[f"msg_{forwarded_msg_id}"] = user_id
    save_json_file(MAPPINGS_FILE, mappings)

def get_user_from_mapping(forwarded_msg_id):
    """Get original user ID from forwarded message ID"""
    mappings = load_json_file(MAPPINGS_FILE)
    return mappings.get(f"msg_{forwarded_msg_id}")

def save_reply_mapping(admin_msg_id, user_id, reply_msg_id):
    """Save reply mapping for potential deletion"""
    mappings = load_json_file(MAPPINGS_FILE)
    mappings[f"reply_{admin_msg_id}"] = {
        'user_id': user_id,
        'message_id': reply_msg_id
    }
    save_json_file(MAPPINGS_FILE, mappings)

def get_reply_mapping(admin_msg_id):
    """Get reply mapping info"""
    mappings = load_json_file(MAPPINGS_FILE)
    return mappings.get(f"reply_{admin_msg_id}")

def remove_reply_mapping(admin_msg_id):
    """Remove reply mapping"""
    mappings = load_json_file(MAPPINGS_FILE)
    if f"reply_{admin_msg_id}" in mappings:
        del mappings[f"reply_{admin_msg_id}"]
        save_json_file(MAPPINGS_FILE, mappings)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Only work in private chats
    if chat.type != 'private':
        return
    
    user_info = get_user_info(user)
    add_user(user.id, user_info)
    
    # Create persistent start button
    keyboard = [[KeyboardButton("🚀 ابدأ")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=reply_markup)

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private messages from users"""
    user = update.effective_user
    message = update.message
    
    # Check if user is banned
    if is_user_banned(user.id):
        await message.reply_text(BAN_MESSAGE)
        return
    
    # Handle start button
    if message.text == "🚀 ابدأ":
        await start(update, context)
        return
    
    user_info = get_user_info(user)
    add_user(user.id, user_info)
    
    # Determine message type and content for history
    message_content = ""
    if message.text:
        message_content = message.text
    elif message.photo:
        message_content = f"[صورة] {message.caption or ''}"
    elif message.video:
        message_content = f"[فيديو] {message.caption or ''}"
    elif message.audio:
        message_content = f"[صوت] {message.caption or ''}"
    elif message.voice:
        message_content = "[رسالة صوتية]"
    elif message.document:
        message_content = f"[ملف: {message.document.file_name}] {message.caption or ''}"
    elif message.sticker:
        message_content = f"[ملصق: {message.sticker.emoji or ''}]"
    elif message.animation:
        message_content = f"[GIF] {message.caption or ''}"
    elif message.video_note:
        message_content = "[فيديو دائري]"
    elif message.location:
        message_content = f"[موقع: {message.location.latitude}, {message.location.longitude}]"
    elif message.contact:
        message_content = f"[جهة اتصال: {message.contact.first_name}]"
    else:
        message_content = "[نوع رسالة غير مدعوم]"
    
    add_to_history(user.id, message_content)
    
    # Forward message to admin group
    try:
        # Send user info first
        forward_text = f"📩 رسالة جديدة من:\n"
        forward_text += f"👤 الاسم: {user_info['display_name']}\n"
        forward_text += f"🆔 المعرف: @{user_info['username']}\n"
        forward_text += f"🔢 الرقم: {user.id}\n"
        forward_text += f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        logger.info(f"Attempting to send message to admin group: {ADMIN_GROUP_ID}")
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=forward_text
        )
        
        # Forward the actual message (preserves media)
        forwarded_message = await message.forward(chat_id=ADMIN_GROUP_ID)
        
        # Store mapping for replies (use forwarded message ID) - now persistent
        save_message_mapping(forwarded_message.message_id, user.id)
        logger.info(f"Message forwarded successfully, stored mapping: msg_{forwarded_message.message_id} -> {user.id}")
        
    except Exception as e:
        logger.error(f"Error forwarding message to admin group {ADMIN_GROUP_ID}: {e}")
        logger.error(f"Make sure the bot is added to the admin group and has permission to send messages")
    
    # Send confirmation to user
    await message.reply_text(CONFIRMATION_MESSAGE)

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages in admin group"""
    message = update.message
    chat = update.effective_chat
    
    # Only work in admin group
    if str(chat.id) != str(ADMIN_GROUP_ID):
        return
    
    # Handle replies to forwarded messages
    if message.reply_to_message:
        replied_msg_id = message.reply_to_message.message_id
        
        original_user_id = get_user_from_mapping(replied_msg_id)
        logger.info(f"Reply attempt - Message ID: {replied_msg_id}, Found user: {original_user_id}")
        
        # Check if message starts with @ (admin internal message)
        if message.text and message.text.strip().startswith('@'):
            logger.info(f"Message starts with @, not forwarding to user: {message.text[:50]}")
            return
        
        if original_user_id:
            
            try:
                # Determine if admin is replying with text or media
                if message.text:
                    # Text reply
                    sent_reply = await context.bot.send_message(
                        chat_id=original_user_id,
                        text=f"📩 رد من الإدارة:\n\n{message.text}"
                    )
                    reply_content = f"Admin reply: {message.text}"
                else:
                    # Media reply - send admin info first then forward the media
                    await context.bot.send_message(
                        chat_id=original_user_id,
                        text="📩 رد من الإدارة:"
                    )
                    sent_reply = await message.forward(chat_id=original_user_id)
                    
                    # Determine reply content for history
                    if message.photo:
                        reply_content = f"Admin reply: [صورة] {message.caption or ''}"
                    elif message.video:
                        reply_content = f"Admin reply: [فيديو] {message.caption or ''}"
                    elif message.audio:
                        reply_content = f"Admin reply: [صوت] {message.caption or ''}"
                    elif message.voice:
                        reply_content = "Admin reply: [رسالة صوتية]"
                    elif message.document:
                        reply_content = f"Admin reply: [ملف: {message.document.file_name}] {message.caption or ''}"
                    elif message.sticker:
                        reply_content = f"Admin reply: [ملصق: {message.sticker.emoji or ''}]"
                    elif message.animation:
                        reply_content = f"Admin reply: [GIF] {message.caption or ''}"
                    elif message.video_note:
                        reply_content = "Admin reply: [فيديو دائري]"
                    elif message.location:
                        reply_content = f"Admin reply: [موقع: {message.location.latitude}, {message.location.longitude}]"
                    elif message.contact:
                        reply_content = f"Admin reply: [جهة اتصال: {message.contact.first_name}]"
                    else:
                        reply_content = "Admin reply: [نوع رسالة غير مدعوم]"
                
                # Store reply message ID for potential deletion - now persistent
                save_reply_mapping(message.message_id, original_user_id, sent_reply.message_id)
                
                # Add to history
                add_to_history(original_user_id, reply_content, "admin_reply")
                
                # Confirm to admin
                await message.reply_text("✅ تم إرسال الرد للمستخدم")
                
            except Exception as e:
                await message.reply_text(f"❌ فشل في إرسال الرد: {str(e)}")

async def cmd_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send message to all users"""
    chat = update.effective_chat
    
    if str(chat.id) != str(ADMIN_GROUP_ID):
        return
    
    if not context.args:
        await update.message.reply_text("❌ الاستخدام: /all <الرسالة>")
        return
    
    broadcast_message = " ".join(context.args)
    users = load_json_file(USERS_FILE)
    broadcast_data = load_json_file(BROADCAST_FILE)
    
    success_count = 0
    failed_count = 0
    broadcast_id = datetime.now().isoformat()
    broadcast_data[broadcast_id] = {'recipients': []}
    
    for user_id in users.keys():
        try:
            sent_msg = await context.bot.send_message(
                chat_id=int(user_id),
                text=f"📢 رسالة من الإدارة:\n\n{broadcast_message}"
            )
            broadcast_data[broadcast_id]['recipients'].append({
                'user_id': user_id,
                'message_id': sent_msg.message_id
            })
            success_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send to {user_id}: {e}")
    
    save_json_file(BROADCAST_FILE, broadcast_data)
    
    await update.message.reply_text(
        f"✅ تم إرسال الرسالة\n"
        f"نجح: {success_count}\n"
        f"فشل: {failed_count}"
    )

async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user count"""
    chat = update.effective_chat
    
    if str(chat.id) != str(ADMIN_GROUP_ID):
        return
    
    users = load_json_file(USERS_FILE)
    actual_user_count = len(users)
    displayed_count = 1200 + actual_user_count
    
    await update.message.reply_text(f"👥 عدد المستخدمين: {displayed_count}")

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user"""
    chat = update.effective_chat
    
    if str(chat.id) != str(ADMIN_GROUP_ID):
        return
    
    if not context.args:
        await update.message.reply_text("❌ الاستخدام: /ban <المعرف> [السبب]")
        return
    
    try:
        user_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        
        ban_user(user_id, reason)
        await update.message.reply_text(f"✅ تم حظر المستخدم {user_id}")
        
    except ValueError:
        await update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقم")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user"""
    chat = update.effective_chat
    
    if str(chat.id) != str(ADMIN_GROUP_ID):
        return
    
    if not context.args:
        await update.message.reply_text("❌ الاستخدام: /unban <المعرف>")
        return
    
    try:
        user_id = int(context.args[0])
        
        if unban_user(user_id):
            await update.message.reply_text(f"✅ تم رفع الحظر عن المستخدم {user_id}")
            
            # Notify user
            try:
                await context.bot.send_message(chat_id=user_id, text=UNBAN_MESSAGE)
            except Exception as e:
                logger.error(f"Failed to notify unbanned user: {e}")
        else:
            await update.message.reply_text("❌ المستخدم غير محظور")
            
    except ValueError:
        await update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقم")

async def cmd_banlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show banned users"""
    chat = update.effective_chat
    
    if str(chat.id) != str(ADMIN_GROUP_ID):
        return
    
    banlist = load_json_file(BANLIST_FILE)
    
    if not banlist:
        await update.message.reply_text("📋 لا يوجد مستخدمين محظورين")
        return
    
    message = "🚫 قائمة المحظورين:\n\n"
    for user_id, data in banlist.items():
        message += f"👤 {data['display_name']} (@{data['username']})\n"
        message += f"🆔 {user_id}\n"
        message += f"📝 السبب: {data['reason']}\n"
        message += f"📅 تاريخ الحظر: {data['ban_date'][:10]}\n\n"
    
    # Split long messages
    if len(message) > 4000:
        parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(message)

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user message history"""
    chat = update.effective_chat
    
    if str(chat.id) != str(ADMIN_GROUP_ID):
        return
    
    user_id = None
    
    # Check if replying to a message
    if update.message.reply_to_message:
        replied_msg_id = update.message.reply_to_message.message_id
        user_id = get_user_from_mapping(replied_msg_id)
    
    # Check if user ID provided as argument
    elif context.args:
        try:
            user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقم")
            return
    
    if not user_id:
        await update.message.reply_text("❌ الاستخدام: /history <المعرف> أو رد على رسالة")
        return
    
    history = load_json_file(HISTORY_FILE)
    user_history = history.get(str(user_id), [])
    
    if not user_history:
        await update.message.reply_text("📋 لا يوجد تاريخ رسائل لهذا المستخدم")
        return
    
    users = load_json_file(USERS_FILE)
    user_info = users.get(str(user_id), {})
    
    message = f"📋 تاريخ رسائل {user_info.get('display_name', 'Unknown')} ({user_id}):\n\n"
    
    for entry in user_history[-10:]:  # Show last 10 messages
        timestamp = entry['timestamp'][:19].replace('T', ' ')
        message += f"📅 {timestamp}\n"
        message += f"📝 {entry['message'][:100]}{'...' if len(entry['message']) > 100 else ''}\n"
        message += f"🏷️ {entry['type']}\n\n"
    
    if len(user_history) > 10:
        message += f"... و {len(user_history) - 10} رسالة أخرى"
    
    await update.message.reply_text(message)

async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete messages"""
    chat = update.effective_chat
    
    if str(chat.id) != str(ADMIN_GROUP_ID):
        return
    
    # Handle /delete all
    if context.args and context.args[0].lower() == "all":
        broadcast_data = load_json_file(BROADCAST_FILE)
        
        if not broadcast_data:
            await update.message.reply_text("❌ لا يوجد رسائل بث للحذف")
            return
        
        # Get the latest broadcast
        latest_broadcast = max(broadcast_data.keys())
        recipients = broadcast_data[latest_broadcast]['recipients']
        
        deleted_count = 0
        failed_count = 0
        for recipient in recipients:
            try:
                await context.bot.delete_message(
                    chat_id=int(recipient['user_id']),
                    message_id=recipient['message_id']
                )
                deleted_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to delete broadcast message for {recipient['user_id']}: {e}")
        
        # Remove the broadcast record
        del broadcast_data[latest_broadcast]
        save_json_file(BROADCAST_FILE, broadcast_data)
        
        await update.message.reply_text(f"✅ تم حذف آخر رسالة بث\nنجح: {deleted_count}\nفشل: {failed_count}")
        return
    
    # Handle regular delete (reply to message)
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ يجب الرد على رسالة لحذفها")
        return
    
    replied_msg_id = update.message.reply_to_message.message_id
    user_id_key = f"msg_{replied_msg_id}"
    
    try:
        # Delete the message in admin group
        await update.message.reply_to_message.delete()
        
        # Check if this was an admin reply and try to delete it from user chat too
        reply_info = get_reply_mapping(replied_msg_id)
        if reply_info:
            try:
                await context.bot.delete_message(
                    chat_id=reply_info['user_id'],
                    message_id=reply_info['message_id']
                )
                # Remove the mapping
                remove_reply_mapping(replied_msg_id)
                await update.message.reply_text("✅ تم حذف الرسالة من المجموعة ومن المستخدم")
            except Exception as e:
                await update.message.reply_text("✅ تم حذف الرسالة من المجموعة (فشل حذفها من المستخدم)")
        else:
            await update.message.reply_text("✅ تم حذف الرسالة من المجموعة")
            
    except Exception as e:
        await update.message.reply_text(f"❌ فشل في حذف الرسالة: {str(e)}")

async def cmd_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available commands"""
    chat = update.effective_chat
    
    if str(chat.id) != str(ADMIN_GROUP_ID):
        return
    
    commands_text = """📋 قائمة الأوامر المتاحة:

/all <الرسالة> - إرسال رسالة لجميع المستخدمين
/list - عرض عدد المستخدمين
/ban <المعرف> [السبب] - حظر مستخدم
/unban <المعرف> - رفع الحظر عن مستخدم
/banlist - عرض قائمة المحظورين
/history <المعرف> - عرض تاريخ رسائل مستخدم
/delete - حذف رسالة (رد على الرسالة)
/delete all - حذف آخر رسالة بث
/commands - عرض هذه القائمة

💡 يمكن استخدام /history بالرد على رسالة مُعاد توجيهها"""
    
    await update.message.reply_text(commands_text)

# Flask Web App Integration
app = Flask(__name__)
CORS(app)

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/stats')
def get_stats():
    """Get bot statistics"""
    try:
        users = load_json_file(USERS_FILE)
        history = load_json_file(HISTORY_FILE)
        banlist = load_json_file(BANLIST_FILE)
        mappings = load_json_file(MAPPINGS_FILE)
        
        # Calculate message count
        total_messages = 0
        for user_messages in history.values():
            total_messages += len(user_messages)
        
        # Get active mappings count
        active_mappings = len([k for k in mappings.keys() if k.startswith('msg_')])
        
        stats = {
            'total_users': len(users),
            'display_users': 1200 + len(users),  # User preference from replit.md
            'banned_users': len(banlist),
            'total_messages': total_messages,
            'active_mappings': active_mappings,
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users')
def get_users():
    """Get user list"""
    try:
        users = load_json_file(USERS_FILE)
        banlist = load_json_file(BANLIST_FILE)
        
        user_list = []
        for user_id, user_data in users.items():
            user_info = {
                'id': user_id,
                'display_name': user_data.get('display_name', 'Unknown'),
                'username': user_data.get('username', 'No username'),
                'join_date': user_data.get('join_date', ''),
                'is_banned': user_id in banlist
            }
            user_list.append(user_info)
        
        # Sort by join date (newest first)
        user_list.sort(key=lambda x: x['join_date'], reverse=True)
        
        return jsonify(user_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent-activity')
def get_recent_activity():
    """Get recent bot activity"""
    try:
        history = load_json_file(HISTORY_FILE)
        
        # Get recent messages from all users
        recent_messages = []
        for user_id, messages in history.items():
            if not messages:  # Skip empty message lists
                continue
            for message in messages[-5:]:  # Last 5 messages per user
                if isinstance(message, dict) and 'message' in message and 'timestamp' in message:
                    recent_messages.append({
                        'user_id': user_id,
                        'message': message['message'][:100] + ('...' if len(message['message']) > 100 else ''),
                        'type': message.get('type', 'user_message'),
                        'timestamp': message['timestamp']
                    })
        
        # Sort by timestamp (newest first)
        recent_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify(recent_messages[:20])  # Return 20 most recent
    except Exception as e:
        logger.error(f"Error in recent-activity API: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

def run_flask_app():
    """Run Flask app in a separate thread"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def check_dependencies():
    """Check and install required dependencies"""
    required_packages = {
        'telegram': 'python-telegram-bot',
        'flask': 'flask',
        'flask_cors': 'flask-cors'
    }
    
    missing_packages = []
    for module, package in required_packages.items():
        try:
            __import__(module)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Run 'python install_requirements.py' to install dependencies")
        return False
    return True

def main():
    """Start the bot"""
    # Check dependencies first
    if not check_dependencies():
        print("❌ Please install missing dependencies before running the bot")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("all", cmd_all))
    application.add_handler(CommandHandler("list", cmd_list))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("banlist", cmd_banlist))
    application.add_handler(CommandHandler("history", cmd_history))
    application.add_handler(CommandHandler("delete", cmd_delete))
    application.add_handler(CommandHandler("commands", cmd_commands))
    
    # Message handlers
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & ~filters.COMMAND, 
        handle_private_message
    ))
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.COMMAND, 
        handle_group_message
    ))
    
    # Bot data is now persistent via JSON files
    
    print("🤖 Bot is starting...")
    print(f"🔑 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"👥 Admin Group ID: {ADMIN_GROUP_ID}")
    print("🌐 Starting Flask web interface on port 5000...")
    print("✅ Bot and web interface are running! Press Ctrl+C to stop.")
    
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
