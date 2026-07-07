# Auto Support Generator

Auto Support Generator - Windows-программа для автоматической сборки и проверки
Supporting Information (SI) в органической химии.

Программа берет таблицу с соединениями, структуры ChemDraw, raw-спектры ЯМР,
HRMS/IR/elemental analysis/физические свойства и собирает готовый
`support_information.docx` в заданном оформлении. Дополнительно сохраняются
картинки спектров, обработанные `.mnova` файлы, отчеты проверки и служебные
логи.

Короткая инструкция по установке для пользователей без опыта работы с Python и
GitHub находится в [INSTALL_RU.md](INSTALL_RU.md).

## Быстрый старт

1. Установите Microsoft Word, ChemDraw и MestReNova.
2. Скачайте и запустите `installer/AutoSupportGeneratorSetup.exe`.
3. Откройте ярлык `Auto Support Generator`.
4. Нажмите `Load example`, чтобы подставить пример входных данных.
5. Нажмите `Generate SI`.
6. После окончания нажмите `Open output folder` или `Open last output`.
7. Откройте `docx/support_information.docx`.

Для своего проекта обычно нужно заполнить только три поля на вкладке
`Generate`:

| Поле | Что выбрать |
| --- | --- |
| `Compound table` | Word-таблицу `.docx` с соединениями и структурами ChemDraw |
| `Spectra source` | zip-архив или папку с raw-спектрами |
| `Output folder` | папку, куда сохранить результат |

Остальные параметры можно оставить по умолчанию.

## Что программа умеет

Основные функции:

- генерирует текстовые блоки описания соединений;
- копирует структуры из Word-таблицы как OLE-объекты ChemDraw/ChemSketch;
- получает номенклатурные названия из ChemDraw, если поле `name` пустое;
- обрабатывает 1H и 13C NMR через MestReNova;
- калибрует спектры по растворителю;
- извлекает текстовое описание ЯМР из MestReNova;
- экспортирует картинки спектров в PNG;
- сохраняет обработанные `.mnova` файлы;
- вставляет спектры в SI как PNG или как кликабельные Mnova OLE-объекты;
- считает расчетный HRMS по молекулярной формуле;
- форматирует HRMS, NMR, IR, elemental analysis и физические свойства;
- считает и вставляет расчетный elemental analysis;
- проверяет соответствие NMR/HRMS/elemental analysis формуле вещества;
- добавляет предупреждения в отчет и в SI, если данные не сходятся;
- создает отдельную output-папку для каждого запуска;
- позволяет проверить уже созданный SI;
- позволяет перенумеровать, удалить или переставить блоки в существующем SI;
- позволяет добавить новые соединения к старому SI.

## Требования

Полный workflow рассчитан на Windows, потому что используются Microsoft Word,
ChemDraw OLE и MestReNova automation.

| Программа | Для чего нужна | Проверенная версия |
| --- | --- | --- |
| Windows | запуск GUI и COM/OLE automation | Windows 10/11 |
| Microsoft Word desktop | создание `.docx`, вставка OLE-объектов | Microsoft 365 / Word 2019+ |
| ChemDraw / ChemOffice | структуры и генерация названий | ChemDraw 22.2.0.3300 |
| MestReNova | обработка и экспорт ЯМР | MestReNova 14.2.0-26256 |

Python пользователю готовой версии не нужен: он упакован внутрь
`AutoSupportGenerator.exe`. Python нужен только разработчику, если запускать
проект из исходников или собирать установщик.

### Важные замечания по внешним программам

- ChemDraw должен быть установлен как desktop-приложение и уметь открывать CDX
  через OLE/COM.
- MestReNova должна запускаться на этой машине хотя бы один раз вручную, чтобы
  лицензия и начальные настройки были активированы.
- Если MestReNova не найдена автоматически, укажите путь к `MestReNova.exe` в
  GUI на вкладке `Advanced`.
