# Установка Auto Support Generator beta 1.2

## Что установить заранее

- Windows 10 или 11, 64-bit;
- Microsoft Word desktop;
- ChemDraw/ChemOffice с поддержкой OLE;
- MestReNova.

Проверенные версии: ChemDraw `22.2.0.3300`, MestReNova `14.2.0-26256`. Используйте [официальную инструкцию загрузки ChemDraw](https://support.revvitysignals.com/hc/en-us/articles/4408210538132-How-do-I-download-the-MSI-installer-for-ChemDraw) и [официальную страницу загрузки Mnova](https://mestrelab.com/download). Обе программы требуют собственной действующей лицензии и не входят в установщик. Python для готовой сборки не нужен.

## Установка без Git и Python

1. На странице GitHub откройте [`installer/AutoSupportGeneratorSetup.exe`](installer/AutoSupportGeneratorSetup.exe) и нажмите **Download raw file**. Клонировать репозиторий не нужно.
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

В установленной папке находятся три полных набора:

```text
examples\example_1
examples\example_2
examples\example_3
```

Каждый набор использует те же названия, что и поля GUI:

- `Compound_table.docx`;
- `Spectra_source` или `Spectra_source.zip`;
- `SI_template.docx`;
- `Reaction_schema.docx`;
- `Scope.docx`.

Примеры также можно скопировать из раздела **Instructions → Example files**.

## Первый запуск

1. На странице **Generate** выберите `Compound_table.docx`.
2. В **Spectra source** выберите zip или папку со спектрами.
3. Выберите **Output folder**.
4. При необходимости укажите SI template, отдельные 1H/13C `.mngp`, Reaction schema и Scope.
5. Проверьте настройки на странице **Processing**.
6. Нажмите **Generate SI**.

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
