#!/bin/bash

# Скрипт установки зависимостей для пайплайна

echo "Установка зависимостей для пайплайна извлечения информации..."

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "Ошибка: Python3 не найден. Установите Python 3.8 или выше."
    exit 1
fi

echo "Python версия: $(python3 --version)"

# Создаем виртуальное окружение (опционально)
read -p "Создать виртуальное окружение? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Виртуальное окружение активировано"
fi

# Устанавливаем зависимости
echo "Установка зависимостей из requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

# Устанавливаем русскую модель для SpaCy (если используется)
echo ""
read -p "Установить русскую модель для SpaCy (ru_core_news_md)? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 -m spacy download ru_core_news_md
fi

echo ""
echo "Установка завершена!"
echo ""
echo "Для активации виртуального окружения (если создавали):"
echo "  source venv/bin/activate"
echo ""
echo "Для запуска тестов:"
echo "  python3 test_pipeline.py"
echo ""
echo "Для обработки документов:"
echo "  python3 main.py"