- Пути с кириллицей поддерживаются. Для ChemDraw/MestReNova программа временно
  копирует рабочие файлы в ASCII-папку
  `C:\Users\Public\AutoSupportGenerator\temp`, потому что внешние программы не
  всегда корректно работают с Unicode-путями.

## Установка готовой версии

Самый простой способ:

1. Откройте репозиторий:

```text
https://github.com/danilalebedev/Auto_support_generator
```

2. Откройте папку `installer`.
3. Скачайте `AutoSupportGeneratorSetup.exe`.
4. Запустите скачанный файл двойным кликом.
5. После установки запустите `Auto Support Generator` с рабочего стола или из
   меню Пуск.

Установщик копирует программу в:

```text
%LOCALAPPDATA%\AutoSupportGenerator
```

Туда же кладутся примеры, README и дополнительные файлы.

## Запуск из исходников

Этот вариант нужен разработчику или пользователю, который скачал проект как ZIP
и хочет запустить его без установщика.

1. Установите Python 3.12.
2. Скачайте проект с GitHub через `Code -> Download ZIP`.
3. Распакуйте архив.
4. Запустите `Setup Auto SI Generator.bat`.
5. После установки зависимостей запустите `Run Auto SI Generator.bat`.

## Главный сценарий работы

### 1. Подготовьте таблицу соединений

Обычно это Word-файл `.docx` с таблицей. Первая строка - заголовки колонок,
каждая следующая строка - одно соединение.

В первой колонке обычно находятся:

- номер соединения, например `2a`;
- структура, вставленная как OLE-объект ChemDraw или ChemSketch.

Если структура вставлена как обычная картинка, программа не сможет перенести ее
как редактируемый ChemDraw-объект.

### 2. Подготовьте спектры

Спектры можно передать как zip-архив или как обычную папку. Внутри должны быть
папки с номерами соединений:

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

Номер папки должен совпадать с номером соединения в таблице. Названия
экспериментов внутри папки могут быть любыми: программа ищет Bruker-файл `fid`
и читает `acqus`/`acqu`, чтобы понять, где 1H, а где 13C.

### 3. Запустите GUI

На вкладке `Generate` выберите:

- `Compound table`;
- `Spectra source`;
- `Output folder`.

После этого нажмите `Generate SI`.

### 4. Проверьте результат

После окончания откройте:

```text
output/runs/<дата>_<input_name>/docx/support_information.docx
```

Если есть warnings, откройте `Open report` или папку `logs`.

## GUI: вкладка Generate

Вкладка `Generate` - основной режим генерации нового SI.

### Simple

| Поле | Что означает | Когда заполнять |
| --- | --- | --- |
| `Compound table` | Word `.docx` или CSV с данными по соединениям | всегда |
| `Spectra source` | zip-архив или папка с raw-спектрами | если нужно автоматически обработать ЯМР |
| `Output folder` | папка для результатов | всегда |

Кнопки рядом со `Spectra source`:

- `Zip...` - выбрать zip-архив;
- `Folder...` - выбрать обычную папку со спектрами.

### Results

После запуска здесь появляются основные файлы:

| Кнопка | Что открывает |
| --- | --- |
| `Open support` | итоговый `.docx` |
| `Open output folder` | папку текущего запуска |
| `Open logs` | служебные логи и warnings |
| `Open report` | JSON-отчет запуска |

Строка под кнопками показывает краткий статус: успешно, есть warnings или есть
ошибки.

### Run Log

Текстовый лог выполнения. Сюда выводятся:

- выбранные входные файлы;
- preflight checks;
- предупреждения по input-таблице;
- сообщения ChemDraw;
- сообщения MestReNova;
- путь к итоговым файлам.

Если что-то пошло не так, сначала смотрите `Run Log`.

## GUI: вкладка Advanced

Вкладка `Advanced` нужна для дополнительных файлов и тонкой настройки.

### Optional inputs

