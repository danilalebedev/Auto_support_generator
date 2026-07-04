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
spectra.zip или spectra_folder/
```

`compound_table.docx` - Word-файл с таблицей соединений. В первой строке таблицы
должны быть заголовки колонок, каждая следующая строка описывает одно
соединение. В первой колонке обычно находится номер соединения и структура,
вставленная как OLE-объект ChemDraw или ChemSketch.

`spectra.zip` или `spectra_folder/` - источник raw-спектров ЯМР. Это может быть
zip-архив или обычная папка. Внутри должны быть папки с номерами соединений.
Названия папок должны совпадать с номерами в таблице:

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

Колонки для РСА/XRD необязательны. Если они есть, программа добавляет XRD-строку
в SI и сохраняет пути в manifest. Поддерживаются заголовки `XRD`, `CCDC`, `CIF`,
`checkCIF`, `XRD table`, `XRD figures`.

Дополнительные входные файлы необязательны:

- `SI template .docx` - Word-шаблон, из которого берутся поля страницы,
  шрифты, интервалы, стили и оформление отдельных элементов SI;
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

Для каждого запуска создается отдельная папка результата:

```text
output/
  runs/
    20260704_153000_test_input/
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

Для пользователя обычно важны:

- `support_information.docx` - финальный SI;
- `support_information.manifest.json` - техническая карта результата: порядок
  соединений, внутренние `cmp_...` id, Word bookmarks и пути к артефактам;
- `support_information.run_summary.json` - краткий отчет генерации: статус,
  количество warnings/errors, список issues и диагностика по каждому соединению;
- `processed_spectra.zip` - архив с PNG-картинками спектров и обработанными
  `.mnova` файлами;
- `processed_spectra/` - те же файлы в обычных папках.

`logs/`, `reports/`, `mnova/` и `spectra/processed_spectra/` нужны для проверки,
отладки и ручной правки обработанных спектров. GUI запоминает последний run и
кнопка `Open last output` открывает именно эту папку.

## Как пользоваться GUI

В окне программы:

1. На вкладке `Generate` в `Compound table` выберите таблицу с веществами.
2. В `Spectra source` выберите zip-архив или папку со спектрами.
3. В `Output folder` выберите папку, куда писать результат.
4. На вкладке `Advanced` при необходимости задайте Word-шаблон, references,
   путь к MestReNova, `.mngp`-профиль отображения спектров, режим приложения
   спектров, thresholds, baseline correction и `Check support`.
5. Нажмите `Generate SI`.

Отдельные инструменты вынесены в свои вкладки:

- `Check support` - проверить уже созданный `support_information.manifest.json`;
- `Patch SI` - перенумеровать, удалить или переставить compound-блоки без полной
  регенерации;
- `Add compounds` - добавить новые соединения к старому SI.

В нижнем окне будет лог выполнения. После завершения нажмите `Open last output`,
чтобы открыть папку последнего запуска.

В блоке `Results` GUI показывает основные артефакты. Кнопка `Open report`
открывает JSON-отчет: после генерации это `support_information.run_summary.json`,
после проверки manifest - `*.check_report.json`, после patch workflow -
`*.patch_report.json`. Эти отчеты удобны для диагностики: в них есть общий
статус, счетчики warnings/errors и привязка проблем к конкретным соединениям.

## Что получается на выходе

Если выбран output folder:

```text
output/
```

то внутри него создается отдельная папка запуска:

```text
output/
  runs/
    20260704_153000_test_input/
      docx/
        support_information.docx
        support_information.manifest.json
        support_information.run_summary.json
      input/
      spectra/
        processed_spectra.zip
        processed_spectra/
      mnova/
        processed/
      logs/
        mnova_reports/
      reports/
```

Главные файлы для пользователя:

- `support_information.docx` - готовый SI;
- `support_information.run_summary.json` - машинно-читаемый отчет запуска. В нем
  видно, какие соединения были обработаны, сколько warnings/errors найдено и к
  каким соединениям они относятся;
- `support_information.manifest.json` - карта результата для проверки,
  перенумерации, удаления и перестановки compound-блоков без полной регенерации;
- `processed_spectra.zip` - архив с обработанными спектрами, PNG-картинками и
  `.mnova` файлами;
- `processed_spectra/` - то же самое, но в виде обычных папок.

`logs/` - служебные файлы. Там лежат текстовые warnings по входным данным и
проверке SI. Обычно пользователю достаточно открыть `Run report` в GUI, но эти
файлы помогают быстро понять, какое поле в таблице нужно поправить.

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
- `Spectra source`: `examples/test_input.zip`;
- `Output folder`: любая удобная папка, например `output`.

