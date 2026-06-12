# Auto Support Generator beta.1.1

Это релизная ветка первой стабильной версии Auto Support Generator для
передачи коллегам. Ветка: `Auto_support_generator_beta.1.1`.

## Что делает программа

Программа автоматически собирает Supporting Information для органической химии:

- берет таблицу соединений из `.docx` с ChemDraw/ChemSketch OLE-структурами или
  из CSV;
- переносит структуры в итоговый `.docx`;
- читает физические свойства, HRMS и NMR-данные;
- может обработать raw `1H` и `13C` NMR через MestReNova;
- экспортирует картинки спектров и обработанные `.mnova`;
- проверяет соответствие NMR/HRMS структурной формуле;
- создает итоговый `support_information.docx` и папки с артефактами.

## Требования

Для полного workflow нужен Windows-компьютер с установленными desktop-программами:

- Microsoft Word;
- ChemDraw или ChemOffice для OLE-структур;
- MestReNova для обработки raw NMR.

Python пользователю готового установщика не нужен: он упакован внутрь
`AutoSupportGenerator.exe`.

## Установка

1. Скачайте `installer/AutoSupportGeneratorSetup.exe` из этой ветки.
2. Запустите установщик двойным кликом.
3. После установки на рабочем столе появится ярлык `Auto Support Generator`.
4. Ярлык должен открывать GUI программы. Если Windows спросит разрешение на
   запуск неизвестного приложения, разрешите запуск.

Программа устанавливается в:

```text
%LOCALAPPDATA%\AutoSupportGenerator
```

## Входные файлы

Минимальный вход:

- `Compound table` - Word `.docx` или CSV с таблицей соединений;
- `Output .docx` - путь, куда сохранить итоговый SI.

Опционально:

- `Spectra zip/folder` - zip-архив или обычная папка с raw NMR;
- `Template .docx` - Word-шаблон оформления;
- `Style config .yml` - настройки жирного/курсива, индексов и отдельных блоков;
- `MestReNova .exe` - путь к MestReNova, если автоопределение не сработало.

Структура spectra source:

```text
spectra/
  2a/
    any_name_1H/
      fid
      acqus
    any_name_13C/
      fid
      acqus
  2b/
    ...
```

Можно выбрать как саму папку `spectra`, так и `.zip` с такой же структурой.
Для одного соединения можно выбрать папку самого соединения, например `2a`.

## Выходные файлы

Рядом с выбранным output создаются:

- `support_information.docx` - итоговый Supporting Information;
- `processed_spectra.zip` - архив обработанных спектров;
- `processed_mnova/` - сохраненные `.mnova` файлы;
- `mnova_reports/` - текстовые NMR-отчеты;
- `logs/` - служебные логи и предупреждения.

## Что исправлено в этой релизной правке

- Ярлык на рабочем столе теперь создается с явным target на
  `AutoSupportGenerator.exe` и проверяется после сохранения.
- Поле `Spectra zip/folder` принимает не только zip, но и обычную папку.
- Zip extraction дополнительно проверяет path traversal, количество файлов и
  общий распакованный размер.
- Добавлены regression tests для этих сценариев.

## Быстрая проверка после установки

1. Откройте `Auto Support Generator` с рабочего стола.
2. Нажмите `Browse...` у `Compound table` и выберите пример
   `%LOCALAPPDATA%\AutoSupportGenerator\examples\test_input.docx`.
3. У `Spectra zip/folder` выберите
   `%LOCALAPPDATA%\AutoSupportGenerator\examples\test_input.zip`.
4. В `Output .docx` задайте путь в удобной папке, например на рабочем столе.
5. Нажмите `Generate SI`.

Если MestReNova не найдена автоматически, укажите путь к `MestReNova.exe`
в соответствующем поле.