| Поле | Что означает |
| --- | --- |
| `SI template .docx` | Word-шаблон оформления SI. Если пусто, используется встроенный шаблон |
| `References .yml` | YAML-файл со списком литературы |
| `MestReNova .exe` | путь к `MestReNova.exe`, если автоопределение не сработало |
| `Mnova graphics .mngp` | профиль отображения спектров MestReNova |

Кнопка `Detect` рядом с `MestReNova .exe` пытается найти MestReNova
автоматически.

### Processing

| Поле | Значение по умолчанию | Что делает |
| --- | --- | --- |
| `Compound table type` | `Word table with ChemDraw objects` | выбирает формат таблицы: Word с OLE-структурами или CSV |
| `Check support` | включено | проверяет NMR, HRMS и elemental analysis |
| `Calculate elemental analysis` | выключено | добавляет расчетный elemental analysis по формуле |
| `Spectra appendix` | `png` | выбирает, как вставлять спектры в конец SI |
| `1H threshold (%)` | `6` | минимальная высота пика для 1H peak picking |
| `13C threshold (%)` | `4` | минимальная высота пика для 13C peak picking |
| `Signal height (%)` | `80` | высота самого высокого сигнала на экспортируемой картинке |

`Spectra appendix` имеет три режима:

| Режим | Что будет в SI |
| --- | --- |
| `png` | обычные картинки спектров |
| `mnova` | кликабельные Mnova OLE-объекты с картинкой-превью |
| `none` | спектральное приложение не добавляется |

Режим `mnova` удобен, если нужно открыть спектр прямо из Word и вручную
подправить его в MestReNova. Для каждого спектра используется отдельный файл:
`2a_1H.mnova` или `2a_13C.mnova`.

### Baseline correction

| Поле | Значение по умолчанию | Что делает |
| --- | --- | --- |
| `Mode` | `auto` | выбирает алгоритм baseline correction |
| `Apply to 1H` | выключено | применять baseline correction к 1H |
| `Apply to 13C` | включено | применять baseline correction к 13C |
| `Bernstein order` | `3` | порядок полинома Bernstein |
| `Whittaker lambda` | `100000` | параметр сглаживания Whittaker |
| `Whittaker asymmetry` | `0.001` | асимметрия Whittaker |

Режимы baseline:

- `auto` - использовать стандартную автоматическую обработку;
- `off` - не делать baseline correction;
- `bernstein` - использовать Bernstein baseline;
- `whittaker` - использовать Whittaker baseline.

Для обычной работы лучше оставить значения по умолчанию. Whittaker-настройки -
expert mode для случаев, где baseline плохо корректируется автоматически.

### Reagent Loadings

| Поле | Что означает |
| --- | --- |
| `Calculate reagent loadings` | включает расчет загрузок реагентов |
| `Reaction schema .docx` | схема реакции с placeholders для реагентов |
| `Scope .docx` | таблица scope/продуктов для расчета загрузок |

Если загрузки не нужны, этот блок можно не трогать.

## GUI: вкладка Check support

Эта вкладка проверяет уже созданный SI без повторной генерации.

| Поле | Что выбрать |
| --- | --- |
| `Manifest` | `support_information.manifest.json` из папки `docx/` |
| `Support .docx override` | другой `.docx`, если нужно проверить не тот файл, который записан в manifest |

Результат проверки сохраняется в `*.check_report.json`.

Этот режим полезен, если вы вручную поправили `support_information.docx` и
хотите проверить, что manifest, bookmarks и файлы результата все еще
согласованы.

## GUI: вкладка Patch SI

Эта вкладка меняет уже созданный SI без полной регенерации.

| Поле | Что означает |
| --- | --- |
| `Existing manifest` | manifest старого SI |
| `Existing support .docx override` | опционально: другой `.docx`, если он не совпадает с путем из manifest |
| `Patched output .docx` | куда сохранить новую копию SI |
| `Renumber` | перенумеровать соединения |
| `Remove` | удалить соединения |
| `Reorder` | изменить порядок соединений |