После запуска программа должна создать run-папку внутри `output/runs/` с готовым
`docx/support_information.docx`, `spectra/processed_spectra.zip` и служебными
папками `logs/`, `mnova/`, `reports/`, `input/`.

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
| `ir` | IR строка: можно писать только пики `3038, 2957, 1711` или полный формат `IR (ATR, cm-1): 3038, 2957, 1711` |
| `elemental_analysis` | найденные значения, например `C, 66.03; H, 3.55; N, 8.92` или `C, 30.75; H, 7.74; S, 41.04` |
| `xrd` | готовая строка РСА/XRD, если ее нужно вставить вручную |
| `ccdc` | CCDC number; если `xrd` пустой, программа сформирует короткую XRD-строку |
| `cif` | путь к CIF-файлу |
| `checkcif` | путь к checkCIF report |
| `xrd_table` | путь к таблице кристаллографических данных |
| `xrd_figures` | пути к рисункам РСА/XRD через `;` |
| `references` | ключи ссылок через запятую или `;`, например `ref1; ref2` |
| `target_mmol` | масштаб реакции для расчета загрузок реагентов |
| `reagent_1_name` | название первого реагента |
| `reagent_1_equiv` | эквиваленты первого реагента |
| `reagent_1_mw` | молярная масса первого реагента |
| `reagent_1_density_g_ml` | плотность, если нужен расчет объема жидкости |
| `reagent_1_concentration_m` | концентрация раствора, если нужен расчет объема раствора |

Если подключен zip со спектрами, `h1_nmr` и `c13_nmr` можно не заполнять:
программа попробует получить их из MestReNova.

Для нескольких реагентов используйте тот же набор колонок с номерами `reagent_2_*`,
`reagent_3_*` и так далее. Если reaction/loadings колонки заполнены, программа
рассчитает `mmol`, `mg` и `uL` и добавит строку `Reaction loadings` в описание соединения.

Для IR по умолчанию используется метод `KBr`, если в колонке указан только
список пиков. Если нужен другой метод, укажите его прямо в строке, например
`IR (ATR, cm-1): 3038, 2957, 1711` или `IR (film, cm-1): 1711, 1606`.

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

## Формат spectra source

Источник спектров может быть zip-архивом или обычной папкой. Внутри должны быть
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
6. Для elemental analysis программа считает теоретические проценты по `formula`
   для C/H/N и для дополнительных элементов, указанных в found-строке
   (`S`, `Cl`, `Br`, `O` и т.п.), затем сравнивает их с найденными значениями.
   Если в found-строке указан элемент, которого нет в формуле, это тоже
   попадает в warnings.
7. Если есть расхождение, в итоговом SI добавляется красная пометка
   `Support check`.

Если NMR-текст был получен из MestReNova и число H/C не совпало с формулой,
в `support_information.run_summary.json` дополнительно появляется issue
`MNOVA_1H_REPORT_REVIEW_REQUIRED` или `MNOVA_13C_REPORT_REVIEW_REQUIRED`.
Это означает, что нужно открыть соответствующий single-spectrum `.mnova` файл и
проверить auto integration, multiplet analysis, peak threshold или baseline
settings. Такая пометка не заменяет обычный mismatch warning, а добавляет к нему
понятное действие для ручной проверки.

Важно: проверка не заменяет ручную проверку химика. Это быстрый автоматический
контроль, который помогает найти подозрительные места.

## Настройка оформления

Оформление задается одним Word-шаблоном `SI_template.docx`. В GUI это поле
называется `SI template .docx`. Если поле оставить пустым, используется
встроенный шаблон.

Шаблон выглядит как обычный будущий SI: текст Word с placeholder-ами в фигурных
скобках. Программа копирует поля страницы, шрифты, интервалы, жирность, курсив,
нижние и верхние индексы из шаблона. Если placeholder или группа вида
`[{hrms.label}]` выделены жирным, вставленный текст тоже будет жирным.

Публичный формат placeholder-ов единый: используются точки, не подчеркивания.
Основные placeholder-ы:

```text
{compound.name}
{compound.number}
{compound.preparation}
{reaction.loadings}
{number.Product}
{number.Reagent.1}
{name.Reagent.2}
{mg.Reagent.2}
{mmol.Reagent.2}
{mg.K2CO3}
{mmol.K2CO3}
{uL.AcOH}
{mL.Solvent.MeCN}
{yield.Product.mg}
{yield.Product.percent}
{appearance}
{rf.value}
{rf.system}
{nmr.1h.label}
{nmr.1h.conditions}
{nmr.1h.peaks}
{nmr.13c.label}
{nmr.13c.conditions}
{nmr.13c.peaks}
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
{xrd.text}
{xrd.ccdc}
{xrd.cif}
{xrd.checkcif}
```

Для reagent loadings больше не нужен отдельный `Compound_characterization`
template: текст загрузок берется из этого же `SI_template.docx`. В шаблоне
реакции можно написать, например, `K2CO3` и выставить цифрам `2` и `3`
нижний индекс прямо в Word.

## CLI для продвинутых пользователей

Если программа установлена через `AutoSupportGeneratorSetup.exe`, CLI можно
запускать через установленный exe:

```powershell
%LOCALAPPDATA%\AutoSupportGenerator\AutoSupportGenerator.exe --word-input examples\test_input.docx --spectra-source examples\test_input.zip --output output\support_information.docx
```

Если программа запущена из исходников, используйте `py -m si_generator`.

Основной Word workflow из исходников:

