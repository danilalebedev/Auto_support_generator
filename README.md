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

MestReNova не привязана к одному пути. Программа ищет `MestReNova.exe` через
поле `MestReNova .exe` в GUI, переменные окружения `AUTO_SUPPORT_MNOVA_EXE`,
`AUTO_SI_MNOVA_EXE`, `MNOVA_EXE` или `MESTRENOVA_EXE`, системный `PATH`,
реестр Windows и типовые папки `Program Files`.

Пути с кириллицей в имени пользователя поддерживаются. Для MestReNova и
ChemDraw программа временно копирует рабочие файлы в ASCII-папку
`C:\Users\Public\AutoSupportGenerator\temp`, потому что эти программы могут
некорректно читать Unicode-пути через свои script/COM-интерфейсы. Если на
компьютере эта папка недоступна, можно задать другую ASCII-папку через
переменную окружения `AUTO_SUPPORT_TEMP_DIR`.

## Как установить готовую версию

Самый простой вариант:

1. Скачайте файл `installer/AutoSupportGeneratorSetup.exe` из репозитория.
   На GitHub откройте папку `installer`, выберите `AutoSupportGeneratorSetup.exe`
   и нажмите `Download raw file`.
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

## Что программа получает на входе

Минимальный вход для основного workflow состоит из двух файлов:

```text
compound_table.docx
spectra.zip
```

`compound_table.docx` - Word-файл с таблицей соединений. В первой строке таблицы
должны быть заголовки колонок, каждая следующая строка описывает одно
соединение. В первой колонке обычно находится номер соединения и структура,
вставленная как OLE-объект ChemDraw или ChemSketch.

`spectra.zip` - zip-архив со спектрами ЯМР. Внутри архива должны быть папки с
номерами соединений. Названия папок должны совпадать с номерами в таблице:

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

Дополнительные входные файлы необязательны:

- `Template .docx` - Word-шаблон, из которого берутся поля страницы, шрифты,
  интервалы и стили;
- `Style config .yml` - настройки смыслового форматирования, например какие
  элементы делать жирными или курсивными;
- `References .yml` - необязательная библиография, если в SI нужно добавить
  список литературы по ключам из таблицы;
- CSV-таблица - упрощенный вариант вместо Word-таблицы, если OLE-структуры не
  нужны.

Если колонка `name` в таблице пустая, программа пытается получить
номенклатурное название напрямую через ChemDraw. Для этого структура извлекается
из OLE-объекта как CDX и открывается через `ChemDraw.Application`, поэтому
системная ассоциация OLE с другими программами не должна мешать.

## Что программа создает на выходе

Главный результат - готовый Word-файл Supporting Information:

```text
support_information.docx
```

В него вставляются:

- названия и номера соединений;
- структуры как OLE-объекты ChemDraw/ChemSketch;
- физические свойства, Rf, выход, температура плавления;
- описания 1H и 13C NMR;
- HRMS с расчетной массой по формуле;
- IR и дополнительные ЯМР, если они есть;
- список литературы, если передан `References .yml`;
- картинки спектров в конце SI.

Рядом с итоговым `.docx` создаются дополнительные папки и архив:

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

Для пользователя обычно важны:

- `support_information.docx` - финальный SI;
- `processed_spectra.zip` - архив с PNG-картинками спектров и обработанными
  `.mnova` файлами;
- `processed_spectra/` - те же файлы в обычных папках.

`logs/`, `mnova_reports/` и `processed_mnova/` нужны в основном для проверки и
отладки.

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
6. В `References .yml` можно выбрать файл со списком литературы. Это
   необязательно.
7. В `MestReNova .exe` можно вручную указать путь к MestReNova, если программа
   не нашла ее автоматически. Это необязательно.
8. В `Output .docx` выберите, куда сохранить готовый support.
9. Оставьте `Check support` включенным, если хотите проверять ЯМР и HRMS.
10. Нажмите `Generate SI`.

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

В папке `examples/` лежит один полный демонстрационный набор: входные данные,
архив со спектрами и пример результата. Его можно использовать, чтобы быстро
проверить GUI и понять, какой формат файлов ожидает программа.

```text
examples/test_input.docx
examples/test_input.zip
examples/references.example.yml
examples/example_output/support_information.docx
examples/example_output/processed_spectra.zip
```

Что это за файлы:

- `test_input.docx` - входная Word-таблица с соединениями `2a-2f`,
  физическими свойствами, HRMS и OLE-структурами ChemDraw/ChemSketch;
- `test_input.zip` - входной архив со спектрами для тех же соединений; внутри
  лежат папки `2a`, `2b`, ..., `2f`, а в них Bruker-эксперименты 1H и 13C;
- `references.example.yml` - пример необязательного файла библиографии;
- `example_output/support_information.docx` - пример готового SI, который
  должен получиться после обработки этих входных файлов;
- `example_output/processed_spectra.zip` - пример архива с обработанными
  спектрами: PNG-картинки 1H/13C и `.mnova` файл для каждого соединения.

В GUI для этого примера выберите:

- `Table type`: `Word table with ChemDraw objects`;
- `Compound table`: `examples/test_input.docx`;
- `Spectra zip`: `examples/test_input.zip`;
- `Output .docx`: любой удобный путь, например `output/support_information.docx`.

После запуска программа должна создать рядом с выбранным output-файлом готовый
`support_information.docx`, `processed_spectra.zip` и служебные папки
`logs/`, `mnova_reports/`, `processed_mnova/`, `processed_spectra/`.

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
| `elemental_analysis` | найденные значения, например `C, 66.03; H, 3.55; N, 8.92` |
| `references` | ключи ссылок через запятую или `;`, например `ref1; ref2` |