Примеры:

```text
Renumber: 2a=3a,2b=3b
Remove:   2a,2c
Reorder:  2b,2a,2c
```

В `Remove` и `Reorder` можно указывать номера соединений или внутренние
`cmp_...` id из manifest.

Patch workflow всегда создает новый `.docx`, новый manifest и report. Старый SI
не изменяется.

## GUI: вкладка Add compounds

Эта вкладка добавляет новые соединения к уже созданному SI.

| Поле | Что означает |
| --- | --- |
| `Existing manifest` | manifest старого SI |
| `Existing support .docx` | старый SI `.docx` |
| `New table type` | формат новой таблицы: Word или CSV |
| `New compound table` | таблица только с новыми соединениями |
| `New spectra source` | спектры только для новых соединений |
| `Output .docx` | новый объединенный SI |

Если номер нового соединения уже есть в старом manifest, workflow
останавливается с ошибкой `DUPLICATE_COMPOUND_NUMBER`. Это сделано специально,
чтобы случайно не перезаписать старый блок.

## Кнопки в верхней и нижней части GUI

| Кнопка | Что делает |
| --- | --- |
| `Load example` | подставляет пример из папки `examples/` |
| `Open examples` | открывает папку с примерами |
| `Generate SI` | запускает генерацию |
| `Open last output` | открывает последнюю папку результата |
| `Clear log` | очищает текстовый лог |

## Формат Word-таблицы

Рекомендуемый вариант input - Word-таблица `.docx`, потому что в нее можно
вставить структуры как OLE-объекты ChemDraw.

Минимально нужны:

- номер соединения;
- структура ChemDraw или название;
- физические свойства;
- формула;
- HRMS found;
- спектры или готовый NMR-текст.

Поддерживаемые колонки:

| Колонка | Что писать |
| --- | --- |
| `number`, `No`, `compound`, `id` | номер соединения, например `2a` |
| `name`, `title`, `compound name` | название соединения. Если пусто, программа попробует получить название через ChemDraw |
| `preparation`, `procedure` | текст синтеза/получения |
| `yield`, `yield_text` | выход, например `492 mg (31%)` |
| `color` | цвет |
| `state`, `appearance` | агрегатное состояние или внешний вид |
| `melting_point`, `mp` | температура плавления, например `81-82 °C` |
| `rf` | Rf/TLC строка |
| `formula` | нейтральная молекулярная формула, например `C11H10BrFO2` |
| `hrms_found` или колонка с `HRMS` в названии | найденная HRMS масса |
| `hrms_adduct` | аддукт, например `[M+H]+` |
| `h1_nmr`, `1H NMR` | готовое описание 1H NMR |
| `c13_nmr`, `13C NMR` | готовое описание 13C NMR |
| `h1_spectrum_path` | путь к 1H spectrum folder, если не используете общий spectra source |
| `c13_spectrum_path` | путь к 13C spectrum folder |
| `extra_nmr` | дополнительные NMR, например 19F NMR |
| `ir` | IR строка или список пиков |
| `elemental_analysis`, `anal`, `ea` | найденные значения elemental analysis |
| `references`, `refs`, `reference_keys` | ключи ссылок из `References .yml` |

Примеры `elemental_analysis`:

```text
C, 66.03; H, 3.55; N, 8.92
C, 30.75; H, 7.74; S, 41.04
```

Если нужное поле пустое, программа обычно не останавливается, а пишет warning.
Блокирующие ошибки:

- нет ни одного соединения;
- пустой номер соединения;
- повторяющийся номер соединения;
- выбранный input-файл не существует;
- output path не является `.docx`.

## CSV-таблица

CSV можно использовать, если не нужны структуры как OLE-объекты ChemDraw.

Плюсы CSV:

- проще создать программно;
- удобно для быстрых тестов.

Минусы CSV:

- нельзя вставить ChemDraw OLE-структуру;
- если нужна структура, придется передавать путь к файлу структуры и отдельно
  включать соответствующую обработку.

