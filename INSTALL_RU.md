# Установка Auto Support Generator beta 1.3

## Что установить заранее

- Windows 10 или 11, 64-bit;
- Microsoft Word desktop;
- ChemDraw/ChemOffice с поддержкой OLE;
- MestReNova.

Проверенные версии: ChemDraw `22.2.0.3300`, MestReNova `14.2.0-26256`. Используйте [официальную инструкцию загрузки ChemDraw](https://support.revvitysignals.com/hc/en-us/articles/4408210538132-How-do-I-download-the-MSI-installer-for-ChemDraw) и [официальную страницу загрузки Mnova](https://mestrelab.com/download). Обе программы требуют собственной действующей лицензии и не входят в установщик. Python для готовой сборки не нужен.

## Установка без Git и Python

1. На странице GitHub откройте [`installer/AutoSupportGeneratorSetup.exe`](installer/AutoSupportGeneratorSetup.exe) и нажмите **Download raw file**. Рядом находится файл [`AutoSupportGeneratorSetup.exe.sha256`](installer/AutoSupportGeneratorSetup.exe.sha256) для проверки контрольной суммы. Клонировать репозиторий не нужно.
2. Запустите скачанный файл двойным кликом.
3. Если Windows SmartScreen показывает предупреждение, проверьте источник файла, нажмите **Подробнее**, затем **Выполнить в любом случае**.
4. В поле **Installation folder** оставьте предложенный путь или нажмите **Browse...** и выберите другую папку.
5. Оставьте включенным создание ярлыков и нажмите **Install**.
6. После установки откройте **Auto Support Generator** с рабочего стола или из меню «Пуск».
7. Перед первой генерацией один раз вручную запустите Word, ChemDraw и MestReNova.

Предлагаемая папка установки для текущего пользователя:

```text
%LOCALAPPDATA%\AutoSupportGenerator
```

Установщик не загружает Python или химические программы из интернета и не требует прав администратора.

## Удаление

1. Откройте **Параметры Windows → Приложения → Установленные приложения**.
2. Найдите **Auto Support Generator** и нажмите **Удалить**.
3. Альтернативный путь: **Пуск → Auto Support Generator → Uninstall Auto Support Generator**.
4. Галочка **Keep generated output...** включена по умолчанию: программа и примеры удаляются, но output, GUI-настройки и неизвестные пользовательские файлы сохраняются.
5. Снимите эту галочку только для полного удаления всей папки установки; uninstaller запросит дополнительное подтверждение.

## Примеры

В установленной папке находятся пять полных наборов:

```text
examples\example_1
examples\example_2
examples\example_3
examples\example_4
examples\example_5
```

Каждый набор содержит редактируемые входы и ожидаемый `Reference_output.docx`, собранный с **Show scope**. Первые три примера показывают базовые серии, `example_4` — несколько методик, 28 соединений и необязательную РСА, `example_5` — реальные HSQC/HMBC. Наборы используют те же названия, что и поля GUI:

- `Compound_table.docx`;
- `Spectra_source` или `Spectra_source.zip`;
- `SI_template.docx`;
- `Reaction_schema.docx`;
- `Scope.docx`;
- `All_in_one_input.docx`;
- `Reference_output.docx`.

Примеры также можно скопировать из раздела **Instructions → Example files**.

## Первый запуск

1. На странице **Generate** выберите режим **Separate files** или **Single all-in-one DOCX**.
2. Для отдельного режима выберите `Compound_table.docx`; для единого — `All_in_one_input.docx`.
3. В **Spectra source** выберите zip или папку со спектрами, затем задайте **Output folder**.
4. При необходимости укажите CIF source, отдельные 1H/13C `.mngp` и включите **Show scope**.
5. Проверьте настройки на странице **Processing** и нажмите **Generate SI**.

В all-in-one сохраняйте неизменными метки `[AUTO SI: COMPOUND TABLE]`, `[AUTO SI: REACTION SCHEMA]`, `[AUTO SI: SCOPE]`, `[AUTO SI: SI TEMPLATE]`, `[AUTO SI: CRYSTALLOGRAPHY TEMPLATE]` и `[AUTO SI: END]`. Для нескольких серий используйте селекторы `[AUTO SI: REACTION 2a-2f]` перед соответствующими таблицами и `[AUTO SI: METHOD 2a-2f]` перед общими методиками; после методов поставьте `[AUTO SI: COMPOUND TEMPLATE]`.

Подробное описание всех функций находится в `README_RU.md` и внутри страницы **Instructions** приложения.

## Контакты

- Email: [lebedevdanilaaa@gmail.com](mailto:lebedevdanilaaa@gmail.com)
- Telegram: [@lebdanchem](https://t.me/lebdanchem)

При обращении приложите `support_information.run_summary.json` и папку `logs` проблемного запуска.

## Если программа не запускается

- Убедитесь, что файл скачан из официального репозитория и не заблокирован Windows.
- Проверьте, что Word, ChemDraw и MestReNova запускаются вручную.
- Если MestReNova не найдена, укажите путь к `MestReNova.exe` в Generate.
- Откройте папку `logs` последнего запуска для подробной диагностики.
