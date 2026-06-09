# Auto Support Generator

Короткая инструкция по установке для пользователей без опыта работы с Python и
GitHub: [INSTALL_RU.md](INSTALL_RU.md).

Auto Support Generator - программа для автоматической сборки Supporting
Information (SI) в органической химии.

Идея простая: пользователь заполняет таблицу по веществам, добавляет архив со
спектрами ЯМР, выбирает настройки оформления, а программа собирает готовый
`docx` support information. Программа также сохраняет обработанные спектры,
картинки спектров и `.mnova` файлы для каждого соединения.

## Для чего нужна программа

Обычно SI собирают вручную: копируют структуры из ChemDraw, пишут названия,
переносят ЯМР, вставляют HRMS, форматируют спектры и картинки. Это долго и
легко ошибиться.

Auto Support Generator делает это автоматически:

- переносит структуры как настоящие OLE-объекты ChemDraw/ChemSketch;
- генерирует блоки описания соединений в одном стиле;
- обрабатывает 1H и 13C NMR через MestReNova;
- вставляет описания ЯМР в текст SI;
- экспортирует картинки спектров;
- сохраняет обработанные `.mnova` файлы;
- считает расчетный HRMS по формуле;
- проверяет, совпадают ли экспериментальные данные с формулой вещества.

## Что нужно установить

Полный workflow сейчас рассчитан на Windows, потому что используются Word,
ChemDraw OLE и MestReNova.

Обязательные внешние программы:

| Программа | Для чего нужна | Проверенная версия |
| --- | --- | --- |
| Windows | запуск Word/ChemDraw/MestReNova automation | Windows 10/11 |
| Microsoft Word desktop | создание итогового `.docx` и вставка OLE-структур | Microsoft 365 / Word 2019+ |
| ChemDraw / ChemOffice | хранение и перенос структур как OLE-объектов | ChemDraw 22.2.0.3300 |
| MestReNova | обработка ЯМР, peak picking, экспорт PNG и `.mnova` | MestReNova 14.2.0-26256 |

Важно: ChemDraw и MestReNova должны быть установлены как обычные desktop
программы. Для генерации только из CSV без структур и без спектров можно
запустить часть функций без ChemDraw/MestReNova, но основной сценарий требует
обе программы.

Python пользователю готовой версии не нужен: он уже упакован внутрь
`AutoSupportGenerator.exe`. Python 3.12 нужен только разработчику, если нужно
собрать программу из исходников.

По умолчанию MestReNova ожидается здесь:

```text
C:\Program Files\Mestrelab Research S.L\MestReNova\MestReNova.exe
```

## Как установить готовую версию

Самый простой вариант:

1. Скачайте файл `AutoSupportGeneratorSetup.exe` из GitHub Releases или получите
   его от разработчика.
2. Дважды кликните `AutoSupportGeneratorSetup.exe`.
3. Дождитесь окончания установки.
4. Запустите программу через ярлык `Auto Support Generator` на рабочем столе или
   в меню Пуск.

Установщик кладет программу сюда:

```text
%LOCALAPPDATA%\AutoSupportGenerator
```

В эту же папку копируются:

- `AutoSupportGenerator.exe` - сама программа;
- `style_config.example.yml` - пример настроек оформления;
- `examples/` - примеры входных данных и сгенерированного SI;
- `README.md` и `INSTALL_RU.md` - инструкции.

Чтобы удалить программу, можно удалить папку
`%LOCALAPPDATA%\AutoSupportGenerator` и ярлыки `Auto Support Generator`.

## Как скачать исходники с GitHub

Если вы не знакомы с GitHub:

1. Откройте страницу проекта:

```text
https://github.com/danilalebedev/Auto_support_generator
```

2. Нажмите зеленую кнопку `Code`.
3. Выберите `Download ZIP`.
4. Распакуйте архив, например на рабочий стол.
5. Откройте распакованную папку `Auto_support_generator`.

Этот способ нужен только для разработки или пересборки установщика. После
распаковки в папке должны быть файлы:

```text
Setup Auto SI Generator.bat
Run Auto SI Generator.bat
Build Auto Support Generator Installer.bat
README.md
pyproject.toml
src/
scripts/
examples/
```

## Как запустить из исходников

Если готового `AutoSupportGeneratorSetup.exe` нет, программу можно запустить из
исходников:

1. Откройте папку проекта.
2. Дважды кликните `Setup Auto SI Generator.bat`.
3. После успешной установки дважды кликните:

```text
Run Auto SI Generator.bat
```

