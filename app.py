from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from database import db, User, Message, init_db
import os
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app)

# Online kullanıcıları ve onların Socket SID'lerini tutan bir sözlük
# Format: {user_id: sid, ...}
online_users_sid = {}
# Format: {sid: user_id, ...}
sid_to_user_id = {}


with app.app_context():
    init_db(app)

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'), user_id=session.get('user_id'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Geçersiz kullanıcı adı veya şifre.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            return render_template('register.html', error='Kullanıcı adı ve şifre boş bırakılamaz.')
        if User.query.filter_by(username=username).first():
            return render_template('register.html', error='Bu kullanıcı adı zaten alınmış.')
        
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    # Session'ı temizlemeden önce SocketIO bağlantısını kesmesi için bir mesaj gönderebiliriz
    # Veya direkt olarak session'ı sonlandırırız, disconnect olayı tetiklenecektir.
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@socketio.on('connect')
def handle_connect():
    if 'user_id' not in session:
        print(f"Yetkisiz bağlantı denemesi: {request.sid}")
        # Yetkisiz bağlantıyı reddetmek için False döndür veya disconnect et
        return False 
    
    user_id = session.get('user_id')
    username = session.get('username')
    
    # Kullanıcıyı online kullanıcılar listesine ekle
    online_users_sid[user_id] = request.sid
    sid_to_user_id[request.sid] = user_id

    print(f'Kullanıcı bağlı: {username} ({request.sid})')
    join_room('genel_sohbet') 
    
    # Yeni bağlanan kullanıcıya son 50 genel mesajı gönder
    messages = Message.query.order_by(Message.timestamp.desc()).limit(50).all()
    messages.reverse() # En eski mesajdan en yeniye doğru sırala
    for msg in messages:
        author_username = User.query.get(msg.user_id).username if User.query.get(msg.user_id) else "Bilinmeyen"
        emit('receive_message', {'username': author_username, 'message': msg.content, 'timestamp': msg.timestamp.strftime('%H:%M')}, room=request.sid) 
    
    # Diğer kullanıcılara yeni kullanıcının katıldığını bildir
    emit('receive_message', {'username': 'Sistem', 'message': f'{username} sohbete katıldı.', 'timestamp': datetime.datetime.now().strftime('%H:%M')}, room='genel_sohbet', include_self=False)
    
    # Tüm kullanıcılara güncel online kullanıcı listesini gönder
    broadcast_online_users()


@socketio.on('disconnect')
def handle_disconnect():
    user_id = sid_to_user_id.get(request.sid)
    # Session'dan username alma, eğer session sona ermişse default değer kullan
    username = session.get('username')
    
    # online_users_sid ve sid_to_user_id sözlüklerinden kullanıcıyı kaldır
    if user_id in online_users_sid:
        del online_users_sid[user_id]
    if request.sid in sid_to_user_id:
        del sid_to_user_id[request.sid]

    if username: # Eğer username alınabildiyse, ayrılma mesajı gönder
        print(f'Kullanıcı bağlantısı kesildi: {username} ({request.sid})')
        emit('receive_message', {'username': 'Sistem', 'message': f'{username} sohbetten ayrıldı.', 'timestamp': datetime.datetime.now().strftime('%H:%M')}, room='genel_sohbet', include_self=False)
    else:
        print(f'Bilinmeyen bir kullanıcı bağlantısı kesildi: ({request.sid})')

    leave_room('genel_sohbet')
    
    # Tüm kullanıcılara güncel online kullanıcı listesini gönder
    broadcast_online_users()

@socketio.on('send_message')
def handle_message(data):
    # Kullanıcının oturumu var mı kontrol et
    if 'user_id' not in session:
        print("Yetkisiz kullanıcıdan mesaj alındı.")
        return
    
    user_id = session['user_id']
    username = session['username']
    message_content = data['message']
    current_time = datetime.datetime.now()
    
    # Mesajı veritabanına kaydet (genel mesajlar için)
    new_message = Message(user_id=user_id, content=message_content, timestamp=current_time)
    db.session.add(new_message)
    db.session.commit()
    
    emit('receive_message', {'username': username, 'message': message_content, 'timestamp': current_time.strftime('%H:%M'), 'is_private': False}, room='genel_sohbet')
    print(f"Genel Mesaj: {username}: {message_content}")

@socketio.on('send_private_message')
def handle_private_message(data):
    if 'user_id' not in session:
        print("Yetkisiz kullanıcıdan özel mesaj alındı.")
        return

    sender_id = session['user_id']
    sender_username = session['username']
    recipient_id = data['recipient_id']
    message_content = data['message']
    current_time = datetime.datetime.now()

    recipient_sid = online_users_sid.get(recipient_id)
    sender_sid = online_users_sid.get(sender_id) # Gönderen SID'si (kendi mesajını görmesi için)

    recipient_user = User.query.get(recipient_id)
    recipient_username = recipient_user.username if recipient_user else "Bilinmeyen Alıcı"


    if recipient_sid and sender_sid:
        # Mesajı alıcıya gönder
        emit('receive_private_message', {
            'sender_id': sender_id,
            'sender_username': sender_username,
            'message': message_content,
            'timestamp': current_time.strftime('%H:%M')
        }, room=recipient_sid)
        
        # Mesajı gönderene de kendi ekranında görmesi için gönder
        # (Eğer gönderen ve alıcı aynı kişi değilse ve gönderen zaten o an o sohbetteyse)
        if sender_id != recipient_id: # Kendi kendine mesaj atmıyorsa, kendine de gönder
            emit('receive_private_message', {
                'sender_id': sender_id, # Gönderen kendisi olduğu için
                'sender_username': sender_username,
                'message': message_content,
                'timestamp': current_time.strftime('%H:%M')
            }, room=sender_sid)
        
        print(f"Özel Mesaj: {sender_username} -> {recipient_username}: {message_content}")
    else:
        # Kullanıcı çevrimdışıysa gönderene bilgi ver
        if sender_sid:
            emit('receive_message', {'username': 'Sistem', 'message': f'{recipient_username} çevrimdışı. Mesaj gönderilemedi.', 'timestamp': current_time.strftime('%H:%M')}, room=sender_sid)
            print(f"Uyarı: {sender_username}, {recipient_username} çevrimdışı.")

def broadcast_online_users():
    online_users_data = []
    # User nesnelerini alıp online_users_data listesine ekle
    for user_id, sid in online_users_sid.items():
        user = User.query.get(user_id)
        if user: # user_id'si olan kullanıcıyı ekle
            online_users_data.append({'id': user.id, 'username': user.username})
    
    # Tüm bağlı istemcilere güncel listeyi gönder
    emit('online_users_list', {'users': online_users_data}, broadcast=True)


if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)