Для обычного SI с редактируемыми структурами лучше использовать Word-таблицу.

## Формат spectra source

`Spectra source` может быть:

- zip-архивом;
- обычной папкой.

Требования:

- папки верхнего уровня называются номерами соединений;
- внутри каждой папки лежат Bruker experiments;
- в каждом experiment должен быть файл `fid`;
- желательно наличие `acqus` или `acqu`, чтобы определить ядро.

Пример:

```text
spectra/
  2a/
    da9534_1H/
      fid
      acqus
    da9534_13C/
      fid
      acqus
  2b/
    ...
```

Если в spectra source нет папки для какого-то соединения, программа просто не
извлечет NMR для этого соединения и запишет warning.

## Как программа обрабатывает NMR

Для каждого соединения программа пытается найти 1H и 13C spectra folders.

MestReNova workflow:

1. Открывает raw-спектр.
2. Калибрует химический сдвиг по растворителю.
3. Делает обработку и peak picking.
4. Извлекает текстовое описание спектра.
5. Экспортирует PNG.
6. Сохраняет обработанный `.mnova`.
7. Передает результат в сборку SI.

Калибровка растворителей:

| Растворитель | 1H | 13C |
| --- | --- | --- |
| CDCl3 | 7.26 ppm | 77.16 ppm |
| DMSO-d6 | 2.50 ppm | 39.52 ppm |

Диапазоны картинок:

| Ядро | Диапазон |
| --- | --- |
| 1H | от -1 до 12 ppm |
| 13C | от -10 до 210 ppm |

Для 1H программа оставляет интегралы снизу, но убирает верхнюю integral curve.
Для 13C оставляется peak picking без интегралов и multiplet labels.

## Peak picking threshold

Threshold задает минимальную высоту пика, который будет считаться сигналом.
Значение указывается в процентах от самого высокого не-solvent пика.

Примеры:

- `6` значит 6%;
- `0.06` тоже значит 6%.

Рекомендации:

- если программа захватывает шум или слабые примеси, увеличьте threshold;
- если программа пропускает настоящие слабые пики, уменьшите threshold;
- для 13C обычно нужен threshold ниже, чем для 1H;
- значения по умолчанию: `1H = 6`, `13C = 4`.

## Signal height

`Signal height (%)` задает, сколько места по вертикали занимает самый высокий
сигнал на экспортируемой картинке спектра.

По умолчанию стоит `80`: самый высокий сигнал должен занимать примерно 80%
доступной высоты и не вылезать за край картинки.

Допустимый диапазон: от 20 до 95%.

## Baseline correction

Baseline correction особенно важен для 13C NMR, поэтому по умолчанию он включен
для 13C и выключен для 1H.

Режимы:

- `auto` - стандартный автоматический режим;
- `off` - отключить baseline correction;
- `bernstein` - Bernstein baseline;
- `whittaker` - Whittaker baseline.

Whittaker-настройки:

- `Whittaker lambda` - сила сглаживания;
- `Whittaker asymmetry` - асимметрия baseline fitting.

Если вы не уверены, оставьте настройки по умолчанию.

## Spectra appendix: png, mnova, none

Поле `Spectra appendix` управляет приложением спектров в конце SI.

### `png`

Вставляет обычные PNG-картинки спектров. Это самый надежный режим.

### `mnova`

Вставляет кликабельные MestReNova OLE-объекты с картинкой-превью. Пользователь
видит спектр как картинку, но по клику может открыть его в MestReNova.

Важно:

- для 1H вставляется single-spectrum файл `2a_1H.mnova`;
- для 13C вставляется single-spectrum файл `2a_13C.mnova`;
- общий файл `2a.mnova` может храниться в output как набор обработанных
  спектров, но кликабельные объекты используют именно single-spectrum файлы.

Это нужно, чтобы при ручной правке 13C из Word не открывался общий файл на
странице 1H.

