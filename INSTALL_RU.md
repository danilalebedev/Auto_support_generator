# Простая установка Auto Support Generator

Эта инструкция рассчитана на пользователя, который не знаком с Python и GitHub.

## Что нужно установить отдельно

Auto Support Generator автоматизирует сборку SI, но не заменяет внешние
программы. Для полного workflow на компьютере должны быть установлены:

- Windows 10/11;
- Microsoft Word desktop;
- ChemDraw или ChemOffice с поддержкой OLE-объектов;
- MestReNova.

Проверенные версии:

- ChemDraw `22.2.0.3300`;
- MestReNova `14.2.0-26256`.

Python устанавливать не нужно, если вы используете готовый установщик
`AutoSupportGeneratorSetup.exe`.

## Как установить программу

1. Скачайте `installer/AutoSupportGeneratorSetup.exe` из репозитория.
   На GitHub откройте папку `installer`, выберите `AutoSupportGeneratorSetup.exe`
   и нажмите `Download raw file`.
2. Дважды кликните `AutoSupportGeneratorSetup.exe`.
3. Дождитесь окончания установки.
4. Запустите программу через ярлык `Auto Support Generator` на рабочем столе или
   в меню Пуск.

Программа устанавливается в папку:

```text
%LOCALAPPDATA%\AutoSupportGenerator
```

Там будут лежать:

- `AutoSupportGenerator.exe` - сама программа;
- `style_config.example.yml` - пример настроек оформления;
- `examples/` - примеры входных данных и готового support;
- `README.md` и `INSTALL_RU.md` - инструкции.

## Как пользоваться

В окне программы:

1. В `Table type` выберите тип таблицы:
   - `Word table with ChemDraw objects` - основной вариант;
   - `CSV table` - вариант без OLE-структур.
2. В `Compound table` выберите таблицу с веществами.
3. В `Spectra zip` выберите zip-архив со спектрами.
4. В `Template .docx` можно выбрать Word-шаблон оформления.
5. В `Style config .yml` можно выбрать файл настроек оформления.
6. В `MestReNova .exe` можно вручную указать путь к MestReNova, если программа
   не нашла ее автоматически.
7. В `Output .docx` выберите, куда сохранить готовый support.
8. Оставьте `Check support` включенным, если хотите проверять ЯМР, HRMS и
   elemental analysis.
9. Нажмите `Generate SI`.

После завершения нажмите `Open output folder`, чтобы открыть папку с
результатами.

## Пример входных файлов

В установленной папке есть пример полного workflow:

```text
%LOCALAPPDATA%\AutoSupportGenerator\examples\test_input.docx
%LOCALAPPDATA%\AutoSupportGenerator\examples\test_input.zip
%LOCALAPPDATA%\AutoSupportGenerator\examples\example_output\support_information.docx
%LOCALAPPDATA%\AutoSupportGenerator\examples\example_output\processed_spectra.zip
```

В GUI выберите `Word table with ChemDraw objects`, затем укажите этот `.docx` в
поле `Compound table`, а `.zip` - в поле `Spectra zip`.

Файлы в `example_output` - это пример результата: готовый SI и архив с
обработанными спектрами.

## Что получается на выходе

В выбранной output-папке будут созданы:

- `support_information.docx` - готовый SI;
- `processed_spectra.zip` - архив с обработанными спектрами, PNG-картинками и
  `.mnova` файлами;
- `processed_spectra/` - те же файлы в виде обычных папок;
- `logs/` - служебные файлы для отладки.

## Если готового установщика нет

Можно запустить программу из исходников:

1. Скачайте проект с GitHub через `Code` -> `Download ZIP`.
2. Распакуйте архив.
3. Установите Python 3.12.
4. Запустите `Setup Auto SI Generator.bat`.
5. Запустите `Run Auto SI Generator.bat`.

Этот путь нужен в основном разработчикам или для пересборки установщика.

## Что делать, если программа не запускается

Проверьте, что Word, ChemDraw и MestReNova открываются вручную и активированы.
Если ошибка возникает при обработке спектров, укажите путь к `MestReNova.exe`
в поле `MestReNova .exe`. Программа также ищет MestReNova через `PATH`, реестр
Windows, типовые папки `Program Files` и переменные окружения
`AUTO_SUPPORT_MNOVA_EXE`, `AUTO_SI_MNOVA_EXE`, `MNOVA_EXE`, `MESTRENOVA_EXE`.

Если на компьютере имя пользователя или путь к данным содержит кириллицу,
программа должна работать автоматически: для ChemDraw/MestReNova создается
временная ASCII-папка `C:\Users\Public\AutoSupportGenerator\temp`. Если эта
папка недоступна, создайте любую папку без кириллицы и укажите ее в переменной
окружения `AUTO_SUPPORT_TEMP_DIR`.
