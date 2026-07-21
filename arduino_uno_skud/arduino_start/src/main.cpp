#include <Arduino.h>

// Перечисление состояний конечного автомата
enum State {
    STATE_LOCKED,
    STATE_UNLOCKED,
    STATE_BLOCKED
};

class SecuritySystem {
private:
    State currentState;
    const String correctPassword;
    String currentInput;
    int wrongAttempts;
    const int maxAttempts = 3;
    
    unsigned long stateTimer;
    const unsigned long unlockDuration = 5000; // 5 секунд открыто
    const unsigned long blockDuration = 10000; // 10 секунд блокировки при ошибке

    const int ledPin = 13; // Встроенный светодиод на Arduino Uno

public:
    // Конструктор класса
    SecuritySystem(String password) : correctPassword(password) {
        currentState = STATE_LOCKED;
        currentInput = "";
        wrongAttempts = 0;
        stateTimer = 0;
    }

    void init() {
        pinMode(ledPin, OUTPUT);
        digitalWrite(ledPin, LOW);
        Serial.println("=== СИСТЕМА ОХРАНЫ ЗАПУЩЕНА ===");
        Serial.println("Введите пароль в терминал:");
    }

    // Основной цикл обновления состояний (вызывается в loop)
    void update() {
        unsigned long currentMillis = millis();

        switch (currentState) {
            case STATE_LOCKED:
                digitalWrite(ledPin, LOW); // Замок закрыт
                break;

            case STATE_UNLOCKED:
                digitalWrite(ledPin, HIGH); // Замок открыт (светодиод горит)
                if (currentMillis - stateTimer >= unlockDuration) {
                    currentState = STATE_LOCKED;
                    Serial.println("\n[Дверь закрыта]. Система снова заблокирована.");
                }
                break;

            case STATE_BLOCKED:
                // Визуализация тревоги — мигание светодиода без delay
                digitalWrite(ledPin, (currentMillis / 200) % 2); 
                
                if (currentMillis - stateTimer >= blockDuration) {
                    currentState = STATE_LOCKED;
                    wrongAttempts = 0;
                    Serial.println("\n[Система разблокирована]. Попробуйте ввести пароль снова:");
                }
                break;
        }
    }

    // Обработка входящего символа
    void handleInput(char ch) {
        if (currentState == STATE_BLOCKED) {
            Serial.println("Система заблокирована! Подождите.");
            return;
        }
        if (currentState == STATE_UNLOCKED) {
            Serial.println("Дверь уже открыта.");
            return;
        }

        // Если нажали Enter (в зависимости от настроек монитора порта '\n' или '\r')
        if (ch == '\n' || ch == '\r') {
            if (currentInput.length() > 0) {
                checkPassword();
            }
            return;
        }

        // Добавляем символ в буфер и эхо-ответом выводим '*' в консоль для конфиденциальности
        currentInput += ch;
        Serial.print("*");
    }

private:
    void checkPassword() {
        Serial.println(); // Перенос строки после ввода
        
        if (currentInput == correctPassword) {
            Serial.println("[ДОСТУП РАЗРЕШЕН] Светодиод 13 зажжен на 5 секунд.");
            currentState = STATE_UNLOCKED;
            wrongAttempts = 0;
            stateTimer = millis();
        } else {
            wrongAttempts++;
            Serial.print("[ОШИБКА] Неверный пароль. Осталось попыток: ");
            Serial.println(maxAttempts - wrongAttempts);
            
            if (wrongAttempts >= maxAttempts) {
                Serial.println("[ТРЕВОГА!] Превышено число попыток. Блокировка на 10 секунд.");
                currentState = STATE_BLOCKED;
                stateTimer = millis();
            }
        }
        currentInput = ""; // Очищаем буфер ввода
    }
};

// Создаем объект системы с паролем "1234"
SecuritySystem myLock("1234");

void setup() {
    Serial.begin(9600);
    myLock.init();
}

void loop() {
    myLock.update();

    // Читаем данные из последовательного порта ПК
    while (Serial.available() > 0) {
        char incomingChar = Serial.read();
        myLock.handleInput(incomingChar);
    }
}