### `none`

Не добавляет спектральное приложение. Текстовые описания NMR при этом могут
быть вставлены в блоки соединений, если они есть в input или извлечены из
MestReNova.

## HRMS

Для HRMS программа использует:

- `formula` - нейтральная формула вещества;
- `hrms_adduct` - аддукт, например `[M+H]+`;
- `hrms_found` - найденная масса.

Программа считает расчетную массу и формирует строку вида:

```text
HRMS (ESI/Q-TOF) m/z: [M+H]+ calcd for C11H11BrFO2+ 272.9921. Found 272.9920.
```

Для Br/Cl автоматически добавляются моноизотопные подписи в формуле, где это
нужно для корректного оформления.

## Elemental analysis

Если в таблице указано поле `elemental_analysis`, программа вставляет строку:

```text
Anal. Calcd for C17H11FN2O3: C, 65.81; H, 3.57; N, 9.03. Found: C, 66.03; H, 3.55; N, 8.92.
```

Если включить `Calculate elemental analysis`, программа рассчитает
теоретическую часть по формуле даже без found-значений.

Проверка elemental analysis сравнивает найденные значения с расчетными и пишет
warning, если расхождение слишком большое или найден элемент, которого нет в
формуле.

## IR

Поле `ir` можно заполнять кратко:

```text
3038, 2957, 1711
```

или полностью:

```text
IR (ATR, cm-1): 3038, 2957, 1711.
```

Если указан только список пиков, программа оформит строку по шаблону.

## References

`References .yml` нужен, если в SI должен быть раздел литературы.

Пример:

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

В таблице соединений укажите ключи в колонке `references`, например:

```text
data_automation
```

или несколько ключей:

```text
ref1; ref2
```

Если ключ указан в таблице, но отсутствует в YAML, программа добавит warning.

## SI template .docx

Шаблон управляет оформлением итогового SI.

Если поле `SI template .docx` пустое, используется встроенный шаблон. Если вы
выбрали свой шаблон, программа берет из него:

- поля страницы;
- шрифт;
- размер шрифта;
- интервалы;
- жирность;
- курсив;
- верхние и нижние индексы;
- расположение блоков;
- формат заголовков и спектрального приложения.

Шаблон пишется как обычный Word-документ, похожий на будущий SI. Вместо данных
используются placeholders.

Основные placeholders:

```text
{compound.name}
{compound.number}
{compound.label}
{compound.preparation}
{compound.support_warning}
{reaction.loadings}
{nmr.1h.label}
{nmr.1h.conditions}
{nmr.1h.peaks}
{nmr.13c.label}
{nmr.13c.conditions}
{nmr.13c.peaks}
{nmr.extra}
{hrms.label}
{hrms.adduct}
{hrms.formula}
{hrms.calculated}
{hrms.found}
{anal.label}
{anal.formula}
{anal.calculated}
{anal.found}
{ir.label}
{ir.method}
{ir.peaks}
{spectrum.label}
{spectrum.conditions}
{spectrum.structure.marker}
```

Для reagent loadings используются placeholders вида:

```text
{number.Product}
{number.Reagent.1}
{name.Reagent.1}
{name.Reagent.2}
{mg.Reagent.2}
{mmol.Reagent.2}
{mg.K2CO3}
{mmol.K2CO3}
{uL.AcOH}
{mL.Solvent.MeCN}
{yield.Product.mg}
{yield.Product.percent}
```

Если placeholder выделен жирным или курсивом в шаблоне, вставленный текст
сохранит это оформление. Для формул можно вручную поставить нижние индексы в
шаблоне, например в `K2CO3`.

## Проверка support

Опция `Check support (NMR, HRMS, elemental analysis)` включена по умолчанию.

Проверяются:

1. Количество H по интегралам 1H NMR.
2. Количество C по 13C NMR.
3. Совпадение рассчитанного и найденного HRMS.
4. Совпадение elemental analysis с формулой.
5. Наличие ключевых входных данных.

