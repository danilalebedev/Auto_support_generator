# Auto Support Generator

## Видео интерфейса

[![Демонстрация интерфейса Auto Support Generator](docs/assets/Auto_Support_Generator_promo_ru_preview.gif)](docs/assets/Auto_Support_Generator_promo_ru.mp4)

Нажмите на превью, чтобы открыть полное видео со звуком.

[English](README_EN.md) | **Русский**

## Research status and citation

Auto Support Generator is an early research software project for automated generation of supporting information in organic chemistry.

A ChemRxiv preprint describing the method, software architecture, and example workflows is currently in preparation.

Auto Support Generator — исследовательский проект с открытым исходным кодом. Исходный код проекта опубликован на GitHub.

Author: Danila Lebedev  
Copyright © 2026 Danila Lebedev

## Контакты

Если у вас есть вопросы, предложения или сообщения об ошибках, напишите автору:

- Email: [lebedevdanilaaa@gmail.com](mailto:lebedevdanilaaa@gmail.com)
- Telegram: [@lebdanchem](https://t.me/lebdanchem)

## Установка без Git и Python

1. Откройте файл [`installer/AutoSupportGeneratorSetup.exe`](installer/AutoSupportGeneratorSetup.exe) на GitHub.
2. Нажмите **Download raw file** и сохраните установщик. Клонировать репозиторий и устанавливать Git не нужно.
3. Запустите `AutoSupportGeneratorSetup.exe`. Если появился Windows SmartScreen, убедитесь, что файл скачан из этого репозитория, затем нажмите **Подробнее → Выполнить в любом случае**.
4. В поле **Installation folder** оставьте предложенный путь в `%LOCALAPPDATA%` или нажмите **Browse...** и выберите другую папку.
5. Оставьте включенным создание ярлыков и нажмите **Install**.
6. Запустите **Auto Support Generator** с рабочего стола или из меню «Пуск».
7. Перед первой генерацией отдельно запустите Word, ChemDraw и MestReNova и завершите их первичную настройку.

Microsoft Word, ChemDraw и MestReNova являются отдельными лицензионными программами и не входят в установщик.

### Удаление

Откройте **Параметры Windows → Приложения → Установленные приложения → Auto Support Generator → Удалить** либо выберите **Пуск → Auto Support Generator → Uninstall Auto Support Generator**. По умолчанию удаляются только файлы программы, а output, настройки и неизвестные пользовательские файлы сохраняются. Чтобы удалить всю папку установки, снимите галочку сохранения пользовательских данных и подтвердите действие.

## License

Copyright © 2026 Danila Lebedev.

This project is licensed under the Apache License, Version 2.0.

See the [LICENSE](LICENSE) file for details.

![Интерфейс Auto Support Generator](docs/assets/gui_overview.png)

## Назначение

Auto Support Generator автоматически собирает Supporting Information (SI) для органической химии. Программа переносит структуры ChemDraw, физические свойства и аналитические данные в Word, обрабатывает спектры ЯМР в MestReNova, рассчитывает загрузки и формирует отчеты проверки.

## Возможности

| Раздел | Что делает |
|---|---|
| **Generate** | Создает новый SI из таблицы соединений и raw-спектров; применяет профиль выбранного журнала. |
| **Processing** | Настраивает обработку ЯМР, вид appendix и проверку данных. |
| **Check** | Проверяет ранее созданный output: целостность manifest/DOCX/артефактов, количество H и сигналов 13C по брутто-формуле, HRMS и элементный анализ; сохраняет отчет о найденных несоответствиях. |
| **Patch** | Создает измененную копию SI без повторной обработки спектров: renumber, remove, reorder, swap или переоформление под другой журнал. |
| **Add** | Добавляет новые соединения в существующий SI, не пересобирая старые блоки. |
| **Instructions** | Содержит встроенную справку, таблицу алиасов и скачиваемые примеры. |

Программа также:

- сохраняет структуры как редактируемые OLE-объекты ChemDraw;
- получает номенклатурные названия из ChemDraw;
- извлекает описания 1H/13C NMR и экспортирует PNG или кликабельные Mnova-объекты;
- рассчитывает HRMS и элементный анализ по формуле структуры;
- проверяет количество H/C в NMR, HRMS и элементный анализ;
- рассчитывает массы, количества, объемы, эквиваленты и выходы реакции;
- сохраняет обработанные `.mnova`, изображения, manifest, отчеты и логи.

## Требования

| Программа | Для чего нужна | Проверенная версия |
|---|---|---|
| Windows 10/11 | запуск приложения | 64-bit |
| Microsoft Word desktop | создание DOCX и OLE | Microsoft 365 / Word 2021 |
| ChemDraw | структуры и названия | 22.2.0.3300 |
| MestReNova | обработка ЯМР | 14.2.0-26256 |

Лицензионные установщики доступны через [официальную инструкцию ChemDraw](https://support.revvitysignals.com/hc/en-us/articles/4408210538132-How-do-I-download-the-MSI-installer-for-ChemDraw) и [официальную страницу загрузки Mnova](https://mestrelab.com/download). ChemDraw и MestReNova не входят в установщик Auto Support Generator и требуют собственных действующих лицензий.

В готовой сборке Python устанавливать не нужно. Перед первым запуском один раз откройте Word, ChemDraw и MestReNova вручную и завершите их первичную настройку. Если MestReNova не найдена автоматически, укажите ее `.exe` в Generate.

## Запуск из исходного кода

Этот раздел нужен только разработчикам. Установите Python 3.12, затем выполните `Setup Auto SI Generator.bat` и `Run Auto SI Generator.bat`. Обычным пользователям следует использовать готовый установщик по инструкции в начале README.

## Быстрый старт

1. Откройте **Instructions → Example files → Copy all examples**.
2. Возьмите `example_1`: можно редактировать отдельные Word-файлы или один `All_in_one_input.docx`.
3. В **Generate** выберите журнал и режим **Separate files** либо **Single all-in-one DOCX**.
4. Укажите `Spectra_source` и папку результата. При необходимости измените `.mngp` и Processing.
5. В **Processing** проверьте настройки спектров.
6. Вернитесь в Generate и нажмите **Generate SI**.
7. После завершения нажмите **Open support** или **Open output folder**.

## Поля Generate

### Основные

| Поле программы | Что загрузить |
|---|---|
| **Publication preset** | Целевой журнал. Выбор применяет встроенный Word-шаблон, MNGP, диапазоны ppm и правила appendix; **Apply** возвращает значения профиля после ручных изменений. |
| **Input format** | **Separate files** для обычного набора документов или **Single all-in-one DOCX** для единого файла. |
| **Compound table** | `Compound_table.docx`: одна строка на соединение, номер, свойства, HRMS/IR/Anal и OLE-структура ChemDraw. |
| **All-in-one input** | `All_in_one_input.docx`, содержащий Compound table и секции Reaction schema, Scope и пользовательский SI template. Используется только в режиме **Single all-in-one DOCX**; готовые примеры уже содержат все четыре части. |
| **Spectra source** | Папку `Spectra_source` или `Spectra_source.zip` с подпапками по номерам соединений. |
| **Output folder** | Родительскую папку для результатов. Программа сама создаст в ней отдельный каталог запуска и разложит DOCX, редактируемые Mnova-файлы, PNG, копии входов, отчеты и логи по подпапкам. |

### Optional inputs

| Поле программы | Что загрузить |
|---|---|
| **SI template .docx** | `SI_template.docx` с текстом, форматированием и алиасами. Это пользовательский шаблон методики: его можно оформить как будущий SI, изменить формулировки, порядок данных, жирный/курсив и набор выводимых полей. Если поле пустое, используется шаблон выбранного журнала. |
| **MestReNova .exe** | Путь к `MestReNova.exe`, если автоматический поиск не сработал. |
| **1H .mngp** | Пользовательский стиль отображения 1H NMR. Без файла используется встроенный classic. |
| **13C .mngp** | Пользовательский стиль отображения 13C NMR. Без файла используется встроенный classic. |

### Reagent Loadings

| Поле программы | Что загрузить |
|---|---|
| **Reaction schema .docx** | `Reaction_schema.docx`: список `Reagent_1`, `Reagent_2`, именованных реагентов и растворителей, их eq, MW, плотности или концентрации. |
| **Scope .docx** | `Scope.docx`: данные для каждого продукта, включая массы и структуры переменных реагентов. |

Включите расчет загрузок только при наличии обоих файлов. Номера продуктов в Compound table и Scope должны совпадать.

### Как подготовить входные Word-файлы

Начните с файлов из **Instructions → Example files**. Не создавайте таблицы с нуля: сохраните заголовки столбцов и замените демонстрационные данные и OLE-структуры своими.

**1. Сначала настройте SI template**

`SI_template.docx` выглядит как один готовый блок соединения. Объект обозначает сущность, например `Product`, `Reagent_1`, `NBS` или `Solvent_CHCl3`; атрибут после точки обозначает нужное свойство, например `.name`, `.mg`, `.mmol` или `.ml`. Поэтому `{NBS.mg}` означает «рассчитанная масса NBS», а `{Product.yield.percent}` означает «выход продукта в процентах». Программа повторяет этот блок для каждого продукта и заменяет алиасы значениями. Жирный и курсив алиаса в Word сохраняются у вставленного значения.

Добавляйте в шаблон только нужные поля. Расчет может быть выполнен, но значение появится в SI только там, где расположен соответствующий алиас. Для собственной методики измените обычный текст вокруг алиасов и набор реагентов. В режиме all-in-one тот же шаблон помещается после метки `[AUTO SI: SI TEMPLATE]`.

**2. Заполните Compound table**

| Столбец | Как заполнить |
|---|---|
| `number` | Уникальный номер продукта, например `2a`. Он должен точно совпадать с номером в Scope и именем папки спектров. |
| `structure` | Редактируемый OLE-объект ChemDraw, вставленный в ячейку Word. Не заменяйте его PNG-картинкой. Из структуры программа получает формулу, молярную массу, SMILES и название. |
| `color` | Внешний вид, например `white solid`; `-` полностью отключает это поле для соединения. |
| `mp` | Температура плавления без `°C`; `-` отключает строку. |
| `Rf` | Значение и система, например `0.38 (petroleum ether : ethyl acetate = 7 : 1)`; `-` отключает поле. |
| `HRMS` | Экспериментальное найденное `m/z`; расчетное значение и ионная формула получаются из структуры. `-` отключает HRMS. |
| `Elemental_analysis` | Экспериментальные значения, например `C, 48.38; H, 3.69`; `-` отключает Anal. |
| `IR` | Список ИК-пиков, если столбец используется; `-` отключает IR. |

**3. Заполните Reaction schema**

| Столбец | Как заполнить |
|---|---|
| `Reagents` | `Reagent_1`, `Reagent_2`, ... для переменных структур из Scope; обычное имя (`NBS`, `DBP`) для постоянного реагента; `Solvent_CHCl3` для растворителя. `Reagent_1` является основой масштаба реакции. |
| `equiv.` | Эквиваленты относительно `Reagent_1`. Для `Reagent_1` обычно указывается `1`. |
| `MW, g/mol` | Молярная масса постоянного реагента. Для `Reagent_N` она извлекается из OLE-структуры в Scope и может быть пустой. |
| `Density, g/ml` | Плотность жидкого реагента, если в SI нужен рассчитанный объем. |
| `Concentration, M` | Концентрация раствора или растворителя, если объем должен рассчитываться из масштаба реакции. |

Число `Reagent_N` не ограничено двумя: добавляйте согласованные строки и столбцы `Reagent_3`, `Reagent_4` и далее. Имя объекта из Reaction schema должно совпадать с началом алиаса в SI template.

**4. Заполните Scope**

| Столбец | Как заполнить |
|---|---|
| `Reagent_N` | OLE-структура переменного реагента для соответствующей серии. |
| `Mass of Reagent_1, mg` | Реальная масса лимитирующего `Reagent_1`; по ней определяется масштаб реакции. |
| `Product` | OLE-структура продукта, используемая для расчета его молярной массы и названия. |
| `Product_number` | Тот же номер, что в Compound table и Spectra source. |
| `Mass of product, mg` | Изолированная масса продукта для расчета количества и выхода. |

**5. Как считаются загрузки**

1. Молярные массы переменных реагентов и продукта извлекаются из ChemDraw; для постоянных реагентов используются значения `MW` из Reaction schema.
2. Масштаб реакции рассчитывается по `Reagent_1`: `mmol = mass_mg / MW / equiv`.
3. Для каждого следующего реагента: `mmol = reaction_scale × equiv`, затем `mass_mg = mmol × MW`.
4. Для жидкости с плотностью: `volume_mcl = mass_mg / density_g_ml`. Для раствора с концентрацией: `volume_ml = reaction_scale_mmol / concentration_M`.
5. Для продукта: `product_mmol = product_mass_mg / product_MW`; `yield_percent = product_mmol / reaction_scale_mmol × 100`.
6. Алиасы `.g`, `.kg`, `.mol`, `.ml` и `.l` получают переводом рассчитанного базового значения; объем в mL выводится до двух знаков после запятой.

Если отсутствуют обе таблицы загрузок, SI все равно генерируется без расчетов. Если предоставлена только одна из них или номера продуктов не совпадают, программа показывает ошибку/предупреждение вместо молчаливого неверного расчета.

### Единый All-in-one DOCX

Файл разделяется неизменяемыми метками:

- `[AUTO SI: COMPOUND TABLE]` — обязательная таблица соединений;
- `[AUTO SI: REACTION SCHEMA]` — необязательные правила расчета реагентов;
- `[AUTO SI: SCOPE]` — необязательные данные серии;
- `[AUTO SI: SI TEMPLATE]` — необязательный текст и форматирование результата;
- `[AUTO SI: END]` — конец входных данных.

Во всех готовых `All_in_one_input.docx` уже собраны Compound table, Reaction schema, Scope и SI template. Можно редактировать шаблон прямо внутри секции `[AUTO SI: SI TEMPLATE]`; при запуске программа извлекает его и использует вместо отдельного файла. Если эту секцию удалить, применяется шаблон выбранного **Publication preset**. При наличии Reaction schema и Scope расчет загрузок включается автоматически. Publication preset, Spectra source, Output folder, MestReNova, `.mngp` и Processing остаются настройками приложения и не хранятся в объединенном DOCX.

## Processing

| Настройка | Значение |
|---|---|
| **Check support** | Проверять NMR, HRMS и элементный анализ во время генерации. |
| **Calculate elemental analysis** | Рассчитать Anal. по формуле, если поле не отключено знаком `-`. |
| **Spectra appendix** | `png` — картинки; `mnova` — кликабельные объекты; `none` — не добавлять appendix. |
| **1H/13C threshold** | Минимальная относительная высота пика. Увеличьте значение, если выбираются шум и примеси. |
| **Signal height** | Доля высоты страницы, занимаемая самым высоким сигналом. |
| **1H/13C ppm range** | Диапазон оси X на экспортируемой картинке. |
| **Highlight solvent peaks** | Показывать или скрывать определенные MestReNova пики растворителя. |
| **Baseline mode** | `auto`, `off`, `Bernstein` или `Whittaker`. |
| **Apply to 1H/13C** | Выбрать, для каких ядер выполнять baseline correction. |
| **Whittaker / polynomial parameters** | Экспертные параметры соответствующего алгоритма baseline. |

При проверке `13C NMR` программа автоматически читает структуру ChemDraw и считает симметрически эквивалентные ароматические углероды одним ожидаемым сигналом. Неароматические углероды остаются отдельными. Если структура или SMILES недоступны либо не согласуются с формулой, применяется строгая проверка по общему числу атомов C.

### Как работает химическая проверка

- **1H NMR:** программа суммирует интегралы вида `1H`, `2H`, `3H` в описании спектра и сравнивает сумму с числом атомов H в брутто-формуле.
- **13C NMR:** программа считает описанные сигналы и сравнивает их с ожидаемым числом. Симметрически эквивалентные ароматические атомы C из структуры считаются одним сигналом; при отсутствии структуры используется полное число C из формулы.
- **HRMS:** найденное `m/z` сравнивается с рассчитанным для формулы и выбранного аддукта; базовый предел расхождения составляет 5 ppm, а профиль журнала может добавить собственные требования.
- **Elemental analysis:** экспериментальные доли элементов сравниваются с рассчитанными по формуле.

Проверка не доказывает структуру соединения и не заменяет ручную интерпретацию спектра. Она выделяет несоответствия, которые нужно проверить в исходных данных, интегралах, peak picking или формуле.

## Формат Spectra source

```text
Spectra_source/
  2a/
    experiment_1H/fid
    experiment_13C/fid
  2b/
    experiment_1H/fid
    experiment_13C/fid
```

Названия внутренних экспериментов произвольны: тип ядра определяется по acquisition metadata. Набор номеров верхнего уровня должен совпадать с Compound table.

## Check

1. Загрузите `support_information.manifest.json` из `docx` старого запуска.
2. При необходимости укажите перемещенный `support_information.docx`.
3. Нажмите **Check support**.

Check проверяет manifest, порядок соединений, существование DOCX/артефактов, закладки и неразрешенные алиасы. Затем он повторно проверяет сохраненные в manifest данные 1H, 13C, HRMS и элементного анализа по брутто-формуле и записывает найденные несоответствия в `support_information.check_report.json`. MestReNova при этом не запускается: используются снимки данных, сохраненные во время Generate.

## Patch

Выберите **Existing output folder**, одну операцию и нажмите **Apply patch**. Исходный SI не изменяется, результат сохраняется в новой папке.

| Операция | Формат | Результат |
|---|---|---|
| **Renumber** | `2a=3a,2b=3b` | Меняет номера соединений и связанные ссылки. |
| **Remove** | `2a,2c` | Удаляет выбранные соединения и их appendix. |
| **Reorder** | Полный список, например `2c,2a,2b` | Меняет порядок блоков; нужно указать все номера. |
| **Swap compounds** | `2a=3a` | Меняет местами полные назначения соединений, сохраняя видимый порядок номеров. |
| **Reformat existing SI** | Выбрать целевой Publication preset | Пересобирает оформление из manifest, повторно используя готовые данные, спектры и ChemDraw OLE. |

Patch использует уже обработанные PNG и Mnova OLE и не запускает новую обработку спектров. Каждая операция создает новый run и не изменяет исходный SI.

## Add

1. Выберите **Previous output folder**: manifest и старый DOCX подставятся автоматически.
2. Загрузите Compound table и Spectra source только для новых соединений.
3. Выберите режим и нажмите **Add compounds**.

| Режим | Поведение |
|---|---|
| **Same series** | Повторно использует старые publication preset, template, Reaction schema и Processing settings. Новый Scope загружается отдельно. |
| **New method** | Позволяет выбрать новый publication preset и задать новые SI template, Reaction schema и Scope; настройки можно уточнить в Processing. |

Старые блоки не пересобираются. Дублирующийся номер или несовпадающие номера во входных файлах останавливают операцию с понятным сообщением.

## Профили журналов

В Generate доступен **Publication preset**. Сначала выберите журнал и нажмите **Apply**, затем при необходимости измените отдельные параметры в Processing. Профиль задает встроенный Word-шаблон, поля и шрифт документа, диапазоны спектров, MNGP по умолчанию, ориентацию appendix и дополнительные предупреждения проверки. Настройки Processing, измененные после применения профиля, считаются пользовательскими переопределениями и сохраняются в manifest. В Patch операция **Reformat existing SI** применяет другой профиль к уже созданному SI без повторного запуска обработки Mnova.

| Издательство | Доступные профили |
|---|---|
| **ACS** | The Journal of Organic Chemistry (JOC), Organic Letters (Org. Lett.), Journal of Medicinal Chemistry, JACS |
| **RSC** | Organic Chemistry |
| **Wiley** | Angewandte Chemie, Chemistry Europe / EurJOC, Archiv der Pharmazie |
| **Elsevier** | Tetrahedron, Tetrahedron Letters, European Journal of Medicinal Chemistry, Bioorganic & Medicinal Chemistry |
| **Nature Portfolio** | Nature Chemistry, Communications Chemistry |
| **Другие** | Molecules, Beilstein Journal of Organic Chemistry, Chemical Papers, General Organic SI |

Профили построены как общее правило издательства плюс уточнение конкретного журнала. Встроенные DOCX являются воспроизводимыми шаблонами программы на основе действующих author guidelines, а не официальными файлами издательств. Перед подачей сверяйтесь с сайтом журнала. Источники и дата проверки сохраняются в `support_information.manifest.json`; подробная матрица находится в [`docs/journal_si_template_requirements.md`](docs/journal_si_template_requirements.md).

## SI template и алиасы

Шаблон выглядит как будущий SI и одновременно задает стиль конкретной методики. Введите алиас в фигурных скобках и оформите его в Word жирным/курсивом: вставленное значение наследует это оформление. Объект до точки отвечает на вопрос «о чем данные» (`Product`, `Reagent_1`, `NBS`), а атрибут после точки отвечает на вопрос «какое значение нужно» (`name`, `mg`, `mmol`, `yield.percent`). Например, `{Reagent_1.name}` и `{Reagent_1.mmol}` относятся к одному объекту, но выводят разные его свойства.

Основные группы:

- `Product.*`: `{Product.name}`, `{Product.number}`, `{Product.structure}`, `{Product.mg}`, `{Product.mmol}`, `{Product.yield.percent}`, `{Product.appearance}`, `{Product.mp}`, `{Product.rf.value}`, `{Product.rf.system}`, `{Product.nmr.1h.picture}`, `{Product.nmr.13c.picture}`.
- `Reagent_N.*`: `.name`, `.mg`, `.g`, `.kg`, `.mmol`, `.mol`, `.mcl`, `.ml`, `.l`, `.eq`, `.number`.
- Именованные реагенты и растворители используют те же атрибуты: `{NBS.mg}`, `{AcOH.mcl}`, `{Solvent_MeCN.ml}`.
- NMR: `{nmr.1h.label}`, `{nmr.1h.conditions}`, `{nmr.1h.peaks}`, аналогично `nmr.13c`, плюс `{nmr.extra}`.
- HRMS: `{hrms.label}`, `{hrms.adduct}`, `{hrms.formula}`, `{hrms.calculated}`, `{hrms.found}`.
- Anal: `{anal.label}`, `{anal.formula}`, `{anal.calculated}`, `{anal.found}`.
- IR: `{ir.label}`, `{ir.method}`, `{ir.peaks}`.

Полная таблица с пояснением каждого алиаса находится в **Instructions → Template aliases**.

## Примеры

В репозитории и в **Instructions → Example files** находятся только три согласованных набора:

| Папка | Содержание |
|---|---|
| [`examples/example_1`](examples/example_1) | Первая серия, соединения 2a–2d; Spectra source как папка. |
| [`examples/example_2`](examples/example_2) | Продолжение серии, соединения 2e–2f. |
| [`examples/example_3`](examples/example_3) | Новая методика, соединения 3a, 3b, 3c, 3d, 3i; Spectra source как папка и zip. |

Во всех папках одинаковые имена, совпадающие с полями GUI: `Compound_table.docx`, `Spectra_source`, `SI_template.docx`, `Reaction_schema.docx`, `Scope.docx`.

## Результат

Каждый запуск создает `output/runs/YYYYMMDD_HHMMSS_имя/`:

| Папка | Содержимое |
|---|---|
| `docx/` | `support_information.docx`, `support_information.manifest.json` и `support_information.run_summary.json` |
| `input/` | копии Word-входов, профилей `.mngp` и использованного Spectra source |
| `spectra/` | каталог `processed_spectra/`, PNG и архив `processed_spectra.zip`, если спектры обрабатывались |
| `mnova/` | каталог `processed/` с обработанными и одиночными `.mnova` для кликабельных объектов |
| `logs/` | логи запуска, автоматизации Word/ChemDraw/Mnova и каталог `mnova_reports/` |
| `reports/` | текстовые отчеты NMR и отчеты проверки; операции Add/Patch также сохраняют собственный JSON-отчет |

Каждая генерация получает собственную папку, поэтому предыдущий SI не перезаписывается. В `mnova/processed/` сохраняются отдельные редактируемые `.mnova` для 1H и 13C, а в `spectra/` находятся соответствующие PNG. В режиме appendix `mnova` спектр можно открыть двойным щелчком по картинке непосредственно в `support_information.docx`, отредактировать в MestReNova и сохранить объект обратно в Word. Это позволяет вручную поправить подписи, пики и масштаб после автоматической обработки.

`support_information.manifest.json` связывает соединения, блоки DOCX, настройки и артефакты; он нужен для Check, Patch и Add. `support_information.run_summary.json` дает краткий итог запуска и список предупреждений. При ошибке сначала откройте `logs/` последнего запуска. Не держите выходной DOCX открытым во время повторной генерации: Word блокирует файл. Для сообщения об ошибке приложите run summary и папку `logs/`.
