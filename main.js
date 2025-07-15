document.addEventListener('DOMContentLoaded', () => {
    // Socket.IO bağlantısını kur
    // Eğer uygulaman Render gibi bir PaaS üzerinde çalışıyorsa
    // window.location.origin ile doğru WebSocket URL'sini alır.
    const socket = io.connect(window.location.origin);

    const messageInput = document.getElementById('messageInput');
    const sendMessageButton = document.getElementById('sendMessageButton');
    const messagesDiv = document.getElementById('messages');

    // Sayfa yüklendiğinde mesajları en aşağı kaydır
    function scrollToBottom() {
        if (messagesDiv) {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
    }

    // Socket bağlantısı kurulduğunda
    socket.on('connect', () => {
        console.log('Socket.IO Bağlantısı kuruldu.');
        // Bağlantı kurulduğunda sunucuya mevcut odaya katılma isteği gönder (eğer oda varsa)
        if (CURRENT_ROOM_ID !== null) {
            // Sunucuya bilgi gitmesine gerek yok, Flask route'u zaten odaya katılımı yönetiyor
            // Socket.IO connect eventi sunucu tarafında user.room_id'yi kontrol edip join_room yapıyor.
        } else {
            console.log("Oda seçili değil, mesaj gönderme butonu ve inputu devre dışı.");
            if (messageInput) messageInput.disabled = true;
            if (sendMessageButton) sendMessageButton.disabled = true;
        }
        scrollToBottom();
    });

    // Bağlantı kesildiğinde
    socket.on('disconnect', () => {
        console.log('Socket.IO Bağlantısı kesildi.');
    });

    // Yeni mesaj geldiğinde
    socket.on('new_message', (data) => {
        if (messagesDiv) {
            const messageElement = document.createElement('div');
            messageElement.classList.add('message');

            // Mesajın benim mi yoksa başkasının mı olduğunu kontrol et
            if (data.user_id === MY_USER_ID) {
                messageElement.classList.add('my-message');
            } else {
                messageElement.classList.add('other-message');
            }

            messageElement.innerHTML = `
                <span class="username">${data.username}:</span>
                <span class="content">${data.content}</span>
                <span class="timestamp">${data.timestamp}</span>
            `;
            messagesDiv.appendChild(messageElement);
            scrollToBottom();
        }
    });

    // Sistem mesajları (oda giriş/çıkışları gibi)
    socket.on('status_message', (data) => {
        if (messagesDiv) {
            const statusElement = document.createElement('div');
            statusElement.classList.add('system-message');
            statusElement.textContent = data.msg;
            messagesDiv.appendChild(statusElement);
            scrollToBottom();
        }
    });

    // Mesaj gönderme fonksiyonu
    const sendMessage = () => {
        if (messageInput && sendMessageButton) {
            const messageContent = messageInput.value.trim();
            if (messageContent && CURRENT_ROOM_ID !== null) {
                socket.emit('message', {
                    room_id: CURRENT_ROOM_ID,
                    msg: messageContent
                });
                messageInput.value = ''; // Mesaj gönderildikten sonra inputu temizle
                messageInput.focus(); // Inputa odaklan
            } else if (CURRENT_ROOM_ID === null) {
                alert("Mesaj göndermek için lütfen bir oda seçin.");
            }
        }
    };

    // Butona tıklayınca mesaj gönder
    if (sendMessageButton) {
        sendMessageButton.addEventListener('click', sendMessage);
    }

    // Enter tuşuna basınca mesaj gönder
    if (messageInput) {
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }

    // Sayfa yüklendiğinde scroll'u en alta indir
    scrollToBottom();
});