Этот путь требует Python 3.12. Батник пытается найти Python автоматически, даже
если `python` не добавлен в `PATH`.

## Как пользоваться GUI

В окне программы:

1. В `Table type` выберите тип таблицы:
   - `Word table with ChemDraw objects` - основной вариант, если в таблице есть
     структуры ChemDraw/ChemSketch;
   - `CSV table` - простой вариант без OLE-структур.
2. В `Compound table` выберите таблицу с веществами.
3. В `Spectra zip` выберите zip-архив со спектрами.
4. В `Template .docx` можно выбрать Word-шаблон оформления. Это необязательно.
5. В `Style config .yml` можно выбрать файл настроек оформления. Это
   необязательно.
6. В `Output .docx` выберите, куда сохранить готовый support.
7. Оставьте `Check support` включенным, если хотите проверять ЯМР и HRMS.
8. Нажмите `Generate SI`.

В нижнем окне будет лог выполнения. После завершения нажмите `Open output
folder`, чтобы открыть папку с результатами.

## Что получается на выходе

Если выбран output:

```text
output/support_information.docx
```

то рядом создается структура:

```text
output/
  support_information.docx
  processed_spectra.zip
  processed_spectra/
    2a/
      2a_1H.png
      2a_13C.png
      2a.mnova
  processed_mnova/
    2a/
      2a.mnova
  mnova_reports/
    2a/
      2a_1H.txt
      2a_13C.txt
  logs/
```

Главные файлы для пользователя:

- `support_information.docx` - готовый SI;
- `processed_spectra.zip` - архив с обработанными спектрами, PNG-картинками и
  `.mnova` файлами;
- `processed_spectra/` - то же самое, но в виде обычных папок.

`logs/` - служебные файлы. Они нужны для отладки, но обычно пользователю их
трогать не нужно.

## Примеры

В папке `examples/` есть пример CSV-входа:

```text
examples/sample_compounds.csv
```

После установки зависимостей можно сгенерировать пример support без спектров:

```powershell
py -m si_generator ^
  --input examples\sample_compounds.csv ^
  --style-config style_config.example.yml ^
  --no-check-support ^
  --output examples\generated_support_example.docx
```

Файл `examples/generated_support_example.docx` - пример результата. Он показывает
формат описания соединений, HRMS, IR и ручные ЯМР-описания. В реальном workflow
ЯМР-описания и картинки спектров можно генерировать автоматически из
MestReNova/Bruker spectra zip. В этой демонстрационной команде проверка
отключена, чтобы пример выглядел как чистовой документ без диагностических
пометок.

## Формат Word-таблицы

Основной вариант ввода - Word-файл с таблицей.

Первая строка таблицы - заголовки. Каждая следующая строка - одно соединение.
В первой колонке должен быть номер соединения и OLE-структура ChemDraw или
ChemSketch. Программа копирует эту структуру в итоговый SI как настоящий OLE
объект.

Полезные колонки:

| Колонка | Что писать |
| --- | --- |
| `number` | номер соединения, например `2a` |
| `name` | название вещества |
| `preparation` | текст получения вещества |
| `yield` | выход, например `492 mg (31%)` |
| `color` | цвет, например `white` |
| `state` | состояние, например `solid` или `oil` |
| `melting_point` | температура плавления без `mp`, например `81-82 °C` |
| `rf` | TLC/Rf строка |
| `formula` | нейтральная молекулярная формула |
| `hrms_adduct` | аддукт, например `[M+H]+` |
| `hrms_found` | экспериментальный HRMS |
| `h1_nmr` | ручное описание 1H NMR, если нет spectra zip |
| `c13_nmr` | ручное описание 13C NMR, если нет spectra zip |
| `extra_nmr` | дополнительные спектры, например 19F NMR |
| `ir` | IR строка |

Если подключен zip со спектрами, `h1_nmr` и `c13_nmr` можно не заполнять:
программа попробует получить их из MestReNova.

## Формат spectra zip

Архив со спектрами должен содержать папки с номерами соединений:

```text
spectra.zip
  2a/
    any_name_1H/
      fid
      acqus
      ...
    any_name_13C/
      fid
      acqus
      ...
  2b/
    ...
```

Названия внутренних папок могут отличаться. Программа ищет Bruker `fid` файлы и
читает `acqus`/`acqu`, чтобы понять, где 1H, а где 13C.

## Как обрабатываются спектры

MestReNova запускается автоматически.

Сейчас программа делает следующее:

- открывает все спектры в одной сессии MestReNova;
- калибрует 1H по растворителю:
  - CDCl3: 7.26 ppm;
  - DMSO-d6: 2.50 ppm;
