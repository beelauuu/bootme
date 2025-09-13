import os
import logging
import requests
from flask import Flask, request
from dotenv import load_dotenv
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
load_dotenv()

app = Flask(__name__)

BOT_ID = os.getenv('GROUPME_BOT_ID')
ACCESS_TOKEN = os.getenv('GROUPME_ACCESS_TOKEN')
GROUP_ID = os.getenv('GROUPME_GROUP_ID')
PORT = int(os.getenv('PORT', 3000))
GROUPME_API = 'https://api.groupme.com/v3'
BANNED_KEYWORDS = [
    'give out',
    'for free',
    'willing to give',
    'free because',
    'free',
    'give it because',
    'macbook',
    'macbook air',
    'ps5',
    'playstation',
    'gaming system',
    'model 2025',
    'lost my son',
    'cancer',
    'son',
    'daughter',
    'hurts my soul',
    'no mother should',
    'god knows best',
    'text me',
    'send me a message',
    'email',
    'gmail',
    'hotmail',
    'yahoo',
    'perfect health and good condition',
    'condition',
    'health'
    'charger included',
    'afford one',
    'interested',
]

recently_joined = {}
NEW_USER_WINDOW_HOURS = 72 

def validate_config():
    if not all([BOT_ID, ACCESS_TOKEN, GROUP_ID]):
        logger.error("Missing required environment variables")
        raise ValueError("Missing BOT_ID, ACCESS_TOKEN, or GROUP_ID")

def contains_banned_keyword(text):
    if not text:
        return False
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in BANNED_KEYWORDS)

def send_bot_message(text):
    try:
        response = requests.post(
            f'{GROUPME_API}/bots/post',
            json={'bot_id': BOT_ID, 'text': text}
        )
        
        if response.status_code == 202:
            logger.info(f"Message sent: {text}")
            return True
        else:
            logger.error(f"Failed to send message. Status: {response.json()}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Error sending message: {e}")
        return False

def get_membership_id(user_id):
    try:
        response = requests.get(
            f"{GROUPME_API}/groups/{GROUP_ID}",
            params={'token': ACCESS_TOKEN}
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to get group info. Status: {response.json()}")
            return None
        
        group_data = response.json()['response']
        print(group_data)
        
        for member in group_data['members']:
            if member['user_id'] == user_id:
                return member['id']
        
        logger.warning(f"User ID {user_id} not found in group members")
        return None
        
    except requests.RequestException as e:
        logger.error(f"Error getting membership ID: {e}")
        return None
    
def delete_message(message_id):
    try:
        response = requests.delete(
            f"{GROUPME_API}/conversations/{GROUP_ID}/messages/{message_id}",
            params={'token': ACCESS_TOKEN}
        )
        
        if response.status_code == 204:
            logger.info(f"Successfully deleted message {message_id}")
            return True
        else:
            logger.error(f"Failed to delete message. Info: {response.json()}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Error deleting message: {e}")
        return False

def kick_user(user_id, username):
    try:
        membership_id = get_membership_id(user_id)
        if not membership_id:
            logger.error(f"Cannot kick user {username}: membership ID not found")
            return False
        
        response = requests.post(
            f"{GROUPME_API}/groups/{GROUP_ID}/members/{membership_id}/remove",
            params={'token': ACCESS_TOKEN}
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully kicked user {username} (ID: {user_id})")
            return True
        else:
            logger.error(f"Failed to kick user {username}. Info: {response.json()}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Error kicking user: {e}")
        return False

def is_new_user(user_id):
    if user_id not in recently_joined:
        return False
    
    join_time = recently_joined[user_id]
    time_since_join = datetime.now() - join_time
    if time_since_join > timedelta(hours=NEW_USER_WINDOW_HOURS):
        del recently_joined[user_id]
        return False
    return True

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()        
        text = data.get('text', '')
        user_id = data.get('user_id')
        username = data.get('name', 'Unknown')
        message_id = data.get('id')

        if data.get('system'):
            if 'added' in text.lower() or 'joined' in text.lower():
                recently_joined[user_id] = datetime.now()
                logger.info(f"User {username} joined the group")
                return '', 200
              
        if contains_banned_keyword(text) and is_new_user(user_id):
            if message_id:
                delete_message(message_id)
            if kick_user(user_id, username):
                message = f"⚠️ User {username} was removed for violating group rules."
                send_bot_message(message)
                if user_id in recently_joined:
                    del recently_joined[user_id]
        return '', 200
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return '', 500

@app.route('/', methods=['GET'])
def index():
    """Basic status page"""
    return f'''
    <h1>GroupMe Moderation Bot</h1>
    <p>Status: Running</p>
    <p>Monitoring keywords: {len(BANNED_KEYWORDS)}</p>
    ''', 200

if __name__ == '__main__':
    try:        
        logger.info(f"Starting GroupMe bot on port {PORT}")        
        app.run(host='0.0.0.0', port=PORT, debug=False)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        exit(1)