```powershell
py -m si_generator ^
  --word-input C:\path\to\input.docx ^
  --spectra-source C:\path\to\spectra.zip ^
  --mnova-exe "C:\Program Files\Mestrelab Research S.L\MestReNova\MestReNova.exe" ^
  --insert-spectra-as png ^
  --generate-loadings ^
  --references references.yml ^
  --output output\support_information.docx
```

Параметр `--insert-spectra-as` управляет приложением спектров в конце SI:
`png` вставляет обычные изображения спектров, `mnova` вставляет кликабельные
OLE-объекты MestReNova с картинкой-превью, `none` не добавляет спектральный
appendix. Для `mnova`-режима у каждого спектра должны быть сохраненный `.mnova`
файл и сгенерированная page PNG: single-spectrum `.mnova` встраивается как
native `MestReNova.Document.1`, а PNG используется только как отображаемое
превью. Общий файл вида `2a.mnova` остается в output для хранения набора
обработанных спектров, а кликабельные объекты используют `2a_1H.mnova` или
`2a_13C.mnova`, чтобы при ручной правке не переключаться на другую страницу.
В GUI это поле называется `Spectra appendix`.

Если в MestReNova уже настроен нужный внешний вид спектров, его можно сохранить
как `.mngp` graphics/profile file и указать в GUI на вкладке `Advanced` в поле
`Mnova graphics .mngp`. Программа передает этот профиль в Mnova при экспорте PNG
и пытается применить его при экспорте PNG и сохранении single-spectrum `.mnova`.
В CLI тот же параметр задается так:

```powershell
py -m si_generator ^
  --word-input C:\path\to\input.docx ^
  --spectra-source C:\path\to\spectra.zip ^
  --mnova-graphics-profile C:\path\to\display_profile.mngp ^
  --output output\support_information.docx
```

Профиль является expert-настройкой. В MestReNova 14.2.0 `.mngp` доходит до
batch-скрипта, но публичный scripting API может не дать применить бинарный
Graphic Properties file напрямую. В таком случае генерация продолжится, а
предупреждение будет записано в `logs/mnova_batch/mnova_batch.status.txt`.

Peak picking threshold задает минимальную высоту пика относительно самого
высокого не-solvent пика. В GUI есть отдельные поля `1H threshold (%)` и
`13C threshold (%)`; значения по умолчанию: `6` для `1H` и `4` для `13C`.
В CLI можно задать их отдельно:

```powershell
py -m si_generator ^
  --word-input C:\path\to\input.docx ^
  --spectra-source C:\path\to\spectra_folder ^
  --peak-threshold-1h 6 ^
  --peak-threshold-13c 4 ^
  --output output\support_information.docx
```

Старый параметр `--peak-threshold 6` остается рабочим и задает одинаковый порог
для обоих ядер.

Параметр `--spectra-source` принимает zip-архив или обычную папку. Старый
`--spectra-zip` оставлен как совместимый alias для старых команд.

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

Рядом с manifest создается файл `support_information.check_report.json`. В нем
сохранены статус проверки, список найденных issues, счетчики по severity и
`compound_issue_counts` для проблем, связанных с конкретными соединениями.

Создать патченую копию уже сгенерированного SI с новой нумерацией соединений:

```powershell
py -m si_generator ^
  --patch-manifest output\support_information.manifest.json ^
  --renumber 2a=3a,2b=3b ^
  --patched-output output\support_information_renumbered.docx
```

Сейчас patch workflow поддерживает безопасную перенумерацию, удаление и перестановку compound-блоков по
`manifest` и невидимым Word bookmarks: он создает новый `.docx`, новый `.manifest.json` и сразу
проверяет, что bookmarks в документе совпадают с manifest. Замена отдельных структур будет добавлена
отдельной patch-операцией.

Для patch workflow дополнительно создается `*.patch_report.json`. Этот отчет
фиксирует примененные операции (`renumber`, `remove`, `reorder`), итоговый
статус проверки и issues по соединениям.

Удалить одно или несколько соединений без полной регенерации:

```powershell
py -m si_generator ^
  --patch-manifest output\support_information.manifest.json ^
  --remove 2a,2c ^
  --patched-output output\support_information_removed.docx
```

В `--remove` можно указывать номера соединений или внутренние `cmp_...` id из manifest.

Поменять порядок compound-блоков без полной регенерации:

```powershell
py -m si_generator ^
  --patch-manifest output\support_information.manifest.json ^
  --reorder 2b,2a,2c ^
  --patched-output output\support_information_reordered.docx
```

В `--reorder` нужно перечислить все соединения из manifest ровно один раз, по номеру соединения
или внутреннему `cmp_...` id.

Отключить проверку:

```powershell
py -m si_generator ^
  --word-input C:\path\to\input.docx ^
  --spectra-source C:\path\to\spectra.zip ^
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
`support_information.manifest.json` и `support_information.run_summary.json`,
а также планирование NMR render spec для экспорта спектров. Отдельно проверяется
промежуточная модель SI-документа перед записью `.docx`; GUI также проверяется
как thin wrapper вокруг graph workflow. Check/patch workflows покрыты тестами
на `*.check_report.json`, `*.patch_report.json`, перенумерацию, удаление и
перестановку compound-блоков.
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
