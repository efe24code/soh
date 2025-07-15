const messagesDiv = document.getElementById('messages');
const messageInput = document.getElementById('messageInput');
const onlineUsersList = document.getElementById('onlineUsersList');
const generalChatChannel = document.getElementById('generalChatChannel');
const chatHeader = document.getElementById('chatHeader');
const chatTitle = document.getElementById('chatTitle'); // Yeni eklenen başlık span'i

const socket = io();

let currentChatMode = 'general'; // 'general' veya 'private'
let currentRecipient = null; // Özel sohbetteki alıcının {id, username} bilgisi

// Socket.IO Bağlantı Olayları
socket.on('connect', function() {
    console.log("WebSocket bağlantısı kuruldu.");
    // appendMessage("Sistem", "Sohbete hoş geldin!"); // İlk bağlanmada bu mesajı arka arkaya basabiliyor, kapatabiliriz.
});

// Sunucudan 'receive_message' olayı (genel mesaj) alındığında
socket.on('receive_message', function(data) {
    // Sadece genel sohbet modundaysak ve mesaj özel mesaj değilse göster
    // Sistem mesajları her zaman gösterilir (is_private false olduğu için)
    if (currentChatMode === 'general' || data.username === 'Sistem') { 
        appendMessage(data.username, data.message, data.timestamp, false); 
    }
});

// Sunucudan 'receive_private_message' olayı (özel mesaj) alındığında
socket.on('receive_private_message', function(data) {
    console.log("Özel Mesaj alındı:", data);
    
    // Eğer o an bu kullanıcıyla özel sohbetteysek veya mesajı biz gönderdiysek göster
    if (currentChatMode === 'private' && currentRecipient && 
        (currentRecipient.id === data.sender_id || data.sender_id === MY_USER_ID)) {
        appendMessage(data.sender_username, data.message, data.timestamp, true); 
    } else if (data.sender_id !== MY_USER_ID) { // Kendi gönderdiğimiz mesaj değilse
        // Kullanıcıya yeni özel mesaj geldiğini bildirimle
        alert(`Yeni özel mesaj var: ${data.sender_username}'dan!`);
        // İstersen burada daha şık bir bildirim sistemi kurabilirsin (toast notification vb.)
    }
});


// Sunucu bağlantısı kesildiğinde
socket.on('disconnect', function() {
    console.log("WebSocket bağlantısı kapatıldı.");
    appendMessage("Sistem", "Bağlantı kesildi. Lütfen sayfayı yenileyin.", new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }));
    onlineUsersList.innerHTML = '<p class="no-users">Bağlantı kesildi. Çevrimiçi kullanıcılar yüklenemiyor.</p>';
});

// Socket.IO bağlantısında hata oluştuğunda
socket.on('connect_error', function(error) {
    console.error("Socket.IO bağlantı hatası:", error);
    appendMessage("Sistem", "Bağlantı hatası oluştu.", new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }));
});

// Online kullanıcı listesi sunucudan geldiğinde
socket.on('online_users_list', function(data) {
    updateOnlineUsersList(data.users);
});


// Mesajı sohbet ekranına ekleyen yardımcı fonksiyon
function appendMessage(username, message, timestamp, isPrivate = false) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    if (isPrivate) {
        messageElement.classList.add('private-message');
    }
    // Sistem mesajlarını farklı stilize etmek için
    if (username === "Sistem") {
        messageElement.classList.add('system-notification');
        messageElement.innerHTML = `<span class="text">${message}</span>`;
    } else if (isPrivate) {
        // Özel mesajda göndereni ve mesajı net göster
        // Eğer kendi gönderdiğimiz mesajsa "Ben" olarak göster
        const displayUsername = (username === MY_USERNAME && !currentRecipient) ? "Ben (özel)" : username + " (özel)";
        messageElement.innerHTML = `<span class="username">${displayUsername}:</span> <span class="text">${message}</span> <span class="timestamp">${timestamp}</span>`;
    } else {
        messageElement.innerHTML = `<span class="username">${username}:</span> <span class="text">${message}</span> <span class="timestamp">${timestamp}</span>`;
    }
    
    messagesDiv.appendChild(messageElement);
    messagesDiv.scrollTop = messagesDiv.scrollHeight; 
}