Если есть проблема, программа:

- пишет warning в `Run Log`;
- сохраняет issue в `support_information.run_summary.json`;
- сохраняет подробности в `logs/support_warnings.txt`;
- добавляет красную пометку `Support check` в SI, если это применимо.

Проверка не заменяет ручную проверку химика. Она нужна, чтобы быстро найти
подозрительные места.

## Output folder

Для каждого запуска создается отдельная папка:

```text
output/
  runs/
    20260707_153000_test_input/
      docx/
        support_information.docx
        support_information.manifest.json
        support_information.run_summary.json
      input/
        copied input files
      spectra/
        processed_spectra.zip
        processed_spectra/
          2a/
            2a_1H.png
            2a_13C.png
            2a_1H.mnova
            2a_13C.mnova
      mnova/
        processed/
      logs/
        mnova_reports/
      reports/
```

Главные файлы:

| Файл | Для чего нужен |
| --- | --- |
| `docx/support_information.docx` | итоговый SI |
| `docx/support_information.manifest.json` | карта результата для проверки, patch и add workflows |
| `docx/support_information.run_summary.json` | отчет запуска, warnings/errors, issues по соединениям |
| `spectra/processed_spectra.zip` | архив обработанных PNG и `.mnova` |
| `spectra/processed_spectra/` | те же спектры в папках |
| `logs/` | текстовые warnings и логи MestReNova |

Старые файлы в корне `output/`, созданные предыдущими версиями программы,
удаляются только если это известные generated-файлы. Пользовательские файлы в
`output/` программа не должна удалять.

## Примеры в репозитории

В папке `examples/` лежат входные данные и пример результата.

| Файл или папка | Что это |
| --- | --- |
| `examples/test_input.docx` | Word-таблица с соединениями и ChemDraw/ChemSketch OLE-структурами |
| `examples/test_input.zip` | zip-архив со спектрами для `test_input.docx` |
| `examples/test_input_2.docx` | дополнительный пример input-таблицы |
| `examples/spectra_2/` | пример spectra source как обычной папки |
| `examples/references.example.yml` | пример библиографии |
| `examples/templates/SI_template_visual_current.docx` | пример Word-шаблона оформления |
| `examples/templates/SI_template_visual_current_preview.png` | preview шаблона |
| `examples/loadings/Reaction_schema.docx` | пример схемы для reagent loadings |
| `examples/loadings/Scope.docx` | пример scope-таблицы для reagent loadings |
| `examples/example_output/support_information.docx` | пример готового SI |
| `examples/example_output/processed_spectra.zip` | пример архива обработанных спектров |

Чтобы проверить программу на примере:

1. Нажмите `Load example` в GUI.
2. Проверьте, что подставились `examples/test_input.docx` и
   `examples/test_input.zip`.
3. Нажмите `Generate SI`.
4. Сравните результат с `examples/example_output/support_information.docx`.

## CLI

Обычному пользователю удобнее GUI. CLI нужен для автоматизации или отладки.

Генерация SI:

```powershell
AutoSupportGenerator.exe ^
  --word-input examples\test_input.docx ^
  --spectra-source examples\test_input.zip ^
  --output output\support_information.docx
```

С указанием MestReNova и шаблона:

```powershell
AutoSupportGenerator.exe ^
  --word-input C:\data\input.docx ^
  --spectra-source C:\data\spectra.zip ^
  --template-docx C:\data\SI_template.docx ^
  --mnova-exe "C:\Program Files\Mestrelab Research S.L\MestReNova\MestReNova.exe" ^
  --insert-spectra-as png ^
  --output C:\data\output\support_information.docx
```

Проверить существующий manifest:

```powershell
AutoSupportGenerator.exe ^
  --check-manifest output\runs\run_name\docx\support_information.manifest.json
```

Patch SI:

