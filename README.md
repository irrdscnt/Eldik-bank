#  Eldik Taxi

Этот проект — backend-приложение на Django с использованием MongoEngine и Django REST Framework. Также используется WebSocket (Django Channels) для работы в реальном времени (например, отслеживание локации).

##  Установка

### 1. Клонирование проекта

```bash
git clone https://github.com/irrdscnt/Eldik-bank.git
cd Eldik-bank
```
Создание виртуального окружения
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# или
.venv\Scripts\activate  # Windows
```
Установка зависимостей
```bash
pip install -r requirements.txt
```
Для запуска 
```bash
daphne car_rental_bank.asgi:application
```
