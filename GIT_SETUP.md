# Инструкция по публикации в Git

## Текущий статус

✅ Git репозиторий инициализирован
✅ Все файлы добавлены в коммит
✅ .gitignore настроен (исключает venv, output, кэш)

## Публикация на GitHub/GitLab

### Вариант 1: GitHub

1. Создайте новый репозиторий на GitHub:
   - Перейдите на https://github.com/new
   - Название: например, `vdnh-document-pipeline` или `russian-document-ner`
   - Выберите Public или Private
   - НЕ создавайте README, .gitignore или лицензию (у нас уже есть)

2. Подключите удаленный репозиторий:
```bash
git remote add origin https://github.com/ВАШ_USERNAME/НАЗВАНИЕ_РЕПО.git
```

3. Переименуйте ветку в main (если нужно):
```bash
git branch -M main
```

4. Загрузите код:
```bash
git push -u origin main
```

### Вариант 2: GitLab

1. Создайте новый проект на GitLab
2. Подключите удаленный репозиторий:
```bash
git remote add origin https://gitlab.com/ВАШ_USERNAME/НАЗВАНИЕ_ПРОЕКТА.git
git push -u origin main
```

### Вариант 3: Другой Git хостинг

Аналогично, создайте репозиторий и выполните:
```bash
git remote add origin URL_ВАШЕГО_РЕПОЗИТОРИЯ
git push -u origin main
```

## Что НЕ включено в репозиторий

Следующие файлы/папки исключены через .gitignore:
- `venv/` - виртуальное окружение (каждый должен создать свое)
- `output/` - результаты обработки
- `__pycache__/` - кэш Python
- `*.json` - результаты (кроме requirements.txt)
- `.DS_Store` - системные файлы Mac

## Что включено

✅ Все исходные файлы Python
✅ requirements.txt
✅ Документация (README, QUICKSTART, etc.)
✅ business_processes.txt
✅ config.py
✅ Скрипты установки

## Вопрос про validate_data/

Папка `validate_data/` с тестовыми документами **НЕ добавлена** в репозиторий по умолчанию, так как:
- Может содержать конфиденциальные данные
- Файлы могут быть большими

Если хотите добавить тестовые данные (без конфиденциальной информации):
```bash
git add validate_data/
git commit -m "Add test documents"
git push
```

Или создайте отдельную папку с примерами:
```bash
mkdir examples
# Скопируйте несколько примеров документов
git add examples/
git commit -m "Add example documents"
```

## Быстрая команда для публикации

Если у вас уже есть репозиторий на GitHub:

```bash
# Замените URL на ваш
git remote add origin https://github.com/ВАШ_USERNAME/РЕПОЗИТОРИЙ.git
git branch -M main
git push -u origin main
```

## Для других разработчиков

После клонирования репозитория:

```bash
git clone https://github.com/ВАШ_USERNAME/РЕПОЗИТОРИЙ.git
cd РЕПОЗИТОРИЙ
python3 -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows
pip install -r requirements.txt
python -m spacy download ru_core_news_md  # опционально
python test_pipeline.py
```

## Текущие коммиты

Проверить историю:
```bash
git log --oneline
```

Проверить статус:
```bash
git status
```