- калибрует 13C по растворителю:
  - CDCl3: 77.16 ppm;
  - DMSO-d6: 39.52 ppm;
- для 13C делает baseline correction перед финальным peak picking;
- для 1H экспортирует картинку в диапазоне от -1 до 12 ppm;
- для 13C экспортирует картинку в диапазоне от -10 до 210 ppm;
- для 1H оставляет интегралы снизу и убирает лишнюю верхнюю integral curve;
- для 13C оставляет только peak picking без интегралов и мультиплетов;
- сохраняет один `.mnova` файл на соединение, где лежат обработанные 1H и 13C.

## Как работает проверка экспериментальных данных

Проверка включается чекбоксом `Check support`.

Она нужна, чтобы быстро заметить типичные ошибки:

- в 1H NMR потеряли или добавили лишний интеграл;
- в 13C NMR не все атомы углерода попали в описание;
- HRMS не совпадает с расчетной массой.

Что именно проверяется:

1. Формула вещества разбирается на количество H и C.
2. В 1H NMR программа ищет интегралы вида `1H`, `2H`, `3H` и суммирует их.
3. В 13C NMR программа считает количество сигналов или назначений углерода.
4. Для HRMS программа считает массу по `formula` и `hrms_adduct`, например
   `[M+H]+`, и сравнивает с `hrms_found`.
5. Если есть расхождение, в итоговом SI добавляется красная пометка
   `Support check`.

Важно: проверка не заменяет ручную проверку химика. Это быстрый автоматический
контроль, который помогает найти подозрительные места.

## Настройка оформления

Есть два уровня оформления.

### Word template

В GUI можно выбрать `Template .docx`.

Из него берутся:

- поля страницы;
- размер страницы;
- стандартный шрифт;
- Word-стили.

Тело шаблона очищается, а внутрь вставляется новый SI.

### style_config.yml

Файл `style_config.yml` управляет смысловым форматированием:

- какие элементы жирные;
- какие элементы курсивные;
- делать ли `1H`, `13C` верхними индексами;
- делать ли цифры в формулах нижними индексами;
- делать ли `J` в константах курсивным;
- насколько опустить структуру под названием.

Начните с примера:

```text
style_config.example.yml
```

Пример важной настройки:

```yaml
chem_formatting:
  coupling_constants:
    j_italic: true
```

Она делает символ `J` в константах спин-спинового взаимодействия курсивным.

## CLI для продвинутых пользователей

Если программа установлена через `AutoSupportGeneratorSetup.exe`, CLI можно
запускать через установленный exe:

```powershell
%LOCALAPPDATA%\AutoSupportGenerator\AutoSupportGenerator.exe --input examples\sample_compounds.csv --output output\support_information.docx
```

Если программа запущена из исходников, используйте `py -m si_generator`.

Основной Word workflow из исходников:

```powershell
py -m si_generator ^
  --word-input C:\path\to\input.docx ^
  --spectra-zip C:\path\to\spectra.zip ^
  --style-config style_config.example.yml ^
  --output output\support_information.docx
```

CSV workflow:

```powershell
py -m si_generator ^
  --input examples\sample_compounds.csv ^
  --output output\support_information.docx
```

Отключить проверку:

```powershell
py -m si_generator ^
  --word-input C:\path\to\input.docx ^
  --spectra-zip C:\path\to\spectra.zip ^
  --no-check-support ^
  --output output\support_information.docx
```

Запуск GUI из командной строки:

```powershell
py -m si_generator.gui
```

## Как собрать установщик

Сборка установщика нужна разработчику, который хочет получить один файл
`AutoSupportGeneratorSetup.exe`.

1. Установите Python 3.12.
2. Запустите `Setup Auto SI Generator.bat`.
3. Запустите `Build Auto Support Generator Installer.bat`.
4. Готовые файлы появятся в папке `dist/`:

```text
dist/AutoSupportGenerator.exe
dist/AutoSupportGeneratorSetup.exe
```

Сборка использует PyInstaller: сначала он упаковывает GUI в
`AutoSupportGenerator.exe`, затем упаковывает установщик
`AutoSupportGeneratorSetup.exe` с программой, примерами и инструкциями внутри.

## Что не нужно добавлять в GitHub

Не нужно загружать в репозиторий:

- папку `output/`;
- временные файлы MestReNova;
- распакованные спектры;
- рабочие `.mnova` batch-файлы;
- `__pycache__/`.

Эти файлы уже добавлены в `.gitignore`.
