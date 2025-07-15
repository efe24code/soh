from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
import os
import secrets

# Uygulama ve veritabanı yapılandırması
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16) # Güvenli bir gizli anahtar
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Bellek kullanımını optimize etmek için

db = SQLAlchemy(app)
socketio = SocketIO(app)

# Veritabanı Modelleri
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=True) # Kullanıcının içinde bulunduğu oda
    room = db.relationship('Room', backref=db.backref('users', lazy=True)) # Oda ile ilişki

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    user = db.relationship('User', backref=db.backref('messages', lazy=True))
    room = db.relationship('Room', backref=db.backref('messages', lazy=True))

# Veritabanını oluşturma veya güncelleme
with app.app_context():
    db.create_all()
    print("Veritabanı başlatıldı veya zaten mevcut.")
    # Varsayılan odaları ekle (eğer yoksa)
    default_rooms = ['Genel', 'Oyun', 'Sohbet']
    for room_name in default_rooms:
        if not Room.query.filter_by(name=room_name).first():
            new_room = Room(name=room_name)
            db.session.add(new_room)
            print(f"'{room_name}' odası eklendi.")
    db.session.commit()

# Route'lar (Sayfa Yönlendirmeleri)
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login')) # Kullanıcı girişi yapılmamışsa login sayfasına yönlendir

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None) # Kullanıcı bulunamazsa oturumu kapat
        return redirect(url_for('login'))

    rooms = Room.query.all()
    current_room = None
    messages = []
    if user.room_id:
        current_room = Room.query.get(user.room_id)
        messages = Message.query.filter_by(room_id=user.room_id).order_by(Message.timestamp.asc()).all()
    
    return render_template('index.html',
                           user_id=session['user_id'],
                           username=user.username,
                           rooms=rooms,
                           current_room=current_room,
                           messages=messages)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: # Zaten giriş yapmışsa ana sayfaya yönlendir
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash('Başarıyla giriş yapıldı!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Kullanıcı adı veya şifre yanlış.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session: # Zaten giriş yapmışsa ana sayfaya yönlendir
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten alınmış.', 'danger')
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password_hash=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Çıkış yapıldı.', 'info')
    return redirect(url_for('login'))

@app.route('/join_room/<int:room_id>')
def join_room_route(room_id):
    if 'user_id' not in session:
        flash('Lütfen önce giriş yapın.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    room = Room.query.get(room_id)

    if user and room:
        user.room_id = room.id
        db.session.commit()
        flash(f'"{room.name}" odasına katıldınız.', 'success')
    else:
        flash('Oda bulunamadı veya bir hata oluştu.', 'danger')
    return redirect(url_for('index'))

# SocketIO Olayları
@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.room_id:
            room = Room.query.get(user.room_id)
            if room:
                join_room(room.id)
                emit('status_message', {'msg': f'{user.username} odaya katıldı.'}, room=room.id)
                print(f"{user.username} odasına katıldı: {room.name}")
            else:
                print(f"Kullanıcı {user.username} için oda bulunamadı.")
        else:
            print("Kullanıcı oturumu aktif ancak oda ID'si yok veya kullanıcı bulunamadı.")
    else:
        print("Bağlantı kuruldu ama kullanıcı oturumu yok.")
        # Bağlantı kurulur kurulmaz kullanıcı girişi yapılmadığı için disconnect edebilirsin
        # veya frontendde kullanıcıyı login'e yönlendirebilirsin.
        # request.namespace.disconnect() # İstemci tarafında yönlendirme daha iyi

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.room_id:
            room = Room.query.get(user.room_id)
            if room:
                leave_room(room.id)
                emit('status_message', {'msg': f'{user.username} odadan ayrıldı.'}, room=room.id)
                print(f"{user.username} odasından ayrıldı: {room.name}")

@socketio.on('message')
def handle_message(data):
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        room_id = data.get('room_id')
        msg_content = data.get('msg')
        
        if not user or not room_id or not msg_content:
            print("Geçersiz mesaj veya kullanıcı/oda bilgisi eksik.")
            return

        room = Room.query.get(room_id)
        if not room:
            print(f"Mesaj gönderilen oda bulunamadı: {room_id}")
            return

        new_message = Message(room_id=room.id, user_id=user.id, content=msg_content)
        db.session.add(new_message)
        db.session.commit()

        # Mesajı odaya yayınla
        emit('new_message', {
            'username': user.username,
            'content': msg_content,
            'timestamp': new_message.timestamp.strftime('%H:%M'), # Sadece saat ve dakika
            'user_id': user.id # Kullanıcının kendi mesajı olup olmadığını kontrol etmek için
        }, room=room.id)
        print(f"Mesaj alındı - Oda: {room.name}, Kullanıcı: {user.username}, Mesaj: {msg_content}")
    else:
        print("Mesaj göndermek için oturum açılmamış.")

# Uygulamayı başlat
if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5000))