```powershell
AutoSupportGenerator.exe ^
  --patch-manifest output\runs\run_name\docx\support_information.manifest.json ^
  --renumber 2a=3a,2b=3b ^
  --patched-output output\support_information_renumbered.docx
```

Add compounds:

```powershell
AutoSupportGenerator.exe ^
  --add-compounds-manifest output\runs\run_name\docx\support_information.manifest.json ^
  --support-docx output\runs\run_name\docx\support_information.docx ^
  --add-word-input C:\data\new_compounds.docx ^
  --spectra-source C:\data\new_spectra.zip ^
  --add-output C:\data\output\support_information_extended.docx
```

Часто используемые CLI-параметры:

| Параметр | Что делает |
| --- | --- |
| `--word-input` | Word-таблица с ChemDraw OLE-структурами |
| `--input` | CSV-таблица |
| `--spectra-source` | zip или папка со спектрами |
| `--output` | путь к итоговому `.docx` |
| `--template-docx` | Word-шаблон SI |
| `--references` | YAML со ссылками |
| `--mnova-exe` | путь к MestReNova |
| `--mnova-graphics-profile` | `.mngp` профиль отображения спектров |
| `--insert-spectra-as` | `png`, `mnova` или `none` |
| `--target-signal-height` | высота сигналов, например `80` |
| `--peak-threshold-1h` | threshold для 1H |
| `--peak-threshold-13c` | threshold для 13C |
| `--baseline-mode` | `auto`, `off`, `bernstein`, `whittaker` |
| `--baseline-apply-1h` | включить baseline correction для 1H |
| `--no-baseline-13c` | выключить baseline correction для 13C |
| `--generate-loadings` | считать reagent loadings |
| `--calculate-elemental-analysis` | считать elemental analysis |
| `--no-check-support` | отключить проверку NMR/HRMS/elemental analysis |

## Типичные проблемы

### MestReNova не найдена

Что сделать:

1. Откройте `Advanced`.
2. Нажмите `Detect` рядом с `MestReNova .exe`.
3. Если не помогло, выберите `MestReNova.exe` вручную.

Типовой путь:

```text
C:\Program Files\Mestrelab Research S.L\MestReNova\MestReNova.exe
```

### Не генерируются названия соединений

Проверьте:

- ChemDraw установлен;
- структуры в Word вставлены как OLE-объекты, а не как PNG;
- Word и ChemDraw не показывают модальные окна;
- файл не открыт в защищенном режиме.

### Output DOCX не записывается

Чаще всего файл открыт в Word. Закройте `support_information.docx` и запустите
генерацию снова.

### В спектрах лишние пики

Увеличьте:

- `1H threshold (%)` для 1H;
- `13C threshold (%)` для 13C.

### Пропадают настоящие слабые пики

Уменьшите threshold для соответствующего ядра.

### 13C baseline выглядит плохо

Попробуйте в `Advanced -> Baseline correction`:

- `Mode = whittaker`;
- изменить `Whittaker lambda`;
- изменить `Whittaker asymmetry`.

### В отчете NMR count mismatch

Откройте single-spectrum `.mnova` файл из output:

```text
spectra/processed_spectra/2a/2a_1H.mnova
spectra/processed_spectra/2a/2a_13C.mnova
```

Проверьте auto integration, multiplet analysis, peak picking threshold и
baseline correction.

## Для разработчиков

Запуск тестов:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests
```

Основные папки кода:

```text
src/si_generator/domain/      доменные модели и расчеты
src/si_generator/graph/       LangGraph-style workflow nodes
src/si_generator/workflows/   entrypoints generate/check/patch/add
src/si_generator/render/      модель SI-документа
src/si_generator/resources/   MestReNova scripts и ресурсы
```

Сборка установщика:

```text
Build Auto Support Generator Installer.bat
```

Не добавляйте в GitHub:

- `output/`;
- временные папки MestReNova;
- `__pycache__/`;
- локальные run artifacts;
- пользовательские `.mnova` batch-файлы.