Если подключен zip со спектрами, `h1_nmr` и `c13_nmr` можно не заполнять:
программа попробует получить их из MestReNova.

Критически важен номер соединения: он связывает строку таблицы с папкой спектров
в zip-архиве. Если номер пустой или повторяется, генерация останавливается с
понятной ошибкой. Остальные поля можно заполнять постепенно: если отсутствуют
HRMS, ЯМР, formula, mp или appearance, программа выводит предупреждение в лог и
пропускает соответствующую строку/проверку.

## Формат references.yml

Файл ссылок необязателен. Он нужен, если в конце SI должен появиться раздел
`References`. В таблице соединений укажите ключи в колонке `references`,
`refs` или `reference_keys`, а в YAML-файле опишите сами ссылки:

```yaml
references:
  data_automation:
    authors: [Smith J., Ivanova O. A.]
    title: Automation of chemical data workflows
    journal: J. Chem. Inf. Model.
    year: 2025
    volume: 65
    pages: 1-10
    doi: 10.0000/example
order: [data_automation]
```

Если соединение ссылается на ключ, которого нет в файле, программа не
останавливает генерацию, но пишет предупреждение в лог. Если в таблице ключи не
указаны, но `References .yml` выбран, в библиографию попадут все ссылки из
`order`.

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
- элементный анализ не совпадает с расчетом по формуле.

Что именно проверяется:

1. Формула вещества разбирается на количество H и C.
2. В 1H NMR программа ищет интегралы вида `1H`, `2H`, `3H` и суммирует их.
3. В 13C NMR программа считает количество сигналов или назначений углерода.
4. Для HRMS программа считает массу по `formula` и `hrms_adduct`, например
   `[M+H]+`, и сравнивает с `hrms_found`.
5. Для соединений с Br/Cl программа автоматически отмечает моноизотопные
   формулы как `79Br` или `35Cl` в строке HRMS.
6. Для elemental analysis программа считает теоретические проценты C/H/N по
   `formula` и сравнивает с найденными значениями.
7. Если есть расхождение, в итоговом SI добавляется красная пометка
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

### journal_profile.yml

Journal profile управляет общим форматом SI: порядком секций, названием профиля,
путем к Word-шаблону и будущими правилами для ссылок/NMR/HRMS. Сейчас доступны
встроенные профили:

```text
default
acs
rsc
wiley
```

Профиль можно выбрать по имени или передать путь к своему YAML:

```powershell
py -m si_generator ^
  --word-input C:\path\to\input.docx ^
  --journal-profile acs ^
  --output output\support_information.docx
```

## CLI для продвинутых пользователей

Если программа установлена через `AutoSupportGeneratorSetup.exe`, CLI можно
запускать через установленный exe:

```powershell
%LOCALAPPDATA%\AutoSupportGenerator\AutoSupportGenerator.exe --word-input examples\test_input.docx --spectra-zip examples\test_input.zip --output output\support_information.docx
```

Если программа запущена из исходников, используйте `py -m si_generator`.

Основной Word workflow из исходников:

```powershell
py -m si_generator ^
  --word-input C:\path\to\input.docx ^
  --spectra-zip C:\path\to\spectra.zip ^
  --mnova-exe "C:\Program Files\Mestrelab Research S.L\MestReNova\MestReNova.exe" ^
  --insert-spectra-as png ^
  --style-config style_config.example.yml ^
  --references references.yml ^
  --output output\support_information.docx
```

Параметр `--insert-spectra-as` управляет приложением спектров в конце SI:
`png` вставляет изображения спектров, `mnova` добавляет placeholders для будущей вставки Mnova-объектов,
`both` оставляет оба представления, `none` не добавляет спектральный appendix. В GUI это поле называется
`Spectra appendix`.

CSV workflow:

```powershell
py -m si_generator ^
  --input C:\path\to\compounds.csv ^
  --output output\support_information.docx
```

Проверить уже сгенерированный output и его `support_information.manifest.json`:

```powershell
py -m si_generator ^
  --check-manifest output\support_information.manifest.json
```

Этот режим не пересобирает SI. Он проверяет структуру manifest, наличие финального `.docx`,
соответствие списка соединений и доступность перечисленных артефактов. Если нужно проверить
только manifest и итоговый документ, без строгой проверки всех PNG/MNova файлов, добавьте
`--no-strict-artifacts`.

Отключить проверку:

```powershell
py -m si_generator ^
  --word-input C:\path\to\input.docx ^
  --spectra-zip C:\path\to\spectra.zip ^
  --journal-profile acs ^
  --no-check-support ^
  --output output\support_information.docx
```

Запуск GUI из командной строки:

```powershell
py -m si_generator.gui
```

## Автотесты для разработки

Перед изменениями в ядре генератора удобно запускать smoke/regression tests:

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Тесты покрывают расчет HRMS, проверку ЯМР, чтение текущего Word-примера,
smoke-генерацию `.docx` без запуска MestReNova, LangGraph request/state,
маршрутизацию генерации SI, расчет HRMS перед render-этапом и запись
`support_information.manifest.json`, а также планирование NMR render spec для
экспорта спектров. Отдельно проверяется промежуточная модель SI-документа
перед записью `.docx`; GUI также проверяется как thin wrapper вокруг graph workflow.
NMR-строки теперь дополнительно разбираются в структурированный список сигналов,
а политика peak picking применяется отдельной graph node.
Новая архитектурная основа лежит в:

```text
src/si_generator/domain/
src/si_generator/graph/
src/si_generator/render/
src/si_generator/workflows/
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
