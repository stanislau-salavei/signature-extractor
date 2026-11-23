[English](README.md) | **Русский**

<p align="center">
  <img src="docs/images/icon.png" width="96" height="96" alt="Значок программы «Извлечение подписи»">
</p>

<h1 align="center">Извлечение подписи</h1>

<p align="center">Превращает фото или скан подписи в чистый файл PNG, SVG или DXF без фона.</p>

<p align="center">
  <a href="https://github.com/stanislau-salavei/signature-extractor/releases/latest"><img src="https://img.shields.io/github/v/release/stanislau-salavei/signature-extractor?label=release" alt="Последняя версия"></a>
  <a href="https://github.com/stanislau-salavei/signature-extractor/releases"><img src="https://img.shields.io/github/downloads/stanislau-salavei/signature-extractor/total" alt="Скачивания"></a>
  <a href="https://github.com/stanislau-salavei/signature-extractor/actions/workflows/build-installer.yml"><img src="https://img.shields.io/github/actions/workflow/status/stanislau-salavei/signature-extractor/build-installer.yml?branch=main&label=build" alt="Сборка"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPLv3-blue" alt="Лицензия: GPLv3"></a>
  <img src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D4" alt="Платформа: Windows 10 | 11">
</p>

<p align="center">
  <a href="https://github.com/stanislau-salavei/signature-extractor/releases/latest"><img src="https://img.shields.io/badge/%D0%A1%D0%BA%D0%B0%D1%87%D0%B0%D1%82%D1%8C_%D0%B4%D0%BB%D1%8F_Windows-005FB8?style=for-the-badge&logo=windows&logoColor=white" alt="Скачать для Windows" height="40"></a>
</p>

<p align="center"><img src="docs/images/process_ru.png" alt="Экран обработки: слева фото, справа подпись на прозрачном фоне"></p>

## Как пользоваться

1. **Загрузка.** Перетащите фото или папку в окно, нажмите «Открыть файл» или вставьте изображение из буфера обмена (Ctrl+V). Поддерживаются JPG, PNG, BMP, TIFF, WebP и HEIC, до 50 МБ.
2. **Обработка.** Программа отделит подпись от фона, теней, линовки и постороннего текста. При необходимости поправьте рамку, сотрите лишнее ластиком или настройте фильтры.
3. **Экспорт.** Выберите форматы, цвет и размер подписи и сохраните файлы.

| 1. Загрузка | 2. Обработка | 3. Экспорт |
|:---:|:---:|:---:|
| <img src="docs/images/import_ru.png" alt="Экран загрузки"> | <img src="docs/images/process_ru.png" alt="Экран обработки"> | <img src="docs/images/export_ru.png" alt="Экран экспорта"> |

Можно обработать сразу много фото: выберите несколько файлов или целую папку. Светлая и тёмная тема берутся из настроек Windows или задаются в параметрах.

<details>
<summary>Тёмная тема</summary>
<p><img src="docs/images/dark_ru.png" alt="Экран обработки в тёмной теме"></p>
</details>

## Форматы

| Формат | Что получится | Для чего |
|---|---|---|
| **PNG** | Растровое изображение с прозрачным фоном, 300, 600 или 1200 DPI (по умолчанию 1200) | Word, Excel, PDF, сканы, электронные письма |
| **SVG** | Вектор, остаётся чётким при любом масштабе; размер записан в миллиметрах; штрихи «Как в оригинале» или «Заданная толщина» (по умолчанию 0,18 мм) | Inkscape, CorelDRAW, Illustrator, Word 2016 и новее, веб |
| **DXF** | Линии заданной толщины, единицы — миллиметры | AutoCAD, КОМПАС-3D, nanoCAD, BricsCAD и другие программы, которые читают DXF |

- **Размер:** «Как в исходнике», **15 × 5 мм** (графа подписи в штампе чертежа, по умолчанию) или свой размер в миллиметрах, который можно сохранить как шаблон.
- **Цвет:** «Как на фото», «Чёрный», «Синий», «Чернильный синий», «Яркий синий» или свой цвет.

## Системные требования

- Windows 10 версии 1809 или новее либо Windows 11, 64-bit.
- Права администратора не нужны: программа ставится только для вашей учётной записи, в `%LOCALAPPDATA%\Programs\Signature Extractor`.
- Установщик — около 46 МБ.

## Вопросы и ответы

**Windows пишет «Система Windows защитила ваш компьютер». Это нормально?**
Да. Установщик не подписан цифровой подписью, поэтому фильтр SmartScreen может предупредить о нём. Нажмите «Подробнее» → «Выполнить в любом случае». К каждой версии приложена контрольная сумма SHA-256 установщика (в файле `.sha256` и в заметках к выпуску), по ней можно проверить скачанный файл.

**Программа куда-нибудь отправляет мои подписи?**
Нет. Все фото обрабатываются на вашем компьютере. Программа ничего не отправляет в интернет. Сеть нужна только для обновлений.

**Как работают обновления?**
Если в параметрах включено «Проверять обновления при запуске» (включено по умолчанию, проверка не чаще раза в день) или вы нажали «Проверить сейчас», программа ищет новую версию здесь, на GitHub. Нажмите «Скачать»: программа скачает установщик, проверит его контрольную сумму SHA-256 и установит обновление. Настройки сохраняются.

**Как сообщить о проблеме?**
В программе: ⋯ › «Параметры» › «Сообщить о проблеме». Откроется новый issue на GitHub, в котором уже указаны версия программы, версия Windows и язык. Можно и самостоятельно [создать issue](https://github.com/stanislau-salavei/signature-extractor/issues). Не прикладывайте фото настоящих подписей: всё, что там публикуется, видно всем.

## Сборка из исходников

Нужен Python 3.12 (эта версия используется в CI).

```bash
pip install -r requirements.txt
python main.py
```

Тесты (тесты, которым нужны личные фото, без них пропускаются):

```bash
pip install -r requirements-dev.txt
python -m pytest -q tests
```

Установщик (Windows x64, Inno Setup 6.6 или новее):

```bash
pip install -r requirements.txt -r packaging/requirements-build.txt -c packaging/constraints-win.txt
python packaging/build.py
```

Получится `dist/SignatureExtractor-<версия>-setup.exe` и файл `.sha256`. GitHub Actions делает то же самое в [`build-installer.yml`](.github/workflows/build-installer.yml).

## Лицензия

[GNU General Public License v3.0](LICENSE). © 2026 Stanislau Salavei