// Mesaj gönderme fonksiyonu
function sendMessage() {
    const message = messageInput.value.trim();
    if (message === '') return;

    if (currentChatMode === 'general') {
        socket.emit('send_message', { message: message });
    } else if (currentChatMode === 'private' && currentRecipient) {
        socket.emit('send_private_message', { recipient_id: currentRecipient.id, message: message });
    }
    messageInput.value = '';
}

// Enter tuşuna basıldığında mesaj gönderme
messageInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Online kullanıcı listesini güncelleyen fonksiyon
function updateOnlineUsersList(users) {
    onlineUsersList.innerHTML = ''; // Listeyi temizle

    // Kendi kullanıcımızı listeden filtrele
    const filteredUsers = users.filter(user => user.id !== MY_USER_ID);

    if (filteredUsers.length === 0) {
        onlineUsersList.innerHTML = '<p class="no-users">Henüz kimse çevrimiçi değil.</p>';
        return;
    }

    filteredUsers.forEach(user => {
        const userElement = document.createElement('p');
        userElement.classList.add('user-item');
        userElement.textContent = user.username;
        userElement.dataset.userId = user.id; 
        userElement.dataset.username = user.username; 

        userElement.addEventListener('click', () => startPrivateChat(user));
        onlineUsersList.appendChild(userElement);
    });

    // Eğer şu an özel sohbetteysek ve alıcı hala online ise, aktif kullanıcıyı işaretle
    if (currentChatMode === 'private' && currentRecipient) {
        const activeUserElement = document.querySelector(`.user-item[data-user-id="${currentRecipient.id}"]`);
        if (activeUserElement) {
            activeUserElement.classList.add('active-user-item');
        } else {
            // Eğer alıcı çevrimdışı olduysa genel sohbete dön
            appendMessage("Sistem", `${currentRecipient.username} çevrimdışı oldu. Genel sohbete geçildi.`, new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }));
            switchChatMode('general');
        }
    }
}

// Genel sohbete geçiş
generalChatChannel.addEventListener('click', () => {
    switchChatMode('general');
});

// Özel sohbete başlama fonksiyonu
function startPrivateChat(user) {
    // Kendi kendine özel mesaj atmasını engelle (zaten filteredUsers ile engelleniyor ama ekstra kontrol)
    if (user.id === MY_USER_ID) { 
        alert("Kendinize özel mesaj gönderemezsiniz.");
        return;
    }
    switchChatMode('private', user);
}

// Sohbet modunu değiştiren fonksiyon
function switchChatMode(mode, user = null) {
    currentChatMode = mode;
    messagesDiv.innerHTML = ''; // Mesajları temizle
    currentRecipient = null;

    // Kanal seçimlerini güncelle
    document.querySelectorAll('.channel-list p, .user-list p').forEach(p => {
        p.classList.remove('active-channel');
        p.classList.remove('active-user-item');
    });

    if (mode === 'general') {
        chatHeader.dataset.mode = "general"; // Header ikonunu güncellemek için
        chatTitle.textContent = 'genel-sohbet';
        generalChatChannel.classList.add('active-channel');
        appendMessage("Sistem", "Genel sohbete geri döndün. Geçmiş mesajlar yükleniyor...", new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }));
        // Bağlandığımızda genel mesajlar zaten gönderiliyor, ekstra istek gerekmez.
        // Ama manuel geçişte geçmişi tekrar istersen:
        // socket.emit('request_general_chat_history'); // Backend'de tanımlanmalı
    } else if (mode === 'private' && user) {
        currentRecipient = user;
        chatHeader.dataset.mode = "private"; // Header ikonunu güncellemek için
        chatTitle.textContent = user.username; // Özel sohbet başlığı
        
        // Özel sohbetteki kullanıcıyı aktif olarak işaretle
        const activeUserElement = document.querySelector(`.user-item[data-user-id="${user.id}"]`);
        if (activeUserElement) {
            activeUserElement.classList.add('active-user-item');
        }
        appendMessage("Sistem", `${user.username} ile özel sohbettesin.`, new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }));
        // İdealde burada backend'den özel mesaj geçmişi istenir
    }
}